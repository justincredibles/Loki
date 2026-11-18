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
    me = nodes.get(my.my_node_num) or {}
    user = me.get("user") or {}
    return {"my_num": my.my_node_num,
            "my_name": _name(nodes, my.my_node_num),
            "my_short": user.get("shortName") or "",
            "nodes_known": len(nodes)}


def _wait_config(iface) -> None:
    node = iface.localNode
    for _ in range(40):
        if getattr(node, "channels", None):
            return
        time.sleep(0.25)


def _enum_name(field_owner, field: str, value) -> str:
    try:
        desc = field_owner.DESCRIPTOR.fields_by_name[field]
        return desc.enum_type.values_by_number[value].name
    except Exception:
        return str(value)


def _channel_url(iface, settings) -> str | None:
    """The meshtastic.org/e/ share link for one channel."""
    import base64 as b64

    try:
        from meshtastic.protobuf import apponly_pb2

        cs = apponly_pb2.ChannelSet()
        cs.settings.append(settings)
        cs.lora_config.CopyFrom(iface.localNode.localConfig.lora)
        raw = b64.urlsafe_b64encode(
            cs.SerializeToString()).decode().rstrip("=")
        return f"https://meshtastic.org/e/#{raw}"
    except Exception:
        return None


def op_channels(iface) -> dict:
    import base64 as b64

    from meshtastic.protobuf import channel_pb2

    _wait_config(iface)
    node = iface.localNode
    out = []
    for ch in node.channels or []:
        out.append({
            "index": ch.index,
            "role": channel_pb2.Channel.Role.Name(ch.role),
            "name": ch.settings.name,
            "psk": b64.b64encode(ch.settings.psk).decode(),
            "url": _channel_url(iface, ch.settings)
                   if ch.role != channel_pb2.Channel.Role.DISABLED
                   else None,
        })
    lora = node.localConfig.lora
    return {"channels": out,
            "preset": _enum_name(lora, "modem_preset",
                                 lora.modem_preset),
            "region": _enum_name(lora, "region", lora.region)}


def op_setch(iface, spec: dict) -> dict:
    import base64 as b64

    from meshtastic.protobuf import channel_pb2

    _wait_config(iface)
    node = iface.localNode
    idx = int(spec["index"])
    ch = node.channels[idx]
    ch.settings.name = str(spec.get("name", ""))[:11]
    psk = spec.get("psk")
    if psk is not None:
        ch.settings.psk = b64.b64decode(psk) if psk else b""
    if ch.role == channel_pb2.Channel.Role.DISABLED:
        ch.role = channel_pb2.Channel.Role.SECONDARY
    node.writeChannel(idx)
    return {"saved_channel": idx, "note": "node reboots to apply"}


def op_delch(iface, spec: dict) -> dict:
    from meshtastic.protobuf import channel_pb2

    _wait_config(iface)
    node = iface.localNode
    idx = int(spec["index"])
    ch = node.channels[idx]
    ch.role = channel_pb2.Channel.Role.DISABLED
    ch.settings.name = ""
    ch.settings.psk = b""
    node.writeChannel(idx)
    return {"disabled_channel": idx, "note": "node reboots to apply"}


def _field_dump(msg) -> dict:
    """One config section as editor metadata: every scalar field
    with its kind and (for enums) its value names. Nested or
    repeated fields come back 'complex' — shown, not edited."""
    from google.protobuf.descriptor import FieldDescriptor as FD

    out = {}
    for f in msg.DESCRIPTOR.fields:
        entry = {"name": f.name}
        repeated = getattr(f, "is_repeated", None)
        if repeated is None:  # older pure-python protobuf
            repeated = f.label == FD.LABEL_REPEATED
        if repeated or f.type == FD.TYPE_MESSAGE:
            entry["kind"] = "complex"
            try:
                from google.protobuf.json_format import MessageToDict

                entry["value"] = MessageToDict(
                    msg, preserving_proto_field_name=True).get(f.name)
            except Exception:
                entry["value"] = None
        elif f.type == FD.TYPE_BOOL:
            entry.update(kind="bool", value=bool(getattr(msg, f.name)))
        elif f.type == FD.TYPE_ENUM:
            entry.update(kind="enum",
                         value=f.enum_type.values_by_number[
                             getattr(msg, f.name)].name,
                         values=[v.name for v in
                                 f.enum_type.values])
        elif f.type == FD.TYPE_STRING:
            entry.update(kind="string", value=getattr(msg, f.name))
        elif f.type == FD.TYPE_BYTES:
            import base64 as b64

            entry.update(kind="bytes",
                         value=b64.b64encode(
                             getattr(msg, f.name)).decode())
        elif f.type in (FD.TYPE_FLOAT, FD.TYPE_DOUBLE):
            entry.update(kind="float", value=getattr(msg, f.name))
        else:
            entry.update(kind="int", value=int(getattr(msg, f.name)))
        out[f.name] = entry
    return out


def op_config(iface) -> dict:
    from google.protobuf.descriptor import FieldDescriptor as FD

    _wait_config(iface)
    node = iface.localNode
    sections = {}
    for f in node.localConfig.DESCRIPTOR.fields:
        if f.type != FD.TYPE_MESSAGE:
            continue  # e.g. the scalar `version` field
        sections[f.name] = _field_dump(getattr(node.localConfig,
                                               f.name))
    for f in node.moduleConfig.DESCRIPTOR.fields:
        if f.type != FD.TYPE_MESSAGE:
            continue
        sections["mod:" + f.name] = _field_dump(
            getattr(node.moduleConfig, f.name))
    return {"sections": sections}


def op_setconfig(iface, spec: dict) -> dict:
    import base64 as b64

    from google.protobuf.descriptor import FieldDescriptor as FD

    _wait_config(iface)
    node = iface.localNode
    section = str(spec["section"])
    if section.startswith("mod:"):
        cfg = getattr(node.moduleConfig, section[4:])
        write_name = section[4:]
    else:
        cfg = getattr(node.localConfig, section)
        write_name = section
    for name, raw in (spec.get("fields") or {}).items():
        fd = cfg.DESCRIPTOR.fields_by_name[name]
        if fd.type == FD.TYPE_BOOL:
            setattr(cfg, name, raw is True or raw == "true")
        elif fd.type == FD.TYPE_ENUM:
            setattr(cfg, name, fd.enum_type.values_by_name[raw].number)
        elif fd.type in (FD.TYPE_FLOAT, FD.TYPE_DOUBLE):
            setattr(cfg, name, float(raw))
        elif fd.type == FD.TYPE_STRING:
            setattr(cfg, name, str(raw))
        elif fd.type == FD.TYPE_BYTES:
            setattr(cfg, name, b64.b64decode(raw) if raw else b"")
        else:
            setattr(cfg, name, int(raw))
    node.writeConfig(write_name)
    return {"saved_config": section,
            "fields": sorted((spec.get("fields") or {}).keys()),
            "note": "node reboots to apply"}


def op_setname(iface, spec: dict) -> dict:
    _wait_config(iface)
    node = iface.localNode
    node.setOwner(long_name=str(spec["long"]),
                  short_name=str(spec["short"]))
    return {"saved_owner": True, "note": "node reboots to apply"}


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
            elif op == "channels":
                result = op_channels(iface)
            elif op == "setch":
                result = op_setch(iface, json.loads(sys.argv[2]))
            elif op == "delch":
                result = op_delch(iface, json.loads(sys.argv[2]))
            elif op == "setname":
                result = op_setname(iface, json.loads(sys.argv[2]))
            elif op == "config":
                result = op_config(iface)
            elif op == "setconfig":
                result = op_setconfig(iface, json.loads(sys.argv[2]))
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
