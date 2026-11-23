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
    # Chip tuples are (key, label[, tone[, cap]]) — the cap tag
    # draws the compat bar: dark blue = CC1101 cap, magenta =
    # LoRa cap, split = works with either (see ui._cap_bar_v).
    if page == 2:
        return [("1", "WPA-SEC", "text", "both"),
                ("2", "LAST AUDIT", "text", "both"),
                ("3", "STOP"),
                ("4", "FLIGHTS", "text", "both"),
                ("5", "RADAR", "text", "both"),
                ("6", "TRACKER", "text", "both"),
                ("7", "PROBES", "text", "both"),
                ("8", "GPS LOG", "text", "lora"),
                ("9", "◂ BACK")]
    cap_tone = "text" if cfg.get("capture_enabled", True) else "off"
    return [("1", "STATUS"), ("2", "CAPTURE", cap_tone, "both"),
            ("3", "RADIO", "text", "cc1101"),
            ("4", "WARDRIVE", "text", "both"),
            ("5", "SNIFF", "text", "both"),
            ("6", "MESH", "text", "lora"),
            ("7", "AUDIT", "text", "both"),
            ("8", "CAP TGL"),
            ("9", "MORE ▸")]


def _status_rows(cfg: dict) -> list:
    from . import wpasec

    profile = caps.detect_cap(cfg["cap"])
    dongle = wifi_recon.capture_available(cfg["capture_iface"])
    on = cfg.get("capture_enabled", True)
    w = wpasec.status(cfg)
    rows = [
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
    try:
        from . import watchdog

        state = watchdog.latest_state()
        if state and state.get("counts"):
            c = state["counts"]
            if c["new_hosts"] or c["new_cves"]:
                rows.append(("kv", "WATCHDOG",
                             f"+{c['new_hosts']} HOST "
                             f"+{c['new_cves']} CVE", "warn"))
    except Exception:
        pass
    rows.append(("text", "BAR: BLUE=CC1101 PINK=LORA", "dim"))
    rows.append(("text", "0/ESC: AVATAR · HOLD ESC: EXIT", "dim"))
    return rows


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


def _radio_rows(cfg: dict) -> list:
    rows = [("text", "CAP RADIO LAB", "gold"),
            ("text", "1 sweep · 2 ook 433 · 3 ook 315", "text"),
            ("text", "4 ook 915 · 5 replay · 6 nfc", "text"),
            ("text", "0 back", "dim")]
    if cfg["cap"] != "cc1101":
        rows.append(("kv", "WARNING", "NEEDS CC1101 CAP", "warn"))
    return rows


def _ook_capture(freq: float) -> list:
    """15 s OOK capture at `freq` + protocol decode of the result."""
    import time as _time

    from . import subghz
    from .cc1101 import CC1101

    stamp = _time.strftime("%Y%m%d-%H%M%S")
    path = subghz.SUBGHZ_DIR / f"ook-{freq:.2f}MHz-{stamp}.sub"
    with ui.Spinner("OOK CAPTURE", f"{freq} MHz — press the fob",
                    expected=15, abortable=True) as spinner:
        with CC1101() as radio:
            stats = radio.capture_ook(
                freq, 15, str(path),
                stop_check=spinner.stop_requested)
    dec = subghz.decode_file(str(path))
    rows = [("big", f"{stats['bursts']} BURSTS",
             "gold" if stats["bursts"] else "text"),
            ("kv", "PROTOCOL", dec["protocol"][:20], "text")]
    if dec["bits"]:
        rows.append(("kv", "CODE", "0x" + dec["code_hex"][:14],
                     "gold"))
        rows.append(("kv", "CONFIDENCE",
                     dec["confidence"].upper(), "ok"))
    rows.append(("kv", "FILE", path.name[:24], "dim"))
    rows.append(("text", "SAME KEY RETRIES · ANY KEY BACK", "dim"))
    _award("ook", stats)
    return rows


def _replay_rows() -> list:
    from . import subghz
    from .cc1101 import CC1101

    found = subghz.list_captures()
    if not found:
        return [("text", "NO CAPTURES YET", "warn"),
                ("text", "capture a fob first (2/3/4)", "dim")]
    path = subghz.SUBGHZ_DIR / found[0]["name"]
    with ui.Spinner("REPLAY", f"sending {path.name[:18]} (TX)",
                    abortable=True) as spinner:
        with CC1101() as radio:
            r = radio.replay_sub(str(path), 3,
                                 stop_check=spinner.stop_requested)
    if r.get("stopped"):
        return [("big", "STOPPED", "warn"),
                ("kv", "FRAMES SENT", str(r.get("frames", 0)), "text"),
                ("text", "SAME KEY RETRIES · ANY KEY BACK", "dim")]
    if r.get("sent"):
        return [("big", "SENT", "ok"),
                ("kv", "FILE", path.name[:24], "text"),
                ("kv", "FRAMES", str(r["frames"]), "text"),
                ("text", "SAME KEY RETRIES · ANY KEY BACK", "dim")]
    return [("text", "REPLAY FAILED", "bad"),
            ("text", str(r.get("reason", ""))[:26], "dim"),
            ("text", "SAME KEY RETRIES · ANY KEY BACK", "dim")]


def _nfc_rows() -> list:
    from . import nfc

    with ui.Spinner("NFC", "hold a tag to the cap..."):
        try:
            r = nfc.scan_once()
        except RuntimeError as exc:
            return [("text", "NFC UNAVAILABLE", "bad"),
                    ("text", str(exc)[:26], "dim"),
                    ("text", "SAME KEY RETRIES · ANY KEY BACK", "dim")]
    _award("nfc", r)
    if r["found"]:
        return [("big", "TAG FOUND", "ok"),
                ("kv", "UID", r["uid"][:20], "gold"),
                ("kv", "ATQA", r["atqa"] or "—", "text"),
                ("kv", "SAK", f"0x{r['sak']:02X}", "text"),
                ("text", "SAME KEY RETRIES · ANY KEY BACK", "dim")]
    if r.get("collision"):
        return [("big", "COLLISION", "warn"),
                ("text", "two tags — one at a time", "dim"),
                ("text", "SAME KEY RETRIES · ANY KEY BACK", "dim")]
    return [("big", "NO TAG", "text"),
            ("text", "nothing in the field", "dim"),
            ("text", "SAME KEY RETRIES · ANY KEY BACK", "dim")]


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
            page: int = 0, cap: str | None = None) -> str:
    """Draw a screen; page 0 = no chips, 1/2 = that menu page.
    Redraws every 20 s while waiting so the header clock and
    battery stay live on an idle screen."""
    while True:
        ui.show_screen(title, rows,
                       chips=_chips(cfg, page) if page else None,
                       right="CAP " + cfg["cap"].upper(), cap=cap)
        key = ui.read_key_timeout(20)
        if key is not None:
            return key


# The home carousel (Justin's layout): label + dispatch target
# + cap tag for the compat bar — "status"/"loki"/"stop",
# or (page, key) into the classic menus.
HOME_ITEMS = [
    ("Status", "status", None),
    ("Handshake Capture", (1, "2"), "both"),
    ("Radio Lab", (1, "3"), "cc1101"),
    ("Wardrive", (1, "4"), "both"),
    ("Sniff", (1, "5"), "both"),
    ("Mesh", (1, "6"), "lora"),
    ("Network Audit", (1, "7"), "both"),
    ("Capture On/Off", (1, "8"), None),
    ("WPA-Sec", (2, "1"), "both"),
    ("Last Audit", (2, "2"), "both"),
    ("Flight Radar", (2, "4"), "both"),
    ("Proximity Radar", (2, "5"), "both"),
    ("Tracker Watch", (2, "6"), "both"),
    ("Probe Logger", (2, "7"), "both"),
    ("GPS Track", (2, "8"), "lora"),
    ("Loki", "loki", None),
    ("Stop", "stop", None),
]


def _award(action: str, result) -> None:
    """Feed a finished action to the avatar; celebrate any news."""
    try:
        from . import avatar

        news = avatar.award_for(action, result)
    except Exception:
        return
    if not (news.get("level_up") or news.get("achievements")):
        return
    from . import avatar

    lines = []
    if news.get("level_up"):
        lines.append(f"LEVEL {news['level_up']}!")
        lines.append(avatar.TITLES[min(news["level_up"], 10) - 1]
                     .upper())
    for name in news.get("achievements", []):
        lines.append(f"★ {name.upper()}")
    lines.append(f"XP +{news['xp_gained']}")
    ui.celebrate(lines[:6])


def _loki_rows() -> list:
    from . import avatar

    st = avatar.state()
    return [("big", f"LEVEL {st['level']}", "gold"),
            ("kv", "TITLE", st["title"].upper(), "gold"),
            ("kv", "XP",
             f"{st['xp']} · NEXT {st['needed'] - st['into']}",
             "text"),
            ("kv", "TROPHIES",
             f"{sum(1 for a in st['achievements'] if a['unlocked'])}"
             f"/{len(st['achievements'])}", "cyan")]


def _stop() -> int:
    ui.show_screen("LOKI", [
        ("gap", 14),
        ("big", "GODSPEED", "gold"),
        ("text", "lokicz stopped — restart with", "dim"),
        ("text", "sudo systemctl start lokicz", "text"),
    ], right="")
    return 0


def _start_display_hat(cfg: dict):
    """Bring up the display hat when the tft profile is fitted.

    Constructs ONE ili9341.ILI9341, enters it, and registers it
    as ui's TFT sink; run() holds the returned object for the
    life of the process (the driver's power claim follows the
    0.36 claim-once rule — never cycled, never reconstructed
    per frame). Returns the panel, or None.

    A panel that won't init (unplugged, a jumper worked loose)
    is a journal line, not a crash: the menu carries on on the
    built-in screen alone — the same philosophy as the 0.32
    radio error guard. Other cap profiles return before the
    driver is even imported, so their startup is untouched.
    """
    if cfg.get("cap") != "tft":
        return None
    try:
        from . import ili9341

        tft = ili9341.ILI9341()
        tft.__enter__()
    except Exception as exc:
        print(f"lokicz: display hat unavailable ({exc}) — "
              "built-in screen only", flush=True)
        return None
    ui.set_tft_sink(tft)
    print("lokicz: display hat live — menu also renders on the "
          "big screen", flush=True)
    return tft


def run() -> int:
    from . import avatar

    cfg = config.load()
    # Held for the whole run: the display hat (tft profile only).
    _hat = _start_display_hat(cfg)
    try:
        ui.splash()
    except OSError:
        pass
    rows = _status_rows(cfg)
    title = "LOKI"
    screen = "home"
    page = 1
    home_idx = 0
    saying = avatar.saying()
    pending = None
    radio_result = False
    radio_result_key = None
    while True:
        if ui.exit_requested:
            # An ESC hold landed during a timed operation: its key
            # watcher aborted the job and set this — leave now.
            ui.exit_requested = False
            return _stop()
        if pending is not None:
            key, pending = pending, None
        elif screen == "home":
            st = avatar.state()
            key = ui.home_screen(
                HOME_ITEMS[home_idx][0], st["level"], st["title"],
                st["frac"],
                f"XP {st['xp']} · NEXT {st['needed'] - st['into']}",
                saying, st["equipped"], saying_fn=avatar.saying,
                cap=HOME_ITEMS[home_idx][2])
            if key in ("4", "8"):
                home_idx = (home_idx
                            + (1 if key == "8" else -1)) \
                    % len(HOME_ITEMS)
                saying = avatar.saying()
                continue
            if key == "esc_hold":
                return _stop()
            if key in ("6", "\n", "enter"):
                kind = HOME_ITEMS[home_idx][1]
                if kind == "status":
                    screen = "main"
                    page = 1
                    rows = _status_rows(cfg)
                elif kind == "loki":
                    screen = "main"
                    page = 1
                    title = "LOKI"
                    rows = _loki_rows()
                elif kind == "stop":
                    return _stop()
                else:
                    screen = "main"
                    page, pending = kind
                    rows = _status_rows(cfg)
                continue
            continue
        else:
            strip = "cc1101" if screen == "radio" else \
                "lora" if title in ("MESH", "GPS TRACK") else None
            key = _screen(rows, cfg, title=title,
                          page=page if screen == "main" else 0,
                          cap=strip)
        title = "LOKI"
        if screen == "wpasec":
            # WPA-SEC screen has its own keys; anything else goes back.
            from . import wpasec

            if key == "esc_hold":
                return _stop()
            if key == "9":
                cfg["wpasec_enabled"] = not cfg.get("wpasec_enabled",
                                                    False)
                config.save(cfg)
                title = "WPA-SEC"
                rows = _wpasec_rows(cfg)
            elif key == "0":
                with ui.Spinner("WPA-SEC", "upload + download",
                                abortable=True) as spinner:
                    r = wpasec.sync(
                        cfg, stop_check=spinner.stop_requested)
                if r["ok"]:
                    _award("wpasec-sync", r)
                if r["ok"]:
                    rows = [("big", f"+{r['uploaded']} UP", "ok"),
                            ("kv", "CRACKED TOTAL",
                             str(r["cracked_total"]), "gold"),
                            ("kv", "NEW THIS SYNC",
                             str(r["cracked_new"]), "text")]
                elif r.get("stopped"):
                    rows = [("big", "STOPPED", "warn"),
                            ("kv", "UPLOADED BEFORE STOP",
                             str(r["uploaded"]), "text"),
                            ("text", "finished uploads stay marked",
                             "dim")]
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
        if screen == "radio":
            # The radio lab has its own keys; a result screen
            # consumes one keypress to return to the radio menu.
            title = "RADIO"
            if key == "esc_hold":
                return _stop()
            if key in ("q", "esc"):
                screen = "main"
                rows = _status_rows(cfg)
                continue
            if radio_result:
                radio_result = False
                if key != radio_result_key or key not in \
                        ("1", "2", "3", "4", "5", "6"):
                    rows = _radio_rows(cfg)
                    continue
                # Same key again = retry the action that just ran:
                # fall through and let the dispatch below re-run it.
            if key == "0":
                screen = "main"
                rows = _status_rows(cfg)
                continue
            radio_result_key = key
            if cfg["cap"] != "cc1101" and key in \
                    ("1", "2", "3", "4", "5", "6"):
                rows = [("text", "NEEDS THE CC1101 CAP", "warn"),
                        ("text", "fit it, set profile, reboot",
                         "dim")]
                radio_result = True
                continue
            try:
                if key == "1":
                    from .cc1101 import CC1101

                    with ui.Spinner("SUB-GHZ",
                                    "listening on both bands",
                                    abortable=True) as spinner:
                        with CC1101() as radio:
                            out = []
                            for start, stop in ((430.0, 437.0),
                                                (902.0, 928.0)):
                                sweep = radio.sweep(
                                    start, stop, 0.5, dwell_s=0.05,
                                    stop_check=spinner
                                    .stop_requested)
                                if not sweep:
                                    continue  # stopped before a step
                                floor = sorted(r for _, r in sweep)[
                                    len(sweep) // 2]
                                peak_f, peak_r = max(
                                    sweep, key=lambda t: t[1])
                                out.append(
                                    (f"{start:.0f}-{stop:.0f} MHZ",
                                     f"FLR {floor:.0f} · "
                                     f"PK {peak_r:.0f}@{peak_f:.0f}"))
                    if spinner.stop_requested() and not out:
                        rows = [("big", "STOPPED", "warn"),
                                ("text", "sweep cut short", "dim"),
                                ("text", "SAME KEY RETRIES · ANY KEY "
                                 "BACK", "dim")]
                        radio_result = True
                        continue
                    rows = [("text", "BAND SWEEP COMPLETE", "ok")] + [
                        ("kv", band, val, "text") for band, val in out]
                    rows.append(("text", "SAME KEY RETRIES · ANY KEY "
                                 "BACK", "dim"))
                    _award("sweep", {})
                    radio_result = True
                elif key in ("2", "3", "4"):
                    freq = {"2": 433.92, "3": 315.0, "4": 915.0}[key]
                    rows = _ook_capture(freq)
                    radio_result = True
                elif key == "5":
                    rows = _replay_rows()
                    radio_result = True
                elif key == "6":
                    rows = _nfc_rows()
                    radio_result = True
                else:
                    rows = _radio_rows(cfg)
            except Exception as exc:
                # A radio hiccup must never kill the menu (the
                # pre-0.32 'GPIO busy' crash bounced straight home).
                rows = [("text", "RADIO ERROR", "warn"),
                        ("text", f"{type(exc).__name__}: {exc}"[:60],
                         "dim"),
                        ("text", "SAME KEY RETRIES · ANY KEY BACK",
                         "dim")]
                radio_result = True
            continue
        if key == "esc_hold":
            return _stop()
        if key in ("0", "q", "esc") and screen == "main":
            # 0 has always meant "back to the avatar"; a short
            # ESC/q tap means the same now (the Status screen's
            # only exits used to be 0, undocumented, or an
            # app-killing ESC). Exiting takes an ESC hold
            # (above) or the Stop menu item — never a tap.
            screen = "home"
            saying = avatar.saying()
            continue
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

                with ui.Spinner("FLIGHT RADAR", "asking the sky...",
                                abortable=True) as spinner:
                    r = flights.nearest(cfg)
                if spinner.stop_requested():
                    # The lookup is one HTTP call (20 s timeout) —
                    # a stop press lands as soon as it returns.
                    rows = [("big", "STOPPED", "warn"),
                            ("text", "lookup abandoned", "dim")]
                elif r["ok"]:
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
                    ui.radar_screen(
                        "FLIGHT RADAR", blips, frows,
                        right="ADS-B "
                        + r["center"]["source"].upper())
                    rows = frows
                else:
                    rows = [("text", "FLIGHT RADAR OFFLINE", "bad"),
                            ("text", r["reason"][:28], "dim")]
                _award("flights", r)
            elif key == "5":
                from . import proximity

                with ui.Spinner("PROXIMITY",
                                "listening for nearby radios...",
                                expected=25,
                                abortable=True) as spinner:
                    r = proximity.scan(
                        25, stop_check=spinner.stop_requested)
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
                _award("proximity", r)
            elif key == "6":
                from . import trackers

                with ui.Spinner("TRACKERS",
                                "listening for trackers (90s)...",
                                expected=90,
                                abortable=True) as spinner:
                    r = trackers.watch(
                        90, stop_check=spinner.stop_requested)
                if r["found"]:
                    rows = [("big", f"{r['heard']} TRACKERS",
                             "warn")]
                    for d in r["found"][:3]:
                        rows.append(("kv", d["kind"][:12],
                                     d["verdict"][:13],
                                     "warn" if "FOLLOW" in d["verdict"]
                                     else "text"))
                    title = "TRACKERS"
                else:
                    rows = [("big", "NO TRACKERS", "ok"),
                            ("kv", "IN HISTORY",
                             str(r["known_total"]), "dim"),
                            ("text", "none heard in 90s", "dim")]
                    title = "TRACKERS"
                _award("trackers", r)
            elif key == "7":
                from . import probes

                with ui.Spinner("PROBES",
                                "listening for probe requests...",
                                expected=60,
                                abortable=True) as spinner:
                    r = probes.run_probes(
                        60, cfg["capture_iface"],
                        stop_check=spinner.stop_requested)
                rows = [("big", f"{r['directed_devices']} DEVICES",
                         "gold" if r["directed_devices"] else "text"),
                        ("kv", "PROBES HEARD",
                         str(r["probes_total"]), "text"),
                        ("kv", "UNIQUE SSIDS",
                         str(r["unique_ssids"]), "text"),
                        ("kv", "TOP SSID",
                         (r["top_ssids"][0]["ssid"][:16]
                          if r["top_ssids"] else "—"), "gold")]
                title = "PROBES"
                _award("probes", r)
            elif key == "8":
                from . import gpslog

                with ui.Spinner("GPS TRACK",
                                "recording 2 min of sky...",
                                expected=120,
                                abortable=True) as spinner:
                    r = gpslog.track(
                        120,
                        progress=lambda m: setattr(spinner,
                                                   "message", m),
                        stop_check=spinner.stop_requested)
                if r["fix"]:
                    rows = [("big", f"{r['points']} POINTS", "gold"),
                            ("kv", "DISTANCE",
                             f"{r['distance_m']} M", "text"),
                            ("kv", "SATELLITES",
                             str(r["max_sats"]), "text"),
                            ("kv", "FILE", r["file"][:24], "dim")]
                else:
                    rows = [("big", "NO FIX", "warn"),
                            ("text", "no position in 2 min", "text"),
                            ("text", "GPS needs open sky", "dim")]
                if r.get("stopped"):
                    rows.append(("text",
                                 f"stopped at {r['seconds']}s — "
                                 "track saved", "dim"))
                title = "GPS TRACK"
                _award("gps", r)
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
                            expected=cfg["capture_seconds"],
                            abortable=True) as spinner:
                stats = capture.run_capture(
                    cfg["capture_seconds"], cfg["capture_iface"],
                    stop_check=spinner.stop_requested)
            rows = [("big", f"{stats['hashes']} HASHES",
                     "gold" if stats["hashes"] else "text"),
                    ("kv", "EAPOL MSGS", str(stats["eapol"]), "text"),
                    ("kv", "PCAP SAVED", f"{stats['bytes'] // 1024} KB",
                     "text")]
            if stats.get("stopped"):
                rows.append(("text",
                             f"stopped at {stats['seconds']}s — "
                             "capture saved", "dim"))
            title = "CAPTURE"
            _award("capture", stats)
            if cfg.get("wpasec_enabled"):
                from . import wpasec

                with ui.Spinner("WPA-SEC", "auto-sync...",
                                abortable=True) as spinner2:
                    r = wpasec.sync(
                        cfg, stop_check=spinner2.stop_requested)
                if r["ok"]:
                    _award("wpasec-sync", r)
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
                    ("text", "3 STOP · 4 FLIGHTS · 5 RADAR · 6 TRK",
                     "text"),
                    ("text", "9 back to page 1", "dim"),
                    ("kv", "WEB PORTAL",
                     f"{web.lan_ip()}:{web.PORT}", "gold")]
        elif key == "3":
            screen = "radio"
            title = "RADIO"
            rows = _radio_rows(cfg)
        elif key == "4":
            from . import wardrive

            with ui.Spinner("WARDRIVE", "scanning — GPS logging",
                            expected=cfg["wardrive_seconds"],
                            abortable=True) as spinner:
                stats = wardrive.run_wardrive(
                    cfg["wardrive_seconds"],
                    stop_check=spinner.stop_requested)
            rows = [("big", f"{stats['networks']} NETS", "gold"),
                    ("kv", "GPS FIX",
                     "YES" if stats["gps_fix"] else "NO — NEEDS SKY",
                     "ok" if stats["gps_fix"] else "warn")]
            if stats.get("stopped"):
                rows.append(("text", "stopped early — CSV saved",
                             "dim"))
            title = "WARDRIVE"
            _award("wardrive", stats)
        elif key == "5":
            from . import sniffer

            with ui.Spinner("SNIFF", "passive — Wi-Fi + BLE",
                            expected=cfg["sniff_seconds"],
                            abortable=True) as spinner:
                stats = sniffer.run_sniff(
                    cfg["sniff_seconds"],
                    stop_check=spinner.stop_requested)
            rows = [("big", f"{len(stats['hits'])} HITS",
                     "bad" if stats["hits"] else "ok"),
                    ("kv", "OBSERVED",
                     f"WI-FI {stats['wifi_obs']} · BLE {stats['ble_obs']}",
                     "text")]
            for hit in stats["hits"][:2]:
                rows.append(("text",
                             f"[{hit['confidence']}] {hit['label']}",
                             "warn"))
            if stats.get("stopped"):
                rows.append(("text", "stopped early — log saved",
                             "dim"))
            title = "SNIFF"
            _award("sniff", stats)
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

            with ui.Spinner("AUDIT", "starting...",
                            abortable=True) as spinner:
                stats = audit.run_audit(
                    cfg, progress=lambda m: setattr(spinner,
                                                    "message", m),
                    stop_check=spinner.stop_requested)
            rows = _audit_rows(stats)
            if stats.get("aborted"):
                rows.append(("text", "STOPPED — PARTIAL REPORT",
                             "warn"))
            title = "AUDIT"
            _award("audit", stats)
        # any other key: just redraw the current screen


if __name__ == "__main__":
    raise SystemExit(run())
