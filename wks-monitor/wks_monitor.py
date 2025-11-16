import json
import os
import sys
import time
import threading
from pathlib import Path

import paho.mqtt.client as mqtt
import serial

OPTIONS_PATH = Path("/data/options.json")
# CRC pré-calculés pour les commandes QPGS0/1/2 (MKS I 5kVA à 2400 bauds)
CRC_QPGS = {
    0: (0x3F, 0xDA),  # QPGS0
    1: (0x2F, 0xFB),  # QPGS1
    2: (0x1F, 0x98),  # QPGS2
}

def log(msg):
    print(msg, flush=True)

def load_options():
    with open(OPTIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

class SerialReader:
    def __init__(self, port, baudrate, timeout, open_retry_sec=3, debug=False):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.open_retry_sec = open_retry_sec
        self.debug = debug
        self.ser = None
        self.lock = threading.Lock()

    def open(self):
        while True:
            try:
                if self.debug:
                    log(f"[SERIAL] Ouverture {self.port} @ {self.baudrate} 8N1 (timeout {self.timeout}s)")
                self.ser = serial.Serial(
                    self.port,
                    baudrate=self.baudrate,
                    bytesize=8,
                    parity=serial.PARITY_NONE,
                    stopbits=1,
                    timeout=self.timeout,
                    write_timeout=self.timeout,
                    exclusive=True
                )
                time.sleep(1.0)
                if self.debug:
                    log("[SERIAL] Ouvert ✅")
                return
            except Exception as e:
                log(f"[SERIAL] Échec ouverture ({e}); retry dans {self.open_retry_sec}s...")
                time.sleep(self.open_retry_sec)

    def close(self):
        with self.lock:
            if self.ser:
                try:
                    self.ser.close()
                except Exception:
                    pass
                self.ser = None

    def query(self, cmd: bytes):
        """Envoie une commande et lit jusqu'au CR. None si pas de réponse"""
        with self.lock:
            if not self.ser or not self.ser.is_open:
                return None
            try:
                try:
                    self.ser.reset_input_buffer()
                    self.ser.reset_output_buffer()
                except Exception:
                    pass

                self.ser.write(cmd)
                self.ser.flush()
                time.sleep(0.15)
                resp = self.ser.read_until(b"\r")
                return resp if resp else None
            except serial.SerialException as e:
                log(f"[SERIAL] SerialException: {e}")
                return None
            except Exception as e:
                log(f"[SERIAL] Exception: {e}")
                return None

def is_valid_qpgs(resp: bytes) -> bool:
    if not resp:
        return False
    # On ignore les NAK
    if resp.startswith(b"(NAK"):
        return False
    # Trame WKS classique : commence par "(" et finit par CR
    return resp.startswith(b"(") and resp.endswith(b"\r")

def parse_qpgs(resp: bytes) -> dict:
    """
    Parse une trame QPGS des onduleurs WKS/Voltronic en parallèle.
    
    Format typique (20+ champs séparés par espaces):
    (230.5 50.0 230.5 50.0 1200 1200 015 54.2 12.5 075 385.0 012.5 045 350 045 00010110 1 3 000 010<CR>
    
    Retourne un dict avec tous les champs parsés + la trame brute.
    """
    try:
        # Décodage et nettoyage
        txt = resp.strip().decode(errors="ignore")
        
        # Suppression des parenthèses et CR
        if txt.startswith("("):
            txt = txt[1:]
        if txt.endswith("\r"):
            txt = txt[:-1]
        
        # Split par espaces
        fields = txt.split()
        
        # Vérification du nombre minimal de champs
        if len(fields) < 18:
            log(f"[PARSER] Trame trop courte: {len(fields)} champs (attendu >= 18)")
            return {"raw": txt, "error": "incomplete_frame"}
        
        # Helper function: convertir en int même si le format est "000.0"
        def safe_int(val):
            return int(float(val))
        
        # Parsing des champs individuels
        data = {
            "raw": txt,
            
            # Champs 0-1: Sortie AC (phase 1)
            "ac_output_voltage": float(fields[0]),
            "ac_output_freq": float(fields[1]),
            
            # Champs 2-3: Sortie AC (dupliqué, on ignore)
            
            # Champs 4-6: Puissance et charge
            "output_apparent_power_va": safe_int(fields[4]),
            "output_active_power_w": safe_int(fields[5]),
            "output_load_pct": safe_int(fields[6]),
            
            # Champs 7-9: Batterie
            "battery_voltage": float(fields[7]),
            "battery_charge_current_a": float(fields[8]),
            "battery_capacity_pct": safe_int(fields[9]),
            
            # Champs 10-11: PV (solaire)
            "pv_input_voltage": float(fields[10]),
            "pv_input_current_a": float(fields[11]),
            
            # Champ 12: Température dissipateur
            "heatsink_temp": safe_int(fields[12]),
            
            # Champ 13: Bus DC
            "dc_bus_voltage": safe_int(fields[13]),
            
            # Champ 14: Température batterie
            "battery_temp_c": safe_int(fields[14]),
            
            # Champ 15: Flags d'état (8 bits binaires)
            "status_flags_raw": fields[15],
            
            # Champ 16: Rôle dans le parallèle (0=standalone, 1=master, 2=slave)
            "parallel_role": safe_int(fields[16]),
            
            # Champ 17: Nombre total d'unités en parallèle
            "total_units": safe_int(fields[17]),
        }
        
        # Décodage des flags d'état (champ 15)
        # Format: 8 caractères binaires (0 ou 1)
        # Exemple: "00010110"
        flags_str = fields[15]
        if len(flags_str) >= 8:
            data["status_flags"] = {
                "inverter_output": bool(int(flags_str[0])),      # Bit 0: Sortie onduleur active
                "pv_charging": bool(int(flags_str[1])),          # Bit 1: Charge PV active
                "ac_charging": bool(int(flags_str[2])),          # Bit 2: Charge secteur active
                "load_on_battery": bool(int(flags_str[3])),      # Bit 3: Charge sur batterie
                "fault": bool(int(flags_str[4])),                # Bit 4: Défaut/erreur
                "line_mode": bool(int(flags_str[5])),            # Bit 5: Mode ligne (vs batterie)
                "test_mode": bool(int(flags_str[6])),            # Bit 6: Mode test
                "silence_buzzer": bool(int(flags_str[7])),       # Bit 7: Buzzer désactivé
            }
        
        # Ajout de champs calculés utiles
        data["pv_input_power_w"] = round(data["pv_input_voltage"] * data["pv_input_current_a"], 1)
        data["battery_charge_power_w"] = round(data["battery_voltage"] * data["battery_charge_current_a"], 1)
        
        return data
        
    except (ValueError, IndexError) as e:
        log(f"[PARSER] Erreur parsing: {e}")
        # En cas d'erreur, on retourne au moins la trame brute
        txt = resp.strip().decode(errors="ignore")
        return {
            "raw": txt,
            "error": str(e)
        }

def mqtt_client(host, port, user, password, client_id="wks-monitor"):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, clean_session=True)
    if user:
        client.username_pw_set(user, password)
    client.connect(host, port, keepalive=30)
    client.loop_start()
    return client

def main():
    if not OPTIONS_PATH.exists():
        log("❌ /data/options.json introuvable")
        sys.exit(1)

    opt = load_options()
    port = opt.get("port")
    baudrate = int(opt.get("baudrate", 2400))
    inverter_count = int(opt.get("inverter_count", 3))
    poll_interval = float(opt.get("poll_interval", 2.0))
    debug = bool(opt.get("debug", False))
    read_timeout = float(opt.get("read_timeout", 2.5))
    open_retry_sec = int(opt.get("open_retry_sec", 3))
    max_consecutive_fail = int(opt.get("max_consecutive_fail", 10))

    mqtt_host = opt.get("mqtt_host", "core-mosquitto.local.hass.io")
    mqtt_port = int(opt.get("mqtt_port", 1883))
    mqtt_user = opt.get("mqtt_user", "")
    mqtt_pass = opt.get("mqtt_password", "")
    topic_prefix = opt.get("mqtt_topic_prefix", "wks")

    log(f"[BOOT] 🚀 Lancement du lecteur WKS - rafraîchissement {poll_interval}s")
    log(f"[BOOT] Port: {port} | Baud: {baudrate} | Onduleurs: {inverter_count}")

    sr = SerialReader(port, baudrate, read_timeout, open_retry_sec=open_retry_sec, debug=debug)
    sr.open()

    # Connexion MQTT avec gestion d'erreur
    try:
        client = mqtt_client(mqtt_host, mqtt_port, mqtt_user, mqtt_pass)
        log("[MQTT] ✅ Connecté")
    except Exception as e:
        log(f"[MQTT] ❌ Échec connexion: {e}")
        sys.exit(1)

    consecutive_fail = 0

    while True:
        any_ok = False
        for idx in range(inverter_count):
            # Construction QPGSx + CRC + CR
            base_cmd = f"QPGS{idx}".encode()

            if idx in CRC_QPGS:
                hi, lo = CRC_QPGS[idx]
                cmd = base_cmd + bytes([hi, lo]) + b"\r"
            else:
                # Sécurité : si jamais inverter_count > 3
                cmd = base_cmd + b"\r"

            resp = sr.query(cmd)

            if not resp or not is_valid_qpgs(resp):
                log(f"[WARN] ⚠️ Aucune réponse ou trame invalide pour QPGS{idx}")
                consecutive_fail += 1
                continue

            try:
                data = parse_qpgs(resp)
                
                # Vérification qu'on a bien des données valides
                if "error" in data:
                    log(f"[WARN] ⚠️ Erreur parsing QPGS{idx}: {data['error']}")
                    consecutive_fail += 1
                    continue
                
                topic = f"{topic_prefix}/{idx}/status"
                client.publish(topic, json.dumps(data), qos=0, retain=True)
                
                if debug:
                    log(f"[OK] QPGS{idx} → {data.get('output_active_power_w', 0)}W, "
                        f"Batt: {data.get('battery_voltage', 0)}V, "
                        f"PV: {data.get('pv_input_voltage', 0)}V")
                else:
                    log(f"[OK] QPGS{idx} → publish {topic}")
                
                any_ok = True
                
            except Exception as e:
                log(f"[PARSER] Erreur parse QPGS{idx}: {e}")
                consecutive_fail += 1

            time.sleep(0.05)

        # Gestion des échecs consécutifs
        if any_ok:
            consecutive_fail = 0
        elif consecutive_fail >= max_consecutive_fail:
            log("[HEAL] Trop d'échecs consécutifs — on referme/réouvre le port proprement")
            sr.close()
            time.sleep(1.0)
            sr.open()
            consecutive_fail = 0

        # Délai avant prochain cycle
        if not any_ok and poll_interval < 3.0:
            log("⚠️ Communication instable, passage temporaire à 3s")
            time.sleep(3.0)
        else:
            time.sleep(poll_interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("🛑 Arrêt demandé")
        sys.exit(0)
    except Exception as e:
        log(f"❌ Crash: {e}")
        time.sleep(1)
        sys.exit(1)
