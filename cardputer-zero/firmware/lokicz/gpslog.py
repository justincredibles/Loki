"""GPS track logger — GPX tracks from the LoRa cap's GPS.

Samples the cap's GP-02 receiver (via wardrive's NMEA reader)
once a second for the chosen window and writes a standard GPX
1.1 track to ~/lokicz-tracks/ — openable in any mapping tool —
plus a JSON sidecar summary for the portal.

Points are recorded when the position has moved ~2 m or 5 s
have passed, so a stationary device doesn't write 120 copies of
the same dot. Distance is the haversine sum over the track.

Honest as ever: indoors the receiver hears satellites but gets
no fix (GGA quality 0) — then the track is empty and the result
says NO FIX, NEED SKY rather than inventing a position.
"""

import json
import math
import time
from pathlib import Path

from . import wardrive

TRACK_DIR = Path.home() / "lokicz-tracks"


def _haversine_m(a: dict, b: dict) -> float:
    r = 6371000.0
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    dp = math.radians(b["lat"] - a["lat"])
    dl = math.radians(b["lon"] - a["lon"])
    h = math.sin(dp / 2) ** 2 \
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _write_gpx(points: list[dict], path: Path, stamp: str) -> None:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<gpx version="1.1" creator="lokicz" '
             'xmlns="http://www.topografix.com/GPX/1/1">',
             f"<metadata><name>lokicz track {stamp}</name>"
             f"<time>{_iso(points[0]['t']) if points else _iso(time.time())}"
             "</time></metadata>",
             "<trk><name>lokicz track</name><trkseg>"]
    for p in points:
        lines.append(
            f'<trkpt lat="{p["lat"]:.6f}" lon="{p["lon"]:.6f}">'
            f"<ele>{p['alt']:.1f}</ele><time>{_iso(p['t'])}</time>"
            "</trkpt>")
    lines.append("</trkseg></trk></gpx>")
    path.write_text("\n".join(lines) + "\n")


def _iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def track(seconds: int = 120, progress=lambda msg: None,
          stop_check=None) -> dict:
    """Record a track for `seconds`.

    `stop_check` (a callable returning True) ends the run early:
    the track is finalized exactly as on a natural finish — same
    GPX + JSON sidecar — with the points gathered so far and the
    actual elapsed seconds. The portal passes no stop_check and
    always gets the full window.
    """
    TRACK_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    reader = wardrive.GpsReader()
    reader.start()
    points: list[dict] = []
    distance = 0.0
    max_sats = 0
    last_recorded = 0.0
    t0 = time.time()
    end = t0 + seconds
    stopped = False
    while time.time() < end:
        if stop_check and stop_check():
            stopped = True
            break
        fix = reader.fix
        if fix:
            max_sats = max(max_sats, fix.get("sats", 0))
            now = time.time()
            moved = not points or _haversine_m(points[-1], fix) >= 2.0
            if moved or now - last_recorded >= 5:
                if points:
                    distance += _haversine_m(points[-1], fix)
                points.append({"lat": fix["lat"], "lon": fix["lon"],
                               "alt": fix.get("alt", 0.0), "t": now})
                last_recorded = now
        progress(f"{len(points)} PTS · {distance:.0f} M · "
                 f"{max_sats} SATS" if points or max_sats
                 else "WAITING FOR FIX...")
        # Sleep in slices so a stop press lands within ~0.25 s.
        for _ in range(4):
            if stop_check and stop_check():
                break
            time.sleep(0.25)
    gpx_path = TRACK_DIR / f"track-{stamp}.gpx"
    _write_gpx(points, gpx_path, stamp)
    summary = {"file": gpx_path.name, "when": _iso(time.time()),
               "seconds": int(round(time.time() - t0)),
               "points": len(points),
               "distance_m": round(distance), "max_sats": max_sats,
               "fix": bool(points), "stopped": stopped}
    (TRACK_DIR / f"track-{stamp}.json").write_text(
        json.dumps(summary, indent=1) + "\n")
    return summary


def list_tracks() -> list[dict]:
    out = []
    for f in sorted(TRACK_DIR.glob("track-*.json"), reverse=True):
        try:
            out.append(json.loads(f.read_text()))
        except (OSError, ValueError):
            continue
    return out[:20]


if __name__ == "__main__":
    import sys

    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    r = track(secs, progress=lambda m: print(m, flush=True))
    print(json.dumps(r, indent=1))
