#!/usr/bin/env python3
"""
WKS Monitor v4.0.0 - Complete Edition
Couvre 100% des 232 capteurs YAML Home Assistant
Ajouts v4: EnergyTracker, StatisticsTracker, InfoTracker
"""

import json
import sys
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from collections import deque

import paho.mqtt.client as mqtt
import serial

OPTIONS_PATH = Path("/data/options.json")
PERSISTENT_DATA_PATH = Path("/data/wks_persistent.json")

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
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

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
                cmd_bytes = cmd.encode()
                if cmd in CRC_TABLE:
                    hi, lo = CRC_TABLE[cmd]
                    full_cmd = cmd_bytes + bytes([hi, lo]) + b"\r"
                else:
                    crc = calculate_crc(cmd_bytes)
                    full_cmd = cmd_bytes + crc + b"\r"
                
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                self.ser.write(full_cmd)
                self.ser.flush()
                time.sleep(0.15)
                
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
        """Parse QPIGS - General Status"""
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
                "fan_locked_warning": bool(int(txt[10])),
                "battery_voltage_high_warning": bool(int(txt[11])),
                "battery_low_alarm_warning": bool(int(txt[12])),
                "battery_under_shutdown_warning": bool(int(txt[14])),
                "overload_fault": bool(int(txt[16])),
                "eeprom_fault": bool(int(txt[17])),
                "inverter_over_current_fault": bool(int(txt[18])),
                "inverter_soft_fail_fault": bool(int(txt[19])),
                "self_test_fail_warning": bool(int(txt[20])),
                "op_dc_voltage_over_warning": bool(int(txt[21])),
                "battery_open_warning": bool(int(txt[22])),
                "current_sensor_fail_warning": bool(int(txt[23])),
                "bat_short_warning": bool(int(txt[24])),
                "power_limit_warning": bool(int(txt[25])),
                "pv_voltage_high_warning": bool(int(txt[26])),
                "mppt_overload_fault": bool(int(txt[27])),
                "mppt_overload_warning": bool(int(txt[28])),
                "battery_too_low_to_charge_warning": bool(int(txt[29])),
                "overload_warning": bool(int(txt[16])),  # Alias
                "over_temperature_warning": bool(int(txt[9])),  # Alias
                "battery_sensor_alarm_warning": bool(int(txt[23])),  # Alias
                "pv_input_short_warning": bool(int(txt[6])),  # Alias
                "parallel_loss_warning": False,  # Pas dans protocole standard
                "parallel_invalid_sync_warning": False,
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


class EnergyTracker:
    """Module de suivi énergétique avec intégration Riemann"""
    def __init__(self, inverter_count: int):
        self.inverter_count = inverter_count
        self.data = {}
        self.last_update = {}
        self.boot_time = datetime.now()
        
        for idx in range(inverter_count):
            self.data[idx] = {
                "energy_produced_kwh": 0.0,
                "energy_consumed_kwh": 0.0,
                "pv_energy_kwh": 0.0,
                "battery_charge_kwh": 0.0,
                "battery_discharge_kwh": 0.0,
                "daily_energy_kwh": 0.0,
                "daily_pv_kwh": 0.0,
                "_last_pv_power": 0.0,
                "_last_load_power": 0.0,
                "_last_battery_power": 0.0,
            }
            self.last_update[idx] = datetime.now()
        
        self._load_persistent()
    
    def update(self, idx: int, qpgs_data: dict, qpigs_data: dict = None):
        """Mise à jour avec intégration Riemann"""
        now = datetime.now()
        dt = (now - self.last_update[idx]).total_seconds() / 3600.0
        
        if dt > 0.1:  # Ignore si >6 min
            self.last_update[idx] = now
            return
        
        d = self.data[idx]
        
        pv_power = qpgs_data.get("pv_input_power_w", 0.0)
        load_power = qpgs_data.get("output_active_power_w", 0.0)
        batt_charge = qpgs_data.get("battery_charge_current_a", 0)
        batt_voltage = qpgs_data.get("battery_voltage", 48.0)
        battery_power = batt_charge * batt_voltage
        
        # Intégration trapézoïdale
        if d["_last_pv_power"] > 0 or pv_power > 0:
            energy_kwh = ((d["_last_pv_power"] + pv_power) / 2) * dt / 1000.0
            d["pv_energy_kwh"] += energy_kwh
            d["daily_pv_kwh"] += energy_kwh
        
        if d["_last_load_power"] > 0 or load_power > 0:
            energy_kwh = ((d["_last_load_power"] + load_power) / 2) * dt / 1000.0
            d["energy_consumed_kwh"] += energy_kwh
            d["daily_energy_kwh"] += energy_kwh
        
        if battery_power > 0:
            energy_kwh = ((max(0, d["_last_battery_power"]) + battery_power) / 2) * dt / 1000.0
            d["battery_charge_kwh"] += energy_kwh
        elif battery_power < 0:
            energy_kwh = ((min(0, d["_last_battery_power"]) + battery_power) / 2) * dt / 1000.0
            d["battery_discharge_kwh"] += abs(energy_kwh)
        
        d["energy_produced_kwh"] = d["pv_energy_kwh"]
        
        d["_last_pv_power"] = pv_power
        d["_last_load_power"] = load_power
        d["_last_battery_power"] = battery_power
        self.last_update[idx] = now
    
    def get_data(self, idx: int) -> dict:
        d = self.data[idx]
        return {
            "energy_produced_kwh": round(d["energy_produced_kwh"], 3),
            "energy_consumed_kwh": round(d["energy_consumed_kwh"], 3),
            "pv_energy_kwh": round(d["pv_energy_kwh"], 3),
            "battery_charge_kwh": round(d["battery_charge_kwh"], 3),
            "battery_discharge_kwh": round(d["battery_discharge_kwh"], 3),
            "daily_energy_kwh": round(d["daily_energy_kwh"], 3),
            "daily_pv_kwh": round(d["daily_pv_kwh"], 3),
            "last_update": self.last_update[idx].isoformat(),
        }
    
    def reset_daily(self):
        for idx in range(self.inverter_count):
            self.data[idx]["daily_energy_kwh"] = 0.0
            self.data[idx]["daily_pv_kwh"] = 0.0
        log("[ENERGY] ✅ Reset journalier effectué")
        self._save_persistent()
    
    def _save_persistent(self):
        try:
            save_data = {"version": 1, "boot_time": self.boot_time.isoformat(), "inverters": {}}
            for idx in range(self.inverter_count):
                save_data["inverters"][str(idx)] = {
                    "energy_produced_kwh": self.data[idx]["energy_produced_kwh"],
                    "energy_consumed_kwh": self.data[idx]["energy_consumed_kwh"],
                    "pv_energy_kwh": self.data[idx]["pv_energy_kwh"],
                    "battery_charge_kwh": self.data[idx]["battery_charge_kwh"],
                    "battery_discharge_kwh": self.data[idx]["battery_discharge_kwh"],
                }
            with open(PERSISTENT_DATA_PATH, "w") as f:
                json.dump(save_data, f, indent=2)
        except Exception as e:
            log(f"[ENERGY] ⚠️ Erreur sauvegarde: {e}")
    
    def _load_persistent(self):
        try:
            if PERSISTENT_DATA_PATH.exists():
                with open(PERSISTENT_DATA_PATH, "r") as f:
                    save_data = json.load(f)
                if save_data.get("version") == 1:
                    for idx_str, inv_data in save_data.get("inverters", {}).items():
                        idx = int(idx_str)
                        if idx < self.inverter_count:
                            self.data[idx].update(inv_data)
                    log(f"[ENERGY] ✅ Données restaurées")
        except Exception as e:
            log(f"[ENERGY] ⚠️ Erreur chargement: {e}")


class StatisticsTracker:
    """Module de statistiques (min/max/pics)"""
    def __init__(self, inverter_count: int, history_size: int = 1000):
        self.inverter_count = inverter_count
        self.data = {}
        
        for idx in range(inverter_count):
            self.data[idx] = {
                "pv_power_history": deque(maxlen=history_size),
                "load_power_history": deque(maxlen=history_size),
                "peak_power_today": 0,
                "peak_pv_today": 0,
                "runtime_hours_today": 0.0,
                "warnings_count_today": 0,
                "last_warning_type": "Aucune",
                "last_warning_timestamp": datetime.now().isoformat(),
                "min_load_pct_today": 100,
                "max_load_pct_today": 0,
                "_start_time": datetime.now(),
            }
    
    def update(self, idx: int, qpgs_data: dict, qpiws_data: dict = None):
        d = self.data[idx]
        
        pv_power = qpgs_data.get("pv_input_power_w", 0)
        load_power = qpgs_data.get("output_active_power_w", 0)
        load_pct = qpgs_data.get("output_load_pct", 0)
        
        d["pv_power_history"].append(pv_power)
        d["load_power_history"].append(load_power)
        
        d["peak_power_today"] = max(d["peak_power_today"], load_power)
        d["peak_pv_today"] = max(d["peak_pv_today"], pv_power)
        d["min_load_pct_today"] = min(d["min_load_pct_today"], load_pct)
        d["max_load_pct_today"] = max(d["max_load_pct_today"], load_pct)
        
        d["runtime_hours_today"] = (datetime.now() - d["_start_time"]).total_seconds() / 3600
        
        if qpiws_data:
            if qpiws_data.get("any_warning") or qpiws_data.get("any_fault"):
                d["warnings_count_today"] += 1
                d["last_warning_timestamp"] = datetime.now().isoformat()
                # Trouver le premier warning actif
                for key, val in qpiws_data.items():
                    if isinstance(val, bool) and val and ("warning" in key or "fault" in key):
                        d["last_warning_type"] = key.replace("_", " ").title()
                        break
    
    def get_data(self, idx: int) -> dict:
        d = self.data[idx]
        return {
            "peak_power_today": d["peak_power_today"],
            "peak_pv_today": d["peak_pv_today"],
            "runtime_hours_today": round(d["runtime_hours_today"], 1),
            "warnings_count_today": d["warnings_count_today"],
            "last_warning_type": d["last_warning_type"],
            "last_warning_timestamp": d["last_warning_timestamp"],
            "min_load_pct_today": d["min_load_pct_today"],
            "max_load_pct_today": d["max_load_pct_today"],
        }
    
    def reset_daily(self):
        for idx in range(self.inverter_count):
            d = self.data[idx]
            d["peak_power_today"] = 0
            d["peak_pv_today"] = 0
            d["warnings_count_today"] = 0
            d["min_load_pct_today"] = 100
            d["max_load_pct_today"] = 0
            d["_start_time"] = datetime.now()
        log("[STATS] ✅ Reset journalier effectué")


class InfoTracker:
    """Module d'informations système/diagnostic"""
    def __init__(self, inverter_count: int):
        self.inverter_count = inverter_count
        self.boot_time = datetime.now()
        self.data = {}
        
        for idx in range(inverter_count):
            self.data[idx] = {
                "serial_number": "",
                "firmware_version": "",
                "uptime_days": 0,
                "uptime_hours": 0,
                "communication_errors": 0,
                "last_successful_poll": None,
                "poll_success_rate_pct": 100.0,
                "mqtt_signal_quality": 100,
                "last_restart_timestamp": self.boot_time.isoformat(),
                "_poll_attempts": 0,
                "_poll_success": 0,
            }
    
    def update(self, idx: int, qpgs_data: dict, success: bool = True):
        d = self.data[idx]
        d["_poll_attempts"] += 1
        
        if success:
            d["_poll_success"] += 1
            d["last_successful_poll"] = datetime.now().isoformat()
            d["serial_number"] = qpgs_data.get("serial_number", "")
            d["firmware_version"] = str(qpgs_data.get("eeprom_version", "Unknown"))
        else:
            d["communication_errors"] += 1
        
        if d["_poll_attempts"] > 0:
            d["poll_success_rate_pct"] = round((d["_poll_success"] / d["_poll_attempts"]) * 100, 1)
            d["mqtt_signal_quality"] = int(d["poll_success_rate_pct"])
        
        uptime_seconds = (datetime.now() - self.boot_time).total_seconds()
        d["uptime_days"] = round(uptime_seconds / 86400, 1)
        d["uptime_hours"] = round(uptime_seconds / 3600, 1)
    
    def get_data(self, idx: int) -> dict:
        return {k: v for k, v in self.data[idx].items() if not k.startswith("_")}


class MQTTPublisher:
    def __init__(self, host: str, port: int, user: str, password: str, 
                 topic_prefix: str, debug: bool = False):
        self.topic_prefix = topic_prefix
        self.debug = debug
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, 
                                  client_id="wks-monitor-v4", 
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
    
    enable_qpigs = bool(opt.get("enable_qpigs", True))
    enable_qpiri = bool(opt.get("enable_qpiri", True))
    enable_qpiws = bool(opt.get("enable_qpiws", True))
    enable_qmod = bool(opt.get("enable_qmod", False))
    
    enable_energy = bool(opt.get("enable_energy_tracking", True))
    enable_statistics = bool(opt.get("enable_statistics", True))
    enable_info = bool(opt.get("enable_info", True))

    mqtt_host = opt.get("mqtt_host", "core-mosquitto.local.hass.io")
    mqtt_port = int(opt.get("mqtt_port", 1883))
    mqtt_user = opt.get("mqtt_user", "")
    mqtt_pass = opt.get("mqtt_password", "")
    topic_prefix = opt.get("mqtt_topic_prefix", "wks")

    log(f"[BOOT] 🚀 WKS Monitor v4.0.0 - Polling {poll_interval}s")
    log(f"[BOOT] Port: {port} @ {baudrate} | Onduleurs: {inverter_count}")
    log(f"[BOOT] Modules v4: Energy={enable_energy} Stats={enable_statistics} Info={enable_info}")

    sr = SerialReader(port, baudrate, read_timeout, open_retry_sec, debug)
    sr.open()

    try:
        mqtt_pub = MQTTPublisher(mqtt_host, mqtt_port, mqtt_user, mqtt_pass, topic_prefix, debug)
        log("[MQTT] ✅ Connecté")
    except Exception as e:
        log(f"[MQTT] ❌ Échec: {e}")
        sys.exit(1)

    parser = VoltronicParser()
    
    energy_tracker = EnergyTracker(inverter_count) if enable_energy else None
    stats_tracker = StatisticsTracker(inverter_count) if enable_statistics else None
    info_tracker = InfoTracker(inverter_count) if enable_info else None
    
    consecutive_fail = 0
    qpiri_cached = {}
    iteration_count = 0
    last_midnight = datetime.now().date()

    while True:
        any_ok = False
        iteration_count += 1
        
        # Reset journalier
        current_date = datetime.now().date()
        if current_date > last_midnight:
            log("[DAILY] 🌅 Nouveau jour - Reset compteurs")
            if energy_tracker:
                energy_tracker.reset_daily()
            if stats_tracker:
                stats_tracker.reset_daily()
            last_midnight = current_date
        
        for idx in range(inverter_count):
            qpgs_data = {}
            qpigs_data = {}
            qpiws_data = {}
            
            # QPGS
            resp = sr.query(f"QPGS{idx}")
            if resp and len(resp) > 10:
                qpgs_data = parser.parse_qpgs(resp)
                if "error" not in qpgs_data:
                    mqtt_pub.publish(f"{idx}/status", qpgs_data)
                    any_ok = True
                    if debug:
                        log(f"[OK] QPGS{idx}: {qpgs_data.get('work_mode_decoded')} | "
                            f"{qpgs_data.get('output_active_power_w')}W")
                else:
                    consecutive_fail += 1
            else:
                consecutive_fail += 1
            
            time.sleep(0.05)
            
            # QPIGS
            if enable_qpigs:
                resp = sr.query("QPIGS")
                if resp and len(resp) > 10:
                    qpigs_data = parser.parse_qpigs(resp)
                    if "error" not in qpigs_data:
                        mqtt_pub.publish(f"{idx}/general", qpigs_data)
                    time.sleep(0.05)
            
            # QPIWS
            if enable_qpiws:
                resp = sr.query("QPIWS")
                if resp and len(resp) > 10:
                    qpiws_data = parser.parse_qpiws(resp)
                    if "error" not in qpiws_data:
                        mqtt_pub.publish(f"{idx}/warnings", qpiws_data)
                    time.sleep(0.05)
            
            # QMOD
            if enable_qmod:
                resp = sr.query("QMOD")
                if resp and len(resp) > 1:
                    data = parser.parse_qmod(resp)
                    if "error" not in data:
                        mqtt_pub.publish(f"{idx}/mode", data)
                    time.sleep(0.05)
            
            # === MODULES V4 ===
            
            if energy_tracker and qpgs_data and "error" not in qpgs_data:
                energy_tracker.update(idx, qpgs_data, qpigs_data)
                mqtt_pub.publish(f"{idx}/energy", energy_tracker.get_data(idx))
            
            if stats_tracker and qpgs_data and "error" not in qpgs_data:
                stats_tracker.update(idx, qpgs_data, qpiws_data)
                mqtt_pub.publish(f"{idx}/statistics", stats_tracker.get_data(idx))
            
            if info_tracker and qpgs_data:
                info_tracker.update(idx, qpgs_data, success=("error" not in qpgs_data))
                mqtt_pub.publish(f"{idx}/info", info_tracker.get_data(idx))
        
        # QPIRI
        if enable_qpiri and (not qpiri_cached or iteration_count % 10 == 0):
            resp = sr.query("QPIRI")
            if resp and len(resp) > 10:
                data = parser.parse_qpiri(resp)
                if "error" not in data:
                    qpiri_cached = data
                    mqtt_pub.publish("rating", data)

        # Sauvegarde
        if energy_tracker and iteration_count % 60 == 0:
            energy_tracker._save_persistent()

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
        import traceback
        traceback.print_exc()
        sys.exit(1)
