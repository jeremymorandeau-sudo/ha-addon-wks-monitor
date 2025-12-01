# 📦 WKS Monitor - Modules d'écriture Voltronic

Architecture modulaire pour ajouter le support des commandes d'écriture à ton addon wks-monitor.

## 🎯 Objectif

Rendre le code **plus léger, plus clair, plus maintenable** en découpant les fonctionnalités en modules indépendants.

---

## 📁 Structure des fichiers

```
modules/
├── __init__.py          ← Exports des modules
├── auth.py              ← Authentification Voltronic (300 lignes)
├── commands.py          ← Générateur de commandes (400 lignes)
├── writer.py            ← Écriture série (250 lignes)
├── mqtt_handler.py      ← Gestion MQTT (250 lignes)
└── integration.py       ← Guide d'intégration
```

**Total: ~1200 lignes découpées en 4 modules** au lieu d'un énorme fichier monolithique !

---

## 🚀 Installation rapide

### Étape 1 : Copier les fichiers

```bash
# Dans ton repo ha-addon-wks-monitor
cd wks-monitor/

# Créer le dossier modules
mkdir modules

# Copier les fichiers
cp auth.py modules/
cp commands.py modules/
cp writer.py modules/
cp mqtt_handler.py modules/

# Créer __init__.py
cat > modules/__init__.py << 'EOF'
from .auth import VoltronicAuth
from .commands import VoltronicCommands, VoltronicPresets
from .writer import VoltronicWriter, SafetyValidator
from .mqtt_handler import MQTTCommandHandler

__all__ = [
    'VoltronicAuth',
    'VoltronicCommands',
    'VoltronicPresets',
    'VoltronicWriter',
    'SafetyValidator',
    'MQTTCommandHandler'
]
EOF
```

### Étape 2 : Modifier wks_monitor.py

**Ajouter en haut du fichier :**
```python
from modules import VoltronicAuth, VoltronicWriter, MQTTCommandHandler
```

**Remplacer la classe MQTTPublisher :**
```python
class MQTTPublisher:
    def __init__(self, host: str, port: int, user: str, password: str, 
                 topic_prefix: str, serial_reader, debug: bool = False):
        self.topic_prefix = topic_prefix
        self.debug = debug
        self.serial_reader = serial_reader
        
        # Initialiser les modules d'écriture
        self.auth = VoltronicAuth(debug=debug)
        self.writer = VoltronicWriter(self.auth, debug=debug)
        self.command_handler = MQTTCommandHandler(
            topic_prefix, self.writer, serial_reader, debug
        )
        
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, 
                                  client_id="wks-monitor-v4", clean_session=True)
        if user:
            self.client.username_pw_set(user, password)
        
        # Setup du handler de commandes
        self.command_handler.setup_mqtt_client(self.client)
        
        self.client.connect(host, port, keepalive=30)
        self.client.loop_start()
    
    def publish(self, subtopic: str, data: dict):
        """Méthode existante - ne pas modifier"""
        topic = f"{self.topic_prefix}/{subtopic}"
        self.client.publish(topic, json.dumps(data), qos=0, retain=True)
        if self.debug:
            log(f"[MQTT] Published to {topic}")
```

### Étape 3 : Tester

```bash
# Redémarrer l'addon
# Vérifier les logs :
# [AUTH] Module chargé
# [MQTT] Subscribed to wks/command/#
```

---

## 📚 Descriptions des modules

### **auth.py** - Authentification
- `VoltronicAuth`: Gère l'authentification avec mot de passe "administrator"
- Cache l'authentification pendant 30 secondes
- Gère automatiquement la ré-authentification

**Usage:**
```python
auth = VoltronicAuth(debug=True)
if auth.authenticate(ser):
    print("Authentifié!")
```

---

### **commands.py** - Générateur de commandes
- `VoltronicCommands`: Génère toutes les commandes P... possibles
- `VoltronicPresets`: Presets prédéfinis pour batteries LiFePO4
- Validation des valeurs intégrée

**Usage:**
```python
# Commande simple
cmd = VoltronicCommands.set_battery_float_voltage(54.4)
# Retourne: "PBFT54.4"

# Preset complet
preset = VoltronicPresets.lifepo4_16s_balanced()
# Retourne: {battery_voltage: 58.4, float_voltage: 54.4, ...}
```

**Commandes disponibles:**
- `set_battery_charge_voltage(voltage)` - PBT
- `set_battery_float_voltage(voltage)` - PBFT
- `set_battery_cutoff_voltage(voltage)` - PSDV
- `set_battery_recharge_voltage(voltage)` - PBR
- `set_max_charge_current(current)` - MCHGC
- `set_max_ac_charge_current(current)` - MUCHGC
- `set_output_source_priority(priority)` - POP
- `set_charger_source_priority(priority)` - PCP

**Presets disponibles:**
- `conservative` - Durée de vie max (SOC min 35%)
- `balanced` - Équilibré (SOC min 28%) ← **Recommandé**
- `performance` - Capacité max (SOC min 20%)

---

### **writer.py** - Écriture série
- `VoltronicWriter`: Envoie les commandes sur le port série
- `SafetyValidator`: Valide la cohérence des paramètres
- Gère automatiquement l'authentification

**Usage:**
```python
writer = VoltronicWriter(auth, debug=True)
success, msg = writer.write_parameter(ser, "PBFT54.4")

if success:
    print("Paramètre modifié!")
```

**Validation de sécurité:**
```python
# Valider une config complète
valid, msg = SafetyValidator.validate_voltage_range(
    bulk=58.4, float_v=54.4, cutoff=44.8, recharge=49.0
)

# Valider courant vs BMS
valid, msg = SafetyValidator.validate_current_vs_bms(
    charge_current=180, bms_limit=200
)
```

---

### **mqtt_handler.py** - Gestion MQTT
- `MQTTCommandHandler`: Gère les commandes reçues via MQTT
- Subscribe automatiquement aux topics `/command/...`
- Publie les résultats sur `/command/result`
- Stats intégrées

**Usage:**
```python
handler = MQTTCommandHandler("wks", writer, serial_reader, debug=True)
handler.setup_mqtt_client(mqtt_client)
# C'est tout ! Les commandes sont gérées automatiquement
```

**Topics MQTT:**
```
wks/command/set_battery_voltage {"voltage": 58.4}
wks/command/set_float_voltage {"voltage": 54.4}
wks/command/set_cutoff_voltage {"voltage": 44.8}
wks/command/set_recharge_voltage {"voltage": 49.0}
wks/command/set_max_charge_current {"current": 60}
wks/command/set_max_ac_charge_current {"current": 20}
wks/command/apply_preset {"preset": "balanced"}
wks/command/get_stats {}

→ Résultat publié sur: wks/command/result
```

---

## ✨ Avantages de cette architecture

### 🎯 **Modularité**
- Chaque module a une responsabilité unique
- Facile de modifier un module sans toucher aux autres
- Testable indépendamment

### 📝 **Lisibilité**
- Code court et clair (250-400 lignes par fichier)
- Documentation intégrée
- Exemples d'usage

### 🔧 **Maintenabilité**
- Ajout de nouvelles commandes simple
- Modification de presets facile
- Debug plus simple

### 🛡️ **Sécurité**
- Validation intégrée
- SafetyValidator pour éviter les erreurs
- Messages d'erreur clairs

### 🚀 **Évolutivité**
- Facile d'ajouter de nouveaux presets
- Facile d'ajouter de nouvelles commandes MQTT
- Facile d'ajouter des validations

---

## 🔨 Personnalisation

### Ajouter un nouveau preset

Édite `modules/commands.py` :

```python
@staticmethod
def lifepo4_16s_custom():
    """Ma configuration personnalisée"""
    return {
        "battery_voltage": 58.4,
        "float_voltage": 54.0,
        "cutoff_voltage": 45.0,
        "recharge_voltage": 49.5,
        "description": "Ma config perso"
    }
```

### Ajouter une nouvelle commande

Édite `modules/commands.py` :

```python
@staticmethod
def set_battery_type(battery_type: int) -> str:
    """PBT - Battery Type"""
    if battery_type not in [0, 1, 2]:
        raise ValueError(f"Type invalide: {battery_type}")
    return f"PBT{battery_type:02d}"
```

Puis ajoute le handler dans `modules/mqtt_handler.py` :

```python
def _handle_set_battery_type(self, payload: dict) -> tuple:
    try:
        btype = int(payload.get("type", 0))
        cmd = VoltronicCommands.set_battery_type(btype)
        return self.writer.write_parameter(self.serial_reader.ser, cmd)
    except ValueError as e:
        return False, str(e)
```

Et dans `on_message()` :

```python
elif command == "set_battery_type":
    success, message = self._handle_set_battery_type(payload)
```

---

## 🧪 Tests

### Test d'authentification
```bash
# Dans les logs, tu devrais voir:
[AUTH] ✅ Authentification réussie
```

### Test de commande simple
```yaml
# MQTT - Outils de développement
Topic: wks/command/set_float_voltage
Payload: {"voltage": 54.4}

# Résultat attendu:
[MQTT-CMD] Reçu #1: wks/command/set_float_voltage
[AUTH] ✅ Authentification réussie
[WRITE] ✅ Commande acceptée: PBFT54.4
```

### Test de preset
```yaml
Topic: wks/command/apply_preset
Payload: {"preset": "balanced"}

# Résultat: 4 paramètres modifiés
```

---

## 📊 Comparaison

### Avant (monolithique)
```
wks_monitor.py: 2500+ lignes
- Difficile à maintenir
- Difficile à tester
- Difficile à modifier
```

### Après (modulaire)
```
wks_monitor.py: 1300 lignes (code existant)
modules/
  auth.py: 300 lignes
  commands.py: 400 lignes
  writer.py: 250 lignes
  mqtt_handler.py: 250 lignes
Total: 2500 lignes, mais organisées!
- Facile à maintenir
- Testable module par module
- Ajout de fonctionnalités simple
```

---

## 🐛 Dépannage

### Import error
```
ModuleNotFoundError: No module named 'modules'
```
→ Vérifier que `modules/__init__.py` existe

### Authentification échoue
```
[AUTH] ❌ Échec
```
→ Vérifier que le port série est ouvert
→ Vérifier que ce sont des onduleurs Voltronic MKS

### Commande refusée
```
[WRITE] ❌ Commande refusée
```
→ Vérifier que la valeur est valide
→ Activer le debug pour voir les détails

---

## 📞 Support

Pour toute question sur l'intégration :
1. Vérifie `integration.py` pour le guide complet
2. Active le mode debug dans `options.json`
3. Vérifie les logs de l'addon
4. Teste avec une commande simple d'abord

---

## 🎉 C'est parti !

Tu as maintenant une architecture propre, modulaire et maintenable !

**Prochaines étapes suggérées :**
1. Intégrer les modules
2. Tester avec une commande simple
3. Créer des scripts Home Assistant
4. Créer une interface Lovelace
5. Ajouter tes propres presets

Bon dev ! 🚀
