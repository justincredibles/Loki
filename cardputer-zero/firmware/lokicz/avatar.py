"""The Loki avatar — XP, levels, achievements, gear.

Design: docs/AVATAR.md (Justin's rule: every real action in the
app earns XP). The profile lives on-device at
~/.config/lokicz/avatar.json — never in the repo.

award_for(action, result) is the single entry point both the
LCD app and the web portal call when an action completes; it
maps each module's result dict onto the XP table, updates the
lifetime counters the achievements check against, and reports
back any level-ups / new achievements so the UI can celebrate.

The home screen (Justin's layout, 2026-11-17): avatar portrait
left, level box + XP bar top right, rotating Loki sayings under
them, and a bottom carousel — PREV over key 4, the selected
menu item over key 6 (press to launch), NEXT over key 8.
"""

import json
import random
import time
from pathlib import Path

PROFILE_PATH = Path.home() / ".config" / "lokicz" / "avatar.json"

LEVEL_XP = [0, 100, 250, 500, 850, 1300, 1900, 2700, 3700, 5000]
TITLES = ["Mortal", "Trickster", "Mischief Maker", "Illusionist",
          "Schemer", "Sorcerer", "Prince of Lies", "God of Mischief",
          "King of Asgard", "All-Father's Problem"]

# slot -> [(id, name, unlock level, unlock achievement or None)]
GEAR = {
    "horns": [("classic", "Classic Horns", 1, None),
              ("longhorn", "Longhorns", 3, None),
              ("crown", "Crown of Horns", 6, None),
              ("winged", "Winged Helm", 9, None)],
    "armor": [("street", "Street Clothes", 1, None),
              ("leather", "Leather Armor", 2, None),
              ("chain", "Chainmail", 4, None),
              ("plate", "Asgardian Plate", 7, None),
              ("royal", "Royal Gold", 10, None)],
    "cape": [("none", "No Cape", 1, None),
             ("green", "Green Cape", 3, None),
             ("royal", "Royal Cape", 8, None)],
    "gem": [("none", "No Gem", 1, None),
            ("emerald", "Emerald", 0, "bug_hunter"),
            ("sapphire", "Sapphire", 0, "sky_watcher"),
            ("ruby", "Ruby", 0, "exterminator")],
    "scepter": [("none", "No Scepter", 1, None),
                ("scepter", "Scepter of Mischief", 10, None)],
}

# (id, name, counter key, threshold)
ACHIEVEMENTS = [
    ("first_blood", "First Blood", "hashes", 1),
    ("century", "Century Club", "hashes", 100),
    ("cracked_it", "Cracked It", "cracks", 1),
    ("cartographer", "Cartographer", "wardrive_networks", 1000),
    ("eagle_eye", "Eagle Eye", "sniff_hits", 1),
    ("bug_hunter", "Bug Hunter", "cves", 1),
    ("exterminator", "Exterminator", "crits", 1),
    ("auditor", "The Auditor", "audits", 10),
    ("sky_watcher", "Sky Watcher", "flight_checks", 100),
    ("crowded_room", "Crowded Room", "proximity_max", 50),
    ("ghosted", "Ghosted", "tracker_follows", 1),
    ("signal_thief", "Signal Thief", "ook_signals", 1),
    ("sleight_of_hand", "Sleight of Hand", "nfc_tags", 1),
    ("well_connected", "Well Connected", "mesh_nodes", 10),
]

SAYINGS = [
    "I am burdened with glorious handshakes.",
    "Another network? How quaint.",
    "Trust is for people with no exit plan.",
    "I do what I want. So does my human.",
    "Kneel? No. Scan.",
    "Your Wi-Fi password is showing.",
    "I make mischief. You make coffee.",
    "Somewhere, a router fears me.",
    "Born to rule. Assigned to wardrive.",
    "That CVE? I saw it first.",
    "An ant has no quarrel with an access point.",
    "Puny firewall.",
    "I have been falling for 30 packets!",
    "The sun will shine again. After this audit.",
    "Your savior is here — he brought tshark.",
    "Mischief managed. Logs saved.",
    "I am a god. The dongle does the typing.",
    "Tell me where the trackers are. Slowly.",
]

_COUNTERS = ["hashes", "cracks", "wardrive_networks", "sniff_hits",
             "cves", "crits", "audits", "flight_checks",
             "proximity_max", "tracker_follows", "ook_signals",
             "mesh_nodes", "captures", "probes", "tracks", "nfc_tags"]


def _default() -> dict:
    return {"xp": 0,
            "counters": {k: 0 for k in _COUNTERS},
            "achievements": [],
            "gear": {"horns": "classic", "armor": "street",
                     "cape": "none", "gem": "none",
                     "scepter": "none"},
            "daily": {"date": "", "flight_xp": 0}}


def load() -> dict:
    try:
        profile = json.loads(PROFILE_PATH.read_text())
    except (OSError, ValueError):
        return _default()
    base = _default()
    base.update({k: v for k, v in profile.items()
                 if k in base and not isinstance(v, dict)})
    base["counters"].update(profile.get("counters", {}))
    base["gear"].update(profile.get("gear", {}))
    base["achievements"] = profile.get("achievements", [])
    base["daily"].update(profile.get("daily", {}))
    return base


def save(profile: dict) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=1) + "\n")


def level_for(xp: int) -> int:
    level = 1
    for i, threshold in enumerate(LEVEL_XP, 1):
        if xp >= threshold:
            level = i
    if xp >= LEVEL_XP[-1]:
        level = 10 + (xp - LEVEL_XP[-1]) // 1500
    return level


def progress(xp: int) -> tuple[int, int, int, float]:
    """(level, xp into level, xp needed for next, fraction)."""
    level = level_for(xp)
    if level < 10:
        base, nxt = LEVEL_XP[level - 1], LEVEL_XP[level]
    else:
        base = LEVEL_XP[-1] + (level - 10) * 1500
        nxt = base + 1500
    into, needed = xp - base, nxt - base
    return level, into, needed, (into / needed if needed else 1.0)


def _unlocked(item: tuple, profile: dict) -> bool:
    _id, _name, level, achievement = item
    if achievement:
        return achievement in profile["achievements"]
    return level_for(profile["xp"]) >= level


def equip(slot: str, item_id: str) -> tuple[bool, str]:
    profile = load()
    for item in GEAR.get(slot, []):
        if item[0] == item_id:
            if not _unlocked(item, profile):
                return False, "locked"
            profile["gear"][slot] = item_id
            save(profile)
            return True, "equipped"
    return False, "no such item"


def state() -> dict:
    profile = load()
    level, into, needed, frac = progress(profile["xp"])
    gear = {}
    for slot, items in GEAR.items():
        gear[slot] = [
            {"id": i[0], "name": i[1],
             "unlocked": _unlocked(i, profile),
             "equipped": profile["gear"].get(slot) == i[0]}
            for i in items]
    achievements = [
        {"id": a[0], "name": a[1],
         "unlocked": a[0] in profile["achievements"],
         "progress": f"{profile['counters'].get(a[2], 0)}/{a[3]}"}
        for a in ACHIEVEMENTS]
    return {"xp": profile["xp"], "level": level,
            "title": TITLES[min(level, 10) - 1],
            "into": into, "needed": needed, "frac": round(frac, 3),
            "counters": profile["counters"],
            "achievements": achievements,
            "gear": gear, "equipped": profile["gear"]}


def saying() -> str:
    return random.choice(SAYINGS)


def _check_achievements(profile: dict) -> list[str]:
    new = []
    for aid, name, counter, threshold in ACHIEVEMENTS:
        if aid not in profile["achievements"] \
                and profile["counters"].get(counter, 0) >= threshold:
            profile["achievements"].append(aid)
            new.append(name)
    return new


def award(xp: int, counters: dict | None = None) -> dict:
    """Grant XP + counter bumps; return the celebration news."""
    profile = load()
    old_level = level_for(profile["xp"])
    profile["xp"] += max(0, xp)
    for key, delta in (counters or {}).items():
        if key == "proximity_max":
            profile["counters"][key] = max(
                profile["counters"].get(key, 0), delta)
        else:
            profile["counters"][key] = \
                profile["counters"].get(key, 0) + delta
    new_achievements = _check_achievements(profile)
    save(profile)
    new_level = level_for(profile["xp"])
    return {"xp_gained": xp,
            "level_up": new_level if new_level > old_level else None,
            "achievements": new_achievements,
            "level": new_level}


def award_for(action: str, result: dict) -> dict:
    """The XP table (docs/AVATAR.md) applied to a result dict."""
    if not isinstance(result, dict):
        return {"xp_gained": 0, "level_up": None, "achievements": []}
    if action == "capture":
        pairs = max(0, result.get("hashes", 0)
                    - result.get("pmkid", 0))
        xp = min(250, 10 + 25 * pairs + 10 * result.get("pmkid", 0))
        return award(xp, {"hashes": result.get("hashes", 0),
                          "captures": 1})
    if action == "wardrive":
        xp = min(100, result.get("networks", 0)) \
            + (10 if result.get("gps_fix") else 0)
        return award(xp, {"wardrive_networks":
                          result.get("networks", 0)})
    if action in ("audit", "watchdog"):
        xp = min(300, 30 + 2 * result.get("open_ports", 0)
                 + 3 * result.get("cves", 0)
                 + 10 * result.get("crit", 0))
        return award(xp, {"audits": 1, "cves": result.get("cves", 0),
                          "crits": result.get("crit", 0)})
    if action == "sniff":
        hits = len(result.get("hits", []))
        return award(10 + 40 * hits, {"sniff_hits": hits})
    if action == "trackers":
        follows = sum(1 for d in result.get("found", [])
                      if d.get("verdict") == "FOLLOWING CANDIDATE")
        return award(5 + 50 * follows,
                     {"tracker_follows": follows})
    if action == "probes":
        return award(5 + min(30, result.get("directed_devices", 0)),
                     {"probes": 1})
    if action == "proximity":
        return award(5, {"proximity_max": result.get("count", 0)})
    if action == "eviltwin":
        alerts = len(result.get("alerts", []))
        return award(10 + 20 * alerts,
                     {"eviltwin_checks": 1, "eviltwin_alerts": alerts})
    if action == "deauth":
        hot = result.get("level") in ("elevated", "flood")
        return award(15 + (40 if hot else 0),
                     {"deauth_watches": 1,
                      "deauth_floods": 1 if hot else 0})
    if action == "flights":
        if not result.get("ok"):
            return {"xp_gained": 0, "level_up": None,
                    "achievements": []}
        profile = load()
        today = time.strftime("%Y-%m-%d")
        if profile["daily"]["date"] != today:
            profile["daily"] = {"date": today, "flight_xp": 0}
            save(profile)
        if profile["daily"]["flight_xp"] >= 10:
            return award(0, {"flight_checks": 1})
        profile = load()
        profile["daily"]["flight_xp"] += 2
        save(profile)
        return award(2, {"flight_checks": 1})
    if action == "gps":
        return award(5 + (10 if result.get("fix") else 0),
                     {"tracks": 1})
    if action == "sweep":
        return award(5, {})
    if action == "ook":
        return award(15 * result.get("bursts", 0),
                     {"ook_signals": result.get("bursts", 0)})
    if action == "nfc":
        found = bool(result.get("found"))
        return award(10 + (25 if found else 0),
                     {"nfc_tags": 1 if found else 0})
    if action in ("mesh-send", "mesh-listen", "mesh-nodes",
                  "mesh-setch", "mesh-delch", "mesh-setname",
                  "mesh-setconfig", "meshcore-setconfig"):
        return award(5)
    if action == "wpasec-sync":
        return award(2 + 25 * result.get("cracked_new", 0),
                     {"cracks": result.get("cracked_new", 0)})
    return {"xp_gained": 0, "level_up": None, "achievements": []}
