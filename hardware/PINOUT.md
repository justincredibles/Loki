# Loki — Pin Mapping Reference

Extracted from `hardware/DESIGN.md` §3 (2026-10-16) for quick reference during KiCad work. If this file and DESIGN.md ever disagree, DESIGN.md wins.

**Board:** 85.6 × 56.5 mm (full Raspberry Pi footprint), 40-pin stacking header.

## 3. Pin Assignment Tables

### 3.1 Raspberry Pi 40-pin header

BCM numbering. "Free" = routed to the expansion header (§3.4).

| Pin | BCM | Function on Loki HAT | Notes |
|---|---|---|---|
| 1 | 3V3 (from Pi) | **24C32 EEPROM VCC only** | Isolated net per HAT spec; does NOT power the board |
| 2 | 5V | **5V_SYS in** (from TPS61088) | Both 5V pins used — Pi 5 current |
| 3 | GPIO2 / SDA1 | I2C1 SDA → MAX17048, expansion | 4.7 kΩ pull-up to board 3V3 on HAT |
| 4 | 5V | **5V_SYS in** | Wide pour, via-stitched to pin 2 |
| 5 | GPIO3 / SCL1 | I2C1 SCL → MAX17048, expansion | Pairs with pin 3 |
| 6 | GND | GND | |
| 7 | GPIO4 | MAX17048 **ALRT** interrupt in | Also drives red LED in hardware |
| 8 | GPIO14 / TXD0 | UART TX → ESP32 IO44 (RX0) | PL011 UART0 (see note below) |
| 9 | GND | GND | |
| 10 | GPIO15 / RXD0 | UART RX ← ESP32 IO43 (TX0) | 115200 8N1 protocol + flashing |
| 11 | GPIO17 | → ESP32 **EN** (reset) | 1 kΩ series; ESP32 side has 10 kΩ PU + 1 µF |
| 12 | GPIO18 / PWM0 | Display backlight FET gate | Hardware PWM dimming |
| 13 | GPIO27 | → ESP32 **IO0** (boot strap) | 1 kΩ series; ESP32 side 10 kΩ PU |
| 14 | GND | GND | |
| 15 | GPIO22 | ← ESP32 IO42 **attention IRQ** | ESP32 raises on BadUSB-done / RF event |
| 16 | GPIO23 | FREE → expansion | |
| 17 | 3V3 | NC | Not used (avoid back-powering Pi rail) |
| 18 | GPIO24 | Display **RST** | |
| 19 | GPIO10 / MOSI0 | SPI0 MOSI → display (+ expansion) | |
| 20 | GND | GND | |
| 21 | GPIO9 / MISO0 | SPI0 MISO ← display module SD | LCD itself is write-only; MISO serves module SD |
| 22 | GPIO25 | Display **DC** | |
| 23 | GPIO11 / SCLK0 | SPI0 SCLK → display (+ expansion) | |
| 24 | GPIO8 / CE0 | Display **CS** | |
| 25 | GND | GND | |
| 26 | GPIO7 / CE1 | Display-module microSD **CS** | Optional socket on the display module itself |
| 27 | GPIO0 / ID_SD | 24C32 SDA | HAT ID bus — nothing else, ever |
| 28 | GPIO1 / ID_SC | 24C32 SCL | HAT ID bus |
| 29 | GPIO5 | Button **UP** | Shared net (§3.3), 1 kΩ series to header |
| 30 | GND | GND | |
| 31 | GPIO6 | Button **DOWN** | Shared net |
| 32 | GPIO12 | FREE → expansion (PWM1 capable) | |
| 33 | GPIO13 | Button **LEFT** | Shared net |
| 34 | GND | GND | |
| 35 | GPIO19 | FREE → expansion | |
| 36 | GPIO16 | FREE → expansion | |
| 37 | GPIO26 | Button **RIGHT** | Shared net (long-press = Home, in Pi UI) |
| 38 | GPIO20 | FREE → expansion (default = expansion SPI CS) | |
| 39 | GND | GND | |
| 40 | GPIO21 | FREE → expansion | |

**UART note (all three Pis):** use the PL011 (UART0) on GPIO14/15 — on the Zero 2 W that means the `dtoverlay=disable-bt` (or `miniuart-bt`) overlay so the PL011 isn't stolen by Bluetooth; on Pi 5, GPIO14/15 is UART0 by default and the dedicated debug header stays free. 115200 baud is the locked protocol rate; esptool flashing over the same wires can run faster after sync, but the protocol doesn't need it.

**Left free on the Pi:** GPIO12, 16, 19, 20, 21, 23 (all to expansion), GPIO7 (display SD). Nothing else is spare — the header is fully committed, which is fine because the ESP32 owns everything radio.

### 3.2 ESP32-S3-WROOM-1-N16R8 GPIO map

Aligned with the pin conventions of existing DIY Bruce boards wherever Loki's scope allows (less fork work): shared SPI on IO11/12/13, PN532 on I2C, IR on IO1/IO2, buttons on IO15/16/38/39.

| GPIO | Function | Notes |
|---|---|---|
| IO0 | Boot strap ← Pi GPIO27 | 10 kΩ PU on board |
| IO1 | IR RX (TSOP38438 OUT) | Matches Bruce DIY convention |
| IO2 | IR TX → MMBT2222A base | Via 1 kΩ |
| IO3 | Spare — test pad only | Strapping pin (JTAG select); do not load |
| IO4 | nRF24 **CE** | |
| IO5 | nRF24 **CSN** | |
| IO6 | nRF24 **IRQ** | |
| IO7 | microSD card-detect | Spare if slot is DNP |
| IO8 | I2C SDA → PN532 | Bruce DIY builds put PN532 here @ 0x24 |
| IO9 | CC1101 **GDO0** | Packet interrupt |
| IO10 | CC1101 **CS** | |
| IO11 | SPI MOSI (shared) | CC1101 + nRF24 + microSD |
| IO12 | SPI SCK (shared) | |
| IO13 | SPI MISO (shared) | |
| IO14 | microSD **CS** | |
| IO15 | Button UP (shared with Pi GPIO5) | §3.3 |
| IO16 | Button DOWN (shared with Pi GPIO6) | §3.3 |
| IO17 | CC1101 **GDO2** | Async serial / carrier-sense out |
| IO18 | I2C SCL → PN532 | |
| IO19 | USB D− | → USB-C #2 via USBLC6 |
| IO20 | USB D+ | → USB-C #2 via USBLC6 |
| IO21 | USB VBUS detect | 100 k/100 k divider from port-2 VBUS |
| IO38 | Button LEFT (shared with Pi GPIO13) | §3.3 |
| IO39 | Button RIGHT (shared with Pi GPIO26) | §3.3 |
| IO40 | PN532 **IRQ** | |
| IO41 | PN532 **RSTPDN** | |
| IO42 | → Pi GPIO22 attention IRQ | Open-drain style: drive low / release |
| IO43 | UART0 TX → Pi GPIO15 | Protocol + esptool |
| IO44 | UART0 RX ← Pi GPIO14 | |
| IO47 | Spare → test pad / aux header | |
| IO48 | Spare → test pad / aux header | |
| EN | ← Pi GPIO17 | 10 kΩ PU + 1 µF to GND on board |
| — | **Forbidden:** IO26–32 (flash), IO33–37 (octal PSRAM), IO45/46 (strapping) | All left NC per Espressif guidance |

**SPI bus sharing:** CC1101, nRF24 and microSD share SPI2 with per-device CS and per-device SPI settings (ESP-IDF/Arduino `SPISettings` transactions). Known friction, handled in the fork: Bruce's CC1101 driver and the SD library both like owning the bus — all three are polled devices with no DMA contention in practice, and the existing DIY Bruce boards already run CC1101 + dual nRF24 + SD on this exact bus topology. PN532 is deliberately **not** on SPI (I2C instead) to keep one slow, chatty device off the RF bus. The Pi's display SPI is a completely separate bus on the Pi — no interaction.

### 3.3 Shared buttons (one net, two readers)

Each button net connects to: the button (to GND), one 10 kΩ pull-up to board 3V3, the ESP32 GPIO directly, and the Pi header pin through a 1 kΩ series resistor. The series resistor limits ESD-clamp backfeed into an unpowered Pi to < 3.3 mA while costing the Pi nothing in signal quality (its input is high-impedance; the button is a DC signal). Payoff: the ESP32 can take on-device confirmations (the BadUSB arm gate) and even run Bruce's standalone menus with the Pi fully off — which the architecture requires — and Loki's Pi UI uses the same four buttons when the Pi is up. Neither chip ever *drives* these nets.

### 3.4 Expansion header (2 × 8, 2.54 mm, top edge)

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | 5V_SYS (fused 500 mA PPTC) | 2 | GND |
| 3 | Board 3V3 (≤ 300 mA) | 4 | GND |
| 5 | I2C1 SDA (Pi GPIO2) | 6 | I2C1 SCL (Pi GPIO3) |
| 7 | SPI0 MOSI (Pi GPIO10) | 8 | SPI0 SCLK (Pi GPIO11) |
| 9 | SPI0 MISO (Pi GPIO9) | 10 | EXP_CS (Pi GPIO20) |
| 11 | Pi GPIO12 | 12 | Pi GPIO16 |
| 13 | Pi GPIO19 | 14 | Pi GPIO21 |
| 15 | Pi GPIO23 | 16 | ESP_IRQ (Pi GPIO22) — add-on wake/interrupt |

Honest note for the build guide: this is **signal-compatible, not pin-compatible** with a Flipper Zero's 18-pin GPIO header — Flipper add-ons that speak I2C/SPI/UART will work through a passive adapter or jumper wires, but nobody should promise a Cardputer or Flipper module will plug straight in and enumerate. (A true Flipper-pinout adapter board is a natural future add-on — the signals are all here.)

---
