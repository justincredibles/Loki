"""Proximity radar — the 'person radar'.

Honest physics first: with one antenna you cannot measure the
*bearing* of a radio. What you can measure is how loud it is —
and on a scope, loud means close. This radar listens passively
to BLE advertisements for a window, estimates each device's
range from its RSSI, and plots it on the radar scope: radius is
real (signal-derived), angle is a stable per-device slot (a hash
of its address, so a device always sits at the same bearing and
you can watch it drift in and out). In practice the blips are
phones, watches, earbuds and trackers — which is to say, people.

Range model: free-space-ish, d = 10^((−59 − RSSI) / 20) metres,
the usual 1 m reference for BLE. Walls and pockets lie; treat
the number as 'about this far', not surveying.
"""

import hashlib

from . import sniffer

_KIND_HINTS = (
    ("watch", ("watch", "galaxy watch")),
    ("earbuds", ("airpods", "buds", "pods")),
    ("phone", ("iphone", "galaxy", "pixel", "phone")),
    ("tag", ("airtag", "smarttag", "tile")),
    ("tv", ("tv", "roku", "fire tv", "chromecast")),
    ("speaker", ("echo", "homepod", "speaker", "sonos")),
    ("computer", ("macbook", "laptop", "imac", "desktop")),
)


def classify(name: str, uuids: list) -> str:
    low = (name or "").lower()
    for kind, needles in _KIND_HINTS:
        if any(n in low for n in needles):
            return kind
    return "device"


def est_meters(rssi: int) -> float:
    d = 10 ** ((-59 - rssi) / 20.0)
    return round(max(0.3, min(d, 40.0)), 1)


def scope_frac(rssi: int) -> float:
    """RSSI → scope radius fraction: −40 dBm is on top of you,
    −95 dBm is the rim."""
    return round(max(0.07, min(1.0, (-rssi - 40) / 55.0)), 2)


def slot_bearing(address: str) -> int:
    """Stable pseudo-bearing for a device (NOT a direction —
    a fixed slot so the blip is recognisable between scans)."""
    digest = hashlib.md5(address.encode()).hexdigest()
    return int(digest[:4], 16) % 360


def scan(seconds: int = 25) -> dict:
    devices, method = sniffer.scan_ble(seconds)
    out = []
    for dev in devices:
        if not dev["rssi"]:
            continue  # heard of, never heard — no range estimate
        out.append({
            "address": dev["address"],
            "name": dev["name"] or dev["address"][-8:],
            "kind": classify(dev["name"], dev["uuids"]),
            "rssi": dev["rssi"],
            "meters": est_meters(dev["rssi"]),
            "frac": scope_frac(dev["rssi"]),
            "bearing": slot_bearing(dev["address"]),
        })
    out.sort(key=lambda d: d["rssi"], reverse=True)
    return {"devices": out, "count": len(out), "method": method,
            "seconds": seconds,
            "spam_suspects": spam_suspects(out)}


# BLE spam (the Flipper trick) floods phones with pairing
# popups by advertising the same product name from many
# rapidly-rotating addresses. One name from >=4 distinct
# addresses in a single scan is that signature — a real
# household rarely fields four of the same gadget at once.
_BAIT = ("airpod", "beats", "apple tv", "appletv",
         "galaxy buds", "galaxy watch", "pixel buds",
         "swift pair", "fast pair")


def spam_suspects(devices: list[dict]) -> list[dict]:
    by_name: dict[str, set] = {}
    for dev in devices:
        low = (dev.get("name") or "").lower()
        if any(b in low for b in _BAIT):
            by_name.setdefault(dev["name"], set()).add(
                dev["address"])
    return [{"name": name, "addresses": len(addrs)}
            for name, addrs in by_name.items()
            if len(addrs) >= 4]


if __name__ == "__main__":
    r = scan()
    print(f"{r['count']} devices ({r['method']})")
    for d in r["devices"]:
        print(f"  {d['name']:<22} {d['kind']:<8} {d['rssi']:>4} dBm "
              f"~{d['meters']} m")
