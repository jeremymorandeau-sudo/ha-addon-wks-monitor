import json
import os
import sys
import time
import threading
from pathlib import Path

import paho.mqtt.client as mqtt
import serial

OPTIONS_PATH = Path("/data/options.json")

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
    return bool(resp and resp.startswith(b"(") and resp.endswith(b"\r"))

def parse_qpgs(resp: bytes) -> dict:
    txt = resp.strip().decode(errors="ignore")
    data = {"raw": txt}
    return data

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

    client = mqtt_client(mqtt_host, mqtt_port, mqtt_user, mqtt_pass)

    consecutive_fail = 0

    while True:
        any_ok = False
        for idx in range(inverter_count):
            cmd = f"QPGS{idx}\r".encode()
            resp = sr.query(cmd)

            if not resp or not is_valid_qpgs(resp):
                log(f"[WARN] ⚠️ Aucune réponse ou trame invalide pour QPGS{idx}")
                consecutive_fail += 1
                continue

            try:
                data = parse_qpgs(resp)
                topic = f"{topic_prefix}/{idx}/status"
                client.publish(topic, json.dumps(data), qos=0, retain=True)
                if debug:
                    log(f"[OK] QPGS{idx} → publish {topic}")
                any_ok = True
            except Exception as e:
                log(f"[PARSER] Erreur parse QPGS{idx}: {e}")
                consecutive_fail += 1

            time.sleep(0.05)

        if not any_ok:
            if consecutive_fail >= max_consecutive_fail:
                log("[HEAL] Trop d'échecs consécutifs — on referme/réouvre le port proprement")
                sr.close()
                time.sleep(1.0)
                sr.open()
                consecutive_fail = 0
            else:
                if poll_interval < 3.0:
                    log("⚠️ Communication instable, passage temporaire à 3s")
                    time.sleep(3.0)
                else:
                    time.sleep(poll_interval)
        else:
            consecutive_fail = 0
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