"""NFC probe — is the cap's ST25R3916 alive, and how do we reach it?

The CC1101 cap (U219) also carries an ST25R3916 NFC frontend.
Reaching it took three discoveries, all verified on hardware
2026-11-17:

1. **Its chip-select is GPIO22**, provided by a stock firmware
   overlay with a trap in its name: the file is
   `spi0-spidev2-gpio22-overlay.dtbo`, and the overlay only loads
   when config.txt (or the runtime `dtoverlay` command) uses the
   FULL name — the short form silently loads nothing. Loaded, it
   creates /dev/spidev0.2 on the shared SPI0 bus.
2. **It speaks SPI mode 1**, not mode 0. In mode 0 the identity
   register reads 0x15 — the true value bit-shifted by one, the
   classic wrong-clock-phase tell. In mode 1 it reads 0x2A.
3. **0x2A is the ST25R3916's IC identity** (register 0x3F: type
   bits 00101 + revision). The chip is present, powered by the
   cap's usual two-step gate, and answering.

This module is the probe only: identity + liveness. The full
driver (oscillator/regulator init, then ISO14443A inventory via
the chip's FIFO and direct commands, IRQ on GPIO23) is the next
NFC step.
"""

import subprocess
import time

SPIDEV_PATH = "/dev/spidev0.2"
IDENTITY_REG = 0x3F
ST25R3916_IDENTITY_MASK = 0xF8
ST25R3916_IDENTITY = 0x28


def ensure_spidev() -> bool:
    """Make sure /dev/spidev0.2 exists, loading the overlay live
    if the boot-time load didn't happen."""
    from pathlib import Path

    if Path(SPIDEV_PATH).exists():
        return True
    subprocess.run(["sudo", "-n", "dtoverlay",
                    "spi0-spidev2-gpio22-overlay"],
                   capture_output=True, timeout=15)
    time.sleep(0.5)
    return Path(SPIDEV_PATH).exists()


def probe() -> dict:
    """Power the cap and ask the NFC chip who it is."""
    import spidev
    from gpiozero import OutputDevice

    from .cc1101 import _rail_on, POWER_EN_GPIO

    result = {"spidev": ensure_spidev(), "identity": None,
              "found": False}
    if not result["spidev"]:
        return result
    _rail_on()
    pwr = OutputDevice(POWER_EN_GPIO)
    pwr.on()
    time.sleep(0.1)
    try:
        spi = spidev.SpiDev()
        spi.open(0, 2)
        spi.max_speed_hz = 1_000_000
        spi.mode = 1  # the 3916 samples on the falling edge — see header
        try:
            # Register read framing: 0b01 + 6-bit address, then data.
            reads = [spi.xfer2([0x40 | IDENTITY_REG, 0x00])[1]
                     for _ in range(3)]
        finally:
            spi.close()
    finally:
        pwr.off()
        pwr.close()
    result["identity"] = reads[0]
    result["stable"] = len(set(reads)) == 1
    result["found"] = (reads[0] & ST25R3916_IDENTITY_MASK) == ST25R3916_IDENTITY
    return result


def main() -> int:
    r = probe()
    if not r["spidev"]:
        print("NFC: /dev/spidev0.2 missing and overlay load failed")
        return 1
    if r["found"]:
        print(f"NFC: ST25R3916 FOUND — identity 0x{r['identity']:02X} "
              f"(stable across reads: {r['stable']})")
        return 0
    print(f"NFC: chip answered 0x{r['identity']:02X}, not the "
          "ST25R3916 identity — check seating/power")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
