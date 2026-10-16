# Loki — Pin Mapping & Complete KiCad Build Sheet

Complete schematic + placement reference for the Loki HAT PCB: every subsystem, every component, every net, and the placement rules that matter electrically. The pin tables in **Part B** are the original DESIGN.md §3 tables, kept verbatim. If this file and `hardware/DESIGN.md` ever disagree on architecture, DESIGN.md wins; if they disagree on a component value, **this file wins** (it is derived from the manufacturers' datasheets, cited per section).

Values are marked: **(DS)** = taken from / calculated with the cited datasheet or app note; **(CALC)** = calculated here, arithmetic shown; **(EC)** = engineering choice where the datasheet specifies no value — treat as a starting point, not gospel; **⚠️ VERIFY** = could not be confirmed from a primary source — check before fabrication.

**Revision:** expanded 2026-10-16 from the §3 pin tables into the full build sheet.

---

## ⚠️ Read first — three errata against DESIGN.md found during datasheet verification

1. **bq24074 input limit cannot be 3 A.** DESIGN.md §2.6 says "ILIM ≈ 3 A input". Per TI SLUS810N, the ILIM resistor range (1.1–8 kΩ) programs only **200 mA–1.5 A**, and IN is rated 1.5 A recommended / 1.6 A abs-max. This build sheet sets ILIM to the maximum (~1.4 A). System load above the input limit is supplemented from the battery by the power-path (OUT is rated 4.5 A), so the device still works — but **net charging while a Pi 5 is under load will be slow or negative**, and full-speed charging happens with the device off/idle (as DESIGN.md §4.3 already anticipates). If a future rev wants real 3 A input, the charger IC must change.
2. **"NXP AN10688" is the wrong document number for the PN532 antenna design.** No PN532 document numbered AN10688 could be found. The antenna/EMC/matching values here come from **NXP AN1445** (*Antenna design guide for MFRC52x, PN51x and PN53x*, which explicitly covers PN532) plus the PN532/C1 data sheet §13 reference circuit.
3. **TSOP38438 is a through-hole part** (Vishay Minicast, leaded), not SMD as DESIGN.md §2.5 calls it. Its footprint is THT — JLCPCB THT assembly or a builder-soldered part. The VS1838B fallback is also a leaded can. There is no true-SMD receiver in the current selection; if that matters, the IR receiver choice needs a rev-2 revisit.

---

## Net names used throughout

| Net | Meaning |
|---|---|
| `VBAT_RAW` | Battery + at the connector, before the protection PPTC |
| `VBAT` | Battery + after F1 — feeds charger BAT pin and the fuel gauge |
| `VSYS` | bq24074 OUT — always live while a battery is fitted or USB is plugged in (≈ battery voltage, or regulated 4.4 V with USB present) |
| `5V_SYS` | TPS61088 output, regulated 5.1 V — present only when the power switch is ON |
| `3V3` | SY8089 output, 3.3 V — present only when the power switch is ON |
| `3V3_ID` | Isolated net: Pi header pin 1 → EEPROM only (HAT spec) |
| `PWR_EN` | Power-switch output → TPS61088 EN |
| `GND` | Common ground (solid L2 plane, 4-layer stackup per DESIGN.md §6) |

## Reference-designator groups

1xx charger/USB-C #1 · 2xx fuel gauge · 3xx 5 V boost · 4xx 3.3 V buck · 5xx ESP32/USB-C #2 · 6xx CC1101 · 7xx nRF24 · 8xx PN532 · 9xx microSD · 10xx IR · 11xx Pi interface/display/EEPROM/buttons/expansion · battery parts ungrouped (J4, F1).

---

# Part A — Subsystem build sheets

## 1. Power input & charging — TI bq24074 (U1)

Source for all values: TI **SLUS810N** (bq2407x family datasheet), sections cited per item.
U1 = bq24074RGTR, VQFN-16 + thermal pad.

### 1.1 USB-C #1 — charge-only port (J2)

J2 = HRO TYPE-C-31-M-12, LCSC C165948 ✅.

| J2 terminal | Connection |
|---|---|
| VBUS (all) | Net `USB1_VBUS` → U1 pin 13 (IN). **5 V only by design** — no USB-PD circuitry anywhere on this port |
| CC1 | R105, 5.1 kΩ → GND (Rd, marks the port as a sink) |
| CC2 | R106, 5.1 kΩ → GND |
| D+ / D− | No connect — this port carries no data, ever (decision D10's mirror) |
| Shield | GND (chassis fingers to enclosure if metal hardware is used) |

### 1.2 U1 pin-by-pin

| Pin | Name | Connection | Notes / source |
|---|---|---|---|
| 13 | IN | `USB1_VBUS`; **C101 = 1 µF** IN→GND at the pin | DS: bypass range 1–10 µF, example 1 µF (§7, §10.2.2.5) |
| 16 | ISET | **R101 = 890 Ω** → GND | **(CALC)** R_ISET = K_ISET / I_CHG, K_ISET = 890 A·Ω typ (§8.5, §10.2.2.2.1). 890/890 = **1.00 A** charge current (DESIGN.md §2.6 set point). Alternatives: 742 Ω → 1.2 A; 593 Ω → 1.5 A (593 Ω is the bottom of the allowed 590 Ω–8.9 kΩ range — use 1 % parts). Never leave ISET open: open = charging disabled |
| 12 | ILIM | **R102 = 1.1 kΩ** → GND | **(CALC)** I_IN-MAX = K_ILIM / R_ILIM, K_ILIM = 1550 A·Ω (design-example value, §10.2.2.2.2; electrical table typ 1610, range 1500–1720). 1550/1100 ≈ **1.41 A typ** — the maximum this IC can be programmed for. See erratum 1 |
| 5 | EN2 | → `USB1_VBUS` | With EN1 = 0 this selects ILIM-resistor mode whenever USB is plugged in (Table 7-2: EN2=1, EN1=0 → ILIM). USB absent → EN2 falls to its internal ~285 kΩ pull-down → USB100 mode, which is harmless with no input present. ⚠️ VERIFY: EN1/EN2 abs-max voltage was not explicitly extracted; the family's other logic/status pins are 7 V-class (§8.1) and IN is 5 V in this design, but confirm EN pin rating at BOM freeze |
| 6 | EN1 | → GND | See EN2 row. (EN2=0, EN1=1 would be USB500; EN2=1, EN1=1 is standby — neither is used) |
| 4 | CE | → GND | Charge enable, active-low; low = charging enabled (§7). Internal pull-down exists, but tie it explicitly — do not float |
| 14 | TMR | **No connect** (open) | Open = datasheet default safety timers: pre-charge 1800 s typ, max fast-charge 18000 s (5 h) typ (§9.3.5.6). Do NOT tie to GND (that disables all safety timers). A resistor 18–72 kΩ → GND programs custom timers via t = K_TMR × R_TMR (K_TMR = 48 s/kΩ) if a rev wants them |
| 15 | ITERM | **No connect** (open) | Open = internal default termination at 10 % of I_CHG typ (§7, §8.5) = 100 mA at our 1.0 A set point. To program explicitly: R_ITERM = I_TERM × R_ISET / 0.030 → for 100 mA with R_ISET = 890 Ω, R_ITERM ≈ 2.97 kΩ → GND (§9.3.5.2) |
| 1 | TS | **R103 = 10 kΩ** → GND | Datasheet-sanctioned thermistor defeat (§7, §9.3, §10.2.2.3): the kit's 2-wire JST-PH cells bring no thermistor lead to the board. V_TS ≈ 75 µA × 10 kΩ = 0.75 V, inside the 0.30–2.10 V valid window. Never tie TS directly to GND or leave it open. (If a future cell has a 10 kΩ NTC lead, route it here instead: Semitec 103AT-2 is the specified thermistor) |
| 2, 3 | BAT | Net `VBAT`; **C102 = 4.7 µF** BAT→GND at the pins | DS example 4.7 µF; allowed 4.7–47 µF ceramic (§7, §10.2.2.5) |
| 10, 11 | OUT | Net `VSYS`; **C103 = 4.7 µF** OUT→GND at the pins | DS example 4.7 µF; allowed 4.7–47 µF. With USB present OUT regulates to a fixed **4.4 V typ** (4.3–4.5 V) regardless of battery voltage (§8.5, §9.3.4.1) — remember VSYS can be 4.4 V when sizing anything hanging off it. Bulk capacitance for the boost's pulsed draw lives at U3's input (§3) |
| 9 | CHG | → blue LED network (§1.3) | Open-drain, active-low while charging; abs-max sink 15 mA, pin max 7 V (§8.1) |
| 7 | PGOOD | No connect (test pad optional) | Open-drain power-good; unused in v1. Do not tie to a rail |
| 8 | VSS | GND | |
| EP | Thermal pad | GND | Must be at VSS potential with thermal vias; the VSS pin must still be grounded separately — the pad is not the primary ground path (§7) |

**Placement:** C101/C102/C103 within ~3 mm of their pins. U1 sits near the USB-C #1 board edge so the IN run from J2 is short.

### 1.3 Blue "charging" LED (D4)

VSYS → **R104 = 1.0 kΩ** → D4 anode; D4 cathode → U1 pin 9 (CHG). D4 = 0805 blue (LCSC: confirm at BOM freeze ⚠️).

**(CALC)** With USB present VSYS = 4.4 V; blue Vf ≈ 3.0 V: I ≈ (4.4 − 3.0) / 1000 ≈ **1.4 mA** — well under CHG's 15 mA abs-max, bright enough for a modern high-efficiency 0805. (TI's own typical circuit uses 1.5 kΩ from OUT, §10.2.2.4; 1.0 kΩ trades a little current for visibility.) The LED lights whenever the charger is actively charging, including with the device switched off — exactly per spec, zero firmware.

---

## 2. Fuel gauge — MAX17048 (U2)

Source: Analog Devices **MAX17048/MAX17049 datasheet, doc. 19-6171 Rev 7** (cited "ADI DS").
U2 = MAX17048G+T10, TDFN-8 + EP. I²C address **0x36** (7-bit).

| Pin | Name | Connection | Notes / source |
|---|---|---|---|
| 3 | VDD | Net `VBAT` (direct from battery) | On the MAX17048, VDD is **both** supply and voltage-sense input (ADI DS Table 3: all 1S configs power VDD directly from the battery). Range 2.5–4.5 V operating — a 4.2 V cell at full charge (≈4.35–4.4 V worst case incl. charger tolerance) fits, with little margin: do not feed VDD from VSYS-with-USB (4.4 V regulated + tolerance is too close to the 4.5 V ceiling is *not* the issue — VBAT is the correct, datasheet-specified source) |
| 3 | VDD | **C201 = 0.1 µF** VDD→GND at the pin | The **only** external component the datasheet requires (ADI DS pin description; Fig. 14) |
| 4 | GND | GND (battery − side) | |
| 1 | CTG | → GND | "Connect to ground" (ADI DS pin 1). Note: there is **no CTL pin** on this part — CTG is it |
| 2 | CELL | **No connect** | On the MAX17048 (1-cell version) CELL is not internally connected — sensing is via VDD. (CELL is live only on the MAX17049.) No series R, no filter C |
| 6 | QSTRT | → GND | Quick-start unused → GND (ADI DS pin description, Fig. 14, Table 3) |
| 5 | ALRT | → Pi header pin 7 (GPIO4) **and** red LED network (§2.1) | Open-drain, active-low |
| 7 | SCL | Pi I²C1 SCL (header pin 5) + expansion header pin 6 | Pull-up R203 (§2.2) |
| 8 | SDA | Pi I²C1 SDA (header pin 3) + expansion header pin 5 | Pull-up R202 (§2.2) |
| EP | — | GND | |

**Placement:** bottom side (per DESIGN.md §2.11 low-profile plan). Keep C201 tight to pin 3. VDD trace comes straight from the battery side of the board — the gauge must see the cell even when everything else is off (its draw is ~25 µA active / 4 µA hibernate, DESIGN.md §5.2).

### 2.1 Red "low battery" LED (D3)

VSYS → **R201 = 1.0 kΩ** → D3 anode; D3 cathode → U2 pin 5 (ALRT). D3 = 0805 red, LCSC C84256 ✅.

**(CALC + DS check)** ALRT is characterised at V_OL ≤ 0.4 V with I_OL = 4 mA, abs-max sink 20 mA (ADI DS Electrical Characteristics / Abs-Max). Budget: LED current + any pull-up current on the ALRT net must stay ≤ 4 mA for the guaranteed logic-low. Worst case VSYS = 4.4 V (USB present), red Vf ≈ 2.0 V: I_LED ≈ (4.4 − 2.0 − 0.2) / 1000 ≈ **2.2 mA**. Battery-only at the low-battery threshold (≈3.4 V): I ≈ (3.4 − 1.9 − 0.2) / 1000 ≈ 1.3 mA — visible on a high-efficiency 0805. The Pi-side GPIO4 input is high-impedance; **firmware must not enable a strong pull-up on GPIO4** (the Pi's internal ~50 kΩ pull-up, if enabled, adds only ~70 µA — acceptable; note it in the software handoff). The LED lights with the device off — per spec.

### 2.2 I²C1 pull-ups

**R202 = 4.7 kΩ** (SDA→3V3), **R203 = 4.7 kΩ** (SCL→3V3), on the HAT (DESIGN.md §3.1). The MAX17048 datasheet requires system-provided pull-ups on SDA/SCL/ALRT but specifies **no value** (ADI DS Application Examples) — 4.7 kΩ is the standard I²C value for a short, low-capacitance bus (bus is specified to 400 kHz / 400 pF max). These pull-ups go to board `3V3`, so the bus is only pulled up when the device is on; the gauge itself stays alive on VBAT regardless. (The Pi also has its own 1.8 kΩ pull-ups on GPIO2/3 — the parallel combination is fine for this bus length.)

---

## 3. 5 V boost — TI TPS61088 (U3) + power switch (SW1)

Sources: TI **SLVSCM8D** (TPS61088 datasheet; note — the correct document number is SLVSCM8**D**, there is no SLVSF01 for this part) and the open-source **Boosty** design (Absurd Industries, GitHub `absurd-industries/boosty`, CERN-OHL-S), whose component values are a proven 5 V/5 A-from-1S instantiation of the datasheet topology.
U3 = TPS61088RHLT, VQFN-20 + thermal pad. Target: **5.1 V out, 4 A continuous / 5 A peak** from 1S.

| Pin | Name | Connection | Notes / source |
|---|---|---|---|
| 9 | VIN | Net `VSYS`; **C301/C302/C303 = 3 × 22 µF** X5R (≥10 V) VSYS→GND + **C304 = 0.1 µF** closest to the pin | Boosty BOM (input bulk) + DS §8.2.2.6 (0.1 µF bypass closest to VIN; ≥10 µF effective input capacitance, §6.3) |
| 4–7 | SW | Switch node → **L1** → VIN node | L1 = **2.2 µH**, Isat ≥ 12 A (Cyntec PIMB065T-2R2M class, per Boosty BOM / DS Table 8-2). Keep this loop physically tiny — see placement rules |
| 8 | BOOT | **C305 = 0.1 µF** BOOT→SW node | DS Fig. 8-1 |
| 14–16 | VOUT | Net `5V_SYS`; **C306/C307/C308 = 3 × 22 µF** X5R (≥10 V) → GND | DS §8.2.2.7 ("typically three 22 µF") + Boosty BOM |
| 1 | VCC | **C309 = 2.2 µF** VCC→AGND | VCC is the internal bias LDO **output** — decouple only, never feed it (DS Fig. 8-1) |
| 17 | FB | Divider: **R301 = 182 kΩ** (5V_SYS→FB), **R302 = 56 kΩ** (FB→AGND) | **(CALC)** V_REF = 1.204 V typ (DS §6.5). R_top = 56 kΩ × (5.1/1.204 − 1) = 181.2 kΩ → E96 **182 kΩ** → V_OUT = 1.204 × (1 + 182/56) = **5.117 V**. Divider current = 5.117 V / 238 kΩ ≈ 21.5 µA, meeting the DS ≥ 20 µA guidance (§8.2.2.4). 56 kΩ bottom is also the DS/Boosty standard value |
| 19 | ILIM | **R303 = 100 kΩ** → AGND | **(CALC)** PFM mode: I_LIM = 1,190,000 / R_ILIM = **11.9 A typ** (DS §8.2.2.3). Matches DESIGN.md's ≈11 A cycle-by-cycle target. Worst-case minimum can sit ~1.3 A below the calculated value — still ≥ the 10 A switch class |
| 13 | MODE | **No connect** (floating = PFM) | DS §8.4: floating → PFM (best light-load efficiency); grounded → forced PWM. Boosty also floats it. Note: in PFM the output regulates ~0.7 % high at very light load — harmless here. Do not tie MODE high (no such mode; internal ~800 kΩ pull-up exists) |
| 3 | FSW | **R304 = 270 kΩ** FSW→**SW node** (not to GND!) | **(CALC)** R_FREQ = 4 × (1/f_SW − t_DELAY × V_OUT/V_IN) / C_FREQ, C_FREQ = 23 pF, t_DELAY = 89 ns (DS §8.2.2.2). At V_IN = 3.6 V, V_OUT = 5.1 V, f = 600 kHz → 268 kΩ → **270 kΩ** (Boosty's value, ≈595–600 kHz at this operating point). Frequency shifts somewhat with V_IN — expected and harmless |
| 10 | SS | **C310 = 47 nF** → AGND | **(CALC)** t_SS = V_REF × C_SS / I_SS, I_SS = 5 µA → 1.204 × 47 nF / 5 µA ≈ **11.3 ms** soft-start (DS §7.3.1: "47 nF is usually sufficient"; Boosty uses 47 nF) |
| 18 | COMP | **R305 = 10 kΩ** in series with **C311 = 4.7 nF** (C0G) → AGND | ⚠️ These are **Boosty's values**, not datasheet-printed ones: the DS gives only the sizing equations (Eqs. 18–20, §8.2.2.8; crossover ≤ min(f_SW/10, f_RHPZ/5)). Proven in the Boosty design at this exact operating point; validate loop stability on proto #1 (load-step test) |
| 2 | EN | Net `PWR_EN` from SW1 | High = on (V_ENH 1.2 V), low = off; internal ~800 kΩ pull-down defaults the boost OFF (DS §6.5) — so the switch genuinely gates it |
| 11, 12 | NC | → GND plane | DS/Boosty: tie to ground for thermal performance |
| 20 | AGND | GND | Join to the main plane at the pad |
| EP (21) | PGND / pad | GND, thermal vias under the pad | DS §10.1 layout |

**SW1 — power switch:** slide switch, common → `PWR_EN`, ON throw → `VSYS`, OFF throw → open (U3's internal pull-down holds EN low). SW1 carries only EN-pin current (µA) — any small SMD slide switch works; it never carries load current (DESIGN.md §5.2 "off" semantics). Rate it ≥ 100 mA for mechanical margin anyway.

**Placement (this is the layout-critical IC — DS §10.1: "Minimize the length and area of all traces connected to the SW pin"):** L1 and C301–C304 within 5 mm of the VIN/SW pins (DESIGN.md §6.3); SW-node copper as small as connectivity allows, over the solid L2 ground; thermal vias under the EP; keep FB/COMP/SS components on the quiet side of the package, away from the SW node; the whole boost cluster sits close to the battery/charger edge so the high-current VSYS path (battery → U1 OUT → U3 VIN) is short and wide.

---

## 4. 3.3 V buck — SY8089AAAC (U4)

Source: Silergy **AN_SY8089/A Rev. 0.9A** (the SY8089/SY8089A datasheet; LCSC lists C78988 as "Output Type: Adjustable").
U4 = SY8089AAAC, SOT-23-5. **Confirmed: this variant is adjustable** (V_REF = 0.6 V typ) with hiccup short-circuit protection — it is not a fixed-output part, and no fixed variant is listed in the datasheet. Input = `5V_SYS` (fed from the boost, **not** from the battery — DESIGN.md §2.6), output 3.3 V / 2 A, f_SW = 1 MHz.

| Pin | Name | Connection | Notes / source |
|---|---|---|---|
| 4 | IN | `5V_SYS`; **C401 = 22 µF** IN→GND at the pin | DS pin description demands ≥ 10 µF ceramic at IN; Fig. 1 uses 22 µF; Applications recommends X5R-or-better, > 6.3 V rating, paralleled parts at 2 A — one 22 µF 10 V X5R 0805/1206 meets this at our operating point (DS p.2, p.7–8) |
| 3 | LX | → **L401 = 2.2 µH** → net `3V3` | DS Fig. 1 value. Check (CALC, DS p.7 formula): L_min ≈ 3.3 × (1 − 3.3/5.1) / (1 MHz × 2 A × 0.4) ≈ 1.46 µH → 2.2 µH is conservative (ripple ≈ 0.53 A). Inductor Isat must exceed ≈ 2.3 A peak; DCR < 50 mΩ desirable (DS p.8) |
| — | OUT | **C402/C403 = 2 × 22 µF** X5R (≥6.3 V; use 10 V) `3V3`→GND at L401's output | DS Fig. 1 (2 × 22 µF) / Applications: output capacitance > 22 µF, X5R or better |
| 5 | FB | Divider: **R401 = 453 kΩ** (3V3→FB), **R402 = 100 kΩ** (FB→GND); **C404 = 22 pF** across R401 | **(CALC)** V_OUT = 0.6 × (1 + R1/R2) (DS p.2). R1 = 100 kΩ × (3.3/0.6 − 1) = 450 kΩ → nearest E96 **453 kΩ** → V_OUT = 0.6 × (1 + 4.53) = **3.318 V** (+0.55 %). Resistor range 10 kΩ–1 MΩ per DS. C404 is the DS Fig. 1 feedforward capacitor (22 pF) for transient response (DS p.8) |
| 1 | EN | → `5V_SYS`; **R403 = 1 MΩ** EN→GND | Sequencing by construction: the buck can only start once the boost has brought 5V_SYS up (DESIGN.md §5.1: "SY8089 EN slaved to 5V_SYS"). EN rising threshold 1.5 V / falling 0.4 V, abs-max V_IN + 0.6 V (DS p.2, p.4) — tying EN to the 5.1 V input rail is within rating (inference from the abs-max table; the DS does not print an explicit "may tie to IN" sentence). EN must not float (DS p.2); R403 is the DS p.8-recommended pull-down against false turn-on |
| 2 | GND | GND | |

**Placement:** C401 tight to pin 4; L401 and C402/C403 tight to pin 3 (LX loop small); FB divider + C404 close to pin 5, away from the LX node. Fed from 5V_SYS means the whole 3V3 domain (ESP32, radios, PN532, SD, button pull-ups) dies cleanly with the power switch — "device off = ESP32 off" (DESIGN.md §2.6).

---

## 5. ESP32-S3 coprocessor — ESP32-S3-WROOM-1-N16R8 (U5) + USB-C #2

Sources: Espressif **ESP32-S3-WROOM-1 Datasheet v1.2** §3.2/§6 (cited "Module DS") and **ESP32-S3 Hardware Design Guidelines** (cited "HDG"). Module LCSC C2913202 ✅. Connections are named by GPIO (module pads are labelled by GPIO); module pin numbers are given where verified.

| Module pad | Connection | Notes / source |
|---|---|---|
| 3V3 (pin 2 — the module's only power pin) | Net `3V3`; **C501 = 22 µF** + **C502 = 0.1 µF** at the pin | Module DS §6 Fig. 7 typical circuit: 22 µF + 0.1 µF per module. (The often-quoted 10 µF figure is the *bare-chip* rule — the WROOM-1 takes 22 µF.) Supply must deliver ≥ 500 mA (HDG); our 2 A buck has > 2× headroom over the module's ~0.35 A TX peaks (DESIGN.md §4.1) |
| GND (pins 1, 40, EPAD 41) | GND | |
| EN (pin 3) | **R501 = 10 kΩ** pull-up → 3V3; **C503 = 1 µF** EN→GND; net `ESP_EN` ← Pi header pin 11 (GPIO17) via **R502 = 1 kΩ** series | RC per Module DS §6 note + HDG (R = 10 kΩ, C = 1 µF typical; rails must be stable ≥ 50 µs before EN rises). The 1 kΩ series is DESIGN.md §3.1 (limits clamp backfeed; the Pi can reset/reflash the ESP32) |
| IO0 (pin 27) | **R503 = 10 kΩ** pull-up → 3V3; ← Pi header pin 13 (GPIO27) via **R504 = 1 kΩ** series | Boot strap. HDG says "fit a pull-up" without a value and warns against large capacitors on IO0 — 10 kΩ is the value in DESIGN.md §3.2 and Espressif's reference designs (⚠️ the guidelines text itself states no number). No capacitor on this net |
| IO43 / U0TXD (pin 37) | → Pi header pin 10 (GPIO15), via **R505 = 499 Ω** series at the module | HDG recommends a 499 Ω series resistor on U0TXD (harmonic suppression). Protocol UART, 115200 8N1 (DESIGN.md §3.1) |
| IO44 / U0RXD (pin 36) | ← Pi header pin 8 (GPIO14) | Direct |
| IO42 | → Pi header pin 15 (GPIO22), net `ESP_IRQ`; **R506 = 10 kΩ** pull-up → 3V3 on the HAT | Attention line, open-drain style (ESP32 drives low / releases) per DESIGN.md §3.2. The HAT-side pull-up (EC) keeps the net defined before Pi firmware configures GPIO22 |
| IO19 / USB_D− (pin 13) | → **R507 = 0 Ω** → U10 (§5.1) → J3 D− | Native USB. HDG reserves 22 Ω/33 Ω series + DNP shunt caps near the chip; the module's own typical circuit uses 0 Ω (Module DS §6 Fig. 7). Fit 0 Ω footprints; swap to 22 Ω only if signal integrity demands. 90 Ω ±10 % differential pair, length-matched, unbroken ground beneath (HDG) |
| IO20 / USB_D+ (pin 14) | → **R508 = 0 Ω** → U10 → J3 D+ | As above |
| IO21 | VBUS detect ← divider **R509 = 100 kΩ / R510 = 100 kΩ** from J3 VBUS; **C504 = 0.1 µF** at IO21 | Divider per DESIGN.md §3.2 (USB present → ≈2.5 V at IO21). C504 is an (EC) noise/debounce addition |
| IO11 (MOSI), IO12 (SCK), IO13 (MISO) | Shared SPI2 bus → U6, U7, SD1 (§6, §7, §9) | Per-device CS and SPI settings; see DESIGN.md §3.2 bus-sharing note |
| IO8 (SDA), IO18 (SCL) | ESP32 I²C bus → U8 PN532 (§8); pull-ups **R513/R514 = 4.7 kΩ** → 3V3 | Separate bus from the Pi's I²C1 (§2.2). 4.7 kΩ (EC, standard I²C value for a short bus) |
| IO15, IO16, IO38, IO39 | Button nets UP/DOWN/LEFT/RIGHT (§11.4) | Direct — no series resistor on the ESP32 side (§3.3) |
| IO4, IO5, IO6 | U7 nRF24 CE / CSN / IRQ (§7) | |
| IO10, IO9, IO17 | U6 CC1101 CS / GDO0 / GDO2 (§6) | |
| IO14, IO7 | SD1 CS / card-detect (§9) | |
| IO40, IO41 | U8 PN532 IRQ / RSTPDN (§8) | |
| IO1, IO2 | IR RX in / IR TX out (§10) | |
| IO3, IO47, IO48 | Test pads only | IO3 is a strapping pin (JTAG source) — do not load it (DESIGN.md §3.2). IO45/IO46 stay unconnected (strapping); IO26–32 and IO33–37 do not exist as usable pads (flash/PSRAM) |

**Antenna placement (Module DS §3.1 keep-out zone; HDG module layout rules):** module antenna end overhangs the board edge or sits at the edge with the base board cut away beside/below it; **no copper on any layer** under the antenna zone; dense ground vias *near* (not under) the antenna; ≥ 15 mm clearance to housing walls in the end product. Also keep the whole module away from the Pi's own WiFi antenna corner on the board below (DESIGN.md §6.2).

### 5.1 USB-C #2 — ESP32 data port (J3) + ESD (U10)

J3 = HRO TYPE-C-31-M-12, LCSC C165948 ✅ (same part as J2).

| J3 terminal | Connection |
|---|---|
| D− / D+ | → U10 I/O pins → R507/R508 → U5 IO19/IO20 (§5). BadUSB HID + flashing only (decision D10) |
| VBUS | → R509/R510 divider only. **VBUS on this port powers nothing** — it is a host-presence sense. (The board is powered from its battery/boost domain; do not back-feed 5V_SYS from a PC) |
| CC1 / CC2 | **R511/R512 = 5.1 kΩ** → GND each (Rd — the ESP32 is the device/sink side) |
| Shield | GND |

U10 = USBLC6-2SC6 (SOT-23-6): flow-through routing — connector-side I/O pins face J3, protected-side pins face U5, pin 5 (VBUS) → J3 VBUS, pin 2 → GND. ⚠️ VERIFY: pin numbering per ST's datasheet for the exact ordering code at BOM freeze (the flow-through arrangement above is the part's standard configuration). Place U10 immediately behind J3, before any stub or via on the D+/D− pair.

---

## 6. Sub-GHz radio — EBYTE E07-900M10S CC1101 module (U6)

Source: EBYTE **E07-900M10S User Manual v1.0** (cited "E07 manual"). Module = TI CC1101 + integrated crystal/matching, 14 × 20 mm stamp-hole SMD, 22 pads. (433 MHz builds fit the pin-compatible E07-400M10S instead — decision D2.)

| Pad | Name | Connection |
|---|---|---|
| 9 | VCC | Net `3V3`; **C601 = 0.1 µF** + **C602 = 10 µF** at the pad (EC — the E07 manual §3 requires "an external ceramic filter capacitor" at VCC but **specifies no value**; 0.1 µF + 10 µF is standard module practice. TX draw is only ~36 mA typ, E07 manual §2.2) |
| 1–5, 11, 12, 20, 22 | GND | GND (all of them — they are the module's RF ground) |
| 6, 7, 8, 10, 13 | NC | No connect |
| 19 | CSN | ← ESP32 IO10 |
| 18 | SCK | ← ESP32 IO12 |
| 17 | MOSI | ← ESP32 IO11 |
| 16 | MISO/GDO1 | → ESP32 IO13 |
| 15 | GDO0 | → ESP32 IO9 (packet interrupt) |
| 14 | GDO2 | → ESP32 IO17 (carrier-sense / async serial) |
| 21 | ANT | → **R601 = 0 Ω** selector → **J7** (U.FL) → pigtail → case SMA whip. Alternate footprint from the post-R601 node: soldered spring antenna, **DNP** in the standard build (decision D6 — footprint keeps both options; fit exactly one path) |

Supply range note: the E07 manual contradicts itself (1.8–3.6 V in §2.2 vs 3.0–3.6 V at the pin-9 definition). Design target is our regulated 3.3 V, which satisfies every stated range (⚠️ flagged in sources). 

**Placement:** opposite board corner from the ESP32 antenna (DESIGN.md §6.4); J7 at the case edge; keep the ANT pad and the trace to J7 clear of the display header's ground pins and any digital copper — 50 Ω controlled run, as short as possible.

---

## 7. 2.4 GHz radio — EBYTE E01-ML01SP4 nRF24L01+ PA/LNA module (U7)

Sources: EBYTE **E01-ML01SP4 Datasheet V1.0** + **E01 User Manual** (cited "E01 manual"). ⚠️ **This SMD module's pin order is NOT the common 8-pin DIP nRF24 order** — it is a 10-pad SMD part; wire it exactly as below. Antenna = onboard IPEX, 50 Ω (§8 of the E01 manual; generation — MHF1/U.FL class — not specified by EBYTE ⚠️).

| Pad | Name | Connection |
|---|---|---|
| 1 | VCC | Net `3V3`; **C701 = 10 µF** + **C702 = 0.1 µF** reservoir at the pad — required by DESIGN.md §2.3 for PA TX bursts (**120 mA typ** at +20 dBm per E01 manual §2.2 / product page 110/120/130 mA min/typ/max — the "~115 mA" figure in some listings is not an EBYTE number). EBYTE itself specifies no capacitor value (⚠️); its FCC-filed datasheet instead recommends a π-filter for supply quality and the user manual demands a stabilised supply with > 30 % current margin — the 10 µF + 0.1 µF pair plus our 2 A rail satisfies both in spirit |
| 2 | CE | ← ESP32 IO4 (CE high also enables the module's LNA) |
| 3 | CSN | ← ESP32 IO5 |
| 4 | SCK | ← ESP32 IO12 |
| 5 | MOSI | ← ESP32 IO11 |
| 6 | MISO | → ESP32 IO13 |
| 7 | IRQ | → ESP32 IO6 |
| 8, 9, 10 | GND | GND |

**Placement:** away from the ESP32 antenna (both live at 2.4 GHz — DESIGN.md §2.10); IPEX whip dressed inside the case; keep the module's ground pads stitched to the plane (PA return current is the pulsed 120 mA).

---

## 8. NFC / RFID — NXP PN532 (U8, bare chip, I²C)

Sources: NXP **AN1445 Rev. 1.2** (antenna design guide — see erratum 2 about "AN10688"), **PN532/C1 Data Sheet Rev. 3.6** §7.2/§8.4/§13 (cited "PN532 DS"), **UM0701-02** (user manual). U8 = PN532/C1, HVQFN-40. Pin numbers below are the HVQFN-40 numbers verified from the data sheet; TX1/TX2/RX are named (their pad numbers ride on the KiCad symbol — confirm against PN532 DS Table 3 when the symbol is placed ⚠️).

### 8.1 Power — read carefully, PN532 generates its own rails

| Pin | Name | Connection |
|---|---|---|
| 40 | VBAT | Net `3V3`; **C801 = 0.1 µF** → GND at the pin. VBAT (2.7–5.5 V) is the **only** supply input; an internal LDO makes DVDD (PN532 DS §8.4, §10) |
| 39 | DVDD | **OUTPUT of the internal LDO (≈3.0 V) — do not feed it.** Route DVDD → AVDD and TVDD. Decouple: **C802 = 4.7 µF** + **C803 = 0.1 µF** → GND (PN532 DS §8.4 Fig. 19, §13 Fig. 51: DVDD/AVDD/TVDD each separately decoupled, X7R/X5R low-ESR) |
| 5 | TVDD | ← DVDD net; **C804 = 4.7 µF** + **C805 = 0.1 µF** → GND at the pin |
| 8 | AVDD | ← DVDD net; **C806 = 0.1 µF** → GND at the pin |
| 3, 7 | TVSS1, TVSS2 | GND |
| 11 | AVSS | GND |
| 23 | PVDD | Net `3V3`; **C807 = 0.1 µF** → GND. PVDD is the host-interface pad supply (1.6–3.6 V) — this is what makes the I²C/IRQ/RST levels 3.3 V |
| 37 | SVDD | **No connect** (switchable supply *output* for an NFC-WI secure element we don't fit; leave unloaded, PN532 DS §8.4.2) |
| 9 | VMID | **C808 = 0.1 µF** → GND (internal RX reference, decoupled per AN1445 §4.6.1 / Fig. 51) |

⚠️ Cap-assignment note: Fig. 51's exact per-pin capacitor placement is partially illegible in the PDF; the set above follows the DS §8.4 requirement (separate decoupling on DVDD, AVDD, TVDD; 4.7 µF + 100 nF pairs on DVDD and TVDD; 100 nF on AVDD/PVDD/VMID). This matches the reference circuit's component inventory.

### 8.2 Crystal

**Y1 = 27.12 MHz** between OSCIN (pin 14) and OSCOUT (pin 15); **C815 = 22 pF** (OSCIN→GND), **C816 = 22 pF** (OSCOUT→GND) (PN532 DS §13 Fig. 51). Crystal spec per DS §12.5: 27.12 MHz ± ~480 ppm, ESR ≤ 50 Ω, load capacitance 10 pF, drive 100 µW (e.g. TAS-3225A class). Keep Y1 and its caps within a few mm of pins 14/15, ground-guarded, away from the antenna network.

### 8.3 Host interface (I²C)

| Pin | Name | Connection |
|---|---|---|
| 16 | I0 | → **DVDD net** (interface select: I0=1, I1=0 = I²C — UM0701-02 Table 7) |
| 17 | I1 | → GND |
| 27 | SCL | ← ESP32 IO18 (pull-up R514, §5) |
| 28 | SDA | ↔ ESP32 IO8 (pull-up R513, §5) |
| 38 | RSTPD_N | ← ESP32 IO41. Active-low reset / hard power-down; the DS states no pull requirement — the ESP32 must drive it high for operation (PN532 DS §7.2) |
| 25 | P70_IRQ | → ESP32 IO40. Driven GPIO-style interrupt; no external resistors required (AN10609) |

I²C address is fixed at **0x24** (7-bit; UM0701-02 §6.2.4 gives the 8-bit form 0x48). There are no address-select pins.

### 8.4 Antenna network — EMC filter + matching (AN1445 §4, Fig. 1; §4.7 worked example)

Symmetrical: build the TX1 half and the TX2 half identically. Per side:

TX pin → **L801/L802 = 560 nH** (EMC inductor) → node `EMC_A` / `EMC_B`; **C809/C810 = 220 pF** from each EMC node → TVSS (GND); EMC node → **C811/C812 = 18 pF** (series matching cap C1) → **R801/R802 = 3.3 Ω** (damping Rq) → loop terminal `ANT_A` / `ANT_B`; **C813/C814 = 56 pF** from each loop terminal → TVSS (GND) (shunt matching cap C2).

- EMC filter: L0 = 560 nH with C0 = 220 pF sets fr0 ≈ 14.3 MHz — AN1445 §4.2 worked example (allowed L0 range 390 nH–1 µH, fr0 target 14.1–14.5 MHz).
- C1/C2/Rq values are the AN1445 §4.7 evaluation-board results for a loop of La ≈ 2.9 µH, Ra ≈ 1.9 Ω, Ca ≈ 11 pF, tuned to Rmatch ≈ 50 Ω at Q ≈ 35. **They are starting values, not final values** — C1, C2 and Rq are antenna-dependent by construction (AN1445 Eqs. 7–10) and **must be bench-tuned with the actual adhesive loop and its cable fitted** (DESIGN.md §6.5 already calls for this). The note's design envelope: La 0.3–3 µH, Ra 0.3–8 Ω, Q target 35 ± 10 %.
- **ANT_A → J8** (U.FL) centre; **ANT_B → J8** shell/GND. J8 → coax pigtail → adhesive 13.56 MHz loop in the case back (decision D1). The cable is part of the antenna — tune with the final cable length.
- RX path (from the TX1-side EMC node `EMC_A`): **R803 = 1 kΩ** (R1, predefined) → node `RXD`; **R804 = 2.7 kΩ** (R2) from `RXD` → GND; **C817 = 1 nF** (CRX) from `RXD` → RX pin. R1 and CRX/Cvmid are fixed by AN1445 §4.6.1; R2 = 2.7 kΩ is the PN532 DS Fig. 51 instance value — it is calculated per-loop (AN1445 Eq. 11, target U_RX ≈ 1 Vpp), so treat 2.7 kΩ as the starting value alongside C1/C2/Rq tuning.

**Placement:** the entire network (L801/L802 → J8) is one compact cluster: EMC parts adjacent to the TX pins, matching caps adjacent to J8, **whole network within 10 mm of the U.FL** (DESIGN.md §6.5), no ground-pour tricks under the network, no digital traces crossing it. PN532 sits on the case-back side of the board so the J8 run is short.

---

## 9. microSD slot (SD1)

SD1 = push-push TF slot, LCSC C91145 ✅ / C112217 ✅. SPI mode on the ESP32's shared SPI2 bus (DESIGN.md §2.8, decision D5).

| Slot contact | Connection |
|---|---|
| VDD | Net `3V3`; **C901 = 0.1 µF** + **C902 = 10 µF** at the slot (EC — standard card-edge practice) |
| VSS | GND |
| CLK | ← ESP32 IO12 |
| CMD (MOSI) | ← ESP32 IO11; **R901 = 10 kΩ** pull-up → 3V3 (the SD specification requires pull-ups on CMD and DAT lines in SPI mode) |
| DAT0 (MISO) | → ESP32 IO13; **R902 = 10 kΩ** pull-up → 3V3 |
| DAT3 (CS) | ← ESP32 IO14 |
| DAT1, DAT2 | No connect (unused in SPI mode) |
| CD (card-detect contact) | → ESP32 IO7; **R903 = 10 kΩ** pull-up → 3V3. ⚠️ VERIFY: assumes the slot's CD contact closes to GND with a card inserted (the common arrangement for this slot class) — confirm against the chosen slot's datasheet at BOM freeze |

No series damping resistors are fitted on the SD lines: Espressif's reference designs wire SD slots directly, and our runs are short. If proto testing shows ringing-related card errors, 33 Ω series pads near the slot are the rev-2 fix (note, not fitted).

**Placement:** on the case edge — the card must be insertable without opening the enclosure (DESIGN.md §6.8).

---

## 10. Infrared — TSOP38438 RX (U11) + 940 nm TX (D1/Q1)

Sources: Vishay **TSOP382../TSOP384.. datasheet, Doc. 82491** (Rev. 2.1 current; Rev. 1.0 for the filter-component range).

### 10.1 Receiver — ⚠️ through-hole part (see erratum 3)

U11 = TSOP38438, Minicast **leaded** package. Pin order for THIS series: **1 = OUT, 2 = GND, 3 = VS** (sibling series swap VS/GND — do not cross-wire).

| Pin | Connection |
|---|---|
| 3 (VS) | ← **R1001 = 100 Ω** ← net `3V3`; **C1001 = 1 µF** VS→GND at the device. The series-R + shunt-C supply filter is Vishay's application circuit (diagram 17170): Rev. 1.0 gives the ranges **33 Ω < R1 < 1 kΩ** and **C1 > 0.1 µF** — 100 Ω and 1 µF sit inside both. (The often-quoted "100 Ω + 0.1 µF" pair comes from *other* Vishay families' datasheets; 0.1 µF does not satisfy this family's "> 0.1 µF") |
| 2 (GND) | GND |
| 1 (OUT) | → ESP32 IO1, direct. OUT has an **internal 30 kΩ pull-up** and is specified to connect straight to a microprocessor — no external pull-up (Vishay DS block diagram). Active-low: high = no carrier, low during a received 38 kHz burst |

Supply: 2.0–5.5 V (Rev. 2.1) — our 3.3 V is mid-range; draw ≈ 0.35 mA.

**Placement:** at the case edge with an unobstructed view out (IR window in the enclosure); keep it away from D1's direct blast (a few mm of separation and the case's internal wall do the job) and away from the boost's SW node noise.

### 10.2 Transmitter

ESP32 IO2 → **R1003 = 1 kΩ** → Q1 base. Q1 = MMBT2222A (SOT-23: pin 1 = B, 2 = E, 3 = C); emitter → GND; collector → D1 cathode. D1 anode → **R1002 = 18 Ω** → net `3V3`. D1 = 940 nm SMD IR LED, 1206 (VSMB10940 class; LCSC ⚠️ confirm at BOM freeze).

**(CALC)** Target I_F ≈ 100 mA pulsed (DESIGN.md §2.5; the LED is driven from the transistor, never from the GPIO):
- Base current: (3.3 − 0.7) / 1000 = **2.6 mA** from IO2 — comfortable for the GPIO; forced β at the collector ≈ 100/2.6 ≈ 38, so allow V_CE(sat) ≈ 0.2 V.
- LED resistor: R = (3.3 − V_f − V_CE(sat)) / I_F = (3.3 − 1.35 − 0.2) / 0.100 = 17.5 Ω → **18 Ω** (E24). Assumes V_f ≈ 1.35 V at 100 mA for the 940 nm class — re-check against the finally-chosen LED's datasheet at BOM freeze and re-trim if its V_f differs materially.
- R1002 dissipation at 100 mA: I²R ≈ 0.18 W during bursts — fit a **1206** (or pulse-rated 0805); IR duty cycle is low, but don't fit a plain 0603 here.
- Bruce's DIY builds use exactly this topology (GPIO → 1 kΩ → 2N2222 → LED), per DESIGN.md §2.5.

---

## 11. Pi interface

### 11.1 40-pin header (J1)

The full pin-by-pin net list **is** Part B, §3.1 below — every header pin's HAT-side connection is named there, and each subsystem section above names the component at the other end of the net (e.g. header pin 11 → R502 → U5 EN). Two routing notes from DESIGN.md §3.1 worth repeating at the schematic stage: both 5 V pins (2 + 4) are fed from `5V_SYS` with a wide, via-stitched pour (a single pin is not a 4 A path), and header pin 17 (Pi 3V3) is **not connected** — the board never back-powers the Pi's 3V3 rail. Pin 1 feeds only the EEPROM (§11.3).

### 11.2 Display header (J5) + backlight FET (Q2)

J5 = 2 × 7 (14-pin) 2.54 mm female header, top side, matching the ubiquitous ILI9341 SPI module. Standard module pin order (⚠️ VERIFY against the specific sourced module at build time — the order below is the near-universal one for this module class, but the module is a builder-sourced part):

| J5 pin | Module signal | HAT connection |
|---|---|---|
| 1 | VCC | `5V_SYS` (the module's own regulator makes its 3.3 V — DESIGN.md §2.7) |
| 2 | GND | GND |
| 3 | CS | ← Pi GPIO8 (header pin 24) |
| 4 | RESET | ← Pi GPIO24 (header pin 18) |
| 5 | DC/RS | ← Pi GPIO25 (header pin 22) |
| 6 | SDI (MOSI) | ← Pi GPIO10 (header pin 19) |
| 7 | SCK | ← Pi GPIO11 (header pin 23) |
| 8 | LED (backlight) | → Q2 drain (see below) |
| 9 | SDO (MISO) | → Pi GPIO9 (header pin 21) — serves the module's SD socket; the LCD itself is write-only |
| 10–14 | T_CLK, T_CS, T_DIN, T_DO, T_IRQ | **No connect** (non-touch build per spec) |
| (module SD_CS pad, where the module provides it separately) | SD chip-select | ← Pi GPIO7 (header pin 26) — DESIGN.md §2.7's "bonus socket"; module-variant-dependent ⚠️ |

**Backlight switch:** Q2 = AO3400A N-FET (SOT-23: pin 1 = G, 2 = S, 3 = D; LCSC ⚠️ confirm). Gate ← Pi GPIO18 (header pin 12, hardware PWM) via **R1101 = 100 Ω** series (EC — limits gate-edge current/ringing); **R1102 = 100 kΩ** gate→GND pull-down (backlight deterministically OFF until the Pi drives it — including while the Pi is absent or booting); source → GND; drain → J5 pin 8. Backlight draw is 50–90 mA (DESIGN.md §2.7) — trivial for the AO3400A, far beyond a bare GPIO, which is the point of the FET.

### 11.3 HAT ID EEPROM — 24C32 (U9)

U9 = 24C32, SOIC-8 (LCSC ⚠️ generic, confirm at BOM freeze). Per the official HAT specification.

| Pin | Name | Connection |
|---|---|---|
| 8 | VCC | Net `3V3_ID` = Pi header pin 1 **only**; **C1101 = 0.1 µF** VCC→GND (EC, standard practice) |
| 4 | VSS | GND |
| 5 | SDA | Pi header pin 27 (ID_SD) |
| 6 | SCL | Pi header pin 28 (ID_SC) |
| 1, 2, 3 | A0, A1, A2 | All → GND → I²C address **0x50** |
| 7 | WP | → **SJ1 solder jumper**: default position WP→GND (writable — factory flashes the ID blob, incl. the Pi 5 PSU-capability declaration, DESIGN.md §2.7/§5.3); alternate position WP→VCC (write-protected/locked after flashing) |

**No pull-ups on the ID bus on the HAT** — the HAT specification puts the ID_SD/ID_SC pull-ups on the Pi side; adding our own would violate the spec's bus model. Nothing else may ever connect to ID_SD/ID_SC. **Placement:** bottom side (low profile, §2.11 plan).

### 11.4 Buttons ×4 (SW2–SW5) — shared nets

One circuit ×4 (DESIGN.md §3.3). Nets: `BTN_UP` (SW2), `BTN_DOWN` (SW3), `BTN_LEFT` (SW4), `BTN_RIGHT` (SW5). Buttons = 6 × 6 mm SMD tact, LCSC C11135 ✅.

Per net:
- Switch: one terminal → the button net, other → GND.
- **R1110–R1113 = 10 kΩ** pull-up, button net → `3V3` (one per net, on the board — neither MCU's internal pull-up is relied on, since both chips read the same net).
- Button net → ESP32 GPIO **direct** (UP→IO15, DOWN→IO16, LEFT→IO38, RIGHT→IO39).
- Button net → **R1114–R1117 = 1 kΩ** series → Pi header pin (UP→pin 29/GPIO5, DOWN→pin 31/GPIO6, LEFT→pin 33/GPIO13, RIGHT→pin 37/GPIO26). The 1 kΩ limits ESD-clamp backfeed into an unpowered Pi to < 3.3 mA (§3.3).
- **C1110–C1113 = 100 nF** button net → GND (hardware debounce; τ ≈ 10 kΩ × 100 nF = 1 ms — (EC); firmware debounce also applies, and the caps may be left DNP if proto testing prefers pure firmware debounce).

Neither chip ever drives these nets. ESD: the buttons sit inside the enclosure under case plungers (not user-exposed ports), and the series resistor + both chips' clamp structures are the accepted protection — no dedicated ESD array is fitted, by design decision, stated here so it's a decision and not an omission.

**Placement:** along the board edge, aligned to the enclosure's button plungers — freeze positions together with the case (DESIGN.md §6.6).

### 11.5 Green "power on" LED (D2)

`5V_SYS` → **R1120 = 1.0 kΩ** → D2 anode; cathode → GND. D2 = 0805 green, LCSC C19171391 ✅.
**(CALC)** (5.1 − 2.1) / 1000 = **3.0 mA** (green Vf ≈ 2.1 V). Lit exactly when 5V_SYS exists = device on. Hardware-driven, per spec.

---

## 12. Expansion header (J6)

J6 = 2 × 8, 2.54 mm, top edge. Full signal table in Part B, §3.4. Components:

- Pin 1 (5V_SYS feed): via **F2 = PPTC, 500 mA hold** (1812) from `5V_SYS` (per §3.4's "fused 500 mA").
- Pin 3 (board 3V3, ≤ 300 mA budget): direct from `3V3` — the budget is a build-guide rule, not a component.
- All signal pins (I²C1, SPI0, GPIOs, ESP_IRQ): **direct, no series resistors, no ESD parts** — these are the Pi's/ESP32's own GPIOs brought out; add-on designers own their side's protection. Stated explicitly so the absence is a decision: the header is a hobby interconnect inside a case slot, not an external port.

---

## 13. Battery connector (J4)

J4 = JST-PH 2-pin SMD (B2B-PH-K-S), LCSC C131337 ✅.

| J4 pin | Connection |
|---|---|
| 1 | Net `VBAT_RAW` (+). **Silk-screen "+" beside the connector** — PH plugs are keyed, but clone harnesses vary; the build guide must tell builders to verify red-wire polarity against the silk before first power |
| 2 | GND (−) |

`VBAT_RAW` → **F1 = PPTC (hold ≈ 3 A / trip ≈ 6 A, 1812)** → net `VBAT` (→ U1 BAT pins, U2 VDD). F1 value per DESIGN.md §2.6. ⚠️ **Design tension to resolve on proto #1:** DESIGN.md §4.3 puts worst-case cell draw at ≈5.2 A (Pi 5 stress, near-empty cell) — above F1's 3 A hold. A PPTC's hold is a no-trip guarantee at 23 °C, not a fuse point, and it derates with temperature; under sustained worst-case load F1 may nuisance-trip. Options: accept (fault protection wins; worst case is a corner), or uprate F1 to a 5 A-hold 1812 part. Flagged for Justin — do not silently change it here. The cell's own PCM remains the last line of defense either way (DESIGN.md §2.6).

---

# Part B — Pin assignment tables (from DESIGN.md §3, verbatim)

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

# Part C — Complete BOM

LCSC numbers marked ✅ are carried over from DESIGN.md §8 (verified there). Everything else is **confirm at BOM freeze**. Resistors/caps are 0603 unless a section says otherwise; all ceramic caps X7R/X5R.

| Refdes | Qty | Value / part | Package | LCSC |
|---|---|---|---|---|
| U1 | 1 | TI bq24074RGTR charger | VQFN-16 | confirm (family C473396 is the bq24078 sibling) |
| U2 | 1 | MAX17048G+T10 fuel gauge | TDFN-8 | confirm |
| U3 | 1 | TI TPS61088RHLT boost | VQFN-20 | confirm |
| U4 | 1 | SY8089AAAC buck | SOT-23-5 | **C78988 ✅** |
| U5 | 1 | ESP32-S3-WROOM-1-N16R8 module | SMD module | **C2913202 ✅** |
| U6 | 1 | EBYTE E07-900M10S CC1101 module (433 build: E07-400M10S) | Stamp-hole SMD | confirm |
| U7 | 1 | EBYTE E01-ML01SP4 nRF24 PA module | Stamp-hole SMD | confirm |
| U8 | 1 | NXP PN532/C1 NFC controller | HVQFN-40 | confirm |
| U9 | 1 | 24C32 EEPROM | SOIC-8 | confirm |
| U10 | 1 | ST USBLC6-2SC6 USB ESD | SOT-23-6 | confirm |
| U11 | 1 | Vishay TSOP38438 IR receiver | Minicast **THT** | confirm |
| Q1 | 1 | MMBT2222A | SOT-23 | confirm (Basic-class) |
| Q2 | 1 | AO3400A N-FET | SOT-23 | confirm (Basic-class) |
| D1 | 1 | 940 nm IR LED (VSMB10940 class) | 1206 | confirm |
| D2 | 1 | LED green 0805 | 0805 | **C19171391 ✅** |
| D3 | 1 | LED red 0805 | 0805 | **C84256 ✅** |
| D4 | 1 | LED blue 0805 | 0805 | confirm |
| L1 | 1 | 2.2 µH power inductor, Isat ≥ 12 A (Cyntec PIMB065T-2R2M class) | ~6.5 × 6.5 mm | confirm |
| L401 | 1 | 2.2 µH, Isat > 2.3 A, DCR < 50 mΩ | 2520/2525 class | confirm |
| L801, L802 | 2 | 560 nH RF inductor (tight tolerance, high Q) | 0603/0805 | confirm |
| Y1 | 1 | 27.12 MHz crystal, CL 10 pF, ESR ≤ 50 Ω | 3225 | confirm |
| J1 | 1 | 2 × 20 2.54 mm stacking header (Pi HAT) | THT | confirm |
| J2, J3 | 2 | HRO TYPE-C-31-M-12 USB-C | SMD mid-mount | **C165948 ✅** |
| J4 | 1 | JST-PH B2B-PH-K-S battery connector | SMD | **C131337 ✅** |
| J5 | 1 | 2 × 7 2.54 mm female header (display) | THT/SMD | confirm |
| J6 | 1 | 2 × 8 2.54 mm header (expansion) | THT/SMD | confirm |
| J7, J8 | 2 | U.FL/IPEX RF connector | SMD | confirm |
| SD1 | 1 | microSD push-push slot | SMD | **C91145 ✅ / C112217 ✅** |
| SW1 | 1 | Slide switch (power, EN-level current) | SMD | confirm |
| SW2–SW5 | 4 | Tact switch 6 × 6 mm | SMD | **C11135 ✅** |
| SJ1 | 1 | Solder jumper (EEPROM WP select) | 0603 pads | — |
| F1 | 1 | PPTC hold ≈3 A / trip ≈6 A (see §13 warning) | 1812 | confirm |
| F2 | 1 | PPTC hold 500 mA | 1812 | confirm |
| R101 | 1 | 890 Ω 1 % (ISET) | 0603 | — |
| R102 | 1 | 1.1 kΩ (ILIM) | 0603 | — |
| R103 | 1 | 10 kΩ (TS defeat) | 0603 | — |
| R104 | 1 | 1.0 kΩ (blue LED) | 0603 | — |
| R105, R106, R511, R512 | 4 | 5.1 kΩ (USB-C Rd ×4) | 0603 | — |
| R201 | 1 | 1.0 kΩ (red LED) | 0603 | — |
| R202, R203, R513, R514 | 4 | 4.7 kΩ (I²C pull-ups) | 0603 | — |
| R301 | 1 | 182 kΩ 1 % (boost FB top) | 0603 | — |
| R302 | 1 | 56 kΩ 1 % (boost FB bottom) | 0603 | — |
| R303 | 1 | 100 kΩ (boost ILIM) | 0603 | — |
| R304 | 1 | 270 kΩ (boost FSW — to SW node!) | 0603 | — |
| R305 | 1 | 10 kΩ (boost COMP, Boosty value) | 0603 | — |
| R401 | 1 | 453 kΩ 1 % (buck FB top) | 0603 | — |
| R402 | 1 | 100 kΩ (buck FB bottom) | 0603 | — |
| R403 | 1 | 1 MΩ (buck EN pull-down) | 0603 | — |
| R501, R503, R506 | 3 | 10 kΩ (EN PU / IO0 PU / ESP_IRQ PU) | 0603 | — |
| R502, R504 | 2 | 1 kΩ (EN / IO0 series from Pi) | 0603 | — |
| R505 | 1 | 499 Ω (U0TXD series) | 0603 | — |
| R507, R508 | 2 | 0 Ω (USB series, 0603; footprint accepts 22 Ω) | 0603 | — |
| R509, R510 | 2 | 100 kΩ (VBUS detect divider) | 0603 | — |
| R601 | 1 | 0 Ω (CC1101 antenna selector) | 0603 | — |
| R801, R802 | 2 | 3.3 Ω (PN532 Rq — tune) | 0603 | — |
| R803 | 1 | 1 kΩ (PN532 RX R1) | 0603 | — |
| R804 | 1 | 2.7 kΩ (PN532 RX R2 — tune) | 0603 | — |
| R901, R902, R903 | 3 | 10 kΩ (SD pull-ups) | 0603 | — |
| R1001 | 1 | 100 Ω (TSOP supply filter) | 0603 | — |
| R1002 | 1 | 18 Ω (IR LED current set) | **1206** | — |
| R1003 | 1 | 1 kΩ (IR TX base) | 0603 | — |
| R1101 | 1 | 100 Ω (backlight FET gate) | 0603 | — |
| R1102 | 1 | 100 kΩ (gate pull-down) | 0603 | — |
| R1110–R1113 | 4 | 10 kΩ (button pull-ups) | 0603 | — |
| R1114–R1117 | 4 | 1 kΩ (button series to Pi) | 0603 | — |
| R1120 | 1 | 1.0 kΩ (green LED) | 0603 | — |
| C101 | 1 | 1 µF (charger IN) | 0603 | — |
| C102, C103 | 2 | 4.7 µF (charger BAT / OUT) | 0805 | — |
| C201 | 1 | 0.1 µF (gauge VDD) | 0603 | — |
| C301–C303, C306–C308 | 6 | 22 µF X5R ≥10 V (boost IN ×3 / OUT ×3) | 0805/1206 | — |
| C304 | 1 | 0.1 µF (boost VIN bypass) | 0603 | — |
| C305 | 1 | 0.1 µF (boost BOOT) | 0603 | — |
| C309 | 1 | 2.2 µF (boost VCC) | 0603 | — |
| C310 | 1 | 47 nF (boost SS) | 0603 | — |
| C311 | 1 | 4.7 nF C0G (boost COMP, Boosty value) | 0603 | — |
| C401 | 1 | 22 µF X5R 10 V (buck IN) | 0805/1206 | — |
| C402, C403 | 2 | 22 µF X5R (buck OUT) | 0805/1206 | — |
| C404 | 1 | 22 pF (buck feedforward) | 0603 | — |
| C501 | 1 | 22 µF (ESP32 supply) | 0805 | — |
| C502 | 1 | 0.1 µF (ESP32 supply) | 0603 | — |
| C503 | 1 | 1 µF (ESP32 EN RC) | 0603 | — |
| C504 | 1 | 0.1 µF (VBUS detect) | 0603 | — |
| C601 | 1 | 0.1 µF (CC1101 supply) | 0603 | — |
| C602 | 1 | 10 µF (CC1101 supply) | 0805 | — |
| C701 | 1 | 10 µF (nRF24 reservoir) | 0805 | — |
| C702 | 1 | 0.1 µF (nRF24 supply) | 0603 | — |
| C801, C803, C805, C806, C807, C808 | 6 | 0.1 µF (PN532 decoupling set) | 0603 | — |
| C802, C804 | 2 | 4.7 µF (PN532 DVDD / TVDD) | 0805 | — |
| C809, C810 | 2 | 220 pF (PN532 EMC C0) | 0603 | — |
| C811, C812 | 2 | 18 pF (PN532 C1 — tune) | 0603 C0G | — |
| C813, C814 | 2 | 56 pF (PN532 C2 — tune) | 0603 C0G | — |
| C815, C816 | 2 | 22 pF (PN532 crystal load) | 0603 C0G | — |
| C817 | 1 | 1 nF (PN532 CRX) | 0603 | — |
| C901 | 1 | 0.1 µF (SD supply) | 0603 | — |
| C902 | 1 | 10 µF (SD supply) | 0805 | — |
| C1001 | 1 | 1 µF (TSOP filter) | 0603 | — |
| C1101 | 1 | 0.1 µF (EEPROM VCC) | 0603 | — |
| C1110–C1113 | 4 | 100 nF (button debounce, may be DNP) | 0603 | — |
| TP | ~6 | Test pads: IO3, IO47, IO48, VSYS, 3V3, PGOOD | — | — |
| Spring antenna | 0/1 | CC1101 spring antenna (DNP unless the SMA-whip path is deleted) | — | builder option |

Builder-sourced (not on the PCB BOM): Raspberry Pi, ILI9341 display module, 5000 mAh 1S high-drain (≥3C) pouch cell with JST-PH lead, adhesive 13.56 MHz loop antenna + U.FL pigtail, SMA whip (868/915), IPEX whip (2.4 GHz), enclosure.

---

# Part D — Placement rules summary

The short list of layout-critical items. (DESIGN.md §6 has the full checklist; this is the distilled version, with the datasheet-derived items added.)

1. **Boost SW loop first.** TPS61088: L1 + C301–C304 within 5 mm of the VIN/SW pins; SW-node copper minimum area; thermal vias under U3's pad; FB/COMP/SS parts on the far side of the package from SW. ("Minimize the length and area of all traces connected to the SW pin" — SLVSCM8D §10.1.)
2. **Decoupling proximity.** Every IC's caps within ~3 mm of their pins, via-free where possible: U1 (C101–C103), U2 (C201), U4 (C401 at IN, C402/403 at LX output), U5 (C501/C502 at pin 2), U6 (C601/C602), U7 (C701/C702), U8 (full §8.1 set), SD1 (C901/C902).
3. **PN532 network is one cluster.** TX pins → EMC (L801/L802, C809/C810) → matching (C811–C814, R801/R802) → J8, all within 10 mm of the U.FL, no digital crossings, no ground-pour games. Y1 crystal tight to pins 14/15.
4. **Antenna keep-outs.** ESP32 module antenna overhangs/edges the board with **zero copper on all layers** beneath it and ≥15 mm housing clearance; CC1101 (U6) and nRF24 (U7) at opposite corners from the ESP32 antenna and from each other where the outline allows (U7 and the ESP32 both live at 2.4 GHz); nothing on this board overhangs the **Pi's** WiFi antenna corner below.
5. **USB pairs.** J3 D+/D−: 90 Ω ±10 % differential, length-matched, solid ground beneath, U10 immediately behind the connector, R507/R508 immediately behind U10. J2 is power-only — keep its VBUS run short and wide to U1 IN.
6. **Ground strategy.** 4-layer stackup, L2 solid GND, no splits under RF or the boost. AGND (U3 pin 20) ties into the plane at the pad; every module's ground pads stitched down (U6 has nine ground pads for a reason — PA/RF return currents).
7. **High-current paths are pours, not traces.** Battery → F1 → VBAT → U1; VSYS → U3 VIN; 5V_SYS → header pins 2+4 (wide, via-stitched). Size for 5 A peaks, not averages.
8. **Bottom-side discipline.** Only low-profile parts (U9, U2, U10, passives, Q2) below, ≤ 1.2 mm within Pi keep-out zones (DESIGN.md §6.7); standoff budget is the enclosure's problem only if this rule holds.
9. **Edges are functional.** SD1 on the case edge (hot-swappable cards); SW2–SW5 and D2–D4 aligned to enclosure plungers/light pipes (freeze with the case, §6.6); U11 at an edge with a clear IR view; J7 pigtail exit at the case edge.

---

# Part E — Sources & verification status

**Primary sources used for Part A values:** TI SLUS810N (bq24074); TI SLVSCM8D (TPS61088) + Absurd Industries "Boosty" repo BOM/design notes; Analog Devices MAX17048/49 datasheet doc. 19-6171 Rev 7; Silergy AN_SY8089/A Rev. 0.9A; Espressif ESP32-S3-WROOM-1 Datasheet v1.2 + ESP32-S3 Hardware Design Guidelines; EBYTE E07-900M10S User Manual v1.0; EBYTE E01-ML01SP4 Datasheet V1.0 + E01 User Manual; NXP AN1445 Rev. 1.2, PN532/C1 Data Sheet Rev. 3.6, UM0701-02, AN10609; Vishay Doc. 82491 (TSOP384xx) Rev. 1.0/1.6/2.1; Raspberry Pi HAT specification (EEPROM/ID bus).

**Values that could NOT be verified from a primary source (double-check list for Justin):**

1. **bq24074 EN1/EN2 abs-max voltage** — the tie of EN2 to the 5 V IN net assumes the family's 7 V logic-pin class (verified for CHG/PGOOD in §8.1, not explicitly extracted for EN1/EN2).
2. **bq24074 K_ILIM** — the datasheet is internally inconsistent: 1550 A·Ω (design example) vs 1610 typ (electrical table). ILIM current therefore carries ±~10 % tolerance; the 1.5 A ceiling conclusion is unaffected.
3. **TPS61088 COMP values (R305/C311)** — Boosty's proven values; the datasheet prints only equations. Validate with a load-step test on proto #1.
4. **TPS61088 R_ILIM allowed range** — no explicit min/max in the datasheet; 100 kΩ is the datasheet's own example value.
5. **PN532 C1/C2/Rq/R2 (R801/R802, C811–C814, R804)** — AN1445 *worked-example* values for a 2.9 µH loop. They are starting points by construction; final values come from bench tuning with the real case-back loop + cable (VNA or at minimum a field-strength/read-range sweep).
6. **PN532 TX1/TX2/RX pad numbers** — connections are specified by pin name; numbers ride on the KiCad symbol (verify against PN532/C1 data sheet Table 3 when placing). Verified numbers used: VBAT 40, DVDD 39, RSTPD_N 38, SVDD 37, SDA 28, SCL 27, P70_IRQ 25, PVDD 23, I1 17, I0 16, OSCOUT 15, OSCIN 14, AVSS 11, VMID 9, AVDD 8, TVSS2 7, TVDD 5, TVSS1 3.
7. **PN532 Fig. 51 per-pin capacitor assignment** — partially illegible in the PDF; §8.1's set satisfies the §8.4 decoupling requirement and matches the figure's component inventory, but the exact 100 nF-to-pin mapping in NXP's drawing could not be read with certainty.
8. **USBLC6-2SC6 pin numbering** — flow-through arrangement as standard for the part; confirm against ST's datasheet for the exact order code.
9. **ESP32 IO0 pull-up value (10 kΩ)** — the Hardware Design Guidelines require a pull-up but state no value; 10 kΩ is from DESIGN.md and Espressif reference designs.
10. **E07-900M10S decoupling values (C601/C602)** — EBYTE requires "an external ceramic filter capacitor" at VCC but gives no value; §5's recommended-circuit diagram values were not legibly extractable.
11. **E07-900M10S supply range** — the manual contradicts itself (1.8–3.6 V vs 3.0–3.6 V at pin 9). Our regulated 3.3 V satisfies all versions.
12. **E01-ML01SP4 reservoir values (C701/C702)** — EBYTE specifies no values (π-filter + margin guidance only). 10 µF + 0.1 µF is DESIGN.md's requirement and standard PA-module practice.
13. **E01-ML01SP4 IPEX generation** (MHF1 vs U.FL compatibility) and the FCC datasheet's conflicting 1.5 dBm/PCB-antenna figures vs the manual's 20 dBm/IPEX — confirm the exact hardware revision when ordering modules.
14. **microSD CD-contact polarity (R903/SD1)** — assumes contact closes to GND on insertion; confirm against the chosen slot's datasheet.
15. **Display module (J5) pin order and SD_CS routing** — the module is builder-sourced; the near-universal ILI9341-module order is tabulated, but verify against the actual module in hand.
16. **IR LED V_f (R1002 = 18 Ω)** — calculated at V_f ≈ 1.35 V @ 100 mA for the 940 nm class; re-trim if the frozen LED part's datasheet says otherwise.
17. **SY8089 EN-to-IN tie** — within the pin's abs-max (V_IN + 0.6 V) per the datasheet table; the datasheet prints no explicit "tie EN to IN" sentence.
18. **F1 PPTC sizing tension** (§13) — DESIGN.md's 3 A-hold choice vs its own 5.2 A worst-case draw estimate. A decision for Justin, not a calculation error.
