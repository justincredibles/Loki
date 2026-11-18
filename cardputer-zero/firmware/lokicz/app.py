"""The on-device menu app — lokicz you can drive from the keyboard.

Screens wear the Asgard theme (ui.py): a status board with labeled
readouts, the menu as a 3x3 grid of key chips across two pages,
big gold result numbers, and an animated progress screen for long
operations. Page 1 is the daily kit (recon, capture, caps, mesh,
and the Bjorn-style network AUDIT); page 2 holds WPA-SEC, the last
audit's results, and Stop. Pressing Stop exits the app (under
systemd it stays stopped until started again —
`sudo systemctl start lokicz` brings it back).
"""

import glob

from . import caps, capture, config, ui, wifi_recon


def _total_hashes() -> int:
    total = 0
    for path in glob.glob(str(capture.CAPTURE_DIR / "*.hc22000")):
        try:
            total += len(open(path).read().splitlines())
        except OSError:
            pass
    return total


def _chips(cfg: dict, page: int) -> list:
    if page == 2:
        return [("1", "WPA-SEC"), ("2", "LAST AUDIT"),
                ("3", "STOP"), ("4", "FLIGHTS"), ("5", "RADAR"),
                ("9", "◂ BACK")]
    cap_tone = "text" if cfg.get("capture_enabled", True) else "off"
    return [("1", "STATUS"), ("2", "CAPTURE", cap_tone),
            ("3", "SUB-GHZ"), ("4", "WARDRIVE"), ("5", "SNIFF"),
            ("6", "MESH"), ("7", "AUDIT"), ("8", "CAP TGL"),
            ("9", "MORE ▸")]


def _status_rows(cfg: dict) -> list:
    from . import wpasec

    profile = caps.detect_cap(cfg["cap"])
    dongle = wifi_recon.capture_available(cfg["capture_iface"])
    on = cfg.get("capture_enabled", True)
    w = wpasec.status(cfg)
    return [
        ("kv", "CAP", profile.name.upper(), "gold"),
        ("kv", "WI-FI", "RECON OK", "ok"),
        ("kv", "CAPTURE",
         ("ON" if on else "OFF") + (" · DONGLE RDY" if dongle
                                     else " · NO DONGLE"),
         "ok" if on and dongle else "warn" if on else "off"),
        ("kv", "HASHES", str(_total_hashes()), "gold"),
        ("kv", "WPA-SEC",
         ("ON · %d CRACKED" % w["cracked"]) if w["enabled"] else "OFF",
         "ok" if w["enabled"] else "dim"),
    ]


def _wpasec_rows(cfg: dict) -> list:
    from . import wpasec

    w = wpasec.status(cfg)
    return [
        ("kv", "AUTO-SYNC", "ON" if w["enabled"] else "OFF",
         "ok" if w["enabled"] else "off"),
        ("kv", "API KEY", "SET" if w["key_set"] else "NOT SET",
         "ok" if w["key_set"] else "bad"),
        ("kv", "TO UPLOAD", str(w["pending"]), "text"),
        ("kv", "CRACKED", str(w["cracked"]), "gold"),
        ("gap", 4),
        ("text", "9 on/off    0 sync now", "dim"),
        ("text", "any other key: back", "dim"),
    ]


def _audit_rows(stats: dict) -> list:
    tone = "bad" if stats["crit"] else "warn" if stats["high"] \
        else "ok"
    rows = [("big", f"{stats['cves']} CVES", tone),
            ("kv", "HOSTS SCANNED",
             f"{stats['scanned']}/{stats['hosts']}", "text"),
            ("kv", "CRIT / HIGH",
             f"{stats['crit']} / {stats['high']}", tone)]
    if stats["top"]:
        rows.append(("kv", "WORST",
                     f"{stats['top']['id'][4:]} @ "
                     f"{stats['top']['score']}", "bad"))
    return rows


def _last_audit_rows() -> list:
    from . import audit

    s = audit.latest_summary()
    if not s:
        return [("text", "NO AUDITS YET", "dim"),
                ("text", "page 1 → 7 AUDIT to run one", "dim")]
    # WHEN + big + 2 kv (the fresh-run screen fits one row more).
    return [("kv", "WHEN", s["when"], "dim")] + _audit_rows(s)[:3]


def _screen(rows: list, cfg: dict, title: str = "LOKI",
            page: int = 0) -> str:
    """Draw a screen; page 0 = no chips, 1/2 = that menu page."""
    ui.show_screen(title, rows,
                   chips=_chips(cfg, page) if page else None,
                   right="CAP " + cfg["cap"].upper())
    return ui.read_key()


def _stop() -> int:
    ui.show_screen("LOKI", [
        ("gap", 14),
        ("big", "GODSPEED", "gold"),
        ("text", "lokicz stopped — restart with", "dim"),
        ("text", "sudo systemctl start lokicz", "text"),
    ], right="")
    return 0


def run() -> int:
    cfg = config.load()
    try:
        ui.splash()
    except OSError:
        pass
    rows = _status_rows(cfg)
    title = "LOKI"
    screen = "main"
    page = 1
    while True:
        key = _screen(rows, cfg, title=title,
                      page=page if screen == "main" else 0)
        title = "LOKI"
        if screen == "wpasec":
            # WPA-SEC screen has its own keys; anything else goes back.
            from . import wpasec

            if key == "9":
                cfg["wpasec_enabled"] = not cfg.get("wpasec_enabled",
                                                    False)
                config.save(cfg)
                title = "WPA-SEC"
                rows = _wpasec_rows(cfg)
            elif key == "0":
                with ui.Spinner("WPA-SEC", "upload + download"):
                    r = wpasec.sync(cfg)
                if r["ok"]:
                    rows = [("big", f"+{r['uploaded']} UP", "ok"),
                            ("kv", "CRACKED TOTAL",
                             str(r["cracked_total"]), "gold"),
                            ("kv", "NEW THIS SYNC",
                             str(r["cracked_new"]), "text")]
                else:
                    rows = [("text", "WPA-SEC SYNC FAILED", "bad"),
                            ("text", r.get("reason",
                                           f"{r.get('failures', 0)} "
                                           "step(s) failed"), "dim")]
                title = "WPA-SEC"
                screen = "main"
            else:
                screen = "main"
                rows = _status_rows(cfg)
            continue
        if key in ("q", "esc"):
            return _stop()
        if page == 2:
            if key == "1":
                screen = "wpasec"
                title = "WPA-SEC"
                rows = _wpasec_rows(cfg)
            elif key == "2":
                title = "LAST AUDIT"
                rows = _last_audit_rows()
            elif key == "3":
                return _stop()
            elif key == "4":
                from . import flights

                with ui.Spinner("FLIGHT RADAR", "asking the sky..."):
                    r = flights.nearest(cfg)
                if r["ok"]:
                    blips = [(a["bearing"],
                              a["dist_nm"] / r["radius_nm"],
                              "gold" if not a["on_ground"] else "dim")
                             for a in r["aircraft"]]
                    frows = [("text",
                              f"{r['total']} AIRCRAFT", "dim")]
                    for a in r["aircraft"][:5]:
                        alt = "GND" if a["on_ground"] else \
                            f"{(a['alt_ft'] or 0) // 1000}K FT"
                        frows.append(("kv", a["callsign"][:9],
                                      f"{a['dist_nm']}NM {alt}",
                                      "text"))
                    ui.radar_screen("FLIGHT RADAR", blips, frows,
                                    right="ADS-B")
                    rows = frows
                else:
                    rows = [("text", "FLIGHT RADAR OFFLINE", "bad"),
                            ("text", r["reason"][:28], "dim")]
            elif key == "5":
                from . import proximity

                with ui.Spinner("PROXIMITY",
                                "listening for nearby radios...",
                                expected=25):
                    r = proximity.scan(25)
                if r["devices"]:
                    blips = [(d["bearing"], d["frac"],
                              "gold" if d["rssi"] > -60 else
                              "text" if d["rssi"] > -80 else "dim")
                             for d in r["devices"]]
                    prows = [("text", f"{r['count']} DEVICES", "dim")]
                    for d in r["devices"][:5]:
                        prows.append(("kv", d["name"][:11],
                                      f"~{d['meters']}M", "text"))
                    ui.radar_screen("PROXIMITY", blips, prows,
                                    right="BLE")
                    rows = prows
                else:
                    rows = [("text", "NOTHING NEARBY", "dim"),
                            ("text", "no BLE heard in 25s", "dim")]
            elif key == "9":
                page = 1
                rows = _status_rows(cfg)
            continue
        # --- page 1 ---
        if key == "1":
            rows = _status_rows(cfg)
        elif key == "2":
            if not cfg.get("capture_enabled", True):
                rows = [("text", "CAPTURE IS OFF", "bad"),
                        ("text", "press 8 to turn it on", "dim")]
                continue
            with ui.Spinner("CAPTURE",
                            f"listening on {cfg['capture_iface']} — "
                            "deauth disabled",
                            expected=cfg["capture_seconds"]):
                stats = capture.run_capture(cfg["capture_seconds"],
                                            cfg["capture_iface"])
            rows = [("big", f"{stats['hashes']} HASHES",
                     "gold" if stats["hashes"] else "text"),
                    ("kv", "EAPOL MSGS", str(stats["eapol"]), "text"),
                    ("kv", "PCAP SAVED", f"{stats['bytes'] // 1024} KB",
                     "text")]
            title = "CAPTURE"
            if cfg.get("wpasec_enabled"):
                from . import wpasec

                with ui.Spinner("WPA-SEC", "auto-sync..."):
                    r = wpasec.sync(cfg)
                if r["ok"]:
                    rows.append(("kv", "WPA-SEC",
                                 f"+{r['uploaded']} UP · "
                                 f"{r['cracked_total']} CRACKED", "ok"))
                else:
                    rows.append(("kv", "WPA-SEC",
                                 r.get("reason", "sync had failures"),
                                 "warn"))
        elif key == "8":
            cfg["capture_enabled"] = not cfg.get("capture_enabled", True)
            config.save(cfg)
            rows = _status_rows(cfg)
        elif key == "9":
            from . import web

            page = 2
            rows = [("text", "PAGE 2 — SERVICES", "dim"),
                    ("text", "1 WPA-SEC · 2 LAST AUDIT", "text"),
                    ("text", "3 STOP · 4 FLIGHTS · 5 RADAR", "text"),
                    ("text", "9 back to page 1", "dim"),
                    ("kv", "WEB PORTAL",
                     f"{web.lan_ip()}:{web.PORT}", "gold")]
        elif key == "3":
            from .cc1101 import CC1101

            with ui.Spinner("SUB-GHZ", "listening on both bands"):
                with CC1101() as radio:
                    out = []
                    for start, stop in ((430.0, 437.0), (902.0, 928.0)):
                        sweep = radio.sweep(start, stop, 0.5,
                                            dwell_s=0.05)
                        floor = sorted(r for _, r in sweep)[len(sweep) // 2]
                        peak_f, peak_r = max(sweep, key=lambda t: t[1])
                        out.append((f"{start:.0f}-{stop:.0f} MHZ",
                                    f"FLR {floor:.0f} · PK {peak_r:.0f}"
                                    f"@{peak_f:.0f}"))
            rows = [("text", "BAND SWEEP COMPLETE", "ok")] + [
                ("kv", band, val, "text") for band, val in out]
            title = "SUB-GHZ"
        elif key == "4":
            from . import wardrive

            with ui.Spinner("WARDRIVE", "scanning — GPS logging",
                            expected=cfg["wardrive_seconds"]):
                stats = wardrive.run_wardrive(cfg["wardrive_seconds"])
            rows = [("big", f"{stats['networks']} NETS", "gold"),
                    ("kv", "GPS FIX",
                     "YES" if stats["gps_fix"] else "NO — NEEDS SKY",
                     "ok" if stats["gps_fix"] else "warn")]
            title = "WARDRIVE"
        elif key == "5":
            from . import sniffer

            with ui.Spinner("SNIFF", "passive — Wi-Fi + BLE",
                            expected=cfg["sniff_seconds"]):
                stats = sniffer.run_sniff(cfg["sniff_seconds"])
            rows = [("big", f"{len(stats['hits'])} HITS",
                     "bad" if stats["hits"] else "ok"),
                    ("kv", "OBSERVED",
                     f"WI-FI {stats['wifi_obs']} · BLE {stats['ble_obs']}",
                     "text")]
            for hit in stats["hits"][:2]:
                rows.append(("text",
                             f"[{hit['confidence']}] {hit['label']}",
                             "warn"))
            title = "SNIFF"
        elif key == "6":
            from . import meshtastic, meshcore

            s = meshtastic.status()
            m = meshcore.status()
            rows = [
                ("kv", "MODE", m["mode"].upper(), "gold"),
                ("kv", "MESHTASTIC",
                 "ACTIVE" if s["service"] else "PARKED",
                 "ok" if s["service"] else "dim"),
                ("kv", "SX1262 RADIO",
                 "PROVEN" if s["radio"] else "NOT PROVEN",
                 "ok" if s["radio"] else "warn"),
                ("kv", "MESHCORE",
                 "ACTIVE" if m["pymc_active"] else
                 "READY" if m["mode"] == "meshcore" else "STANDBY",
                 "text"),
            ]
            title = "MESH"
        elif key == "7":
            from . import audit

            with ui.Spinner("AUDIT", "starting...") as spinner:
                stats = audit.run_audit(
                    cfg, progress=lambda m: setattr(spinner,
                                                    "message", m))
            rows = _audit_rows(stats)
            title = "AUDIT"
        # any other key: just redraw the current screen


if __name__ == "__main__":
    raise SystemExit(run())
