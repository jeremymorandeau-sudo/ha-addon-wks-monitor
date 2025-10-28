# WKS Monitor (Home Assistant Add-on)

Add-on Home Assistant pour lire les trames **QPGS0 / QPGS1 / QPGS2** des onduleurs **WKS / Voltronic (série MKS)** en parallèle (triphasé ou non) et publier en **MQTT**.

**Auteur :** @jeremymorandeau-sudo  
**Dépôt :** https://github.com/jeremymorandeau-sudo/ha-addon-wks-monitor

---

## ⚙️ Paramètres configurables

| Nom | Type | Description | Valeur par défaut |
|------|------|-------------|-------------------|
| `port` | string | Port série WKS (utiliser *by-id*). | `/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_BWAAc143M08-if00-port0` |
| `baudrate` | int | Vitesse série. | `2400` |
| `mqtt_host` | string | Hôte broker MQTT. | `core-mosquitto` |
| `mqtt_port` | int | Port broker MQTT. | `1883` |
| `mqtt_topic` | string | Préfixe topics MQTT publiés. | `wks` |
| `scan_interval` | int | Intervalle de lecture (s). | `5` |
| `apply_settings_on_start` | bool | Appliquer les réglages MKS au démarrage. | `false` |
| `set_output_priority` | int | 0=Utility, 1=Solar, 2=SBU | `2` |
| `set_charge_priority` | int | 0=Utility, 1=Solar, 2=Solar+Utility | `2` |
| `set_ac_charge_current` | int | Courant charge AC max (A). | `20` |
| `set_pv_charge_current` | int | Courant charge PV max (A). | `60` |
| `set_float_voltage` | float | Tension float (V). | `54.8` |
| `set_bulk_voltage` | float | Tension bulk/absorption (V). | `56.4` |
| `set_back_to_grid_voltage` | float | Retour réseau (V). | `48.0` |
| `set_back_to_battery_voltage` | float | Retour batterie (V). | `51.0` |

> **Sécurité :** par défaut, `apply_settings_on_start=false`. Les commandes sont **journalisées** en *dry-run* (aperçu) sans être envoyées. Active seulement lorsque tu es sûr des valeurs.

---

## 📡 Topics MQTT publiés

Chaque onduleur `QPGS<N>` publie sur :

```
wks/<N>/status
```

Payload JSON exemple :
```json
{ "index": 0, "ac_output_voltage": 230.1, "ac_output_freq": 50.0, "battery_voltage": 53.4, "pv_input_voltage": 98.5, "parallel_role": "Master" }
```

---

## 🚀 Installation

1. Home Assistant → **Paramètres → Modules complémentaires → Magasin** → ⋮ **Référentiels** → ajouter :  
   `https://github.com/jeremymorandeau-sudo/ha-addon-wks-monitor`
2. Installer **WKS Monitor**, configurer si besoin, puis **Démarrer**.
3. Ouvrir les **Journaux** du module pour contrôler les trames et les probes.

---

## 🆕 v2.0.0
- Structure prête pour le **paramétrage MKS** (dry-run par défaut).
- Probes de lecture ajoutées : `QPIRI`, `QPIGS`, `QMOD`, `QPIWS`, `QFLAG`, `QVFW`, `QID`.
- Comportement identique à la 1.0.7 pour QPGS0/1/2 + MQTT.

---

## 🛟 Notes MKS (non MKS II)
Les commandes SET varient selon les firmwares. Toujours vérifier `QPIRI` / `QVFW` dans les logs. En cas de doute, laisse `apply_settings_on_start=false` pour rester en lecture seule.
