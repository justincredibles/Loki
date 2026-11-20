# Display hat — 2.8" ILI9341 expansion screen

Status: **panel arrived 2026-11-19; jumper wiring in
progress.** The driver is pre-built on branch `tft-driver`
(caps.py "tft" profile, lokicz/ili9341.py, ui.py frame-size
parameter) pending hardware verification — SPI speed and
the init sequence still need the real panel to confirm.
Panel ordered by Justin 2026-11-18 — confirmed from his
own listing screenshots: the red V1.1 board below. Justin
is following the community "Cap TFT V2" build (MakerWorld
model 3235288, written for the Cardputer ADV); this doc
maps that build onto the Cardputer **Zero**.

## The panel

- HiLetgo 2.8" SPI TFT touch panel (Amazon ASIN B073R7BH1B),
  board silk: "2.8 TFT SPI 240X320 V1.1"
- Controller: **ILI9341**, 240×320 native, used **landscape
  320×240** — same width as the built-in screen, +70 rows
- Touch: resistive, XPT2046-class controller (U2 on the
  board), all five touch signals broken out on the header
- The board carries its **own 3.3 V regulator** (that's the
  "5V/3.3V" in the listing title), so VCC can be fed
  straight from the cap port's 5 V rail. The ADV build's
  external AMS1117 module is the alternative if a build
  wants the panel on a dedicated 3.3 V feed.
- Bonus on the back: a microSD slot (SD_CS / SD_MOSI /
  SD_MISO / SD_SCK pads). Unused by this design.

## How it plugs into the Zero

The hat uses the EXT cap port **instead of** a radio cap
(one cap at a time, as always). While it's fitted there is
no CC1101 and no LoRa — the existing wrong-cap guards in the
menus already handle that world.

The EXT port gives us SPI0 (the bus the built-in LCD and the
caps share), I2C1, a UART, and spare GPIOs. The Zero's EXT
header is silkscreen-labeled — confirmed from a photo of
Justin's own unit (2026-11-19), two rows of seven, left to
right as you look at the header:

- **Top row:** G26 · G23 · G22 · G11 CLK · G10 MO · G9 MI ·
  G7 CS1
- **Bottom row:** 5V IN · G · 5V OUT · G2 SDA · G3 SCL ·
  G14 TX · G15 RX

(The G-numbers are CM0 GPIOs: G11/G10/G9 = SPI0 SCLK/MOSI/
MISO, G7 = SPI0 CS1, G2/G3 = I2C1, G14/G15 = the UART pair,
G26 = POWER_EN, G = ground.) The module's 14-pin header, in
order (from the board's own silkscreen, confirmed on
Justin's unit photos), jumper-wires to those labels as
follows. **Meter the 5 V landings before first power** —
this is a hand-wired mod.

| # | Module pin | Goes to (EXT label) | Notes |
|---|---|---|---|
| 1 | VCC | 5V IN if it meters live, else 5V OUT | onboard regulator makes 3.3 V |
| 2 | GND | G | |
| 3 | CS | G7 CS1 → `/dev/spidev0.1` | the cap chip-select |
| 4 | RESET | G22 | free in this profile |
| 5 | DC | G23 | free in this profile |
| 6 | SDI (MOSI) | G10 MO | |
| 7 | SCK | G11 CLK | shared bus |
| 8 | LED | same 5 V landing as VCC | backlight always on, like the ADV build's BLK |
| 9 | SDO (MISO) | G9 MI | optional — driving is write-only |
| 10 | T_CLK | G11 CLK | touch, phase 2 |
| 11 | T_CS | G15 RX | touch, phase 2 |
| 12 | T_DIN | G10 MO | touch, phase 2 |
| 13 | T_DO | G9 MI | touch, phase 2 |
| 14 | T_IRQ | G14 TX | touch, phase 2 |

Power rule (learned the hard way in release 0.36): the cap
rail — GPIO26 `POWER_EN` plus the `ext_5v_out` rail — must be
switched on **once and held** for as long as lokicz runs.
Cycling cap power drags on the shared SPI0 bus and desyncs
the built-in panel; only a reboot revives it. The display
driver follows the same claim-once pattern as the radio code.

## Touch (phase 2)

The ADV build wires only the 8 display lines — no touch.
This module breaks all five touch signals out on the same
header (pins 10–14 above), so touch can be added later on
the same bus: T_CLK / T_DIN / T_DO share SPI0 with the
display, T_CS takes a spare GPIO (software chip-select, the
same trick the NFC overlay uses), T_IRQ another. Input
would map taps to on-screen zones; the keyboard stays the
primary input either way.

## Software plan

Pre-built on branch `tft-driver` (2026-11-19), headless-
verified with mocked spidev/lgpio; hardware verification
(SPI speed, init table, MADCTL orientation) happens at
bring-up, once the wiring is done.

- `caps.py`: a third profile `"tft"` alongside `cc1101` /
  `lora` — **done on `tft-driver`**. Selecting it is a
  config change + reboot, exactly like a cap swap. The
  profile parks the NFC overlay like `lora` does (GPIO22
  is the panel's RESET here), and meshtasticd stays off —
  `meshtastic.apply_profile`'s non-LoRa path already stops
  + disables it, so it needed no change.
- `lokicz/ili9341.py`: userspace driver in the house style —
  **written on `tft-driver`**. spidev on CS1 at 40 MHz (a
  constructor parameter), DC/RES through the raw-lgpio
  line owner from `cc1101.py` (gpiozero never frees lines;
  release 0.32), cap power via `cc1101._power_on()` (claim
  once, hold, never cycle), standard ILI9341 init with
  MADCTL set for landscape, RGB565 windowed writes, plus
  `fill()` and a color-bar `test_pattern()` for bring-up
  (`python3 -m lokicz.ili9341`). The UI already renders to
  a PIL image and packs RGB565 for the built-in panel, so
  the driver is a second sink for the same frames.
  A full 320×240 frame is 150 KB ≈ 31 ms at 40 MHz — fine
  for this app's pace.
- Big-screen layout: `ui.py`'s frame size is now a
  parameter (`set_screen_size()` / `TFT_SIZE`) — **done on
  `tft-driver`**, defaulting to 320×170 everywhere so all
  current call sites are unchanged. The 320×240 layout
  polish itself (home screen's avatar box grows ~148×150,
  sayings get a fifth line, data screens show more rows)
  lands at bring-up. The built-in LCD keeps mirroring the
  320×170 layout, so the device works the same with the
  hat on or off.
- Portal: `/api/screenshot.png` gains a `?screen=big`
  variant once the driver lands.

## Mechanical notes

- The ADV build's printed case targets the ADV body. The
  Zero's body and header position differ — expect to remix
  the case (K2 Pro + Fusion). The panel PCB (~50×69 mm)
  overhangs the device; that's the nature of this mod.
- M2×5 hardware and the 2×7P header come straight from the
  ADV build's BOM.
