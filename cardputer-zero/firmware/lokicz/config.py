"""lokicz configuration — one small JSON file, sensible defaults.

Lives at ~/.config/lokicz/config.json on the device. Anything the
file omits falls back to the defaults below; the environment
variables LOKICZ_CAP and LOKICZ_CAPTURE_IFACE still win when set
(handy for one-off runs from a shell).
"""

import json
import os
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "lokicz" / "config.json"

DEFAULTS = {
    "cap": "cc1101",            # fitted cap profile: cc1101 | lora | none
    "capture_iface": "wlan1",   # USB dongle used for monitor capture
    "capture_seconds": 90,      # default capture run length
    "wardrive_seconds": 300,    # default wardriving session length
    "sniff_seconds": 120,       # default surveillance-sniff length
    "mesh_mode": "meshtastic",  # LoRa cap owner: meshtastic | meshcore | off
    # Master toggle for handshake capture (menu key 8). When off,
    # the Capture action refuses to run — nothing is captured and
    # nothing is uploaded, automatically or otherwise.
    "capture_enabled": True,
    # WPA-SEC addon (menu key 9): uploads new captures to
    # wpa-sec.stanev.org and downloads cracked passwords. Off by
    # default; needs an API key (wpasec_key below, or the
    # LOKICZ_WPASEC_KEY environment variable) before it can sync.
    "wpasec_enabled": False,
    "wpasec_key": "",
    # Network audit (Bjorn-style): the subnet to audit; "" means
    # "the /24 (or so) this device is sitting on". nvd_api_key is
    # optional — without one the NVD allows ~5 requests per 30 s
    # and lokicz paces itself; a free key from nvd.nist.gov lifts
    # that to 50 per 30 s.
    "audit_subnet": "",
    "nvd_api_key": "",
    # Flight radar home point. Deliberately null here: real
    # coordinates belong ONLY in the device's local config file,
    # never in this (public) repo.
    "home_lat": None,
    "home_lon": None,
    "flight_radius_nm": 30,
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text()))
    except (OSError, ValueError):
        pass  # no file yet, or a corrupt one — defaults carry us
    if os.environ.get("LOKICZ_CAP"):
        cfg["cap"] = os.environ["LOKICZ_CAP"]
    if os.environ.get("LOKICZ_CAPTURE_IFACE"):
        cfg["capture_iface"] = os.environ["LOKICZ_CAPTURE_IFACE"]
    if os.environ.get("LOKICZ_WPASEC_KEY"):
        cfg["wpasec_key"] = os.environ["LOKICZ_WPASEC_KEY"]
    return cfg


def save(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")
