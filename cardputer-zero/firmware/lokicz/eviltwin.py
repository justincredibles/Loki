"""Evil-twin / rogue-AP check — defensive, passive.

Builds a baseline of known networks from the wardrive
history (every WiGLE CSV in ~/lokicz-wardrives): for each
SSID, which BSSIDs broadcast it and with what security.
A fresh scan on the built-in radio is then compared:

  - "downgrade": a network that was encrypted in the
    baseline now appears OPEN — the classic evil-twin
    tell (same name, no password, hoping clients roam).
  - "new-bssid": a known SSID appears from a BSSID the
    baseline has never seen. Often innocent (a neighbor
    replaced a router, a second AP came online) — it's a
    graded lead to eyeball, not a verdict.
  - "twin": the same SSID is on air right now from two
    BSSIDs with DIFFERENT security — one real, one not.

Hidden SSIDs and SSIDs never wardrived are ignored: no
baseline, no opinion. Re-running a wardrive refreshes
the baseline.
"""

import csv

from . import wardrive, wifi_recon

WARDRIVE_DIR = wardrive.WARDRIVE_DIR


def _is_open(auth: str) -> bool:
    return "WPA" not in (auth or "") and "WEP" not in (auth or "")


def build_baseline() -> dict:
    """{ssid: {"bssids": set, "auths": set}} from wardrives."""
    base: dict[str, dict] = {}
    for path in sorted(WARDRIVE_DIR.glob("*.csv")):
        try:
            rows = list(csv.reader(path.open()))
        except OSError:
            continue
        for row in rows:
            if len(row) < 3 or row[0] == "MAC" \
                    or row[0].startswith("WigleWifi"):
                continue
            bssid, ssid, auth = row[0].upper(), row[1], row[2]
            if not ssid:
                continue
            entry = base.setdefault(ssid, {"bssids": set(),
                                           "auths": set()})
            entry["bssids"].add(bssid)
            entry["auths"].add(auth)
    return base


def compare(baseline: dict, live: list[dict]) -> list[dict]:
    """Pure comparison — unit-tested with synthetic scans."""
    alerts: dict[tuple, dict] = {}

    def add(kind, ap, detail):
        key = (kind, ap["ssid"], ap["bssid"].upper())
        alerts.setdefault(key, {
            "kind": kind, "ssid": ap["ssid"],
            "bssid": ap["bssid"].upper(), "auth": ap["auth"],
            "signal_dbm": ap.get("signal_dbm"),
            "detail": detail})

    by_ssid: dict[str, list[dict]] = {}
    for ap in live:
        if ap.get("ssid"):
            by_ssid.setdefault(ap["ssid"], []).append(ap)

    for ssid, aps in by_ssid.items():
        auths_now = {a["auth"] for a in aps}
        if len(aps) > 1 and len(auths_now) > 1:
            for ap in aps:
                add("twin", ap,
                    "same SSID on air with mixed security "
                    "right now — one of these is not like "
                    "the others")
        known = baseline.get(ssid)
        if not known:
            continue
        base_encrypted = any(not _is_open(a) for a in known["auths"])
        for ap in aps:
            if base_encrypted and _is_open(ap["auth"]):
                add("downgrade", ap,
                    "this SSID was encrypted in your "
                    "wardrive baseline; this AP is OPEN")
            elif ap["bssid"].upper() not in known["bssids"]:
                add("new-bssid", ap,
                    "known SSID from a BSSID your wardrives "
                    "have never seen — new hardware, or a "
                    "twin; worth an eyeball")
    return sorted(alerts.values(),
                  key=lambda a: (a["kind"] != "downgrade",
                                 a["kind"] != "twin",
                                 a["ssid"]))


def check() -> dict:
    """One live evil-twin check against the baseline."""
    baseline = build_baseline()
    live = wifi_recon.scan_aps()
    alerts = compare(baseline, live)
    return {
        "scanned": len(live),
        "baseline_networks": len(baseline),
        "alerts": alerts,
        "downgrades": sum(1 for a in alerts
                           if a["kind"] == "downgrade"),
        "twins": sum(1 for a in alerts if a["kind"] == "twin"),
        "new_bssids": sum(1 for a in alerts
                          if a["kind"] == "new-bssid"),
    }
