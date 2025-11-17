# Changelog - WKS Monitor

Toutes les modifications notables de ce projet seront documentées dans ce fichier.

## [3.0.0] - 2024-11-17

### 🎉 Ajouts majeurs
- **QPIGS** : Status général détaillé de l'onduleur (bus voltage, battery discharge current, device status)
- **QPIRI** : Rating information (paramètres d'usine : tensions nominales, courants max, type batterie)
- **QPIWS** : Warning status avec 25+ types d'alertes détectées (surcharge, température, batterie faible, etc.)
- **QMOD** : Mode actuel de l'onduleur (optionnel)
- Classe `VoltronicParser` modulaire pour toutes les commandes
- Classe `MQTTPublisher` pour publication organisée
- Calcul CRC automatique pour commandes non pré-calculées
- Logs détaillés avec toutes les métriques importantes

### 📊 Nouveaux topics MQTT
- `wks/0/general` - Status QPIGS par onduleur
- `wks/0/warnings` - Alertes QPIWS par onduleur
- `wks/0/mode` - Mode QMOD par onduleur (si activé)
- `wks/rating` - Informations QPIRI globales

### ⚙️ Nouvelles options de configuration
- `enable_qpigs` (défaut: true) - Active/désactive QPIGS
- `enable_qpiri` (défaut: true) - Active/désactive QPIRI
- `enable_qpiws` (défaut: true) - Active/désactive QPIWS
- `enable_qmod` (défaut: false) - Active/désactive QMOD

### 🔧 Améliorations
- Parser robuste avec gestion d'erreurs améliorée
- Support format décimal ET entier pour tous les champs (`safe_int`, `safe_float`)
- Cache QPIRI (changements rares, lu une fois au démarrage)
- Décodage automatique des status flags (8 bits → booleans)
- Champs calculés : `pv_input_power_w`, `battery_power_w`
- Alertes automatiques dans les logs si fault ou warning détecté

### 📈 Données supplémentaires
- **80+ champs** disponibles (vs 20 en v2.0.x)
- **13+ topics MQTT** (vs 3 en v2.0.x)
- Décodage work_mode : Battery/Line/Fault/PowerOn/Standby
- Décodage battery_type : AGM/Flooded/User
- Indicateurs booléens : `any_fault`, `any_warning`, `grid_available`, `pv_active`, `battery_low`

### 🏗️ Architecture
- Code restructuré en classes pour maintenabilité
- Séparation parsing / communication / publication
- Base préparée pour futures fonctionnalités (contrôle, historique)

### ⚠️ Breaking Changes
- Structure des logs modifiée (plus détaillée)
- Nouveaux topics MQTT nécessitent mise à jour capteurs HA
- Option `debug` affiche maintenant toutes les métriques importantes

---

## [2.0.8] - 2024-XX-XX

### 🔧 Correctifs
- Correction parsing QPGS pour format étendu 27 champs
- Support valeurs décimales dans champs entiers (ex: "000.0")
- Amélioration gestion erreurs série

### ✨ Fonctionnalités
- Parser QPGS complet avec status flags
- Publication MQTT sur topics `wks/0/status`, `wks/1/status`, `wks/2/status`
- Décodage work_mode et champs calculés

---

## [1.0.0] - 2024-XX-XX

### 🎉 Version initiale
- Support QPGS pour onduleurs WKS en parallèle
- Communication série RS-232 (USB-Serial Prolific)
- Publication MQTT basique
- Support 3 onduleurs simultanés
- Gestion reconnexion automatique

---

## Versions à venir

### [3.1.0] - Contrôle (planifié)
- Commandes ON/OFF (PF/PN)
- Modification paramètres (MUCHGC, MCHGC, PBCV, PBFT, etc.)
- Interface Lovelace pour contrôle depuis HA
- Services Home Assistant pour actions

### [3.2.0] - Historique (planifié)
- Commande QET (total énergie)
- Commande QLT (load kWh)
- Commande QYM (énergie mensuelle)
- Commande QYD (énergie journalière)
- Stockage statistiques longue durée

### [4.0.0] - Dashboard intégré (planifié)
- Ingress Home Assistant
- Interface web de monitoring
- Graphiques temps réel
- Configuration visuelle

---

## Liens utiles

- [Documentation Voltronic Protocol](https://github.com/topics/voltronic)
- [Home Assistant Add-ons](https://www.home-assistant.io/addons/)
- [Issues & Support](https://github.com/jeremymorandeau-sudo/ha-addon-wks-monitor/issues)
