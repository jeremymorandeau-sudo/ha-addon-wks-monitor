#!/usr/bin/env python3
"""
example_usage.py - Exemples d'utilisation des modules
======================================================

Ce fichier montre comment utiliser les modules dans différents contextes
"""

import serial
import time
from modules import (
    VoltronicAuth,
    VoltronicCommands,
    VoltronicPresets,
    VoltronicWriter,
    SafetyValidator,
    MQTTCommandHandler
)


# ============================================================================
# EXEMPLE 1 : Modifier un paramètre simple
# ============================================================================

def example_simple_parameter():
    """Modifier le floating voltage à 54.4V"""
    
    # 1. Ouvrir le port série
    ser = serial.Serial(
        port="/dev/ttyUSB0",
        baudrate=2400,
        timeout=2.5
    )
    
    # 2. Créer les objets nécessaires
    auth = VoltronicAuth(debug=True)
    writer = VoltronicWriter(auth, debug=True)
    
    # 3. Générer la commande
    cmd = VoltronicCommands.set_battery_float_voltage(54.4)
    # Retourne: "PBFT54.4"
    
    # 4. Envoyer la commande
    success, message = writer.write_parameter(ser, cmd)
    
    if success:
        print(f"✅ Floating voltage modifié: {message}")
    else:
        print(f"❌ Erreur: {message}")
    
    # 5. Fermer le port
    ser.close()


# ============================================================================
# EXEMPLE 2 : Modifier plusieurs paramètres
# ============================================================================

def example_multiple_parameters():
    """Modifier plusieurs paramètres en une fois"""
    
    ser = serial.Serial("/dev/ttyUSB0", 2400, timeout=2.5)
    auth = VoltronicAuth(debug=True)
    writer = VoltronicWriter(auth, debug=True)
    
    # Préparer les commandes
    commands = {
        "float_voltage": VoltronicCommands.set_battery_float_voltage(54.4),
        "recharge_voltage": VoltronicCommands.set_battery_recharge_voltage(49.0),
        "max_charge": VoltronicCommands.set_max_charge_current(60),
    }
    
    # Envoyer toutes les commandes
    results = writer.write_multiple_parameters(ser, commands)
    
    # Afficher les résultats
    for name, (success, message) in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {name}: {message}")
    
    ser.close()


# ============================================================================
# EXEMPLE 3 : Appliquer un preset complet
# ============================================================================

def example_apply_preset():
    """Appliquer un preset de configuration LiFePO4"""
    
    ser = serial.Serial("/dev/ttyUSB0", 2400, timeout=2.5)
    auth = VoltronicAuth(debug=True)
    writer = VoltronicWriter(auth, debug=True)
    
    # Obtenir les commandes du preset "balanced"
    preset_commands = VoltronicPresets.get_preset_commands("balanced")
    
    print("📋 Preset 'balanced' pour LiFePO4 16S:")
    for name, cmd in preset_commands.items():
        print(f"  - {name}: {cmd}")
    
    # Appliquer le preset
    results = writer.apply_preset(ser, preset_commands)
    
    # Résumé
    successes = sum(1 for s, _ in results.values() if s)
    print(f"\n✅ {successes}/{len(results)} paramètres appliqués")
    
    ser.close()


# ============================================================================
# EXEMPLE 4 : Validation de sécurité
# ============================================================================

def example_safety_validation():
    """Valider une configuration avant de l'appliquer"""
    
    # Paramètres à valider
    config = {
        "bulk": 58.4,
        "float": 54.4,
        "cutoff": 44.8,
        "recharge": 49.0
    }
    
    print("🔍 Validation de la configuration...")
    
    # 1. Valider la cohérence des tensions
    valid, msg = SafetyValidator.validate_voltage_range(
        bulk=config["bulk"],
        float_v=config["float"],
        cutoff=config["cutoff"],
        recharge=config["recharge"]
    )
    
    print(f"Tensions: {msg}")
    
    # 2. Valider le courant vs BMS
    valid, msg = SafetyValidator.validate_current_vs_bms(
        charge_current=180,  # 3 onduleurs × 60A
        bms_limit=200
    )
    
    print(f"Courant: {msg}")
    
    # 3. Valider pour système en parallèle
    valid, msg = SafetyValidator.validate_parallel_inverters_current(
        current_per_inverter=60,
        inverter_count=3,
        bms_limit=200
    )
    
    print(f"Parallèle: {msg}")


# ============================================================================
# EXEMPLE 5 : Configuration complète pour ta batterie
# ============================================================================

def example_your_battery_config():
    """
    Configuration spécifique pour ta batterie:
    - LiFePO4 16S 320Ah
    - BMS 200A
    - 3 onduleurs en parallèle
    """
    
    ser = serial.Serial("/dev/ttyUSB0", 2400, timeout=2.5)
    auth = VoltronicAuth(debug=True)
    writer = VoltronicWriter(auth, debug=True)
    
    print("⚙️ Configuration pour LiFePO4 16S 320Ah avec BMS 200A")
    print("=" * 60)
    
    # 1. Valider la configuration souhaitée
    print("\n1️⃣ Validation des tensions...")
    valid, msg = SafetyValidator.validate_voltage_range(
        bulk=58.4,
        float_v=54.4,
        cutoff=44.8,
        recharge=49.0
    )
    print(f"   {msg}")
    
    # 2. Valider les courants
    print("\n2️⃣ Validation des courants...")
    valid, msg = SafetyValidator.validate_parallel_inverters_current(
        current_per_inverter=60,
        inverter_count=3,
        bms_limit=200
    )
    print(f"   {msg}")
    
    if not valid:
        print("\n❌ Configuration invalide, abandon!")
        ser.close()
        return
    
    # 3. Appliquer la configuration
    print("\n3️⃣ Application des paramètres...")
    
    commands = {
        "bulk_voltage": VoltronicCommands.set_battery_charge_voltage(58.4),
        "float_voltage": VoltronicCommands.set_battery_float_voltage(54.4),
        "cutoff_voltage": VoltronicCommands.set_battery_cutoff_voltage(44.8),
        "recharge_voltage": VoltronicCommands.set_battery_recharge_voltage(49.0),
        "max_charge_current": VoltronicCommands.set_max_charge_current(60),
    }
    
    results = writer.write_multiple_parameters(ser, commands)
    
    # 4. Afficher les résultats
    print("\n4️⃣ Résultats:")
    for name, (success, message) in results.items():
        status = "✅" if success else "❌"
        print(f"   {status} {name}: {message}")
    
    successes = sum(1 for s, _ in results.values() if s)
    print(f"\n{'✅' if successes == len(results) else '⚠️'} {successes}/{len(results)} paramètres appliqués")
    
    ser.close()


# ============================================================================
# EXEMPLE 6 : Utilisation avec MQTT (dans l'addon)
# ============================================================================

def example_mqtt_integration():
    """
    Comment intégrer dans wks_monitor.py avec MQTT
    (Ceci est un pseudo-code montrant la logique)
    """
    
    # Dans wks_monitor.py, fonction main():
    
    # 1. Créer le SerialReader (existant)
    # sr = SerialReader(port, baudrate, timeout)
    # sr.open()
    
    # 2. Créer les modules d'écriture
    # auth = VoltronicAuth(debug=debug)
    # writer = VoltronicWriter(auth, debug=debug)
    
    # 3. Créer le MQTTPublisher avec le handler
    # mqtt_pub = MQTTPublisher(...)
    # command_handler = MQTTCommandHandler(topic_prefix, writer, sr, debug)
    # command_handler.setup_mqtt_client(mqtt_pub.client)
    
    # 4. C'est tout ! Les commandes MQTT sont automatiquement gérées
    
    print("""
    Exemple d'utilisation via MQTT dans Home Assistant:
    
    # Modifier le floating voltage
    Topic: wks/command/set_float_voltage
    Payload: {"voltage": 54.4}
    
    # Appliquer un preset
    Topic: wks/command/apply_preset
    Payload: {"preset": "balanced"}
    
    # Le résultat est publié sur:
    Topic: wks/command/result
    """)


# ============================================================================
# EXEMPLE 7 : Créer un preset personnalisé
# ============================================================================

def example_custom_preset():
    """Créer et utiliser un preset personnalisé"""
    
    # Configuration personnalisée
    custom_config = {
        "battery_voltage": 58.4,
        "float_voltage": 54.0,      # Plus conservateur
        "cutoff_voltage": 45.0,      # Plus conservateur
        "recharge_voltage": 50.0,    # Recharge plus tôt
    }
    
    # Générer les commandes
    commands = {}
    commands["bulk"] = VoltronicCommands.set_battery_charge_voltage(
        custom_config["battery_voltage"]
    )
    commands["float"] = VoltronicCommands.set_battery_float_voltage(
        custom_config["float_voltage"]
    )
    commands["cutoff"] = VoltronicCommands.set_battery_cutoff_voltage(
        custom_config["cutoff_voltage"]
    )
    commands["recharge"] = VoltronicCommands.set_battery_recharge_voltage(
        custom_config["recharge_voltage"]
    )
    
    # Valider
    valid, msg = SafetyValidator.validate_voltage_range(
        bulk=custom_config["battery_voltage"],
        float_v=custom_config["float_voltage"],
        cutoff=custom_config["cutoff_voltage"],
        recharge=custom_config["recharge_voltage"]
    )
    
    print(f"Preset personnalisé: {msg}")
    
    if valid:
        print("✅ Preset prêt à être appliqué!")
        for name, cmd in commands.items():
            print(f"  - {name}: {cmd}")


# ============================================================================
# MAIN : Exécuter les exemples
# ============================================================================

if __name__ == "__main__":
    print("📚 Exemples d'utilisation des modules Voltronic")
    print("=" * 70)
    
    # Décommenter l'exemple que tu veux tester
    
    # example_simple_parameter()
    # example_multiple_parameters()
    # example_apply_preset()
    # example_safety_validation()
    # example_your_battery_config()
    # example_mqtt_integration()
    example_custom_preset()
    
    print("\n✅ Exemple terminé!")
    print("\nℹ️  Pour tester sur tes onduleurs, décommenter l'exemple voulu")
    print("    et adapter le port série (/dev/ttyUSB0)")
