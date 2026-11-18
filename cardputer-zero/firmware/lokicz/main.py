"""lokicz entry point.

Startup order:
1. Load the configured cap profile (cc1101 / lora / none).
2. Report the Wi-Fi situation honestly (recon yes, capture only if a
   USB dongle interface is configured).
3. Show status on the LCD; start the core services (TODO).

Run:  python -m lokicz.main [cap_profile]
"""

import os
import sys

from . import caps, ui, wifi_recon


def main() -> int:
    if "--menu" in sys.argv:
        from . import app

        return app.run()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    configured_cap = args[0] if args else os.environ.get("LOKICZ_CAP")
    profile = caps.detect_cap(configured_cap)
    capture_iface = os.environ.get("LOKICZ_CAPTURE_IFACE")  # USB dongle, if any

    lines = [
        "Loki — Cardputer Zero",
        f"cap: {profile.name}",
        "wifi recon: managed mode OK",
        "capture: " + ("USB dongle" if wifi_recon.capture_available(capture_iface)
                       else "unavailable (built-in radio)"),
    ]
    print("\n".join(lines))
    try:
        ui.show_text(lines)
    except OSError:
        print("(no framebuffer — not running on the device?)")

    # TODO: start job runner + web UI (Ragnar-style tools land here).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
