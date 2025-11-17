# ☀️ WKS Monitor (Home Assistant Add-on)

[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)](https://github.com/jeremymorandeau-sudo/ha-addon-wks-monitor)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Add--on-41BDF5.svg)](https://www.home-assistant.io/)

Add-on qui lit les trames **QPGS0/1/2, QPIGS, QPIRI, QPIWS** d'onduleurs **WKS / Voltronic** en parallèle et publie sur **MQTT**.

## 🌟 Nouveautés v3.0.0

### 📊 Commandes supportées
- **QPGS** - Status parallèle complet (3 onduleurs) → `wks/0/status`, `wks/1/status`, `wks/2/status`
- **QPIGS** - Status général détaillé → `wks/0/general`, `wks/1/general`, `wks/2/general`
- **QPIRI** - Paramètres d'usine → `wks/rating`
- **QPIWS** - 25+ alertes et warnings → `wks/0/warnings`, `wks/1/warnings`, `wks/2/warnings`
- **QMOD** - Mode actuel (optionnel) → `wks/0/mode`, `wks/1/mode`, `wks/2/mode`

### 🎯 Données disponibles
- ⚡ Tensions et fréquences AC (entrée/sortie)
- 🔋 Batterie (voltage, courant, capacité %, température)
- ☀️ Solaire PV (voltage, courant, puissance calculée)
- 🌡️ Températures (dissipateur, batterie)
- 📈 Charges (W, VA, %)
- 🚨 Alertes automatiques (surcharge, température, batterie faible, etc.)
- ⚙️ Paramètres système (puissance nominale, type batterie, courants max)

## 🔧 Configuration par défaut

```yaml
port: "/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_BWAAc143M08-if00-port0"
baudrate: 2400
inverter_count: 3
poll_interval: 2.0

mqtt_host: "core-mosquitto.local.hass.io"
mqtt_port: 1883
mqtt_user: "jeremy"
mqtt_password: ""
mqtt_topic_prefix: "wks"

debug: true
enable_qpigs: true      # Status général détaillé
enable_qpiri: true      # Paramètres d'usine
enable_qpiws: true      # Alertes et warnings
enable_qmod: false      # Mode actuel (optionnel)
```

### 🔍 Trouver votre port série
Dans Home Assistant :
- **Paramètres → Système → Matériel → Tout le matériel**
- Chercher "Prolific" ou "USB Serial"
- Copier le chemin `/dev/serial/by-id/...`

## 📦 Installation (via GitHub)

1. Ajoutez le dépôt dans Home Assistant :  
   **Paramètres → Modules complémentaires → Magasin → ⋮ → Dépôts → Ajouter**  
   Entrez : `https://github.com/jeremymorandeau-sudo/ha-addon-wks-monitor`

2. Installez **WKS Monitor** depuis le magasin

3. Configurez les options (voir ci-dessus)

4. Démarrez l'add-on et consultez les logs

## 🧪 Vérification

### Dans MQTT
**Outils de développement → MQTT → Écouter `wks/#`**

Vous verrez les topics :
```
wks/0/status      # Status parallèle QPGS
wks/0/general     # Status général QPIGS
wks/0/warnings    # Alertes QPIWS
wks/0/mode        # Mode QMOD (si activé)
wks/rating        # Paramètres QPIRI
```

### Format des données (exemple `wks/0/status`)
```json
{
  "parallel_index": 1,
  "work_mode": "B",
  "work_mode_decoded": "Battery",
  "ac_output_voltage": 230.2,
  "ac_output_freq": 49.99,
  "output_active_power_w": 554,
  "battery_voltage": 52.7,
  "battery_capacity_pct": 77,
  "pv_input_voltage": 75.3,
  "pv_input_current_a": 20,
  "pv_input_power_w": 1506.0,
  "heatsink_temp": 45,
  "total_active_power_w": 713,
  "status_flags": {
    "scc_charging": true,
    "battery_discharging": false,
    "alarm_active": false
  }
}
```

## 🏠 Intégration Home Assistant

### Capteurs MQTT de base

Créez `mqtt_wks.yaml` dans votre configuration :

```yaml
sensor:
  - name: "WKS 0 Puissance active"
    unique_id: wks_0_output_active_power
    state_topic: "wks/0/status"
    unit_of_measurement: "W"
    device_class: power
    value_template: "{{ value_json.output_active_power_w }}"
    device:
      identifiers: ["wks_0"]
      name: "Onduleur WKS 0"
      manufacturer: "Voltronic Power"

  - name: "WKS 0 Tension batterie"
    unique_id: wks_0_battery_voltage
    state_topic: "wks/0/status"
    unit_of_measurement: "V"
    device_class: voltage
    value_template: "{{ value_json.battery_voltage }}"
    device:
      identifiers: ["wks_0"]

  - name: "WKS 0 Capacité batterie"
    unique_id: wks_0_battery_capacity
    state_topic: "wks/0/status"
    unit_of_measurement: "%"
    value_template: "{{ value_json.battery_capacity_pct }}"
    device:
      identifiers: ["wks_0"]

  - name: "WKS 0 Puissance PV"
    unique_id: wks_0_pv_power
    state_topic: "wks/0/status"
    unit_of_measurement: "W"
    device_class: power
    value_template: "{{ value_json.pv_input_power_w }}"
    device:
      identifiers: ["wks_0"]

  - name: "WKS 0 Température"
    unique_id: wks_0_heatsink_temp
    state_topic: "wks/0/status"
    unit_of_measurement: "°C"
    device_class: temperature
    value_template: "{{ value_json.heatsink_temp }}"
    device:
      identifiers: ["wks_0"]

binary_sensor:
  # Alertes QPIWS
  - name: "WKS 0 Défaut actif"
    unique_id: wks_0_any_fault
    state_topic: "wks/0/warnings"
    value_template: "{{ value_json.any_fault }}"
    device_class: problem
    payload_on: true
    payload_off: false
    device:
      identifiers: ["wks_0"]

  - name: "WKS 0 Surcharge"
    unique_id: wks_0_overload
    state_topic: "wks/0/warnings"
    value_template: "{{ value_json.overload_fault }}"
    device_class: problem
    device:
      identifiers: ["wks_0"]

  - name: "WKS 0 Température élevée"
    unique_id: wks_0_over_temp
    state_topic: "wks/0/warnings"
    value_template: "{{ value_json.over_temperature_fault }}"
    device_class: problem
    device:
      identifiers: ["wks_0"]
```

Incluez dans `configuration.yaml` :
```yaml
mqtt: !include mqtt_wks.yaml
```

### Automations d'alertes

```yaml
automation:
  - alias: "Alerte WKS - Défaut critique"
    trigger:
      - platform: state
        entity_id: binary_sensor.wks_0_defaut_actif
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ Onduleur WKS 0 en défaut"
          message: "Vérifier l'onduleur immédiatement"

  - alias: "Alerte WKS - Batterie faible"
    trigger:
      - platform: numeric_state
        entity_id: sensor.wks_0_capacite_batterie
        below: 20
    action:
      - service: notify.mobile_app
        data:
          title: "🔋 Batterie faible"
          message: "{{ states('sensor.wks_0_capacite_batterie') }}%"
```

## ⚙️ Options disponibles

| Option | Défaut | Description |
|--------|--------|-------------|
| `port` | - | Chemin du port série USB |
| `baudrate` | 2400 | Vitesse de communication |
| `inverter_count` | 3 | Nombre d'onduleurs (1-10) |
| `poll_interval` | 2.0 | Intervalle de lecture (secondes) |
| `mqtt_host` | core-mosquitto | Broker MQTT |
| `mqtt_port` | 1883 | Port MQTT |
| `mqtt_user` | - | Utilisateur MQTT |
| `mqtt_password` | - | Mot de passe MQTT |
| `mqtt_topic_prefix` | wks | Préfixe des topics |
| `debug` | false | Logs détaillés |
| `enable_qpigs` | true | Status général (QPIGS) |
| `enable_qpiri` | true | Paramètres usine (QPIRI) |
| `enable_qpiws` | true | Alertes (QPIWS) |
| `enable_qmod` | false | Mode actuel (QMOD) |

## 🐛 Dépannage

### L'add-on ne démarre pas
- Vérifier le port série dans **Paramètres → Système → Matériel**
- S'assurer que Mosquitto est installé et démarré
- Consulter les logs : **Modules complémentaires → WKS Monitor → Journaux**

### Pas de données MQTT
- Tester avec `mosquitto_sub -h localhost -t "wks/#" -v`
- Vérifier les identifiants MQTT dans la configuration
- S'assurer que `uart: true` est présent dans `config.yaml`

### Erreurs de parsing
- Activer `debug: true` pour voir les trames brutes
- Consulter les logs pour identifier le problème
- Ouvrir une [issue GitHub](https://github.com/jeremymorandeau-sudo/ha-addon-wks-monitor/issues)

### Performance lente
- Désactiver `enable_qmod` (redondant avec QPGS)
- Augmenter `poll_interval` à 3-5 secondes
- L'intervalle s'adapte automatiquement à 3s en cas d'erreurs

## 📋 Compatibilité

### Onduleurs testés
- ✅ WKS 5kVA Parallel (MKS I)
- ✅ Voltronic Axpert MKS 5KVA
- ⚠️ Autres modèles Voltronic (format peut varier)

### Prérequis
- Home Assistant 2023.1+
- Mosquitto MQTT Broker
- Port série USB (Prolific PL2303 ou compatible)
- Câble RS-232 vers onduleur

## 🚀 Roadmap

### v3.1 - Contrôle (à venir)
- [ ] Commandes ON/OFF
- [ ] Modification paramètres (courants charge, tensions)
- [ ] Services Home Assistant
- [ ] Interface de contrôle

### v3.2 - Historique (à venir)
- [ ] Statistiques énergétiques (kWh générés/consommés)
- [ ] Données mensuelles/journalières
- [ ] Export et stockage long terme

### v4.0 - Interface web (à venir)
- [ ] Dashboard intégré
- [ ] Graphiques temps réel
- [ ] Configuration visuelle

## 📝 Changelog

### [3.0.0] - 2024-11-17
- ✨ Ajout QPIGS (status général détaillé)
- ✨ Ajout QPIRI (paramètres d'usine)
- ✨ Ajout QPIWS (25+ types d'alertes)
- ✨ Ajout QMOD (mode actuel)
- 🎯 80+ champs de données disponibles
- 📊 13+ topics MQTT
- 🔧 Parser modulaire et robuste
- 📈 Champs calculés (puissance PV, puissance batterie)

### [2.0.8] - 2024-XX-XX
- 🔧 Correction parsing QPGS format étendu 27 champs
- 🐛 Support valeurs décimales dans champs entiers

### [1.0.0] - 2024-XX-XX
- 🎉 Version initiale avec QPGS

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :
- Ouvrir des [issues](https://github.com/jeremymorandeau-sudo/ha-addon-wks-monitor/issues)
- Proposer des [pull requests](https://github.com/jeremymorandeau-sudo/ha-addon-wks-monitor/pulls)
- Partager vos configurations et automations

## 📄 Licence

MIT License - Voir [LICENSE](LICENSE)

## 🙏 Remerciements

- [Voltronic Power](https://voltronicpower.com/)
- Communauté Home Assistant
- Projet [mpp-solar](https://github.com/jblance/mpp-solar)

---

**Développé avec ❤️ pour la communauté Home Assistant**  
*— by jeremymorandeau-sudo (fork original: jejelaprairie)*
