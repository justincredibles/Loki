# Loki — KiCad Footprint Map (FOOTPRINTS.md)

Every line of the PINOUT.md Part C BOM, mapped to a concrete KiCad footprint.
Audit date: 2026-10-17. Target: KiCad 8/9 standard libraries.

**How the names were verified:** each `Library:Name` below was confirmed present in the
KiCad standard footprint libraries (kicad-footprints master) or in the manufacturer's
own library — not typed from memory. Custom footprints live in this repo under
`hardware/kicad/loki.pretty/` (library nickname **Loki**) — see `hardware/kicad/README.md`
for how to add it. The Espressif library is installed separately (also in the README).

**Result summary (102 BOM rows):**

| Source | Rows |
|---|---|
| KiCad standard library | 95 |
| Manufacturer library (Espressif) | 1 (U5) |
| Custom, in this repo (`Loki:`) | 4 (U3, U6, U7, U11) |
| **No footprint yet — unverified** | 1 (SD1) |
| No footprint needed (builder option) | 1 (spring antenna) |

⚠️ **Read the "Unverified geometry" section at the bottom before ordering boards.**
Three of the four custom footprints contain dimensions that could not be confirmed
from a datasheet and are flagged in their file descriptions as well.

---

## Main table

Symbol column = best match. "Custom/generic" means no verified part-specific symbol
exists in the standard libraries — draw one or use a generic symbol with the right
pin count; the footprint assignment is unaffected.

### ICs, modules, actives

| Refdes | Part | Package | KiCad symbol | Footprint (Library:Name) | Source | Notes |
|---|---|---|---|---|---|---|
| U1 | TI bq24074RGTR charger | VQFN-16 3×3, P0.5, EP | custom/generic QFN-16 | `Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm` | KiCad standard | ⚠️ EP size: RGT exposed pad ≈1.7×1.7 assumed from package class; library also has EP1.45/1.75/1.9 variants — confirm against TI RGT drawing (SLUS810N package section) and swap the suffix if needed. Symbol must expose the EP as pin 17 (GND). |
| U2 | MAX17048G+T10 fuel gauge | TDFN-8 2×2, P0.5, EP | custom/generic DFN-8 | `Package_DFN_QFN:DFN-8-1EP_2x2mm_P0.5mm_EP0.9x1.5mm` | KiCad standard | ⚠️ Nearest standard EP size; ADI package EP ≈0.95×1.55 — treat EP dimensions as approximate (electrically it's GND; solder coverage is forgiving). |
| U3 | TI TPS61088RHLT boost | VQFN-20 (RHL) 4.5×3.5, P0.5, EP | custom (must expose EP as pin 21) | `Loki:TPS61088_RHL_VQFN-20_3.5x4.5_P0.5` | **Custom in repo** | No standard QFN-20 exists in 4.5×3.5. Built from TI drawing RHL0020A: pads 0.28×0.6, EP 2.05×3.05 (= pin 21, PGND), pin split 7/3/7/3 decoded from datasheet pin order (SW×4 = 4–7, VOUT×3 = 14–16). See unverified list, item 3. |
| U4 | SY8089AAAC buck | SOT-23-5 | custom/generic SOT-23-5 regulator | `Package_TO_SOT_SMD:SOT-23-5` | KiCad standard | Pinout is part-specific (1=EN, 2=GND, 3=LX, 4=IN, 5=FB) — wire the symbol to match PINOUT §4, not a generic 1117-style pinout. |
| U5 | ESP32-S3-WROOM-1-N16R8 | SMD module, 41 pads | `Espressif:ESP32-S3-WROOM-1` (Espressif lib) | `Espressif:ESP32-S3-WROOM-1` | Manufacturer library — github.com/espressif/kicad-libraries (also in KiCad PCM) | **Not** in KiCad's standard RF_Module library (verified — it has ESP32-WROOM-32/32U, S2-WROVER, but no S3-WROOM-1). Do not substitute the WROOM-32 footprint: different pad map. Antenna keep-out per PINOUT §5 still applies at layout. |
| U6 | EBYTE E07-900M10S (or E07-400M10S) | Stamp-hole SMD, 22 pads | custom/generic 22-pad module | `Loki:EBYTE_E07-900M10S` | **Custom in repo — ⚠️ GEOMETRY UNVERIFIED** | Body 14×20 mm, 1.27 mm pitch, pad functions per EBYTE manual §3 — those are datasheet facts. Pad size, row inset, pin-1 corner and numbering direction are **not** confirmed (manual dimension drawing is graphical). See unverified list, item 1. Same footprint serves the 433 MHz E07-400M10S (pin-compatible). |
| U7 | EBYTE E01-ML01SP4 | Stamp-hole SMD, 10 pads | custom/generic 10-pad module | `Loki:EBYTE_E01-ML01SP4` | **Custom in repo — ⚠️ GEOMETRY UNVERIFIED** | Body 14.5×18 mm, 1.27 mm interface, pad functions per EBYTE datasheet — datasheet facts. Two-row arrangement, pad size, row inset, pin-1 corner **not** confirmed. See unverified list, item 2. Pad order is NOT the DIP nRF24 order (PINOUT §7). |
| U8 | NXP PN532/C1 | HVQFN-40 5×5, P0.4, EP | custom (40-pin + EP) | `Package_DFN_QFN:QFN-40-1EP_5x5mm_P0.4mm_EP3.6x3.6mm` | KiCad standard | ⚠️ NXP SOT618-1 exposed-pad exact size not verified from the package drawing. Only other standard option is EP3.8x3.8 — check SOT618-1 and swap if needed. Pin *numbers* ride on your symbol (PINOUT §8, unverified item 6 there). |
| U9 | 24C32 EEPROM | SOIC-8 | generic 24Cxx SOIC-8 symbol | `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm` | KiCad standard | |
| U10 | ST USBLC6-2SC6 ESD | SOT-23-6 | custom (flow-through pinout) | `Package_TO_SOT_SMD:SOT-23-6` | KiCad standard | ⚠️ Pin numbering is the part's flow-through arrangement — confirm against ST datasheet for the exact order code (PINOUT Part E item 8). |
| U11 | Vishay TSOP38438 IR receiver | Minicast **THT**, SIP-3 | generic 3-pin (Device-level) | `Loki:TSOP38438_Minicast_THT` | **Custom in repo** | Through-hole part (PINOUT erratum 3) — JLCPCB THT assembly or hand-solder. Lead pitch 2.54 nom; pin order **1=OUT, 2=GND, 3=VS** (sibling series swap VS/GND — do not cross-wire). Body silk outline approximate; see unverified list, item 4. |
| Q1 | MMBT2222A | SOT-23 | `Device:Q_NPN_BCE` | `Package_TO_SOT_SMD:SOT-23` | KiCad standard | Standard pinout 1=B, 2=E, 3=C matches the symbol. |
| Q2 | AO3400A N-FET | SOT-23 | `Device:Q_NMOS_GDS` | `Package_TO_SOT_SMD:SOT-23` | KiCad standard | Pinout 1=G, 2=S, 3=D matches. |
| D1 | 940 nm IR LED (VSMB10940 class) | 1206 | `Device:LED` | `LED_SMD:LED_1206_3216Metric` | KiCad standard | Check polarity marks against the chosen LED's datasheet. |
| D2 | LED green | 0805 | `Device:LED` | `LED_SMD:LED_0805_2012Metric` | KiCad standard | |
| D3 | LED red | 0805 | `Device:LED` | `LED_SMD:LED_0805_2012Metric` | KiCad standard | |
| D4 | LED blue | 0805 | `Device:LED` | `LED_SMD:LED_0805_2012Metric` | KiCad standard | |
| L1 | 2.2 µH power inductor (Cyntec PIMB065T class) | ~6.5×6.5 mm | `Device:L` | `Inductor_SMD:L_6.3x6.3_H3` | KiCad standard | ⚠️ Closest standard body (6.3 vs 6.5 mm nominal). Verify pad size/position against the frozen inductor's recommended land pattern; widen pads in a local copy if its datasheet shows larger pads. |
| L401 | 2.2 µH | 2520/2525 class | `Device:L` | `Inductor_SMD:L_1008_2520Metric` | KiCad standard | |
| L801, L802 | 560 nH RF | 0603/0805 | `Device:L` | `Inductor_SMD:L_0603_1608Metric` (alt `L_0805_2012Metric`) | KiCad standard | Pick per the frozen part's case size. |
| Y1 | 27.12 MHz crystal, CL 10 pF | 3225, 4-pin | `Device:Crystal_GND24` | `Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm` | KiCad standard | Library nickname is `Crystal` (not Crystal_SMD). Pads 2/4 are the case/GND pads on this footprint family — ground them. |

### Connectors, switches, protection

| Refdes | Part | Package | KiCad symbol | Footprint (Library:Name) | Source | Notes |
|---|---|---|---|---|---|---|
| J1 | 2×20 stacking header (Pi 40-pin) | THT socket | generic 2×20 | `Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical` | KiCad standard | A stacking header is a long-pin **socket** on the HAT side — use the PinSocket footprint, not PinHeader. |
| J2, J3 | HRO TYPE-C-31-M-12 USB-C | SMD mid-mount | generic USB-C receptacle | `Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12` | KiCad standard | ✅ Exact part footprint exists in the standard library. |
| J4 | JST-PH battery connector, LCSC C131337 | see note | generic 2-pin | `Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical` | KiCad standard | ⚠️ **Part-name vs BOM conflict:** PINOUT §13/Part C names **B2B-PH-K-S**, which is JST's **through-hole** vertical part — the footprint at left matches the named part. The BOM's package column says "SMD"; if the physical C131337 part you receive is the surface-mount version, use `Connector_JST:JST_PH_B2B-PH-SM4-TB_1x02-1MP_P2.00mm_Vertical` instead. Confirm which part C131337 actually is before layout freeze. |
| J5 | 2×7 female header (display) | THT | generic 2×7 socket | `Connector_PinSocket_2.54mm:PinSocket_2x07_P2.54mm_Vertical` | KiCad standard | |
| J6 | 2×8 expansion header | THT | generic 2×8 | `Connector_PinHeader_2.54mm:PinHeader_2x08_P2.54mm_Vertical` | KiCad standard | If you want a female expansion socket instead: `Connector_PinSocket_2.54mm:PinSocket_2x08_P2.54mm_Vertical` (SMD PinHeader variant also exists). |
| J7, J8 | U.FL / IPEX RF connector | SMD | generic coax | `Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical` | KiCad standard | Generic U.FL/MHF1-class land pattern — fits the clone connectors in this class. |
| SD1 | microSD push-push slot, LCSC C91145 / C112217 | SMD | custom card-slot symbol | **— none assigned —** | **⚠️ UNVERIFIED** | No standard or community footprint matches this generic push-push slot class. KiCad's Connector_Card microSD options (Hirose DM3 hinged, Molex 104031-0811 push-**pull**, Würth 693072010801) have different shells/tabs/contact positions — **do not substitute**. Build the footprint from the chosen slot's LCSC datasheet land pattern. See unverified list, item 5. |
| SW1 | Slide switch, SPDT (power, EN-level) | SMD | generic SPDT switch | `Button_Switch_SMD:SW_SPDT_CK-JS102011SAQN` | KiCad standard | Carries only TPS61088 EN current (µA), so any small SPDT works electrically. Alt: `Button_Switch_SMD:SW_SPDT_PCM12`. Verify pad layout against the actual switch purchased — slide-switch footprints are not interchangeable between families. |
| SW2–SW5 | Tact switch 6×6 mm, LCSC C11135 | SMD | `Device:SW_SPST` ×4 | `Button_Switch_SMD:SW_Push_1P1T_NO_6x6mm_H9.5mm` | KiCad standard | The 6×6 SMD tact pad pattern is common across stem heights (the H9.5 in the name is the modelled stem, pads are the standard 6×6 pattern). Verify against the C11135 drawing at BOM freeze. |
| SJ1 | Solder jumper (EEPROM WP) | 0603 pads | solder-jumper symbol | `Jumper:SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm` | KiCad standard | Closest standard to PINOUT's 1.2×1.5 mm CC islands. Bridged-default variants of the same footprint exist in the library if the default state changes. |
| F1 | PPTC ≈3 A hold / ≈6 A trip | 1812 | generic polyfuse | `Fuse:Fuse_1812_4532Metric` | KiCad standard | Sizing tension is a design decision, not a footprint issue — see PINOUT §13. |
| F2 | PPTC 500 mA hold | 1812 | generic polyfuse | `Fuse:Fuse_1812_4532Metric` | KiCad standard | |
| TP | Test pads ×~6 (IO3, IO47, IO48, VSYS, 3V3, PGOOD) | — | `Connector:TestPoint` | `TestPoint:TestPoint_Pad_1.0x1.0mm` | KiCad standard | Round variant `TestPoint_Pad_D1.0mm` also exists. |
| — | CC1101 spring antenna (DNP option) | — | — | **No footprint** | n/a | Builder option soldered at the post-R601 node (PINOUT §6); a plain ~1.5 mm pad drawn in layout is enough. Fit exactly one antenna path (J7 whip *or* spring). |

### Resistors (all `Device:R`, footprint `Resistor_SMD:R_0603_1608Metric` unless noted)

| Refdes | Value / role | Notes |
|---|---|---|
| R101 | 890 Ω 1% (U1 ISET) | |
| R102 | 1.1 kΩ (U1 ILIM) | |
| R103 | 10 kΩ (U1 TS defeat) | |
| R104 | 1.0 kΩ (D4 blue LED) | |
| R105, R106, R511, R512 | 5.1 kΩ (USB-C Rd ×4) | |
| R201 | 1.0 kΩ (D3 red LED) | |
| R202, R203, R513, R514 | 4.7 kΩ (I²C pull-ups) | |
| R301 | 182 kΩ 1% (boost FB top) | |
| R302 | 56 kΩ 1% (boost FB bottom) | |
| R303 | 100 kΩ (boost ILIM) | |
| R304 | 270 kΩ (boost FSW — to SW node) | |
| R305 | 10 kΩ (boost COMP) | |
| R401 | 453 kΩ 1% (buck FB top) | |
| R402 | 100 kΩ (buck FB bottom) | |
| R403 | 1 MΩ (buck EN pull-down) | |
| R501, R503, R506 | 10 kΩ (ESP32 EN/IO0/IRQ pull-ups) | |
| R502, R504 | 1 kΩ (EN/IO0 series from Pi) | |
| R505 | 499 Ω (U0TXD series) | |
| R507, R508 | 0 Ω (USB series; accepts 22 Ω) | |
| R509, R510 | 100 kΩ (VBUS detect divider) | |
| R601 | 0 Ω (CC1101 antenna selector) | |
| R801, R802 | 3.3 Ω (PN532 Rq — bench-tune) | |
| R803 | 1 kΩ (PN532 RX R1) | |
| R804 | 2.7 kΩ (PN532 RX R2 — bench-tune) | |
| R901, R902, R903 | 10 kΩ (SD pull-ups) | |
| R1001 | 100 Ω (TSOP supply filter) | |
| R1002 | 18 Ω (IR LED current) | **`Resistor_SMD:R_1206_3216Metric`** — 1206 for pulse dissipation (PINOUT §10.2) |
| R1003 | 1 kΩ (IR TX base) | |
| R1101 | 100 Ω (backlight FET gate) | |
| R1102 | 100 kΩ (gate pull-down) | |
| R1110–R1113 | 10 kΩ (button pull-ups) | |
| R1114–R1117 | 1 kΩ (button series to Pi) | |
| R1120 | 1.0 kΩ (D2 green LED) | |

### Capacitors (all `Device:C`, X7R/X5R; footprint `Capacitor_SMD:C_0603_1608Metric` unless noted)

| Refdes | Value / role | Footprint |
|---|---|---|
| C101 | 1 µF (charger IN) | 0603 |
| C102, C103 | 4.7 µF (charger BAT / OUT) | `Capacitor_SMD:C_0805_2012Metric` |
| C201 | 0.1 µF (gauge VDD) | 0603 |
| C301–C303, C306–C308 | 22 µF X5R ≥10 V (boost IN ×3 / OUT ×3) | `Capacitor_SMD:C_1206_3216Metric` recommended (22 µF X5R at ≥10 V is realistic in 1206; `C_0805_2012Metric` exists if an 0805 part is frozen — expect heavy DC-bias derating) |
| C304 | 0.1 µF (boost VIN bypass) | 0603 |
| C305 | 0.1 µF (boost BOOT) | 0603 |
| C309 | 2.2 µF (boost VCC) | 0603 |
| C310 | 47 nF (boost SS) | 0603 |
| C311 | 4.7 nF C0G (boost COMP) | 0603 |
| C401 | 22 µF X5R 10 V (buck IN) | `C_1206_3216Metric` recommended, 0805 alt as above |
| C402, C403 | 22 µF X5R (buck OUT) | `C_1206_3216Metric` recommended, 0805 alt as above |
| C404 | 22 pF (buck feedforward) | 0603 C0G preferred |
| C501 | 22 µF (ESP32 supply) | `Capacitor_SMD:C_0805_2012Metric` |
| C502 | 0.1 µF (ESP32 supply) | 0603 |
| C503 | 1 µF (ESP32 EN RC) | 0603 |
| C504 | 0.1 µF (VBUS detect) | 0603 |
| C601 | 0.1 µF (CC1101 supply) | 0603 |
| C602 | 10 µF (CC1101 supply) | `Capacitor_SMD:C_0805_2012Metric` |
| C701 | 10 µF (nRF24 reservoir) | `Capacitor_SMD:C_0805_2012Metric` |
| C702 | 0.1 µF (nRF24 supply) | 0603 |
| C801, C803, C805, C806, C807, C808 | 0.1 µF (PN532 decoupling) | 0603 |
| C802, C804 | 4.7 µF (PN532 DVDD / TVDD) | `Capacitor_SMD:C_0805_2012Metric` |
| C809, C810 | 220 pF (PN532 EMC C0) | 0603 |
| C811, C812 | 18 pF C0G (PN532 C1 — bench-tune) | 0603 |
| C813, C814 | 56 pF C0G (PN532 C2 — bench-tune) | 0603 |
| C815, C816 | 22 pF C0G (crystal load) | 0603 |
| C817 | 1 nF (PN532 CRX) | 0603 |
| C901 | 0.1 µF (SD supply) | 0603 |
| C902 | 10 µF (SD supply) | `Capacitor_SMD:C_0805_2012Metric` |
| C1001 | 1 µF (TSOP filter) | 0603 |
| C1101 | 0.1 µF (EEPROM VCC) | 0603 |
| C1110–C1113 | 100 nF (button debounce, may be DNP) | 0603 |

---

## Custom footprints in `hardware/kicad/loki.pretty/`

| File | For | Geometry source |
|---|---|---|
| `EBYTE_E07-900M10S.kicad_mod` | U6 | EBYTE E07-900M10S User Manual v1.0: body 14×20 mm, 1.27 mm half-hole interface, 22 pads, pin functions (§3 table). Pad size/placement per generic castellated practice — **unverified**, see below. |
| `EBYTE_E01-ML01SP4.kicad_mod` | U7 | EBYTE E01-ML01SP4 datasheet/manual: body 14.5×18 mm, 1.27 mm interface, 10 pads, pin functions. Arrangement **unverified**, see below. |
| `TPS61088_RHL_VQFN-20_3.5x4.5_P0.5.kicad_mod` | U3 | TI package drawing RHL0020A (4219071/A) via TPS61088 datasheet (SLVSCM8D / SLVSE52A): body 4.5×3.5, pitch 0.5, EP 3.05×2.05, land pad length 0.6, 7-pin-side span 4.3. |
| `TSOP38438_Minicast_THT.kicad_mod` | U11 | Vishay Doc. 82491 family: lead pitch 2.54 nom, pin order 1=OUT/2=GND/3=VS. Body outline approximate. |

## ⚠️ Unverified geometry — check before fabrication

1. **U6 E07-900M10S (custom footprint).** Confirmed from the manual: body 14×20 mm, 22 pads, 1.27 mm half-hole pitch, every pad's function. **Not confirmed:** pad width/length (file uses 0.9×2.2 mm), pad-row inset from the body edge (rows at x=±6.6 mm on a 14 mm-wide body), which corner is pin 1, and numbering direction (file: pins 1–11 down the left edge, 12–22 up the right, pin 21 ANT second from top-right). The manual's §3 dimension drawing carries these numbers but is graphical. **Fix:** read the drawing in the EBYTE manual (or measure a physical module with calipers) and adjust the two row positions / rotate as needed — pad pitch and functions won't change.
2. **U7 E01-ML01SP4 (custom footprint).** Confirmed: body 14.5×18 mm (one EBYTE manual for the sibling SP2 says 14.85×18 — another reason to measure), 10 pads, 1.27 mm interface, pad functions. **Not confirmed:** that the pads split 5+5 across the two long edges (file's assumption), pad size (0.9×2.2 mm), row inset (±6.6 mm), pin-1 corner. **Fix:** same as U6 — manual §3 drawing or calipers on a real module.
3. **U3 TPS61088 (custom footprint).** Body, pitch, EP (3.05×2.05), pad length (0.6) and the 7-pin sides' outer span (4.3 mm) are from TI's RHL0020A drawing. **Assumed:** the 3-pin (top/bottom) rows use the same 0.4 mm toe as the sides (centres at ±2.35 mm) — the drawing's second span dimension could not be decoded with certainty from the datasheet text. Cross-check this one dimension against the TI drawing before fab; everything else is drawing-sourced. TI's stencil example also segments the EP paste into 6 windows ≈0.92×1.05 mm — optional refinement; the file ships a single EP pad (fine for proto/hot-air assembly).
4. **U11 TSOP38438 (custom footprint).** Lead pitch 2.54 mm nom and pin order are datasheet values (Vishay Doc. 82491; PINOUT §10.1). **Approximate:** the silkscreen body outline (drawn 6.0×4.8 mm from the sibling Minicast-family drawing 6.550-5263.01-4) — it affects only silk/courtyard, not the holes. Pin 1 = OUT is the leftmost lead with the lens facing you, leads down; the footprint marks pin 1 with a square pad and silk dot — confirm orientation against the datasheet drawing when placing.
5. **SD1 microSD slot — no footprint.** Missing: the LCSC C91145 / C112217 datasheet land pattern (contact positions, shell solder tabs, card-detect contact position). Get it from the datasheet link on the LCSC product page of whichever part is frozen, then draw the footprint from it. Do not substitute KiCad's Molex/Hirose/Würth card footprints. CD-contact polarity assumption is also still open (PINOUT Part E item 14).
6. **Standard-library EP sizes (U1, U2, U8).** The QFN/DFN picks are the nearest standard exposed-pad sizes: U1 EP1.7×1.7 (variants 1.45/1.75/1.9 exist), U2 EP0.9×1.5 (ADI ≈0.95×1.55), U8 EP3.6×3.6 (variant 3.8×3.8 exists; NXP SOT618-1 exact EP unverified). All three EPs are ground/thermal — a small EP mismatch solders fine, but swap the suffix if the package drawing disagrees.
7. **J4 JST-PH (see table).** Named part (B2B-PH-K-S) is THT; BOM package column says SMD. The two candidate footprints are both standard — pick after confirming what LCSC C131337 physically is.

## Sources

- KiCad standard footprint libraries, kicad-footprints master (library contents verified 2026-10-17).
- Espressif official KiCad libraries — https://github.com/espressif/kicad-libraries (`footprints/Espressif.pretty/ESP32-S3-WROOM-1.kicad_mod` + matching symbol).
- TI TPS61088 datasheet SLVSCM8D / TPS61088-Q1 SLVSE52A, package drawing RHL0020A (4219071/A).
- EBYTE E07-900M10S User Manual v1.0; EBYTE E01-ML01SP4 Datasheet V1.0 / User Manual.
- Vishay TSOP382../TSOP384.. datasheet, Doc. 82491 (Minicast package family drawings).
- PINOUT.md (this repo, `hardware/PINOUT.md`) — BOM and pin tables audited here.
