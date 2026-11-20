"""Wardriving logger — Wi-Fi scans + GPS, written as a WiGLE CSV.

Plain-English tour:
- Every few seconds the built-in radio (managed mode — wardriving
  needs breadth, not monitor mode) lists the access points around
  us. Each NEW network is appended to a WiGLE-format CSV the moment
  it's first seen, stamped with the freshest GPS fix.
- GPS comes from the LoRa cap's GP-02 module (CASIC; meshtasticd
  detects it as "ATGM336H") on /dev/ttyS0, NMEA at 115200 baud —
  zeroradio's hardware map for this cap is the source. With any
  other cap fitted there is simply no GPS:
  the reader thread finds no sentences and rows go out with empty
  coordinates — the file stays valid, the map just waits for the
  cap swap.
- The CSV is the real WiGLE upload format (preamble line, column
  header, one row per network), so it can go straight to wigle.net
  or any tool that reads their files.
"""

import csv
import os
import subprocess
import threading
import time
from pathlib import Path

from . import wifi_recon

WARDRIVE_DIR = Path.home() / "lokicz-wardrives"
GPS_PORT = "/dev/ttyS0"

PREAMBLE = ("WigleWifi-1.4,appRelease=lokicz 0.1.0,model=Cardputer Zero,"
            "release=2026-11,device=lokicz,display=ST7789v3,board=CM0,"
            "brand=M5Stack")
COLUMNS = ["MAC", "SSID", "AuthMode", "FirstSeen", "Channel", "RSSI",
           "CurrentLatitude", "CurrentLongitude", "AltitudeMeters",
           "AccuracyMeters", "Type"]


def _nmea_coord(raw: str, hemi: str) -> float:
    """'3541.2345' + 'N' -> 35.687... (empty/garbage -> 0.0)."""
    try:
        value = float(raw)
    except ValueError:
        return 0.0
    degrees = int(value // 100)
    minutes = value - degrees * 100
    out = degrees + minutes / 60.0
    return -out if hemi in ("S", "W") else out


class GpsReader(threading.Thread):
    """Background NMEA listener; .fix is the latest good position."""

    def __init__(self, port: str = GPS_PORT) -> None:
        super().__init__(daemon=True)
        self.port = port
        self.fix: dict | None = None

    def run(self) -> None:
        try:
            subprocess.run(["stty", "-F", self.port, "115200", "raw", "-echo"],
                           capture_output=True, timeout=5)
            fd = os.open(self.port, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            return  # no GPS on this cap — fixes stay None, by design
        buf = b""
        while True:
            try:
                chunk = os.read(fd, 256)
            except OSError:
                chunk = b""
            if not chunk:
                time.sleep(0.2)
                continue
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                self._sentence(line.decode("ascii", "ignore").strip())

    def _sentence(self, line: str) -> None:
        if not line.startswith("$"):
            return
        parts = line.split("*")[0].split(",")
        try:
            if parts[0].endswith("GGA") and parts[6] != "0":
                self.fix = {
                    "lat": _nmea_coord(parts[2], parts[3]),
                    "lon": _nmea_coord(parts[4], parts[5]),
                    "alt": float(parts[9] or 0),
                    "sats": int(parts[7] or 0),
                }
            elif parts[0].endswith("RMC") and parts[2] == "A":
                self.fix = {
                    "lat": _nmea_coord(parts[3], parts[4]),
                    "lon": _nmea_coord(parts[5], parts[6]),
                    "alt": (self.fix or {}).get("alt", 0.0),
                    "sats": (self.fix or {}).get("sats", 0),
                }
        except (IndexError, ValueError):
            pass  # a garbled sentence costs us nothing


def run_wardrive(seconds: int = 300, interval: int = 10,
                 iface: str = "wlan0", progress=None,
                 stop_check=None) -> dict:
    """Log new networks for `seconds`; return a session summary.

    `stop_check` ends the session early — rows are written and
    flushed the moment each network is first seen, so the CSV
    already holds everything collected; stopping loses nothing."""
    WARDRIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = WARDRIVE_DIR / f"wardrive-{stamp}.csv"
    gps = GpsReader()
    gps.start()

    seen: dict[str, dict] = {}
    sightings = 0
    stopped = False
    with open(path, "w", newline="") as f:
        f.write(PREAMBLE + "\n")
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        f.flush()
        t_end = time.time() + seconds
        while time.time() < t_end:
            if stop_check and stop_check():
                stopped = True
                break
            fix = gps.fix
            for ap in wifi_recon.scan_aps(iface):
                sightings += 1
                if ap["bssid"] in seen:
                    continue
                seen[ap["bssid"]] = ap
                writer.writerow([
                    ap["bssid"], ap["ssid"], ap["auth"],
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    ap["channel"], int(ap["signal_dbm"]),
                    f"{fix['lat']:.6f}" if fix else "",
                    f"{fix['lon']:.6f}" if fix else "",
                    f"{fix['alt']:.1f}" if fix else "",
                    0, "WIFI",
                ])
            f.flush()
            if progress:
                progress(len(seen), gps.fix)
            # Interval sleep in slices so a stop press lands fast.
            slept = 0.0
            while slept < interval:
                if stop_check and stop_check():
                    break
                time.sleep(0.5)
                slept += 0.5

    return {"file": str(path), "networks": len(seen),
            "sightings": sightings, "gps_fix": gps.fix is not None,
            "stopped": stopped}


def main() -> int:
    import sys

    from . import ui

    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    def show(lines):
        print("\n".join(lines))
        try:
            ui.show_text(lines)
        except OSError:
            pass

    show(["Wardriving...", f"{seconds}s — scanning wlan0"])
    stats = run_wardrive(
        seconds, progress=lambda n, fix: show(
            ["Wardriving...", f"networks: {n}",
             "GPS: " + ("fix" if fix else "no fix (LoRa cap GPS)")]))
    show(["Wardrive done", f"networks: {stats['networks']}",
          f"sightings: {stats['sightings']}",
          "GPS: " + ("had fix" if stats["gps_fix"] else "no fix")])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
