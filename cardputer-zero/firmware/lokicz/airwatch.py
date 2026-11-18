"""Airwave watch — one passive listen that grades the
whole 2.4 GHz neighborhood, built from the Bruce /
Evil-Cardputer playbook read backwards: those firmwares
SEND beacon spam and karma lures; lokicz listens for
the signatures instead.

One 60 s monitor-mode session on the dongle counts:

  - Beacons (subtype 8): a beacon flood (Bruce's "beacon
    spam") lights up dozens of fake APs at once, or one
    SSID from a crowd of BSSIDs. Normal neighborhoods
    have a handful of APs; a flood is an order of
    magnitude more.
  - Probe responses (5) + beacons per BSSID: a karma
    device (Evil-Cardputer's signature attack) answers
    every probe by impersonating whatever SSID was
    asked for — one BSSID advertising MANY SSIDs is
    the tell. A real AP advertises a handful.
  - Deauth (12) / disassoc (10): graded exactly like
    deauth.watch (this module's older sibling).

Everything is a graded lead, never a verdict: dense
apartment blocks and ISP community SSIDs can look
busy honestly. Detection only — nothing here transmits.
"""

import subprocess
import threading
from collections import Counter, defaultdict

from . import capture, deauth, probes

FLOOD_BSSIDS = 60        # distinct beaconing BSSIDs/min
FLOOD_SSIDS_PER_NET = 8  # one SSID from this many BSSIDs
KARMA_SSIDS = 8          # one BSSID advertising this many


def _ssid_text(raw: str) -> str:
    """tshark fields mode emits SSIDs as hex bytes."""
    if raw and len(raw) % 2 == 0:
        try:
            dec = bytes.fromhex(raw).decode("utf-8")
            if dec.isprintable():
                return dec
        except (ValueError, UnicodeDecodeError):
            pass
    return raw


def analyze(frames: list[tuple]) -> dict:
    """Pure grading over (subtype, sa, ssid) frames —
    unit-tested with synthetic air."""
    beacons = 0
    beacon_aps: set = set()
    ssid_bssids: dict[str, set] = defaultdict(set)
    bssid_ssids: dict[str, set] = defaultdict(set)
    kinds: Counter = Counter()
    deauth_counts: Counter = Counter()
    for subtype, sa, ssid in frames:
        sa = (sa or "").upper()
        if not sa:
            continue
        if subtype == "8":
            beacons += 1
            beacon_aps.add(sa)
            if ssid:
                ssid_bssids[ssid].add(sa)
                bssid_ssids[sa].add(ssid)
        elif subtype == "5":
            if ssid:
                bssid_ssids[sa].add(ssid)
        elif subtype in ("12", "10"):
            kinds[subtype] += 1
            deauth_counts[sa] += 1

    flood = [{"ssid": ssid, "bssids": len(bs)}
             for ssid, bs in sorted(ssid_bssids.items())
             if len(bs) >= FLOOD_SSIDS_PER_NET]
    if len(beacon_aps) >= FLOOD_BSSIDS:
        flood.append({"ssid": "(many networks)",
                      "bssids": len(beacon_aps)})
    karma = [{"bssid": b, "ssids": len(ss),
              "sample": sorted(ss)[:5]}
             for b, ss in sorted(bssid_ssids.items())
             if len(ss) >= KARMA_SSIDS]
    total_deauth = sum(kinds.values())
    level, verdict = deauth.grade(
        total_deauth,
        deauth_counts.most_common(1)[0][1] if deauth_counts
        else 0)
    return {"beacons": beacons, "beacon_aps": len(beacon_aps),
            "deauth": kinds.get("12", 0),
            "disassoc": kinds.get("10", 0),
            "deauth_level": level, "deauth_verdict": verdict,
            "beacon_flood": flood, "karma_suspects": karma}


def watch(seconds: int = 60, iface: str = "wlan1") -> dict:
    capture._release(iface)
    stop = threading.Event()
    frames: list[tuple] = []
    try:
        capture._run(f"sudo -n ip link set {iface} down")
        capture._run(f"sudo -n iw dev {iface} set type monitor")
        capture._run(f"sudo -n ip link set {iface} up")
        hopper = threading.Thread(target=probes._hop,
                                  args=(iface, stop), daemon=True)
        hopper.start()
        proc = subprocess.Popen(
            ["sudo", "-n", "tshark", "-i", iface, "-l",
             "-Y", "wlan.fc.type_subtype == 8 || "
                   "wlan.fc.type_subtype == 5 || "
                   "wlan.fc.type_subtype == 12 || "
                   "wlan.fc.type_subtype == 10",
             "-T", "fields", "-e", "wlan.fc.type_subtype",
             "-e", "wlan.sa", "-e", "wlan.ssid",
             "-E", "separator=|"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True)

        def _reader():
            for line in proc.stdout:
                parts = line.strip().split("|")
                if len(parts) < 2:
                    continue
                ssid = _ssid_text(parts[2]) if len(parts) > 2 \
                    else ""
                frames.append((parts[0], parts[1], ssid))

        reader = threading.Thread(target=_reader, daemon=True)
        reader.start()
        try:
            stop.wait(seconds)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            reader.join(timeout=3)
    finally:
        stop.set()
        capture._restore(iface)

    out = analyze(frames)
    out["seconds"] = seconds
    out["frames"] = len(frames)
    return out
