# Installatie Instructies - Blinds Time Control v2.0.0

## 📋 Overzicht

Deze geüpdatete versie is volledig compatibel met Home Assistant 2025 en bevat alle nodige aanpassingen om future-proof te zijn.

## 🔧 Installatie Stappen

### Optie 1: Handmatige Installatie

1. **Backup maken** (aanbevolen!)
   ```bash
   # Maak een backup van je huidige configuratie
   cp -r config/custom_components/blinds_controller config/custom_components/blinds_controller.backup
   ```

2. **Stop Home Assistant** (optioneel maar aanbevolen)
   - Via UI: Settings → System → Restart
   - Of via CLI: `ha core restart`

3. **Verwijder oude versie**
   ```bash
   rm -rf config/custom_components/blinds_controller
   ```

4. **Pak nieuwe versie uit**
   - Unzip het bestand `blinds_controller_v2.0_HA2025.zip`
   - Plaats de `blinds_controller_updated` map in `config/custom_components/`
   - **Belangrijk**: Hernoem `blinds_controller_updated` naar `blinds_controller`

5. **Herstart Home Assistant**

### Optie 2: Via HACS (als je HACS gebruikt)

Als de originele repository wordt geüpdatet:
1. Ga naar HACS → Integrations
2. Zoek "Blinds Time Control"
3. Klik op "Update" als beschikbaar
4. Herstart Home Assistant

## ✅ Verificatie

Na installatie:

1. **Controleer de logs**
   ```
   Settings → System → Logs
   ```
   Zoek naar errors gerelateerd aan `blinds_controller`

2. **Test de integratie**
   - Open Developer Tools → States
   - Zoek je cover entities (bijv. `cover.blinds_controller_...`)
   - Test open/close/stop functies
   - Test positie instelling

3. **Controleer versie**
   - Ga naar Settings → Devices & Services
   - Klik op Blinds Time Control
   - Versie zou "2.0.0" moeten zijn

## 🔍 Troubleshooting

### Foutmelding: "Integration not found"
**Oplossing**: Controleer of de map naam exact `blinds_controller` is (niet `blinds_controller_updated`)

### Foutmelding: "Cannot import name..."
**Oplossing**: 
1. Verwijder `__pycache__` directories
2. Herstart Home Assistant volledig (niet alleen reload)

### Entities werken niet meer
**Oplossing**:
1. Controleer de logs voor specifieke errors
2. Je configuratie blijft behouden, geen herinrichting nodig
3. Als het probleem aanhoudt, herstel de backup en meld een issue

### Optie flow werkt niet
**Oplossing**: Dit zou nu moeten werken met de nieuwe `async_reload_entry` functie

## 📝 Wat blijft hetzelfde?

- ✅ Al je bestaande configuraties blijven behouden
- ✅ Entity IDs blijven hetzelfde
- ✅ Alle features blijven werken
- ✅ Automations hoeven niet aangepast te worden

## 🆕 Wat is er nieuw?

- ✅ Compatibel met Home Assistant 2025.x
- ✅ Modernere code volgens HA best practices
- ✅ Betere type hints en error handling
- ✅ Options flow werkt beter
- ✅ Deprecated warnings zijn verdwenen

## 📊 File Structuur

Na installatie zou je deze structuur moeten hebben:

```
config/
└── custom_components/
    └── blinds_controller/
        ├── __init__.py
        ├── calculator.py
        ├── config_flow.py
        ├── const.py
        ├── cover.py
        ├── manifest.json
        ├── services.yaml
        ├── strings.json
        ├── CHANGELOG.md (optioneel)
        └── translations/
            └── en.json
```

## 🐛 Problemen Melden

Als je problemen ondervindt:

1. Controleer eerst de logs
2. Zorg dat je Home Assistant 2024.x of nieuwer gebruikt
3. Maak een issue aan op: https://github.com/MatthewOnTour/BUT_blinds_time_control/issues
4. Vermeld:
   - Home Assistant versie
   - Error logs
   - Wat je hebt geprobeerd

## 💡 Tips

- **Maak altijd een backup** voordat je updates installeert
- Test eerst op een non-productie systeem als mogelijk
- Lees de CHANGELOG.md voor details over alle wijzigingen
- Gebruik de HA logs om eventuele problemen te diagnosticeren

## 📞 Support

- GitHub Issues: https://github.com/MatthewOnTour/BUT_blinds_time_control/issues
- Home Assistant Community: https://community.home-assistant.io/

---

**Veel succes met de installatie! 🚀**
