# Changelog - Blinds Time Control v2.0.1

## Updates voor Home Assistant 2026.4.2 Compatibiliteit

### Wijzigingen in v2.0.1

#### 1. **config_flow.py**
- ✅ Verwijderd: `OptionsFlow.__init__(config_entry)` — volledig verwijderd als breaking change in HA 2026.4.x
- ✅ Aangepast: `async_get_options_flow` geeft nu `BlindsOptionsFlow()` terug zonder argument; `self.config_entry` wordt automatisch gezet door de HA basisklasse

#### 2. **cover.py**
- ✅ Verwijderd: `SERVICE_CLOSE_COVER`, `SERVICE_OPEN_COVER`, `SERVICE_STOP_COVER` imports uit `homeassistant.const` (deprecated en verwijderd in HA 2026.x); vervangen door lokale string-constanten `_CMD_CLOSE`, `_CMD_OPEN`, `_CMD_STOP`
- ✅ Vervangen: blokkerende `urllib.request.urlopen()` call voor Open-Meteo API → volledig async via `aiohttp` / `async_get_clientsession(hass)` (blokkerende I/O in de event loop is niet toegestaan in modern HA)
- ✅ Verwijderd: `import urllib.request` en `import json` (niet meer nodig)
- ✅ Toegevoegd: `from homeassistant.helpers.aiohttp_client import async_get_clientsession`
- ✅ Verbeterd: alle event listeners en timers in `async_added_to_hass` worden nu correct afgemeld via `self.async_on_remove(...)` bij verwijderen van de entiteit (geheugenlek voorkomen)

Upgraded to comply with version 2026.4.2 of home assistant. Assisted by Claude.

---



## Updates voor Home Assistant 2025 Compatibiliteit

Deze versie is volledig geüpdatet om compatibel te zijn met de laatste versie van Home Assistant (2025). Alle deprecated code is vervangen door moderne alternatieven.

### Belangrijkste Wijzigingen

#### 1. **manifest.json**
- ✅ Toegevoegd: `integration_type: "device"` (verplicht vanaf HA 2024.x)
- ✅ Gewijzigd: `iot_class` van `"assumed_state"` naar `"calculated"` (beter passend)
- ✅ Versie verhoogd naar `2.0.0`

#### 2. **__init__.py**
- ✅ Vervangen: `async_forward_entry_setup()` → `async_forward_entry_setups()` (nieuwe methode)
- ✅ Vervangen: `async_forward_entry_unload()` → `async_unload_platforms()` (nieuwe methode)
- ✅ Toegevoegd: `async_reload_entry()` functie voor betere options flow ondersteuning
- ✅ Toegevoegd: Update listener voor config entry changes
- ✅ Toegevoegd: Type hints (`from __future__ import annotations`)
- ✅ Toegevoegd: Platform lijst met `Platform.COVER`

#### 3. **config_flow.py**
- ✅ Verwijderd: `CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL` (deprecated sinds HA 2022.x)
- ✅ Toegevoegd: Type hints en betere documentatie
- ✅ Verbeterd: Code formatting en leesbaarheid

#### 4. **cover.py** (Grote refactoring)
- ✅ Vervangen: `async_track_state_change()` → `async_track_state_change_event()` (nieuwe API)
- ✅ Vervangen: `device_state_attributes` → `extra_state_attributes` (nieuwe property naam)
- ✅ Verbeterd: Event handling met correct `Event` type
- ✅ Toegevoegd: `AddEntitiesCallback` type hint voor `async_setup_entry`
- ✅ Toegevoegd: `_attr_has_entity_name = True` voor betere entity naming
- ✅ Toegevoegd: `_attr_name` en `_attr_unique_id` als class attributes
- ✅ Verbeterd: Error handling bij het ophalen van entity states
- ✅ Verbeterd: Type hints overal toegevoegd (`-> None`, `-> bool`, etc.)
- ✅ Verbeterd: Service registratie verplaatst naar `async_setup_entry`
- ✅ Toegevoegd: Return type annotations voor alle methodes
- ✅ Verbeterd: Walrus operator (`:=`) voor betere code in unload functie

#### 5. **Algemene Verbeteringen**
- ✅ Alle bestanden: Toegevoegd `from __future__ import annotations` voor betere type hints
- ✅ Code formatting volgens moderne Python/HA standards
- ✅ Betere error handling en logging
- ✅ Verbeterde documentatie in docstrings

### Deprecated Functies Verwijderd

| Oude Code | Nieuwe Code | Reden |
|-----------|-------------|-------|
| `CONNECTION_CLASS` | Verwijderd | Deprecated sinds HA 2022.x |
| `async_forward_entry_setup()` | `async_forward_entry_setups()` | Nieuwe multi-platform methode |
| `async_forward_entry_unload()` | `async_unload_platforms()` | Nieuwe multi-platform methode |
| `async_track_state_change()` | `async_track_state_change_event()` | Event-based state tracking |
| `device_state_attributes` | `extra_state_attributes` | Property hernoemd |

### Compatibiliteit

✅ **Getest voor Home Assistant 2025.x**
✅ **Backwards compatible met HA 2024.x**
⚠️ **Niet compatibel met HA 2023.x of ouder** (vanwege async_forward_entry_setups)

### Installatie

1. Vervang de oude `custom_components/blinds_controller` map met deze nieuwe versie
2. Herstart Home Assistant
3. Controleer de logs op eventuele warnings of errors
4. Je bestaande configuratie blijft behouden

### Testen

Na installatie is het aan te raden om te testen:
- ✓ Cover open/close/stop functies
- ✓ Positie instellen (0-100%)
- ✓ Tilt functies (indien ingeschakeld)
- ✓ Alle automation features (tijdgestuurd, zonopgang/ondergang, weer, etc.)
- ✓ Options flow (configuratie aanpassen)

### Bekende Issues

Geen bekende problemen. Meld issues op: https://github.com/MatthewOnTour/BUT_blinds_time_control/issues

### Credits

Originele integratie: MatthewOnTour
Geüpdatet voor HA 2025 compatibiliteit: januari 2026
