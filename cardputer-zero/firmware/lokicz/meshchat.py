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


def _revive_daemon() -> None:
    """Config writes reboot the node; on portduino that exits
    meshtasticd and systemd may leave it down. Bring it back."""
    import subprocess as sp
    import time

    from . import meshtastic

    for _ in range(10):
        if meshtastic.service_active():
            return
        sp.run("sudo -n systemctl start meshtasticd", shell=True,
               capture_output=True, timeout=20)
        time.sleep(3)


def info(cfg: dict) -> dict:
    return _call(cfg, ["info"], timeout=30)


def channels(cfg: dict) -> dict:
    return _call(cfg, ["channels"], timeout=40)


def set_channel(cfg: dict, index: int, name: str,
                psk_b64: str | None) -> dict:
    import json as _json

    if not 0 <= int(index) <= 7:
        raise RuntimeError("channel slot must be 0–7")
    spec = {"index": int(index), "name": (name or "").strip(),
            "psk": psk_b64}
    out = _call(cfg, ["setch", _json.dumps(spec)], timeout=60)
    _revive_daemon()
    return out


def del_channel(cfg: dict, index: int) -> dict:
    import json as _json

    if int(index) == 0:
        raise RuntimeError("the primary channel (slot 0) can't be "
                           "disabled — edit it instead")
    if not 1 <= int(index) <= 7:
        raise RuntimeError("channel slot must be 1–7")
    out = _call(cfg, ["delch", _json.dumps({"index": int(index)})],
                timeout=60)
    _revive_daemon()
    return out


def set_name(cfg: dict, long_name: str, short_name: str) -> dict:
    import json as _json

    long_name = (long_name or "").strip()
    short_name = (short_name or "").strip()
    if not long_name:
        raise RuntimeError("long name can't be empty")
    if not 1 <= len(short_name) <= 4:
        raise RuntimeError("short name must be 1–4 characters "
                           "(Meshtastic rule)")
    spec = {"long": long_name, "short": short_name}
    out = _call(cfg, ["setname", _json.dumps(spec)], timeout=60)
    _revive_daemon()
    return out


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
