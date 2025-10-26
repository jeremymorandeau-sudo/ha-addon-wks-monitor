# 🧠 WKS Monitor Add-on pour Home Assistant

Cet add-on lit les trames QPGS0, QPGS1, QPGS2 des onduleurs Voltronic / WKS 5kVA en parallèle, et publie leurs données sur MQTT (wks/0/status, wks/1/status, wks/2/status).

## ⚙️ Configuration

- MQTT Broker : core-mosquitto
- Périphérique série : /dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_BWAAc143M08-if00-port0
- Lecture toutes les 2 secondes, avec adaptation automatique en cas d’erreurs.

## 🧩 Installation

1. Ajoutez le dépôt GitHub dans Home Assistant :
   https://github.com/<TON_UTILISATEUR>/ha-addon-wks-monitor
2. Installez l’add-on WKS Monitor
3. Démarrez-le et ouvrez les logs pour suivre les trames.
