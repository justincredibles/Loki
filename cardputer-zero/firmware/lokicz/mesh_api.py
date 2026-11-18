"""Meshtastic API helper — runs under the meshtastic CLI venv
python (~/meshtastic-cli), NOT the system python: the daemon's
client library lives there. lokicz/meshchat.py shells out to
this file; it talks to meshtasticd on 127.0.0.1:4403 and prints
exactly one JSON object on the last stdout line.

Usage: mesh_api.py info | nodes | send <text> | listen <secs>
"""

import json
import sys
import time
from pathlib import Path

# This file lives inside the lokicz package, next to lokicz's own
# meshtastic.py supervisor module. Python puts the script's
# directory first on sys.path, which would shadow the venv's
# real `meshtastic` package with that module — remove it.
_HERE = str(Path(__file__).resolve().parent)
sys.path = [p for p in sys.path
            if str(Path(p or ".").resolve()) != _HERE]


def _iface():
    from meshtastic.tcp_interface import TCPInterface

    iface = TCPInterface(hostname="127.0.0.1")
    for _ in range(40):  # the node DB syncs in the background
        if getattr(iface, "myInfo", None):
            break
        time.sleep(0.25)
    return iface


def _nodes(iface) -> dict:
    by_num = getattr(iface, "nodesByNum", None)
    if by_num:
        return dict(by_num)
    out = {}
    for node in (getattr(iface, "nodes", None) or {}).values():
        num = node.get("num")
        if num is not None:
            out[num] = node
    return out


def _name(nodes: dict, num) -> str:
    node = nodes.get(num) or {}
    user = node.get("user") or {}
    return user.get("longName") or user.get("id") or f"!{num:08x}"


def op_info(iface) -> dict:
    nodes = _nodes(iface)
    my = iface.myInfo
    return {"my_num": my.my_node_num,
            "my_name": _name(nodes, my.my_node_num),
            "nodes_known": len(nodes)}


def op_nodes(iface) -> dict:
    rows = []
    for num, node in _nodes(iface).items():
        user = node.get("user") or {}
        pos = node.get("position") or {}
        rows.append({
            "num": num,
            "name": user.get("longName") or user.get("id")
                    or f"!{num:08x}",
            "short": user.get("shortName") or "",
            "last_heard": node.get("lastHeard"),
            "snr": node.get("snr"),
            "hops": node.get("hopsAway"),
            "lat": pos.get("latitude"),
            "lon": pos.get("longitude"),
        })
    rows.sort(key=lambda r: -(r["last_heard"] or 0))
    return {"nodes": rows[:40]}


def op_send(iface, text: str) -> dict:
    iface.sendText(text)
    time.sleep(2)  # let the packet queue onto the radio
    return {"sent": True, "text": text}


def op_listen(iface, seconds: int) -> dict:
    from pubsub import pub

    found = []

    def on_receive(packet, interface):  # noqa: ANN001 - pubsub
        try:
            decoded = packet.get("decoded") or {}
            if decoded.get("portnum") != "TEXT_MESSAGE_APP":
                return
            text = decoded.get("text")
            if text is None:
                payload = decoded.get("payload") or b""
                text = payload.decode("utf-8", "replace")
            nodes = _nodes(interface)
            found.append({
                "from_num": packet.get("from"),
                "from_name": _name(nodes, packet.get("from")),
                "text": text,
                "rx_time": packet.get("rxTime"),
                "rssi": packet.get("rxRssi"),
                "snr": packet.get("rxSnr"),
            })
        except Exception:
            pass

    pub.subscribe(on_receive, "meshtastic.receive")
    try:
        time.sleep(seconds)
    finally:
        pub.unsubscribe(on_receive, "meshtastic.receive")
    return {"messages": found, "seconds": seconds}


def main() -> int:
    op = sys.argv[1] if len(sys.argv) > 1 else "info"
    try:
        iface = _iface()
        try:
            if op == "nodes":
                result = op_nodes(iface)
            elif op == "send":
                result = op_send(iface, sys.argv[2])
            elif op == "listen":
                secs = max(5, min(int(sys.argv[2]), 120))
                result = op_listen(iface, secs)
            else:
                result = op_info(iface)
        finally:
            iface.close()
    except Exception as exc:  # surface, don't traceback
        result = {"error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
