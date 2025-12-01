#!/usr/bin/env python3
"""
integration.py - Guide d'intégration modulaire
===============================================

Ce fichier montre comment intégrer les modules dans ton wks_monitor.py existant
"""

# ============================================================================
# ÉTAPE 1 : COPIER LES FICHIERS DANS LE DOSSIER DE L'ADDON
# ============================================================================

"""
Structure de dossiers à créer:

wks-monitor/
├── config.json
├── Dockerfile
├── run.sh
├── wks_monitor.py          ← Fichier principal existant
└── modules/                 ← NOUVEAU DOSSIER
    ├── __init__.py
    ├── auth.py              ← Copier depuis wks_monitor_modular/
    ├── commands.py          ← Copier depuis wks_monitor_modular/
    ├── writer.py            ← Copier depuis wks_monitor_modular/
    └── mqtt_handler.py      ← Copier depuis wks_monitor_modular/
"""

# ============================================================================
# ÉTAPE 2 : CRÉER modules/__init__.py
# ============================================================================

"""
Créer le fichier modules/__init__.py avec ce contenu:

# modules/__init__.py
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
"""

# ============================================================================
# ÉTAPE 3 : MODIFIER wks_monitor.py
# ============================================================================

"""
Dans ton fichier wks_monitor.py, ajoute ces imports en haut:
"""

# ---- AJOUTER EN HAUT DU FICHIER ----
from modules import VoltronicAuth, VoltronicWriter, MQTTCommandHandler
# ------------------------------------


# ============================================================================
# ÉTAPE 4 : MODIFIER LA CLASSE MQTTPublisher
# ============================================================================

"""
Remplacer la classe MQTTPublisher existante par celle-ci:
"""

class MQTTPublisher:
    def __init__(self, host: str, port: int, user: str, password: str, 
                 topic_prefix: str, serial_reader, debug: bool = False):
        self.topic_prefix = topic_prefix
        self.debug = debug
        self.serial_reader = serial_reader
        
        # ---- NOUVEAU CODE ----
        # Initialiser les modules d'écriture
        self.auth = VoltronicAuth(debug=debug)
        self.writer = VoltronicWriter(self.auth, debug=debug)
        self.command_handler = MQTTCommandHandler(
            topic_prefix, self.writer, serial_reader, debug
        )
        # ----------------------
        
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, 
                                  client_id="wks-monitor-v4", clean_session=True)
        if user:
            self.client.username_pw_set(user, password)
        
        # ---- NOUVEAU CODE ----
        # Setup du handler de commandes
        self.command_handler.setup_mqtt_client(self.client)
        # ----------------------
        
        self.client.connect(host, port, keepalive=30)
        self.client.loop_start()
    
    def publish(self, subtopic: str, data: dict):
        """Méthode existante - ne pas modifier"""
        topic = f"{self.topic_prefix}/{subtopic}"
        self.client.publish(topic, json.dumps(data), qos=0, retain=True)
        if self.debug:
            log(f"[MQTT] Published to {topic}")


# ============================================================================
# ÉTAPE 5 : C'EST TOUT ! 🎉
# ============================================================================

"""
Aucune autre modification nécessaire dans wks_monitor.py !

Les modules gèrent automatiquement:
- L'authentification Voltronic
- L'écriture des paramètres
- La réception des commandes MQTT
- La validation des valeurs
- Les presets de configuration

Tu peux maintenant utiliser l'addon comme avant, avec en plus
la possibilité de modifier les paramètres via MQTT !
"""

# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

"""
# Dans Home Assistant - Outils de développement - MQTT

# 1. Changer le floating voltage
Topic: wks/command/set_float_voltage
Payload: {"voltage": 54.4}

# 2. Changer le courant max
Topic: wks/command/set_max_charge_current
Payload: {"current": 60}

# 3. Appliquer un preset complet
Topic: wks/command/apply_preset
Payload: {"preset": "balanced"}

# 4. Obtenir les statistiques
Topic: wks/command/get_stats
Payload: {}

# Les résultats sont publiés sur:
Topic: wks/command/result
"""

# ============================================================================
# CONFIGURATION DES PRESETS
# ============================================================================

"""
Presets disponibles (définis dans modules/commands.py):

1. "conservative" - LiFePO4 16S Conservateur
   - Bulk: 58.4V
   - Float: 54.4V
   - Cutoff: 44.8V
   - Recharge: 50.4V (35% SOC)
   - Durée de vie maximale

2. "balanced" - LiFePO4 16S Équilibré (RECOMMANDÉ)
   - Bulk: 58.4V
   - Float: 54.4V
   - Cutoff: 44.8V
   - Recharge: 49.0V (28% SOC)
   - Bon compromis

3. "performance" - LiFePO4 16S Performance
   - Bulk: 58.4V
   - Float: 54.4V
   - Cutoff: 44.8V
   - Recharge: 48.0V (20% SOC)
   - Capacité maximale

Tu peux ajouter tes propres presets en modifiant modules/commands.py
"""

# ============================================================================
# AVANTAGES DE CETTE ARCHITECTURE
# ============================================================================

"""
✅ Code modulaire et maintenable
✅ Facile d'ajouter de nouvelles commandes
✅ Validation de sécurité intégrée
✅ Presets configurables
✅ Stats de commandes
✅ Séparation des responsabilités:
   - auth.py: Authentification
   - commands.py: Génération de commandes
   - writer.py: Écriture série
   - mqtt_handler.py: Gestion MQTT
✅ Pas de modification majeure du code existant
✅ Testable unitairement
"""

# ============================================================================
# DÉPANNAGE
# ============================================================================

"""
Si ça ne fonctionne pas:

1. Vérifier que le dossier modules/ est bien créé
2. Vérifier que __init__.py existe dans modules/
3. Vérifier les logs pour les erreurs d'import
4. Redémarrer complètement l'addon
5. Tester avec une commande simple (set_float_voltage)
6. Activer le mode debug dans options.json

Logs à surveiller:
[AUTH] ✅ Authentification réussie
[MQTT] Subscribed to wks/command/#
[MQTT-CMD] Reçu #1: wks/command/set_float_voltage
[WRITE] ✅ Commande acceptée: PBFT54.4
"""
