"""Flight radar — aircraft overhead, on a pocket scope.

Two ways exist to track aircraft: receive their ADS-B broadcasts
yourself (1090 MHz — needs an RTL-SDR; neither cap tunes up there),
or ask the network that already does. This module does the second:
it polls the free adsb.lol feed for traffic around where you are
and reduces it to what a radar screen wants — callsign, altitude,
speed, distance and bearing from you, nearest first.

Where "you" are is resolved GPS-first: when the LoRa cap is the
fitted profile, its GPS supplies the position (a shared NMEA
reader, so the port isn't reopened per call). Without a fix, the
configured home point is the fallback. Home coordinates live ONLY
in the device's local config (home_lat / home_lon) — never in
this repo — and GPS fixes are runtime values, never stored.
"""

import json
import math
import time
import urllib.request

API = "https://api.adsb.lol/v2/lat/{lat:.4f}/lon/{lon:.4f}/dist/{dist}"
CACHE_S = 20
GPS_WAIT_S = 6.0

_cache = {"at": 0.0, "key": None, "data": None}
_reader = None


def _shared_reader():
    """The process-wide GPS reader, started on first use."""
    global _reader
    if _reader is None:
        from .wardrive import GpsReader

        _reader = GpsReader()
        _reader.start()
    return _reader


def gps_fix(cfg: dict, wait_s: float = GPS_WAIT_S):
    """Latest GPS fix dict {lat, lon, alt, sats}, or None.

    Only attempted under the LoRa cap profile — that's the cap
    carrying the GPS. Waits up to `wait_s` for a first fix; a fix
    the shared reader already holds returns at once.
    """
    if cfg.get("cap") != "lora":
        return None
    try:
        reader = _shared_reader()
    except Exception:
        return None
    deadline = time.time() + wait_s
    while True:
        fix = reader.fix
        if fix and fix.get("lat") is not None:
            return fix
        if time.time() >= deadline:
            return None
        time.sleep(0.25)


def locate(cfg: dict):
    """Where the radar centers: GPS first, configured home second.

    Returns {"lat", "lon", "source"} (+"sats" for GPS), or None.
    """
    fix = gps_fix(cfg)
    if fix:
        return {"lat": fix["lat"], "lon": fix["lon"],
                "source": "gps", "sats": fix.get("sats")}
    h = home(cfg)
    if h is not None:
        return {"lat": h[0], "lon": h[1], "source": "home"}
    return None


def _dist_bearing_nm(lat1, lon1, lat2, lon2) -> tuple[float, float]:
    """Great-circle distance (nm) and initial bearing (deg)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    dp = p2 - p1
    a = math.sin(dp / 2) ** 2 \
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    dist_km = 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) \
        - math.sin(p1) * math.cos(p2) * math.cos(dl)
    brg = (math.degrees(math.atan2(y, x)) + 360) % 360
    return dist_km * 0.539957, brg


def home(cfg: dict):
    """(lat, lon) from config, or None when unset."""
    lat, lon = cfg.get("home_lat"), cfg.get("home_lon")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) \
            and (lat or lon):
        return float(lat), float(lon)
    return None


def nearest(cfg: dict, limit: int = 12) -> dict:
    """Nearest aircraft to the resolved center (GPS, else home).

    {ok, center, aircraft:[...]} or a reason. Aircraft carry
    their own lat/lon so the portal can plot them on a map.
    """
    center = locate(cfg)
    if center is None:
        return {"ok": False,
                "reason": "no GPS fix and no home location set"}
    lat, lon = center["lat"], center["lon"]
    radius = int(cfg.get("flight_radius_nm", 30))
    key = (round(lat, 3), round(lon, 3), radius)
    now = time.time()
    if _cache["data"] is not None and _cache["key"] == key \
            and now - _cache["at"] < CACHE_S:
        return _cache["data"]

    url = API.format(lat=lat, lon=lon, dist=radius)
    req = urllib.request.Request(
        url, headers={"User-Agent": "lokicz-flight-radar"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            feed = json.loads(resp.read().decode())
    except (OSError, ValueError) as exc:
        return {"ok": False, "reason": f"feed unreachable: {exc}"}

    out = []
    for ac in feed.get("ac", []):
        if ac.get("lat") is None or ac.get("lon") is None:
            continue
        dist, brg = _dist_bearing_nm(lat, lon, ac["lat"], ac["lon"])
        alt = ac.get("alt_baro")
        out.append({
            "hex": ac.get("hex", ""),
            "callsign": (ac.get("flight") or ac.get("r")
                         or ac.get("hex", "")).strip(),
            "type": ac.get("t", ""),
            "alt_ft": alt if isinstance(alt, (int, float)) else None,
            "on_ground": alt == "ground",
            "speed_kt": ac.get("gs"),
            "track": ac.get("track"),
            "vrate_fpm": ac.get("baro_rate"),
            "squawk": ac.get("squawk", ""),
            "lat": ac["lat"],
            "lon": ac["lon"],
            "dist_nm": round(dist, 1),
            "bearing": round(brg),
        })
    out.sort(key=lambda a: a["dist_nm"])
    data = {"ok": True, "center": center,
            "home": {"lat": lat, "lon": lon},
            "radius_nm": radius, "total": feed.get("total",
                                                   len(out)),
            "aircraft": out[:limit]}
    _cache.update(at=now, key=key, data=data)
    return data


if __name__ == "__main__":
    from . import config

    r = nearest(config.load())
    if not r["ok"]:
        print("unavailable:", r["reason"])
    else:
        print(f"{r['total']} aircraft within {r['radius_nm']} nm "
              f"of {r['center']['source']} "
              f"({r['center']['lat']:.4f}, {r['center']['lon']:.4f})")
        for a in r["aircraft"]:
            alt = "GND" if a["on_ground"] else f"{a['alt_ft']} ft"
            print(f"  {a['callsign']:<9} {a['type']:<5} {alt:>9} "
                  f"{a['dist_nm']:>5} nm @ {a['bearing']:>3}° "
                  f"{a['speed_kt']} kt")
