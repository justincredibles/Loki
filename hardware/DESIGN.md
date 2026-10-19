# Project Loki — Hardware Design Document (Schematic-Ready Draft)

**Board:** Loki top board — custom PCB, **85.6 × 56.5 mm (full Raspberry Pi footprint)**, 40-pin stacking header. Deliberately NOT the 65 × 56.5 mm HAT-spec outline: the board is the same size as the Pi 4/5 itself, per Justin's spec (corrected 2026-10-16). Mounting holes follow the Pi pattern (Ø2.7 mm, 3.5 mm edge offsets, 58 × 49 mm spacing — verify against the official Pi 5 mechanical drawing at fabrication). On a Pi Zero 2 W (65 × 30 mm) the board overhangs; the enclosure defines the device outline.
**Revision:** 0.1 — 2026-10-16
**Status:** Ready to enter schematic capture (KiCad). All §7 decisions resolved — Justin accepted every recommendation on 2026-10-16.
**Distribution model:** Sold **assembled** (JLCPCB PCBA). Design rules applied throughout: JLCPCB parts library preferred, Basic-library parts where possible, modules over bare RF ICs, single-sided assembly as the goal (see §2.11 for the two-sided caveat), 4-layer stackup (§6).

**Verification legend:** ✅ = verified against a live source during research (source named). ⚠️ = part/family confirmed to exist and be stocked in the LCSC/JLC ecosystem, but the exact LCSC C-number was **not** confirmed — must be pinned at BOM freeze. No prices are cited anywhere in this document.

---

## 1. Block Diagram

```
                          USB-C #1 (CHARGE ONLY)
                          VBUS 5V, CC Rd x2
                                |
                                v
  Battery 1S LiPo      +-------------------+        VSYS (BAT..4.4V, always live)
  5000 mAh, JST-PH --> |  bq24074 charger  |------+-----------------------------+
  (PCM cell)           |  power-path, 1.5A |      |                             |
                       |  CHG -> blue LED  |      |                             |
                       +-------------------+      |                             |
                                ^                 v                             v
                                |          +-------------+            +----------------+
                                |          | MAX17048    |  I2C1      | Power switch   |
                                |          | fuel gauge  |<---------->| (slide, gates  |
                                |          | ALRT -> red |  Pi GPIO4  |  boost+buck EN)|
                                |          | LED + IRQ   |            +-------+--------+
                                |          +-------------+                    |
                                |                                             |
                                |        +------------------------------------+-----------+
                                |        |                                                    |
                                |        v                                                    v
                                |  +---------------------+                          +------------------+
                                |  | TPS61088 boost      |   5V_SYS (5.1V)         | SY8089 buck      |
                                |  | 5.1V / 4A cont,     |------------------+      | 3.3V / 2A        |
                                |  | 5A peak             |                  |      +--------+---------+
                                |  +---------------------+                  |               |
                                |        |                                  |               | 3V3 rail
                                |        |  pins 2+4                        v               v
                                |        |                          Display module   ESP32-S3, CC1101,
                                |        |                          VCC + BL FET     nRF24, PN532,
                       +--------+--------+----------------+              |           EEPROM*, SD
                       |  RASPBERRY PI (host, under HAT)   |              |
                       |  Zero 2 W min / Pi 4 / Pi 5       |        2x7 header
                       |  WiFi attacks via onboard radio  |        (ILI9341-class
                       |  + nexmon patch                  |         module, SPI0)
                       +--------+--------+----------------+
                                |
        Pi 40-pin header nets (see §3.1):
          UART0 GPIO14/15 <=====> ESP32-S3 UART0 (protocol + esptool flashing)
          GPIO17 ----------------> ESP32 EN   (Pi can reset / reflash ESP32)
          GPIO27 ----------------> ESP32 IO0  (boot-mode control)
          GPIO22 <---------------- ESP32 IO42 (ESP -> Pi attention IRQ)
          SPI0 GPIO8-11 ---------> display module (CS/DC/RST/BL on GPIO8/25/24/18)
          I2C1 GPIO2/3 ----------> MAX17048 + expansion header
          I2C0 GPIO0/1 (ID pins) -> 24C32 HAT EEPROM @ 0x50 (only device on ID bus)
          GPIO5/6/13/26 <-------- buttons (SHARED nets: also wired to ESP32, §3.3)
          GPIO12/16/19/20/21/23 -> expansion header (free IO)

  +------------------------------- ESP32-S3-WROOM-1-N16R8 -------------------------------+
  |  UART0 IO43/44 <-> Pi          USB IO19/20 -> USB-C #2 (DATA: BadUSB HID + flashing)|
  |  SPI2 (IO11 MOSI / IO12 SCK / IO13 MISO) shared bus:                               |
  |     |- CC1101 module  CS IO10, GDO0 IO9, GDO2 IO17  -> U.FL -> SMA whip / spring   |
  |     |- nRF24 module   CSN IO5, CE IO4, IRQ IO6      -> IPEX or PCB antenna          |
  |     '- microSD slot   CS IO14, CD IO7                                               |
  |  I2C (IO8 SDA / IO18 SCL): PN532 NFC module via J8 header  IRQ IO40, RST IO41       |
  |  -> external module (builder-sourced); its antenna is on the module                |
  |  IR: RX IO1 (TSOP38438), TX IO2 -> MMBT2222A -> 940 nm IR LED                       |
  |  Buttons IO15/16/38/39 (shared with Pi), spares IO47/48 -> test pads               |
  +-------------------------------------------------------------------------------------+

  Expansion header (2x8, 2.54 mm): 5V, 3V3, GND x2, I2C1, SPI0, GPIO x6, ESP_IRQ
      -> Flipper Zero / Cardputer / add-on modules (signal-level, see §3.4)
```

\* The 24C32 is powered from the Pi's 3V3 (header pin 1) per the HAT spec, **not** from the board 3V3 rail — see §3.1.

---

## 2. Component Selection

### 2.1 Compute / coprocessor

| Part | Choice | Why |
|---|---|---|
| ESP32 coprocessor | **ESP32-S3-WROOM-1-N16R8** (Espressif module, 16 MB flash / 8 MB octal PSRAM, onboard PCB antenna) — LCSC **C2913202** ✅ (JLCPCB part listing) | Bruce's best-supported target class; DIY Bruce builds standardize on exactly this variant. PSRAM is required for Bruce's heavier features (JS interpreter, large capture buffers). Module (not bare chip) = no RF matching to design, pre-certified radio, castellated PCBA-friendly footprint. **Layout:** IO35/36/37 are consumed by the octal PSRAM and IO26–32 by flash — the pin map in §3.2 avoids all of them. Antenna end of the module overhangs the board edge with a full copper keep-out on all layers (Espressif hardware design guidelines). |

### 2.2 Sub-GHz radio (CC1101)

**Choice: EBYTE E07-900M10S SMD module** (TI CC1101, 855–925 MHz, +10 dBm, 26 MHz TCXO-class crystal, 14 × 20 mm stamp-hole SMD) ✅ module verified via EBYTE's official store/datasheets; LCSC stocks the E07 family (LCSC hosts E07 datasheets) ⚠️ exact C-number for the M10S variant to confirm at BOM freeze.

- **Module vs bare CC1101:** bare CC1101 (QFN-20) needs a band-specific balun/matching network and its performance is layout-sensitive; worse, one matching network cannot cover 315/433/868/915 well. The module integrates crystal + matching, solders down like a part, and keeps RF risk at "antenna choice" level. This is the single biggest schedule-saver on the board.
- **Band reality check:** E07-900M10S covers 868 + 915 MHz. 433 MHz needs the pin-compatible sibling **E07-400M10S** (same 14 × 20 mm family). The footprint is designed to accept either; the kit BOM picks one per region (US kit = 900). Dual-populating both modules is a layout stretch goal (§7, Decision D2).
- **Antenna:** module RF pad → series 0 Ω selector → (a) U.FL/IPEX + short pigtail to a case-mounted **SMA whip** (recommended, Flipper-style range), or (b) soldered spring antenna on the stamp pad (cheapest, shorter range). See Decision D6.

### 2.3 2.4 GHz radio (nRF24L01+)

**Choice: EBYTE E01-ML01SP4 SMD module** (nRF24L01+ with PA+LNA, +20 dBm, IPEX antenna port, 14.5 × 18 mm) ✅ family verified via EBYTE datasheets hosted at LCSC ⚠️ exact C-number to confirm.
**Alternate: E01-ML01S** (0 dBm, onboard PCB antenna, 12 × 19 mm) ✅ verified via EBYTE/RobotShop — smaller and cheaper, fine for short-range MouseJack work.

Bruce's nRF24 features (spectrum, jammer; MouseJack-class attacks) are range-limited with a 0 dBm PCB antenna, which is why the PA version is primary. PA TX bursts (~115 mA) need a local 10 µF + 100 nF reservoir at the module — included in the schematic notes. One module only: the dual-nRF24 trick some DIY Bruce boards use is a jammer nicety, not worth the area (§7, D3).

### 2.4 NFC / RFID — PN532 vs MFRC522 vs ST25R

| Candidate | Bruce support | Capability | PCBA notes | Verdict |
|---|---|---|---|---|
| **NXP PN532** (bare chip, HVQFN-40 + 27.12 MHz crystal) | ✅ **Native** — Bruce's RFID config lists PN532 (and PN532Killer) as its supported modules; DIY Bruce builds run it on I2C @ 0x24 | ISO14443A/B, MIFARE, FeliCa, card emulation, peer modes | Needs external matching network + antenna (see below) | **Was RECOMMENDED — superseded 2026-10-18: external module instead (see Antenna strategy)** |
| MFRC522 | ❌ Not in Bruce's supported-module list (older forks only) — choosing it means writing/maintaining a driver in our fork | ISO14443A only, no emulation | Cheapest, simplest antenna | Rejected: firmware cost |
| ST25R3911B/3916 (Flipper Zero's chip) | ❌ No Bruce support at all | Best-in-class range + auto antenna tuning | QFN-32, needs full RF design + new driver | Rejected for v1: zero firmware support |

**Antenna strategy — superseded 2026-10-18.** The bare-chip plan above was dropped before layout, for two reasons: the bare PN532/C1 was the BOM's only part with **no LCSC listing** (a JLC sourcing gamble on every kit run), and its AN1445 matching network feeding a cabled case-back loop would have needed bench tuning on every prototype. **Current design:** NFC is an **external PN532 I2C module** (the common Elechouse-type board, builder-sourced like the Pi, display and battery) plugged into a dedicated 1×6 header **J8** — GND, 3V3, SCL (IO18), SDA (IO8), RST (IO41), IRQ (IO40); full spec in PINOUT.md §8. The module's antenna is factory-tuned; Bruce sees the same chip at the same 0x24 address on the same pins; and roughly 25 on-board parts (chip, crystal, decoupling set, EMC/matching network, U.FL) leave the BOM. The honest cost: NFC becomes a plug-in pod rather than an invisible case-back loop, and the module is hand-solder hobby-board grade rather than PCBA-integrated. The original D1 reasoning is kept in §7 for the record.

### 2.5 Infrared

| Function | Part | Notes |
|---|---|---|
| RX | **Vishay TSOP38438** (38 kHz) ⚠️ **through-hole (Minicast leaded), NOT SMD** [errata 2026-10-16] — needs JLC THT assembly or hand-soldering; exact LCSC C# to confirm. Alternate: **VS1838B** ✅ (the part DIY Bruce builds use; also leaded, JLC THT assembly or builder-solder) | Both candidates are leaded parts; TSOP38438 is the pick, VS1838B the Bruce-community-proven fallback. An SMD receiver swap is a possible rev-2 cleanup. |
| TX | **940 nm SMD IR LED** (e.g. Vishay VSMB10940-class or LCSC generic 1206 IR emitter) ⚠️ C# to confirm + **MMBT2222A** driver transistor (SOT-23, ubiquitous Basic part) | Bruce DIY builds drive the LED from a 2N2222 the same way; LED current ~100 mA pulsed from 3V3 via the transistor, never from the GPIO |

### 2.6 Power — charger, gauge, boost, 3.3 V

| Function | Part | Why |
|---|---|---|
| Charger + power-path | **TI bq24074** (VQFN-16) ⚠️ TI datasheet hosted at LCSC (family listing C473396 = bq24078 sibling); bq24074 exact C# to confirm | True power-path (system runs from USB while battery charges; DPPM sheds charge current before the system browns out), 1.5 A max charge, 10.5 V input OVP so cheap adapters can't hurt it, resistor-programmed (no I2C firmware needed), open-drain **CHG** pin drives the blue LED directly, works with the device "off" (charging LEDs alive whenever USB is in). Set: ISET ≈ 1.0 A charge; ILIM at max ≈ 1.4 A input [errata 2026-10-16: bq24074 ILIM programming caps at ~1.5 A per TI SLUS810N — a 3 A input limit is NOT achievable with this IC. Power-path still supplements system load from the battery (OUT rated 4.5 A), but net charging under a loaded Pi 5 will be slow/negative; a true 3 A input requires a different charger IC]. |
| Rejected charger alt. | IP5306 (LCSC C181692 ✅) — charger+boost+gauge in one eSOP-8 | Its boost tops out at ~2.4 A — cannot feed a Pi 5. Fine chip, wrong ceiling. TP4056 rejected (no power-path). |
| Fuel gauge | **MAX17048G+T10** (TDFN-8, I2C 0x36) ⚠️ part confirmed current ("recommended for new designs", Analog Devices); LCSC C# unverified — alternates if unstocked: MAX17043, or CW2015 (LCSC-native, register-compatible class of part, would need a driver check) | ModelGauge = no sense resistor, no learn cycle; **ALRT pin (open-drain) does double duty**: drives the red low-battery LED *and* interrupts the Pi (GPIO4). Powered straight from the battery so it never sleeps through a charge cycle. |
| 5 V boost | **TI TPS61088RHLT** (VQFN-20, 10 A switch synchronous boost) ⚠️ C# to confirm; topology proven at exactly this job — the open-source "Boosty" design delivers 5 V/5 A continuous from a 1S cell with this IC ✅ | Set VOUT = 5.1 V (Pi header voltage-drop margin). Inductor 2.2 µH, Isat ≥ 12 A (Cyntec PIMB065T-2R2M class ✅ from Boosty BOM). Design targets: **4 A continuous at VIN ≥ 3.3 V, 5 A peak**; cycle-by-cycle ILIM ≈ 11 A. Datasheet-faithful layout (tight SW loop, thermal vias) is mandatory — this is the one part of the board that can ruin your day. |
| 3.3 V rail | **Silergy SY8089AAAC** (SOT-23-5, 2 A sync buck) — LCSC **C78988, Basic library** ✅ | Fed **from 5V_SYS**, not from the battery — a buck can't make 3.3 V from a 3.1 V battery, and gating it with the power switch gives a clean "device off = ESP32 off". 2 A covers ESP32 TX peaks + PN532 field + both RF modules with >2× headroom. |
| Battery connector | JST-PH 2-pin SMD (B2B-PH-K-S, LCSC C131337 ✅ / S2B-PH family) | The de-facto standard on 1S pouches; builders' cells plug straight in. Plus a PPTC (hold ≈ 3 A / trip ≈ 6 A, 1812) and a note that the cell's own PCM is the last line of defense. |

### 2.7 USB, EEPROM, UI, display

| Function | Part | Notes |
|---|---|---|
| USB-C ×2 | **HRO TYPE-C-31-M-12** (16-pin mid-mount) — LCSC **C165948** ✅ (multiple independent BOMs) | Port 1 = charge-only: VBUS → bq24074 IN, CC1/CC2 each 5.1 kΩ Rd to GND, D+/D− unconnected. Port 2 = ESP32-S3 native USB: D+/D− → IO20/IO19 with **USBLC6-2SC6** ESD array, CC 5.1 kΩ Rd, VBUS → divider → IO21 (VBUS detect for HID host-presence). Keeping the two ports physically separate kills the classic "charging or BadUSB, pick one" mux problem. |
| HAT ID EEPROM | **24C32** (SOIC-8, I2C 0x50) ⚠️ generic part, stocked everywhere at LCSC; C# at BOM freeze | Per the official HAT spec: lives on the ID pins (GPIO0/1), powered from header pin 1 (Pi 3V3), WP tied to GND through a solder jumper so the ID blob can be flashed at the factory and locked later. The EEPROM blob is also where we declare PSU capability for the Pi 5 (§5.3). |
| Buttons ×4 | 6 × 6 mm SMD tact (LCSC C11135 ✅ Basic class / C318884 ✅) | To GND, one shared 10 kΩ pull-up per button on the board (neither MCU's internal pull-up is relied on — both chips read the same net, §3.3). Caps in the enclosure press them; place along the board edge under the case button plungers. |
| LEDs | 0805: green C19171391 ✅, red C84256 ✅, blue (0805 generic) ⚠️ | Green ← 5V_SYS (lit = device on). Red ← MAX17048 ALRT sink, anode to VSYS (lit = low battery, **works with device off**). Blue ← bq24074 CHG sink, anode to VSYS (lit = charging, works with device off). All anodes on VSYS/5V rails — the LEDs are hardware-driven, zero firmware involvement, exactly per spec. |
| Display connector | 2 × 7 (14-pin) 2.54 mm female header, top side | Matches the ubiquitous ILI9341 SPI module pinout (VCC/GND/CS/RST/DC/MOSI/SCK/LED/MISO + touch + SD pins). Module VCC fed 5V_SYS (module's own regulator makes its 3.3 V). Backlight pin driven through an **AO3400A** N-FET (LCSC-basic MOSFET) switched by Pi GPIO18 hardware PWM — the backlight draws 50–90 mA, far more than a GPIO pin may source. Touch pins = NC (non-touch build per spec). Module's microSD CS routed to Pi GPIO7 as a free bonus socket. |

### 2.8 microSD (ESP32 storage)

Push-push TF slot (LCSC C91145 ✅ / C112217 ✅), on the ESP32's shared SPI bus, CS = IO14. Bruce stores payloads, .sub files and PCAPs on SD; without it the fork leans on LittleFS and every capture has to squeeze through the 115200 UART to the Pi. The slot costs ~15 × 15 mm and one CS line — include it (§7, D5).

### 2.9 What was deliberately left off

- **No USB-UART bridge chip** (no CP2102/CH340): the ESP32-S3's native USB covers flashing/HID, and the Pi flashes it over the header UART. One less IC, one less driver.
- **No second nRF24, no Si5351, no GPS, no buzzer** — all present in various DIY Bruce boards; none are in Loki's locked scope. Spare ESP32 GPIOs are broken out to test pads if a future add-on wants them.
- **No Pi camera/display connectors, no audio.**

### 2.10 Antenna / RF placement summary

| Radio | Antenna | Placement rule |
|---|---|---|
| ESP32-S3 (BLE/WiFi) | Module PCB antenna | Board corner, keep-out all layers, away from Pi header |
| CC1101 | U.FL → SMA whip (or spring) | Opposite corner from ESP32; SMA on case edge |
| nRF24 (SP4) | IPEX whip inside case / (S) PCB antenna | Away from ESP32 antenna (both live at 2.4 GHz) |
| PN532 module (external) | J8 header (1×6) on the HAT | Builder-sourced module plugs into J8; antenna is on the module |
| Pi WiFi (nexmon) | On the Pi itself | Nothing on the HAT may overhang the Pi's antenna corner — HAT outline keep-out note for Pi 4/5 and Zero 2 W antenna zones |

### 2.11 Assembly reality check

Everything listed above is SMT and JLCPCB-placeable, **but not all on one side at HAT clearances**: the underside of a HAT faces the Pi's tall parts (USB/Ethernet on Pi 4/5), leaving room only for low-profile parts (EEPROM, gauge, passives, the FET) with standard 11 mm standoffs. Plan: **top side** = ESP32 module, both RF modules, SD slot, display header, buttons, USB-C ×2 (edge), charger/boost/buck power train; **bottom side** = 24C32, MAX17048, USBLC6, passives only. That means double-sided assembly at JLCPCB (a modest per-order surcharge) or JLC assembles the top and the few bottom parts are large-pad 0603/SOIC a builder can hand-solder in minutes. Flagged as Decision D8 — recommended: pay for double-sided; a "solder these 6 parts" step breaks the kit promise.

---

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

## 4. Power Budget

Estimates from published draw figures for each Pi class and module datasheets; ±20 % engineering tolerance. "Battery-side" = draw from the cell after conversion losses (boost ≈ 88 %, buck ≈ 92 % at these loads).

### 4.1 Subsystem draw (typical active use, at the rails)

| Subsystem | Rail draw | Notes |
|---|---|---|
| Pi Zero 2 W (nexmon monitor/deauth) | 5 V × 0.55 A ≈ 2.8 W | Idle ≈ 1.6 W; CPU+radio peaks 3.2 W |
| Pi 4 (same workload) | 5 V × 1.1 A ≈ 5.5 W | Peaks ≈ 7 W |
| Pi 5 (same workload) | 5 V × 1.6 A ≈ 8 W | Stress peaks 12–15 W (see §5.3 caveat) |
| Display module + backlight | ≈ 0.5 W | From 5V_SYS; backlight dominates |
| ESP32-S3 (BLE active, CPU up) | 3.3 V × 0.15 A ≈ 0.5 W | TX bursts to 0.35 A |
| CC1101 module | ≈ 0.12 W TX / 0.06 W RX | +10 dBm |
| nRF24 SP4 (PA) | ≈ 0.4 W TX bursts / 0.05 W RX | Bursty; average far lower |
| PN532 (field on) | ≈ 0.5 W | Field off ≈ 0.05 W |
| microSD + misc + LEDs | ≈ 0.15 W | |
| **Coprocessor + display subtotal** | **≈ 1.2 W typical / 1.9 W worst** | Radios rarely all transmit at once |

### 4.2 System totals and runtime — 5000 mAh cell (18.5 Wh nominal, ≈ 15.7 Wh usable)

| Configuration | Battery-side draw | Estimated runtime |
|---|---|---|
| Zero 2 W, screen on, radios idle | ≈ 3.4 W | **≈ 4.5 h** |
| Zero 2 W, active WiFi attack + radios | ≈ 4.6 W | **≈ 3.5 h** |
| Pi 4, active | ≈ 7.6 W | **≈ 2 h** |
| Pi 5, idle (screen on) | ≈ 4.9 W | **≈ 3.2 h** |
| Pi 5, active typical | ≈ 10.4 W | **≈ 1.5 h** |
| Pi 5, worst-case stress | ≈ 17 W | **≈ 55 min** |

### 4.3 Sizing conclusions

- **Boost converter rating:** TPS61088 configured for **4 A continuous / 5 A peak at 5.1 V** — this is a hard requirement driven by the Pi 5 row, and the reason a one-chip charger+boost (IP5306 class, 2.4 A) was rejected.
- **Battery peak current:** worst case ≈ 17 W ÷ 3.3 V (near-empty cell) ≈ **5.2 A from the cell** → the specified cell must be a **high-drain pouch rated ≥ 3C continuous (≥ 15 A)** — commodity "power bank" pouches with 1C ratings and 2 A PCM boards will brown out a Pi 5 build. This requirement goes in the kit's sourced-parts list in bold.
- **Charging while running:** bq24074 input limit 3 A (15 W) minus a running Pi 5's appetite leaves little for the battery — expected behavior, documented for builders: full-speed charging happens with the device off or idle; DPPM guarantees the system wins the fight for watts.

---

## 5. Power Tree & Pi 5 Notes

### 5.1 Tree

```
USB-C #1 VBUS ──> bq24074 IN ──> OUT = VSYS ──┬── battery (via BAT pin) ── 1S LiPo
                                              ├── MAX17048 (always on, µA)
                                              ├── red/blue LED anodes
                                              ├── power switch ──> TPS61088 EN ──> 5V_SYS ──> Pi pins 2+4, display VCC, backlight FET, SY8089 IN
                                              └── power switch ──> SY8089 EN (slaved to 5V_SYS PG region)
                                                                 └── 3V3 ──> ESP32, RF modules, PN532, EEPROM*no, SD, button pull-ups
```

### 5.2 "Off" semantics

The slide switch gates converter EN pins only. VSYS (and therefore the gauge + charge LEDs) is always live while a battery is fitted — that's what makes charge/low-batt indication work with the device off, at a total standby cost of the MAX17048's ~25 µA active / 4 µA hibernate draw plus bq24074 battery leakage (~µA). Weeks of shelf life, not months — the build guide should tell builders to unplug the cell for long storage (JST is right there).

### 5.3 Pi 5 powered through the header — read this twice

- The Pi 5's official 27 W USB-C supply negotiates 5 V/5 A by USB PD. **Fed through the GPIO header, there is no PD negotiation** — the Pi 5 assumes a weak supply and caps USB peripheral current + may throttle under load unless told otherwise. Mitigations, both cheap: (1) declare the PSU capability in the HAT EEPROM device-tree blob (the HAT+ mechanism), and (2) ship the Loki image with `usb_max_current_enable=1` in config.txt and document it for installer-route builders.
- Both 5 V header pins (2 + 4) are used, with a wide, via-stitched pour — a single pin is not a 4 A path.
- A Pi 5 under full CPU+radio stress on battery is a ~1-hour device (§4.2). That's physics, not a design flaw — the kit positions the Pi 5 as the "bench power / heavy cracking" option and the Zero 2 W as the pocket option.

---

## 6. Layout Constraints Checklist (for PCB phase)

1. 4-layer stackup (JLC 4-layer is the price sweet spot): L1 signals/RF, L2 solid GND, L3 power, L4 signals.
2. ESP32 antenna keep-out: no copper any layer under/past the module antenna; HAT must also not overhang the **Pi's** WiFi antenna zone (Pi antenna sits at the far end from the header on Zero 2 W; corner notch on Pi 4/5) — verify against each Pi's mechanical drawing at layout.
3. TPS61088: copy TI's reference layout geometry for the SW-node loop; inductor + input caps within 5 mm; thermal vias under the pad.
4. CC1101 / nRF24 modules at opposite board corners from the ESP32 antenna; U.FL connectors at the case edge; keep module RF pads clear of the display header's ground pins.
5. J8 NFC header at a board edge; keep its I2C run short and clear of the boost SW node. (The on-board PN532 matching network was deleted 2026-10-18 — NFC is an external module; §7 D1 is superseded.)
6. Button/LED edge placement must match the enclosure's plungers/openings — freeze case + PCB outlines together (Fusion 360 ↔ KiCad step exchange).
7. Bottom-side parts limited to ≤ 1.2 mm height within the HAT-over-Pi keep-out zones; nothing under the Pi's SoC/RAM area taller than the standoff budget.
8. microSD slot on the case edge (card must be insertable without opening the case — builders will swap payload cards constantly).

---

## 7. Decisions (all resolved 2026-10-16)

Justin accepted every recommendation below as written on 2026-10-16; the Recommendation column is now the design baseline.

| # | Decision | Options | **Recommendation** |
|---|---|---|---|
| D1 | NFC antenna | (a) U.FL → adhesive loop in case back (b) etched loop on HAT (c) revisit ST25R + write driver | **(a)** — lowest RF risk, proven pattern; etched loop detunes over the Pi. Revisit (b) in rev 2 with bench tuning time. **Superseded 2026-10-18:** NFC left the board entirely — external PN532 module on header J8 (§2.4); neither (a) nor (b) ships. |
| D2 | CC1101 band(s) | (a) one footprint, BOM picks E07-900M10S (868/915) or E07-400M10S (433) (b) dual footprints, both populated | **(a)** for v1 — one module, region-chosen. (b) doubles RF area and antenna count; Flipper-envy is not a v1 requirement. |
| D3 | nRF24 variant | (a) E01-ML01SP4 PA+LNA + IPEX (b) E01-ML01S 0 dBm PCB antenna | **(a)** — Bruce's nRF24 tricks are range games; PCB-antenna range disappoints. (b) is the fallback if area runs out. |
| D4 | Battery capacity | (a) 5000 mAh (b) 3500 mAh slimmer (c) 8000 mAh chunkier | **(a) 5000 mAh high-drain (≥3C) pouch, max cell envelope ≈ 68 × 54 × 11 mm** — Zero 2 W gets a real 3.5–4.5 h; a 3500 cell makes the Pi 5 config a <1 h toy. |
| D5 | microSD on ESP32 | (a) include slot (b) LittleFS only | **(a)** — Bruce's storage model assumes SD; one CS line is cheap insurance. |
| D6 | CC1101 antenna | (a) U.FL → SMA whip on case (b) spring antenna on module pad | **(a)** — Flipper-class range, and the whip unscrews for pocket carry. Footprint keeps (b) possible via the 0 Ω selector. |
| D7 | Buttons wired to ESP32 as well as Pi | (a) shared nets (b) Pi-only | **(a)** — required for the ESP32-side BadUSB confirm gate with the Pi off; costs four 1 kΩ resistors. |
| D8 | Assembly sides | (a) JLC double-sided assembly (b) top-only + builder hand-solders ~6 bottom parts | **(a)** — the kit promise is "attach Pi, print case, flash, go." (b) quietly breaks it. |
| D9 | Charge rate | (a) bq24074 @ ~1.0–1.5 A (b) I2C charger (BQ25895 class) @ 3 A | **(a)** for v1 — zero firmware, honest charge times. (b) is a rev-2 upgrade if builders complain. |
| D10 | Second ESP32 USB port usage | (a) BadUSB + flashing only (b) also expose USB-serial console for debugging | **(a)** — the Pi UART is the debug/console path; one personality per port keeps the fork simple. (Revisit if standalone Bruce use grows.) |

---

## 8. Verification Status & Sources

Verified live during research (Oct 2026): ESP32-S3-WROOM-1-N16R8 = LCSC C2913202 (JLCPCB listing, multiple projects); SY8089AAAC = C78988 Basic; HRO TYPE-C-31-M-12 = C165948; IP5306 = C181692 (considered, rejected on boost current); TF slots C91145/C112217; tact switches C11135/C318884; 0805 LEDs C84256/C19171391; JST B2B-PH-K-S = C131337. TPS61088 5 V/5 A-from-1S design point: Absurd Industries "Boosty" open design (TI datasheet topology). E07-900M10S / E07-400M10S / E01-ML01S / E01-ML01SP4: EBYTE official datasheets (LCSC hosts the E01/E07 family datasheets). Bruce PN532-over-I2C + shared-SPI + IO1/IO2 IR conventions: pr3y/Bruce supported-module list and multiple DIY Bruce board definitions (e.g. modabucksmain-pixel/bruce-diy-flipper pinout). bq24074 power-path/DPPM/4.4 V-class system rail behaviour: TI bq2407x datasheet (hosted at LCSC). MAX17048 ModelGauge + ALRT: Analog Devices datasheet.

**To confirm at BOM freeze (flagged ⚠️ in §2):** exact LCSC numbers for TPS61088RHLT, bq24074RGTR, MAX17048G+T10, E07-900M10S, E01-ML01SP4, TSOP38438, 940 nm SMD IR LED, 24C32 SOIC, 0805 blue LED. If MAX17048 is unstocked at order time, evaluate CW2015 (LCSC-native) — the Pi-side driver is ours either way.

**Not verified / known-unknowns:** real-world runtime (bench-measure on proto #1 and update §4); PN532 module variant quirks (I2C-mode switches, onboard pull-ups) — confirm on the reference module at bring-up; Pi 5 sustained current through header pins under thermal load (test with the worst-case cell at 3.4 V).
