"""Deauth-flood watch — passive detection only.

Deauthentication attacks kick clients off Wi-Fi by
flooding forged deauth/disassoc frames (the noisy half
of every evil-twin playbook). lokicz never sends one —
capture.py runs hcxdumptool with deauthentication
disabled by design — but it can LISTEN for them: park
the dongle in monitor mode for a minute, count deauth
(subtype 12) and disassoc (subtype 10) frames per
source, and grade what it heard.

A few deauths are normal life (APs managing clients,
roaming). A flood from one source is not. Verdicts are
graded leads, same honesty rule as the sniffer: an
elevated count says "worth a look", not "attack
proven" — a busy enterprise AP can look shouty too.
"""

import subprocess
import threading
import time
from collections import Counter

from . import capture, probes

# Per-minute grading. Normal homes sit near zero; a
# targeted flood runs hundreds per minute.
ELEVATED_TOTAL = 25
ELEVATED_SOURCE = 15
FLOOD_TOTAL = 100


def grade(total: int, top_count: int) -> tuple[str, str]:
    if total == 0:
        return ("quiet",
                "not a single deauth/disassoc heard — "
                "the air is polite")
    if total >= FLOOD_TOTAL or top_count >= FLOOD_TOTAL // 2:
        return ("flood",
                "deauth FLOOD — this volume is not normal "
                "network life; someone nearby is very "
                "likely kicking clients off Wi-Fi")
    if total >= ELEVATED_TOTAL or top_count >= ELEVATED_SOURCE:
        return ("elevated",
                "elevated deauth traffic — could be a "
                "busy AP managing clients, could be the "
                "start of an attack; worth watching")
    return ("normal",
            "a few deauths — ordinary AP/client housekeeping")


def watch(seconds: int = 60, iface: str = "wlan1") -> dict:
    capture._release(iface)
    stop = threading.Event()
    counts: Counter = Counter()
    kinds: Counter = Counter()
    try:
        capture._run(f"sudo -n ip link set {iface} down")
        capture._run(f"sudo -n iw dev {iface} set type monitor")
        capture._run(f"sudo -n ip link set {iface} up")
        hopper = threading.Thread(target=probes._hop,
                                  args=(iface, stop), daemon=True)
        hopper.start()
        proc = subprocess.Popen(
            ["sudo", "-n", "tshark", "-i", iface, "-l",
             "-Y", "wlan.fc.type_subtype == 12 || "
                   "wlan.fc.type_subtype == 10",
             "-T", "fields", "-e", "wlan.fc.type_subtype",
             "-e", "wlan.sa", "-E", "separator=|"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True)

        def _reader():
            # A dedicated reader thread: a blocking readline
            # in the main thread would hang forever on a
            # quiet night when zero frames arrive — the
            # deadline must live outside the read.
            for line in proc.stdout:
                parts = line.strip().split("|")
                if len(parts) < 2 or not parts[1]:
                    continue
                kinds[parts[0]] += 1
                counts[parts[1].upper()] += 1

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

    total = sum(counts.values())
    top = [{"mac": mac, "count": n}
           for mac, n in counts.most_common(5)]
    level, verdict = grade(total, top[0]["count"] if top else 0)
    return {"seconds": seconds, "total": total,
            "deauth": kinds.get("12", 0),
            "disassoc": kinds.get("10", 0),
            "top_sources": top, "level": level,
            "verdict": verdict}
