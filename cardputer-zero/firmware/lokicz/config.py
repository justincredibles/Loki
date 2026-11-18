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
    return cfg


def save(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")
