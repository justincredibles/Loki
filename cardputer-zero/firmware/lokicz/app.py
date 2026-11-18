"""The on-device menu app — lokicz you can drive from the keyboard.

Screens wear the Asgard theme (ui.py): a status board with labeled
readouts, the menu as a 3x3 grid of key chips, big gold result
numbers, and an animated progress screen for long operations. The
46-key board makes navigation simple: every chip is a digit, you
press the digit. Pressing "Stop" exits the app (under systemd it
stays stopped until started again — `sudo systemctl start lokicz`
brings it back).
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


def _chips(cfg: dict) -> list:
    cap_tone = "text" if cfg.get("capture_enabled", True) else "off"
    return [("1", "STATUS"), ("2", "CAPTURE", cap_tone),
            ("3", "SUB-GHZ"), ("4", "WARDRIVE"), ("5", "SNIFF"),
            ("6", "MESH"), ("7", "STOP"), ("8", "CAP TGL"),
            ("9", "WPA-SEC")]


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


def _screen(rows: list, cfg: dict, title: str = "LOKI",
            chips: bool = True) -> str:
    """Draw a screen (menu chips as the footer); return the key."""
    ui.show_screen(title, rows,
                   chips=_chips(cfg) if chips else None,
                   right="CAP " + cfg["cap"].upper())
    return ui.read_key()


def run() -> int:
    cfg = config.load()
    try:
        ui.splash()
    except OSError:
        pass
    rows = _status_rows(cfg)
    title = "LOKI"
    screen = "main"
    while True:
        key = _screen(rows, cfg, title=title,
                      chips=(screen == "main"))
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
            screen = "wpasec"
            title = "WPA-SEC"
            rows = _wpasec_rows(cfg)
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
        elif key in ("7", "q", "esc"):
            ui.show_screen("LOKI", [
                ("gap", 14),
                ("big", "GODSPEED", "gold"),
                ("text", "lokicz stopped — restart with", "dim"),
                ("text", "sudo systemctl start lokicz", "text"),
            ], right="")
            return 0
        # any other key: just redraw the current screen


if __name__ == "__main__":
    raise SystemExit(run())
