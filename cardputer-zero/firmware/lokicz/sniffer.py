"""Surveillance sniffer — passive Wi-Fi/BLE ears, public-research signatures.

What this is: a defensive awareness tool. It listens (never
transmits) to the Wi-Fi networks and BLE advertisements already
floating through the air and compares them against signatures.json
— a small database where EVERY entry carries its public source and
an honest confidence tier. A hit is a lead graded by that tier,
never a verdict; the database itself documents why (including the
commercial detector that famously flagged a treadmill as a camera).

v1 coverage:
- Wi-Fi (managed scan): drone OUIs, drone SSID patterns, Flock
  watchlist patterns — matched against lokicz's structured scans.
- BLE: names + OUIs from bluetoothctl, and — when btmon is
  available — OpenDroneID service data (UUID 0xFFFA, the ASTM
  F3411 standard every legal US drone broadcasts) and DJI's
  0xFFE0, parsed out of raw advertising reports.

Deliberately NOT in v1 (in the DB as documented_not_implemented):
the two monitor-mode signatures — Flock's wildcard probe-request
fingerprint and Wi-Fi-form Remote ID. They need the dongle's frame
capture, a later step on the capture path.
"""

import json
import re
import subprocess
import time
from pathlib import Path

from . import wifi_recon

SIG_PATH = Path(__file__).with_name("signatures.json")
SNIFF_DIR = Path.home() / "lokicz-sniffs"


def load_signatures() -> list[dict]:
    return json.loads(SIG_PATH.read_text())["signatures"]


def _oui(mac: str) -> str:
    return mac.upper()[:8]


def match_wifi(ap: dict, sigs: list[dict]) -> list[dict]:
    hits = []
    for sig in sigs:
        if sig["kind"] == "oui" and _oui(ap["bssid"]) in sig["value"]:
            hits.append({"signature": sig["id"], "label": sig["label"],
                         "confidence": sig["confidence"], "radio": "wifi",
                         "identifier": ap["bssid"], "detail": ap["ssid"],
                         "rssi": int(ap["signal_dbm"])})
        elif (sig["kind"] == "wifi_ssid_prefix" and ap["ssid"] and
              ap["ssid"].upper().startswith(tuple(sig["value"]))):
            hits.append({"signature": sig["id"], "label": sig["label"],
                         "confidence": sig["confidence"], "radio": "wifi",
                         "identifier": ap["bssid"], "detail": ap["ssid"],
                         "rssi": int(ap["signal_dbm"])})
    return hits


def scan_ble(seconds: int) -> tuple[list[dict], str]:
    """BLE observations: [{address, name, rssi, uuids}] + method used.

    btmon gives the full advertising payload (that's where service
    UUIDs live); bluetoothctl gives names/MACs only. We run both
    when btmon exists, else bluetoothctl alone.
    """
    devices: dict[str, dict] = {}
    method = "bluetoothctl"
    btmon_text = ""
    procs = []
    try:
        p = subprocess.Popen(["sudo", "-n", "btmon"],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True)
        procs.append(p)
        method = "btmon+bluetoothctl"
    except OSError:
        pass
    try:
        # bluetoothctl needs its own --timeout to stay alive: a bare
        # one-shot `scan on` exits instantly and kills discovery
        # before any advertisement lands (verified on hardware —
        # 0 devices without it, 10 in 20 s with it).
        ctl = subprocess.run(["bluetoothctl", "--timeout", str(seconds),
                              "scan", "on"], capture_output=True,
                             text=True, timeout=seconds + 15)
        out = ctl.stdout or ""
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    for p in procs:
        p.terminate()
        try:
            btmon_text = p.communicate(timeout=5)[0] or ""
        except subprocess.TimeoutExpired:
            p.kill()

    for m in re.finditer(
            r"Device ([0-9A-F:]{17}) (.*)", out):
        addr, rest = m.group(1), m.group(2)
        dev = devices.setdefault(addr, {"address": addr, "name": "",
                                        "rssi": 0, "uuids": []})
        if rest and not rest.startswith(("(", "RSSI", "TxPower")):
            dev["name"] = rest.strip()
    for m in re.finditer(r"Device ([0-9A-F:]{17}) RSSI: (-?\d+)", out):
        if m.group(1) in devices:
            devices[m.group(1)]["rssi"] = int(m.group(2))

    # btmon: split into per-report blocks; a block mentioning a known
    # service UUID attributes it to the block's address.
    if btmon_text:
        for block in re.split(r"LE Advertising Report", btmon_text):
            addr_m = re.search(r"Address: ([0-9A-F:]{17})", block)
            if not addr_m:
                continue
            addr = addr_m.group(1)
            dev = devices.setdefault(addr, {"address": addr, "name": "",
                                            "rssi": 0, "uuids": []})
            low = block.lower()
            for uuid in ("fffa", "ffe0"):
                if uuid in low and uuid not in dev["uuids"]:
                    dev["uuids"].append(uuid)
            name_m = re.search(r"Name \(complete\): (.+)", block)
            if name_m:
                dev["name"] = name_m.group(1).strip()
            rssi_m = re.search(r"RSSI: (-?\d+)", block)
            if rssi_m and not dev["rssi"]:
                dev["rssi"] = int(rssi_m.group(1))
    return list(devices.values()), method


def match_ble(dev: dict, sigs: list[dict]) -> list[dict]:
    hits = []
    for sig in sigs:
        if sig["kind"] in ("ble_service_data", "ble_service"):
            if sig["value"] in dev["uuids"]:
                hits.append({"signature": sig["id"], "label": sig["label"],
                             "confidence": sig["confidence"], "radio": "ble",
                             "identifier": dev["address"],
                             "detail": dev["name"], "rssi": dev["rssi"]})
        elif sig["kind"] == "oui" and _oui(dev["address"]) in sig["value"]:
            hits.append({"signature": sig["id"], "label": sig["label"],
                         "confidence": sig["confidence"], "radio": "ble",
                         "identifier": dev["address"],
                         "detail": dev["name"], "rssi": dev["rssi"]})
        elif (sig["kind"] == "ble_name_prefix" and dev["name"] and
              dev["name"].upper().startswith(tuple(sig["value"]))):
            hits.append({"signature": sig["id"], "label": sig["label"],
                         "confidence": sig["confidence"], "radio": "ble",
                         "identifier": dev["address"],
                         "detail": dev["name"], "rssi": dev["rssi"]})
    return hits


def run_sniff(seconds: int = 120, progress=None) -> dict:
    sigs = load_signatures()
    SNIFF_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    log_path = SNIFF_DIR / f"sniff-{stamp}.jsonl"

    hits: dict[tuple, dict] = {}
    wifi_obs = ble_obs = 0
    ble_window = min(30, seconds)
    ble_devices, method = scan_ble(ble_window)
    ble_obs = len(ble_devices)
    for dev in ble_devices:
        for hit in match_ble(dev, sigs):
            hits[(hit["signature"], hit["identifier"])] = hit
    if progress:
        progress(f"BLE done ({method}): {ble_obs} devices")

    t_end = time.time() + max(0, seconds - ble_window)
    while True:
        aps = wifi_recon.scan_aps("wlan0")
        wifi_obs += len(aps)
        for ap in aps:
            for hit in match_wifi(ap, sigs):
                hits[(hit["signature"], hit["identifier"])] = hit
        if progress:
            progress(f"Wi-Fi: {wifi_obs} obs, hits so far: {len(hits)}")
        if time.time() >= t_end:
            break
        time.sleep(10)

    with open(log_path, "w") as f:
        for hit in hits.values():
            f.write(json.dumps(hit) + "\n")
    return {"file": str(log_path), "hits": list(hits.values()),
            "wifi_obs": wifi_obs, "ble_obs": ble_obs, "ble_method": method}


def main() -> int:
    import sys

    from . import ui

    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 120

    def show(lines):
        print("\n".join(lines))
        try:
            ui.show_text(lines)
        except OSError:
            pass

    show(["Sniffing (passive)...", f"{seconds}s — Wi-Fi + BLE"])
    stats = run_sniff(seconds, progress=lambda m: show(["Sniffing...", m]))
    lines = ["Sniff done",
             f"Wi-Fi obs: {stats['wifi_obs']}  BLE: {stats['ble_obs']}",
             f"hits: {len(stats['hits'])}"]
    for hit in stats["hits"][:3]:
        lines.append(f"[{hit['confidence']}] {hit['label']}")
    show(lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
