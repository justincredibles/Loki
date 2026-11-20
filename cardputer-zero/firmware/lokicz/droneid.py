"""OpenDroneID Wi-Fi decoding (ASTM F3411) — sniffer v2.

v1 flagged drones by BLE service UUID and Wi-Fi OUIs. v2 goes
further: drones broadcasting Remote ID over Wi-Fi put the full
ASTM message set in a vendor-specific beacon IE (element 221,
OUI FA:0B:BC) — Basic ID (serial), Location (the drone's live
lat/lon/altitude/speed), System (the OPERATOR's lat/lon), Self
ID and Operator ID. Decoding them turns a fingerprint hit into
"drone here, pilot there".

Message layouts follow the public ASTM F3411 / OpenDroneID
reference structures (25-byte messages; a pack header carries
several). The parser is pure and unit-tested against synthetic
messages; the capture pass reuses the probe logger's monitor
choreography on the USB dongle and parses the pcap with scapy.

Defensive framing, same as the rest of the sniffer: a decode is
a graded lead from a public broadcast the drone is legally
required to make — not a verdict about anyone.
"""

import struct
import subprocess
import threading
import time
from pathlib import Path

OUI = b"\xfa\x0b\xbc"
MSG_SIZE = 25
CHANNELS = (1, 6, 11, 36, 149, 165)
PCAP = Path("/tmp/lokicz-droneid.pcap")


def _latlon(raw: int) -> float | None:
    return None if raw == 0 else raw / 1e7


def _alt(raw: int) -> float:
    return raw * 0.5 - 1000.0


def _text(raw: bytes) -> str:
    return raw.split(b"\x00")[0].decode("ascii", "replace").strip()


def decode_message(msg: bytes) -> dict | None:
    """One 25-byte OpenDroneID message -> a dict, or None."""
    if len(msg) < MSG_SIZE:
        return None
    mtype = msg[0] >> 4
    if mtype == 0:  # Basic ID
        return {"type": "basic_id",
                "id_type": msg[1] >> 4, "ua_type": msg[1] & 0x0F,
                "id": _text(msg[2:22])}
    if mtype == 1:  # Location / vector
        lat = struct.unpack_from("<i", msg, 5)[0]
        lon = struct.unpack_from("<i", msg, 9)[0]
        direction = msg[2] * 2 + (180 if msg[1] & 0x02 else 0)
        return {"type": "location",
                "lat": _latlon(lat), "lon": _latlon(lon),
                "alt_geo_m": _alt(struct.unpack_from("<H", msg, 15)[0]),
                "height_m": _alt(struct.unpack_from("<H", msg, 17)[0]),
                "direction_deg": direction % 360,
                "speed_ms": msg[3] * 0.25}
    if mtype == 3:  # Self ID
        return {"type": "self_id", "text": _text(msg[2:25])}
    if mtype == 4:  # System (operator position lives here)
        lat = struct.unpack_from("<i", msg, 2)[0]
        lon = struct.unpack_from("<i", msg, 6)[0]
        return {"type": "system",
                "operator_lat": _latlon(lat),
                "operator_lon": _latlon(lon)}
    if mtype == 5:  # Operator ID
        return {"type": "operator_id", "id": _text(msg[2:22])}
    if mtype == 2:
        return {"type": "authentication"}
    return None


def decode_ie(info: bytes) -> list[dict]:
    """A vendor-IE payload (starting at the OUI) -> messages.

    Layout: OUI(3) + OUI-type(1, 0x0D for ODID) + counter(1),
    then one message or a pack (type 0xF: size byte, count
    byte, then count messages)."""
    if len(info) < 5 or info[:3] != OUI:
        return []
    body = info[5:]
    out = []
    if len(body) >= 3 and (body[0] >> 4) == 0x0F:
        size, count = body[1], body[2]
        if size >= MSG_SIZE:
            for i in range(count):
                chunk = body[3 + i * size: 3 + (i + 1) * size]
                decoded = decode_message(chunk[:MSG_SIZE])
                if decoded:
                    out.append(decoded)
            return out
    decoded = decode_message(body[:MSG_SIZE])
    return [decoded] if decoded else out


def _ies_from_pcap(path: Path) -> list[tuple[str, bytes]]:
    """(transmitter MAC, IE payload) pairs from a pcap."""
    from scapy.all import Dot11, Dot11Elt, rdpcap

    found = []
    for pkt in rdpcap(str(path)):
        if not pkt.haslayer(Dot11):
            continue
        mac = pkt[Dot11].addr2 or "?"
        elt = pkt.getlayer(Dot11Elt)
        while elt is not None:
            if elt.ID == 221 and bytes(elt.info)[:3] == OUI:
                found.append((mac, bytes(elt.info)))
            nxt = elt.payload
            elt = nxt if isinstance(nxt, Dot11Elt) else None
    return found


def summarize(ies: list[tuple[str, bytes]]) -> list[dict]:
    """Group decoded messages per drone (by transmitter MAC)."""
    drones: dict[str, dict] = {}
    for mac, info in ies:
        drone = drones.setdefault(
            mac, {"mac": mac, "id": None, "lat": None, "lon": None,
                  "alt_geo_m": None, "height_m": None,
                  "operator_lat": None, "operator_lon": None,
                  "operator_id": None, "self_id": None,
                  "messages": 0})
        for msg in decode_ie(info):
            drone["messages"] += 1
            kind = msg["type"]
            if kind == "basic_id":
                drone["id"] = msg["id"]
            elif kind == "location":
                drone.update({k: msg[k] for k in
                              ("lat", "lon", "alt_geo_m", "height_m")
                              if msg.get(k) is not None})
            elif kind == "system":
                drone.update({k: msg[k] for k in
                              ("operator_lat", "operator_lon")
                              if msg.get(k) is not None})
            elif kind == "operator_id":
                drone["id"] = drone["id"] or msg["id"]
                drone["operator_id"] = msg["id"]
            elif kind == "self_id":
                drone["self_id"] = msg["text"]
    return [d for d in drones.values() if d["messages"]]


def capture(seconds: int = 24,
            iface: str = "wlan1", stop_check=None) -> list[dict]:
    """Monitor-listen for DroneID Wi-Fi broadcasts; decode them.

    Same release/restore choreography as the probe logger.
    `stop_check` ends the listen early: tshark is terminated,
    whatever landed in the pcap still gets decoded, and the
    finally-restore returns the dongle to managed mode."""
    from . import capture as capture_mod

    capture_mod._release(iface)
    stop = threading.Event()

    def hop() -> None:
        idx = 0
        while not stop.is_set():
            subprocess.run(["sudo", "iw", "dev", iface, "set",
                            "channel", str(CHANNELS[idx % len(CHANNELS)])],
                           capture_output=True)
            idx += 1
            stop.wait(1.2)

    try:
        subprocess.run(["sudo", "iw", "dev", iface, "set", "type",
                        "monitor"], capture_output=True)
        hopper = threading.Thread(target=hop, daemon=True)
        hopper.start()
        proc = subprocess.Popen(
            ["sudo", "timeout", str(seconds), "tshark",
             "-i", iface, "-w", str(PCAP), "-q"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + seconds + 5
        while proc.poll() is None and time.time() < deadline:
            if stop_check and stop_check():
                proc.terminate()
                break
            time.sleep(0.25)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        stop.set()
        hopper.join(timeout=3)
    finally:
        capture_mod._restore(iface)
    if not PCAP.exists():
        return []
    return summarize(_ies_from_pcap(PCAP))
