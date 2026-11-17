# Cardputer Zero hardware — the facts this fork is built on

Plain-English notes with the exact values the firmware needs. Full sourcing
for every claim is in `RESEARCH.md` (same folder).

## The device

| Part | What it is |
|---|---|
| Brain | Raspberry Pi Compute Module 0 (CM0): RP3A0 chip, quad-core Cortex-A53 @ 1 GHz |
| RAM | 512 MB — this is the ceiling for everything; keep services lean |
| Storage / OS | microSD card; M5Stack's Raspberry Pi OS (Debian, 64-bit) image |
| Screen | 1.9″ colour LCD, 320 × 170, ST7789v3 controller |
| Keyboard | 46 keys, TCA8418 controller — shows up as a normal Linux keyboard (evdev) |
| Wi-Fi / Bluetooth | Cypress **CYW43439** combo chip (2.4 GHz Wi-Fi, BT 5.0) — **no nexmon patch exists for this chip** |
| Ethernet | Built-in 10/100 port (USB-attached internally) — handy for Ragnar-style LAN work |
| USB | 1 × USB-A host port (this is where a monitor-mode Wi-Fi dongle would go), USB-C for power/data |
| Battery | 3.7 V, 1750 mAh LiPo |
| Also on board | IR transmitter + receiver, speaker + mic, Grove port |

### Screen and keys from Python (already solved problems)

- The LCD is exposed as a Linux **framebuffer**: `/dev/fb_lcd`
  (driver `fb_st7789v`). Draw with Pillow, push the image to the framebuffer —
  no special display library needed.
- The keyboard arrives as a standard **evdev** input device — read it with
  `python-evdev` like any USB keyboard.

## The expansion port (where the caps plug in)

One 14-pin header on top of the device ("EXT" / Cap bus). Both caps share:

- **SPI0** — the same SPI bus the LCD uses. The screen is chip-select 0,
  caps are **chip-select 1 (CM0 GPIO7)**, so screen and cap can share the bus.
- I2C1 (GPIO2/GPIO3), a UART (GPIO14/GPIO15), and a few spare GPIOs.
- **Only one cap fits at a time**, and they are not hot-swappable.
  The firmware must detect/decide which cap is fitted and load that profile.

## Cap CC1101 (M5Stack SKU U219)

Two radios in one cap:

| Radio | Chip | Notes |
|---|---|---|
| Sub-GHz | TI **CC1101** | 315 / 433 / 868 / 915 MHz via RF switches on the cap; +10 dBm |
| NFC / RFID | ST **ST25R3916** | ISO14443A/B, FeliCa, ISO15693, card emulation |

Verified connections (from the CardputerZero org's own working SubG-Chat app):

- CC1101 appears as **`/dev/spidev0.1`** (SPI0, kernel chip-select 1).
- Cap power enable: **GPIO26** (`POWER_EN`) — the cap does nothing until this
  is switched on.
- The NFC chip sits behind a **GPIO22 chip-select** device-tree overlay
  (it shares the SPI bus but is not on the kernel's CS1 line).
- ⚠️ Still unverified: the CC1101's GDO0 interrupt pin assignment (evidence
  points at the GPIO14/GPIO15 pair) and one RF-switch control line. Confirm
  on hardware before relying on interrupt-driven receive.

## Cap LoRa-1262 (M5Stack SKU U214)

| Part | Chip | Notes |
|---|---|---|
| LoRa radio | Semtech **SX1262** | One wideband 868–923 MHz design — the region (e.g. US915) is a **software setting**, not a different board |
| Output | +22 dBm | **An antenna on the RP-SMA connector is mandatory** — transmitting into no antenna can damage the radio |
| GPS | ATGM336H | Shows up as a serial device on **`/dev/ttyS0`** |

Verified connections (probed on real hardware by the zeroradio project,
which runs native `meshtasticd` on this cap):

- Data/control interrupt **DIO1 = GPIO23**
- **BUSY = GPIO22**
- **RESET is not wired** — the firmware cannot hardware-reset the radio;
  recover by re-initialising over SPI.
- **TCXO configuration is mandatory** — the radio's reference oscillator is a
  temperature-compensated one (TCXO); the driver must be told, or the radio
  misbehaves. (meshtasticd/RadioLib handle this when configured.)
- The antenna RF switch is controlled through an I2C I/O expander
  (**PI4IOE5V6408 at I2C address 0x43, pin P0 held high**).

## The Wi-Fi limitation (the big one)

- Chip: **CYW43439**. Nexmon (the firmware-patch project that gives Pi
  Zero 2 W its monitor mode) supports the Zero 2 W's `bcm43436b0` — it has
  **no CYW43439 patch**. Kali's packaged nexmon builds likewise don't cover it.
- Consequence: **no monitor mode, no frame injection** on the built-in radio.
  No handshake capture, no PMKID harvesting, no deauth — from the internal
  antenna, ever, unless someone writes a new nexmon port.
- Workaround: a **USB Wi-Fi adapter that supports monitor mode/injection**
  in the USB-A port (the RaspyJack pattern). The firmware's Wi-Fi layer is
  written so the capture interface is a setting, not an assumption.
- Sanity check on your unit: `dmesg | grep -i brcmfmac` — expect a
  `brcmfmac43439` firmware line.
