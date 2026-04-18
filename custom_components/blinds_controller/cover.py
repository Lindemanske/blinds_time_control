"""Cover platform for Blinds Time Control integration."""
from __future__ import annotations

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverEntityFeature,
    CoverEntity,
)
from homeassistant.helpers import entity_platform
from homeassistant.core import callback, Event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval, async_track_state_change_event
from homeassistant.helpers.aiohttp_client import async_get_clientsession

import logging
from datetime import datetime, timedelta, timezone
import asyncio

from .calculator import TravelCalculator, TravelStatus
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_KNOWN_POSITION = "set_known_position"
SERVICE_SET_KNOWN_TILT_POSITION = "set_known_tilt_position"

# Service name constants (avoid deprecated imports from homeassistant.const)
_CMD_CLOSE = "close_cover"
_CMD_OPEN = "open_cover"
_CMD_STOP = "stop_cover"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the cover platform."""
    name = entry.title
    device_id = entry.entry_id
    async_add_entities([BlindsCover(hass, entry, name, device_id)])

    # Register custom services
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_KNOWN_POSITION,
        {},
        "set_known_position"
    )
    platform.async_register_entity_service(
        SERVICE_SET_KNOWN_TILT_POSITION,
        {},
        "set_known_tilt_position"
    )


class BlindsCover(CoverEntity, RestoreEntity):
    """Representation of a time-based cover."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        name: str,
        device_id: str,
    ) -> None:
        """Initialize the cover."""
        self.hass = hass
        self.entry = entry
        self._attr_name = name
        self._attr_unique_id = f"cover_timebased_synced_uuid_{device_id}"
        self._state = None
        self._available = True

        # Travel times
        self._travel_time_down = entry.data["time_down"]
        self._travel_time_up = entry.data["time_up"]
        self._travel_tilt_closed = entry.data["tilt_closed"]
        self._travel_tilt_open = entry.data["tilt_open"]

        # Entity IDs
        self._up_switch_entity_id = entry.data["entity_up"]
        self._down_switch_entity_id = entry.data["entity_down"]

        # Add-ons configuration
        self._timed_control_down = entry.data["timed_control_down"]
        self._time_to_roll_up = entry.data["time_to_roll_up"]
        self._timed_control_up = entry.data["timed_control_up"]
        self._time_to_roll_down = entry.data["time_to_roll_down"]
        self._delay_control = entry.data["delay_control"]
        self._delay_sunrise = entry.data["delay_sunrise"]
        self._delay_sunset = entry.data["delay_sunset"]
        self._night_lights = entry.data["night_lights"]
        self._entity_night_lights = entry.data["entity_night_lights"]
        self._tilting_day = entry.data["tilting_day"]
        self._protect_the_blinds = entry.data["protect_the_blinds"]
        self._set_wind_speed = entry.data["wind_speed"]
        self._wmo_code = entry.data["wmo_code"]
        self._netamo_enable = entry.data["netamo_enable"]
        self._netamo_speed_entity = entry.data["netamo_speed_entity"]
        self._netamo_speed = entry.data["netamo_speed"]
        self._netamo_gust_entity = entry.data["netamo_gust_entity"]
        self._netamo_gust = entry.data["netamo_gust"]
        self._send_stop_at_end = entry.data["send_stop_at_end"]
        self._netamo_rain_entity = entry.data["netamo_rain_entity"]
        self._netamo_rain = entry.data["netamo_rain"]

        # Initialize Netatmo state values
        if self._netamo_speed_entity is not None:
            state = self.hass.states.get(self._netamo_speed_entity)
            self._wind_speed = state.state if state else None
        else:
            self._wind_speed = None

        if self._netamo_gust_entity is not None:
            state = self.hass.states.get(self._netamo_gust_entity)
            self._gust_speed = state.state if state else None
        else:
            self._gust_speed = None

        if self._netamo_rain_entity is not None:
            state = self.hass.states.get(self._netamo_rain_entity)
            self._netamo_cur_rain = state.state if state else None
        else:
            self._netamo_cur_rain = None

        # Sun sensors
        sun_dawn = self.hass.states.get("sensor.sun_next_dawn")
        self._sun_next_sunrise = sun_dawn.state if sun_dawn else None
        sun_dusk = self.hass.states.get("sensor.sun_next_dusk")
        self._sun_next_sunset = sun_dusk.state if sun_dusk else None

        self._target_position = 0
        self._target_tilt_position = 0
        self._weather_check_counter = 0
        self._tilt_check_counter = 0
        self._unsubscribe_auto_updater = None

        # Initialize travel calculators
        self.travel_calc = TravelCalculator(
            self._travel_time_down,
            self._travel_time_up,
        )

        if self.has_tilt_support():
            self.tilt_calc = TravelCalculator(
                self._travel_tilt_closed,
                self._travel_tilt_open,
            )
        else:
            self.tilt_calc = None

        self._switch_close_state = "off"
        self._switch_open_state = "off"
        self._night_lights_state = "off"

    async def sun_state_changed(self, event: Event) -> None:
        """Handle sun state changes."""
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")

        if new_state is not None:
            if entity_id == "sensor.sun_next_dawn":
                self._sun_next_sunrise = new_state.state
            elif entity_id == "sensor.sun_next_dusk":
                self._sun_next_sunset = new_state.state

    @property
    def device_class(self) -> str | None:
        """Return the class of this device."""
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return {
            "entity_up": self._up_switch_entity_id,
            "entity_down": self._down_switch_entity_id,
            "time_up": self._travel_time_up,
            "time_down": self._travel_time_down,
            "tilt_open": self._travel_tilt_open,
            "tilt_closed": self._travel_tilt_closed,
        }

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

        if self.has_tilt_support():
            supported_features |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.SET_TILT_POSITION
                | CoverEntityFeature.STOP_TILT
            )

        return supported_features

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        return self.travel_calc.current_position()

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt."""
        if self.has_tilt_support():
            return self.tilt_calc.current_position()
        return None

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        return (
            self.travel_calc.is_traveling()
            and self.travel_calc.travel_direction == TravelStatus.DIRECTION_UP
        )

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        return (
            self.travel_calc.is_traveling()
            and self.travel_calc.travel_direction == TravelStatus.DIRECTION_DOWN
        )

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        return self.travel_calc.is_closed()

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return True

    async def async_set_cover_position(self, **kwargs) -> None:
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            _LOGGER.debug("async_set_cover_position: %d", position)
            await self.set_position(position)

    async def async_set_cover_tilt_position(self, **kwargs) -> None:
        """Move the cover tilt to a specific position."""
        if self.has_tilt_support() and ATTR_TILT_POSITION in kwargs:
            tilt_position = kwargs[ATTR_TILT_POSITION]
            _LOGGER.debug("async_set_cover_tilt_position: %d", tilt_position)
            await self.set_tilt_position(tilt_position)

    async def async_close_cover(self, **kwargs) -> None:
        """Turn the device close."""
        _LOGGER.debug("async_close_cover")
        if not self.has_tilt_support():
            self._target_position = 0
            self.travel_calc.start_travel_down()
            self.start_auto_updater()
            await self._async_handle_command(_CMD_CLOSE)
        else:
            self.update_tilt_before_travel(_CMD_CLOSE)
            self._target_position = 0
            self.travel_calc.start_travel_down()
            self.start_auto_updater()
            await self._async_handle_command(_CMD_CLOSE)

    async def async_open_cover(self, **kwargs) -> None:
        """Turn the device open."""
        _LOGGER.debug("async_open_cover")
        if not self.has_tilt_support():
            self._target_position = 100
            self.travel_calc.start_travel_up()
            self.start_auto_updater()
            await self._async_handle_command(_CMD_OPEN)
        else:
            self.update_tilt_before_travel(_CMD_OPEN)
            self._target_position = 100
            self.travel_calc.start_travel_up()
            self.start_auto_updater()
            await self._async_handle_command(_CMD_OPEN)

    async def async_stop_cover(self, **kwargs) -> None:
        """Turn the device stop."""
        _LOGGER.debug("async_stop_cover")
        self._handle_my_button()
        await self._async_handle_command(_CMD_STOP)

    async def async_open_cover_tilt(self, **kwargs) -> None:
        """Open the cover tilt."""
        if self.has_tilt_support():
            _LOGGER.debug("async_open_cover_tilt")
            self._target_tilt_position = 100
            self.tilt_calc.start_travel_up()
            self.start_auto_updater()

    async def async_close_cover_tilt(self, **kwargs) -> None:
        """Close the cover tilt."""
        if self.has_tilt_support():
            _LOGGER.debug("async_close_cover_tilt")
            self._target_tilt_position = 0
            self.tilt_calc.start_travel_down()
            self.start_auto_updater()

    async def async_stop_cover_tilt(self, **kwargs) -> None:
        """Stop the cover tilt."""
        if self.has_tilt_support():
            _LOGGER.debug("async_stop_cover_tilt")
            self._handle_my_button()

    async def set_position(self, position: int) -> None:
        """Move cover to a designated position."""
        _LOGGER.debug("set_position")
        current_position = self.travel_calc.current_position()
        _LOGGER.debug(
            "set_position :: current_position: %d, new_position: %d",
            current_position,
            position,
        )

        if not self.has_tilt_support():
            self._target_position = position
            if position < current_position:
                self.travel_calc.start_travel(position)
                self.start_auto_updater()
                await self._async_handle_command(_CMD_CLOSE)
            elif position > current_position:
                self.travel_calc.start_travel(position)
                self.start_auto_updater()
                await self._async_handle_command(_CMD_OPEN)
        else:
            self._target_position = position
            if position < current_position:
                self.update_tilt_before_travel(_CMD_CLOSE)
                self.travel_calc.start_travel(position)
                self.start_auto_updater()
                await self._async_handle_command(_CMD_CLOSE)
            elif position > current_position:
                self.update_tilt_before_travel(_CMD_OPEN)
                self.travel_calc.start_travel(position)
                self.start_auto_updater()
                await self._async_handle_command(_CMD_OPEN)

    async def set_tilt_position(self, tilt_position: int) -> None:
        """Move cover tilt to a designated position."""
        if self.has_tilt_support():
            _LOGGER.debug("set_tilt_position")
            current_tilt_position = self.tilt_calc.current_position()
            _LOGGER.debug(
                "set_tilt_position :: current: %d, new: %d",
                current_tilt_position,
                tilt_position,
            )

            self._target_tilt_position = tilt_position
            if tilt_position != current_tilt_position:
                self.tilt_calc.start_travel(tilt_position)
                self.start_auto_updater()

    def update_tilt_before_travel(self, command: str) -> None:
        """Update tilt position before travel."""
        if not self.has_tilt_support():
            return

        if command == _CMD_CLOSE:
            self._target_tilt_position = 0
            self.tilt_calc.start_travel_down()
        elif command == _CMD_OPEN:
            self._target_tilt_position = 100
            self.tilt_calc.start_travel_up()

    def set_known_position(self, **kwargs) -> None:
        """Set known position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            _LOGGER.debug("set_known_position: %d", position)
            self.travel_calc.set_position(position)
            self.async_write_ha_state()

    def set_known_tilt_position(self, **kwargs) -> None:
        """Set known tilt position."""
        if self.has_tilt_support() and ATTR_TILT_POSITION in kwargs:
            tilt_position = kwargs[ATTR_TILT_POSITION]
            _LOGGER.debug("set_known_tilt_position: %d", tilt_position)
            self.tilt_calc.set_position(tilt_position)
            self.async_write_ha_state()

    def start_auto_updater(self) -> None:
        """Start the autoupdater to update HA state while cover is moving."""
        _LOGGER.debug("start_auto_updater")
        if self._unsubscribe_auto_updater is None:
            _LOGGER.debug("init _unsubscribe_auto_updater")
            interval = timedelta(seconds=0.1)
            self._unsubscribe_auto_updater = async_track_time_interval(
                self.hass, self.auto_updater_hook, interval
            )

    @callback
    def auto_updater_hook(self, now) -> None:
        """Call for the autoupdater."""
        _LOGGER.debug("auto_updater_hook")
        self.async_write_ha_state()
        if self.position_reached():
            _LOGGER.debug("auto_updater_hook :: position_reached")
            self.stop_auto_updater()
        self.hass.async_create_task(self.auto_stop_if_necessary())

    def stop_auto_updater(self) -> None:
        """Stop the autoupdater."""
        _LOGGER.debug("stop_auto_updater")
        if self._unsubscribe_auto_updater is not None:
            self._unsubscribe_auto_updater()
            self._unsubscribe_auto_updater = None

    async def add_ons(self, now) -> None:
        """Handle add-on automations."""
        current_time = datetime.now(timezone.utc)
        formatted_time = current_time.strftime("%H:%M")

        # Timed control for rolling down
        if self._timed_control_down and formatted_time == self._time_to_roll_down:
            _LOGGER.info("Time to roll down: %s", formatted_time)
            await self.async_close_cover()

        # Timed control for rolling up
        if self._timed_control_up and formatted_time == self._time_to_roll_up:
            _LOGGER.info("Time to roll up: %s", formatted_time)
            await self.async_open_cover()

        # Delay control based on sunrise/sunset
        if self._delay_control:
            if self._sun_next_sunrise:
                try:
                    sunrise_time = datetime.fromisoformat(
                        self._sun_next_sunrise.replace("Z", "+00:00")
                    )
                    delayed_sunrise = sunrise_time + timedelta(minutes=self._delay_sunrise)
                    if current_time.hour == delayed_sunrise.hour and current_time.minute == delayed_sunrise.minute:
                        _LOGGER.info("Delayed sunrise triggered")
                        await self.async_open_cover()
                except Exception as e:
                    _LOGGER.error("Error parsing sunrise time: %s", e)

            if self._sun_next_sunset:
                try:
                    sunset_time = datetime.fromisoformat(
                        self._sun_next_sunset.replace("Z", "+00:00")
                    )
                    delayed_sunset = sunset_time + timedelta(minutes=self._delay_sunset)
                    if current_time.hour == delayed_sunset.hour and current_time.minute == delayed_sunset.minute:
                        _LOGGER.info("Delayed sunset triggered")
                        await self.async_close_cover()
                except Exception as e:
                    _LOGGER.error("Error parsing sunset time: %s", e)

        # Night lights control
        if self._night_lights and self._entity_night_lights:
            night_light_state = self.hass.states.get(self._entity_night_lights)
            if night_light_state and night_light_state.state == "on":
                current_position = self.travel_calc.current_position()
                if current_position == 0:
                    _LOGGER.info("Night light is on, opening cover")
                    await self.async_open_cover()

        # Tilt during day
        if self._tilting_day and self.has_tilt_support():
            if self._tilt_check_counter >= 10:
                current_position = self.travel_calc.current_position()
                current_tilt = self.tilt_calc.current_position()
                if 10 <= current_time.hour < 18 and current_position == 100 and current_tilt != 50:
                    _LOGGER.info("Setting tilt to 50%% during day")
                    await self.set_tilt_position(50)
                self._tilt_check_counter = 0
            else:
                self._tilt_check_counter += 1

        # Weather protection
        if self._protect_the_blinds or self._netamo_enable:
            if self._weather_check_counter >= 5:
                await self._check_weather_protection()
                self._weather_check_counter = 0
            else:
                self._weather_check_counter += 1

        _LOGGER.info("Current time: %s", formatted_time)

    async def _check_weather_protection(self) -> None:
        """Check weather conditions and protect blinds if needed."""
        # Netatmo sensor protection
        if self._netamo_enable:
            protect = False

            if self._netamo_speed_entity:
                wind_state = self.hass.states.get(self._netamo_speed_entity)
                if wind_state:
                    try:
                        wind_speed = float(wind_state.state)
                        if wind_speed >= self._netamo_speed:
                            _LOGGER.warning("Wind speed %s exceeds limit %s", wind_speed, self._netamo_speed)
                            protect = True
                    except (ValueError, TypeError):
                        pass

            if self._netamo_gust_entity:
                gust_state = self.hass.states.get(self._netamo_gust_entity)
                if gust_state:
                    try:
                        gust_speed = float(gust_state.state)
                        if gust_speed >= self._netamo_gust:
                            _LOGGER.warning("Gust speed %s exceeds limit %s", gust_speed, self._netamo_gust)
                            protect = True
                    except (ValueError, TypeError):
                        pass

            if self._netamo_rain_entity:
                rain_state = self.hass.states.get(self._netamo_rain_entity)
                if rain_state:
                    try:
                        rain = float(rain_state.state)
                        if rain >= self._netamo_rain:
                            _LOGGER.warning("Rain %s exceeds limit %s", rain, self._netamo_rain)
                            protect = True
                    except (ValueError, TypeError):
                        pass

            if protect:
                current_position = self.travel_calc.current_position()
                if current_position != 0:
                    _LOGGER.info("Weather protection: closing cover")
                    await self.async_close_cover()

        # Open-Meteo API protection
        if self._protect_the_blinds:
            try:
                latitude, longitude = self.get_location_coordinates(self.hass)
                url = (
                    f"https://api.open-meteo.com/v1/forecast"
                    f"?latitude={latitude}&longitude={longitude}&current_weather=true"
                )

                session = async_get_clientsession(self.hass)
                async with session.get(url, timeout=10) as response:
                    data = await response.json()

                    if "current_weather" in data:
                        wind_speed = data["current_weather"].get("windspeed", 0)
                        weather_code = data["current_weather"].get("weathercode", 0)

                        if wind_speed >= self._set_wind_speed or weather_code >= self._wmo_code:
                            current_position = self.travel_calc.current_position()
                            if current_position != 0:
                                _LOGGER.warning(
                                    "Weather protection triggered: wind=%s, code=%s",
                                    wind_speed,
                                    weather_code,
                                )
                                await self.async_close_cover()

                        _LOGGER.info("Wind speed: %s, Weather code: %s", wind_speed, weather_code)
            except Exception as e:
                _LOGGER.error("Error retrieving weather data: %s", e)

    def get_location_coordinates(self, hass: HomeAssistant) -> tuple[float, float]:
        """Get latitude and longitude from Home Assistant configuration."""
        latitude = hass.config.latitude
        longitude = hass.config.longitude
        return latitude, longitude

    def position_reached(self) -> bool:
        """Return if cover has reached its final position."""
        return self.travel_calc.position_reached() and (
            not self.has_tilt_support() or self.tilt_calc.position_reached()
        )

    def has_tilt_support(self) -> bool:
        """Return whether cover supports tilt."""
        return (
            self.entry.data.get("tilt_open") is not None
            and self.entry.data.get("tilt_closed") is not None
            and self._travel_tilt_open != 0
            and self._travel_tilt_closed != 0
        )

    async def _handle_state_changed(self, event: Event) -> None:
        """Handle state changes of switches."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        entity_id = event.data.get("entity_id")

        if new_state is None or old_state is None:
            return

        if new_state.state == old_state.state:
            return

        if entity_id == self._entity_night_lights:
            if self._night_lights_state == new_state.state:
                return
            self._night_lights_state = new_state.state

        if entity_id == self._down_switch_entity_id:
            if self._switch_close_state == new_state.state:
                return
            self._switch_close_state = new_state.state
        elif entity_id == self._up_switch_entity_id:
            if self._switch_open_state == new_state.state:
                return
            self._switch_open_state = new_state.state
        else:
            return

        # Handle switch state combinations
        if self._switch_open_state == "off" and self._switch_close_state == "off":
            self._handle_my_button()
        elif self._switch_open_state == "on" and self._switch_close_state == "on":
            self._handle_my_button()
            if entity_id == self._down_switch_entity_id:
                await self.hass.services.async_call(
                    "homeassistant",
                    "turn_off",
                    {"entity_id": self._up_switch_entity_id},
                    False,
                )
            if entity_id == self._up_switch_entity_id:
                await self.hass.services.async_call(
                    "homeassistant",
                    "turn_off",
                    {"entity_id": self._down_switch_entity_id},
                    False,
                )
        elif self._switch_open_state == "on" and self._switch_close_state == "off":
            if not self.has_tilt_support():
                if self._target_position not in (0, 100):
                    self.travel_calc.start_travel(self._target_position)
                else:
                    self._target_position = 100
                    self.travel_calc.start_travel_up()
                self.start_auto_updater()
            else:
                if not self.tilt_calc.is_traveling():
                    self.update_tilt_before_travel(_CMD_OPEN)
                    if self._target_position not in (0, 100):
                        self.travel_calc.start_travel(self._target_position)
                    else:
                        self._target_position = 100
                        self.travel_calc.start_travel_up()
                    self.start_auto_updater()
        elif self._switch_open_state == "off" and self._switch_close_state == "on":
            if not self.has_tilt_support():
                if self._target_position not in (0, 100):
                    self.travel_calc.start_travel(self._target_position)
                else:
                    self._target_position = 0
                    self.travel_calc.start_travel_down()
                self.start_auto_updater()
            else:
                if not self.tilt_calc.is_traveling():
                    self.update_tilt_before_travel(_CMD_CLOSE)
                    if self._target_position not in (0, 100):
                        self.travel_calc.start_travel(self._target_position)
                    else:
                        self._target_position = 0
                        self.travel_calc.start_travel_down()
                    self.start_auto_updater()

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.async_on_remove(
            self.hass.bus.async_listen("state_changed", self._handle_state_changed)
        )

        # Set up periodic time update (store unsubscribe for cleanup)
        self.async_on_remove(
            async_track_time_interval(self.hass, self.add_ons, timedelta(minutes=1))
        )

        # Track sun sensors
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, "sensor.sun_next_dawn", self.sun_state_changed
            )
        )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, "sensor.sun_next_dusk", self.sun_state_changed
            )
        )

        # Restore previous state
        old_state = await self.async_get_last_state()

        if (
            old_state is not None
            and self.travel_calc is not None
            and old_state.attributes.get(ATTR_CURRENT_POSITION) is not None
        ):
            self.travel_calc.set_position(
                int(old_state.attributes.get(ATTR_CURRENT_POSITION))
            )

            if (
                self.has_tilt_support()
                and old_state.attributes.get(ATTR_CURRENT_TILT_POSITION) is not None
            ):
                self.tilt_calc.set_position(
                    int(old_state.attributes.get(ATTR_CURRENT_TILT_POSITION))
                )

    def _handle_my_button(self) -> None:
        """Handle MY button press (stop)."""
        if self.travel_calc.is_traveling() or (
            self.has_tilt_support() and self.tilt_calc.is_traveling()
        ):
            self.travel_calc.stop()
            if self.has_tilt_support():
                self.tilt_calc.stop()
            self.stop_auto_updater()

    async def auto_stop_if_necessary(self) -> None:
        """Auto stop if position reached."""
        current_position = self.travel_calc.current_position()
        current_tilt_position = (
            self.tilt_calc.current_position() if self.has_tilt_support() else None
        )

        if self.position_reached():
            self.travel_calc.stop()
            if self.has_tilt_support():
                self.tilt_calc.stop()
                if ((current_position > 0) and (current_position < 100)) or (
                    (current_tilt_position > 0) and (current_tilt_position < 100)
                ):
                    await self._async_handle_command(_CMD_STOP)
                else:
                    if self._send_stop_at_end:
                        await self._async_handle_command(_CMD_STOP)
            else:
                if (current_position > 0) and (current_position < 100):
                    await self._async_handle_command(_CMD_STOP)
                else:
                    if self._send_stop_at_end:
                        await self._async_handle_command(_CMD_STOP)

    async def _async_handle_command(self, command: str, *args) -> None:
        """Handle commands to control the cover switches."""
        if command == "close_cover":
            self._state = False
            await self.hass.services.async_call(
                "homeassistant",
                "turn_off",
                {"entity_id": self._up_switch_entity_id},
                False,
            )
            await self.hass.services.async_call(
                "homeassistant",
                "turn_on",
                {"entity_id": self._down_switch_entity_id},
                False,
            )
        elif command == "open_cover":
            self._state = True
            await self.hass.services.async_call(
                "homeassistant",
                "turn_off",
                {"entity_id": self._down_switch_entity_id},
                False,
            )
            await self.hass.services.async_call(
                "homeassistant",
                "turn_on",
                {"entity_id": self._up_switch_entity_id},
                False,
            )
        elif command == "stop_cover":
            self._state = True
            await self.hass.services.async_call(
                "homeassistant",
                "turn_off",
                {"entity_id": self._up_switch_entity_id},
                False,
            )
            await self.hass.services.async_call(
                "homeassistant",
                "turn_off",
                {"entity_id": self._down_switch_entity_id},
                False,
            )

        self.async_write_ha_state()
