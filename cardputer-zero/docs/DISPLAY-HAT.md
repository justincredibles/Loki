# Display hat — 2.8" ILI9341 expansion screen

Status: **design** (2026-11-18). Justin is following the
community "Cap TFT V2" build (MakerWorld model 3235288,
written for the Cardputer ADV) with a HiLetgo 2.8" SPI panel.
This doc maps that build onto the Cardputer **Zero** and plans
the lokicz support. No code ships until the panel is in hand —
SPI speed and the init sequence need hardware to verify.

## The panel

- HiLetgo 2.8" SPI TFT touch panel (Amazon ASIN B073R7BH1B)
- Controller: **ILI9341**, 240×320 native, used **landscape
  320×240** — same width as the built-in screen, +70 rows
- Touch: resistive, XPT2046-class controller (phase 2, below)
- Logic: 3.3 V. The module wants a real 3.3 V feed, which is
  why the ADV build carries an **AMS1117-3.3** step-down
  module off the cap port's 5 V rail. Same approach here.

## How it plugs into the Zero

The hat uses the EXT cap port **instead of** a radio cap
(one cap at a time, as always). While it's fitted there is
no CC1101 and no LoRa — the existing wrong-cap guards in the
menus already handle that world.

The EXT port gives us SPI0 (the bus the built-in LCD and the
caps share), I2C1, a UART, and spare GPIOs. Wiring, by signal
name — match the physical header positions to the EXT pinout
and **meter the 5 V / GND positions before first power**;
this is a hand-wired mod.

| Display pin | Goes to | Notes |
|---|---|---|
| GND | EXT GND | |
| VCC | AMS1117 VOUT (3.3 V) | |
| SCL | SPI0 SCLK | shared bus |
| SDA | SPI0 MOSI | display is write-only here |
| RES | GPIO22 | free in this profile |
| DC | GPIO23 | free in this profile |
| CS | SPI0 CS1 (GPIO7) → `/dev/spidev0.1` | the cap chip-select |
| BLK | AMS1117 VOUT | backlight always on, like the ADV build |
| AMS1117 VIN | EXT 5 V | the gated cap rail — see power rule |
| AMS1117 GND | EXT GND | |

Power rule (learned the hard way in release 0.36): the cap
rail — GPIO26 `POWER_EN` plus the `ext_5v_out` rail — must be
switched on **once and held** for as long as lokicz runs.
Cycling cap power drags on the shared SPI0 bus and desyncs
the built-in panel; only a reboot revives it. The display
driver follows the same claim-once pattern as the radio code.

## Touch (phase 2)

The ADV build wires only the 8 display lines — no touch.
The panel's touch side can be added later on the same bus:
T_CLK → SCLK, T_DIN → MOSI, T_DO → MISO (MISO is present on
the cap bus), T_CS → GPIO15 (software chip-select, the same
trick the NFC overlay uses), T_IRQ → GPIO14. Input would map
taps to on-screen zones; the keyboard stays the primary
input either way.

## Software plan

- `caps.py`: a third profile `"tft"` alongside `cc1101` /
  `lora`. Selecting it is a config change + reboot, exactly
  like a cap swap.
- `lokicz/ili9341.py`: userspace driver in the house style —
  spidev on CS1 at 32–48 MHz, DC/RES through the raw-lgpio
  line owner from `cc1101.py` (gpiozero never frees lines;
  release 0.32), standard ILI9341 init with MADCTL set for
  landscape, RGB565 windowed writes. The UI already renders
  to a PIL image and packs RGB565 for the built-in panel, so
  the driver is a second sink for the same frames.
  A full 320×240 frame is 150 KB ≈ 31 ms at 40 MHz — fine
  for this app's pace.
- Big-screen layout: `ui.py`'s frame size becomes a
  parameter instead of a hard-coded 320×170. At 320×240 the
  home screen's avatar box grows (~148×150), sayings get a
  fifth line, and data screens show more rows. The built-in
  LCD keeps mirroring the 320×170 layout, so the device
  works the same with the hat on or off.
- Portal: `/api/screenshot.png` gains a `?screen=big`
  variant once the driver lands.

## Mechanical notes

- The ADV build's printed case targets the ADV body. The
  Zero's body and header position differ — expect to remix
  the case (K2 Pro + Fusion). The panel PCB (~50×69 mm)
  overhangs the device; that's the nature of this mod.
- M2×5 hardware and the 2×7P header come straight from the
  ADV build's BOM.
