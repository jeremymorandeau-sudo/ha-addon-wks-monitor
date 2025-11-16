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
    # Trame WKS : peut commencer par un chiffre (index parallèle) ou "("
    # et finit par CR
    return resp.endswith(b"\r") and len(resp) > 10

def parse_qpgs(resp: bytes) -> dict:
    """
    Parse une trame QPGS des onduleurs WKS/Voltronic en mode parallèle (format étendu).
    
    Format: 27 champs séparés par espaces
    Exemple: 1 73252019060406 B 00 000.0 00.00 230.2 49.99 0554 0554 013 52.7 000 077 075.3 001 00761 00713 005 10100110 4 1 050 120 20 01 010
    
    Retourne un dict avec tous les champs parsés + la trame brute.
    """
    try:
        # Décodage et nettoyage
        txt = resp.strip().decode(errors="ignore")
        
        # Suppression des caractères de contrôle en fin de trame
        txt = txt.split('\r')[0].split('\n')[0]
        
        # Suppression de la parenthèse si présente
        if txt.startswith("("):
            txt = txt[1:]
        
        # Split par espaces
        fields = txt.split()
        
        # Vérification du nombre minimal de champs
        if len(fields) < 20:
            log(f"[PARSER] Trame trop courte: {len(fields)} champs (attendu >= 20)")
            return {"raw": txt, "error": "incomplete_frame", "field_count": len(fields)}
        
        # Helper function: convertir en int même si le format est "000.0"
        def safe_int(val):
            try:
                return int(float(val))
            except:
                return 0
        
        def safe_float(val):
            try:
                return float(val)
            except:
                return 0.0
        
        # Parsing des champs individuels (format étendu WKS Parallel)
        data = {
            "raw": txt,
            "field_count": len(fields),
            
            # Champ 0: Index de l'onduleur dans le système parallèle
            "parallel_index": safe_int(fields[0]),
            
            # Champ 1: Numéro de série
            "serial_number": fields[1] if len(fields) > 1 else "",
            
            # Champ 2: Mode de travail (B=Battery, L=Line, F=Fault, etc.)
            "work_mode": fields[2] if len(fields) > 2 else "",
            
            # Champ 3: Code erreur (00 = pas d'erreur)
            "fault_code": fields[3] if len(fields) > 3 else "00",
            
            # Champs 4-5: Entrée AC (secteur)
            "grid_voltage": safe_float(fields[4]) if len(fields) > 4 else 0.0,
            "grid_freq": safe_float(fields[5]) if len(fields) > 5 else 0.0,
            
            # Champs 6-7: Sortie AC (onduleur)
            "ac_output_voltage": safe_float(fields[6]) if len(fields) > 6 else 0.0,
            "ac_output_freq": safe_float(fields[7]) if len(fields) > 7 else 0.0,
            
            # Champs 8-10: Puissance et charge (cet onduleur)
            "output_apparent_power_va": safe_int(fields[8]) if len(fields) > 8 else 0,
            "output_active_power_w": safe_int(fields[9]) if len(fields) > 9 else 0,
            "output_load_pct": safe_int(fields[10]) if len(fields) > 10 else 0,
            
            # Champs 11-13: Batterie
            "battery_voltage": safe_float(fields[11]) if len(fields) > 11 else 0.0,
            "battery_charge_current_a": safe_int(fields[12]) if len(fields) > 12 else 0,
            "battery_capacity_pct": safe_int(fields[13]) if len(fields) > 13 else 0,
            
            # Champ 14: Tension PV
            "pv_input_voltage": safe_float(fields[14]) if len(fields) > 14 else 0.0,
            
            # Champ 15: Courant de charge total
            "total_charge_current_a": safe_int(fields[15]) if len(fields) > 15 else 0,
            
            # Champs 16-18: Totaux système parallèle (tous onduleurs)
            "total_apparent_power_va": safe_int(fields[16]) if len(fields) > 16 else 0,
            "total_active_power_w": safe_int(fields[17]) if len(fields) > 17 else 0,
            "total_load_pct": safe_int(fields[18]) if len(fields) > 18 else 0,
            
            # Champ 19: Flags d'état (8 bits binaires)
            "status_flags_raw": fields[19] if len(fields) > 19 else "00000000",
        }
        
        # Champs optionnels supplémentaires (si présents)
        if len(fields) > 20:
            data["fan_lock_status"] = safe_int(fields[20])
        if len(fields) > 21:
            data["eeprom_version"] = safe_int(fields[21])
        if len(fields) > 22:
            data["pv_charge_current_a"] = safe_int(fields[22])
        if len(fields) > 23:
            data["heatsink_temp"] = safe_int(fields[23])
        if len(fields) > 24:
            data["pv_input_current_a"] = safe_int(fields[24])
        
        # Décodage des flags d'état (champ 19)
        # Format: 8 caractères binaires (0 ou 1)
        # Exemple: "10100110"
        flags_str = data["status_flags_raw"]
        if len(flags_str) >= 8:
            data["status_flags"] = {
                "utility_charging": bool(int(flags_str[0])),     # Bit 0: Charge depuis secteur
                "ac_charging": bool(int(flags_str[1])),          # Bit 1: Charge AC active
                "scc_charging": bool(int(flags_str[2])),         # Bit 2: Charge solaire (SCC) active
                "battery_discharging": bool(int(flags_str[3])),  # Bit 3: Batterie en décharge
                "alarm_active": bool(int(flags_str[4])),         # Bit 4: Alarme active
                "line_mode": bool(int(flags_str[5])),            # Bit 5: Mode ligne (vs batterie)
                "test_mode": bool(int(flags_str[6])),            # Bit 6: Mode test
                "reserved": bool(int(flags_str[7])),             # Bit 7: Réservé
            }
        
        # Décodage du mode de travail
        work_mode_map = {
            "B": "Battery",      # Sur batterie
            "L": "Line",         # Sur secteur
            "F": "Fault",        # Défaut
            "P": "Power On",     # Démarrage
            "S": "Standby",      # Veille
            "Y": "Bypass",       # Bypass
        }
        data["work_mode_decoded"] = work_mode_map.get(data["work_mode"], "Unknown")
        
        # Calcul de champs dérivés utiles
        # Puissance PV (si on a tension et courant)
        if "pv_input_current_a" in data and data["pv_input_voltage"] > 0:
            data["pv_input_power_w"] = round(data["pv_input_voltage"] * data["pv_input_current_a"], 1)
        else:
            data["pv_input_power_w"] = 0.0
        
        # Puissance charge batterie
        if data["battery_charge_current_a"] > 0:
            data["battery_charge_power_w"] = round(data["battery_voltage"] * data["battery_charge_current_a"], 1)
        else:
            data["battery_charge_power_w"] = 0.0
        
        # Indicateur de santé
        data["grid_available"] = data["grid_voltage"] > 100.0
        data["pv_active"] = data["pv_input_voltage"] > 50.0
        data["battery_low"] = data["battery_capacity_pct"] < 20
        
        return data
        
    except Exception as e:
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
                    log(f"[WARN] ⚠️ Erreur parsing QPGS{idx}: {data.get('error', 'unknown')} (champs: {data.get('field_count', 0)})")
                    consecutive_fail += 1
                    continue
                
                topic = f"{topic_prefix}/{idx}/status"
                client.publish(topic, json.dumps(data), qos=0, retain=True)
                
                if debug:
                    mode = data.get('work_mode_decoded', '?')
                    power = data.get('output_active_power_w', 0)
                    batt_v = data.get('battery_voltage', 0)
                    batt_pct = data.get('battery_capacity_pct', 0)
                    pv_v = data.get('pv_input_voltage', 0)
                    temp = data.get('heatsink_temp', 0)
                    log(f"[OK] QPGS{idx} → Mode:{mode} | {power}W | Batt:{batt_v}V({batt_pct}%) | PV:{pv_v}V | Temp:{temp}°C")
                else:
                    log(f"[OK] QPGS{idx} → {data.get('output_active_power_w', 0)}W")
                
                any_ok = True
                
            except Exception as e:
                log(f"[PARSER] Exception QPGS{idx}: {e}")
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
