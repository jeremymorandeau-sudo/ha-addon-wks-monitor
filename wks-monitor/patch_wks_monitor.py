#!/usr/bin/env python3
"""
patch_wks_monitor.py - Script de patch automatique
===================================================

Ce script modifie automatiquement wks_monitor.py pour ajouter
le support des commandes d'écriture Voltronic.

Usage:
    python3 patch_wks_monitor.py /chemin/vers/wks_monitor.py
    
    ou depuis le dossier de l'addon:
    python3 patch_wks_monitor.py wks_monitor.py
"""

import sys
import os
import shutil
from datetime import datetime


def log(msg):
    """Affiche un message avec horodatage"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def backup_file(filepath):
    """Crée une sauvegarde du fichier original"""
    backup_path = f"{filepath}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(filepath, backup_path)
    log(f"✅ Backup créé : {backup_path}")
    return backup_path


def read_file(filepath):
    """Lit le contenu du fichier"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def write_file(filepath, content):
    """Écrit le contenu dans le fichier"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def patch_imports(content):
    """Ajoute l'import des modules"""
    log("📝 Patch 1/4 : Ajout des imports...")
    
    # Chercher la ligne après "import serial"
    import_marker = "import serial"
    
    if import_marker not in content:
        log("⚠️  'import serial' non trouvé, tentative avec 'import paho.mqtt'")
        import_marker = "import paho.mqtt.client as mqtt"
    
    if import_marker not in content:
        log("❌ Impossible de trouver l'emplacement pour les imports")
        return content, False
    
    # Vérifier si déjà patché
    if "from modules import" in content:
        log("⚠️  Import déjà présent, skip")
        return content, True
    
    # Ajouter l'import
    import_addition = """
# ===== AJOUT : Modules d'écriture Voltronic =====
from modules import VoltronicAuth, VoltronicWriter, MQTTCommandHandler
# ===============================================
"""
    
    content = content.replace(
        import_marker,
        import_marker + import_addition
    )
    
    log("✅ Patch 1/4 : Imports ajoutés")
    return content, True


def patch_mqtt_publisher_init(content):
    """Ajoute le paramètre serial_reader au constructeur"""
    log("📝 Patch 2/4 : Modification du constructeur MQTTPublisher...")
    
    # Chercher la signature de __init__
    old_signature = "def __init__(self, host: str, port: int, user: str, password: str, \n                 topic_prefix: str, debug: bool = False):"
    
    if old_signature not in content:
        # Essayer une variante
        old_signature = "def __init__(self, host: str, port: int, user: str, password: str, topic_prefix: str, debug: bool = False):"
    
    if old_signature not in content:
        log("⚠️  Signature exacte non trouvée, recherche flexible...")
        # Recherche plus flexible
        if "class MQTTPublisher:" in content and "def __init__" in content:
            log("⚠️  Classe trouvée mais signature différente")
            log("⚠️  Modification manuelle requise pour le paramètre serial_reader")
            return content, False
        else:
            log("❌ Classe MQTTPublisher non trouvée")
            return content, False
    
    # Vérifier si déjà patché
    if "serial_reader" in old_signature or "serial_reader, debug" in content:
        log("⚠️  Paramètre serial_reader déjà présent, skip")
        return content, True
    
    # Remplacer la signature
    new_signature = "def __init__(self, host: str, port: int, user: str, password: str, \n                 topic_prefix: str, serial_reader, debug: bool = False):"
    
    content = content.replace(old_signature, new_signature)
    
    log("✅ Patch 2/4 : Constructeur modifié")
    return content, True


def patch_mqtt_publisher_body(content):
    """Ajoute l'initialisation des modules dans MQTTPublisher"""
    log("📝 Patch 3/4 : Ajout de l'initialisation des modules...")
    
    # Chercher où ajouter l'initialisation
    marker1 = "self.topic_prefix = topic_prefix\n        self.debug = debug"
    
    if marker1 not in content:
        marker1 = "self.debug = debug"
    
    if marker1 not in content:
        log("❌ Impossible de trouver l'emplacement pour l'initialisation")
        return content, False
    
    # Vérifier si déjà patché
    if "self.auth = VoltronicAuth" in content:
        log("⚠️  Initialisation déjà présente, skip")
        return content, True
    
    # Ajouter l'initialisation
    init_code = """
        self.serial_reader = serial_reader
        
        # ===== AJOUT : Initialiser modules d'écriture =====
        self.auth = VoltronicAuth(debug=debug)
        self.writer = VoltronicWriter(self.auth, debug=debug)
        self.command_handler = MQTTCommandHandler(
            topic_prefix, self.writer, serial_reader, debug
        )
        # =================================================="""
    
    content = content.replace(marker1, marker1 + init_code)
    
    # Ajouter le setup du handler MQTT
    marker2 = "if user:\n            self.client.username_pw_set(user, password)"
    
    if marker2 not in content:
        marker2 = "self.client.username_pw_set(user, password)"
    
    if marker2 in content:
        # Vérifier si déjà patché
        if "self.command_handler.setup_mqtt_client" not in content:
            setup_code = """
        
        # ===== AJOUT : Setup handler de commandes =====
        self.command_handler.setup_mqtt_client(self.client)
        # =============================================="""
            
            content = content.replace(marker2, marker2 + setup_code)
    
    log("✅ Patch 3/4 : Initialisation ajoutée")
    return content, True


def patch_main_function(content):
    """Modifie l'appel au constructeur MQTTPublisher dans main()"""
    log("📝 Patch 4/4 : Modification de la fonction main()...")
    
    # Chercher l'appel au constructeur
    old_call = "mqtt_pub = MQTTPublisher(mqtt_host, mqtt_port, mqtt_user, mqtt_pass, topic_prefix, debug)"
    
    if old_call not in content:
        log("⚠️  Appel exact non trouvé, recherche flexible...")
        if "MQTTPublisher(mqtt_host" in content:
            log("⚠️  Trouvé mais format différent")
            # Essayer de le patcher quand même
            import re
            pattern = r'mqtt_pub = MQTTPublisher\(mqtt_host, mqtt_port, mqtt_user, mqtt_pass, topic_prefix, debug\)'
            if re.search(pattern, content):
                content = re.sub(
                    pattern,
                    'mqtt_pub = MQTTPublisher(mqtt_host, mqtt_port, mqtt_user, mqtt_pass, topic_prefix, sr, debug)',
                    content
                )
                log("✅ Patch 4/4 : Appel modifié (regex)")
                return content, True
            else:
                log("❌ Impossible de modifier l'appel automatiquement")
                return content, False
        else:
            log("❌ Appel à MQTTPublisher non trouvé")
            return content, False
    
    # Vérifier si déjà patché
    if "MQTTPublisher(mqtt_host, mqtt_port, mqtt_user, mqtt_pass, topic_prefix, sr, debug)" in content:
        log("⚠️  Appel déjà patché, skip")
        return content, True
    
    # Remplacer l'appel
    new_call = "mqtt_pub = MQTTPublisher(mqtt_host, mqtt_port, mqtt_user, mqtt_pass, topic_prefix, sr, debug)"
    content = content.replace(old_call, new_call)
    
    # Modifier aussi le message de log si présent
    if 'log("[MQTT] ✅ Connecté")' in content:
        content = content.replace(
            'log("[MQTT] ✅ Connecté")',
            'log("[MQTT] ✅ Connecté avec support commandes")'
        )
    
    log("✅ Patch 4/4 : Fonction main() modifiée")
    return content, True


def verify_modules_exist():
    """Vérifie que le dossier modules/ existe"""
    if not os.path.exists("modules"):
        log("❌ ERREUR : Le dossier 'modules/' n'existe pas !")
        log("   Assure-toi d'avoir copié le dossier modules/ dans le même répertoire.")
        return False
    
    required_files = ["__init__.py", "auth.py", "commands.py", "writer.py", "mqtt_handler.py"]
    missing = []
    
    for file in required_files:
        if not os.path.exists(f"modules/{file}"):
            missing.append(file)
    
    if missing:
        log(f"❌ ERREUR : Fichiers manquants dans modules/ : {', '.join(missing)}")
        return False
    
    log("✅ Dossier modules/ vérifié : tous les fichiers présents")
    return True


def main():
    """Fonction principale"""
    print("=" * 70)
    print("🔧 Script de patch automatique pour wks_monitor.py")
    print("=" * 70)
    print()
    
    # Vérifier les arguments
    if len(sys.argv) != 2:
        print("Usage: python3 patch_wks_monitor.py /chemin/vers/wks_monitor.py")
        print()
        print("Exemple:")
        print("  python3 patch_wks_monitor.py wks_monitor.py")
        print("  python3 patch_wks_monitor.py /addon/wks-monitor/wks_monitor.py")
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    # Vérifier que le fichier existe
    if not os.path.exists(filepath):
        log(f"❌ ERREUR : Le fichier '{filepath}' n'existe pas !")
        sys.exit(1)
    
    log(f"📄 Fichier à patcher : {filepath}")
    
    # Vérifier que le dossier modules/ existe
    if not verify_modules_exist():
        sys.exit(1)
    
    # Créer un backup
    backup_path = backup_file(filepath)
    
    # Lire le contenu
    log("📖 Lecture du fichier...")
    content = read_file(filepath)
    original_content = content
    
    # Appliquer les patches
    success_count = 0
    total_patches = 4
    
    content, success = patch_imports(content)
    if success:
        success_count += 1
    
    content, success = patch_mqtt_publisher_init(content)
    if success:
        success_count += 1
    
    content, success = patch_mqtt_publisher_body(content)
    if success:
        success_count += 1
    
    content, success = patch_main_function(content)
    if success:
        success_count += 1
    
    # Vérifier si des modifications ont été faites
    if content == original_content:
        log("⚠️  Aucune modification effectuée")
        log("   Le fichier est peut-être déjà patché ou a une structure différente")
        print()
        response = input("Voulez-vous voir le fichier de backup ? (o/n) : ")
        if response.lower() == 'o':
            log(f"📄 Backup disponible : {backup_path}")
        sys.exit(0)
    
    # Écrire le fichier modifié
    log("💾 Écriture du fichier patché...")
    write_file(filepath, content)
    
    # Résumé
    print()
    print("=" * 70)
    print(f"✅ Patch terminé : {success_count}/{total_patches} modifications appliquées")
    print("=" * 70)
    print()
    
    if success_count == total_patches:
        log("🎉 SUCCÈS COMPLET ! Toutes les modifications ont été appliquées.")
        log("📋 Prochaines étapes :")
        log("   1. Redémarre ton addon WKS Monitor")
        log("   2. Vérifie les logs pour '[MQTT] Subscribed to wks/command/#'")
        log("   3. Teste une commande via MQTT")
        print()
        log(f"💾 Backup disponible : {backup_path}")
    else:
        log("⚠️  SUCCÈS PARTIEL : Certaines modifications n'ont pas pu être appliquées automatiquement")
        log("📋 Actions requises :")
        log("   1. Vérifie le fichier manuellement")
        log("   2. Consulte integration.py pour les modifications manquantes")
        log(f"   3. En cas de problème, restaure le backup : {backup_path}")
    
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        log("🛑 Interrompu par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print()
        log(f"❌ ERREUR CRITIQUE : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
