"""Wi-Fi handshake capture — the Pwnagotchi loop, on the USB dongle.

Plain-English tour:
- The built-in CYW43439 radio can only *watch* (managed mode). All
  capturing happens on the USB dongle (an RTL8822BU, interface
  wlan1), which can run in monitor mode.
- hcxdumptool insists on owning its interface outright: on this
  driver a separate monitor vif starves ("failed to arm interface",
  0 packets), while handing it wlan1 itself captured ~1,900 packets
  in 15 s. So: NetworkManager releases the dongle, hcxdumptool
  takes it (it sets monitor mode, channel plan and a virtual MAC
  itself), and afterwards we put the interface back to managed
  mode and hand it back to NetworkManager.
- hcxdumptool writes a pcapng; hcxpcapngtool then scores it. The
  score that matters is the .hc22000 line count — one line per
  crackable PMKID/handshake. Raw EAPOL/PMKID counts are reported
  too, including the useless ones, because honesty beats confetti.

Safety posture (Loki design rule: attack-class actions are gated):
the default profile runs with --disable_deauthentication, so the
tool never knocks a client off its network. It still requests
PMKIDs and records handshakes it overhears — standard handshake
capture, same as Pwnagotchi's passive side. Dropping the
--disable flag is an attack-class change and belongs behind the
arm token, not in a default.
"""

import os
import re
import subprocess
import time
from pathlib import Path

CAPTURE_DIR = Path.home() / "lokicz-captures"


def _run(cmd: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True,
                          text=True, timeout=timeout)


def _release(iface: str) -> None:
    """Take the dongle away from NetworkManager for the run."""
    _run(f"nmcli device set {iface} managed no")
    time.sleep(1)


def _restore(iface: str) -> None:
    """Put the interface back exactly as a normal Wi-Fi device."""
    _run(f"sudo -n ip link set {iface} down")
    _run(f"sudo -n iw dev {iface} set type managed")
    _run(f"sudo -n ip link set {iface} up")
    _run(f"nmcli device set {iface} managed yes")


def run_capture(seconds: int = 90, iface: str = "wlan1",
                stop_check=None) -> dict:
    """Run one timed capture and return honest stats about it.

    `stop_check` ends the run early via the same SIGINT path as
    the natural timeout: hcxdumptool closes the pcapng cleanly,
    the partial capture is scored like any other, and the
    finally-restore returns the dongle to managed mode either
    way. The portal passes no stop_check (full window)."""
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    pcapng = CAPTURE_DIR / f"capture-{stamp}.pcapng"
    _release(iface)
    stopped = False
    t0 = time.time()
    try:
        # SIGINT lets hcxdumptool close the pcapng cleanly.
        proc = subprocess.Popen(
            ["sudo", "-n", "hcxdumptool", "-i", iface, "-w", str(pcapng),
             "--disable_deauthentication"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        out = ""
        while True:
            try:
                out, _ = proc.communicate(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                if stop_check and stop_check():
                    stopped = True
                if stopped or time.time() - t0 >= seconds:
                    proc.send_signal(2)  # SIGINT
                    out, _ = proc.communicate(timeout=15)
                    break
    finally:
        _restore(iface)

    stats = {"pcapng": str(pcapng),
             "seconds": int(round(time.time() - t0)),
             "stopped": stopped,
             "bytes": pcapng.stat().st_size if pcapng.exists() else 0,
             "hashes": 0, "pmkid": 0, "eapol": 0,
             "tool_tail": "\n".join((out or "").splitlines()[-3:])}
    if stats["bytes"]:
        hashfile = pcapng.with_suffix(".hc22000")
        r = _run(f"hcxpcapngtool -o {hashfile} {pcapng}", timeout=120)
        if hashfile.exists():
            stats["hashes"] = len(hashfile.read_text().splitlines())
        m = re.search(r"EAPOL messages \(total\)\.*:\s*(\d+)", r.stdout)
        if m:
            stats["eapol"] = int(m.group(1))
        m = re.search(r"PMKID \(best\)\.*:\s*(\d+)", r.stdout)
        if m:
            stats["pmkid"] = int(m.group(1))
    return stats


def main() -> int:
    import sys

    from . import ui

    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    iface = os.environ.get("LOKICZ_CAPTURE_IFACE", "wlan1")
    lines = ["Loki capture", f"iface: {iface}", f"running {seconds}s..."]
    print("\n".join(lines))
    try:
        ui.show_text(lines)
    except OSError:
        pass
    stats = run_capture(seconds, iface)
    lines = [
        "Loki capture — done",
        f"hashes caught: {stats['hashes']}",
        f"  PMKID best: {stats['pmkid']}  EAPOL: {stats['eapol']}",
        f"pcap: {stats['bytes'] // 1024} KB",
    ]
    print("\n".join(lines))
    try:
        ui.show_text(lines)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
