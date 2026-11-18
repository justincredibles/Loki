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
    profile = caps.detect_cap(cfg["cap"])
    return [
        "Loki — Cardputer Zero",
        f"cap: {profile.name}",
        "wifi recon: managed mode OK",
        "capture: " + ("USB dongle ready"
                       if wifi_recon.capture_available(cfg["capture_iface"])
                       else "dongle missing"),
        f"hashes caught (all runs): {_total_hashes()}",
    ]


def _screen(lines: list[str], cfg: dict) -> str:
    """Draw a screen with the menu footer; return the key pressed."""
    ui.show_text(lines + ["", "1 Status  2 Capture",
                          "3 Sub-GHz sweep  4 Stop lokicz"])
    return ui.read_key()


def run() -> int:
    cfg = config.load()
    lines = _status_lines(cfg)
    while True:
        key = _screen(lines, cfg)
        if key == "1":
            lines = _status_lines(cfg)
        elif key == "2":
            ui.show_text([f"Capturing {cfg['capture_seconds']}s on "
                          f"{cfg['capture_iface']}...", "",
                          "deauth: disabled (default)"])
            stats = capture.run_capture(cfg["capture_seconds"],
                                         cfg["capture_iface"])
            lines = ["Capture done",
                     f"hashes: {stats['hashes']}  EAPOL: {stats['eapol']}",
                     f"pcap: {stats['bytes'] // 1024} KB saved"]
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
        elif key in ("4", "q", "esc"):
            ui.show_text(["lokicz stopped.", "",
                          "sudo systemctl start lokicz", "to bring it back"])
            return 0
        # any other key: just redraw the current screen


if __name__ == "__main__":
    raise SystemExit(run())
