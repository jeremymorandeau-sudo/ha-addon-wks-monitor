#!/usr/bin/env python3
"""
WKS Monitor v4.3.0 - Version stable avec CRC originaux
- CRC originaux qui fonctionnent pour QPGS, QPIGS, QPIRI
- Option enable_firmware_query désactivable
- Correction parsing battery_discharge_current
- Note: QVFW/QVFW2/QGMN/QPI/QPIWS/QMOD non supportés par certains onduleurs WKS
"""

import json
import sys
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from collections import deque

import paho.mqtt.client as mqtt
import serial

OPTIONS_PATH = Path("/data/options.json")
PERSISTENT_DATA_PATH = Path("/data/wks_persistent.json")

# CRC originaux qui fonctionnent
CRC_TABLE = {
    "QPGS0": (0x3F, 0xDA),
    "QPGS1": (0x2F, 0xFB),
    "QPGS2": (0x1F, 0x98),
    "QPIGS": (0xB7, 0xA9),
    "QPIRI": (0xF8, 0x54),
    "QPIWS": (0xB4, 0xDA),
    "QMOD": (0x49, 0xC1),
    "QPI": (0xBE, 0xAC),
    "QVFW": (0x62, 0x99),
    "QVFW2": (0xC3, 0xF5),
    "QGMN": (0x49, 0x28),
}

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def load_options() -> dict:
    with open(OPTIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def calculate_crc(cmd: bytes) -> bytes:
    """CRC XMODEM"""
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
                    self.port, baudrate=self.baudrate, bytesize=8,
                    parity=serial.PARITY_NONE, stopbits=1,
                    timeout=self.timeout, write_timeout=self.timeout, exclusive=True
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
                except:
                    pass
                self.ser = None

    def query(self, cmd: str, extra_wait: float = 0.0) -> Optional[bytes]:
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
                time.sleep(0.15 + extra_wait)
                
                return self.ser.read_until(b"\r") or None
            except Exception as e:
                log(f"[SERIAL] Erreur: {e}")
                return None

class VoltronicParser:
    @staticmethod
    def safe_int(val: str) -> int:
        try:
            cleaned = ''.join(c for c in val if c.isdigit())
            return int(cleaned) if cleaned else 0
        except:
            return 0
    
    @staticmethod
    def safe_float(val: str) -> float:
        try:
            cleaned = ''.join(c for c in val if c.isdigit() or c == '.')
            return float(cleaned) if cleaned else 0.0
        except:
            return 0.0
    
    @staticmethod
    def parse_qpgs(resp: bytes) -> Dict[str, Any]:
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
                "grid_voltage": VoltronicParser.safe_float(fields[4]),
                "grid_freq": VoltronicParser.safe_float(fields[5]),
                "ac_output_voltage": VoltronicParser.safe_float(fields[6]),
                "ac_output_freq": VoltronicParser.safe_float(fields[7]),
                "output_apparent_power_va": VoltronicParser.safe_int(fields[8]),
                "output_active_power_w": VoltronicParser.safe_int(fields[9]),
                "output_load_pct": VoltronicParser.safe_int(fields[10]),
                "battery_voltage": VoltronicParser.safe_float(fields[11]),
                "battery_charge_current_a": VoltronicParser.safe_int(fields[12]),
                "battery_capacity_pct": VoltronicParser.safe_int(fields[13]),
                "pv_input_voltage": VoltronicParser.safe_float(fields[14]),
                "total_charge_current_a": VoltronicParser.safe_int(fields[15]),
                "total_apparent_power_va": VoltronicParser.safe_int(fields[16]),
                "total_active_power_w": VoltronicParser.safe_int(fields[17]),
                "total_load_pct": VoltronicParser.safe_int(fields[18]),
                "status_flags_raw": fields[19] if len(fields) > 19 else "00000000",
            }
            
            if len(fields) > 20:
                data["output_mode"] = VoltronicParser.safe_int(fields[20])
            if len(fields) > 21:
                data["charger_source_priority"] = VoltronicParser.safe_int(fields[21])
            if len(fields) > 22:
                data["max_charger_current"] = VoltronicParser.safe_int(fields[22])
            if len(fields) > 23:
                data["max_charger_range"] = VoltronicParser.safe_int(fields[23])
            if len(fields) > 24:
                data["max_ac_charger_current"] = VoltronicParser.safe_int(fields[24])
            if len(fields) > 25:
                data["pv_input_current_a"] = VoltronicParser.safe_int(fields[25])
            if len(fields) > 26:
                # Correction: nettoyer le dernier champ (peut contenir CRC)
                last_field = fields[26]
                cleaned = ''.join(c for c in last_field[:3] if c.isdigit())
                data["battery_discharge_current_a"] = int(cleaned) if cleaned else 0
            
            flags = data["status_flags_raw"]
            if len(flags) >= 8:
                data["status_flags"] = {
                    "scc_ok": flags[0] == '1',
                    "ac_charging": flags[1] == '1',
                    "scc_charging": flags[2] == '1',
                    "battery_open": int(flags[3:5], 2) == 2 if len(flags) >= 5 else False,
                    "battery_under": int(flags[3:5], 2) == 1 if len(flags) >= 5 else False,
                    "battery_normal": int(flags[3:5], 2) == 0 if len(flags) >= 5 else True,
                    "line_loss": flags[5] == '1',
                    "load_on": flags[6] == '1',
                    "config_changed": flags[7] == '1',
                }
            
            if "pv_input_current_a" in data:
                data["pv_input_power_w"] = round(data["pv_input_voltage"] * data["pv_input_current_a"], 1)
            else:
                data["pv_input_power_w"] = 0.0
            
            if "battery_discharge_current_a" in data:
                data["battery_power_w"] = round(data["battery_voltage"] * data["battery_discharge_current_a"], 1)
            else:
                data["battery_power_w"] = 0.0
            
            work_modes = {"B": "Battery", "L": "Line", "F": "Fault", "P": "PowerOn", "S": "Standby", "H": "PowerSaving"}
            data["work_mode_decoded"] = work_modes.get(data["work_mode"], "Unknown")
            
            return data
        except Exception as e:
            log(f"[PARSER] Erreur QPGS: {e}")
            return {"raw": resp.decode(errors="ignore"), "error": str(e)}
    
    @staticmethod
    def parse_qpigs(resp: bytes) -> Dict[str, Any]:
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
                    "sbu_priority": status[0] == '1' if len(status) > 0 else False,
                    "config_changed": status[1] == '1' if len(status) > 1 else False,
                    "scc_firmware_updated": status[2] == '1' if len(status) > 2 else False,
                    "load_on": status[3] == '1' if len(status) > 3 else False,
                    "battery_voltage_steady": status[4] == '1' if len(status) > 4 else False,
                    "charging_on": status[5] == '1' if len(status) > 5 else False,
                    "scc_charging_on": status[6] == '1' if len(status) > 6 else False,
                    "ac_charging_on": status[7] == '1' if len(status) > 7 else False,
                }
            
            if len(fields) > 17:
                data["battery_voltage_offset"] = VoltronicParser.safe_int(fields[17])
            if len(fields) > 18:
                data["eeprom_version"] = VoltronicParser.safe_int(fields[18])
            if len(fields) > 19:
                data["pv_charging_power_w"] = VoltronicParser.safe_int(fields[19])
            
            data["pv_input_power_w"] = round(data["pv_input_voltage"] * data["pv_input_current_a"], 1)
            data["battery_power_w"] = round(data["battery_voltage"] * data["battery_discharge_current_a"], 1)
            
            return data
        except Exception as e:
            log(f"[PARSER] Erreur QPIGS: {e}")
            return {"raw": resp.decode(errors="ignore"), "error": str(e)}
    
    @staticmethod
    def parse_qpiri(resp: bytes) -> Dict[str, Any]:
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
            
            if len(fields) > 21:
                data["output_mode"] = VoltronicParser.safe_int(fields[21])
            if len(fields) > 22:
                data["battery_redischarge_voltage"] = VoltronicParser.safe_float(fields[22])
            if len(fields) > 23:
                data["pv_ok_condition"] = VoltronicParser.safe_int(fields[23])
            if len(fields) > 24:
                data["pv_power_balance"] = VoltronicParser.safe_int(fields[24])
            
            battery_types = {0: "AGM", 1: "Flooded", 2: "User"}
            data["battery_type_decoded"] = battery_types.get(data["battery_type"], "Unknown")
            
            output_priorities = {0: "Utility first", 1: "Solar first", 2: "SBU first"}
            data["output_source_priority_decoded"] = output_priorities.get(data["output_source_priority"], "Unknown")
            
            charger_priorities = {0: "Utility first", 1: "Solar first", 2: "Solar + Utility", 3: "Solar only"}
            data["charger_source_priority_decoded"] = charger_priorities.get(data["charger_source_priority"], "Unknown")
            
            return data
        except Exception as e:
            log(f"[PARSER] Erreur QPIRI: {e}")
            return {"raw": resp.decode(errors="ignore"), "error": str(e)}
    
    @staticmethod
    def parse_qpiws(resp: bytes) -> Dict[str, Any]:
        try:
            txt = resp.strip().decode(errors="ignore").split('\r')[0]
            if txt.startswith("("):
                txt = txt[1:]
            
            if len(txt) < 32 or "NAK" in txt:
                return {"raw": txt, "error": f"incomplete_or_nak"}
            
            warnings = {
                "reserved_a0": txt[0] == '1',
                "inverter_fault": txt[1] == '1',
                "bus_over_fault": txt[2] == '1',
                "bus_under_fault": txt[3] == '1',
                "bus_soft_fail_fault": txt[4] == '1',
                "line_fail_warning": txt[5] == '1',
                "opv_short_warning": txt[6] == '1',
                "inverter_voltage_too_low_fault": txt[7] == '1',
                "inverter_voltage_too_high_fault": txt[8] == '1',
                "over_temperature": txt[9] == '1',
                "fan_locked": txt[10] == '1',
                "battery_voltage_high": txt[11] == '1',
                "battery_low_alarm_warning": txt[12] == '1',
                "overcharge_fault": txt[13] == '1',
                "battery_under_shutdown_warning": txt[14] == '1',
                "battery_derating_warning": txt[15] == '1',
                "overload": txt[16] == '1',
                "eeprom_fault_warning": txt[17] == '1',
                "inverter_over_current_fault": txt[18] == '1',
                "inverter_soft_fail_fault": txt[19] == '1',
                "self_test_fail_fault": txt[20] == '1',
                "op_dc_voltage_over_fault": txt[21] == '1',
                "battery_open_fault": txt[22] == '1',
                "current_sensor_fail_fault": txt[23] == '1',
                "battery_short_fault": txt[24] == '1',
                "power_limit_warning": txt[25] == '1',
                "pv_voltage_high_warning": txt[26] == '1',
                "mppt_overload_fault": txt[27] == '1',
                "mppt_overload_warning": txt[28] == '1',
                "battery_too_low_to_charge_warning": txt[29] == '1',
            }
            
            is_fault = warnings["inverter_fault"]
            warnings["over_temperature_fault"] = warnings["over_temperature"] and is_fault
            warnings["over_temperature_warning"] = warnings["over_temperature"] and not is_fault
            warnings["fan_locked_fault"] = warnings["fan_locked"] and is_fault
            warnings["fan_locked_warning"] = warnings["fan_locked"] and not is_fault
            warnings["battery_voltage_high_fault"] = warnings["battery_voltage_high"] and is_fault
            warnings["battery_voltage_high_warning"] = warnings["battery_voltage_high"] and not is_fault
            warnings["overload_fault"] = warnings["overload"] and is_fault
            warnings["overload_warning"] = warnings["overload"] and not is_fault
            
            warnings["eeprom_fault"] = warnings["eeprom_fault_warning"]
            warnings["battery_sensor_alarm_warning"] = warnings["current_sensor_fail_fault"]
            warnings["pv_input_short_warning"] = warnings["opv_short_warning"]
            warnings["bat_short_warning"] = warnings["battery_short_fault"]
            warnings["parallel_loss_warning"] = False
            warnings["parallel_invalid_sync_warning"] = False
            
            warnings["raw"] = txt
            warnings["any_fault"] = any([v for k, v in warnings.items() if "fault" in k and isinstance(v, bool)])
            warnings["any_warning"] = any([v for k, v in warnings.items() if "warning" in k and isinstance(v, bool)])
            
            return warnings
        except Exception as e:
            log(f"[PARSER] Erreur QPIWS: {e}")
            return {"raw": resp.decode(errors="ignore"), "error": str(e)}
    
    @staticmethod
    def parse_qmod(resp: bytes) -> Dict[str, Any]:
        try:
            txt = resp.strip().decode(errors="ignore").split('\r')[0]
            if txt.startswith("("):
                txt = txt[1:]
            
            modes = {"P": "PowerOn", "S": "Standby", "L": "Line", "B": "Battery", "F": "Fault", "H": "PowerSaving"}
            return {"raw": txt, "mode_code": txt, "mode": modes.get(txt, "Unknown")}
        except Exception as e:
            return {"raw": resp.decode(errors="ignore"), "error": str(e)}


class EnergyTracker:
    def __init__(self, inverter_count: int):
        self.inverter_count = inverter_count
        self.data = {}
        self.last_update = {}
        self.boot_time = datetime.now()
        
        for idx in range(inverter_count):
            self.data[idx] = {
                "energy_produced_kwh": 0.0, "energy_consumed_kwh": 0.0,
                "pv_energy_kwh": 0.0, "battery_charge_kwh": 0.0,
                "battery_discharge_kwh": 0.0, "daily_energy_kwh": 0.0,
                "daily_pv_kwh": 0.0, "_last_pv_power": 0.0,
                "_last_load_power": 0.0, "_last_battery_power": 0.0,
            }
            self.last_update[idx] = datetime.now()
        self._load_persistent()
    
    def update(self, idx: int, qpgs_data: dict, qpigs_data: dict = None):
        now = datetime.now()
        dt = (now - self.last_update[idx]).total_seconds() / 3600.0
        if dt > 0.1:
            self.last_update[idx] = now
            return
        
        d = self.data[idx]
        pv_power = qpgs_data.get("pv_input_power_w", 0.0)
        load_power = qpgs_data.get("output_active_power_w", 0.0)
        batt_charge = qpgs_data.get("battery_charge_current_a", 0)
        batt_voltage = qpgs_data.get("battery_voltage", 48.0)
        battery_power = batt_charge * batt_voltage
        
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
    def __init__(self, inverter_count: int, history_size: int = 1000):
        self.inverter_count = inverter_count
        self.data = {}
        for idx in range(inverter_count):
            self.data[idx] = {
                "pv_power_history": deque(maxlen=history_size),
                "load_power_history": deque(maxlen=history_size),
                "peak_power_today": 0, "peak_pv_today": 0,
                "runtime_hours_today": 0.0, "warnings_count_today": 0,
                "last_warning_type": "Aucune",
                "last_warning_timestamp": datetime.now().isoformat(),
                "min_load_pct_today": 100, "max_load_pct_today": 0,
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
        
        if qpiws_data and (qpiws_data.get("any_warning") or qpiws_data.get("any_fault")):
            d["warnings_count_today"] += 1
            d["last_warning_timestamp"] = datetime.now().isoformat()
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
    def __init__(self, inverter_count: int):
        self.inverter_count = inverter_count
        self.boot_time = datetime.now()
        self.data = {}
        for idx in range(inverter_count):
            self.data[idx] = {
                "serial_number": "", "firmware_version": "",
                "firmware_version_scc": "", "model_number": "",
                "uptime_days": 0, "uptime_hours": 0,
                "communication_errors": 0, "last_successful_poll": None,
                "poll_success_rate_pct": 100.0, "mqtt_signal_quality": 100,
                "last_restart_timestamp": self.boot_time.isoformat(),
                "_poll_attempts": 0, "_poll_success": 0,
            }
    
    def set_firmware_info(self, idx: int, fw_main: str = "", fw_scc: str = "", model: str = ""):
        if fw_main:
            self.data[idx]["firmware_version"] = fw_main
        if fw_scc:
            self.data[idx]["firmware_version_scc"] = fw_scc
        if model:
            self.data[idx]["model_number"] = model
    
    def update(self, idx: int, qpgs_data: dict, success: bool = True):
        d = self.data[idx]
        d["_poll_attempts"] += 1
        
        if success:
            d["_poll_success"] += 1
            d["last_successful_poll"] = datetime.now().isoformat()
            d["serial_number"] = qpgs_data.get("serial_number", "")
            if not d["firmware_version"]:
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
                                  client_id="wks-monitor-v4", clean_session=True)
        if user:
            self.client.username_pw_set(user, password)
        self.client.connect(host, port, keepalive=30)
        self.client.loop_start()
    
    def publish(self, subtopic: str, data: dict):
        topic = f"{self.topic_prefix}/{subtopic}"
        self.client.publish(topic, json.dumps(data), qos=0, retain=True)
        if self.debug:
            log(f"[MQTT] Published to {topic}")


def query_firmware_versions(sr: SerialReader, mqtt_pub: MQTTPublisher, info_tracker, inverter_count: int):
    """Interroge les versions firmware au démarrage"""
    log("[FIRMWARE] 📋 Interrogation versions firmware...")
    
    firmware_data = {
        "main_cpu": "", "scc_cpu": "", "model_number": "",
        "protocol_id": "", "query_timestamp": datetime.now().isoformat()
    }
    
    for cmd, key in [("QVFW", "main_cpu"), ("QVFW2", "scc_cpu"), ("QGMN", "model_number"), ("QPI", "protocol_id")]:
        resp = sr.query(cmd)
        if resp:
            txt = resp.decode(errors="ignore").strip()
            if txt.startswith("("):
                txt = txt[1:]
            if "NAK" not in txt:
                firmware_data[key] = txt
                log(f"[FIRMWARE] {cmd}: {txt}")
            else:
                log(f"[FIRMWARE] {cmd}: NAK (commande non supportée)")
        else:
            log(f"[FIRMWARE] {cmd}: Pas de réponse")
        time.sleep(0.3)
    
    mqtt_pub.publish("firmware", firmware_data)
    
    if info_tracker:
        fw_main = firmware_data["main_cpu"].replace("VERFW:", "")
        fw_scc = firmware_data["scc_cpu"].replace("VERFW2:", "")
        model = firmware_data["model_number"]
        for idx in range(inverter_count):
            info_tracker.set_firmware_info(idx, fw_main, fw_scc, model)
    
    log("[FIRMWARE] 📋 Interrogation terminée")
    return firmware_data


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
    enable_qpiws = bool(opt.get("enable_qpiws", False))  # Désactivé par défaut
    enable_qmod = bool(opt.get("enable_qmod", False))    # Désactivé par défaut
    enable_firmware_query = bool(opt.get("enable_firmware_query", False))  # Désactivé par défaut
    
    enable_energy = bool(opt.get("enable_energy_tracking", True))
    enable_statistics = bool(opt.get("enable_statistics", True))
    enable_info = bool(opt.get("enable_info", True))

    mqtt_host = opt.get("mqtt_host", "core-mosquitto.local.hass.io")
    mqtt_port = int(opt.get("mqtt_port", 1883))
    mqtt_user = opt.get("mqtt_user", "")
    mqtt_pass = opt.get("mqtt_password", "")
    topic_prefix = opt.get("mqtt_topic_prefix", "wks")

    log(f"[BOOT] 🚀 WKS Monitor v4.3.0 - Polling {poll_interval}s")
    log(f"[BOOT] Port: {port} @ {baudrate} | Onduleurs: {inverter_count}")
    log(f"[BOOT] Modules v4: Energy={enable_energy} Stats={enable_statistics} Info={enable_info}")
    cmds = "QPGS"
    if enable_qpigs: cmds += " QPIGS"
    if enable_qpiri: cmds += " QPIRI"
    if enable_qpiws: cmds += " QPIWS"
    if enable_qmod: cmds += " QMOD"
    if enable_firmware_query: cmds += " QVFW"
    log(f"[BOOT] Commandes: {cmds}")

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
    
    if enable_firmware_query:
        query_firmware_versions(sr, mqtt_pub, info_tracker, inverter_count)
    
    consecutive_fail = 0
    qpiri_cached = {}
    iteration_count = 0
    last_midnight = datetime.now().date()

    while True:
        any_ok = False
        iteration_count += 1
        
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
            
            # QPGS - Parallel Information (commande principale)
            resp = sr.query(f"QPGS{idx}")
            if resp and len(resp) > 10:
                qpgs_data = parser.parse_qpgs(resp)
                if "error" not in qpgs_data:
                    mqtt_pub.publish(f"{idx}/status", qpgs_data)
                    any_ok = True
                    if debug:
                        log(f"[OK] QPGS{idx}: {qpgs_data.get('work_mode_decoded')} | "
                            f"{qpgs_data.get('output_active_power_w')}W | "
                            f"PV: {qpgs_data.get('pv_input_power_w', 0)}W")
                else:
                    consecutive_fail += 1
            else:
                consecutive_fail += 1
            
            time.sleep(0.05)
            
            # QPIGS - General Status
            if enable_qpigs:
                resp = sr.query("QPIGS")
                if resp and len(resp) > 10:
                    qpigs_data = parser.parse_qpigs(resp)
                    if "error" not in qpigs_data:
                        mqtt_pub.publish(f"{idx}/general", qpigs_data)
                time.sleep(0.05)
            
            # QPIWS - Warnings
            if enable_qpiws:
                resp = sr.query("QPIWS", extra_wait=0.15)
                if resp and len(resp) >= 3:
                    qpiws_data = parser.parse_qpiws(resp)
                    if "error" not in qpiws_data:
                        mqtt_pub.publish(f"{idx}/warnings", qpiws_data)
                time.sleep(0.05)
            
            # QMOD - Mode
            if enable_qmod:
                resp = sr.query("QMOD")
                if resp and len(resp) > 1:
                    data = parser.parse_qmod(resp)
                    if "error" not in data and "NAK" not in data.get("raw", ""):
                        mqtt_pub.publish(f"{idx}/mode", data)
                time.sleep(0.05)
            
            # Modules v4
            if energy_tracker and qpgs_data and "error" not in qpgs_data:
                energy_tracker.update(idx, qpgs_data, qpigs_data)
                mqtt_pub.publish(f"{idx}/energy", energy_tracker.get_data(idx))
            
            if stats_tracker and qpgs_data and "error" not in qpgs_data:
                stats_tracker.update(idx, qpgs_data, qpiws_data)
                mqtt_pub.publish(f"{idx}/statistics", stats_tracker.get_data(idx))
            
            if info_tracker and qpgs_data:
                info_tracker.update(idx, qpgs_data, success=("error" not in qpgs_data))
                mqtt_pub.publish(f"{idx}/info", info_tracker.get_data(idx))
        
        # QPIRI - Rating Info
        if enable_qpiri and (not qpiri_cached or iteration_count % 10 == 0):
            resp = sr.query("QPIRI")
            if resp and len(resp) > 10:
                data = parser.parse_qpiri(resp)
                if "error" not in data:
                    qpiri_cached = data
                    mqtt_pub.publish("rating", data)

        # Sauvegarde périodique
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
