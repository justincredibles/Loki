"""Always-on Meshtastic text logger — the chat history keeper.

Meshtastic keeps no browsable message history: meshtasticd hands
each text to connected clients as it arrives and then it's gone.
This daemon stays subscribed to the local API and appends every
TEXT_MESSAGE_APP packet to ~/lokicz-meshlog/messages.jsonl so the
portal can show the primary-channel conversation (and DMs).

Run under the meshtastic-cli venv python (it has the client lib):
    python3 -m lokicz.mesh_log

Behaviour notes:
- Packets from our own node are skipped — the send path logs
  outgoing texts itself (meshchat.send), so nothing doubles up.
- Relay duplicates are dropped by packet id (last 512 kept).
- When meshtasticd is down (mesh off, MeshCore mode, mid-reboot)
  the connect loop just retries quietly; a heartbeat file is
  touched every cycle so the portal can say whether history is
  currently being collected.
"""

from __future__ import annotations

import json
import sys
import time
from collections import OrderedDict
from pathlib import Path

# Same sys.path guard as mesh_api.py: this package has its own
# meshtastic.py; the real client lib must win the import.
sys.path = [p for p in sys.path
            if not p.replace("\\", "/").rstrip("/").endswith("lokicz")]

LOG_DIR = Path.home() / "lokicz-meshlog"
LOG_FILE = LOG_DIR / "messages.jsonl"
HEARTBEAT = LOG_DIR / "heartbeat"
BROADCAST = 4294967295
MAX_KEEP = 3000

_seen: "OrderedDict[int, None]" = OrderedDict()
_state = {"own_num": None, "iface": None, "dead": False}


def _append(record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as fh:
        fh.write(json.dumps(record) + "\n")


def _trim() -> None:
    try:
        lines = LOG_FILE.read_text().splitlines()
    except OSError:
        return
    if len(lines) > MAX_KEEP + 1000:
        LOG_FILE.write_text("\n".join(lines[-MAX_KEEP:]) + "\n")


def _name(iface, num: int) -> str:
    try:
        node = (iface.nodes or {}).get(f"!{num:08x}") or {}
        user = node.get("user") or {}
        return user.get("longName") or f"!{num:08x}"
    except Exception:
        return f"!{num:08x}"


def _on_receive(packet, interface=None) -> None:
    try:
        decoded = packet.get("decoded") or {}
        if decoded.get("portnum") != "TEXT_MESSAGE_APP":
            return
        from_num = packet.get("from")
        if from_num is None or from_num == _state["own_num"]:
            return  # our own sends are logged by the send path
        pid = packet.get("id")
        if pid is not None:
            if pid in _seen:
                return
            _seen[pid] = None
            while len(_seen) > 512:
                _seen.popitem(last=False)
        payload = decoded.get("payload") or b""
        if isinstance(payload, str):
            text = payload
        else:
            text = bytes(payload).decode("utf-8", "replace")
        to_num = packet.get("to") or 0
        _append({
            "ts": int(packet.get("rxTime") or time.time()),
            "from": from_num,
            "from_name": _name(interface or _state["iface"], from_num),
            "to": to_num,
            "dm": to_num != BROADCAST,
            "channel": packet.get("channel") or 0,
            "text": text,
            "rssi": packet.get("rxRssi"),
            "snr": packet.get("rxSnr"),
        })
    except Exception:
        pass  # a bad packet must never kill the logger


def _on_lost(*_args) -> None:
    _state["dead"] = True


def _connect():
    import meshtastic.tcp_interface
    from pubsub import pub

    iface = meshtastic.tcp_interface.TCPInterface(
        hostname="127.0.0.1")
    for _ in range(40):
        if getattr(iface, "myInfo", None):
            break
        time.sleep(0.25)
    _state["iface"] = iface
    _state["own_num"] = iface.myInfo.my_node_num
    _state["dead"] = False
    pub.subscribe(_on_receive, "meshtastic.receive")
    pub.subscribe(_on_lost, "meshtastic.connection.lost")
    return iface


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _trim()
    while True:
        iface = None
        try:
            iface = _connect()
            print(f"mesh_log: connected, own num "
                  f"{_state['own_num']}", flush=True)
            while not _state["dead"]:
                HEARTBEAT.touch()
                time.sleep(20)
        except Exception as exc:
            print(f"mesh_log: {exc!r} — retrying", flush=True)
        finally:
            if iface is not None:
                try:
                    iface.close()
                except Exception:
                    pass
        time.sleep(10)


if __name__ == "__main__":
    main()
