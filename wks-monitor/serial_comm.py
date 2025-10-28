import serial, time
from utils import crc16

def read_cmd(ser, cmd_ascii: str, delay=0.25):
    cmd = cmd_ascii.encode("ascii")
    c = crc16(cmd)
    full = cmd + bytes([(c >> 8) & 0xFF, c & 0xFF]) + b"\r"
    ser.write(full)
    time.sleep(delay)
    return ser.readline().decode(errors="ignore").strip()
