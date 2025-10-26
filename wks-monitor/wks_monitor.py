#!/usr/bin/env python3
import serial, time, json, paho.mqtt.client as mqtt, sys

# --- CONFIG MQTT ---
MQTT_BROKER = "core-mosquitto"
MQTT_PORT = 1883
MQTT_USER = "jeremy"
MQTT_PASS = "123456"
MQTT_TOPIC_BASE = "wks"

# --- CONFIG SÉRIE ---
PORT = "/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_BWAAc143M08-if00-port0"
BAUD = 2400
INDEXES = [0, 1, 2]
REFRESH_INTERVAL = 2   # secondes
TIMEOUT = 2

# --- CRC16 XMODEM ---
def crc16(data: bytes):
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = (crc << 1) ^ 0x1021 if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return crc

def send_cmd(ser, cmd_ascii: str, delay=0.35):
    cmd = cmd_ascii.encode("ascii")
    c = crc16(cmd)
    full = cmd + bytes([(c >> 8) & 0xFF, c & 0xFF]) + b"\r"
    ser.reset_input_buffer()
    ser.write(full)
    time.sleep(delay)
    return ser.read_until(b"\r").decode(errors="ignore").strip()

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

def publish_data(client, topic, data):
    payload = json.dumps(data)
    client.publish(topic, payload, qos=0, retain=True)
    print(f"📤 Publié sur {topic}")

def init_mqtt():
    print(f"[MQTT] Connexion à {MQTT_BROKER}:{MQTT_PORT}...")
    client = mqtt.Client(client_id=f"wks-monitor-{int(time.time())}")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        print("✅ MQTT connecté.")
    except Exception as e:
        print(f"❌ Erreur MQTT : {e}")
    return client

def main():
    mqtt_client = init_mqtt()
    print(f"🚀 WKS Monitor lancé — Lecture toutes les {REFRESH_INTERVAL}s")
    cycle = 0
    consecutive_errors = 0
    current_interval = REFRESH_INTERVAL

    while True:
        cycle += 1
        print(f"\n🔄 Cycle {cycle} — intervalle {current_interval}s")
        try:
            with serial.Serial(PORT, BAUD, timeout=TIMEOUT) as ser:
                for n in INDEXES:
                    resp = send_cmd(ser, f"QPGS{n}")
                    if resp and "NAK" not in resp and "00000000000000" not in resp:
                        parsed = parse_qpgs(n, resp)
                        publish_data(mqtt_client, f"{MQTT_TOPIC_BASE}/{n}/status", parsed)
                        consecutive_errors = 0
                        print(f"✅ QPGS{n} OK")
                    else:
                        print(f"⚠️ QPGS{n} — aucune réponse ou NAK")
                        consecutive_errors += 1
        except Exception as e:
            print(f"❌ Erreur série : {e}")
            consecutive_errors += 1
            current_interval = max(3, current_interval)

        # Adaptation douce si erreurs répétées
        if consecutive_errors >= 3:
            current_interval = 4
            print("⚠️ Communication instable → passage temporaire à 4s")
        else:
            current_interval = REFRESH_INTERVAL

        print(f"⏳ Pause {current_interval}s...")
        time.sleep(current_interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Arrêt manuel.")
        sys.exit(0)
