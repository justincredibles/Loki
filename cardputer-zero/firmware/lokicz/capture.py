"""Wi-Fi handshake capture — the Pwnagotchi loop, on the USB dongle.

Plain-English tour:
- The built-in CYW43439 radio can only *watch* (managed mode). All
  capturing happens on the USB dongle (an RTL8822BU, interface
  wlan1), which can run in monitor mode.
- We create a throwaway monitor interface (`lokimon`) on the
  dongle's PHY, hand it to hcxdumptool for a timed run, then delete
  it — the dongle's normal interface is never touched.
- hcxdumptool writes a pcapng; hcxpcapngtool then counts what was
  caught: PMKIDs and EAPOL handshakes (each becomes one line in a
  hashcat .hc22000 file — the count IS the score).

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

MON_NAME = "lokimon"
CAPTURE_DIR = Path.home() / "lokicz-captures"


def _run(cmd: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True,
                          text=True, timeout=timeout)


def _sudo(cmd: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return _run(f"sudo -n {cmd}", timeout=timeout)


def phy_of(iface: str) -> str:
    """'wlan1' -> 'phy2' (the radio the interface belongs to)."""
    out = _run(f"iw dev {iface} info").stdout
    m = re.search(r"wiphy\s+(\d+)", out)
    if not m:
        raise RuntimeError(f"cannot find PHY for {iface} — is it plugged in?")
    return f"phy{m.group(1)}"


def ensure_monitor(iface: str) -> str:
    """Create (or recycle) the monitor interface on iface's radio."""
    _sudo(f"iw dev {MON_NAME} del")  # stale one from a crashed run
    phy = phy_of(iface)
    r = _sudo(f"iw phy {phy} interface add {MON_NAME} type monitor")
    if r.returncode != 0:
        raise RuntimeError(f"monitor interface failed: {r.stderr.strip()}")
    _sudo(f"ip link set {MON_NAME} up")
    return MON_NAME


def drop_monitor() -> None:
    _sudo(f"iw dev {MON_NAME} del")


def run_capture(seconds: int = 90, iface: str = "wlan1") -> dict:
    """Run one timed capture and return honest stats about it."""
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    pcapng = CAPTURE_DIR / f"capture-{stamp}.pcapng"
    mon = ensure_monitor(iface)
    try:
        # SIGINT lets hcxdumptool close the pcapng cleanly.
        proc = subprocess.Popen(
            ["sudo", "-n", "hcxdumptool", "-i", mon, "-w", str(pcapng),
             "--disable_deauthentication"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        try:
            proc.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            proc.send_signal(2)  # SIGINT
            proc.wait(timeout=15)
    finally:
        drop_monitor()

    stats = {"pcapng": str(pcapng), "seconds": seconds,
             "bytes": pcapng.stat().st_size if pcapng.exists() else 0,
             "hashes": 0, "pmkid": 0, "eapol": 0}
    if stats["bytes"]:
        hashfile = pcapng.with_suffix(".hc22000")
        r = _run(f"hcxpcapngtool -o {hashfile} {pcapng}", timeout=120)
        if hashfile.exists():
            stats["hashes"] = len(hashfile.read_text().splitlines())
        for label, key in (("PMKID(s)", "pmkid"), ("EAPOL", "eapol")):
            m = re.search(rf"{re.escape(label)}[^\d]*?(\d+)\s*$",
                          r.stdout, re.M)
            if m:
                stats[key] = int(m.group(1))
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
        f"  PMKID: {stats['pmkid']}  EAPOL: {stats['eapol']}",
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
