#!/usr/bin/env python3
import serial, time, json, paho.mqtt.client as mqtt, sys, warnings, os
from datetime import datetime
from utils import log, crc16
from serial_comm import read_cmd
from settings_writer import apply_settings

warnings.filterwarnings("ignore", category=DeprecationWarning)

DEFAULTS = {
    "port": "/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_BWAAc143M08-if00-port0",
    "baudrate": 2400,
    "mqtt_host": "core-mosquitto",
    "mqtt_port": 1883,
    "mqtt_topic": "wks",
    "scan_interval": 5,
    "apply_settings_on_start": False,
    "set_output_priority": 2,
    "set_charge_priority": 2,
    "set_ac_charge_current": 20,
    "set_pv_charge_current": 60,
    "set_float_voltage": 54.8,
    "set_bulk_voltage": 56.4,
    "set_back_to_grid_voltage": 48.0,
    "set_back_to_battery_voltage": 51.0
}

def load_config():
    cfg = DEFAULTS.copy()
    path = "/data/options.json"
    try:
        if os.path.exists(path):
            with open(path) as f:
                loaded = json.load(f)
            for k in DEFAULTS.keys():
                if k in loaded:
                    cfg[k] = loaded[k]
    except Exception as e:
        log(f"⚠️ Erreur lecture /data/options.json: {e} — valeurs par défaut utilisées.")
    return cfg

def init_mqtt(host, port, user=None, password=None):
    client = mqtt.Client()
    if user and password:
        client.username_pw_set(user, password)
    client.connect(host, port, 60)
    client.loop_start()
    return client

def publish_data(client, topic, data):
    payload = json.dumps(data)
    client.publish(topic, payload, qos=0, retain=True)
    log(f"📤 Publié sur {topic}")

def send_cmd(ser, cmd_ascii: str, delay=0.25):
    cmd = cmd_ascii.encode("ascii")
    c = crc16(cmd)
    full = cmd + bytes([(c >> 8) & 0xFF, c & 0xFF]) + b"\r"
    ser.write(full)
    time.sleep(delay)
    return ser.readline().decode(errors="ignore").strip()

def decode_flags(binary_str):
    if len(binary_str) != 8:
        return {"raw": binary_str}
    bits = list(binary_str)
    return {
        "inverter_output": bits[0] == "1",
        "fault": bits[1] == "1",
        "bypass": bits[2] == "1",
        "battery_charging": bits[3] == "1",
        "ac_input_present": bits[4] == "1",
        "pv_charging": bits[5] == "1",
        "load_on_battery": bits[6] == "1",
        "overload": bits[7] == "1"
    }

def parse_qpgs(index, resp):
    vals = resp.strip("()").split()
    data = {"index": index, "raw": resp}
    if len(vals) < 25:
        data["error"] = f"Trame incomplète ({len(vals)} valeurs)"
        return data
    try:
        data.update({
            "serial_number": vals[1],
            "device_type": vals[2],
            "ac_output_voltage": float(vals[6]),
            "ac_output_freq": float(vals[7]),
            "output_active_power_w": int(vals[9]),
            "output_load_pct": int(vals[10]),
            "battery_voltage": float(vals[11]),
            "battery_charge_current_a": int(vals[12]),
            "battery_capacity_pct": int(vals[13]),
            "pv_input_voltage": float(vals[14]),
            "pv_input_current_a": int(vals[15]),
            "heatsink_temp": int(vals[16]),
            "dc_bus_voltage": int(vals[17]),
            "status_flags_raw": vals[19],
            "status_flags": decode_flags(vals[19]),
            "parallel_role": "Master" if vals[20] == "1" else "Slave",
            "total_units": int(vals[21]),
            "battery_temp_c": vals[24] if len(vals) > 24 else ""
        })
    except Exception as e:
        data["error"] = str(e)
    return data

def main():
    cfg = load_config()
    PORT = cfg["port"]
    BAUD = int(cfg["baudrate"])
    MQTT_HOST = cfg["mqtt_host"]
    MQTT_PORT = int(cfg["mqtt_port"])
    MQTT_TOPIC_BASE = cfg["mqtt_topic"]
    REFRESH_INTERVAL = int(cfg["scan_interval"])
    APPLY = bool(cfg.get("apply_settings_on_start", False))

    log(f"🚀 WKS Monitor v2.0.0 — port={PORT} baud={BAUD} mqtt={MQTT_HOST}:{MQTT_PORT} topic={MQTT_TOPIC_BASE}")
    mqtt_client = init_mqtt(MQTT_HOST, MQTT_PORT)
    consecutive_errors = 0
    INDEXES = [0, 1, 2]

    while True:
        try:
            with serial.Serial(PORT, BAUD, timeout=2) as ser:
                log("✅ Port série ouvert.")
                for cmd, label in [("QPIRI","QPIRI"),("QPIGS","QPIGS"),("QMOD","QMOD"),("QPIWS","QPIWS"),("QFLAG","QFLAG"),("QVFW","QVFW"),("QID","QID")]:
                    try:
                        resp = read_cmd(ser, cmd)
                        log(f"📥 {label}: {resp}")
                    except Exception as e:
                        log(f"⚠️ {label} erreur: {e}")

                try:
                    apply_settings(ser, cfg, dry_run=(not APPLY))
                except Exception as e:
                    log(f"⚠️ Paramétrage: {e}")

                for n in INDEXES:
                    resp = send_cmd(ser, f"QPGS{n}")
                    if resp and "NAK" not in resp and "00000000000000" not in resp:
                        parsed = parse_qpgs(n, resp)
                        publish_data(mqtt_client, f"{MQTT_TOPIC_BASE}/{n}/status", parsed)
                        log(f"✅ QPGS{n} OK")
                        consecutive_errors = 0
                    else:
                        log(f"⚠️ Aucune réponse ou trame invalide pour QPGS{n}")
                        consecutive_errors += 1

        except Exception as e:
            log(f"❌ Erreur série : {e}")
            consecutive_errors += 1

        pause = 3 if consecutive_errors >= 3 else REFRESH_INTERVAL
        log(f"⏳ Pause {pause}s...\n")
        time.sleep(pause)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("🛑 Arrêt manuel du script.")
        sys.exit(0)
