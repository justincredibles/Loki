"""ILI9341 display-hat driver — the 2.8" SPI touch panel.

Plain-English tour:
- The hat is a HiLetgo 2.8" SPI TFT (board silk "2.8 TFT SPI
  240X320 V1.1", controller ILI9341) jumper-wired onto the EXT
  cap port INSTEAD of a radio cap — see docs/DISPLAY-HAT.md for
  the wiring map. It is the "tft" cap profile in caps.py.
- The panel is native portrait 240x320; we run it landscape
  320x240 via the MADCTL row/column-exchange bit, so frames are
  the same 320-wide shape ui.py already draws, just 70 rows
  taller than the built-in LCD.
- Talk is SPI0 chip-select 1 (/dev/spidev0.1 — the cap CS line,
  header label G7 CS1) plus two plain GPIO lines: DC (GPIO23,
  header G23) picks command vs data bytes, RESET (GPIO22,
  header G22) is the panel's hardware reset.
- Power is the cap power, with the release-0.36 rule: the EXT
  5V rail + GPIO26 POWER_EN go on ONCE and stay on (shared with
  cc1101._power_on — claim-or-borrow, never cycled). An
  unpowered device drags on the shared SPI0 bus and desyncs
  the built-in LCD; only a reboot revives it.

STATUS: pre-built on branch tft-driver (2026-11-19) before the
panel was wired, and verified headless with mocked spidev/lgpio
(init order + frame packing). TODO-VERIFY on real hardware:
the 40 MHz SPI clock, the MADCTL orientation value (flip bits
if the image lands rotated/mirrored), and the gamma/init table
against this exact clone panel.
"""

import time

# --- Wiring (docs/DISPLAY-HAT.md; header labels from the unit) -------------
SPIDEV_PATH = "/dev/spidev0.1"  # SPI0 CS1 — EXT header "G7 CS1"
DC_GPIO = 23                     # EXT header "G23"
RESET_GPIO = 22                  # EXT header "G22"

WIDTH, HEIGHT = 320, 240         # landscape surface
DEFAULT_SPEED_HZ = 40_000_000
DATA_CHUNK = 4096                # spidev's per-transfer buffer ceiling

# --- Commands ----------------------------------------------------------------
SWRESET, SLPOUT, DISPON = 0x01, 0x11, 0x29
CASET, RASET, RAMWR = 0x2A, 0x2B, 0x2C
MADCTL, COLMOD = 0x36, 0x3A

# MADCTL bits: MY 0x80 (row flip), MX 0x40 (column flip),
# MV 0x20 (row/column exchange = landscape), BGR 0x08 (these
# clone panels are BGR-ordered). 0x28 = MV|BGR is the standard
# landscape starting point; orientation flips are the expected
# hardware bring-up tweak, so the value is a constructor knob.
MADCTL_LANDSCAPE = 0x28

# Standard ILI9341 power/gamma bring-up (the widely used
# reference table for these modules — Adafruit-lineage values).
# (command, data...) pairs, sent in order after the reset.
INIT_SEQUENCE = [
    (0xEF, (0x03, 0x80, 0x02)),          # power control (undocumented)
    (0xCF, (0x00, 0xC1, 0x30)),          # Power control B
    (0xED, (0x64, 0x03, 0x12, 0x81)),    # Power on sequence
    (0xE8, (0x85, 0x00, 0x78)),          # Driver timing A
    (0xCB, (0x39, 0x2C, 0x00, 0x34, 0x02)),  # Power control A
    (0xF7, (0x20,)),                     # Pump ratio control
    (0xEA, (0x00, 0x00)),                # Driver timing B
    (0xC0, (0x23,)),                     # Power control 1 (VRH)
    (0xC1, (0x10,)),                     # Power control 2 (SAP)
    (0xC5, (0x3E, 0x28)),                # VCM control
    (0xC7, (0x86,)),                     # VCM control 2
    (0xB1, (0x00, 0x18)),                # Frame rate control
    (0xB6, (0x08, 0x82, 0x27)),          # Display function control
    (0xF2, (0x00,)),                     # 3-gamma function disable
    (0x26, (0x01,)),                     # Gamma curve select
    (0xE0, (0x0F, 0x31, 0x2B, 0x0C, 0x0E, 0x08, 0x4E, 0xF1,
            0x37, 0x07, 0x10, 0x03, 0x0E, 0x09, 0x00)),  # +gamma
    (0xE1, (0x00, 0x0E, 0x14, 0x03, 0x11, 0x07, 0x31, 0xC1,
            0x48, 0x08, 0x0F, 0x0C, 0x31, 0x36, 0x0F)),  # -gamma
]


def pack_rgb565(img) -> bytes:
    """Pack an RGB Pillow image into little-endian RGB565 bytes.

    Same math as ui._to_rgb565, sized from the image itself —
    a 320x240 frame packs to exactly 153600 bytes.
    """
    rgb = img.convert("RGB")
    try:
        import numpy as np

        a = np.asarray(rgb, dtype=np.uint16)
        v = ((a[:, :, 0] >> 3) << 11) | ((a[:, :, 1] >> 2) << 5) \
            | (a[:, :, 2] >> 3)
        return v.astype("<u2").tobytes()
    except Exception:
        pass  # fall through to the slow packer
    data = rgb.tobytes()
    npix = rgb.width * rgb.height
    out = bytearray(npix * 2)
    for i in range(npix):
        r, g, b = data[3 * i], data[3 * i + 1], data[3 * i + 2]
        v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        out[2 * i] = v & 0xFF
        out[2 * i + 1] = v >> 8
    return bytes(out)


class ILI9341:
    """The fitted display hat, powered and talking.

    Use as a context manager:

        with ILI9341() as tft:
            tft.show(frame_image)
    """

    def __init__(self, speed_hz: int = DEFAULT_SPEED_HZ,
                 madctl: int = MADCTL_LANDSCAPE) -> None:
        self.speed_hz = speed_hz
        self.madctl = madctl
        self.width, self.height = WIDTH, HEIGHT
        self._spi = None
        self._dc = None
        self._reset = None

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "ILI9341":
        import spidev

        from .cc1101 import _Line, _power_on

        # Cap power first, held for the life of the process —
        # claim-or-borrow, never cycled (see module docstring).
        _power_on()

        # _Line claims the GPIO as an output at level 0, so DC
        # starts in "command" and RESET starts asserted (low).
        self._dc = _Line(DC_GPIO)
        self._reset = _Line(RESET_GPIO)
        try:
            self._spi = spidev.SpiDev()
            self._spi.open(0, 1)  # /dev/spidev0.1
            self._spi.max_speed_hz = self.speed_hz
            self._spi.mode = 0
            self._init_panel()
        except Exception:
            self.close()
            raise
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        """Release SPI and the two panel-private GPIO lines.

        Cap POWER is deliberately NOT dropped here — _power_on()
        holds it for the life of the process. Cutting cap power
        freezes the built-in LCD (release 0.36). DC/RESET belong
        to this panel alone, so freeing them is safe.
        """
        if self._spi is not None:
            try:
                self._spi.close()
            except Exception:
                pass
            self._spi = None
        for line in (self._dc, self._reset):
            if line is not None:
                line.close()
        self._dc = self._reset = None

    # -- SPI primitives ------------------------------------------------------
    def _cmd(self, cmd: int) -> None:
        self._dc.off()
        self._spi.xfer2([cmd])

    def _data(self, data) -> None:
        self._dc.on()
        buf = bytes(data)
        for i in range(0, len(buf), DATA_CHUNK):
            self._spi.writebytes(buf[i:i + DATA_CHUNK])

    def command(self, cmd: int, *data: int) -> None:
        """Send one command byte, then its data bytes (if any)."""
        self._cmd(cmd)
        if data:
            self._data(data)

    # -- panel bring-up --------------------------------------------------------
    def _reset_pulse(self) -> None:
        # _Line claimed RESET at 0 (asserted). Hold, release,
        # then give the controller its full wake-up time.
        time.sleep(0.02)
        self._reset.on()
        time.sleep(0.12)

    def _init_panel(self) -> None:
        self._reset_pulse()
        for cmd, data in INIT_SEQUENCE:
            self.command(cmd, *data)
        self.command(MADCTL, self.madctl)
        self.command(COLMOD, 0x55)  # 16-bit RGB565 pixels
        self.command(SLPOUT)
        time.sleep(0.12)
        self.command(DISPON)

    # -- drawing ---------------------------------------------------------------
    def set_window(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Address window, inclusive corners, in landscape coords."""
        self.command(CASET, (x0 >> 8) & 0xFF, x0 & 0xFF,
                     (x1 >> 8) & 0xFF, x1 & 0xFF)
        self.command(RASET, (y0 >> 8) & 0xFF, y0 & 0xFF,
                     (y1 >> 8) & 0xFF, y1 & 0xFF)

    def show(self, img) -> None:
        """Push a full frame — the same PIL image ui.py produces.

        Converted to RGB and resized to the panel surface if it
        isn't already 320x240, then streamed as one windowed
        RAMWR write of packed RGB565.
        """
        frame = img.convert("RGB")
        if frame.size != (self.width, self.height):
            frame = frame.resize((self.width, self.height))
        self.set_window(0, 0, self.width - 1, self.height - 1)
        self._cmd(RAMWR)
        self._data(pack_rgb565(frame))

    def fill(self, rgb: tuple) -> None:
        """Fill the whole panel with one (r, g, b) color."""
        r, g, b = rgb
        v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        pixel = bytes((v & 0xFF, v >> 8))
        self.set_window(0, 0, self.width - 1, self.height - 1)
        self._cmd(RAMWR)
        self._data(pixel * (self.width * self.height))

    def test_pattern(self) -> None:
        """Color bars + border + diagonals — the bring-up picture.

        If this lands sharp and correctly oriented, the wiring,
        init table and MADCTL are all right; if it's rotated or
        mirrored, only MADCTL needs to change.
        """
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (self.width, self.height), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        bars = [(255, 255, 255), (255, 255, 0), (0, 255, 255),
                (0, 255, 0), (255, 0, 255), (255, 0, 0),
                (0, 0, 255), (0, 0, 0)]
        bw = self.width // len(bars)
        for i, color in enumerate(bars):
            draw.rectangle([i * bw, 0, (i + 1) * bw - 1,
                            self.height - 1], fill=color)
        draw.rectangle([0, 0, self.width - 1, self.height - 1],
                       outline=(255, 255, 255), width=3)
        draw.line([(0, 0), (self.width - 1, self.height - 1)],
                  fill=(0, 0, 0), width=2)
        draw.line([(0, self.height - 1), (self.width - 1, 0)],
                  fill=(0, 0, 0), width=2)
        self.show(img)


def main() -> int:
    """Bring-up check: `python3 -m lokicz.ili9341 [--fill RRGGBB]`.

    Default: init the panel and show the test pattern. Run with
    the lokicz service stopped (the panel's GPIO lines are
    claimed per-process).
    """
    import sys

    with ILI9341() as tft:
        if "--fill" in sys.argv:
            hexv = sys.argv[sys.argv.index("--fill") + 1]
            rgb = tuple(int(hexv[i:i + 2], 16) for i in (0, 2, 4))
            tft.fill(rgb)
            print(f"ILI9341 filled {hexv}")
        else:
            tft.test_pattern()
            print("ILI9341 test pattern shown — check orientation: "
                  "white bar at the LEFT, border square, X diagonals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
