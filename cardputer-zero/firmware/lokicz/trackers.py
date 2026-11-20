"""Tracker detector — is something following you?

Trackers (AirTags and friends) are BLE advertisers with very
distinctive payloads, all parseable out of btmon's rendering:

- Apple FindMy: manufacturer data from Apple (company 76)
  starting 12 19 — the offline-finding beacon an AirTag (or a
  FindMy accessory) broadcasts when separated from its owner.
- Samsung SmartTag: service UUID 0xFD59.
- Tile: service UUID 0xFEED.
- Chipolo: service UUID 0xFE2C (medium confidence).

Presence is not following. The detector keeps a small on-device
history (~/.config/lokicz/trackers.json): every watch window
that hears a tracker is logged against its address, and the
verdict escalates with persistence — NEW → SEEN BEFORE →
PERSISTENT → FOLLOWING CANDIDATE (heard in 3+ windows spanning
20+ minutes, staying loud). A candidate is a graded lead, not a
verdict: verify physically before accusing a backpack.

Honest limits: AirTags rotate their BLE address (roughly
daily), so address history undercounts them across days; and a
tracker in your own home will look 'persistent' — it should,
it lives there. The signal that matters is persistence while
you MOVE between places.
"""

import json
import re
import subprocess
import time
from pathlib import Path

DB_PATH = Path.home() / ".config" / "lokicz" / "trackers.json"

_UUID_KINDS = {"fd59": ("SmartTag", "high"),
               "feed": ("Tile", "high"),
               "fe2c": ("Chipolo", "medium")}


def parse_btmon(text: str) -> list[dict]:
    """Tracker-type devices from btmon text:
    [{address, kind, confidence, rssi, name}]."""
    found: dict[str, dict] = {}
    for block in re.split(r"LE Advertising Report", text):
        addr_m = re.search(r"Address: ([0-9A-F:]{17})", block)
        if not addr_m:
            continue
        addr = addr_m.group(1)
        kind = conf = None
        apple = re.search(r"Company: Apple, Inc\. \(76\)\s*\n"
                          r"\s*Data\[\d+\]: ([0-9a-f]+)", block)
        if apple and apple.group(1).startswith("1219"):
            kind, conf = "AirTag / FindMy", "high"
        else:
            for m in re.finditer(r"\((0x[0-9a-f]{4})\)", block):
                hit = _UUID_KINDS.get(m.group(1)[2:])
                if hit:
                    kind, conf = hit
                    break
        if not kind:
            continue
        rssi_m = re.search(r"RSSI: (-?\d+)", block)
        name_m = re.search(r"Name \(complete\): (.+)", block)
        dev = found.setdefault(addr, {
            "address": addr, "kind": kind, "confidence": conf,
            "rssi": -999, "name": ""})
        if rssi_m:
            dev["rssi"] = max(dev["rssi"], int(rssi_m.group(1)))
        if name_m:
            dev["name"] = name_m.group(1).strip()
    return [d for d in found.values() if d["rssi"] > -999]


def _load_db() -> dict:
    try:
        return json.loads(DB_PATH.read_text())
    except (OSError, ValueError):
        return {}


def _save_db(db: dict) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(json.dumps(db, indent=1))


def _verdict(entry: dict) -> str:
    span_min = (entry["last"] - entry["first"]) / 60.0
    if entry["windows"] >= 3 and span_min >= 20 \
            and entry["best_rssi"] > -75:
        return "FOLLOWING CANDIDATE"
    if entry["windows"] >= 3:
        return "PERSISTENT"
    if entry["windows"] == 2:
        return "SEEN BEFORE"
    return "NEW"


def known() -> list[dict]:
    """The whole tracker history, worst verdict first."""
    out = []
    for addr, e in _load_db().items():
        out.append({"address": addr, **e, "verdict": _verdict(e),
                    "span_min": round((e["last"] - e["first"]) / 60)})
    order = {"FOLLOWING CANDIDATE": 0, "PERSISTENT": 1,
             "SEEN BEFORE": 2, "NEW": 3}
    return sorted(out, key=lambda d: order[d["verdict"]])


def watch(seconds: int = 90, stop_check=None) -> dict:
    """Listen for trackers, fold the window into the history.

    `stop_check` ends the window early: the scan is terminated
    and whatever was heard still folds into the history."""
    run_id = time.strftime("%Y%m%d-%H%M%S")
    btmon_text = ""
    try:
        p = subprocess.Popen(["sudo", "-n", "btmon"],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True)
    except OSError:
        p = None
    try:
        ctl = subprocess.Popen(["bluetoothctl", "--timeout",
                                str(seconds), "scan", "on"],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, text=True)
        deadline = time.time() + seconds + 15
        while ctl.poll() is None and time.time() < deadline:
            if stop_check and stop_check():
                ctl.terminate()
                break
            time.sleep(0.25)
        try:
            ctl.wait(timeout=5)
        except subprocess.TimeoutExpired:
            ctl.kill()
    except OSError:
        pass
    if p is not None:
        p.terminate()
        try:
            btmon_text = p.communicate(timeout=5)[0] or ""
        except subprocess.TimeoutExpired:
            p.kill()

    heard = parse_btmon(btmon_text)
    db = _load_db()
    now = time.time()
    for dev in heard:
        e = db.setdefault(dev["address"], {
            "kind": dev["kind"], "confidence": dev["confidence"],
            "first": now, "last": now, "windows": 0,
            "sightings": 0, "best_rssi": dev["rssi"],
            "last_run": ""})
        e["last"] = now
        e["sightings"] += 1
        e["best_rssi"] = max(e["best_rssi"], dev["rssi"])
        if e["last_run"] != run_id:
            e["windows"] += 1
            e["last_run"] = run_id
    _save_db(db)

    out = []
    for dev in heard:
        e = db[dev["address"]]
        out.append({**dev, "windows": e["windows"],
                    "verdict": _verdict(e)})
    out.sort(key=lambda d: d["rssi"], reverse=True)
    return {"found": out, "heard": len(heard),
            "known_total": len(db), "seconds": seconds,
            "stopped": bool(stop_check and stop_check())}


if __name__ == "__main__":
    r = watch()
    print(f"{r['heard']} tracker(s) this window; "
          f"{r['known_total']} in history")
    for d in r["found"]:
        print(f"  {d['kind']:<16} {d['address']} {d['rssi']} dBm "
              f"[{d['verdict']}]")
