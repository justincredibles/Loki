"""Mesh chat + node queries for the portal — the system-side
half. All Meshtastic client work happens in mesh_api.py under
the CLI venv's python (the library lives there); this module
guards and shells out.

Guards, in order: the LoRa cap must be fitted, the configured
mesh mode must be Meshtastic, and meshtasticd's API must be
answering. Anything else is a clear sentence, not a traceback.
MeshCore has no chat here by design: it runs as an openHop
repeater (it relays other nodes; messaging lives in companion
apps) and its dashboard is on :8000.
"""

import json
import subprocess
from pathlib import Path

VENV_PY = Path.home() / "meshtastic-cli" / "bin" / "python"
SCRIPT = Path(__file__).with_name("mesh_api.py")


def guard(cfg: dict) -> str | None:
    """None when Meshtastic chat is live, else why it isn't."""
    if cfg.get("cap") != "lora":
        return ("the LoRa cap is not fitted — mesh is dormant "
                "with the CC1101 cap in. Swap caps to bring "
                "Meshtastic up.")
    mode = cfg.get("mesh_mode", "meshtastic")
    if mode != "meshtastic":
        return (f"mesh mode is '{mode}' — chat needs Meshtastic "
                "mode (MeshCore is a repeater; see its dashboard)")
    from . import meshtastic

    if not meshtastic.api_up():
        return "meshtasticd's API (127.0.0.1:4403) is not answering"
    return None


def _call(cfg: dict, args: list[str], timeout: int) -> dict:
    why = guard(cfg)
    if why:
        raise RuntimeError(why)
    r = subprocess.run([str(VENV_PY), str(SCRIPT), *args],
                       capture_output=True, text=True,
                       timeout=timeout)
    for line in reversed(r.stdout.strip().splitlines()):
        try:
            out = json.loads(line)
            break
        except ValueError:
            continue
    else:
        raise RuntimeError("mesh helper returned nothing usable: "
                           + (r.stderr.strip()[-200:] or r.stdout[-200:]))
    if out.get("error"):
        raise RuntimeError(out["error"])
    return out


def info(cfg: dict) -> dict:
    return _call(cfg, ["info"], timeout=30)


def nodes(cfg: dict) -> dict:
    return _call(cfg, ["nodes"], timeout=40)


def send(cfg: dict, text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise RuntimeError("empty message")
    if len(text) > 200:
        raise RuntimeError("message too long (200 chars max — a "
                           "mesh packet is ~237 bytes)")
    return _call(cfg, ["send", text], timeout=40)


def listen(cfg: dict, seconds: int) -> dict:
    seconds = max(10, min(int(seconds or 30), 120))
    return _call(cfg, ["listen", str(seconds)], timeout=seconds + 40)
