"""The on-device menu app — lokicz you can drive from the keyboard.

Screens are plain text on the LCD for now (the Pwnagotchi-style
face is a later polish step). The 46-key board makes navigation
simple: every screen lists numbered actions, you press the number.
Pressing the digit for "Stop lokicz" exits the app (under systemd
it stays stopped until started again — `sudo systemctl start
lokicz` brings it back).
"""

import glob
import os

from . import caps, capture, config, ui, wifi_recon


def _total_hashes() -> int:
    total = 0
    for path in glob.glob(str(capture.CAPTURE_DIR / "*.hc22000")):
        try:
            total += len(open(path).read().splitlines())
        except OSError:
            pass
    return total


def _status_lines(cfg: dict) -> list[str]:
    from . import wpasec

    profile = caps.detect_cap(cfg["cap"])
    dongle = ("dongle ready"
              if wifi_recon.capture_available(cfg["capture_iface"])
              else "dongle missing")
    w = wpasec.status(cfg)
    return [
        "Loki — Cardputer Zero",
        f"cap: {profile.name}",
        "wifi recon: managed mode OK",
        "capture: " + ("ON" if cfg.get("capture_enabled", True)
                       else "OFF") + f" · {dongle}",
        f"hashes caught (all runs): {_total_hashes()}",
        "wpa-sec: " + ("ON" if w["enabled"] else "OFF")
        + (f" · {w['cracked']} cracked" if w["enabled"] else ""),
    ]


def _wpasec_lines(cfg: dict) -> list[str]:
    from . import wpasec

    w = wpasec.status(cfg)
    return [
        "WPA-SEC — wpa-sec.stanev.org",
        "auto-sync: " + ("ON" if w["enabled"] else "OFF"),
        "api key: " + ("set" if w["key_set"] else "NOT set"),
        f"captures to upload: {w['pending']}",
        f"cracked passwords: {w['cracked']}",
        "",
        "9 on/off   0 sync now",
        "any other key: back",
    ]


def _screen(lines: list[str], cfg: dict) -> str:
    """Draw a screen with the menu footer; return the key pressed."""
    ui.show_text(lines + ["", "1 Status  2 Capture  3 Sub-GHz",
                          "4 Wardrive  5 Sniff  6 Mesh",
                          "7 Stop  8 Capture on/off",
                          "9 WPA-SEC"])
    return ui.read_key()


def run() -> int:
    cfg = config.load()
    lines = _status_lines(cfg)
    screen = "main"
    while True:
        key = _screen(lines, cfg)
        if screen == "wpasec":
            # WPA-SEC screen has its own keys; anything else goes back.
            from . import wpasec

            if key == "9":
                cfg["wpasec_enabled"] = not cfg.get("wpasec_enabled",
                                                    False)
                config.save(cfg)
                lines = _wpasec_lines(cfg)
            elif key == "0":
                ui.show_text(["WPA-SEC syncing...", "upload + download"])
                r = wpasec.sync(cfg)
                if r["ok"]:
                    lines = ["WPA-SEC sync done",
                             f"uploaded: {r['uploaded']}",
                             f"cracked: {r['cracked_total']} total "
                             f"(+{r['cracked_new']} new)"]
                else:
                    lines = ["WPA-SEC sync failed",
                             r.get("reason",
                                   f"{r.get('failures', 0)} step(s) failed")]
                screen = "main"
            else:
                screen = "main"
                lines = _status_lines(cfg)
            continue
        if key == "1":
            lines = _status_lines(cfg)
        elif key == "2":
            if not cfg.get("capture_enabled", True):
                lines = ["Capture is OFF",
                         "press 8 to turn it on"]
                continue
            ui.show_text([f"Capturing {cfg['capture_seconds']}s on "
                          f"{cfg['capture_iface']}...", "",
                          "deauth: disabled (default)"])
            stats = capture.run_capture(cfg["capture_seconds"],
                                         cfg["capture_iface"])
            lines = ["Capture done",
                     f"hashes: {stats['hashes']}  EAPOL: {stats['eapol']}",
                     f"pcap: {stats['bytes'] // 1024} KB saved"]
            if cfg.get("wpasec_enabled"):
                from . import wpasec

                ui.show_text(["WPA-SEC auto-sync..."])
                r = wpasec.sync(cfg)
                if r["ok"]:
                    lines.append(f"wpa-sec: +{r['uploaded']} up, "
                                 f"{r['cracked_total']} cracked")
                else:
                    lines.append("wpa-sec: " + r.get(
                        "reason", "sync had failures"))
        elif key == "8":
            cfg["capture_enabled"] = not cfg.get("capture_enabled", True)
            config.save(cfg)
            lines = _status_lines(cfg)
        elif key == "9":
            screen = "wpasec"
            lines = _wpasec_lines(cfg)
        elif key == "3":
            ui.show_text(["Sub-GHz sweep...", "listening on both bands"])
            from .cc1101 import CC1101

            with CC1101() as radio:
                out = []
                for start, stop in ((430.0, 437.0), (902.0, 928.0)):
                    sweep = radio.sweep(start, stop, 0.5, dwell_s=0.05)
                    floor = sorted(r for _, r in sweep)[len(sweep) // 2]
                    peak_f, peak_r = max(sweep, key=lambda t: t[1])
                    out.append(f"{start:.0f}-{stop:.0f} MHz floor "
                               f"{floor:.0f} peak {peak_r:.0f}@{peak_f:.0f}")
            lines = ["Sub-GHz sweep done"] + out
        elif key == "4":
            from . import wardrive

            ui.show_text(["Wardriving...",
                          f"{cfg['wardrive_seconds']}s — scanning"])
            stats = wardrive.run_wardrive(cfg["wardrive_seconds"])
            lines = ["Wardrive done",
                     f"networks: {stats['networks']}",
                     "GPS: " + ("had fix" if stats["gps_fix"]
                                else "no fix (needs LoRa cap)")]
        elif key == "5":
            from . import sniffer

            ui.show_text(["Sniffing (passive)...",
                          f"{cfg['sniff_seconds']}s — Wi-Fi + BLE"])
            stats = sniffer.run_sniff(cfg["sniff_seconds"])
            lines = ["Sniff done",
                     f"hits: {len(stats['hits'])} "
                     f"(Wi-Fi {stats['wifi_obs']} / BLE {stats['ble_obs']})"]
            for hit in stats["hits"][:3]:
                lines.append(f"[{hit['confidence']}] {hit['label']}")
        elif key == "6":
            from . import meshtastic

            s = meshtastic.status()
            lines = ["Meshtastic",
                     "daemon: " + ("installed" if s["installed"]
                                   else "NOT installed"),
                     "service: " + ("active" if s["service"]
                                    else "stopped (cap profile)"),
                     "radio: " + ("SX1262 proven" if s["radio"]
                                  else "not proven")]
        elif key in ("7", "q", "esc"):
            ui.show_text(["lokicz stopped.", "",
                          "sudo systemctl start lokicz", "to bring it back"])
            return 0
        # any other key: just redraw the current screen


if __name__ == "__main__":
    raise SystemExit(run())
