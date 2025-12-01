"""
Modules d'écriture Voltronic pour WKS Monitor
==============================================

Ce package contient les modules nécessaires pour ajouter le support
des commandes d'écriture (P...) aux onduleurs Voltronic MKS.

Modules disponibles:
- auth: Authentification Voltronic
- commands: Générateur de commandes et presets
- writer: Écriture série avec validation
- mqtt_handler: Gestion des commandes MQTT

Usage:
    from modules import VoltronicAuth, VoltronicWriter, MQTTCommandHandler
    
    auth = VoltronicAuth(debug=True)
    writer = VoltronicWriter(auth, debug=True)
    handler = MQTTCommandHandler("wks", writer, serial_reader, debug=True)
"""

from .auth import VoltronicAuth
from .commands import VoltronicCommands, VoltronicPresets
from .writer import VoltronicWriter, SafetyValidator
from .mqtt_handler import MQTTCommandHandler

__version__ = "1.0.0"
__author__ = "Claude & Jeremy"

__all__ = [
    'VoltronicAuth',
    'VoltronicCommands',
    'VoltronicPresets',
    'VoltronicWriter',
    'SafetyValidator',
    'MQTTCommandHandler'
]
