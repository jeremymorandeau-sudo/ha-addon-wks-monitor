import json
import sys
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any

import paho.mqtt.client as mqtt
import serial

OPTIONS_PATH = Path("/data/options.json")

# CRC pré-calculés pour les commandes principales
CRC_TABLE = {
    "QPGS0": (0x3F, 0xDA),
    "QPGS1": (0x2F, 0xFB),
    "QPGS2": (0x1F, 0x98),
    "QPIGS": (0xB7, 0xA9),
    "QPIRI": (0xF8, 0x54),
    "QPIWS": (0x44, 0x4D),
    "QMOD": (0x49, 0xC1),
    "QPI": (0xBE, 0xAC),
}

def log(msg: str):
    print(msg, flush=True)

def load_options() -> dict:
    with open(OPTIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def calculate_crc(cmd: bytes) -> bytes:
    """Calcul CRC Voltronic si pas dans la table"""
    crc = 0
    for byte in cmd:
        crc = crc ^ byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc = crc >> 1
    return bytes([crc >> 8, crc & 0xFF])

class SerialReader:
    def __init__(self, port: str, baudrate: int, timeout: float, 
                 open_retry_sec: int = 3, debug: bool = False):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.open_retry_sec = open_retry_sec
        self.debug = debug
        self.ser: Optional[serial.Serial] = None
        self.lock = threading.Lock()

    def open(self):
        while True:
            try:
                if self.debug:
                    log(f"[SERIAL] Ouverture {self.port} @ {self.baudrate} 8N1")
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
                    log("[SERIAL] ✅ Ouvert")
                return
            except Exception as e:
                log(f"[SERIAL] ❌ Échec: {e} - Retry dans {self.open_retry_sec}s")
                time.sleep(self.open_retry_sec)

    def close(self):
        with self.lock:
            if self.ser:
                try:
                    self.ser.close()
                except Exception:
                    pass
                self.ser = None

    def query(self, cmd: str) -> Optional[bytes]:
        """Envoie une commande et lit la réponse"""
        with self.lock:
            if not self.ser or not self.ser.is_open:
                return None
            try:
                # Construction commande avec CRC
                cmd_bytes = cmd.encode()
                if cmd in CRC_TABLE:
                    hi, lo = CRC_TABLE[cmd]
                    full_cmd = cmd_bytes + bytes([hi, lo]) + b"\r"
                else:
                    crc = calculate_crc(cmd_bytes)
                    full_cmd = cmd_bytes + crc + b"\r"
                
                # Envoi
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                self.ser.write(full_cmd)
                self.ser.flush()
                time.sleep(0.15)
                
                # Lecture réponse
                resp = self.ser.read_until(b"\r")
                return resp if resp else None
                
            except serial.SerialException as e:
                log(f"[SERIAL] Exception: {e}")
                return None
            except Exception as e:
                log(f"[SERIAL] Erreur: {e}")
                return None

class VoltronicParser:
    """Parser pour toutes les commandes Voltronic"""
    
    @staticmethod
    def safe_int(val: str) -> int:
        try:
            return int(float(val))
        except:
            return 0
    
    @staticmethod
    def safe_float(val: str) -> float:
        try:
            return float(val)
        except:
            return 0.0
    
    @staticmethod
    def parse_qpgs(resp: bytes) -> Dict[str, Any]:
        """Parse QPGS - Status parallèle (27 champs)"""
        try:
            txt = resp.strip().decode(errors="ignore").split('\r')[0]
            if txt.startswith("("):
                txt = txt[1:]
            
            fields = txt.split()
            if len(fields) < 20:
                return {"raw": txt, "error": "incomplete_frame"}
            
            data = {
                "raw": txt,
                "parallel_index": VoltronicParser.safe_int(fields[0]),
                "serial_number": fields[1] if len(fields) > 1 else "",
                "work_mode": fields[2] if len(fields) > 2 else "",
                "fault_code": fields[3] if len(fields) > 3 else "00",
                "grid_voltage": VoltronicParser.safe_float(fields[4]) if len(fields) > 4 else 0.0,
                "grid_freq": VoltronicParser.safe_float(fields[5]) if len(fields) > 5 else 0.0,
                "ac_output_voltage": VoltronicParser.safe_float(fields[6]) if len(fields) > 6 else 0.0,
                "ac_output_freq": VoltronicParser.safe_float(fields[7]) if len(fields) > 7 else 0.0,
                "output_apparent_power_va": VoltronicParser.safe_int(fields[8]) if len(fields) > 8 else 0,
                "output_active_power_w": VoltronicParser.safe_int(fields[9]) if len(fields) > 9 else 0,
                "output_load_pct": VoltronicParser.safe_int(fields[10]) if len(fields) > 10 else 0,
                "battery_voltage": VoltronicParser.safe_float(fields[11]) if len(fields) > 11 else 0.0,
                "battery_charge_current_a": VoltronicParser.safe_int(fields[12]) if len(fields) > 12 else 0,
                "battery_capacity_pct": VoltronicParser.safe_int(fields[13]) if len(fields) > 13 else 0,
                "pv_input_voltage": VoltronicParser.safe_float(fields[14]) if len(fields) > 14 else 0.0,
                "total_charge_current_a": VoltronicParser.safe_int(fields[15]) if len(fields) > 15 else 0,
                "total_apparent_power_va": VoltronicParser.safe_int(fields[16]) if len(fields) > 16 else 0,
                "total_active_power_w": VoltronicParser.safe_int(fields[17]) if len(fields) > 17 else 0,
                "total_load_pct": VoltronicParser.safe_int(fields[18]) if len(fields) > 18 else 0,
                "status_flags_raw": fields[19] if len(fields) > 19 else "00000000",
            }
            
            # Champs optionnels
            if len(fields) > 20:
                data["fan_lock_status"] = VoltronicParser.safe_int(fields[20])
            if len(fields) > 21:
                data["eeprom_version"] = VoltronicParser.safe_int(fields[21])
            if len(fields) > 22:
                data["pv_charge_current_a"] = VoltronicParser.safe_int(fields[22])
            if len(fields) > 23:
                data["heatsink_temp"] = VoltronicParser.safe_int(fields[23])
            if len(fields) > 24:
                data["pv_input_current_a"] = VoltronicParser.safe_int(fields[24])
            
            # Décodage status flags
            flags = data["status_flags_raw"]
            if len(flags) >= 8:
                data["status_flags"] = {
                    "utility_charging": bool(int(flags[0])),
                    "ac_charging": bool(int(flags[1])),
                    "scc_charging": bool(int(flags[2])),
                    "battery_discharging": bool(int(flags[3])),
                    "alarm_active": bool(int(flags[4])),
                    "line_mode": bool(int(flags[5])),
                    "test_mode": bool(int(flags[6])),
                }
            
            # Champs calculés
            if "pv_input_current_a" in data:
                data["pv_input_power_w"] = round(data["pv_input_voltage"] * data["pv_input_current_a"], 1)
            
            work_modes = {"B": "Battery", "L": "Line", "F": "Fault", "P": "PowerOn", "S": "Standby"}
            data["work_mode_decoded"] = work_modes.get(data["work_mode"], "Unknown")
            
            return data
        except Exception as e:
            log(f"[PARSER] Erreur QPGS: {e}")
            return {"raw": resp.decode(errors="ignore"), "error": str(e)}
    
    @staticmethod
    def parse_qpigs(resp: bytes) -> Dict[str, Any]:
        """Parse QPIGS - General Status (≈18 champs)"""
        try:
            txt = resp.strip().decode(errors="ignore").split('\r')[0]
            if txt.startswith("("):
                txt = txt[1:]
            
            fields = txt.split()
            if len(fields) < 16:
                return {"raw": txt, "error": "incomplete_qpigs"}
            
            data = {
                "raw": txt,
                "grid_voltage": VoltronicParser.safe_float(fields[0]),
                "grid_freq": VoltronicParser.safe_float(fields[1]),
                "ac_output_voltage": VoltronicParser.safe_float(fields[2]),
                "ac_output_freq": VoltronicParser.safe_float(fields[3]),
                "output_apparent_power_va": VoltronicParser.safe_int(fields[4]),
                "output_active_power_w": VoltronicParser.safe_int(fields[5]),
                "output_load_pct": VoltronicParser.safe_int(fields[6]),
                "bus_voltage": VoltronicParser.safe_int(fields[7]),
                "battery_voltage": VoltronicParser.safe_float(fields[8]),
                "battery_charge_current_a": VoltronicParser.safe_int(fields[9]),
                "battery_capacity_pct": VoltronicParser.safe_int(fields[10]),
                "heatsink_temp": VoltronicParser.safe_int(fields[11]),
                "pv_input_current_a": VoltronicParser.safe_float(fields[12]),
                "pv_input_voltage": VoltronicParser.safe_float(fields[13]),
                "battery_voltage_scc": VoltronicParser.safe_float(fields[14]),
                "battery_discharge_current_a": VoltronicParser.safe_int(fields[15]),
            }
            
            # Status byte (si présent)
            if len(fields) > 16:
                status = fields[16]
                data["device_status"] = {
                    "sbu_priority": bool(int(status[0])) if len(status) > 0 else False,
                    "config_changed": bool(int(status[1])) if len(status) > 1 else False,
                    "scc_firmware_updated": bool(int(status[2])) if len(status) > 2 else False,
                    "load_on": bool(int(status[3])) if len(status) > 3 else False,
                    "battery_voltage_steady": bool(int(status[4])) if len(status) > 4 else False,
                    "charging_on": bool(int(status[5])) if len(status) > 5 else False,
                    "scc_charging_on": bool(int(status[6])) if len(status) > 6 else False,
                    "ac_charging_on": bool(int(status[7])) if len(status) > 7 else False,
                }
            
            # Champs calculés
            data["pv_input_power_w"] = round(data["pv_input_voltage"] * data["pv_input_current_a"], 1)
            data["battery_power_w"] = round(data["battery_voltage"] * data["battery_discharge_current_a"], 1)
            
            return data
        except Exception as e:
            log(f"[PARSER] Erreur QPIGS: {e}")
            return {"raw": resp.decode(errors="ignore"), "error": str(e)}
    
    @staticmethod
    def parse_qpiri(resp: bytes) -> Dict[str, Any]:
        """Parse QPIRI - Rating Information"""
        try:
            txt = resp.strip().decode(errors="ignore").split('\r')[0]
            if txt.startswith("("):
                txt = txt[1:]
            
            fields = txt.split()
            if len(fields) < 21:
                return {"raw": txt, "error": "incomplete_qpiri"}
            
            data = {
                "raw": txt,
                "grid_rating_voltage": VoltronicParser.safe_float(fields[0]),
                "grid_rating_current": VoltronicParser.safe_float(fields[1]),
                "ac_output_rating_voltage": VoltronicParser.safe_float(fields[2]),
                "ac_output_rating_freq": VoltronicParser.safe_float(fields[3]),
                "ac_output_rating_current": VoltronicParser.safe_float(fields[4]),
                "ac_output_rating_apparent_power": VoltronicParser.safe_int(fields[5]),
                "ac_output_rating_active_power": VoltronicParser.safe_int(fields[6]),
                "battery_rating_voltage": VoltronicParser.safe_float(fields[7]),
                "battery_recharge_voltage": VoltronicParser.safe_float(fields[8]),
                "battery_under_voltage": VoltronicParser.safe_float(fields[9]),
                "battery_bulk_voltage": VoltronicParser.safe_float(fields[10]),
                "battery_float_voltage": VoltronicParser.safe_float(fields[11]),
                "battery_type": VoltronicParser.safe_int(fields[12]),
                "max_ac_charging_current": VoltronicParser.safe_int(fields[13]),
                "max_charging_current": VoltronicParser.safe_int(fields[14]),
                "input_voltage_range": VoltronicParser.safe_int(fields[15]),
                "output_source_priority": VoltronicParser.safe_int(fields[16]),
                "charger_source_priority": VoltronicParser.safe_int(fields[17]),
                "parallel_max_num": VoltronicParser.safe_int(fields[18]),
                "machine_type": fields[19] if len(fields) > 19 else "",
                "topology": VoltronicParser.safe_int(fields[20]) if len(fields) > 20 else 0,
            }
            
            # Décodage types
            battery_types = {0: "AGM", 1: "Flooded", 2: "User"}
            data["battery_type_decoded"] = battery_types.get(data["battery_type"], "Unknown")
            
            return data
        except Exception as e:
            log(f"[PARSER] Erreur QPIRI: {e}")
            return {"raw": resp.decode(errors="ignore"), "error": str(e)}
    
    @staticmethod
    def parse_qpiws(resp: bytes) -> Dict[str, Any]:
        """Parse QPIWS - Warning Status"""
        try:
            txt = resp.strip().decode(errors="ignore").split('\r')[0]
            if txt.startswith("("):
                txt = txt[1:]
            
            # Format: 32 caractères binaires
            if len(txt) < 32:
                return {"raw": txt, "error": "incomplete_qpiws"}
            
            warnings = {
                "inverter_fault": bool(int(txt[1])),
                "bus_over_fault": bool(int(txt[2])),
                "bus_under_fault": bool(int(txt[3])),
                "bus_soft_fail_fault": bool(int(txt[4])),
                "line_fail_warning": bool(int(txt[5])),
                "opv_short_warning": bool(int(txt[6])),
                "inverter_voltage_too_low_fault": bool(int(txt[7])),
                "inverter_voltage_too_high_fault": bool(int(txt[8])),
                "over_temperature_fault": bool(int(txt[9])),
                "fan_locked_fault": bool(int(txt[10])),
                "battery_voltage_too_high_fault": bool(int(txt[11])),
                "battery_low_alarm_warning": bool(int(txt[12])),
                "battery_under_shutdown_warning": bool(int(txt[14])),
                "overload_fault": bool(int(txt[16])),
                "eeprom_fault_warning": bool(int(txt[17])),
                "inverter_over_current_fault": bool(int(txt[18])),
                "inverter_soft_fail_fault": bool(int(txt[19])),
                "self_test_fail_fault": bool(int(txt[20])),
                "op_dc_voltage_over_fault": bool(int(txt[21])),
                "bat_open_fault": bool(int(txt[22])),
                "current_sensor_fail_fault": bool(int(txt[23])),
                "battery_short_fault": bool(int(txt[24])),
                "power_limit_warning": bool(int(txt[25])),
                "pv_voltage_high_warning": bool(int(txt[26])),
                "mppt_overload_fault": bool(int(txt[27])),
                "mppt_overload_warning": bool(int(txt[28])),
                "battery_too_low_to_charge_warning": bool(int(txt[29])),
            }
            
            warnings["raw"] = txt
            warnings["any_fault"] = any([v for k, v in warnings.items() if "fault" in k and isinstance(v, bool)])
            warnings["any_warning"] = any([v for k, v in warnings.items() if "warning" in k and isinstance(v, bool)])
            
            return warnings
        except Exception as e:
            log(f"[PARSER] Erreur QPIWS: {e}")
            return {"raw": resp.decode(errors="ignore"), "error": str(e)}
    
    @staticmethod
    def parse_qmod(resp: bytes) -> Dict[str, Any]:
        """Parse QMOD - Mode actuel"""
        try:
            txt = resp.strip().decode(errors="ignore").split('\r')[0]
            if txt.startswith("("):
                txt = txt[1:]
            
            modes = {
                "P": "PowerOn",
                "S": "Standby",
                "L": "Line",
                "B": "Battery",
                "F": "Fault",
                "H": "PowerSaving",
            }
            
            return {
                "raw": txt,
                "mode_code": txt,
                "mode": modes.get(txt, "Unknown")
            }
        except Exception as e:
            return {"raw": resp.decode(errors="ignore"), "error": str(e)}

class MQTTPublisher:
    def __init__(self, host: str, port: int, user: str, password: str, 
                 topic_prefix: str, debug: bool = False):
        self.topic_prefix = topic_prefix
        self.debug = debug
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, 
                                  client_id="wks-monitor-v2", 
                                  clean_session=True)
        if user:
            self.client.username_pw_set(user, password)
        self.client.connect(host, port, keepalive=30)
        self.client.loop_start()
    
    def publish(self, subtopic: str, data: dict):
        topic = f"{self.topic_prefix}/{subtopic}"
        self.client.publish(topic, json.dumps(data), qos=0, retain=True)
        if self.debug:
            log(f"[MQTT] Published to {topic}")

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
    
    # Nouvelles options v2
    enable_qpigs = bool(opt.get("enable_qpigs", True))
    enable_qpiri = bool(opt.get("enable_qpiri", True))
    enable_qpiws = bool(opt.get("enable_qpiws", True))
    enable_qmod = bool(opt.get("enable_qmod", False))

    mqtt_host = opt.get("mqtt_host", "core-mosquitto.local.hass.io")
    mqtt_port = int(opt.get("mqtt_port", 1883))
    mqtt_user = opt.get("mqtt_user", "")
    mqtt_pass = opt.get("mqtt_password", "")
    topic_prefix = opt.get("mqtt_topic_prefix", "wks")

    log(f"[BOOT] 🚀 WKS Monitor v3.0.0 - Polling {poll_interval}s")
    log(f"[BOOT] Port: {port} @ {baudrate} | Onduleurs: {inverter_count}")
    log(f"[BOOT] Commandes: QPGS + {'QPIGS ' if enable_qpigs else ''}{'QPIRI ' if enable_qpiri else ''}{'QPIWS ' if enable_qpiws else ''}")

    sr = SerialReader(port, baudrate, read_timeout, open_retry_sec, debug)
    sr.open()

    try:
        mqtt_pub = MQTTPublisher(mqtt_host, mqtt_port, mqtt_user, mqtt_pass, topic_prefix, debug)
        log("[MQTT] ✅ Connecté")
    except Exception as e:
        log(f"[MQTT] ❌ Échec: {e}")
        sys.exit(1)

    parser = VoltronicParser()
    consecutive_fail = 0
    qpiri_cached = {}  # Cache QPIRI (change rarement)

    while True:
        any_ok = False
        
        for idx in range(inverter_count):
            # QPGS - Status parallèle
            resp = sr.query(f"QPGS{idx}")
            if resp and len(resp) > 10:
                data = parser.parse_qpgs(resp)
                if "error" not in data:
                    mqtt_pub.publish(f"{idx}/status", data)
                    any_ok = True
                    if debug:
                        log(f"[OK] QPGS{idx}: {data.get('work_mode_decoded')} | {data.get('output_active_power_w')}W | Batt:{data.get('battery_voltage')}V({data.get('battery_capacity_pct')}%)")
                else:
                    consecutive_fail += 1
            else:
                consecutive_fail += 1
            
            time.sleep(0.05)
            
            # QPIGS - Status général (une fois par onduleur)
            if enable_qpigs:
                resp = sr.query("QPIGS")
                if resp and len(resp) > 10:
                    data = parser.parse_qpigs(resp)
                    if "error" not in data:
                        mqtt_pub.publish(f"{idx}/general", data)
                    time.sleep(0.05)
            
            # QPIWS - Warnings
            if enable_qpiws:
                resp = sr.query("QPIWS")
                if resp and len(resp) > 10:
                    data = parser.parse_qpiws(resp)
                    if "error" not in data:
                        mqtt_pub.publish(f"{idx}/warnings", data)
                        if data.get("any_fault") or data.get("any_warning"):
                            log(f"[ALERT] QPIWS{idx}: Fault={data.get('any_fault')} Warning={data.get('any_warning')}")
                    time.sleep(0.05)
            
            # QMOD - Mode actuel
            if enable_qmod:
                resp = sr.query("QMOD")
                if resp and len(resp) > 1:
                    data = parser.parse_qmod(resp)
                    if "error" not in data:
                        mqtt_pub.publish(f"{idx}/mode", data)
                    time.sleep(0.05)
        
        # QPIRI - Rating info (une fois toutes les 10 itérations)
        if enable_qpiri and not qpiri_cached:
            resp = sr.query("QPIRI")
            if resp and len(resp) > 10:
                data = parser.parse_qpiri(resp)
                if "error" not in data:
                    qpiri_cached = data
                    mqtt_pub.publish("rating", data)
                    log(f"[INFO] QPIRI cached: {data.get('ac_output_rating_active_power')}W rating")

        # Gestion échecs
        if any_ok:
            consecutive_fail = 0
        elif consecutive_fail >= max_consecutive_fail:
            log("[HEAL] Trop d'échecs - Réouverture port")
            sr.close()
            time.sleep(1.0)
            sr.open()
            consecutive_fail = 0

        time.sleep(poll_interval if any_ok else 3.0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("🛑 Arrêt")
        sys.exit(0)
    except Exception as e:
        log(f"❌ Crash: {e}")
        sys.exit(1)
