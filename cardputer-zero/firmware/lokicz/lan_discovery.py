"""Broadcast discovery — what devices SAY they are.

nmap tells you what's open; SSDP/UPnP and mDNS tell you what a
device calls itself. This module listens on both:

- SSDP: an M-SEARCH to 239.255.255.250:1900 — UPnP devices
  answer with their server string, service type and a LOCATION
  URL for the full device description.
- mDNS: PTR queries to 224.0.0.251:5353 for the common service
  types (http, ssh, AirPlay, Google Cast, printers, SMB...);
  instances resolve PTR -> SRV -> A down to an IP.

audit.run_audit folds the results into each host's 'discovery'
field. Everything is stdlib, passive (two well-formed multicast
queries), and failure-isolated: if discovery breaks, the audit
continues without it.
"""

import socket
import struct
import time

SSDP_ADDR = ("239.255.255.250", 1900)
MDNS_ADDR = ("224.0.0.251", 5353)
MDNS_SERVICES = ("_http._tcp.local", "_ssh._tcp.local",
                 "_airplay._tcp.local", "_googlecast._tcp.local",
                 "_printer._tcp.local", "_smb._tcp.local",
                 "_device-info._tcp.local")


def ssdp_scan(seconds: int = 5) -> dict:
    """ip -> {'ssdp': [{server, st, location}]} from responses."""
    found: dict[str, dict] = {}
    msg = ("M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\n"
           'MAN: "ssdp:discover"\r\nMX: 3\r\nST: ssdp:all\r\n\r\n')
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                         socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(0.5)
        sock.sendto(msg.encode(), SSDP_ADDR)
        end = time.time() + seconds
        while time.time() < end:
            try:
                data, (ip, _) = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            headers = {}
            for line in data.decode("utf-8", "replace").split("\r\n"):
                if ": " in line:
                    k, v = line.split(": ", 1)
                    headers[k.lower()] = v
            entry = found.setdefault(ip, {"ssdp": []})
            item = {"server": headers.get("server", ""),
                    "st": headers.get("st", ""),
                    "location": headers.get("location", "")}
            if item not in entry["ssdp"]:
                entry["ssdp"].append(item)
    finally:
        sock.close()
    return found


def _dns_name(name: str) -> bytes:
    out = b""
    for part in name.rstrip(".").split("."):
        out += bytes([len(part)]) + part.encode()
    return out + b"\x00"


def _read_name(pkt: bytes, off: int) -> tuple[str, int]:
    labels, jumped, end = [], False, off
    guard = 0
    while off < len(pkt) and guard < 64:
        guard += 1
        ln = pkt[off]
        if ln == 0:
            if not jumped:
                end = off + 1
            break
        if ln & 0xC0 == 0xC0:
            ptr = ((ln & 0x3F) << 8) | pkt[off + 1]
            if not jumped:
                end = off + 2
            sub, _ = _read_name(pkt, ptr)
            labels.append(sub)
            jumped = True
            break
        labels.append(pkt[off + 1:off + 1 + ln].decode("utf-8",
                                                       "replace"))
        off += 1 + ln
    return ".".join(x for x in labels if x), end


def _parse_mdns(pkt: bytes, instances: dict, srv_map: dict,
                a_map: dict) -> None:
    """Fold one mDNS packet into the join tables:
    instances {service: [instance]}, srv_map {instance: host},
    a_map {host: ip}."""
    try:
        qd, an, ns, ar = struct.unpack(">HHHH", pkt[4:12])
    except struct.error:
        return
    off = 12
    try:
        for _ in range(qd):
            _, off = _read_name(pkt, off)
            off += 4
        for _ in range(an + ns + ar):
            name, off = _read_name(pkt, off)
            rtype, _cls, _ttl, rdlen = struct.unpack(
                ">HHIH", pkt[off:off + 10])
            off += 10
            rdata = off
            if rtype == 12:  # PTR: service -> instance
                target, _ = _read_name(pkt, rdata)
                instances.setdefault(name, [])
                if target not in instances[name]:
                    instances[name].append(target)
            elif rtype == 33:  # SRV: instance -> host
                target, _ = _read_name(pkt, rdata + 6)
                srv_map[name] = target
            elif rtype == 1:  # A: host -> ip
                a_map[name] = socket.inet_ntoa(pkt[rdata:rdata + 4])
            off += rdlen
    except (struct.error, IndexError):
        return


def mdns_scan(seconds: int = 5) -> dict:
    """ip -> {'mdns_services': ['airplay: Living Room', ...]}."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                         socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", 5353))
        sock.setsockopt(socket.IPPROTO_IP,
                        socket.IP_ADD_MEMBERSHIP,
                        socket.inet_aton("224.0.0.251") +
                        socket.inet_aton("0.0.0.0"))
        sock.settimeout(0.5)
    except OSError:
        sock.close()
        return {}
    instances: dict[str, list] = {}
    srv_map: dict[str, str] = {}
    a_map: dict[str, str] = {}
    try:
        for svc in MDNS_SERVICES:
            query = struct.pack(">HHHHHH", 0, 0, 1, 0, 0, 0) \
                + _dns_name(svc) + struct.pack(">HH", 12, 1)
            sock.sendto(query, MDNS_ADDR)
        end = time.time() + seconds
        while time.time() < end:
            try:
                data, _ = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            _parse_mdns(data, instances, srv_map, a_map)
    finally:
        sock.close()
    out: dict[str, dict] = {}
    for svc, insts in instances.items():
        kind = svc.split(".")[0].lstrip("_")
        for inst in insts:
            host = srv_map.get(inst)
            ip = a_map.get(host) if host else None
            if not ip:
                continue  # unresolved instance — drop, don't guess
            label = f"{kind}: {inst.split('.')[0]}"
            entry = out.setdefault(ip, {"mdns_services": []})
            if label not in entry["mdns_services"]:
                entry["mdns_services"].append(label)
    return out


def enrich(hosts: list[dict]) -> None:
    """Attach SSDP/mDNS discovery to audit host dicts, in place."""
    found: dict[str, dict] = {}
    for source in (ssdp_scan, mdns_scan):
        try:
            for ip, info in source().items():
                merged = found.setdefault(ip, {})
                for key, val in info.items():
                    if isinstance(val, list):
                        merged.setdefault(key, [])
                        for item in val:
                            if item not in merged[key]:
                                merged[key].append(item)
                    else:
                        merged[key] = val
        except Exception:
            continue
    for host in hosts:
        info = found.get(host["ip"])
        if info:
            host["discovery"] = info
