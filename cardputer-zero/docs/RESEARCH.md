# Loki → Cardputer Zero Fork — Platform Research

Researched: 2026-11-17. Purpose: scope a fork of the Loki pocket security multi-tool
(Pwnagotchi + Bjorn/Ragnar concepts) for the M5Stack Cardputer Zero, using the
Cap CC1101 and Cap LoRa expansion caps.

**Method note:** Specs are taken from M5Stack's official docs/shop pages,
Raspberry Pi's CM0 product page and datasheet, the `CardputerZero` and `m5stack`
GitHub orgs, and projects that have run code on the real hardware (zeroradio,
Cap-CC1101-SubG-Chat). Anything that could not be verified is flagged
⚠️ UNVERIFIED rather than guessed.

---

## TL;DR — Platform verdict

- The Cardputer Zero is **not an ESP32 device**. It is a pocket **Linux computer**
  built on a **Raspberry Pi Compute Module 0 (CM0)** — RP3A0 SiP (Broadcom
  BCM2710A1 die), quad-core Cortex-A53 @ 1 GHz, 512 MB LPDDR2, booting
  Raspberry Pi OS / Debian (aarch64) from microSD. There is no firmware to flash
  and no Arduino/UiFlow target on this device, despite the caps' docs pages
  listing Arduino/UiFlow2 (that support targets the ESP32-based Cardputer-Adv).
- **The fork is therefore a Linux/Python port**, architecturally a sibling of
  Loki's existing Pi-side codebase — not a Bruce-style ESP32 firmware. Bruce,
  Marauder, NEMO, Evil-M5 and the Flipper-Zero port **do not run on the Zero**
  (all are ESP32-S3 firmware for the original Cardputer / Cardputer-Adv).
- **Top blocker:** the CM0's Wi-Fi chip is a **Cypress CYW43439** (per the current
  CM0 datasheet), *not* the Pi Zero 2 W's BCM43436. **Nexmon has no patch for the
  CYW43439**, so the onboard radio has **no monitor mode and no frame injection**
  — Pwnagotchi-style handshake/PMKID/deauth capture is blocked on the internal
  radio. Workaround: a monitor/injection-capable USB Wi-Fi adapter in the
  USB-A host port (the pattern RaspyJack uses on Pi hardware).
- Everything LAN-side from Bjorn/Ragnar (host/port/vuln scanning, brute force,
  file stealing, web UI) maps cleanly — those features only need a network
  connection, and the Zero has Wi-Fi **and** built-in 10/100 Ethernet.
- Both caps ride the top EXT 14-pin bus on **SPI0** and are proven from Linux
  userspace: CC1101 via `/dev/spidev0.1` (CardputerZero org's own chat app),
  SX1262 via `meshtasticd` (zeroradio project, verified end-to-end on hardware).
- The caps are **one-at-a-time** (single EXT port, no hot-swap) — unlike Loki's
  custom PCB, the fork must treat CC1101 and LoRa as swappable radio profiles,
  not concurrent radios.

---

## 1. Cardputer Zero hardware

Sources: M5Stack docs https://docs.m5stack.com/en/CardputerZero ·
shop https://shop.m5stack.com/pages/m5-cardputerzero ·
Raspberry Pi CM0 https://www.raspberrypi.com/products/compute-module-zero/

| Item | Spec |
|---|---|
| SKUs | C154 / C154-B (CardputerZero), C155 / C155-B (CardputerZero-Lite) |
| Core module | Raspberry Pi Compute Module 0 (CM0) |
| CPU | RP3A0 (BCM2837 family; BCM2710A1 die), quad-core Cortex-A53 @ 1 GHz, ARMv8-A (aarch64) |
| GPU | VideoCore IV, OpenGL ES 1.1/2.0, H.264 1080p30 encode/decode |
| RAM | 512 MB LPDDR2 (fixed, on the RP3A0 SiP) |
| Storage | microSD (boot + OS). Full model bundles a 32 GB card; Lite bundles none. (CM0 also exists in eMMC variants, but M5Stack's design boots from microSD.) |
| Display | 1.9″ LCD, ST7789v3 controller, 320 × 170, on SPI0 (see §2.4) |
| Keyboard | 46-key matrix, TCA8418RTWR I2C keypad controller @ 0x34, IRQ on CM0 G27 |
| Wi-Fi | 2.4 GHz 802.11 b/g/n — **CYW43439** (see §1.1) |
| Bluetooth | Bluetooth 5.0 + BLE (same CYW43439 combo chip) |
| Ethernet | 10/100M via SR9900A USB 2.0-to-Ethernet chip (hangs off the internal USB hub) |
| USB | 1× USB-A 2.0 host, 2× USB-C 2.0; GL852G-OHY60 hub; physical Host/Slave switch — in Slave mode the hub, USB-A port, Ethernet and the EXT port's USB lines are disconnected and the CM0 talks to the right-side USB-C directly (this is also the rpiboot flashing path) |
| Camera | IMX219 CSI 4-lane, 8 MP (3280 × 2464) — **Full model only** |
| IMU | BMI270 + BMM150 magnetometer — **Full model only** (⚠️ at least one retail variant, M5-C154-V1, omits the BMM150 — check the exact SKU) |
| RTC | RX8130CE @ I2C 0x32 |
| Audio | ES8389 codec, MEMS mic, AW8737A amp + 1 W @ 8 Ω speaker, 3.5 mm TRRS jack |
| IR | IR transmitter + receiver built in (CM0 G12 = TX, G13 = RX) |
| Battery | 3.7 V, 1750 mAh LiPo with NTC; BQ27220YZFR fuel gauge; charge via USB-C (5 V @ 2 A recommended); idle draw 2.5 W |
| Size / weight | 84.0 × 54.0 × 23.1 mm, 95 g |
| Other | HDMI video out (1080p30), microSD slot, HY2.0-4P Grove port (I2C/UART switchable, see §1.2), M5IOE1 I/O expander (I2C 0x4F) handling LCD reset/backlight PWM, HAT power enable, keyboard/hub reset, LEDs |

Launch context: Kickstarter launched 2026-05-26; M5Stack's shop page lists
$59 Lite / $89 Full super-early-bird ($99 / $149 MSRP) with shipping expected
around November 2026. Early coverage marked specs "preliminary" — the docs site
is live and community projects below run on real units, but re-check the docs
page against shipped hardware revisions.

### 1.1 The Wi-Fi chip — CYW43439 (this decides the Pwnagotchi question)

- Raspberry Pi's CM0 datasheet (Release 3, 2026-07-08) §2.1: *"The wireless
  interfaces are provided by the Cypress CYW43439 chip, supporting 2.4 GHz IEEE
  802.11 b/g/n Wi-Fi [and] Bluetooth 5.0 and BLE."*
  https://pip-assets.raspberrypi.com/categories/1286-raspberry-pi-compute-module-zero/documents/RP-009251-DS-3-cm0-datasheet.pdf
- ⚠️ Datasheet history: Release 1 of the same datasheet named a **CYW43459**
  instead. The current (Release 3) document says CYW43439. Either way, it is
  **not** the Pi Zero 2 W's radio: the Zero 2 W uses a Synaptics SYN43436
  (Broadcom BCM43436 family, firmware `bcm43436b0` / 9.88.4.x, loaded as
  `brcmfmac43436-sdio`). The RP3A0 *processor* SiP is shared with the Zero 2 W;
  the wireless chip is a separate part on the CM0 and differs.
- **On-device confirmation (do this first on real hardware):**
  `dmesg | grep -i brcmfmac` — expect `brcm/brcmfmac43439-sdio` and a 7.95.x
  firmware version if the CYW43439 is fitted.

### 1.2 Expansion — the top Cap bus (EXT 2.54-14P)

The Cap interface is a 2.54 mm 14-pin header on top of the device
("Cap-Bus" / HAT port, JP5). M5Stack's published pin map (CM0 GPIO numbers):

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | HAT_P0 = USB4_D+ / **G26** | 2 | 5V IN |
| 3 | HAT_P1 = USB4_D− / **G23** | 4 | GND |
| 5 | **G22** | 6 | 5V OUT |
| 7 | SPI0_CLK = **G11** | 8 | I2C1_SDA = **G2** |
| 9 | SPI0_MOSI = **G10** | 10 | I2C1_SCL = **G3** |
| 11 | SPI0_MISO = **G9** | 12 | UART_RXD = **G15** |
| 13 | SPI0_CS1 = **G7** | 14 | UART_TXD = **G14** |

Key behaviours (M5Stack docs, CardputerZero PinMap section):

- HAT_P0/P1 are dual-function: GPIO26/GPIO23 by default, switchable to USB
  (hub USB4) via `PYG1_HAT_SW` on the M5IOE1 expander.
- HAT power is gated by `PYG13_HAT_EN` (M5IOE1); a separate CM0 line
  (G5, `HAT_5VOUT_EN`) also appears in community bring-up notes.
- SPI0 is **shared with the LCD** (display: MOSI G10, SCLK G11, DC G25,
  CS = G8/CS0, TE G5; LCD reset + backlight PWM via M5IOE1). Caps use **CS1**,
  so cap traffic and display traffic coexist on one SPI bus — the CardputerZero
  org's CC1101 app explicitly warns that cutting the cap's I/O supply can freeze
  the LCD.
- **Caps are NOT hot-swappable** — power off before fitting/removing (stated on
  every cap's docs page).
- The HY2.0-4P Grove port is a second, smaller expansion path: GND / 5 V /
  G14-TXD-or-G2-SDA / G15-RXD-or-G3-SCL, switched by CM0 G4, default UART,
  5 V out < 500 mA.

---

## 2. Software / development environment

### 2.1 OS image

- M5Stack ships a **Raspberry Pi OS / Debian (aarch64)** image with a thin
  M5Stack appliance profile — not a bespoke OS. Image components live in the
  `CardputerZero` / `m5stack` GitHub orgs: `CardputerZero/pi-gen` (fork of the
  official Raspberry Pi OS image builder), `CardputerZero/cardputer-zero-os`
  (system profile), a CM0 kernel package (`cm0-firmware`), and
  `m5stack/m5stack-linux-dtoverlays` (device-tree overlays for the LCD,
  keyboard, audio, camera, etc.).
  Org: https://github.com/CardputerZero · profile:
  https://github.com/CardputerZero/cardputer-zero-os ·
  image builder: https://github.com/CardputerZero/pi-gen
- Flashing: **M5 Imager** (M5Stack's Pi-Imager-style tool) writes the image to
  microSD and pre-configures user/password/Wi-Fi/SSH; USB flashing via
  Raspberry Pi's `rpiboot` exists but is explicitly "not recommended".
  https://docs.m5stack.com/en/compute/cardputerzero/image
- Because it is stock Pi OS underneath, the standard Pi toolchain applies
  unchanged: apt, systemd, SSH, Python 3, `libgpiod`, `i2c-tools`, `spidev`,
  BlueZ/`bluetoothctl`, `libcamera`. Nothing needs "porting" — this is the same
  software environment Loki's Pi side and Bjorn/Ragnar already target.

### 2.2 Shell, launcher, app model

- UI layer: `cardputer-zero-shell` — a small-screen **Wayland** shell (labwc
  compositor) with an APPLaunch-compatible app launcher; apps are discovered
  via `.desktop` files.
- Distribution: apps ship as **Debian `.deb` packages (arm64)** installed from
  an on-device **AppStore** (`CardputerZero/Store`) backed by APT repositories
  (`m5stack/CardputerZeroRepository`, `CardputerZero/packages`) and a web hub
  (https://cardputerzero.github.io). The AppStore only installs packages whose
  registry status is `approved`.
  Store source: https://github.com/CardputerZero/Store/blob/HEAD/README.md
- Two official app-development paths:
  1. **`czdev` / CardputerZero-AppBuilder** (m5stack) — builds LVGL apps for
     the 320×170 panel, has an SDL2 desktop emulator for hardware-free UI work,
     and packages the result as a `.deb` (`app-builder.json` manifest; an
     online "submit a Git repo → get a .deb" mode exists).
     https://github.com/m5stack/CardputerZero-AppBuilder
  2. **`CardputerZero/Template`** — CMake + LVGL (v9.5) C++ starter with
     MVVM structure, desktop SDL simulator builds, device cross-builds, and
     `.deb` packaging. https://github.com/CardputerZero/Template
- **Python path (the one this fork cares about):** nothing stops plain Python —
  the OS is Debian. Community proof: zeroradio installs the Meshtastic Python
  CLI in a `venv` on-device; Bjorn/Ragnar themselves are Python services with
  web UIs. A Loki fork can run as Python systemd services + a UI process and
  optionally be wrapped in a `.deb` for AppStore/APPLaunch integration.
  (⚠️ The AppStore catalog is curated LVGL apps; a Python service does not need
  the store — it can ship as its own `.deb` or a plain installer script, the
  same way Bjorn/Ragnar install on Pi OS.)

### 2.3 Display and keyboard drivers (UI feasibility)

- **Display:** ST7789v3 on SPI0 is bound by M5Stack's overlays to the standard
  Linux display stack. On the stock image the panel appears as a framebuffer
  driven by `fb_st7789v` (fbtft-class driver), with a udev-created stable
  symlink **`/dev/fb_lcd`**; the Wayland shell path uses DRM/KMS
  (`panel-mipi-dbi-spi` → labwc). Both are ordinary Linux interfaces:
  - Python UI options: Pillow/pygame writing to `/dev/fb_lcd` (the Bjorn/Ragnar
    pattern — they draw to an SPI e-paper; here it's a framebuffer, which is
    *simpler*), or an LVGL app via the Template/AppBuilder (their config
    exposes `/dev/fb0` fbdev or `/dev/dri/card0` DRM backends).
  - On-hardware proof: `droomurray/czduke` renders straight to `/dev/fb_lcd`
    at 320×170 RGB565 with no X/Wayland/DRM and launches from the stock
    launcher as a `.deb`. https://github.com/droomurray/czduke
  - Resolution reality check: 320×170 colour is *more* room than Pwnagotchi's
    usual 250×122 e-ink or Bjorn's 250×122 e-paper — faces/status UIs port
    comfortably; Ragnar's UI is web-based anyway (port 8000).
- **Keyboard:** TCA8418 keypad controller on I2C1 (0x34, IRQ G27) → mainline
  Linux `tca8418_keypad` driver → standard **evdev** input device
  (`/dev/input/by-path/platform-3f804000.i2c-event` on real hardware, per
  czduke); Fn layers are handled in the kernel driver. Python reads it with
  `evdev` exactly like any USB keyboard. The Template's platform layer likewise
  consumes Linux evdev. A full QWERTY keyboard is a genuine upgrade over
  Bjorn/Ragnar's 4-button navigation and Pwnagotchi's button-less design.

### 2.4 Monitor mode / frame injection — the verdict

**Stock:** the `brcmfmac` driver + stock CYW43439 firmware offers **no monitor
mode and no injection** (true of all Broadcom/Cypress onboard Pi radios).

**Nexmon does not close the gap for this chip:**

- Nexmon (SEEMOO Lab) is a firmware-patching framework that adds monitor mode +
  frame injection to specific Broadcom/Cypress firmware builds. Its upstream
  supported-device table includes the Pi Zero 2 W's radio —
  `bcm43436b0`, firmware 9_88_4_65, "Raspberry Pi Zero 2 W", Pi OS kernel 5.10 —
  but **contains no CYW43439 (bcm43439) entry**.
  https://github.com/seemoo-lab/nexmon
- Kali's packaged nexmon support (`brcmfmac-nexmon-dkms` + `firmware-nexmon`,
  Kali 2025.1+) was tested on Pi 5, Pi 4, Pi 3B, Pi Zero W and
  "Raspberry Pi Zero 2 W (43436s variant)" — again, no 43439-based board, with
  the explicit caveat that other boards "with a compatible Broadcom Wi-Fi
  chipset **may** work."
  https://www.kali.org/blog/raspberry-pi-wi-fi-glow-up/
- Corroboration: the CYW43439's other Linux-adjacent home, the Pi Pico W, is
  documented by its community as **not nexmon-compatible**.

**Verdict: Pwnagotchi-style capture (handshakes, PMKID, deauth) is NOT possible
on the Cardputer Zero's internal radio today.** It becomes possible with a
USB Wi-Fi adapter whose chipset/driver supports monitor mode + injection
plugged into the USB-A host port — the Zero's hub/Ethernet design leaves the
internal radio free for normal connectivity while the dongle does RF work,
which is precisely the split Pwnagotchi builds already use on Pis whose
onboard radio is unsuitable. Budget a dongle (e.g. an RTL8812AU/MT7612U-class
adapter — ⚠️ pick a specific model and verify its driver on arm64 Pi OS at
build time; not verified here).

Also note the asymmetry this creates vs the Pi Zero 2 W: on a Zero 2 W the
*internal* radio does work with nexmon (and the maintained Pwnagotchi forks
target exactly that board — e.g. ev4's fork builds `bcm43436b0/9_88_4_65`
patches and bettercap from source for the Zero 2 W:
https://git.ev4.me/ev4/pwnagotchi). The Cardputer Zero shares the Zero 2 W's
CPU/RAM class but **not** its radio — that one component swap is the whole
story of this fork's Wi-Fi limitations.

---

## 3. Cap CC1101 (SKU U219)

Source: https://docs.m5stack.com/en/cap/Cap_CC1101

### 3.1 What it is

- Exact name: **Cap CC1101** (shop name "Cap CC1101 & NFC for Cardputer Adv"),
  SKU **U219**. Compatible with Cardputer-Adv **and CardputerZero**.
- RF chip: **TI CC1101** sub-1 GHz transceiver. Bands **315 / 433 / 868 / 915
  MHz** multiplexed to one RP-SMA antenna port by dual SP3T RF switches +
  multi-band matching. Modulations: 2-FSK, 4-FSK, GFSK, MSK, ASK, OOK.
  TX power +10 dBm; RX sensitivity up to −99.5 dBm; 64-byte RX/TX FIFOs.
  Ships with three RP-SMA rubber antennas (315, 433, and 868/915 MHz).
  M5Stack's FSK test figures: ~435–441 m range at 58 kbps.
- NFC chip (bonus radio): **ST25R3916** — reader/writer for NFC-A/B
  (ISO14443A/B), NFC-F (FeliCa), NFC-V (ISO15693); card emulation NFC-A/F;
  13.56 MHz; 512-byte FIFO.
- Interface: **SPI** for both chips (separate chip selects). Onboard DC-DC buck;
  HY2.0-4P Grove passthrough (I2C). Draw: ~96 mA @ 5 V worst case
  (CC1101 TX max + NFC polling); sleep ~141 µA.
- Size 84.0 × 24.0 × 19.7 mm, 14.9 g; two M2×4 mm mounting screws to the host.

### 3.2 Published pin mapping

Cap-side connector (M5Stack's Cap-Bus table for U219):

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | CC1101_G0 (GDO0) | 14 | CC1101_CS |
| 2 | CC1101_RF_SW0 | 13 | SPI_MISO |
| 3 | SCL (I2C, Grove) | 12 | SPI_MOSI |
| 4 | SDA (I2C, Grove) | 11 | SPI_SCLK |
| 5 | 5V_OUT | 10 | NFC_CS |
| 6 | GND | 9 | NFC_IRQ |
| 7 | 5V_IN | 8 | POWER_EN |

RF switch truth table (M5Stack): SW0/SW1 = 0/0 → 315 MHz; 0/1 → 433 MHz;
1/1 → 868/915 MHz. ⚠️ Only **RF_SW0** appears on the connector — where RF_SW1
is driven from is **not documented** on the docs page (check the linked
schematic PDF before relying on band switching in a driver).

M5Stack publishes GPIO numbers only for the ESP32 Cardputer-Adv
(CC1101: CS=G5, RF_SW0=G13, G0=G15, SCK=G40, MOSI=G14, MISO=G39;
NFC: IRQ=G4, CS=G6, same SPI bus) — those numbers are meaningless on the CM0.

### 3.3 Verified Cardputer Zero (CM0) mapping

From the CardputerZero org's own working app, **Cap-CC1101-SubG-Chat**
(https://github.com/cardputerzero/cap-cc1101-subg-chat/blob/HEAD/README.md):

- **CC1101 → `/dev/spidev0.1`** — SPI0 with **kernel-managed CS1** (CM0 G7).
  The app runs a verified 868 MHz low-rate 2-FSK profile TX/RX on real
  hardware. This is the reference implementation to port from (C++/LVGL,
  open source, builds an arm64 `.deb`).
- **POWER_EN → GPIO26** (HAT_P0). The app keeps GPIO26 POWER_EN and EXT 5 V
  enabled for the whole session (cutting cap I/O power can freeze the LCD,
  since the cap shares SPI0 with it).
- **NFC (ST25R3916) → a "CS2/GPIO22 overlay"** — i.e. NFC_CS is GPIO22 (EXT
  pin 5) used as a second, GPIO chip select via a device-tree overlay
  (creating a further spidev chip-select); the CC1101 path does not need it.
- On exit the app "restores the G14/G15 pinmux" — the cap's remaining control
  lines evidently share the EXT UART pins (G14/G15) under a pinmux switch.
  ⚠️ The exact assignment of CC1101_G0 (GDO0) and RF_SW0 to CM0 GPIOs is
  **not published**; G14/G15 are the candidates the app's behaviour points to.
  Confirm from the U219 schematic PDF or the SubG-Chat source before writing
  the fork's driver constants.

### 3.4 Libraries on Linux

- M5Stack's own CC1101 and NFC driver libraries linked from the docs page are
  **Arduino** libraries (for the Adv). There is **no official M5Stack Linux
  driver** for this cap — the Linux path is userspace `spidev`, proven by
  SubG-Chat.
- Portable register-level code to port: the SubG-Chat device backend (best —
  same hardware), **RadioLib** (supports CC1101; C++ with a non-Arduino HAL —
  https://github.com/jgromes/RadioLib), and the Arduino-world
  SmartRC-CC1101-Driver-Lib (register sequences worth referencing; Arduino-only).
- For the fork (Python-first), the pragmatic route is a small Python `spidev`
  driver translating the SubG-Chat/RadioLib register init sequences — CC1101
  is a simple register/FIFO device and this is well-trodden.

---

## 4. Cap LoRa-1262 (SKU U214) and Cap LoRa868 (SKU U201)

Sources: https://docs.m5stack.com/en/cap/Cap_LoRa-1262 ·
https://docs.m5stack.com/en/cap/Cap_LoRa868

### 4.1 What they are

- **Cap LoRa-1262** (U214) — current model: smaller "Stamp LoRa-1262 Mini"
  module, RF shielding cover, HY2.0-4P passthrough, RF antenna switch
  controlled via an onboard I/O expander.
- **Cap LoRa868** (U201) — legacy model: standard-size Stamp LoRa-1262, no
  shield, no HY2.0-4P, no RF-switch control. Same radio and band.
- LoRa chip: **Semtech SX1262** (both caps). Band **868–923 MHz** — this is one
  wideband design, not region-locked SKUs; the operating region (EU868 vs
  US915) is a software configuration choice (and a legal one — set it
  correctly for the user's region). TX up to **+22 dBm**; RX sensitivity to
  −147 dBm (LoRa low-data-rate); LoRa ≤ 62.5 kbps, FSK ≤ 300 kbps;
  modulations FSK/GFSK/MSK/GMSK/LoRa. External RP-SMA antenna (3 dBi, included)
  — **M5Stack warns: never power the cap without the antenna fitted** (PA
  damage).
- GNSS (both caps): **ATGM336H-6N @ AT6668**, UART @ 115200 8N1, NMEA 0183,
  GPS/QZSS/BDS/GLONASS/Galileo, ceramic antenna on the cap, <1.5 m CEP50.
- Interface: LoRa over **SPI**; GNSS over **UART**; plus I2C to an onboard
  **PI4IOE5V6408** I/O expander on the U214 (its P0 enables the RF antenna
  switch — the radio hears nothing until P0 is driven high; P1 gates the GNSS
  antenna LNA and should be left alone).
- Size 84.0 × 24.0 × 15.2 mm, 22.1 g (U214, excl. antenna).

### 4.2 Published pin mapping

Cap-side connector (U214): pin 1 GPS_TX, 2 GPS_RX, 3 SCL, 4 SDA, 5 5V_OUT,
6 GND, 7 5V_IN, 8 LoRa_RST, 9 LoRa_IRQ, 10 LoRa_BUSY, 11 LoRa_SCK,
12 LoRa_MOSI, 13 LoRa_MISO, 14 LoRa_NSS. (Adv GPIO numbers are again
published but ESP32-specific; ignore for the Zero.)

### 4.3 Verified Cardputer Zero (CM0) mapping

From **zeroradio** (community project; probed on real hardware against
schematic v0.3, verified end-to-end 2026-07-07) —
https://github.com/andreahaku/zeroradio/blob/HEAD/docs/cap-lora-1262.md:

| Cap signal | On the Zero | Notes |
|---|---|---|
| SX1262 SPI | `/dev/spidev0.1` (SPI0, CS1 = G7, kernel-managed) | Same bus/CS as the CC1101 cap — caps are interchangeable, not simultaneous |
| SX1262 DIO1 (IRQ) | **GPIO23** | Identified empirically (RX-timeout IRQ) |
| SX1262 BUSY | **GPIO22** | "By exclusion" — only two free HAT GPIOs |
| SX1262 RESET | **Not wired** to a CM0 GPIO | Power-on reset on the cap; omit Reset in config |
| SX1262 TCXO | DIO3 @ 1.8 V | Mandatory: without TCXO config, `SetRx` fails `XOSC_START_ERR` |
| RF antenna switch | PI4IOE5V6408 @ I2C1 0x43, **P0 = high** | Must be set before the radio works |
| GNSS | `/dev/ttyS0` (mini-UART, 115200 8N1) | Module autoprobes as ATGM336H ("GP-02" CASIC) |
| Cap 5 V | From the HAT's unswitched supply pin | Toggling `G5_HAT_5VOUT_EN` does **not** power-cycle the cap |

### 4.4 Libraries / software on Linux

- **meshtasticd** (Meshtastic's Linux/Portduino daemon) is the proven stack:
  zeroradio runs it natively on the Zero driving this cap (SX1262 init OK,
  GNSS fix in-app, region EU_868) — so a Loki fork gets a working Meshtastic
  node on this hardware essentially for free, plus Meshtastic's Python CLI/API
  (TCP 127.0.0.1:4403) as the integration surface.
- **RadioLib** supports the SX126x family and has a non-Arduino HAL if a
  custom userspace driver is wanted (C++). M5Stack's linked LoRa/GPS libraries
  are Arduino (Adv-only). No official M5Stack Linux driver exists — same
  pattern as the CC1101 cap.
- The CardputerZero org also ships `trail-mate` (GPS/LoRa chat/maps over the
  Cap EXT bus) as an app-layer reference.

---

## 5. Existing security firmware / projects for this hardware family

| Project | Runs on Cardputer Zero? | Notes |
|---|---|---|
| **Bruce** (BruceDevices) | **No** | ESP32 firmware. bruce.computer's compatibility table lists "M5Stack Cardputer" and "Cardputer Adv" — both ESP32-S3FN8. No Zero target exists; there is no ESP32 in the Zero to flash. https://bruce.computer/ · https://github.com/BruceDevices/firmware |
| ESP32 Marauder, NEMO, Evil-M5Project, MicroHydra, M5Launcher | **No** | Same reason — ESP32-S3 firmware for Cardputer/Cardputer-Adv. M5Stack's own launch material name-drops them as *series heritage*, not Zero-compatible software. |
| Flipper-Zero-meets-M5Stack-Cardputer | **No** | ESP-IDF port for the ESP32-S3 Cardputer/Adv only. https://github.com/elicoftz/flipper-zero-meets-m5stack-cardputer/blob/HEAD/README.md |
| **Pwnagotchi** (any fork) | **Not ported (yet)** | No Cardputer Zero port was found. Search surfaced only a blog "project idea" suggesting the Zero would suit Pwnagotchi. The maintained forks (jayofelony — https://github.com/jayofelony/pwnagotchi; ev4 — https://git.ev4.me/ev4/pwnagotchi) target Pi Zero 2 W / Pi 3/4/5. A port is plausible (same CPU class, Python + bettercap) but the display driver and the radio problem (§2.4) are the work. |
| **Bjorn / Ragnar** | **Not ported (yet)** | No Zero-specific port found. Both are Python on Pi OS for Pi Zero W/2 W (+ Pi 4/5 for Ragnar), so the port is a display/input adaptation, not a rewrite (see §6). |
| **zeroradio** (andreahaku) | **Yes — native** | Zero-native app suite (.deb): Meshtastic via cap LoRa (§4.3), ADS-B via USB RTL-SDR, more. Best existing proof of the cap + packaging patterns this fork needs. https://github.com/andreahaku/zeroradio |
| CardputerZero org apps | **Yes — native** | Cap-CC1101-SubG-Chat (§3.3), trail-mate (LoRa/GPS), Store, default apps. https://github.com/CardputerZero |
| RaspyJack (7h30th3r0n3) | ⚠️ Claimed, unverified | A secondary article claims "optional support for the Cardputer Zero form factor" for this Pi offensive toolkit; not confirmed from the project's own repo in this research pass. Worth a direct look before building — if real, it's the closest existing "Loki-like" for the form factor. |
| Linux-native tools | **Yes** | bettercap, aircrack-ng suite, nmap, scapy, kismet, meshtasticd — standard Debian arm64 packages/source builds; Loki already pins bettercap 2.41.7 + aircrack-ng 1.7 + hcxdumptool 7.1.2 for its Pi side. |

**Build-on-top summary:** there is no security firmware to fork *for the Zero
itself*. The fork's real foundations are (1) Loki's own Pi-side Python
(bettercap orchestration), (2) Bjorn/Ragnar's Python LAN-attack modules as
feature references, (3) the CardputerZero org's cap drivers/apps as hardware
references, and (4) zeroradio's Meshtastic integration.

---

## 6. Feature mapping — Pwnagotchi & Bjorn/Ragnar → Cardputer Zero

Legend: ✅ maps cleanly · 🟡 maps with adaptation/limits · ⛔ blocked on this hardware

### 6.1 Pwnagotchi features

Core Pwnagotchi (upstream/jayofelony lineage): a Python daemon drives
**bettercap** to passively capture and actively elicit WPA/WPA2 key material —
full/half 4-way handshakes and PMKIDs — saved as .pcap for offline cracking
(hashcat); personality config (advertise/associate/deauth), a Tamagotchi face
UI with moods, plugin system (GPS tagging, wpa-sec upload, BT tether, etc.),
web UI, and pwngrid peer discovery. (The original's RL "AI" was removed in the
maintained jayofelony fork; capture is deterministic bettercap orchestration.)

| Feature | Verdict | Why |
|---|---|---|
| bettercap engine (wifi module) | ✅ | Go binary, arm64; Loki already runs bettercap on Pi-class hardware. |
| Passive handshake capture | ⛔ internal / 🟡 with USB dongle | Needs monitor mode. CYW43439 has none and no nexmon patch (§2.4). A monitor-capable USB adapter restores it. |
| PMKID capture (association attack) | ⛔ internal / 🟡 dongle | Needs frame injection as well as monitor mode. Same blocker/fix. |
| Deauthentication attacks | ⛔ internal / 🟡 dongle | Injection. Same blocker/fix. |
| AP/client recon (who's around) | 🟡 | Managed-mode scanning (`iw scan`, bettercap in non-monitor modes) gives AP inventories; full client/probe visibility needs monitor mode. |
| Face / personality UI | ✅ | 320×170 colour LCD via framebuffer is strictly nicer than e-ink; needs a display-driver adaptation in the pwnagotchi UI layer (it ships e-ink/LCD drivers for Pi HATs, not this panel). |
| pwngrid peer discovery | ⛔/🟡 | Pwngrid advertises/detects peers using the same Wi-Fi attack radio path; tied to the monitor/injection blocker. Re-test if a dongle is fitted. ⚠️ Not verified against pwngrid source in this pass. |
| GPS tagging plugin | ✅ | Cap LoRa's GNSS gives NMEA on `/dev/ttyS0` — better than the USB GPS dongles Pwnagotchi builds usually bolt on. (Only when the LoRa cap is fitted.) |
| wpa-sec / onlinehashcrack upload plugins | ✅ | Needs only internet (Wi-Fi client mode or Ethernet). |
| BT-tether plugin | 🟡 | CM0 has BT 5.0/BLE + BlueZ; plausible, untested on this image. |
| Web UI / SSH management | ✅ | Stock Linux. |

### 6.2 Bjorn features

Bjorn (infinition/Bjorn, Python, Pi Zero W/2 W + 2.13″ e-paper): autonomous
LAN-side assessment — network scanning (live hosts + open ports),
vulnerability assessment (Nmap), brute-force attacks (FTP, SSH, SMB, RDP,
Telnet, SQL), file stealing from vulnerable services, host "zombification",
custom attack scripts, Viking Tamagotchi UI on e-paper + web interface.
Source: https://github.com/infinition/Bjorn

| Feature | Verdict | Why |
|---|---|---|
| Network discovery / host scan | ✅ | Needs only a network interface. Zero offers Wi-Fi client **and** wired Ethernet — Ethernet is the better Bjorn interface (no Wi-Fi association juggling). |
| Port scanning (nmap) | ✅ | Standard arm64 tooling; CPU/RAM identical class to Bjorn's reference Pi Zero 2 W. |
| Vulnerability assessment (nmap NSE) | ✅ | Same. |
| Brute force (FTP/SSH/SMB/RDP/Telnet/SQL) | ✅ | Pure userspace Python/tools. Slow on a 1 GHz A53 — exactly as on Bjorn's reference hardware. |
| File stealing | ✅ | Userspace. |
| Zombification / custom attack scripts | ✅ | Python extensibility carries over unchanged. |
| Web interface | ✅ | Flask-style UI runs fine; the Zero's keyboard+LCD also allow local control Bjorn never had. |
| Viking e-paper UI | 🟡 | Must be re-rendered for the 320×170 LCD framebuffer (Pillow → `/dev/fb_lcd`). Straightforward; colour is a bonus. Input moves from GPIO buttons to evdev keyboard. |

### 6.3 Ragnar features (Bjorn's successor)

Ragnar (PierreGode/Ragnar, Python, Pi Zero 2 W / Pi 4 / Pi 5): Bjorn's feature
set plus a richer web dashboard (port 8000) with threat-intel views, an
interactive network map, per-network file browser for stolen data/cracked
passwords, MAC-OUI device classification, and — on 8 GB-class Pis only —
an advanced-tools tier (real-time traffic analysis with tcpdump/tshark,
Nuclei, Nikto, SQLMap, Hydra, OWASP ZAP). Ragnar's own installer **skips the
advanced tier on Pi Zero-class hardware** for resource protection.
Source: https://github.com/PierreGode/Ragnar

| Feature | Verdict | Why |
|---|---|---|
| Core scanning/vuln/brute/file-steal suite | ✅ | Same as Bjorn — LAN-side, interface-agnostic. |
| Web dashboard / network map / file browser | ✅ | Python web UI; 512 MB is the same envelope Ragnar targets on the Zero 2 W. |
| Device classification (OUI + port heuristics) | ✅ | Zero-dependency Python; designed to run on Pi Zero 2 W-class CPUs. |
| Advanced tools tier (Nuclei/Nikto/ZAP/tshark analysis) | ⛔ (by design) | Ragnar itself excludes 512 MB Pi Zero-class hardware. The CM0's 512 MB puts the Zero in that excluded class — not a porting failure, a resource wall. (Individual light tools like hydra/sqlmap can still be run manually.) |
| BLE detection features (Flipper/AirTag/skimmer detection in the Ragnar ecosystem) | 🟡 | CM0 BT 5.0 + BlueZ should cover BLE scanning; ⚠️ not verified against Ragnar's implementation in this pass. |
| Pwnagotchi Bridge (dual-personality SD) | ⛔/n/a | Concept doesn't transfer: one Linux OS here hosts both personalities as services; and the Pwnagotchi half inherits the §2.4 radio blocker anyway. |

### 6.4 What the caps add (Loki's identity beyond Pwnagotchi/Bjorn)

| Capability | Verdict | Why |
|---|---|---|
| Sub-GHz RX/TX 315/433/868/915 (CC1101 cap) | ✅ | Proven from Linux userspace on this exact cap+host (SubG-Chat, 868 MHz 2-FSK). Replay/remote-control tooling = register driver + FIFO handling in Python (spidev). |
| NFC read/write/emulate (ST25R3916, same cap) | 🟡 | Hardware is capable (ISO14443A/B, FeliCa, ISO15693, emulation); on the Zero it needs the GPIO22-CS overlay path the org uses — less battle-tested than the CC1101 path. Proxmark-grade features are out of scope for this frontend. |
| LoRa / Meshtastic (LoRa cap) | ✅ | meshtasticd proven on-device via zeroradio; gives the fork an off-grid mesh comms feature neither Pwnagotchi nor Bjorn has. Region must be configured (US = 915 MHz plan) — the cap is band-capable, software decides. |
| GNSS positioning (LoRa cap) | ✅ | NMEA on `/dev/ttyS0`; feeds GPS-tagging for captures and wardriving logs. |
| IR TX/RX | 🟡 | Built into the Zero (G12/G13) — Bruce-style IR replay is conceivable via Linux LIRC/ir-ctl paths. ⚠️ Not verified on the stock M5 image in this pass. |
| BLE tools (Bruce-style BLE spam/scan) | 🟡 | BT 5.0 + BlueZ on Linux covers scanning/advertising experiments; ESP32-specific Bruce BLE tricks don't transfer 1:1. |
| BadUSB / HID | 🟡 | The CM0 has a USB device controller and the Zero's USB switch has a Slave mode — USB gadget (g_hid) is a standard Pi trick and plausible here, but the hub/switch topology differs from a bare Pi. ⚠️ Unverified on this device. |

### 6.5 Structural constraints to design around

1. **One cap at a time.** Single EXT port, no hot-swap, both caps claim
   SPI0/CS1. The fork's radio layer must be profile-based: detect/select the
   fitted cap at boot (or by user setting) and load that driver.
2. **512 MB RAM ceiling.** Ragnar's advanced tier is out; bettercap +
   Python services + UI is the realistic working set (same as Loki on Pi
   Zero 2 W). Keep the web UI light.
3. **SPI0 is shared with the LCD.** Cap drivers must respect bus sharing
   (CS discipline) and never cut cap power mid-session (LCD freeze warning
   from the org's CC1101 app).
4. **No SX1262 RESET line** and a mandatory TCXO config bit — small, real
   bring-up traps already documented by zeroradio; copy them into the fork's
   driver from day one.
5. **Kickstarter-era platform.** Docs/repos are moving fast (the CM0
   datasheet already changed its Wi-Fi chip line between revisions). Pin the
   fork to a specific M5 image version and re-verify hardware constants
   (GPIOs, firmware filenames) against it.

---

## 7. Recommended fork shape (for the planning doc)

- **Base:** stock M5Stack CardputerZero image (Pi OS/Debian aarch64) +
  Loki-Zero as Python services, packaged as an arm64 `.deb` so it appears in
  APPLaunch alongside the stock apps; UI process draws to `/dev/fb_lcd`
  (Pillow) and reads the keyboard via evdev — no LVGL/C++ required for v1.
- **Reuse:** Loki's existing Pi-side Python (bettercap orchestration, engine
  pins: bettercap 2.41.7, aircrack-ng 1.7, hcxdumptool/hcxtools 7.1.2,
  Scapy 2.8.0) carries over almost unchanged — same OS, same CPU class.
  Bjorn/Ragnar contribute their LAN-attack module designs (Python) — respect
  licences: Bjorn is MIT; Ragnar's licence terms were a known constraint in
  the original Loki research (non-commercial terms) → clean-room the behaviour,
  don't copy code.
- **Radio HAL:** three drivers behind one interface — (a) Wi-Fi via bettercap
  (dongle-gated for attack features), (b) CC1101 via `spidev0.1` (port of
  SubG-Chat register sequences), (c) SX1262 via meshtasticd's client API
  (don't re-implement LoRa — the daemon already owns the radio correctly,
  including the TCXO and RF-switch gotchas).
- **First three bring-up tests on hardware, in order:**
  1. `dmesg | grep -i brcmfmac` → confirm the Wi-Fi chip/firmware the retail
     unit actually ships (settles §1.1 definitively).
  2. `ls /dev/spidev0.1 /dev/fb_lcd /dev/ttyS0` with each cap fitted → confirm
     device nodes on the pinned image version.
  3. Run the org's SubG-Chat `.deb` and zeroradio's meshtasticd config →
     known-good baselines before writing any fork code.

---

## 8. Open questions / unverified items

1. ⚠️ **Wi-Fi chip on retail units** — CM0 datasheet Release 3 says CYW43439;
   Release 1 said CYW43459. Neither has a nexmon patch in the upstream
   supported list checked, so the §2.4 verdict stands either way, but the
   exact chip should be confirmed via `dmesg` on the shipped Cardputer Zero
   (M5Stack's own docs never name the chip).
2. ⚠️ **Cap CC1101 GDO0 / RF_SW0 CM0 GPIO assignment** — not published;
   evidence points at the G14/G15 UART pair (pinmux restore in SubG-Chat).
   Also **RF_SW1**'s control source is undocumented (only SW0 reaches the
   connector, yet the truth table needs both).
3. ⚠️ **NFC on the Zero** — the GPIO22-CS overlay path is referenced by the
   org's app README but no full ST25R3916-on-Zero walkthrough was found.
4. ⚠️ **RaspyJack's claimed Cardputer Zero support** — single secondary
   source; check the project repo directly before counting on it.
5. ⚠️ **pwngrid's exact radio requirements** and **Ragnar's BLE modules** —
   assessed from feature descriptions, not source, in this pass.
6. ⚠️ **USB Wi-Fi dongle choice** for restoring monitor/injection — no
   specific model verified on the Zero's hub + arm64 Pi OS here.
7. ⚠️ **IR (LIRC) and USB-gadget (BadUSB) paths** on the stock M5 image —
   standard Pi techniques, not yet demonstrated on this device in sources
   found.
8. ⚠️ Variant drift: at least one retail CardputerZero variant omits the
   BMM150 magnetometer; Kickstarter-era specs were marked preliminary.
   Verify the exact SKU in hand before writing hardware-dependent code.

---

## 9. Sources

Platform / OS:
- M5Stack CardputerZero docs — https://docs.m5stack.com/en/CardputerZero
- M5Stack shop (pricing/launch) — https://shop.m5stack.com/pages/m5-cardputerzero
- CardputerZero image flashing guide — https://docs.m5stack.com/en/compute/cardputerzero/image
- Raspberry Pi CM0 product page — https://www.raspberrypi.com/products/compute-module-zero/
- Raspberry Pi CM0 datasheet (Rel. 3) — https://pip-assets.raspberrypi.com/categories/1286-raspberry-pi-compute-module-zero/documents/RP-009251-DS-3-cm0-datasheet.pdf
- CardputerZero GitHub org — https://github.com/CardputerZero (pi-gen, cardputer-zero-os, Store, Template, Cap-CC1101-SubG-Chat, trail-mate)
- AppBuilder (czdev) — https://github.com/m5stack/CardputerZero-AppBuilder
- App template — https://github.com/CardputerZero/Template
- AppStore — https://github.com/CardputerZero/Store/blob/HEAD/README.md

Caps:
- Cap CC1101 docs — https://docs.m5stack.com/en/cap/Cap_CC1101
- Cap CC1101 on Zero (working app) — https://github.com/cardputerzero/cap-cc1101-subg-chat/blob/HEAD/README.md
- Cap LoRa-1262 docs — https://docs.m5stack.com/en/cap/Cap_LoRa-1262
- Cap LoRa868 docs — https://docs.m5stack.com/en/cap/Cap_LoRa868
- Cap LoRa-1262 on Zero (probed map, meshtasticd) — https://github.com/andreahaku/zeroradio/blob/HEAD/docs/cap-lora-1262.md
- RadioLib — https://github.com/jgromes/RadioLib

Wi-Fi / monitor mode:
- Nexmon — https://github.com/seemoo-lab/nexmon
- Kali nexmon packaging — https://www.kali.org/blog/raspberry-pi-wi-fi-glow-up/

Existing projects / feature references:
- Bruce — https://bruce.computer/ · https://github.com/BruceDevices/firmware
- Pwnagotchi (maintained forks) — https://github.com/jayofelony/pwnagotchi · https://git.ev4.me/ev4/pwnagotchi
- Bjorn — https://github.com/infinition/Bjorn
- Ragnar — https://github.com/PierreGode/Ragnar
- zeroradio — https://github.com/andreahaku/zeroradio
- czduke (framebuffer + evdev proof) — https://github.com/droomurray/czduke
