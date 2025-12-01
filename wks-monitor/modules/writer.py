#!/usr/bin/env python3
"""
writer.py - Module d'écriture série pour Voltronic
===================================================

Gère l'envoi de commandes d'écriture (P...) aux onduleurs
"""

import time
from datetime import datetime
from typing import Tuple
import serial

from auth import VoltronicAuth, calculate_crc


def log(msg: str):
    """Log helper"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


class VoltronicWriter:
    """
    Gestionnaire d'écriture de paramètres Voltronic
    """
    
    def __init__(self, auth: VoltronicAuth, debug: bool = False):
        """
        Args:
            auth: Instance de VoltronicAuth pour l'authentification
            debug: Mode debug
        """
        self.auth = auth
        self.debug = debug
    
    def write_parameter(self, ser: serial.Serial, command: str, 
                       extra_wait: float = 0.2) -> Tuple[bool, str]:
        """
        Écrit un paramètre sur l'onduleur
        
        Args:
            ser: Port série ouvert
            command: Commande à envoyer (ex: "PBT58.4")
            extra_wait: Temps d'attente supplémentaire après envoi
            
        Returns:
            (success: bool, message: str)
            
        Exemple:
            >>> writer = VoltronicWriter(auth)
            >>> success, msg = writer.write_parameter(ser, "PBFT54.4")
            >>> if success:
            ...     print("Floating voltage modifié!")
        """
        if not ser or not ser.is_open:
            return False, "Port série non ouvert"
        
        # 1. S'authentifier d'abord
        if not self.auth.authenticate(ser):
            return False, "Authentification échouée"
        
        # 2. Préparer la commande
        try:
            cmd_bytes = command.encode()
            crc = calculate_crc(cmd_bytes)
            full_cmd = cmd_bytes + crc + b"\r"
            
            if self.debug:
                log(f"[WRITE] Envoi commande: {command}")
            
            # 3. Envoyer la commande
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            ser.write(full_cmd)
            ser.flush()
            time.sleep(0.2 + extra_wait)
            
            # 4. Lire la réponse
            response = ser.read_until(b"\r")
            resp_str = response.decode(errors="ignore").strip()
            
            # 5. Analyser la réponse
            if "(ACK" in resp_str or "ACK" in resp_str:
                log(f"[WRITE] ✅ Commande acceptée: {command}")
                return True, f"Succès: {resp_str}"
            elif "(NAK" in resp_str or "NAK" in resp_str:
                log(f"[WRITE] ❌ Commande refusée: {command} - {resp_str}")
                return False, f"Refusé par l'onduleur: {resp_str}"
            else:
                log(f"[WRITE] ⚠️ Réponse inattendue pour {command}: {resp_str}")
                return False, f"Réponse inattendue: {resp_str}"
                
        except Exception as e:
            log(f"[WRITE] ❌ Erreur lors de l'envoi de {command}: {e}")
            return False, f"Erreur: {str(e)}"
    
    def write_multiple_parameters(self, ser: serial.Serial, 
                                  commands: dict) -> dict:
        """
        Écrit plusieurs paramètres successivement
        
        Args:
            ser: Port série ouvert
            commands: Dictionnaire {nom: commande}
            
        Returns:
            Dictionnaire {nom: (success, message)}
            
        Exemple:
            >>> commands = {
            ...     "float": "PBFT54.4",
            ...     "recharge": "PBR49.0"
            ... }
            >>> results = writer.write_multiple_parameters(ser, commands)
        """
        results = {}
        
        for name, command in commands.items():
            success, message = self.write_parameter(ser, command)
            results[name] = (success, message)
            
            # Petite pause entre chaque commande
            time.sleep(0.3)
        
        return results
    
    def apply_preset(self, ser: serial.Serial, preset_commands: dict) -> dict:
        """
        Applique un preset complet de configuration
        
        Args:
            ser: Port série ouvert
            preset_commands: Dictionnaire de commandes (depuis VoltronicPresets)
            
        Returns:
            Résultats de l'application
        """
        log(f"[PRESET] Application de {len(preset_commands)} paramètres...")
        results = self.write_multiple_parameters(ser, preset_commands)
        
        # Compter les succès
        successes = sum(1 for success, _ in results.values() if success)
        total = len(results)
        
        log(f"[PRESET] ✅ {successes}/{total} paramètres appliqués avec succès")
        
        return results


class SafetyValidator:
    """
    Validateur de sécurité pour les paramètres batterie
    """
    
    @staticmethod
    def validate_voltage_range(bulk: float, float_v: float, 
                              cutoff: float, recharge: float) -> Tuple[bool, str]:
        """
        Valide la cohérence d'une configuration de tensions
        
        Args:
            bulk: Tension de charge bulk
            float_v: Tension de floating
            cutoff: Tension de coupure
            recharge: Tension de recharge
            
        Returns:
            (valid: bool, message: str)
        """
        # Vérifier l'ordre logique: bulk > float > recharge > cutoff
        if not (bulk > float_v > recharge > cutoff):
            return False, (
                f"Ordre des tensions incorrect!\n"
                f"Doit être: Bulk ({bulk}V) > Float ({float_v}V) > "
                f"Recharge ({recharge}V) > Cutoff ({cutoff}V)"
            )
        
        # Vérifier les écarts minimums
        if (bulk - float_v) < 2.0:
            return False, f"Écart Bulk-Float trop faible: {bulk - float_v:.1f}V (min 2V)"
        
        if (float_v - recharge) < 3.0:
            return False, f"Écart Float-Recharge trop faible: {float_v - recharge:.1f}V (min 3V)"
        
        if (recharge - cutoff) < 3.0:
            return False, f"Écart Recharge-Cutoff trop faible: {recharge - cutoff:.1f}V (min 3V)"
        
        return True, "Configuration valide ✅"
    
    @staticmethod
    def validate_current_vs_bms(charge_current: int, bms_limit: int) -> Tuple[bool, str]:
        """
        Valide que le courant de charge ne dépasse pas la limite BMS
        
        Args:
            charge_current: Courant de charge configuré
            bms_limit: Limite du BMS
            
        Returns:
            (valid: bool, message: str)
        """
        safety_margin = 0.9  # 90% de la limite
        safe_limit = int(bms_limit * safety_margin)
        
        if charge_current > bms_limit:
            return False, (
                f"⚠️ DANGER: Courant {charge_current}A > Limite BMS {bms_limit}A!\n"
                f"Le BMS coupera la charge!"
            )
        
        if charge_current > safe_limit:
            return False, (
                f"⚠️ Attention: Courant {charge_current}A proche de la limite BMS {bms_limit}A\n"
                f"Recommandé: max {safe_limit}A (90% de {bms_limit}A)"
            )
        
        return True, f"Courant sûr: {charge_current}A / {bms_limit}A ✅"
    
    @staticmethod
    def validate_parallel_inverters_current(current_per_inverter: int, 
                                           inverter_count: int, 
                                           bms_limit: int) -> Tuple[bool, str]:
        """
        Valide la configuration de courant pour onduleurs en parallèle
        
        Args:
            current_per_inverter: Courant configuré par onduleur
            inverter_count: Nombre d'onduleurs
            bms_limit: Limite totale du BMS
            
        Returns:
            (valid: bool, message: str)
        """
        total_current = current_per_inverter * inverter_count
        
        valid, msg = SafetyValidator.validate_current_vs_bms(total_current, bms_limit)
        
        if not valid:
            msg += f"\n(Configuration: {inverter_count} onduleurs × {current_per_inverter}A = {total_current}A)"
        
        return valid, msg
