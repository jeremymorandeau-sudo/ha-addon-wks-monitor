# ☀️ WKS Monitor (Home Assistant Add-on)

Add-on qui lit les trames **QPGS0/1/2** d'onduleurs **WKS / Voltronic** en parallèle et publie sur **MQTT** :  
`wks/0/status`, `wks/1/status`, `wks/2/status`.

## 🔧 Configuration par défaut
- Port série : `/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_BWAAc143M08-if00-port0`
- Vitesse : `2400 bauds`
- Broker MQTT : `core-mosquitto` (`jeremy` / `123456`)
- Intervalle de lecture : `2s` (adaptatif si erreurs)

## 📦 Installation (via GitHub)
1. Créez un dépôt GitHub **public** nommé `wks-monitor` et uploadez le contenu de ce dossier.
2. Dans Home Assistant : **Paramètres → Modules complémentaires → Magasin → ⋮ → Dépôts → Ajouter**  
   Entrez : `https://github.com/jejelaprairie/wks-monitor`
3. Installez **WKS Monitor**, démarrez-le et ouvrez les logs.

## 🧪 Vérification
Dans **Outils de développement → MQTT → Écouter `wks/#`** :  
vous verrez les JSON pour `index` 0, 1 et 2.

— *by jejelaprairie*
