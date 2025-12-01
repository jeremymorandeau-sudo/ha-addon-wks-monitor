#!/usr/bin/env python3
"""
auth.py - Module d'authentification Voltronic
============================================

Gère l'authentification avec les onduleurs Voltronic MKS
Mot de passe standard: "administrator"
"""

import time
from datetime import datetime
from typing import Optional
import serial


def log(msg: str):
    """Log helper"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def calculate_crc(cmd: bytes) -> bytes:
    """CRC XMODEM pour protocole Voltronic"""
    crc = 0
    for byte in cmd:
        crc = crc ^ (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
        crc = crc & 0xFFFF
    return bytes([crc >> 8, crc & 0xFF])


class VoltronicAuth:
    """
    Gestionnaire d'authentification Voltronic
    """
    
    PASSWORD = "administrator"  # Mot de passe standard Voltronic
    AUTH_VALIDITY_SECONDS = 30  # Durée de validité de l'authentification
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.authenticated = False
        self.last_auth_time: Optional[datetime] = None
    
    def is_authenticated(self) -> bool:
        """Vérifie si l'authentification est encore valide"""
        if not self.authenticated or not self.last_auth_time:
            return False
        
        elapsed = (datetime.now() - self.last_auth_time).total_seconds()
        if elapsed < self.AUTH_VALIDITY_SECONDS:
            if self.debug:
                log(f"[AUTH] ✅ Déjà authentifié (il y a {elapsed:.1f}s)")
            return True
        
        return False
    
    def authenticate(self, ser: serial.Serial) -> bool:
        """
        Authentifie avec l'onduleur Voltronic
        
        Args:
            ser: Port série ouvert
            
        Returns:
            True si authentification réussie
        """
        if not ser or not ser.is_open:
            log("[AUTH] ❌ Port série non ouvert")
            return False
        
        # Vérifier si déjà authentifié
        if self.is_authenticated():
            return True
        
        try:
            # Commande: PF<password>
            auth_cmd = f"PF{self.PASSWORD}".encode()
            crc = calculate_crc(auth_cmd)
            full_cmd = auth_cmd + crc + b"\r"
            
            # Envoyer la commande
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            ser.write(full_cmd)
            ser.flush()
            time.sleep(0.2)
            
            # Lire la réponse
            response = ser.read_until(b"\r")
            resp_str = response.decode(errors="ignore").strip()
            
            if "(ACK" in resp_str or "ACK" in resp_str:
                log("[AUTH] ✅ Authentification réussie")
                self.authenticated = True
                self.last_auth_time = datetime.now()
                return True
            
            log(f"[AUTH] ❌ Échec - Réponse: {resp_str}")
            self.authenticated = False
            return False
            
        except Exception as e:
            log(f"[AUTH] ❌ Erreur: {e}")
            self.authenticated = False
            return False
    
    def reset(self):
        """Reset l'état d'authentification"""
        self.authenticated = False
        self.last_auth_time = None
