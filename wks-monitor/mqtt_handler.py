#!/usr/bin/env python3
"""
mqtt_handler.py - Gestionnaire MQTT pour commandes d'écriture
==============================================================

Gère la réception des commandes MQTT et leur exécution
"""

import json
from datetime import datetime
from typing import Optional
import paho.mqtt.client as mqtt

from commands import VoltronicCommands, VoltronicPresets
from writer import VoltronicWriter


def log(msg: str):
    """Log helper"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


class MQTTCommandHandler:
    """
    Gestionnaire de commandes MQTT pour Voltronic
    
    Subscribe aux topics de commande et exécute les modifications de paramètres
    """
    
    def __init__(self, topic_prefix: str, writer: VoltronicWriter, 
                 serial_reader, debug: bool = False):
        """
        Args:
            topic_prefix: Préfixe des topics MQTT (ex: "wks")
            writer: Instance de VoltronicWriter
            serial_reader: Référence au SerialReader (pour accès au port série)
            debug: Mode debug
        """
        self.topic_prefix = topic_prefix
        self.writer = writer
        self.serial_reader = serial_reader
        self.debug = debug
        self.command_topic = f"{topic_prefix}/command/#"
        self.result_topic = f"{topic_prefix}/command/result"
        
        # Stats
        self.commands_received = 0
        self.commands_successful = 0
        self.commands_failed = 0
    
    def setup_mqtt_client(self, client: mqtt.Client):
        """
        Configure le client MQTT avec le handler de messages
        
        Args:
            client: Client MQTT paho
        """
        client.on_message = self.on_message
        client.subscribe(self.command_topic)
        log(f"[MQTT] Subscribed to {self.command_topic}")
    
    def on_message(self, client, userdata, msg):
        """
        Handler appelé lors de la réception d'un message MQTT
        
        Topics supportés:
        - {prefix}/command/set_battery_voltage {"voltage": 58.4}
        - {prefix}/command/set_float_voltage {"voltage": 54.4}
        - {prefix}/command/set_cutoff_voltage {"voltage": 44.8}
        - {prefix}/command/set_recharge_voltage {"voltage": 49.0}
        - {prefix}/command/set_max_charge_current {"current": 60}
        - {prefix}/command/set_max_ac_charge_current {"current": 20}
        - {prefix}/command/apply_preset {"preset": "balanced"}
        """
        try:
            self.commands_received += 1
            
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            log(f"[MQTT-CMD] Reçu #{self.commands_received}: {topic}")
            if self.debug:
                log(f"[MQTT-CMD] Payload: {payload}")
            
            # Extraire la commande du topic
            command = topic.split("/")[-1]
            
            # Router vers le bon handler
            if command == "set_battery_voltage":
                success, message = self._handle_set_battery_voltage(payload)
            elif command == "set_float_voltage":
                success, message = self._handle_set_float_voltage(payload)
            elif command == "set_cutoff_voltage":
                success, message = self._handle_set_cutoff_voltage(payload)
            elif command == "set_recharge_voltage":
                success, message = self._handle_set_recharge_voltage(payload)
            elif command == "set_max_charge_current":
                success, message = self._handle_set_max_charge_current(payload)
            elif command == "set_max_ac_charge_current":
                success, message = self._handle_set_max_ac_charge_current(payload)
            elif command == "apply_preset":
                success, message = self._handle_apply_preset(payload)
            elif command == "get_stats":
                success, message = self._handle_get_stats(payload)
            else:
                success = False
                message = f"Commande inconnue: {command}"
            
            # Mettre à jour les stats
            if success:
                self.commands_successful += 1
            else:
                self.commands_failed += 1
            
            # Publier le résultat
            result = {
                "command": command,
                "payload": payload,
                "success": success,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "command_id": self.commands_received
            }
            
            client.publish(self.result_topic, json.dumps(result), qos=0, retain=False)
            
            if self.debug:
                status = "✅" if success else "❌"
                log(f"[MQTT-CMD] {status} {command}: {message}")
            
        except json.JSONDecodeError as e:
            log(f"[MQTT-CMD] ❌ JSON invalide: {e}")
            self._publish_error(client, "JSON invalide", str(e))
        except Exception as e:
            log(f"[MQTT-CMD] ❌ Erreur: {e}")
            self._publish_error(client, "Erreur interne", str(e))
    
    # ============= HANDLERS DE COMMANDES =============
    
    def _handle_set_battery_voltage(self, payload: dict) -> tuple:
        """Handler pour set_battery_voltage"""
        try:
            voltage = float(payload.get("voltage", 0))
            cmd = VoltronicCommands.set_battery_charge_voltage(voltage)
            return self.writer.write_parameter(self.serial_reader.ser, cmd)
        except ValueError as e:
            return False, str(e)
    
    def _handle_set_float_voltage(self, payload: dict) -> tuple:
        """Handler pour set_float_voltage"""
        try:
            voltage = float(payload.get("voltage", 0))
            cmd = VoltronicCommands.set_battery_float_voltage(voltage)
            return self.writer.write_parameter(self.serial_reader.ser, cmd)
        except ValueError as e:
            return False, str(e)
    
    def _handle_set_cutoff_voltage(self, payload: dict) -> tuple:
        """Handler pour set_cutoff_voltage"""
        try:
            voltage = float(payload.get("voltage", 0))
            cmd = VoltronicCommands.set_battery_cutoff_voltage(voltage)
            return self.writer.write_parameter(self.serial_reader.ser, cmd)
        except ValueError as e:
            return False, str(e)
    
    def _handle_set_recharge_voltage(self, payload: dict) -> tuple:
        """Handler pour set_recharge_voltage"""
        try:
            voltage = float(payload.get("voltage", 0))
            cmd = VoltronicCommands.set_battery_recharge_voltage(voltage)
            return self.writer.write_parameter(self.serial_reader.ser, cmd)
        except ValueError as e:
            return False, str(e)
    
    def _handle_set_max_charge_current(self, payload: dict) -> tuple:
        """Handler pour set_max_charge_current"""
        try:
            current = int(payload.get("current", 0))
            cmd = VoltronicCommands.set_max_charge_current(current)
            return self.writer.write_parameter(self.serial_reader.ser, cmd)
        except ValueError as e:
            return False, str(e)
    
    def _handle_set_max_ac_charge_current(self, payload: dict) -> tuple:
        """Handler pour set_max_ac_charge_current"""
        try:
            current = int(payload.get("current", 0))
            cmd = VoltronicCommands.set_max_ac_charge_current(current)
            return self.writer.write_parameter(self.serial_reader.ser, cmd)
        except ValueError as e:
            return False, str(e)
    
    def _handle_apply_preset(self, payload: dict) -> tuple:
        """Handler pour apply_preset"""
        try:
            preset_name = payload.get("preset", "")
            if not preset_name:
                return False, "Nom de preset manquant"
            
            # Obtenir les commandes du preset
            commands = VoltronicPresets.get_preset_commands(preset_name)
            
            # Appliquer le preset
            results = self.writer.apply_preset(self.serial_reader.ser, commands)
            
            # Compter les succès
            successes = sum(1 for success, _ in results.values() if success)
            total = len(results)
            
            if successes == total:
                return True, f"Preset '{preset_name}' appliqué: {successes}/{total} OK"
            else:
                return False, f"Preset '{preset_name}' partiellement appliqué: {successes}/{total} OK"
            
        except ValueError as e:
            return False, str(e)
    
    def _handle_get_stats(self, payload: dict) -> tuple:
        """Handler pour get_stats - retourne les statistiques"""
        stats = {
            "total_commands": self.commands_received,
            "successful": self.commands_successful,
            "failed": self.commands_failed,
            "success_rate": round(self.commands_successful / self.commands_received * 100, 1) 
                           if self.commands_received > 0 else 0
        }
        return True, json.dumps(stats)
    
    def _publish_error(self, client: mqtt.Client, error_type: str, details: str):
        """Publie une erreur sur le topic result"""
        result = {
            "success": False,
            "error_type": error_type,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        client.publish(self.result_topic, json.dumps(result), qos=0, retain=False)
