from utils import log
from serial_comm import read_cmd

OUTPUT_PRIORITY_MAP = {0: "POP00", 1: "POP01", 2: "POP02"}
CHARGE_PRIORITY_MAP = {0: "PCP00", 1: "PCP01", 2: "PCP02"}

def _fmt_int_3d(value):
    try:
        v = int(float(value))
        return f"{v:03d}"
    except:
        return None

def _fmt_volt(value):
    try:
        v = float(value)
        return f"{v:.1f}"
    except:
        return None

def _maybe_send(ser, cmd, dry_run=True):
    if not cmd:
        return
    if dry_run:
        log(f"🧩 [DRY-RUN] Préparer: {cmd}")
        return
    resp = read_cmd(ser, cmd)
    if resp and "ACK" in resp:
        log(f"✅ ACK pour {cmd}")
    else:
        log(f"❌ Pas d'ACK pour {cmd} (réponse: {resp})")

def apply_settings(ser, s: dict, dry_run=True):
    if not s:
        log("ℹ️ Aucun réglage à appliquer.")
        return

    op = s.get("set_output_priority")
    if op in OUTPUT_PRIORITY_MAP:
        _maybe_send(ser, OUTPUT_PRIORITY_MAP[op], dry_run=dry_run)

    cp = s.get("set_charge_priority")
    if cp in CHARGE_PRIORITY_MAP:
        _maybe_send(ser, CHARGE_PRIORITY_MAP[cp], dry_run=dry_run)

    ac = _fmt_int_3d(s.get("set_ac_charge_current"))
    if ac is not None:
        _maybe_send(ser, f"MU{ac}", dry_run=dry_run)

    pv = _fmt_int_3d(s.get("set_pv_charge_current"))
    if pv is not None:
        _maybe_send(ser, f"MN{pv}", dry_run=dry_run)

    fv = _fmt_volt(s.get("set_float_voltage"))
    if fv is not None:
        _maybe_send(ser, f"PBFT{fv}", dry_run=dry_run)

    bv = _fmt_volt(s.get("set_bulk_voltage"))
    if bv is not None:
        _maybe_send(ser, f"PBAT{bv}", dry_run=dry_run)

    b2g = _fmt_volt(s.get("set_back_to_grid_voltage"))
    if b2g is not None:
        _maybe_send(ser, f"PBCV{b2g}", dry_run=dry_run)

    b2b = _fmt_volt(s.get("set_back_to_battery_voltage"))
    if b2b is not None:
        _maybe_send(ser, f"PBDV{b2b}", dry_run=dry_run)

    log("✅ Fin d'application des réglages (dry_run=%s)" % dry_run)
