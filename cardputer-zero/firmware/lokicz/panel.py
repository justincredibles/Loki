"""LCD panel recovery (Cardputer Zero).

The LCD is a MIPI-DBI panel on SPI0 (device spi0.0) — the SAME bus
as the radio caps (CC1101 on spi0.1, NFC on spi0.2). After any
CC1101 radio session the panel stops accepting frame updates: the
app keeps drawing, other SPI devices keep answering, but the glass
holds its last frame until the panel driver is rebound or the
device reboots. Found the hard way on 2026-11-18: every screen
after a capture looked 'frozen' (the countdown's last frame, the
home screen as a still photo) while the app sat healthy behind
it — stack dumps showed it waiting for keys the whole time.

reset() unbinds and rebinds the panel driver, which fully
re-initializes the panel (~2 s, one brief black flash). lokicz
calls it after every radio operation, before drawing the result,
so the result is actually visible. Harmless when the panel is
healthy.
"""

import subprocess
import time
from pathlib import Path

_DRIVER = Path("/sys/bus/spi/drivers/panel-mipi-dbi-spi")
_DEVICE = "spi0.0"
_FB = Path("/dev/fb_lcd")


def reset() -> bool:
    """Re-initialize the LCD panel. True if the framebuffer is back."""
    try:
        for action in ("unbind", "bind"):
            subprocess.run(
                ["sudo", "-n", "tee", str(_DRIVER / action)],
                input=_DEVICE.encode(), capture_output=True,
                timeout=10, check=True)
            time.sleep(0.7)
        # The bind recreates /dev/fb0 (and the fb_lcd symlink); wait
        # for the node so the next draw doesn't race it.
        for _ in range(30):
            if _FB.exists():
                return True
            time.sleep(0.1)
    except Exception:
        pass
    return False
