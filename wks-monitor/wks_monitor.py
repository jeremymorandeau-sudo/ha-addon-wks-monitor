#!/usr/bin/env python3
import serial, time, json, paho.mqtt.client as mqtt
from datetime import datetime

# --- CONFIGURATION ---
PORT = "/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_BWAAc143M08-if00-port0"
BAUD = 2400
MQTT_HOST = "core-mosquitto"
MQTT_PORT = 1883
MQTT_USER = "jeremy"
MQTT_PASS = "123456"
TOPIC_BASE = "wks"
SCAN_INTERVAL = 5
DRY_RUN = True

def log(msg, color="37"):
    ts = datetime.now().strftime("[%H:%M:%S]")
    print(f"\033[{color}m{ts} {msg}\033[0m")

def publish_data(client, topic, data):
    payload = json.dumps(data)
    client.publish(topic, payload, qos=0, retain=True)
    log(f"📤 Publié sur {topic}", "96")

def read_inverter(index):
    # Simulation de lecture trame (exemple)
    data = {
        "index": index,
        "ac_output_voltage": 230.0,
        "ac_output_freq": 50.0,
        "output_active_power_w": 80 + index*10,
        "battery_voltage": 52.1,
        "pv_input_voltage": 0.0,
        "battery_capacity_pct": 70 + index,
    }
    return data

def main():
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()
    log("🚀 WKS Monitor v2.0.4-B démarré (lecture seule)", "92")

    while True:
        for i in range(3):
            try:
                data = read_inverter(i)
                topic = f"{TOPIC_BASE}/{i}/status"
                publish_data(client, topic, data)
                log(f"✅ QPGS{i} OK", "92")
            except Exception as e:
                log(f"⚠️ Erreur onduleur {i}: {e}", "91")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
