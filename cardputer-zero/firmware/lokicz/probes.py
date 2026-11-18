"""Probe-request logger — what the phones around you are asking for.

Every Wi-Fi device looking for a network broadcasts probe
requests. Wildcard probes ask 'anyone there?'; DIRECTED probes
name the network — 'is `HomeWiFi` there? is `Airport_Lounge`
there?' — reciting the device's preferred-network list, which
is a travel diary of everywhere it has ever connected.

This logger parks the dongle in monitor mode, hops the busy
channels, and records directed probes with tshark: which
device (MAC) asked for which SSIDs, how loud, how often.
Passive only — it never answers a probe.

Honest limits: modern phones randomise their MAC per burst,
so 'devices' overcounts people; the durable signal is the
SSID lists themselves. And a quiet room is a valid result —
well-behaved modern devices mostly wildcard-probe.
"""

import json
import subprocess
import threading
import time
from pathlib import Path

from . import capture

PROBE_DIR = Path.home() / "lokicz-probes"
_CHANNELS = (1, 6, 11, 3, 8, 36, 44, 149, 157)


def _hop(iface: str, stop: threading.Event) -> None:
    i = 0
    while not stop.is_set():
        ch = _CHANNELS[i % len(_CHANNELS)]
        capture._run(f"sudo -n iw dev {iface} set channel {ch}",
                     timeout=5)
        i += 1
        stop.wait(1.5)


def run_probes(seconds: int = 60, iface: str = "wlan1") -> dict:
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    log_path = PROBE_DIR / f"probes-{stamp}.jsonl"

    capture._release(iface)
    stop = threading.Event()
    devices: dict[str, dict] = {}
    total = wildcard = 0
    try:
        capture._run(f"sudo -n ip link set {iface} down")
        capture._run(f"sudo -n iw dev {iface} set type monitor")
        capture._run(f"sudo -n ip link set {iface} up")
        hopper = threading.Thread(target=_hop, args=(iface, stop),
                                  daemon=True)
        hopper.start()
        proc = subprocess.Popen(
            ["sudo", "-n", "tshark", "-i", iface, "-l",
             "-Y", "wlan.fc.type_subtype == 4",
             "-T", "fields", "-e", "wlan.sa", "-e", "wlan.ssid",
             "-e", "radiotap.dbm_antsignal", "-E", "separator=|"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True)
        try:
            deadline = time.time() + seconds
            while time.time() < deadline:
                line = proc.stdout.readline()
                if not line:
                    break
                parts = line.strip().split("|")
                if len(parts) < 2 or not parts[0]:
                    continue
                mac, ssid = parts[0].upper(), parts[1]
                try:
                    rssi = int(parts[2]) if len(parts) > 2 \
                        and parts[2] else 0
                except ValueError:
                    rssi = 0
                total += 1
                dev = devices.setdefault(mac, {
                    "mac": mac, "ssids": [], "count": 0,
                    "best_rssi": -999})
                dev["count"] += 1
                if rssi:
                    dev["best_rssi"] = max(dev["best_rssi"], rssi)
                if ssid:
                    if ssid not in dev["ssids"]:
                        dev["ssids"].append(ssid)
                else:
                    wildcard += 1
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    finally:
        stop.set()
        capture._restore(iface)

    directed = {m: d for m, d in devices.items() if d["ssids"]}
    popularity: dict[str, int] = {}
    for d in directed.values():
        for s in d["ssids"]:
            popularity[s] = popularity.get(s, 0) + 1
    top = sorted(popularity.items(), key=lambda kv: -kv[1])

    with open(log_path, "w") as f:
        for d in sorted(directed.values(),
                        key=lambda d: -d["count"]):
            f.write(json.dumps(d) + "\n")
    return {"file": str(log_path), "seconds": seconds,
            "probes_total": total, "wildcard": wildcard,
            "devices": len(devices),
            "directed_devices": len(directed),
            "unique_ssids": len(popularity),
            "top_ssids": [{"ssid": s, "devices": n}
                          for s, n in top[:10]],
            "loudest": sorted(
                ({"mac": d["mac"], "ssids": d["ssids"],
                  "count": d["count"], "best_rssi": d["best_rssi"]}
                 for d in directed.values()),
                key=lambda d: -d["best_rssi"])[:8]}


if __name__ == "__main__":
    import sys

    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    r = run_probes(secs)
    print(f"{r['probes_total']} probes, {r['devices']} devices, "
          f"{r['directed_devices']} directed, "
          f"{r['unique_ssids']} unique SSIDs")
    for t in r["top_ssids"]:
        print(f"  {t['ssid']:<28} x{t['devices']}")
