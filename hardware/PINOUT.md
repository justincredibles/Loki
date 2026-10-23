# Loki — Pin Mapping & Complete Build Sheet (EasyEDA edition)

Complete schematic + placement reference for the Loki HAT PCB: every subsystem, every component, every net, and the placement rules that matter electrically. The pin tables in **Part B** are the original DESIGN.md §3 tables, kept verbatim. If this file and `hardware/DESIGN.md` ever disagree on architecture, DESIGN.md wins; if they disagree on a component value, **this file wins** (it is derived from the manufacturers' datasheets, cited per section).

**Revision:** expanded 2026-10-16 from the §3 pin tables into the full build sheet. **Rewritten 2026-10-17 in beginner-friendly language** — every technical fact, value, and warning is identical to the original; plain-English explanations, a glossary, and drawing hints were added around them. **Updated 2026-10-21 for EasyEDA:** the build moved from KiCad to EasyEDA (EasyEDA Pro, desktop edition), and the schematic is being redrawn there from scratch. Every value, net name, and pin connection in Parts A–E is **unchanged** — what changed is the tooling guidance: a new "Building this schematic in EasyEDA" section up front, an **EasyEDA / LCSC pick** for every part in Part C, and short EasyEDA notes in the sections whose parts need hand-made footprints. Wherever older text says "set the Footprint field to `Library:Name`", read it the EasyEDA way: **you choose the footprint by choosing the LCSC part (the "device") in Part C's new column** — in EasyEDA the symbol, footprint, and orderable part are one pick, not three. `hardware/FOOTPRINTS.md` is no longer where you copy footprint strings from; it survives as the geometry reference (pad sizes and positions) for the few footprints you will draw by hand in EasyEDA. If you ever need the dense original wording, it is preserved as `pinout-full-technical-backup-2026-10-17.md`.

---

## How to read this document

**What this document is.** This is the complete recipe for Loki's circuit board. It tells you, for every single part on the board: what the part is, what value it has (for example, a 1 µF capacitor), and exactly which pins it connects between. If you draw everything in Part A into your KiCad schematic, wire for wire, you will have the whole board. Parts B–E are reference material that supports Part A.

**The five parts:**

- **Part A — Subsystem build sheets.** The main event. The board is divided into 13 numbered sections (§1 charger, §2 fuel gauge, §3 boost converter, and so on). Each section covers one chip and all the small parts around it. Work through them in order, drawing each section into the schematic before moving on — that's exactly how you've been doing it.
- **Part B — Pin assignment tables.** The master lists of what every pin of the Raspberry Pi header, the ESP32, and the expansion header does. You mostly use these to double-check a connection while drawing Part A.
- **Part C — Complete BOM.** The shopping list ("BOM" = Bill of Materials): every part, how many, what package size, and its LCSC part number where one is confirmed.
- **Part D — Placement rules.** Rules for the *PCB layout* step (arranging the physical parts on the board in KiCad), which comes after the schematic. You can skim these now; they matter when you start laying out the board.
- **Part E — Sources & verification status.** Where every value came from (which manufacturer's datasheet), plus a numbered double-check list of the few things that could not be fully confirmed. Read it before ordering boards.

**Schematic vs. layout — the one distinction that unlocks half the wording.** Building a board in KiCad is two separate jobs. First the **schematic**: a diagram showing which pins connect to which, drawn with symbols. Distances on the schematic page mean nothing — two parts drawn far apart can still be connected by a wire or a shared net name. Second the **PCB layout**: the physical board, where every part gets a **footprint** (the pattern of copper pads it solders to) and position suddenly matters a lot. Whenever this document says things like *"closest to the pin"*, *"within 3 mm"*, or *"keep this loop tiny"*, that is a **layout** instruction — write it down for later, but it does not change what you draw in the schematic today. Whenever it says *"connects to"*, *"→ GND"*, or *"no connect"*, that is a **schematic** instruction — it changes what you draw now.

**How the values are marked.** Every value in Part A carries a tag saying how much you can trust it:

- **(DS)** — taken straight from the chip manufacturer's datasheet or application note (the chip's official manual). Trust it.
- **(CALC)** — calculated for this design, with the arithmetic shown so you can check it. The result is what you use; the arithmetic is there so the number isn't magic.
- **(EC)** — "engineering choice": the datasheet doesn't specify a value, so a sensible standard one was picked. Treat it as a good starting point, not gospel.
- **⚠️ VERIFY** — could not be confirmed from an official source. The flag stays visible wherever it applies, and in this rewrite each one also gets a plain-English note telling you what to actually *do* about it (usually: check one specific thing in one specific datasheet before the boards are ordered — nothing you have to resolve while drawing).

**Reference designators ("refdes") — the naming system.** Every part on the board has a code name: a letter for its type plus a number. **C** = capacitor, **R** = resistor, **L** = inductor (a coil), **U** = a chip/IC or module, **D** = diode or LED, **Q** = transistor, **J** = connector, **F** = fuse, **Y** = crystal, **SW** = switch, **SJ** = solder jumper, **SD** = card slot, **TP** = test pad. The number's first digit(s) tell you which section of the board it belongs to: 1xx = charger, 2xx = fuel gauge, 3xx = boost, and so on (full list just below Part A's intro, under "Reference-designator groups"). So **C304** reads as "capacitor, in section 3 (boost), number 04". When the document says **C301/C302/C303 = 3 × 22 µF**, it means three separate capacitors, named C301, C302 and C303, each one 22 µF. A range like **R1114–R1117** means the four resistors R1114, R1115, R1116 and R1117.

**In KiCad, set the Reference by hand.** KiCad's automatic numbering will want to call your capacitors C1, C2, C3… in the order you place them. Double-click each part and type the Reference from this document (C101, R101, …) into its Reference field, so your schematic matches this document, the BOM, and the FOOTPRINTS.md map exactly. It costs a few seconds per part and saves endless confusion later. The **Value** field gets the value from this document (e.g. `1uF`, `890`, `22uF`). The **Footprint** field gets the `Library:Name` string from `hardware/FOOTPRINTS.md`.

**Generic symbols.** Most small parts have no dedicated KiCad symbol, and that's normal — you use the plain generic symbol and let the Reference + Value + Footprint fields say what it really is. Capacitors: `Device:C`. Resistors: `Device:R`. Inductors: `Device:L`. Ground: the `power:GND` symbol (every GND symbol on the page is automatically the same connection — that's how ground is drawn). The chips (U1, U2, …) use their own specific symbols or a drawn box with the right pins; each section says what applies.

### Worked example — one part, end to end (R101)

Nearly every line in Part A follows the same pattern as this one, so here is one decoded completely, using the charger resistor from §1.2:

> | 16 | ISET | **R101 = 890 Ω** → GND | (CALC) … 890/890 = **1.00 A** charge current … Never leave ISET open: open = charging disabled |

- **"16"** is the pin number on the chip (U1, the battery charger). **"ISET"** is the pin's name — short for "current set". This pin is the charger's adjustment dial: the resistor you hang on it tells the charger how fast to charge the battery.
- **"R101 = 890 Ω"** — part R101 (resistor, section 1, number 01) has the value 890 ohms. Bigger resistor = slower charging; smaller = faster.
- **"→ GND"** — the other end of the resistor connects to ground. So the circuit is: pin 16 — resistor — ground.
- **The (CALC) note** explains where 890 came from: the datasheet gives a constant for this chip, K_ISET = 890, and the formula resistor = 890 ÷ desired amps. We want 1.00 A of charge current, so 890 ÷ 1.00 = 890 Ω. You don't need to redo this math — it's shown so you can see the number was derived, not guessed.
- **"Never leave ISET open"** — if this pin is connected to nothing, the charger reads that as "no setting" and switches charging off entirely. In KiCad terms: this pin must end up wired to the resistor. (A pin that is *supposed* to be unconnected gets a red no-connect flag — the little X tool — so KiCad knows it's deliberate. ISET is not one of those pins.)
- **What you actually draw:** place U1's symbol; place a `Device:R`; set its Reference to `R101` and Value to `890`; wire one end of the resistor to U1's pin 16 and the other end to a `power:GND` symbol; set the resistor's Footprint to `Resistor_SMD:R_0603_1608Metric` (per FOOTPRINTS.md). Done — that is the whole pattern, repeated ~180 times with different pins and values.

C101 works the same way: it is the capacitor on U1's pin 13 (IN) — `Device:C`, Reference `C101`, Value `1uF`, one side wired to pin 13's net, the other side to GND, footprint `Capacitor_SMD:C_0603_1608Metric`.

---

---

## Building this schematic in EasyEDA (start here)

*What this section is for: everything about the tool itself — how EasyEDA thinks, how you set the project up, and the handful of places where EasyEDA works differently from the KiCad instructions in the rest of this document. The circuit doesn't change at all; only the drawing mechanics do. Read this once, then work through Part A section by section exactly as before.*

### The one big difference: a "device" is symbol + footprint + real part in a single pick

In KiCad you drew in two steps: place a symbol now, assign a footprint later. **EasyEDA deletes the second step.** Parts live in the **Library** panel, and almost every part there is a **device** — one entry that bundles the schematic symbol, the PCB footprint, and the actual orderable LCSC part (its **C-number**, like C165948) into a single pick. When you place a device, the footprint question is already answered, and the same pick later tells JLCPCB exactly which physical part to solder on.

Three consequences:

1. **Choosing the part IS choosing the footprint.** If you grab the wrong variant (say, a 24C32 in the wrong package), the footprint is wrong too — there is no later step where you'd catch it. Part C's new **EasyEDA / LCSC** column exists to make this pick exact: it gives the C-number to search for, or the exact search words when any of several equivalents will do.
2. **Search by C-number whenever the column gives one.** The Library search box accepts a C-number directly, and it lands on one exact part. Searching by name ("24C32") returns a page of near-identical variants in different packages — the C-number is the disambiguator.
3. **Prefer parts marked "JLCPCB Basic" for the small stuff.** Basic parts live pre-loaded on JLCPCB's assembly machines, so they cost less to place and never add an extended-part fee or a stock surprise. Part C steers every resistor and capacitor to a Basic-class pick for this reason. (Extended parts — like SD1 — work fine; they just cost a small per-part-type fee at assembly time.)

### Project setup (do this once)

1. Create the project (e.g. `Loki`) in EasyEDA Pro.
2. Inside it, create **one schematic page per section of this document** — EasyEDA Pro supports multiple schematic pages in one project. Name them after the sections: `01 Charger`, `02 Fuel gauge`, `03 Boost 5V`, `04 Buck 3V3`, `05 ESP32 + USB2`, `06 CC1101`, `07 nRF24`, `08 NFC header`, `09 microSD`, `10 IR`, `11 Pi interface`, `12 Expansion`, `13 Battery`. Thirteen small pages beat one giant sheet: each page is one sitting's work, and you can check it against its Part A section before moving on.
3. You don't create the PCB yet. Schematic first, in full; converting to PCB is a later phase (Part D's rules apply then).

### Drawing mechanics — the KiCad ideas, translated

- **References (C101, R101, …):** EasyEDA auto-numbers parts as you place them, same as KiCad did. Rename each part's **Designator** (click the part, edit it in the properties panel on the right) to the reference this document gives, as you go. Your schematic, this document, and the BOM then all speak the same names.
- **Values:** the value (e.g. `890`, `22uF`) goes in the part's **Value** field, same as before. For chips and modules the "value" is the part name from Part C (e.g. `bq24074RGTR`).
- **Generic passives:** resistors, capacitors, and inductors are placed straight from the Library by value + package — e.g. search `0603 10k` and pick a JLCPCB Basic result. There is no separate "generic symbol, footprint later" step; the device you pick is 0603 because you picked a 0603 part.
- **Ground:** place GND symbols from the Library's power/ground flags (search `GND`). Every GND on every page is the same net, exactly like KiCad's `power:GND`.
- **Net labels — how wires jump across the drawing:** a named net is a connection, in EasyEDA just as in KiCad. Use **Place → Net Label** for nets that stay on one page. For nets that run between pages (all the power rails — `VBAT`, `VSYS`, `5V_SYS`, `3V3` — and shared signals like the I²C and UART lines), use **Place → Net Port** with the exact net name from the "Net names used throughout" table: a port is a visible doorway, and every port with the same name is connected, across all pages. Either way, **the name must match this document character-for-character** — `5V_SYS` and `5VSYS` are two different, unconnected nets as far as the tool is concerned.
- **Deliberately unconnected pins (NC):** mark them with EasyEDA's **No Connect** flag (Place → No Connect), the same discipline as KiCad's little X: it tells the checker "this pin is empty on purpose" so real mistakes stand out.
- **Power pins that hide:** some EasyEDA library symbols, like KiCad's, tuck power pins away or stack several same-name pins into one visible pin (the USB-C connectors' VBUS/GND pins and the ESP32 module's ground pads are the local examples). The pin-by-pin tables in Part A are the authority on what must end up connected — if a table says a pin goes to a net and you can't see the pin, check the symbol's full pin list in the Library before assuming it's handled.

### Checking your work (EasyEDA's checker is lighter than KiCad's ERC — compensate)

KiCad's ERC produced those error/warning lists we worked through. EasyEDA Pro's built-in schematic checking is thinner — it will catch some unconnected pins and missing footprints, especially when you run **Design → Schematic to PCB** later, but it will not audit you the way ERC did. So the checking discipline moves to a habit:

- **After each page**, open the **Design Manager** panel and read the net list for that page's nets: every pin the Part A table names for a net should appear in it, and nothing extra should. Five minutes per page, while the section is fresh.
- Keep the Part B pin tables open as the second opinion — they are the same tables, organized by chip instead of by net.
- The known traps from the KiCad build all still apply electrically, even if the new tool doesn't flag them: U3's SW pins 4–7 and VOUT pins 14–16 are gangs (several physical pads, one connection — draw them all to the same net), and the ESP32 module has ground pads beyond the one obvious pin (pads 40/41 — draw them to GND in the schematic if the symbol exposes them; check at PCB time that they land on GND either way).

### The five parts EasyEDA does not hand you ready-made

Most of Loki is ordinary LCSC parts with ready devices. Five are not — for these, Part C's column and the section notes say which case you're in:

- **U3 TPS61088** — LCSC **C87357** ✅ (verified on its LCSC page 2026-10-21: TPS61088RHLR, genuine TI, VQFN-20 RHL package, $0.86, in stock). This corrects an earlier claim in this doc that LCSC doesn't stock the part — it does. Pick the C87357 device in EasyEDA. One check when you place it: confirm the device's footprint really is TI's RHL land pattern (4.5 × 3.5 mm; pad geometry in `hardware/FOOTPRINTS.md`) — one LCSC description field showed inconsistent dimensions. However the symbol presents them, pins 4–7 (SW) all go to the one SW net and pins 14–16 (VOUT) all go to `5V_SYS`.
- **U6 E07-900M10S and U7 E01-ML01SP4** — EBYTE modules are not standard LCSC stock either. Same recipe: search the library (including user-contributed) for `E07-900M10S` / `E01-ML01SP4`; otherwise draw them from the pin tables in §6/§7 (22 and 10 pins — the pin functions are fully listed there) with the pad layouts from FOOTPRINTS.md. ⚠️ The KiCad footprints for these two carry an honesty note that still applies: pad count, pitch, and pin functions are datasheet-confirmed, but pad size and pin-1 orientation were never verified against a physical module. Caliper a real module before the board is ordered — in either tool.
- **SD1 Hirose DM3D-SF** — this one *is* a verified LCSC part (**C719027 ✅**, checked on JLCPCB's own page 2026-10-21, listed with an EasyEDA library), so a ready device should exist; still check its footprint against the land pattern before trusting it (JLC's attribute data for this part is already wrong once — it claims "no card detection"; Hirose's datasheet says otherwise). If it's missing or wrong, the full pad-coordinate table in `hardware/kicad/dm3d-sf-footprint-notes.md` lets you redraw it exactly (14 pads; pin 1 at the +X end; pad 9 = detect switch A, pad 10 = switch B to GND).
- **U11 TSOP38438** — an LCSC part (C145271) with wire legs (through-hole). A library device should exist; if its footprint is missing, it's three holes on 2.54 mm pitch per §10.1.
- **J1 stacking header (2×20)** — electrically it's just a 2×20, 2.54 mm through-hole header; the special part is mechanical (long pins that pass through to the display). Any 2×20 header device gives the right schematic; at PCB/order time the footprint is the standard 2×20 pattern and the physical part is the long-pin stacking type from Part C.

---

## Glossary — every piece of jargon in this document, in plain English

**Abs-max (absolute maximum ratings).** The datasheet table of hard limits — exceed them, even briefly, and the chip may be damaged. Different from the *recommended* operating range, which is where you're supposed to live.

**Active-low.** A signal that does its job when it's at 0 V instead of at the supply voltage. Example: the charger's CHG pin sits high doing nothing, and pulls *down* to ground while charging — "low = active". Written with a bar or "_N" in some pin names (e.g. RSTPD_N).

**AGND (analog ground).** A ground pin a chip keeps separate for its quiet, sensitive circuitry. On the finished board it still joins the same ground plane as everything else — the separate name just tells you to connect it at the chip, not route it somewhere strange.

**"At the pin" / "tight to the pin" / "closest to the pin".** A layout instruction: in the physical board layout, place that part immediately next to the named pin — within a few millimetres. Some parts (especially small capacitors on power pins) only do their job when they're physically close; a long trace between the pin and the part acts like a tiny coil and defeats the purpose.

**BOM (Bill of Materials).** The complete shopping list of parts for the board. **BOM freeze** is the moment the part choices are locked so footprints and ordering can be finalized — "confirm at BOM freeze" means "nobody has picked the exact orderable part yet; it gets decided at that lock-in moment, not now".

**Bulk capacitor.** A relatively big capacitor (here, 10–22 µF) placed on a power rail as a local reservoir: the circuit gulps current in pulses, and the bulk cap supplies the gulps so the voltage doesn't dip. Compare *decoupling capacitor* below — many caps here do both jobs at once, and a typical recipe is one bulk cap + one small decoupling cap side by side on the same pin.

**Capacitor size codes (0603, 0805, 1206, 1812, 2520, 3225).** Standard physical sizes for surface-mount parts, in hundredths of an inch (0603 = 0.06″ × 0.03″) or metric for the bigger ones. The size is part of the footprint choice — a 22 µF capacitor in this design is physically bigger (0805/1206) than a 0.1 µF one (0603) even though both are "a capacitor". Part C lists the package for every part.

**Decoupling / bypass capacitor.** A small capacitor (usually 0.1 µF) wired from a chip's power pin straight to ground, placed right at the pin. Chips switch internally millions of times a second and make electrical noise while drawing current in tiny spikes; the decoupling cap is a tiny local reservoir + noise drain that keeps the chip's own supply clean and stops its noise spreading. "IN → GND at the pin" in a table means: one side of the cap to the IN pin's net, other side to ground, placed (at layout time) right next to that pin.

**Device (EasyEDA).** One Library entry that bundles a schematic symbol, a PCB footprint, and a real orderable part (with its LCSC C-number) into a single pick. Placing a device answers the symbol, footprint, and sourcing questions in one move — which is why Part C now names the exact device (or search) for every part.

**Differential pair.** Two wires that carry the same signal in opposite polarities (USB's D+ and D− are the classic pair). They must be routed together, the same length, with an unbroken ground beneath them, so interference cancels out. Applies here to the USB-C port's data lines.

**Divider (voltage divider).** Two resistors in series between a voltage and ground; the middle point sits at a predictable fraction of the voltage. Used two ways here: to *set* an output voltage (the chip watches the middle point and adjusts until it hits its reference — that's the FB/feedback divider on both converters), and to *sense* a voltage safely (the VBUS-detect divider halves 5 V so the ESP32 pin sees ≈2.5 V).

**DNP (Do Not Populate).** A part whose footprint is drawn on the board but which is **not fitted** in the standard build. The pads are there so the option exists; the part is left off. Example: the spring-antenna option is DNP when the SMA whip antenna is fitted — exactly one of the two gets installed.

**ESR (equivalent series resistance).** A small unwanted resistance inside every real capacitor. Low ESR = the capacitor can deliver/absorb current fast, which is what power circuits need. Ceramic capacitors (everything in this design) are naturally low-ESR.

**Feedforward capacitor.** A small capacitor wired *across* the top resistor of a feedback divider. It lets fast voltage changes at the output reach the chip's feedback pin sooner, so the converter reacts quicker to sudden load changes ("transient response").

**Footprint.** The pattern of copper pads on the physical board that a part solders onto — one specific pattern per part/package. In KiCad, each schematic symbol gets a footprint assigned (that's what `hardware/FOOTPRINTS.md` maps out). The schematic doesn't care about size; the layout is nothing but sizes.

**GND / ground.** The common 0 V reference for the whole board — every circuit's "return path". On this board, ground is a solid sheet of copper on layer 2 of the 4-layer board (the **ground plane**), and anything marked GND connects down into it. In the schematic, every `power:GND` symbol is the same connection, even though they're drawn in different corners of the page.

**High-impedance (Hi-Z).** An input pin that listens without drawing meaningful current — it senses voltage only. A button wire connected to a high-impedance input doesn't get "loaded down" by it.

**Hold / trip (PPTC ratings).** A PPTC is a resettable fuse (see below). Its **hold** current is the current it will carry forever without tripping (at room temperature); its **trip** current is where it is guaranteed to trip and block the current. Between the two is a grey zone, and the hold rating drops as temperature rises ("derates").

**I²C.** A two-wire communication bus (clock SCL + data SDA) that lets one chip talk to several others using addresses. Lines idle high, so each needs a **pull-up** resistor (see below). The Pi talks to the fuel gauge over I²C; the ESP32 talks to the PN532 over a separate I²C bus.

**JLCPCB Basic / Extended part.** JLCPCB's assembly service keeps a set of common parts ("Basic") permanently loaded on its machines — cheapest to place, always stocked. Everything else is "Extended": fully supported, but each distinct Extended part on a board adds a small loading fee and a stock check. Steering the ~50 resistors and capacitors to Basic parts is real money on an assembled board.

**Keep-out.** A zone on the board where copper (and sometimes parts) are forbidden — here, mainly under/around antennas, because copper near an antenna detunes it and absorbs the radio energy.

**LCSC.** The parts distributor whose stock JLCPCB (the board fabricator/assembler used for this project) assembles from. An "LCSC number" like C165948 is the exact orderable part. ✅ means the number is verified; "confirm" means the exact part hasn't been picked yet.

**LDO.** A simple type of voltage regulator chip (low-dropout regulator). Mentioned here because some chips have one built in — the PN532 makes its own internal ~3.0 V rail with one, and the TPS61088's VCC pin is the *output* of its internal LDO: you put a capacitor on it, you never feed power into it.

**Net.** Any set of pins that are wired together is one "net" — think of it as one electrical node, one connected piece of copper. Nets get names: `VSYS`, `3V3`, `USB1_VBUS`. In KiCad's schematic, two points with the same net label are connected even if no wire is drawn between them. When a table says pin X connects to "net `3V3`", it means: wire it to the board's 3.3 V supply web, wherever that is drawn.

**Net port (EasyEDA).** A visible doorway symbol for a named net, used when a connection continues onto another schematic page. Every port with the same name is the same net, across all pages — the multi-page version of a net label.

**NC / no-connect.** A pin that must be connected to *nothing* — deliberately left unconnected. In KiCad you mark these with the no-connect flag (the little X) so the checker knows it's intentional, not a mistake. NC sometimes also names a pin that exists physically but does nothing internally.

**NTC thermistor.** A resistor whose value changes predictably with temperature — used as a battery temperature sensor. The bq24074 expects one on its TS pin; our battery packs don't have the sensor wire, so a fixed 10 kΩ resistor "defeats" (fakes) it instead.

**Open-drain.** A type of output pin that can only pull a line *down* to ground or let go — it can never push the line high by itself. So an open-drain line always needs a pull-up resistor (or an LED path to a supply) to ever read "high". The charger's CHG and PGOOD pins, the fuel gauge's ALRT pin, and the ESP32's attention line all work this way.

**Package.** The physical body style of a part: **SOT-23** (small 3- or 5/6-pin plastic package), **SOIC-8** (8-pin with legs), **VQFN / TDFN / HVQFN** (flat square chips with pads underneath and around the edges, no legs — a size and pin count follow, e.g. VQFN-16 is 16 pads), **Minicast** (Vishay's little leaded can for IR receivers), **1206 / 0805 / 0603** (chip sizes, see above). The package decides the footprint.

**PCM.** The tiny protection circuit board built into most lithium battery packs — last-resort protection against shorts, over-charge and over-discharge.

**Pin / pad.** A **pin** is one electrical connection point on a chip (numbered — pin 1, pin 2, … — and named — IN, GND, ISET…). Modules with solder connections around their edges call them **pads** instead. "Pin 13 (IN)" means pin number 13, whose function name is IN.

**Pitch.** The spacing between adjacent pins/pads, centre to centre. Headers here are 2.54 mm pitch (the classic 0.1″ grid); the microSD slot contacts and fine-pitch chips are smaller.

**Pour.** A filled area of copper connected to a net, instead of thin traces — used for ground and for high-current paths (a wide pour carries amps without heating up; a thin trace can't). "Via-stitched pour" means the pour is tied to the same net on another layer by many small vias, making it fatter still.

**PPTC.** A resettable fuse: it behaves like a wire until current exceeds its trip point, then it heats up and chokes the current off; when it cools, it works again. Used here as battery and expansion-port protection.

**Pull-up / pull-down.** A resistor that gently connects a signal line to the supply (pull-up) or to ground (pull-down) so the line has a definite default voltage when nothing else is driving it. Without one, an un-driven line "floats" — it picks up noise and reads randomly. Every open-drain line here has one. "PU" in Part B/C is short for pull-up.

**Q (quality factor).** For the NFC antenna network: roughly, how sharply the antenna circuit is tuned. The design targets Q ≈ 35 — sharp enough for good range, broad enough to be forgiving.

**Rail.** A supply voltage distributed around the board — "the 3.3 V rail" is just the `3V3` net thought of as a power supply. This board has four: `VBAT` (raw battery), `VSYS` (always-on system voltage), `5V_SYS` (5.1 V, only when switched on), `3V3` (3.3 V, only when switched on).

**Rd (USB-C).** The 5.1 kΩ resistor a USB-C *device* (power sink) must put on each CC pin to announce "I'm a device, send me 5 V". Both USB-C ports here are sinks, so all four CC pins get one.

**Refdes.** See "Reference designators" above — the C101/R101-style code name of a part.

**Series / shunt.** A part wired **in series** sits *in the path* of a signal — the signal flows through it (a resistor in series with an LED limits the LED's current). A part wired as a **shunt** sits *across* a line, from the line down to ground (or across another part) — shunt capacitors drain noise to ground; a shunt resistor bleeds current away. "R in series with C to ground" = signal → resistor → capacitor → ground, one after the other.

**Silkscreen ("silk").** The white printing on the board (labels, outlines, the "+" by the battery connector). Purely informational — but a polarity mark in silk is cheap insurance.

**Sink / source (current).** A pin **sinks** current when current flows *into* it toward ground (like a drain); it **sources** current when current flows *out of* it. "Abs-max sink 15 mA" means: never let more than 15 mA flow into that pin.

**Solder jumper (SJ).** Two or three bare pads you bridge with a blob of solder to choose a setting — a zero-cost switch. SJ1 here selects whether the EEPROM is writable or locked.

**SPI.** A fast chip-to-chip bus: clock (SCK), data out (MOSI), data in (MISO), and one chip-select (CS) wire per device — the master (ESP32) selects one device at a time by pulling its CS low. The CC1101, nRF24 and microSD card all share one SPI bus here.

**Strapping pin.** A chip pin that is read once, at the instant the chip starts up, to choose a boot option (which program to run, etc.). Between resets it's a normal pin, but you must not hang anything on it that would hold it at the wrong level during that first instant. The ESP32 has several; this document flags each one.

**Stub.** A short branch off a signal line to nowhere useful. Stubs reflect fast signals and corrupt them — "no stubs on the USB pair" means the line runs connector → protection chip → ESP32 in one clean path.

**Thermal pad / exposed pad (EP).** The metal pad under many flat chips. It carries heat out of the chip and is usually also a ground connection. In the layout it gets its own copper area with **thermal vias** — little plated holes that conduct heat down into the ground plane. Note it is a pin too (it must connect to GND), not just a heatsink.

**UART.** The classic two-wire serial link (TX = transmit, RX = receive) between the Pi and the ESP32 here. 115200 8N1 = 115200 bits/second, 8 data bits, No parity, 1 stop bit.

**Vf (forward voltage).** The voltage a diode/LED "uses up" while conducting — a red LED ≈ 2.0 V, green ≈ 2.1 V, blue ≈ 3.0 V, the IR LED ≈ 1.35 V. LED resistor math is always: (supply − Vf) ÷ resistor = LED current.

**Via.** A tiny plated hole that connects copper on one board layer to another layer. Signals and power hop between layers through vias; more/bigger vias in parallel carry more current and heat.

**X5R / X7R / C0G.** Codes for ceramic capacitor dielectric (the insulating material inside). X7R and X5R are the general-purpose types used for power/bulk/decoupling here (X7R is a bit more stable than X5R). C0G is the precision type — its value barely moves with temperature or voltage — used where the exact value is the tuning (crystal load caps, NFC matching, the boost COMP cap).

---
## ⚠️ Read first — three errata against DESIGN.md found during datasheet verification

("Errata" = corrections to the earlier design document, found when every value was checked against the manufacturers' datasheets. These three matter before you draw anything.)

1. **bq24074 input limit cannot be 3 A.** DESIGN.md §2.6 says "ILIM ≈ 3 A input". Per TI SLUS810N, the ILIM resistor range (1.1–8 kΩ) programs only **200 mA–1.5 A**, and IN is rated 1.5 A recommended / 1.6 A abs-max. This build sheet sets ILIM to the maximum (~1.4 A). System load above the input limit is supplemented from the battery by the power-path (OUT is rated 4.5 A), so the device still works — but **net charging while a Pi 5 is under load will be slow or negative**, and full-speed charging happens with the device off/idle (as DESIGN.md §4.3 already anticipates). If a future rev wants real 3 A input, the charger IC must change.
   - *In plain terms:* the charger chip physically cannot be told "take up to 3 A from USB" — 1.5 A is its ceiling, and this design runs it at ~1.4 A. Loki still works fine plugged in (the battery tops up whatever USB can't supply), but if the Pi 5 is working hard on USB power, the battery may slowly drain instead of charge. Nothing for you to do — just don't "fix" R102 to a smaller value chasing 3 A; 1.1 kΩ is already the maximum setting.
2. **"NXP AN10688" is the wrong document number for the PN532 antenna design.** No PN532 document numbered AN10688 could be found. The antenna/EMC/matching values here come from **NXP AN1445** (*Antenna design guide for MFRC52x, PN51x and PN53x*, which explicitly covers PN532) plus the PN532/C1 data sheet §13 reference circuit.
   - *In plain terms:* a cited document number in the design doc was simply wrong. The NFC values in §8 come from the correct document (AN1445). Nothing for you to do.
3. **TSOP38438 is a through-hole part** (Vishay Minicast, leaded), not SMD as DESIGN.md §2.5 calls it. Its footprint is THT — JLCPCB THT assembly or a builder-soldered part. The VS1838B fallback is also a leaded can. There is no true-SMD receiver in the current selection; if that matters, the IR receiver choice needs a rev-2 revisit.
   - *In plain terms:* the IR receiver (§10.1, U11) has wire legs that go *through* holes in the board, unlike almost everything else on Loki, which solders flat onto the surface (SMD). Its footprint in FOOTPRINTS.md already accounts for this. Nothing changes in the schematic — just don't be surprised that its footprint looks different, and know it may be a hand-soldered part in assembly.

---

## Net names used throughout

Every named net below is one of the board's shared connections. In the schematic, when two places carry the same net name, they are wired together — the name *is* the wire.

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

In plain terms, the power story of the whole board is: battery power enters as `VBAT_RAW`, passes the resettable fuse F1 and becomes `VBAT`. The charger chip (U1) outputs `VSYS`, which is alive whenever a battery is fitted or USB is plugged in — even with the device "off". Only when you flip the power switch does the boost converter (U3) turn `VSYS` into `5V_SYS` (5.1 V for the Pi), and the buck converter (U4) turn that into `3V3` (for the ESP32 and radios). So: `VSYS` = always-on domain, `5V_SYS`/`3V3` = switched domain. "Stackup" means the layer sandwich of the board — 4 copper layers, with layer 2 (L2) as one solid ground sheet.

## Reference-designator groups

1xx charger/USB-C · 2xx fuel gauge · 3xx 5 V boost · 4xx 3.3 V buck · 5xx ESP32/USB · 6xx CC1101 · 7xx nRF24 · 8xx PN532 · 9xx microSD · 10xx IR · 11xx Pi interface/EEPROM/LED/expansion · battery parts ungrouped (J4, F1).

---

# Part A — Subsystem build sheets

*How Part A works: each numbered section is one subsystem — one main chip and every small part connected to it. Each section starts with a plain-English summary of what that part of the board does and what you will draw, then the exact pin-by-pin tables. The tables are the authority; the summaries are the map.*

## 1. Power input & charging — TI bq24074 (U1)

**What this section does.** U1 is the battery charger and the board's front door for power. The board's single USB-C port (J2) plugs into it — that same connector also carries the ESP32's USB data lines (§5.1), but U1 only ever sees its VBUS pin; the data pair passes the charger by entirely. U1 charges the lithium battery at up to 1.0 A, and — this is why this chip was chosen — it merges the sources: Loki can run from USB while the battery charges, and if the load wants more than USB can give, the battery silently makes up the difference (that's the "power-path" feature). Its OUT pin produces the `VSYS` net, the always-on voltage everything else in the power chain feeds from. It also lights the blue LED while charging, with no software involved.

**What you draw.** The U1 symbol; the J2 USB-C connector symbol with two 5.1 kΩ resistors on its CC pins and net stubs on its D+/D− pins (the ESP32's data pair — the rest of that chain is drawn in §5.1); one capacitor on each of the IN, BAT and OUT pins; one resistor on each of the ISET, ILIM and TS pins; two pins (TMR, ITERM) deliberately left unconnected; and the blue LED with its resistor. Sixteen pins, but most of them are one part each.

Source for all values: TI **SLUS810N** (bq2407x family datasheet), sections cited per item.
U1 = bq24074RGTR, VQFN-16 + thermal pad. (VQFN-16: a flat, square 16-pad chip package with a metal thermal pad in the middle of its underside — the pad is pin "EP" in the table below and must connect to GND.)

> **⚠️ EasyEDA note — the charger's evil twin.** Library search will offer you the **BQ24075RGTR (C15464)** first — a different member of the charger family with different defaults, and **not** this design's part. Loki uses the **bq24074**; this entire section is written from its datasheet (SLUS810N). Search the full string `BQ24074RGTR`. The project-recorded LCSC number is C54313 — it could not be re-confirmed on an LCSC page in the 2026-10-21 check, so if the number doesn't resolve in the picker, pick by full part name + VQFN-16 package and write the number you landed on into Part C.

### 1.1 USB-C — the single shared port (J2): charging + ESP32 data

J2 = HRO TYPE-C-31-M-12, LCSC C165948 ✅.

*Loki has ONE USB-C port (decision D11, 2026-10-22 — this supersedes the original two-port arrangement, in which a second connector J3 carried the ESP32's data; J3 is deleted). The port's power pins serve the charger (this section); its data pins serve the ESP32 (§5.1). The two jobs use different pins of the same connector and both want the same CC termination, so they coexist without any switching.*

| J2 terminal | Connection |
|---|---|
| VBUS (all) | Net `USB1_VBUS` → U1 pin 13 (IN); the same net is also tapped by the ESP32's VBUS-detect divider (§5.1). **5 V only by design** — no USB-PD circuitry anywhere on this port |
| CC1 | R105, 5.1 kΩ → GND (Rd, marks the port as a sink) |
| CC2 | R106, 5.1 kΩ → GND |
| D+ / D− | → U10 ESD array → ESP32 USB (§5.1). **Draw net stubs here** (both A-side and B-side contacts of each pair join the one net: A6+B6 = D+, A7+B7 = D−); the rest of the chain is drawn on the §5 page. SBU pins stay no-connect |
| Shield | GND (chassis fingers to enclosure if metal hardware is used) |

*Plain terms:* VBUS is the USB power wire; all its contacts are one net, `USB1_VBUS`, running to the charger's IN pin. This port asks for plain 5 V only — the two 5.1 kΩ resistors (R105/R106) on the CC pins are how a USB-C device says "I'm a sink, give me 5 V" (see *Rd* in the glossary), and that same termination is what the ESP32's USB-device role needs, which is why one pair of resistors serves both jobs. The D+/D− pins are the ESP32's data pair (BadUSB + flashing) — on this page they just get named net stubs; §5.1 picks them up. The metal shield of the connector goes to GND.

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

*Plain terms for the less obvious pins:*
- **EN1 / EN2** are the charger's mode-select pins — two switches that tell it which current-limit rule to use. Wiring EN2 to the USB voltage and EN1 to ground selects "use the ILIM resistor" whenever USB is plugged in. The ⚠️ VERIFY on EN2 is not something to resolve while drawing: it means that before the parts are ordered (BOM freeze), someone should open the SLUS810N datasheet's absolute-maximum table and confirm the EN pins tolerate 5 V. The family's other logic pins are rated 7 V-class, so this is expected to pass — it's a checklist item, not a design change. Draw EN2 → `USB1_VBUS` as written.
- **CE** is the on/off switch for charging. It's active-low (ground = "charging on"), and even though the chip has a built-in pull-down, the design wires it to GND explicitly — "do not float" means never leave a control pin unconnected to fend for itself; it could pick up noise and misbehave.
- **TMR and ITERM** are settings pins that this design deliberately leaves unconnected (no-connect flags in KiCad), because unconnected = the datasheet's built-in defaults, which are what we want: default safety timers (the charger gives up if charging takes abnormally long) and default charge termination (stop when charge current tapers to 100 mA). Especially do **not** ground TMR — that turns the safety timers off.
- **TS** is the battery temperature-sensor input. Our battery packs have no temperature wire, so R103 (10 kΩ to GND) fakes a "temperature is fine" reading permanently. It must be this resistor — grounding TS directly, or leaving it open, makes the charger refuse to charge.
- **CHG** (pin 9) is an open-drain, active-low output: while charging, it connects itself to ground. That's what lights the blue LED in §1.3 — the LED's other side goes to `VSYS`, so current flows supply → LED → CHG pin → ground whenever charging. "Abs-max sink 15 mA" = never let it swallow more than 15 mA; §1.3's resistor keeps it at ~1.4 mA.
- **PGOOD** would tell a processor "input power is good" — nothing reads it in v1, so it gets a no-connect flag. Don't tie it to any supply.
- **EP (thermal pad):** the metal pad under the chip. It goes to GND and gets thermal vias at layout, but note the warning: pin 8 (VSS) still needs its own ground connection — the pad alone isn't the chip's ground path.

**Placement:** C101/C102/C103 within ~3 mm of their pins. U1 sits near the USB-C board edge so the IN run from J2 is short. *(Layout note — matters at PCB time, not in the schematic.)*

### 1.3 Blue "charging" LED (D4)

VSYS → **R104 = 1.0 kΩ** → D4 anode; D4 cathode → U1 pin 9 (CHG). D4 = 0805 blue (LCSC: confirm at BOM freeze ⚠️).

*Plain terms:* an LED needs a resistor in series with it to limit its current, or it burns out — that's R104's whole job. The chain is: `VSYS` → resistor → LED (anode = the + side) → LED cathode (− side) → the CHG pin, which connects the chain to ground while charging. So the LED lights exactly while the charger is charging — including with the device switched off, because `VSYS` is alive whenever USB is in. The ⚠️ on D4 just means the exact orderable blue LED hasn't been picked yet; any standard 0805 blue LED works, and the pick happens at BOM freeze. Draw it as a generic LED (`Device:LED`) with footprint from FOOTPRINTS.md.

**(CALC)** With USB present VSYS = 4.4 V; blue Vf ≈ 3.0 V: I ≈ (4.4 − 3.0) / 1000 ≈ **1.4 mA** — well under CHG's 15 mA abs-max, bright enough for a modern high-efficiency 0805. (TI's own typical circuit uses 1.5 kΩ from OUT, §10.2.2.4; 1.0 kΩ trades a little current for visibility.) The LED lights whenever the charger is actively charging, including with the device switched off — exactly per spec, zero firmware. *(Vf = the voltage the LED itself drops; what's left across the resistor, divided by the resistance, is the current — the standard LED calculation you'll see again for D3 and D2.)*

---

## 2. Fuel gauge — MAX17048 (U2)

**What this section does.** U2 is the battery "fuel gauge" — the chip that tells the Pi what percentage of battery is left, the way a phone knows its battery percentage. It watches the battery voltage directly and talks to the Pi over I²C. It also drives the red "low battery" LED (§2.1) entirely in hardware, so the warning works even with the whole device switched off — the gauge never sleeps, because it runs straight off the battery and sips only ~25 µA.

**What you draw.** The U2 symbol; exactly **one** capacitor (C201) — this chip famously needs almost nothing around it; a few pins strapped straight to GND (CTG, QSTRT); one pin (CELL) left unconnected on purpose; and its two I²C wires to the Pi header, each with a pull-up resistor (§2.2). The ALRT pin goes to the Pi header *and* to the red LED network.

Source: Analog Devices **MAX17048/MAX17049 datasheet, doc. 19-6171 Rev 7** (cited "ADI DS").
U2 = MAX17048G+T10, TDFN-8 + EP. I²C address **0x36** (7-bit). *(I²C address: every device on an I²C bus has a number the master uses to call it. 0x36 is this chip's fixed number — firmware needs it, the schematic doesn't show it. TDFN-8: flat 8-pad package, same family as U1's.)*

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

*Plain terms:* VDD does double duty — it powers the chip *and* is the voltmeter input it measures the battery with, which is why it must come from `VBAT` (the real battery), not from the regulated `VSYS`. CELL is a leftover pin that only does something on the 2-cell sibling chip (MAX17049); on ours it's dead inside, so it gets a no-connect flag and no parts. QSTRT ("quick start") is a feature we don't use, and the datasheet says to ground it when unused — unused pins on this chip are either grounded or flagged no-connect exactly as the table says; never just left dangling by accident. ALRT ("alert") is the open-drain, active-low output that drops to ground when the battery is low: the Pi reads it as an interrupt on GPIO4, and the same wire lights the red LED.

**Placement:** bottom side (per DESIGN.md §2.11 low-profile plan). Keep C201 tight to pin 3. VDD trace comes straight from the battery side of the board — the gauge must see the cell even when everything else is off (its draw is ~25 µA active / 4 µA hibernate, DESIGN.md §5.2). *(Layout notes. "Bottom side" = this chip mounts on the underside of the board, the side facing the Pi.)*

### 2.1 Red "low battery" LED (D3)

VSYS → **R201 = 1.0 kΩ** → D3 anode; D3 cathode → U2 pin 5 (ALRT). D3 = 0805 red, LCSC C84256 ✅.

*Plain terms:* same LED pattern as the blue one in §1.3 — supply → 1 kΩ resistor → LED → a chip pin that connects to ground when active. Here the ALRT pin pulls down when the battery is low, so the red LED lights on low battery, even with the device off. The calculation below exists because ALRT is a weak output: it's only *guaranteed* to hold the line low while sinking up to 4 mA, so the LED current is budgeted to stay under that, with the Pi's own input adding nearly nothing. The one firmware note (50 kΩ internal pull-up ≈ 70 µA extra) is fine as-is — it's recorded here so the software side knows not to enable a *strong* pull-up on GPIO4.

**(CALC + DS check)** ALRT is characterised at V_OL ≤ 0.4 V with I_OL = 4 mA, abs-max sink 20 mA (ADI DS Electrical Characteristics / Abs-Max). Budget: LED current + any pull-up current on the ALRT net must stay ≤ 4 mA for the guaranteed logic-low. Worst case VSYS = 4.4 V (USB present), red Vf ≈ 2.0 V: I_LED ≈ (4.4 − 2.0 − 0.2) / 1000 ≈ **2.2 mA**. Battery-only at the low-battery threshold (≈3.4 V): I ≈ (3.4 − 1.9 − 0.2) / 1000 ≈ 1.3 mA — visible on a high-efficiency 0805. The Pi-side GPIO4 input is high-impedance; **firmware must not enable a strong pull-up on GPIO4** (the Pi's internal ~50 kΩ pull-up, if enabled, adds only ~70 µA — acceptable; note it in the software handoff). The LED lights with the device off — per spec.

### 2.2 I²C1 pull-ups

**R202 = 4.7 kΩ** (SDA→3V3), **R203 = 4.7 kΩ** (SCL→3V3), on the HAT (DESIGN.md §3.1). The MAX17048 datasheet requires system-provided pull-ups on SDA/SCL/ALRT but specifies **no value** (ADI DS Application Examples) — 4.7 kΩ is the standard I²C value for a short, low-capacitance bus (bus is specified to 400 kHz / 400 pF max). These pull-ups go to board `3V3`, so the bus is only pulled up when the device is on; the gauge itself stays alive on VBAT regardless. (The Pi also has its own 1.8 kΩ pull-ups on GPIO2/3 — the parallel combination is fine for this bus length.)

*Plain terms:* I²C lines are open-drain — devices can only pull them down, so something has to pull them back up, and that something is these two resistors, one per wire, each wired from the signal line up to `3V3`. 4.7 kΩ is the everyday standard value for a short bus like this. Two subtleties, both handled: the pull-ups run from the *switched* `3V3` rail, so when Loki is off the bus simply isn't pulled up (the gauge doesn't care — it stays alive on the battery); and the Pi has its own weaker pull-ups on the same wires, which combine harmlessly (two resistors in parallel — electrically fine here). **What you draw:** resistor from SDA to `3V3`, resistor from SCL to `3V3`. That's all a "pull-up" ever means in a schematic.

---

## 3. 5 V boost — TI TPS61088 (U3) + power switch (SW1)

**What this section does.** A lithium battery outputs 3.0–4.2 V, but the Raspberry Pi needs a steady 5.1 V. U3 is a **boost converter**: it takes the always-on `VSYS` (battery-level voltage) and steps it *up* to a regulated 5.1 V on the `5V_SYS` net — up to 4 A continuously, 5 A in peaks (Pi 5 territory). It does this by switching current through an inductor (L1) tens of thousands of times per second, which is why this section has the strictest layout rules on the board. The power switch SW1 doesn't switch the power itself — it just tells U3's EN pin "on" or "off".

**What you draw.** The U3 symbol (20 pins + the EP pad); three 22 µF capacitors on the VIN side and three more on the VOUT side, plus a 0.1 µF closest to VIN; the big inductor L1 between the SW pins and VIN; two resistors forming the feedback divider that sets 5.1 V; and single resistors/capacitors on the ILIM, FSW, SS and COMP setting pins. MODE gets a no-connect flag; NC pins 11/12 go to GND. Then SW1, a simple slide switch wired between `VSYS` and the `PWR_EN` net.

Sources: TI **SLVSCM8D** (TPS61088 datasheet; note — the correct document number is SLVSCM8**D**, there is no SLVSF01 for this part) and the open-source **Boosty** design (Absurd Industries, GitHub `absurd-industries/boosty`, CERN-OHL-S), whose component values are a proven 5 V/5 A-from-1S instantiation of the datasheet topology. *(Boosty is a published, working open-source board built around this same chip for this same job — where the datasheet gives equations instead of numbers, this design borrows Boosty's proven numbers and says so.)*
U3 = TPS61088RHLT, VQFN-20 + thermal pad. Target: **5.1 V out, 4 A continuous / 5 A peak** from 1S. *("1S" = a single-cell lithium battery — one cell, 3.0–4.2 V.)*

> **EasyEDA note.** U3 has a real LCSC device: **C87357** (TPS61088RHLR, verified on LCSC 2026-10-21, $0.86, in stock) — pick it by that number. (This corrects an earlier claim in this doc that LCSC doesn't stock the part.) One check when you place it: confirm the device's footprint matches TI's RHL land pattern (4.5 × 3.5 mm VQFN-20; pad geometry in `hardware/FOOTPRINTS.md`). However the symbol presents them, pins 4–7 (SW) all go to the one SW net and pins 14–16 (VOUT) all go to `5V_SYS` — draw every pad; ganged pads are real connections, not spares.
>
> And L1: TI's datasheet names its recommended inductor exactly — **Cyntec PIMB065T-2R2MS** (2.2 µH, Isat 12 A, DCR ≤ 12.5 mΩ) — search that string in the library. Its body is 7.4 × 6.8 mm, a bit larger than the "~6.5 mm class" shorthand in the pin table below, so the footprint follows whichever inductor is frozen at BOM time.

| Pin | Name | Connection | Notes / source |
|---|---|---|---|
| 9 | VIN | Net `VSYS`; **C301/C302/C303 = 3 × 22 µF** X5R (≥10 V) VSYS→GND + **C304 = 0.1 µF** closest to the pin (at layout time this small cap goes physically right next to the VIN pin — small bypass caps only work up close) | Boosty BOM (input bulk) + DS §8.2.2.6 (0.1 µF bypass closest to VIN; ≥10 µF effective input capacitance, §6.3) |
| 4–7 | SW | Switch node → **L1** → VIN node | L1 = **2.2 µH** (µH = microhenries, the unit of inductance), Isat ≥ 12 A (Cyntec PIMB065T-2R2M class, per Boosty BOM / DS Table 8-2). Keep this loop physically tiny — see placement rules |
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

*Plain terms for the pins that need it:*
- **VIN / VOUT capacitors.** A boost converter draws current in hard pulses, so both its input and its output get a **bank of three 22 µF bulk capacitors** in parallel (3 × 22 µF = 66 µF total per side) to absorb the pulses, plus the one small 0.1 µF (C304) right at the VIN pin for the fastest spikes. "X5R (≥10 V)" is the capacitor type and its minimum voltage rating — VSYS and 5V_SYS never exceed ~5.2 V, so 10 V-rated parts have comfortable margin. In the schematic, all six 22 µF caps are just `Device:C` from their net to GND.
- **SW (pins 4–7) and L1.** SW is the switching node — the violent, fast-moving heart of the converter. Four pins are ganged together because the currents are large. The inductor L1 (2.2 µH, must survive ≥ 12 A without saturating — that's "Isat") connects SW back to the VIN node. The path VIN → L1 → SW → chip is "the SW loop": at layout it must be a tiny, tight loop of copper (Part D, rule 1). In the schematic it's just: SW pins wired to L1, L1 wired to `VSYS`.
- **BOOT (pin 8).** "Bootstrap" capacitor — a 0.1 µF cap between BOOT and the SW node that the chip uses to power its own internal high-side switch driver. Draw it exactly as the table says: C305 from pin 8 to the SW net (not to ground!).
- **VCC (pin 1)** is an *output* of the chip's internal regulator — capacitor only (C309 to AGND), never connect a supply to it.
- **FB (pin 17)** is the feedback input — the chip's voltmeter. It watches the middle of the R301/R302 divider and adjusts its switching until the middle sits at exactly 1.204 V; with 182 kΩ over 56 kΩ, that works out to 5.117 V at the output. "E96" is the precision resistor series the value 182 kΩ comes from (use a 1 % part). AGND here is the chip's quiet ground pin 20 — same ground plane, connected at the pad.
- **ILIM (pin 19)** sets the safety ceiling on the chip's internal switch current: R303 (100 kΩ) → ~11.9 A limit, matched to the chip's 10 A-class switch. "Cycle-by-cycle" means it enforces the limit on every single switching pulse.
- **MODE (pin 13)** chooses between two switching styles. Left unconnected (no-connect flag), the chip uses PFM — an efficient idle style that lets the output sit ~0.7 % high at very light load, which is harmless here. Do not wire it high; that mode doesn't exist.
- **FSW (pin 3)** sets the switching frequency (~600 kHz) via R304 — and note the trap the table flags: this resistor goes to the **SW node**, not to ground, unlike almost every other setting resistor on the board.
- **SS (pin 10)** is soft-start: C310 (47 nF) makes the output ramp up over ~11.3 ms instead of snapping on instantly, which is gentler on everything downstream.
- **COMP (pin 18)** is the converter's stability tuning ("compensation") — a resistor and capacitor in series to AGND: R305 then C311, in that order, then ground. The ⚠️ means these exact values come from the proven Boosty board rather than a datasheet table; what you do about it: draw them as written, and on the first prototype the design gets a load-step test (suddenly change the load and watch the output for ringing) to confirm stability. Nothing to decide now.
- **NC pins 11/12** are marked NC by the manufacturer but the datasheet says to ground them anyway — they carry heat out of the chip. Draw them to GND. (Yes, "NC → GND" looks contradictory; here it means "no electrical function — use as extra ground/thermal connection".)

**SW1 — power switch:** slide switch, common → `PWR_EN`, ON throw → `VSYS`, OFF throw → open (U3's internal pull-down holds EN low). SW1 carries only EN-pin current (µA) — any small SMD slide switch works; it never carries load current (DESIGN.md §5.2 "off" semantics). Rate it ≥ 100 mA for mechanical margin anyway.

*Plain terms:* the switch is a signal, not a gate for the actual power — only microamps flow through it. In the ON position it connects `PWR_EN` to `VSYS` (a high signal → boost on). In the OFF position it connects `PWR_EN` to nothing, and U3's own internal ~800 kΩ pull-down drags EN to ground (boost off, guaranteed). "Throw" = one of the switch's contact positions; "common" = the moving contact. In KiCad, draw a generic SPDT switch symbol: common to `PWR_EN`, one throw to `VSYS`, the other throw left unconnected (no-connect flag).

**Placement (this is the layout-critical IC — DS §10.1: "Minimize the length and area of all traces connected to the SW pin"):** L1 and C301–C304 within 5 mm of the VIN/SW pins (DESIGN.md §6.3); SW-node copper as small as connectivity allows, over the solid L2 ground; thermal vias under the EP; keep FB/COMP/SS components on the quiet side of the package, away from the SW node; the whole boost cluster sits close to the battery/charger edge so the high-current VSYS path (battery → U1 OUT → U3 VIN) is short and wide. *(All layout instructions — for PCB time. The one thing worth remembering now: the SW node is electrically noisy, and the FB/COMP/SS parts are the quiet, sensitive ones — they end up on opposite sides of the chip.)*

---

## 4. 3.3 V buck — SY8089AAAC (U4)

**What this section does.** A **buck converter** is the boost's mirror image: it steps voltage *down*. U4 takes `5V_SYS` (5.1 V) and makes the clean, regulated `3V3` rail (3.3 V, up to 2 A) that powers the ESP32, both radios, the NFC chip and the microSD slot. It runs *from the boost's output*, not from the battery — so when the power switch kills the boost, the whole 3.3 V world dies with it. That is deliberate: power switch off = ESP32 off.

**What you draw.** The U4 symbol (5 pins, SOT-23-5 — a tiny 5-legged package). One 22 µF cap on IN; the inductor L401 from the LX pin to the `3V3` net; two 22 µF caps on the output; the two-resistor feedback divider + a small 22 pF cap on FB; and EN wired straight to `5V_SYS` with a big pull-down resistor to GND.

Source: Silergy **AN_SY8089/A Rev. 0.9A** (the SY8089/SY8089A datasheet; LCSC lists C78988 as "Output Type: Adjustable").
U4 = SY8089AAAC, SOT-23-5. **Confirmed: this variant is adjustable** (V_REF = 0.6 V typ) with hiccup short-circuit protection — it is not a fixed-output part, and no fixed variant is listed in the datasheet. Input = `5V_SYS` (fed from the boost, **not** from the battery — DESIGN.md §2.6), output 3.3 V / 2 A, f_SW = 1 MHz. *("Adjustable" = the output voltage is set by an external resistor divider, as opposed to a fixed-output variant that makes one preset voltage. "Hiccup" protection = when shorted, the chip pulses on briefly, gives up, waits, retries — instead of cooking itself. f_SW = its switching frequency, 1 MHz.)*

| Pin | Name | Connection | Notes / source |
|---|---|---|---|
| 4 | IN | `5V_SYS`; **C401 = 22 µF** IN→GND at the pin | DS pin description demands ≥ 10 µF ceramic at IN; Fig. 1 uses 22 µF; Applications recommends X5R-or-better, > 6.3 V rating, paralleled parts at 2 A — one 22 µF 10 V X5R 0805/1206 meets this at our operating point (DS p.2, p.7–8) |
| 3 | LX | → **L401 = 2.2 µH** → net `3V3` | DS Fig. 1 value. Check (CALC, DS p.7 formula): L_min ≈ 3.3 × (1 − 3.3/5.1) / (1 MHz × 2 A × 0.4) ≈ 1.46 µH → 2.2 µH is conservative (ripple ≈ 0.53 A). Inductor Isat must exceed ≈ 2.3 A peak; DCR < 50 mΩ desirable (DS p.8) |
| — | OUT | **C402/C403 = 2 × 22 µF** X5R (≥6.3 V; use 10 V) `3V3`→GND at L401's output | DS Fig. 1 (2 × 22 µF) / Applications: output capacitance > 22 µF, X5R or better |
| 5 | FB | Divider: **R401 = 453 kΩ** (3V3→FB), **R402 = 100 kΩ** (FB→GND); **C404 = 22 pF** across R401 | **(CALC)** V_OUT = 0.6 × (1 + R1/R2) (DS p.2). R1 = 100 kΩ × (3.3/0.6 − 1) = 450 kΩ → nearest E96 **453 kΩ** → V_OUT = 0.6 × (1 + 4.53) = **3.318 V** (+0.55 %). Resistor range 10 kΩ–1 MΩ per DS. C404 is the DS Fig. 1 feedforward capacitor (22 pF) for transient response (DS p.8) |
| 1 | EN | → `5V_SYS`; **R403 = 1 MΩ** EN→GND | Sequencing by construction: the buck can only start once the boost has brought 5V_SYS up (DESIGN.md §5.1: "SY8089 EN slaved to 5V_SYS"). EN rising threshold 1.5 V / falling 0.4 V, abs-max V_IN + 0.6 V (DS p.2, p.4) — tying EN to the 5.1 V input rail is within rating (inference from the abs-max table; the DS does not print an explicit "may tie to IN" sentence). EN must not float (DS p.2); R403 is the DS p.8-recommended pull-down against false turn-on |
| 2 | GND | GND | |

*Plain terms:* LX (pin 3) is this converter's switching node — same idea as U3's SW, smaller currents. L401 sits between LX and the output net; C402/C403 are the output bulk caps at the far end of the inductor ("at L401's output" = on the `3V3` side of the inductor, not the chip side). "Isat > 2.3 A" means the inductor must not saturate below ~2.3 A; "DCR < 50 mΩ" means its winding resistance should be under 50 milliohms so it doesn't waste power as heat. The FB divider works exactly like U3's — the chip holds FB at 0.6 V, the 453 kΩ/100 kΩ ratio turns that into 3.318 V out (the +0.55 % is well within what 3.3 V parts accept). C404 (22 pF) is wired *across* R401 — one end on the `3V3` side, the other end on the FB pin — that's the feedforward capacitor from the glossary. EN is wired directly to `5V_SYS` so the buck starts automatically the moment the boost is up ("slaved"); R403 (1 MΩ to GND) just guarantees EN reads a firm "off" before that, instead of floating. The note in the EN row is an honest caveat, not an action item: tying EN to the input rail is inside the pin's voltage rating per the datasheet's own limits table, even though the datasheet never prints a sentence explicitly blessing it.

**Placement:** C401 tight to pin 4; L401 and C402/C403 tight to pin 3 (LX loop small); FB divider + C404 close to pin 5, away from the LX node. Fed from 5V_SYS means the whole 3V3 domain (ESP32, radios, PN532, SD) dies cleanly with the power switch — "device off = ESP32 off" (DESIGN.md §2.6). *(Layout notes, as usual — "LX loop small" means the pin 3 → L401 → output caps → ground loop is kept physically tiny.)*

---

## 5. ESP32-S3 coprocessor — ESP32-S3-WROOM-1U-N16R8 (U5) + USB

**What this section does.** U5 is the second brain of Loki: the ESP32-S3 module that runs the radios (Bluetooth, sub-GHz, 2.4 GHz, NFC, IR) while the Pi runs the main show. This section wires its lifelines: power, the reset/boot-strap pins the Pi uses to control it, the UART (serial link) to the Pi, the attention-interrupt line back to the Pi, the native USB pins, and the fan-out of its GPIOs to the radios. Most rows in the table below are "this GPIO goes to that subsystem" — the actual parts for those subsystems live in their own sections (§6–§10); the only *components* in this section are the pull-ups, series resistors and capacitors around the module itself.

**What you draw.** The U5 module symbol (Espressif's own KiCad library has it — see FOOTPRINTS.md); two power caps on its 3V3 pin; on EN: a pull-up, a 1 µF cap, and a 1 kΩ series resistor to a Pi header pin; the same pull-up + series pair on IO0; a 499 Ω series resistor on the UART TX line, a plain wire for RX; a pull-up on the IO42 attention line; 0 Ω series resistors on the two USB data lines (they run to U10 in §5.1); a two-resistor divider + cap for USB VBUS detection on IO21; and two 4.7 kΩ pull-ups for the ESP32's own I²C bus. Everything else is a wire from a module pad to another section's net.

Sources: Espressif **ESP32-S3-WROOM-1U Datasheet** (the U variant's own document; its pin functions are identical to the WROOM-1's, cited "Module DS") and **ESP32-S3 Hardware Design Guidelines** (cited "HDG"). Connections are named by GPIO (module pads are labelled by GPIO); module pin numbers are given where verified.

> **⚠️ EasyEDA note — the module is the U.FL variant now, and its LCSC number is verified.** U5 = **ESP32-S3-WROOM-1U-N16R8, LCSC C3013946 ✅** (verified on its LCSC product page 2026-10-22: $5.22, 19,173 in stock, module body 19.2 × 18 mm). The "U" is the whole point: no PCB antenna — a U.FL connector feeds an external antenna instead (decision D12, 2026-10-22). Traps in the picker: the plain **WROOM-1-N16R8** (PCB antenna — the pre-D12 part, no longer used), the other 1U memory variants (N16**R2** = only 2 MB PSRAM — not enough for Bruce; N8R8 = only 8 MB flash), the **MINI-1 / MINI-1U** modules (the C2913202 number in older project documents belongs to the MINI-1), and the **bare ESP32-S3 chip** (C2913192). Pick by C3013946, or by the full name with "WROOM-1U", "16 MB flash", "8 MB PSRAM" all confirmed.

| Module pad | Connection | Notes / source |
|---|---|---|
| 3V3 (pin 2 — the module's only power pin) | Net `3V3`; **C501 = 22 µF** + **C502 = 0.1 µF** at the pin | Module DS §6 Fig. 7 typical circuit: 22 µF + 0.1 µF per module. (The often-quoted 10 µF figure is the *bare-chip* rule — the WROOM-1 takes 22 µF.) Supply must deliver ≥ 500 mA (HDG); our 2 A buck has > 2× headroom over the module's ~0.35 A TX peaks (DESIGN.md §4.1) |
| GND (pins 1, 40, EPAD 41) | GND | |
| EN (pin 3) | **R501 = 10 kΩ** pull-up → 3V3; **C503 = 1 µF** EN→GND; net `ESP_EN` ← Pi header pin 37 (GPIO26) via **R502 = 1 kΩ** series | RC per Module DS §6 note + HDG (R = 10 kΩ, C = 1 µF typical; rails must be stable ≥ 50 µs before EN rises). The 1 kΩ series is DESIGN.md §3.1 (limits clamp backfeed; the Pi can reset/reflash the ESP32). The source pin is 37 (GPIO26), not 11 (GPIO17), since 2026-10-20: GPIO17 is the touch display's TP_IRQ — see §3.1 pin 11 |
| IO0 (pin 27) | **R503 = 10 kΩ** pull-up → 3V3; ← Pi header pin 13 (GPIO27) via **R504 = 1 kΩ** series | Boot strap. HDG says "fit a pull-up" without a value and warns against large capacitors on IO0 — 10 kΩ is the value in DESIGN.md §3.2 and Espressif's reference designs (⚠️ the guidelines text itself states no number). No capacitor on this net |
| IO43 / U0TXD (pin 37) | → Pi header pin 10 (GPIO15), via **R505 = 499 Ω** series at the module | HDG recommends a 499 Ω series resistor on U0TXD (harmonic suppression). Protocol UART, 115200 8N1 (DESIGN.md §3.1) |
| IO44 / U0RXD (pin 36) | ← Pi header pin 8 (GPIO14) | Direct |
| IO42 | → Pi header pin 15 (GPIO22), net `ESP_IRQ`; **R506 = 10 kΩ** pull-up → 3V3 on the HAT | Attention line, open-drain style (ESP32 drives low / releases) per DESIGN.md §3.2. The HAT-side pull-up (EC) keeps the net defined before Pi firmware configures GPIO22 |
| IO19 / USB_D− (pin 13) | → **R507 = 0 Ω** → U10 (§5.1) → J2 D− | Native USB. HDG reserves 22 Ω/33 Ω series + DNP shunt caps near the chip; the module's own typical circuit uses 0 Ω (Module DS §6 Fig. 7). Fit 0 Ω footprints; swap to 22 Ω only if signal integrity demands. 90 Ω ±10 % differential pair, length-matched, unbroken ground beneath (HDG) |
| IO20 / USB_D+ (pin 14) | → **R508 = 0 Ω** → U10 → J2 D+ | As above |
| IO21 | VBUS detect ← divider **R509 = 100 kΩ / R510 = 100 kΩ** from J2 VBUS (net `USB1_VBUS`); **C504 = 0.1 µF** at IO21 | Divider per DESIGN.md §3.2 (USB present → ≈2.5 V at IO21). C504 is an (EC) noise/debounce addition |
| IO11 (MOSI), IO12 (SCK), IO13 (MISO) | Shared SPI2 bus → U6, U7, SD1 (§6, §7, §9) | Per-device CS and SPI settings; see DESIGN.md §3.2 bus-sharing note |
| IO8 (SDA), IO18 (SCL) | ESP32 I²C bus → PN532 module via J8 (§8); pull-ups **R513/R514 = 4.7 kΩ** → 3V3 | Separate bus from the Pi's I²C1 (§2.2). 4.7 kΩ (EC, standard I²C value for a short bus) |
| IO15, IO16, IO38, IO39 | Spare — unassigned | Were the button nets (§11.4) until 2026-10-19; the touch display replaced the buttons |
| IO4, IO5, IO6 | U7 nRF24 CE / CSN / IRQ (§7) | |
| IO10, IO9, IO17 | U6 CC1101 CS / GDO0 / GDO2 (§6) | |
| IO14, IO7 | SD1 CS / card-detect (§9) | |
| IO40, IO41 | PN532 module IRQ / RSTPDN via J8 (§8) | |
| IO3, IO47, IO48 | Test pads only | IO3 is a strapping pin (JTAG source) — do not load it (DESIGN.md §3.2). IO45/IO46 stay unconnected (strapping); IO26–32 and IO33–37 do not exist as usable pads (flash/PSRAM) |

*Plain terms for the patterns in this table (they repeat all over the board, so they're worth learning once):*
- **EN (pin 3)** is the ESP32's reset/enable pin: hold it low = chip held off/reset; let it rise = chip boots. R501 (10 kΩ pull-up to `3V3`) makes "let it rise" the default. C503 (1 µF to GND) slows that rise slightly so power is stable first (the resistor + capacitor pair is called an "RC" — the delay is the point). The Pi can grab the line through R502 (1 kΩ, *in series* — the Pi's wire goes Pi pin → resistor → EN net) to force a reset or reflash the ESP32. The 1 kΩ exists so that if the Pi is powered while the ESP32 side is not (or vice versa), only a trickle (< 3.3 mA) can sneak through the chips' internal protection ("clamp backfeed") instead of a damaging current.
- **IO0** is the boot-mode strap: high at reset = run normally; low at reset = enter flashing mode. Same pattern: R503 pull-up keeps it high (normal boot) by default; the Pi can pull it low through R504 when it wants to reflash the ESP32. The ⚠️ here only means Espressif's guideline says "fit a pull-up" without printing the value — 10 kΩ is what their own reference boards and our design use. Draw it as written. And note: **no capacitor on this net** — a cap here could hold the pin low during boot and break the strap.
- **Series resistors on signal lines** (R502, R504, R505) sit in the middle of a wire — signal flows through them. They cost the signal almost nothing (the receiving input draws ~no current) but they limit fault currents and, on the UART TX line (R505 = 499 Ω), smooth the signal's edges so it radiates less radio-frequency noise ("harmonic suppression").
- **IO42 / `ESP_IRQ`** is the ESP32 tapping the Pi on the shoulder ("a radio event happened", "BadUSB finished"). It's open-drain style: the ESP32 either pulls the line to ground or lets go, and R506's pull-up is what brings the line back up — without R506 the line could never read high. This is the same open-drain + pull-up pattern as §2's ALRT.
- **IO19/IO20 (USB D−/D+)** are the ESP32's built-in USB. The 0 Ω resistors (R507/R508) are placeholders that conduct like a plain wire — they're fitted so that if testing shows the USB signal needs the 22 Ω version instead, it's a part swap, not a board redesign. The "90 Ω differential pair, length-matched, unbroken ground beneath" is a layout instruction (Part D, rule 5): the two wires run together as a pair.
- **IO21 VBUS detect:** the port's VBUS (`USB1_VBUS`) is 5 V — too much for a 3.3 V GPIO. The two equal 100 kΩ resistors (R509/R510) form a divider that halves it to ≈2.5 V: VBUS → R509 → IO21 → R510 → GND. C504 (0.1 µF) on the same pin just filters noise so the reading doesn't flicker.
- **"Do not load" IO3:** IO3 is a strapping pin. It goes to a test pad only (TP section of the BOM) — a bare copper pad you can touch a probe to — and nothing else may hang on it, or the ESP32 may boot in the wrong mode. IO45/IO46 are also straps and stay fully unconnected; IO26–32 and IO33–37 don't exist as usable pads at all because they're wired inside the module to its flash memory and RAM.

**Antenna (the 1U has no on-module antenna):** the module's U.FL connector feeds a **case-mounted 2.4 GHz whip via a short U.FL→SMA pigtail** — the same arrangement as the CC1101's whip (D6), and the reason the 1U was chosen (D12). Consequences that make layout *easier* than the old PCB-antenna module: there is **no antenna keep-out zone** — the module (19.2 × 18 mm, ~6 mm shorter than the WROOM-1) can sit fully on the board, no edge overhang, copper allowed anywhere around it. Layout notes that remain: keep the coax run short and don't kink it; mount the whip on the enclosure clear of the Pi's own WiFi antenna corner in the stack (DESIGN.md §6.2); the whip and pigtail are enclosure parts, not PCB BOM lines.

### 5.1 USB data on the shared port (J2) + ESD (U10)

The connector itself (J2) is drawn in §1.1 — since the 2026-10-22 single-port merge (decision D11) there is no second connector; this section draws the data chain that hangs off J2's D+/D− stubs.

**What this section does.** This is the ESP32's USB path — what a PC talks to for BadUSB (the ESP32 pretending to be a keyboard) and for flashing the ESP32. U10 is a tiny bodyguard chip (an ESD protection part) sitting between the connector and the ESP32: if a static spark hits the port, U10 absorbs it instead of the ESP32. J2's VBUS feeds the charger (§1) and is *also* sensed here (§5, IO21) so the ESP32 knows something is plugged in — note the divider is a sense only; the board never powers itself *from* the ESP32's side of that wire, and 5V_SYS is never back-fed from a PC.

| J2 terminal / net | Connection |
|---|---|
| D− / D+ (stubs from §1.1) | → U10 I/O pins → R507/R508 → U5 IO19/IO20 (§5). BadUSB HID + flashing only (decision D10) |
| VBUS (net `USB1_VBUS`) | → R509/R510 divider → IO21 (§5). On this page VBUS is a host-presence sense only |
| CC1 / CC2 | R105/R106, already drawn in §1.1 — the one Rd pair serves both the charger and the ESP32's device role. (The merge deleted the second Rd pair, ex-R511/R512) |

U10 = ST USBLC6-2SC6 (SOT-23-6), **LCSC C7519 ✅** (verified on its LCSC product page 2026-10-22: genuine ST part, SOT-23-6L package, $0.09, in stock). Flow-through pin map: pin 1 = I/O1 in (J2 side), pin 6 = I/O1 out (U5 side); pin 3 = I/O2 in (J2 side), pin 4 = I/O2 out (U5 side); pin 5 (VBUS) → `USB1_VBUS`, pin 2 → GND. Wire D− through the pin 1→6 channel and D+ through pin 3→4 (the two channels are identical, so the pairing is a convention — just don't cross them). Place U10 immediately behind J2, before any stub or via on the D+/D− pair.

*Plain terms:* "Flow-through" means the signal enters one side of U10 and exits the opposite side — connector side in, ESP32 side out — so at layout time the USB pair runs in a straight line: connector → U10 → series resistors → module, with no branches (stubs) and no layer-hopping vias before the protection chip. The ⚠️ VERIFY means: USBLC6 parts come in several ordering variants, and before ordering (BOM freeze) the exact variant's pin numbering gets checked against ST's datasheet so pin 5 really is VBUS and pin 2 really is GND on the part we buy. Draw it per the description above now; the check is a pre-order checklist item, not a drawing blocker.

---

## 6. Sub-GHz radio — EBYTE E07-900M10S CC1101 module (U6)

**What this section does.** U6 is the sub-GHz radio module — the 868/915 MHz radio used for things like remote controls, sensors and car key fobs (a 433 MHz variant of the same module fits the same footprint for other regions). It's a ready-made module: the radio chip, its crystal and its matching components are already inside, so this section is mostly wires: power + two capacitors, the shared SPI bus, two interrupt wires, a bank of ground pads, and the antenna connection.

**What you draw.** The module symbol (22 pads); C601 + C602 on the VCC pad; nine pads wired straight to GND; five pads flagged no-connect; four SPI wires and two GDO wires to the ESP32 pins listed; and a 0 Ω resistor (R601) from the ANT pad to the U.FL antenna connector J7.

Source: EBYTE **E07-900M10S User Manual v1.0** (cited "E07 manual"). Module = TI CC1101 + integrated crystal/matching, 14 × 20 mm stamp-hole SMD, 22 pads. (433 MHz builds fit the pin-compatible E07-400M10S instead — decision D2.) *("Stamp-hole" = the module solders down by half-circle notches around its edges — the pads in the table are those notches. The module is 14 × 20 mm.)*

> **EasyEDA note.** The E07 module is not standard LCSC stock. Search EasyEDA's library (including user-contributed parts) for `E07-900M10S`; if you draw it yourself, the 22-pin table below is the symbol, and FOOTPRINTS.md has the pad layout. Pin functions are datasheet-confirmed; pad size and pin-1 orientation were never verified against a physical module — caliper one before ordering boards.

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

*Plain terms:* The capacitor pair on VCC is the standard recipe from the glossary — C602 (10 µF) is the bulk reservoir, C601 (0.1 µF) is the small fast bypass; the "(EC)" tag and the quoted manual line mean EBYTE demands *a* capacitor there but never says which, so the design uses the standard pair (Part E, item 10 keeps this on the double-check list). All nine GND pads really do all get wired to ground — they're the radio's return path, and RF parts misbehave if you skimp on grounds. CSN is this module's SPI chip-select (the ESP32 pulls it low to talk to this module); SCK/MOSI/MISO are the shared SPI bus wires (§5). GDO0/GDO2 are the module's two programmable signal-out pins — here they report "packet received/sent" and "carrier present" back to the ESP32 as interrupts. The ANT pad goes through a 0 Ω resistor (R601 — a wire-like jumper resistor) to J7, the tiny U.FL snap-on coax connector; a thin coax **pigtail** (a short cable with a connector on one end and an antenna fitting on the other) runs from J7 to the SMA whip antenna on the case. The alternative spring antenna (a little coil that solders straight to the board) shares the same node after R601, and is **DNP** — its footprint exists, but in the standard build you fit the whip path only, never both ("fit exactly one path").

Supply range note: the E07 manual contradicts itself (1.8–3.6 V in §2.2 vs 3.0–3.6 V at the pin-9 definition). Design target is our regulated 3.3 V, which satisfies every stated range (⚠️ flagged in sources). *(Nothing to do: 3.3 V is inside both versions of the spec, so the contradiction is harmless — it's recorded so nobody "discovers" it later and worries. Part E, item 11.)*

**Placement:** opposite board corner from the ESP32 antenna (DESIGN.md §6.4); J7 at the case edge; keep the ANT pad and the trace to J7 clear of the display header's ground pins and any digital copper — 50 Ω controlled run, as short as possible. *(Layout notes. "50 Ω controlled run" means the antenna trace is drawn with a specific width so its electrical impedance is 50 Ω, matching the antenna system — the layout tool/your design rules handle the width; what matters now is: short and direct.)*

---

## 7. 2.4 GHz radio — EBYTE E01-ML01SP4 nRF24L01+ PA/LNA module (U7)

**What this section does.** U7 is the 2.4 GHz radio module (nRF24-based — the radio in a lot of wireless mice, and famously in Flipper-Zero-style add-ons for keyboard/mouse jamming research and wireless-device sniffing). "PA/LNA" means it has a power amplifier (PA) to transmit stronger (+20 dBm) and a low-noise amplifier (LNA) to hear weaker signals — which is why it can gulp 120 mA in bursts and needs a bigger reservoir capacitor than U6. Its antenna is a tiny IPEX snap connector on the module itself.

**What you draw.** The module symbol (10 pads); C701 + C702 on VCC; three pads to GND; SPI wires plus CE, CSN and IRQ to the ESP32. And read the warning above the table twice: **this module's pad order is not the order used by the common breakout boards** — wire it by the table, not by habit.

Sources: EBYTE **E01-ML01SP4 Datasheet V1.0** + **E01 User Manual** (cited "E01 manual"). ⚠️ **This SMD module's pin order is NOT the common 8-pin DIP nRF24 order** — it is a 10-pad SMD part; wire it exactly as below. Antenna = onboard IPEX, 50 Ω (§8 of the E01 manual; generation — MHF1/U.FL class — not specified by EBYTE ⚠️). *(The ⚠️ on the antenna connector means EBYTE doesn't state which micro-coax connector generation it is (MHF1 vs U.FL — near-identical snap connectors that are *mostly* intermateable). What to do: when the modules are ordered, confirm the connector on the actual part against the pigtail/whip being bought. Nothing to change in the schematic.)*

> **EasyEDA note.** Same story as §6: search the library (including user-contributed) for `E01-ML01SP4`; the 10-pin table below is the symbol if you draw it, and FOOTPRINTS.md has the pads. Same caliper-before-ordering caution applies.

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

*Plain terms:* CE is the module's "radio enable" (high = radio awake and listening; it also switches on the receive amplifier). CSN is its SPI chip-select; IRQ is its interrupt wire ("something happened — packet received"). The VCC note's ⚠️ is the same situation as U6: EBYTE specifies no capacitor values (their ⚠️-marked guidance is a π-filter — a filter shaped like the letter π: cap, then series element, then cap — plus "give it current headroom"), so the design fits the standard 10 µF bulk + 0.1 µF bypass pair on a 2 A rail, which covers the 120 mA transmit bursts with big margin. The sentence about "~115 mA" is there so nobody "corrects" the design from a marketplace listing — the 110/120/130 mA figures are EBYTE's own. (Part E, items 12–13 keep both EBYTE ⚠️s on the double-check list.)

**Placement:** away from the ESP32 antenna (both live at 2.4 GHz — DESIGN.md §2.10); IPEX whip dressed inside the case; keep the module's ground pads stitched to the plane (PA return current is the pulsed 120 mA). *(Layout notes. "Stitched to the plane" = connected down into the ground layer with vias. "Whip dressed inside the case" = the little antenna wire is routed neatly inside the enclosure.)*

---

## 8. NFC / RFID — external PN532 module on header J8

**What this section does.** NFC/RFID — reading and emulating 13.56 MHz cards and tags (door badges, transit cards, Amiibo-class NFC) — no longer lives on this board. The original design carried a **bare PN532 chip** here: some 25 parts (the chip, a crystal, an unusual power-wiring set, and a hand-tuned antenna network) including the BOM's only component with **no LCSC listing at all** — a JLC sourcing gamble on every kit run — and antenna values that could only be finalised by bench-tuning a prototype. **Decision (2026-10-18, supersedes D1):** the PN532 moves off-board onto a standard, builder-sourced **PN532 I2C module** (the common Elechouse-type board) that plugs into a dedicated 6-pin header, **J8**. The module brings its own factory-tuned antenna. Electrically nothing changes for the ESP32 or the firmware: same I2C bus, same fixed address **0x24**, same four ESP32 pins as the bare chip used — the Bruce fork cannot tell the difference. This board now carries just the header and six wires.

**What you draw.** One 1×6 pin-header symbol and six short wires landing on net labels you already placed in §5. This is the shortest section on the board. (The refdes **J8 is reused**: it used to be the NFC antenna's U.FL connector, deleted with the bare chip. If you ever drew the old §8, delete U8, Y1, C801–C817, L801/L802 and R801–R804 — they no longer exist.)

J8 = 1 × 6, 2.54 mm pin header (through-hole). KiCad symbol: search `Conn_01x06` in **Connector_Generic**; footprint `Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical`.

| J8 pin | Signal | Connection |
|---|---|---|
| 1 | GND | GND |
| 2 | 3V3 | Net `3V3` — module power (the PN532's field draw is already in the 3V3 rail budget, DESIGN.md §4) |
| 3 | SCL | Net `ESP_SCL` (ESP32 IO18) |
| 4 | SDA | Net `ESP_SDA` (ESP32 IO8) |
| 5 | RST | Net `PN532_RST` (ESP32 IO41) |
| 6 | IRQ | Net `PN532_IRQ` (ESP32 IO40) |

*Plain terms:* the pin order is ours, chosen so power sits at one end and the I2C pair (SCL/SDA — the two wires the ESP32 talks over) travels together. **Module pin orders vary by vendor**, so the silkscreen prints the signal name beside every J8 pin and the build-guide rule is *match names, not positions* — most modules ship with a 6-wire cable that lands each wire on its named pin, and a module whose order happens to match can plug straight in. Two builder notes for the guide: (1) most PN532 modules leave the factory switched to UART or SPI — the module's mode switches/jumpers must be set to **I2C** (its address is fixed at 0x24, nothing to configure); (2) some modules carry their own I2C pull-up resistors — harmless here, they simply parallel this board's R513/R514 (§5), which stay fitted so the bus is well-defined even with no module plugged in.

**Placement:** J8 on a board edge, clear of the U6/U7 antenna zones; keep the ESP_SCL/ESP_SDA run short and away from the boost converter's SW node. Everything RF about NFC — chip, crystal, matching network, antenna — now lives on the module, on the far side of this connector.

---
## 9. microSD slot (SD1)

**What this section does.** SD1 is the microSD card slot — removable storage the ESP32 uses (for Bruce firmware files, captured data, BadUSB payloads). The card talks SPI (the same shared bus as the two radios, with its own chip-select wire), and a card-detect contact tells the ESP32 whether a card is physically inserted.

**What you draw.** The SD1 slot symbol; two power caps at its VDD contact; three wires to the shared SPI bus plus CS to IO14; a 10 kΩ pull-up resistor on each of CMD, DAT0 and the card-detect contact; and no-connect flags on DAT1/DAT2.

SD1 = **Hirose DM3D-SF** microSD slot (JLC **C719027**, ~$1.16 as an extended part) — push-pull: push the card in, pull it out; no click-eject spring. Decided 2026-10-19, replacing the earlier generic push-push slot (LCSC C91145/C112217), whose footprint could never be identified. SPI mode on the ESP32's shared SPI2 bus (DESIGN.md §2.8, decision D5). *("TF" is the old name for microSD. "Push-pull" means you push the card in and pull it straight back out — no spring eject like the push-push ballpoint-pen mechanism. A microSD card can speak two protocols; this design uses its slower-but-simple SPI mode, not the fast 4-bit SD mode, because the ESP32 shares the bus with the radios.)*

> **EasyEDA note.** SD1's LCSC number **C719027 was verified on JLCPCB's own page on 2026-10-21** (the listing even names its EasyEDA library), so search that C-number first — but verify any footprint you find against Hirose's land pattern before trusting it: pad 9 is the card-detect switch A (→ the CD net), pad 10 is switch B (→ GND), pin 1 sits at the +X end. The full pad-coordinate table for redrawing it exactly is in `hardware/kicad/dm3d-sf-footprint-notes.md`.

| Slot contact | Connection |
|---|---|
| VDD | Net `3V3`; **C901 = 0.1 µF** + **C902 = 10 µF** at the slot (EC — standard card-edge practice) |
| VSS | GND |
| CLK | ← ESP32 IO12 |
| CMD (MOSI) | ← ESP32 IO11; **R901 = 10 kΩ** pull-up → 3V3 (the SD specification requires pull-ups on CMD and DAT lines in SPI mode) |
| DAT0 (MISO) | → ESP32 IO13; **R902 = 10 kΩ** pull-up → 3V3 |
| DAT3 (CS) | ← ESP32 IO14 |
| DAT1, DAT2 | No connect (unused in SPI mode) |
| CD (card-detect switch) | The DM3D-SF has a dedicated detection switch with two terminals, A and B: **A → ESP32 IO7** with **R903 = 10 kΩ** pull-up → 3V3; **B → GND**. Per the Hirose DM3 datasheet the switch is open with no card and **closes when a card is inserted** — so inserting a card pulls CD to ground (card present = IO7 reads low), exactly what this design assumed. (JLC's listing claims this part has no detection pins — the manufacturer's datasheet says otherwise, and the datasheet wins.) |

*Plain terms:* the contact names are the card's own pin names — in SPI mode, CMD carries data *to* the card (it's the MOSI wire), DAT0 carries data *back* (MISO), and DAT3 works as the chip-select. DAT1/DAT2 are only used in 4-bit SD mode, so here they're no-connects. The pull-ups on CMD/DAT0 aren't our whim — the SD card specification requires them in SPI mode (they're what the lines rest against between transfers). The CD (card-detect) contact is a tiny switch built into the slot. On the DM3D-SF that switch is a separate two-terminal contact (A and B) that is open normally and closes when a card is pushed in (Hirose DM3 datasheet — so the polarity this design assumed is confirmed, not guessed: B goes to ground, A is the CD line, R903 pulls it up to 3.3 V, and a card present reads as ground on ESP32 IO7). This was Part E, item 14 — resolved 2026-10-19 when the DM3D-SF was chosen.

No series damping resistors are fitted on the SD lines: Espressif's reference designs wire SD slots directly, and our runs are short. If proto testing shows ringing-related card errors, 33 Ω series pads near the slot are the rev-2 fix (note, not fitted). *("Series damping resistors" would be small resistors in each data wire to calm electrical ringing — deliberately omitted here; this sentence records that it was considered and why it's a prototype-stage decision, not an oversight.)*

**Placement:** on the case edge — the card must be insertable without opening the enclosure (DESIGN.md §6.8). *(Layout/packaging note: the slot's opening ends up flush with the case wall.)*

---

## 10. Infrared — TSOP38438 RX (U11) + 940 nm TX (D1/Q1)

**What this section does.** This is Loki's infrared eye and voice — the same technology as a TV remote. U11 (the TSOP38438) *receives* 38 kHz modulated IR (remote-control signals), and the D1/Q1 pair *transmits*: D1 is an infrared LED (940 nm — invisible to the eye) and Q1 is the transistor that switches its current, because the LED wants ~100 mA pulses and no ESP32 pin can supply that directly.

**What you draw.** For the receiver: U11 with its 3 pins — a 100 Ω resistor feeding its VS pin from `3V3`, a 1 µF cap beside it, GND, and its OUT wire straight to ESP32 IO1. For the transmitter: ESP32 IO2 → 1 kΩ resistor → Q1's base; Q1's emitter to GND; Q1's collector to D1's cathode; D1's anode → 18 Ω resistor → `3V3`.

Sources: Vishay **TSOP382../TSOP384.. datasheet, Doc. 82491** (Rev. 2.1 current; Rev. 1.0 for the filter-component range).

### 10.1 Receiver — ⚠️ through-hole part (see erratum 3)

U11 = TSOP38438, Minicast **leaded** package. Pin order for THIS series: **1 = OUT, 2 = GND, 3 = VS** (sibling series swap VS/GND — do not cross-wire).

*Plain terms:* "Leaded" = it has three wire legs (through-hole — the part from erratum 3). The pin-order warning is real and worth heeding: Vishay makes near-identical receivers whose legs are in a different order, so when you place the U11 symbol, check its pins read 1 = OUT, 2 = GND, 3 = VS in that order — if a symbol you find has them swapped, fix the symbol, don't wire around it.

> **EasyEDA note.** U11's project-recorded LCSC number is C145271 (picker-confirm it — it could not be re-checked on an LCSC page in 2026-10-21's pass); a library device should exist under `TSOP38438`. It's through-hole (three legs, 2.54 mm pitch) in a surface-mount world — if you have to draw the footprint, §10.1 and FOOTPRINTS.md have what you need.

| Pin | Connection |
|---|---|
| 3 (VS) | ← **R1001 = 100 Ω** ← net `3V3`; **C1001 = 1 µF** VS→GND at the device. The series-R + shunt-C supply filter is Vishay's application circuit (diagram 17170): Rev. 1.0 gives the ranges **33 Ω < R1 < 1 kΩ** and **C1 > 0.1 µF** — 100 Ω and 1 µF sit inside both. (The often-quoted "100 Ω + 0.1 µF" pair comes from *other* Vishay families' datasheets; 0.1 µF does not satisfy this family's "> 0.1 µF") |
| 2 (GND) | GND |
| 1 (OUT) | → ESP32 IO1, direct. OUT has an **internal 30 kΩ pull-up** and is specified to connect straight to a microprocessor — no external pull-up (Vishay DS block diagram). Active-low: high = no carrier, low during a received 38 kHz burst |

*Plain terms:* VS is the receiver's power pin, and it gets its power through a little filter: R1001 (100 Ω, in series) then C1001 (1 µF, from VS down to ground) — the resistor + capacitor smooth out supply noise, which IR receivers are notoriously sensitive to (noise on VS turns into phantom remote signals). Vishay's own application circuit specifies exactly this arrangement, with allowed ranges; our values sit inside them. Note the trap the table flags: a lot of hobby write-ups use 0.1 µF for the cap, but that value belongs to *other* receiver families — this one requires *more than* 0.1 µF, hence 1 µF. OUT is the signal: it has its own 30 kΩ pull-up built inside the part, so it wires straight to IO1 with no resistor, and it idles high, dropping low for each burst of 38 kHz it sees.

Supply: 2.0–5.5 V (Rev. 2.1) — our 3.3 V is mid-range; draw ≈ 0.35 mA.

**Placement:** at the case edge with an unobstructed view out (IR window in the enclosure); keep it away from D1's direct blast (a few mm of separation and the case's internal wall do the job) and away from the boost's SW node noise. *(Layout notes — the receiver needs line-of-sight out of the case, and shouldn't stare straight into our own IR LED from point-blank.)*

### 10.2 Transmitter

ESP32 IO2 → **R1003 = 1 kΩ** → Q1 base. Q1 = MMBT2222A (SOT-23: pin 1 = B, 2 = E, 3 = C); emitter → GND; collector → D1 cathode. D1 anode → **R1002 = 18 Ω** → net `3V3`. D1 = 940 nm SMD IR LED, 1206 (VSMB10940 class; LCSC ⚠️ confirm at BOM freeze).

*Plain terms:* this is the standard one-transistor LED driver. IO2 can't power the LED, so it just whispers to Q1's base through R1003 (1 kΩ limits that whisper to 2.6 mA), and Q1 — switched on by the whisper — connects the LED's cathode to ground, letting ~100 mA flow from `3V3` through R1002 (the LED's current-limiting resistor, 18 Ω) and the LED. "B / E / C" = base / emitter / collector, the transistor's three legs; pin numbers are given so the symbol can't be wired backwards. The generic KiCad symbol is `Device:Q_NPN_BCE` (see FOOTPRINTS.md). The ⚠️ on D1 means the exact IR LED part gets picked at BOM freeze — and item 16 in Part E notes that if the chosen LED's forward voltage differs from the assumed 1.35 V, R1002's value gets re-trimmed (recalculated) to match. Draw 18 Ω now.

**(CALC)** Target I_F ≈ 100 mA pulsed (DESIGN.md §2.5; the LED is driven from the transistor, never from the GPIO):
- Base current: (3.3 − 0.7) / 1000 = **2.6 mA** from IO2 — comfortable for the GPIO; forced β at the collector ≈ 100/2.6 ≈ 38, so allow V_CE(sat) ≈ 0.2 V. *(β (beta) = the transistor's current multiplication; "forced β ≈ 38" means we're deliberately running it so each 1 mA into the base switches ≈38 mA of LED current — deep enough that the transistor is fully on, and its on-state voltage drop V_CE(sat) is only ≈0.2 V. I_F = the LED's forward current.)*
- LED resistor: R = (3.3 − V_f − V_CE(sat)) / I_F = (3.3 − 1.35 − 0.2) / 0.100 = 17.5 Ω → **18 Ω** (E24). Assumes V_f ≈ 1.35 V at 100 mA for the 940 nm class — re-check against the finally-chosen LED's datasheet at BOM freeze and re-trim if its V_f differs materially. *(Same LED math as §1.3, with one extra drop: the transistor's 0.2 V. E24 = the standard resistor value series the round-up to 18 Ω comes from.)*
- R1002 dissipation at 100 mA: I²R ≈ 0.18 W during bursts — fit a **1206** (or pulse-rated 0805); IR duty cycle is low, but don't fit a plain 0603 here. *(The resistor turns ~0.18 W into heat while the LED pulses. A 0603 resistor is typically rated ~0.1 W — too small. 1206 is the bigger body size; that's why R1002 is the one resistor on the board with a 1206 footprint — see FOOTPRINTS.md.)*
- Bruce's DIY builds use exactly this topology (GPIO → 1 kΩ → 2N2222 → LED), per DESIGN.md §2.5. *("Topology" = the shape of the circuit — which parts connect to which, regardless of values.)*

---

## 11. Pi interface

**What changed here — 2026-10-19.** Loki's display is now a **3.5″ color touch display with its own 40-pin header**, stacked on top of the board (stack order, top to bottom: touch display / Loki PCB / Raspberry Pi 4/5 / battery pack). J1 became a stacking (pass-through) header — female socket on the bottom mating the Pi, long pins out the top that the display plugs onto — so the display and the Pi share all 40 header nodes and this board just taps the ones it needs. That change **deletes the old §11.2** (the 2 × 7 display header J5 and the Q2 backlight transistor circuit) **and the old §11.4** (the four navigation buttons SW2–SW5 and all their parts): the touchscreen is the input device now, and the display runs its own backlight. Both subsections are kept below as one-line stubs so the numbering — and any notes pointing at §11.2/§11.4 — still make sense. The display is the **MHS35 class** (SKU MHS3528 — 3.5″ ILI9486 LCD + XPT2046 resistive touch, 50 FPS, Pi driver `MHS35-show`; chosen 2026-10-20). Its socket is 2 × 13, so it contacts header pins 1–26 only, and its pin usage is folded into §3.1 — one consequence: the ESP32's EN line moved from header pin 11 to pin 37.

**What this section does.** Everything that connects the HAT board to the Raspberry Pi and the user: the 40-pin stacking header itself (§11.1), the little ID EEPROM chip that tells the Pi what HAT is attached (§11.3), and the green power-on LED (§11.5). (§11.2 and §11.4 are the removed display header and buttons — see the note above.)

### 11.1 40-pin header (J1)

The full pin-by-pin net list **is** Part B, §3.1 below — every header pin's HAT-side connection is named there, and each subsystem section above names the component at the other end of the net (e.g. header pin 11 → R502 → U5 EN). Two routing notes from DESIGN.md §3.1 worth repeating at the schematic stage: both 5 V pins (2 + 4) are fed from `5V_SYS` with a wide, via-stitched pour (a single pin is not a 4 A path), and header pin 17 (Pi 3V3) is **not connected** — the board never back-powers the Pi's 3V3 rail. Pin 1 feeds only the EEPROM (§11.3).

*Plain terms:* J1 is the 2 × 20 connector that plugs Loki onto the Pi's GPIO header. In the schematic you draw it as a 40-pin connector symbol and land each pin on the net Part B §3.1 assigns — §3.1 is the checklist for this section. The two notes: pins 2 and 4 both carry `5V_SYS` into the Pi because one pin can't safely carry the Pi 5's current (at layout they'll be joined by a wide copper pour stitched with vias — a layout detail, but in the schematic both pins simply land on `5V_SYS`); and pin 17, which is the Pi's *own* 3.3 V output, is deliberately left unconnected (no-connect flag) — powering the Pi's 3V3 rail from our board ("back-powering") could fight the Pi's own regulator. Pin 1 is also Pi 3.3 V, but by HAT rules it feeds only the ID EEPROM.

> **EasyEDA note.** On the schematic J1 is an ordinary 2×20, 2.54 mm header — any matching library device draws correctly. The special requirement is physical (long pass-through pins for the display stack) and bites at PCB/order time, not now: the footprint is the standard 2×20 through-hole pattern, and the part ordered is the stacking type in Part C.

### 11.2 Display header (J5) + backlight FET (Q2) — REMOVED 2026-10-19

Nothing to draw here anymore. J5 (the 2 × 7 header for the old ILI9341 module), the backlight switch Q2 (AO3400A) and its gate parts R1101 (100 Ω) and R1102 (100 kΩ) were deleted in the 2026-10-19 redesign: the 3.5″ touch display plugs straight onto J1's stacking pins and handles its own backlight, so the Pi's GPIO18 is spare (Part B, §3.1). The old pin table and FET explanation were removed with the circuit; DESIGN.md §2.7 records what replaced them.

### 11.3 HAT ID EEPROM — 24C32 (U9)

**What this sub-section does.** Every official-style Pi HAT carries a tiny memory chip (EEPROM) holding the HAT's ID data, which the Pi reads at boot to know what's plugged into it. U9 is that chip. It lives on its own private two-wire bus (the Pi's ID_SD/ID_SC pins), powered from the Pi's pin 1 — it belongs to the Pi's world, not to Loki's power rails.

U9 = 24C32, SOIC-8 (LCSC ⚠️ generic, confirm at BOM freeze). Per the official HAT specification. *(The ⚠️ means the 24C32 is a commodity chip made by many vendors; any standard 24C32 in SOIC-8 (the 8-pin legged package) works, and the exact one gets picked at BOM freeze. The "24C32" name itself encodes the size: 32 kilobits of EEPROM.)*

| Pin | Name | Connection |
|---|---|---|
| 8 | VCC | Net `3V3_ID` = Pi header pin 1 **only**; **C1101 = 0.1 µF** VCC→GND (EC, standard practice) |
| 4 | VSS | GND |
| 5 | SDA | Pi header pin 27 (ID_SD) |
| 6 | SCL | Pi header pin 28 (ID_SC) |
| 1, 2, 3 | A0, A1, A2 | All → GND → I²C address **0x50** |
| 7 | WP | → **SJ1 solder jumper**: default position WP→GND (writable — factory flashes the ID blob, incl. the Pi 5 PSU-capability declaration, DESIGN.md §2.7/§5.3); alternate position WP→VCC (write-protected/locked after flashing) |

*Plain terms:* A0/A1/A2 are the chip's address-select pins — wiring all three to ground sets its I²C address to 0x50, the address the Pi expects a HAT EEPROM at. WP is the write-protect pin, and SJ1 is a solder jumper (three bare pads; a blob of solder connects the middle pad to one side or the other): bridged to GND = the EEPROM can be written (how it leaves the factory, so the ID data can be flashed in); bridged to VCC = locked forever against accidental writes. In KiCad, SJ1 is a solder-jumper symbol and the footprint is in FOOTPRINTS.md — draw WP → SJ1, and the jumper's two throws to GND and to the `3V3_ID` net (that's this chip's VCC). The "ID blob" is just the data block the Pi reads — including a declaration of how much power the HAT can supply a Pi 5, which is part of why this chip exists on Loki at all.

**No pull-ups on the ID bus on the HAT** — the HAT specification puts the ID_SD/ID_SC pull-ups on the Pi side; adding our own would violate the spec's bus model. Nothing else may ever connect to ID_SD/ID_SC. **Placement:** bottom side (low profile, §2.11 plan). *(This is the one place in the design where the absence of pull-ups is itself a rule: the Pi provides them, and doubling up would break the HAT spec's electrical model. In the schematic: SDA and SCL go straight from J1 pins 27/28 to U9 pins 5/6, nothing else on those nets, ever.)*

### 11.4 Buttons ×4 (SW2–SW5) — REMOVED 2026-10-19

Nothing to draw here anymore. The four tact buttons and their whole circuit — the switches SW2–SW5, pull-ups R1110–R1113 (10 kΩ), debounce caps C1110–C1113 (100 nF) and the series resistors to the Pi R1114–R1117 (1 kΩ) — were deleted in the 2026-10-19 redesign: the touchscreen is the input device now, so the shared Pi↔ESP32 button nets (`BTN_UP/DOWN/LEFT/RIGHT`) no longer exist, and GPIO5/6/13/26 on the Pi and IO15/16/38/39 on the ESP32 are spare (Part B, §3.1/§3.2). The original circuit and its reasoning are preserved in DESIGN.md §3.3, marked superseded there.

### 11.5 Green "power on" LED (D2)

`5V_SYS` → **R1120 = 1.0 kΩ** → D2 anode; cathode → GND. D2 = 0805 green, LCSC C19171391 ✅.
**(CALC)** (5.1 − 2.1) / 1000 = **3.0 mA** (green Vf ≈ 2.1 V). Lit exactly when 5V_SYS exists = device on. Hardware-driven, per spec.

*Plain terms:* the simplest circuit on the board, and by now a familiar pattern: supply → current-limiting resistor → LED → ground. Because it hangs on `5V_SYS`, it is lit exactly when the device is switched on — no software, no chip involved, so it can never lie about whether the boost is running.

---

## 12. Expansion header (J6)

**What this section does.** J6 is the tinkering port: a 2 × 8 header on the board's top edge that brings out spare Pi GPIOs, the Pi's I²C and SPI buses, and fused power, so future add-on boards (or your own experiments) can plug into Loki. There are almost no components here — it's mostly straight wires from the Pi header nets — and the one component, F2, is a fuse protecting the 5 V pin.

J6 = 2 × 8, 2.54 mm, top edge. Full signal table in Part B, §3.4. Components:

- Pin 1 (5V_SYS feed): via **F2 = PPTC, 500 mA hold** (1812) from `5V_SYS` (per §3.4's "fused 500 mA"). *(Anything plugged into the expansion port gets its 5 V through this resettable fuse: if an add-on shorts out, F2 chokes at ~500 mA instead of taking the whole board down. 1812 = its physical size, the larger chip package.)*
- Pin 3 (board 3V3, ≤ 300 mA budget): direct from `3V3` — the budget is a build-guide rule, not a component. *("Budget" here is just a promise in the documentation: add-ons may draw at most 300 mA from this pin. Nothing on the board enforces it — it's a rule for whoever designs the add-on.)*
- All signal pins (I²C1, SPI0, GPIOs, ESP_IRQ): **direct, no series resistors, no ESD parts** — these are the Pi's/ESP32's own GPIOs brought out; add-on designers own their side's protection. Stated explicitly so the absence is a decision: the header is a hobby interconnect inside a case slot, not an external port. *(These wires get no protective resistors — deliberately. The header lives inside the case, and protection is the add-on designer's job. Recorded here so a reviewer doesn't mistake the omission for a mistake.)*

---

## 13. Battery connector (J4)

**What this section does.** Where the battery plugs in, and the board's main safety fuse. J4 is the battery socket; F1, a resettable fuse, sits between the socket and everything else, so a short anywhere downstream (or a faulty cell) gets choked off here first.

J4 = JST-PH 2-pin SMD (B2B-PH-K-S), LCSC C131337 ✅. *(JST-PH: the small white 2-pin plug/socket system used on most hobby lithium packs — the battery's lead ends in the plug, this is the board-side socket, surface-mount version.)*

> **⚠️ EasyEDA note — this also closes the old J4 question.** The recorded number C131337 could not be re-confirmed on an LCSC page in the 2026-10-21 check, and JST's own catalog makes **B2B-PH-K-S the through-hole** top-entry part — while this design's BOM intends the **SMD** version. So in the picker: either resolve C131337 and study the listing's photo/drawing, or search `PH 2.0 2P SMD` (the SMD top-entry family name is S2B-PH-SM4). Whichever device you land on, write its C-number into Part C. If you deliberately end up choosing the through-hole part, that is a design change to record — not a silent substitution.

| J4 pin | Connection |
|---|---|
| 1 | Net `VBAT_RAW` (+). **Silk-screen "+" beside the connector** — PH plugs are keyed, but clone harnesses vary; the build guide must tell builders to verify red-wire polarity against the silk before first power |
| 2 | GND (−) |

*Plain terms:* pin 1 is battery positive and starts the `VBAT_RAW` net; pin 2 is negative = GND. The silkscreen warning matters: the plug is keyed (it only fits one way), but cheap clone harnesses are sometimes wired backwards, so the board prints a "+" and the build guide tells builders to check red wire = "+" before first power-up. A reversed lithium battery is one of the few mistakes that can actually burn a board — the silk is cheap insurance.

`VBAT_RAW` → **F1 = PPTC (hold ≈ 3 A / trip ≈ 6 A, 1812)** → net `VBAT` (→ U1 BAT pins, U2 VDD). F1 value per DESIGN.md §2.6. ⚠️ **Design tension to resolve on proto #1:** DESIGN.md §4.3 puts worst-case cell draw at ≈5.2 A (Pi 5 stress, near-empty cell) — above F1's 3 A hold. A PPTC's hold is a no-trip guarantee at 23 °C, not a fuse point, and it derates with temperature; under sustained worst-case load F1 may nuisance-trip. Options: accept (fault protection wins; worst case is a corner), or uprate F1 to a 5 A-hold 1812 part. Flagged for Justin — do not silently change it here. The cell's own PCM remains the last line of defense either way (DESIGN.md §2.6).

*Plain terms — read this one, it's a genuine open decision (also item 18 in Part E):* F1 is specified to *hold* (never trip) up to ≈3 A and to trip by ≈6 A. But the design's own worst-case estimate says a stressed Pi 5 on a nearly-empty battery could draw ≈5.2 A continuously — inside the grey zone between hold and trip, where the fuse *might* trip mid-use (a "nuisance trip": Loki just turns off under heavy load, then works again when the fuse cools). It gets worse on a hot day, because the hold rating drops with temperature. The choice, to be made on prototype #1 with real measurements: **(a)** keep the 3 A part — the worst case is a rare corner (full-stress Pi 5 + nearly flat battery, simultaneously), and stronger fault protection wins; or **(b)** fit a 5 A-hold 1812 PPTC — headroom for the worst case, but a lazier fuse. Nothing to draw differently either way (same footprint, same nets), and the battery pack's own built-in protection board (PCM) is the final backstop regardless. Do not change F1's value in the schematic on your own — this decision is flagged for Justin explicitly.

---

# Part B — Pin assignment tables (from DESIGN.md §3, verbatim)

*What Part B is for: these are the master reference tables — what every pin of the Pi header, the ESP32, and the expansion header does on Loki. You don't usually draw from Part B directly; you use it to check a wire while drawing Part A ("wait, which header pin feeds the EEPROM again?" — §3.1, pin 1). The tables are reproduced exactly as written in the design document; plain-English notes are added before and after them, never inside the table cells. "BCM numbering" means the pin functions are named by the Pi chip's own GPIO numbers (GPIO14, GPIO15, …), which is how all Pi documentation refers to them — not by the physical pin's position, which is the "Pin" column.*

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
| 11 | GPIO17 | Display **TP_IRQ** (pass-through) — no Loki connection | The touch display's interrupt line to the Pi (pulses low while touched). **Was ESP32 EN until 2026-10-20** — EN moved to pin 37, because this line would otherwise reset the ESP32 on every touch |
| 12 | GPIO18 / PWM0 | Spare — pass-through node | Was the backlight FET gate until 2026-10-19; the MHS35 display leaves this pin NC (not connected) |
| 13 | GPIO27 | → ESP32 **IO0** (boot strap) | 1 kΩ series; ESP32 side 10 kΩ PU |
| 14 | GND | GND | |
| 15 | GPIO22 | ← ESP32 IO42 **attention IRQ** | ESP32 raises on BadUSB-done / RF event |
| 16 | GPIO23 | FREE → expansion | |
| 17 | 3V3 | NC | Not used (avoid back-powering Pi rail) |
| 18 | GPIO24 | Display **DC** (pass-through) | The stacked MHS35's data/command select (LCD_RS on the MHS3528 pin table) |
| 19 | GPIO10 / MOSI0 | SPI0 MOSI → touch display via pass-through header (+ expansion) | |
| 20 | GND | GND | |
| 21 | GPIO9 / MISO0 | SPI0 MISO ← touch display via pass-through header (+ expansion) | Carries the touch panel's data back to the Pi (TP_SO); the LCD itself is write-only |
| 22 | GPIO25 | Display **RST** (pass-through) | The stacked MHS35's reset line, per the MHS3528 pin table |
| 23 | GPIO11 / SCLK0 | SPI0 SCLK → touch display via pass-through header (+ expansion) | |
| 24 | GPIO8 / CE0 | Display **LCD CS** (pass-through) | The same chip-select job the old J5 display had |
| 25 | GND | GND | |
| 26 | GPIO7 / CE1 | Display **touch CS** (pass-through) | Was the display-module microSD CS until 2026-10-19 — that socket left with J5. Now the MHS35's touch-panel chip-select (TP_CS) |
| 27 | GPIO0 / ID_SD | 24C32 SDA | HAT ID bus — nothing else, ever |
| 28 | GPIO1 / ID_SC | 24C32 SCL | HAT ID bus |
| 29 | GPIO5 | Spare — pass-through node | Was Button UP (shared net) until 2026-10-19 — buttons removed, touch is the input now. Not used by Loki |
| 30 | GND | GND | |
| 31 | GPIO6 | Spare — pass-through node | Was Button DOWN until 2026-10-19 — see pin 29 |
| 32 | GPIO12 | FREE → expansion (PWM1 capable) | |
| 33 | GPIO13 | Spare — pass-through node | Was Button LEFT until 2026-10-19 — see pin 29 |
| 34 | GND | GND | |
| 35 | GPIO19 | FREE → expansion | |
| 36 | GPIO16 | FREE → expansion | |
| 37 | GPIO26 | → ESP32 **EN** (reset) | **Moved here from pin 11 on 2026-10-20** — the touch display's TP_IRQ owns pin 11 now. Was Button RIGHT until 2026-10-19. 1 kΩ series; ESP32 side has 10 kΩ PU + 1 µF |
| 38 | GPIO20 | FREE → expansion (default = expansion SPI CS) | |
| 39 | GND | GND | |
| 40 | GPIO21 | FREE → expansion | |

**UART note (all three Pis):** use the PL011 (UART0) on GPIO14/15 — on the Zero 2 W that means the `dtoverlay=disable-bt` (or `miniuart-bt`) overlay so the PL011 isn't stolen by Bluetooth; on Pi 5, GPIO14/15 is UART0 by default and the dedicated debug header stays free. 115200 baud is the locked protocol rate; esptool flashing over the same wires can run faster after sync, but the protocol doesn't need it.

*Plain terms:* the Pi has two serial ports of different quality; the good one (the PL011) is sometimes assigned to Bluetooth. The overlay settings named here are Pi software configuration (a line in the Pi's config file) that reserves the good UART for Loki's Pi↔ESP32 link on header pins 8/10. Firmware/config note, not a schematic item — the schematic just wires pins 8 and 10 as the table says. "PU" = pull-up.

**Left free on the Pi:** GPIO12, 16, 19, 20, 21, 23 (all to expansion). Spare on Loki since the 2026-10-19 touch-display change: GPIO5, 6, 13 (were buttons) and GPIO18 (was the backlight FET gate; the display leaves it NC) — pass-through nodes Loki doesn't use. Two pins changed jobs instead of going spare: GPIO7 is now the display's touch chip-select, and GPIO17 is the display's touch interrupt — which is why ESP32 EN moved to GPIO26 (pin 37) on 2026-10-20.

### 3.2 ESP32-S3-WROOM-1U-N16R8 GPIO map

Aligned with the pin conventions of existing DIY Bruce boards wherever Loki's scope allows (less fork work): shared SPI on IO11/12/13, PN532 on I2C, IR on IO1/IO2. (IO15/16/38/39 were the button inputs until 2026-10-19 — spare now; the touch display replaced the buttons.)

*Plain terms: this is the ESP32's half of the map — which of its IO pins runs which job. Loki deliberately copies the pin choices of existing DIY Bruce (ESP32 firmware) boards wherever possible, so the Bruce fork needs less modification. The "Forbidden" row at the bottom is Espressif's rule: those pins are wired inside the module to its flash memory and RAM or are boot straps — they must stay unconnected.*

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
| IO15 | Spare | Was Button UP until 2026-10-19 (§3.3, superseded) |
| IO16 | Spare | Was Button DOWN until 2026-10-19 |
| IO17 | CC1101 **GDO2** | Async serial / carrier-sense out |
| IO18 | I2C SCL → PN532 | |
| IO19 | USB D− | → the shared USB-C port (J2) via USBLC6 |
| IO20 | USB D+ | → the shared USB-C port (J2) via USBLC6 |
| IO21 | USB VBUS detect | 100 k/100 k divider from port-2 VBUS |
| IO38 | Spare | Was Button LEFT until 2026-10-19 |
| IO39 | Spare | Was Button RIGHT until 2026-10-19 |
| IO40 | PN532 **IRQ** | |
| IO41 | PN532 **RSTPDN** | |
| IO42 | → Pi GPIO22 attention IRQ | Open-drain style: drive low / release |
| IO43 | UART0 TX → Pi GPIO15 | Protocol + esptool |
| IO44 | UART0 RX ← Pi GPIO14 | |
| IO47 | Spare → test pad / aux header | |
| IO48 | Spare → test pad / aux header | |
| EN | ← Pi GPIO26 (header pin 37) | 10 kΩ PU + 1 µF to GND on board. Moved from GPIO17 on 2026-10-20 — the touch display's TP_IRQ owns GPIO17 |
| — | **Forbidden:** IO26–32 (flash), IO33–37 (octal PSRAM), IO45/46 (strapping) | All left NC per Espressif guidance |

**SPI bus sharing:** CC1101, nRF24 and microSD share SPI2 with per-device CS and per-device SPI settings (ESP-IDF/Arduino `SPISettings` transactions). Known friction, handled in the fork: Bruce's CC1101 driver and the SD library both like owning the bus — all three are polled devices with no DMA contention in practice, and the existing DIY Bruce boards already run CC1101 + dual nRF24 + SD on this exact bus topology. PN532 is deliberately **not** on SPI (I2C instead) to keep one slow, chatty device off the RF bus. The Pi's display SPI is a completely separate bus on the Pi — no interaction.

*Plain terms:* three devices sharing one SPI bus works because only one is spoken to at a time — each has its own chip-select wire, like extensions on one phone line. The software caveat (two libraries both assuming they own the bus) is a known, already-solved problem in the Bruce fork, not a hardware issue: nothing in the schematic changes because of it. And the NFC chip is intentionally on the slower I²C bus instead, so its chatter can't delay the radios.

### 3.3 Shared buttons (one net, two readers) — REMOVED 2026-10-19

The buttons are gone: the stacked 3.5″ touch display is the input device now (see the note at the top of §11), so the shared-button design that used to fill this section — one net read by both the Pi and the ESP32 — was removed with them. The four nets (`BTN_UP/DOWN/LEFT/RIGHT`), their 10 kΩ pull-ups, 1 kΩ series resistors and 100 nF debounce caps no longer exist, and GPIO5/6/13/26 (Pi) and IO15/16/38/39 (ESP32) are spare. The original explanation is preserved in DESIGN.md §3.3, marked superseded there. Nothing to draw for this section.

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

*Plain terms:* the signals on this header are the same *kinds* a Flipper Zero speaks, so Flipper-style add-ons can work — but the connector shape and pin order are different, so nothing plugs straight in; you'd use jumper wires or a small adapter board. "Enumerate" is USB-speak for "be recognised when plugged in" — borrowed here to mean: don't promise plug-and-play.

---

# Part C — Complete BOM

*What Part C is for: the shopping list — and, in EasyEDA, also the placing list, because the LCSC part you pick here is the device you place in the schematic. One row per part (or group of identical parts): its refdes, quantity, value/part name, physical package, and its **EasyEDA / LCSC** pick. A C-number marked ✅ was verified against LCSC's catalog; "search:" gives the exact words to type into EasyEDA's Library search when several equivalents are fine (all the ordinary resistors and capacitors — prefer results marked JLCPCB Basic); "draw it" means no trustworthy library device exists and the footprint gets drawn by hand from FOOTPRINTS.md, as the section note describes. Resistors and capacitors are 0603 size unless a row says otherwise; all ceramic caps are X7R/X5R type.*

| Refdes | Qty | Value / part | Package | EasyEDA / LCSC pick |
|---|---|---|---|---|
| U1 | 1 | TI bq24074RGTR charger | VQFN-16 | search `BQ24074RGTR` — recorded C54313 (picker-confirm); ⚠️ NOT the BQ24075/C15464 — see §1 note |
| U2 | 1 | MAX17048G+T10 fuel gauge | TDFN-8 | C2682616 (recorded — picker-confirm) |
| U3 | 1 | TI TPS61088RHLT boost | VQFN-20 | **C87357 ✅** — TPS61088RHLR, verified on LCSC 2026-10-21 ($0.86, in stock); confirm the device footprint is TI's RHL land pattern when placing (see §3 note) |
| U4 | 1 | SY8089AAAC buck | SOT-23-5 | C78988 (recorded — picker-confirm) |
| U5 | 1 | ESP32-S3-WROOM-1U-N16R8 module (U.FL external antenna) | SMD module | **C3013946 ✅** verified on LCSC 2026-10-22 ($5.22, in stock); the "U" variant — do NOT substitute the plain WROOM-1 (PCB antenna) or any other memory variant; see §5 note |
| U6 | 1 | EBYTE E07-900M10S CC1101 module (433 build: E07-400M10S) | Stamp-hole SMD | **Draw it** — not LCSC stock (see §6 note) |
| U7 | 1 | EBYTE E01-ML01SP4 nRF24 PA module | Stamp-hole SMD | **Draw it** — not LCSC stock (see §7 note) |
| U9 | 1 | 24C32 EEPROM | SOIC-8 | search `24C32` + SOIC-8 (AT24C32 / BL24C32 / M24C32 — any standard one) |
| U10 | 1 | ST USBLC6-2SC6 USB ESD | SOT-23-6 | **C7519 ✅** verified on LCSC 2026-10-22 (ST part, SOT-23-6L, $0.09, in stock) |
| U11 | 1 | Vishay TSOP38438 IR receiver | Minicast **THT** | recorded C145271 (picker-confirm) |
| Q1 | 1 | MMBT2222A | SOT-23 | search `MMBT2222A` — pick a standard pinout listing (1=B, 2=E, 3=C) |
| D1 | 1 | 940 nm IR LED (VSMB10940 class) | 1206 | search `1206 940nm` IR LED |
| D2 | 1 | LED green 0805 | 0805 | C19171391 (recorded) |
| D3 | 1 | LED red 0805 | 0805 | C84256 (recorded) |
| D4 | 1 | LED blue 0805 | 0805 | search `0805 blue LED` (Basic class) |
| L1 | 1 | 2.2 µH power inductor, Isat ≥ 12 A (Cyntec PIMB065T-2R2M class) | ~6.5 × 6.5 mm | search `PIMB065T-2R2MS` — TI's recommended part (7.4 × 6.8 mm body; footprint follows the frozen pick) |
| L401 | 1 | 2.2 µH, Isat > 2.3 A, DCR < 50 mΩ | 2520/2525 class | search `2520 2.2uH` — check Isat and DCR in the listing's attributes |
| J1 | 1 | 2 × 20 2.54 mm stacking header — female socket on the bottom mates the Pi; long pins out the top carry the touch display | THT | any 2×20 2.54 mm header device draws correctly; the physical stacking part is still TBD (see §11.1 note) |
| J2 | 1 | HRO TYPE-C-31-M-12 USB-C | SMD mid-mount | C165948 (strongly corroborated — picker-confirm). One port only since the 2026-10-22 merge (D11) — the second connector (ex-J3) is deleted |
| J4 | 1 | JST-PH B2B-PH-K-S battery connector | SMD | picker-check recorded C131337 — see §13 note (THT-vs-SMD trap) |
| J6 | 1 | 2 × 8 2.54 mm header (expansion) | THT/SMD | search `2x8 2.54mm header` |
| J7 | 1 | U.FL/IPEX RF connector | SMD | search `U.FL-R-SMT-1` |
| J8 | 1 | 1 × 6 2.54 mm pin header (NFC module, §8) | THT | search `1x6 2.54mm pin header` |
| SD1 | 1 | microSD slot — Hirose DM3D-SF (push-pull, card-detect switch) | SMD | **C719027 ✅** (verified on JLCPCB 2026-10-21; Extended part, ~$1.16) |
| SW1 | 1 | Slide switch (power, EN-level current) | SMD | search `slide switch` SMD SPDT — candidate MST22D18G2 / C2906280 (picker-confirm) |
| SJ1 | 1 | Solder jumper (EEPROM WP select) | 0603 pads | no library part — pads drawn at PCB stage (geometry in FOOTPRINTS.md) |
| F1 | 1 | PPTC hold ≈3 A / trip ≈6 A (see §13 warning) | 1812 | search `1812 PPTC 3A` (Bourns MF-MSMF300 family); value decision still open (Part E #18) |
| F2 | 1 | PPTC hold 500 mA | 1812 | candidate C210348 (Bourns MF-MSMF050-2 — picker-confirm) |
| R101 | 1 | 890 Ω 1 % (ISET) | 0603 | Basic: search `0603 890R 1%` |
| R102 | 1 | 1.1 kΩ (ILIM) | 0603 | Basic: search `0603 1.1k` |
| R103 | 1 | 10 kΩ (TS defeat) | 0603 | Basic: search `0603 10k` |
| R104 | 1 | 1.0 kΩ (blue LED) | 0603 | Basic: search `0603 1k` |
| R105, R106 | 2 | 5.1 kΩ (USB-C Rd ×2) | 0603 | Basic: search `0603 5.1k`. (Ex-R511/R512 deleted in the 2026-10-22 single-port merge) |
| R201 | 1 | 1.0 kΩ (red LED) | 0603 | Basic: search `0603 1k` |
| R202, R203, R513, R514 | 4 | 4.7 kΩ (I²C pull-ups) | 0603 | Basic: search `0603 4.7k` |
| R301 | 1 | 182 kΩ 1 % (boost FB top) | 0603 | Basic: search `0603 182k 1%` |
| R302 | 1 | 56 kΩ 1 % (boost FB bottom) | 0603 | Basic: search `0603 56k 1%` |
| R303 | 1 | 100 kΩ (boost ILIM) | 0603 | Basic: search `0603 100k` |
| R304 | 1 | 270 kΩ (boost FSW — to SW node!) | 0603 | Basic: search `0603 270k` |
| R305 | 1 | 10 kΩ (boost COMP, Boosty value) | 0603 | Basic: search `0603 10k` |
| R401 | 1 | 453 kΩ 1 % (buck FB top) | 0603 | Basic: search `0603 453k 1%` |
| R402 | 1 | 100 kΩ (buck FB bottom) | 0603 | Basic: search `0603 100k` |
| R403 | 1 | 1 MΩ (buck EN pull-down) | 0603 | Basic: search `0603 1M` |
| R501, R503, R506 | 3 | 10 kΩ (EN PU / IO0 PU / ESP_IRQ PU) | 0603 | Basic: search `0603 10k` |
| R502, R504 | 2 | 1 kΩ (EN / IO0 series from Pi) | 0603 | Basic: search `0603 1k` |
| R505 | 1 | 499 Ω (U0TXD series) | 0603 | Basic: search `0603 499R` |
| R507, R508 | 2 | 0 Ω (USB series, 0603; footprint accepts 22 Ω) | 0603 | Basic: search `0603 0R` |
| R509, R510 | 2 | 100 kΩ (VBUS detect divider) | 0603 | Basic: search `0603 100k` |
| R601 | 1 | 0 Ω (CC1101 antenna selector) | 0603 | Basic: search `0603 0R` |
| R901, R902, R903 | 3 | 10 kΩ (SD pull-ups) | 0603 | Basic: search `0603 10k` |
| R1001 | 1 | 100 Ω (TSOP supply filter) | 0603 | Basic: search `0603 100R` |
| R1002 | 1 | 18 Ω (IR LED current set) | **1206** | Basic: search `1206 18R` |
| R1003 | 1 | 1 kΩ (IR TX base) | 0603 | Basic: search `0603 1k` |
| R1120 | 1 | 1.0 kΩ (green LED) | 0603 | Basic: search `0603 1k` |
| C101 | 1 | 1 µF (charger IN) | 0603 | Basic: search `0603 1uF` |
| C102, C103 | 2 | 4.7 µF (charger BAT / OUT) | 0805 | Basic: search `0805 4.7uF` |
| C201 | 1 | 0.1 µF (gauge VDD) | 0603 | Basic: search `0603 100nF` |
| C301–C303, C306–C308 | 6 | 22 µF X5R ≥10 V (boost IN ×3 / OUT ×3) | 0805/1206 | search `22uF X5R 25V` in 0805/1206 — voltage rating ≥10 V matters |
| C304 | 1 | 0.1 µF (boost VIN bypass) | 0603 | Basic: search `0603 100nF` |
| C305 | 1 | 0.1 µF (boost BOOT) | 0603 | Basic: search `0603 100nF` |
| C309 | 1 | 2.2 µF (boost VCC) | 0603 | Basic: search `0603 2.2uF` |
| C310 | 1 | 47 nF (boost SS) | 0603 | Basic: search `0603 47nF` |
| C311 | 1 | 4.7 nF C0G (boost COMP, Boosty value) | 0603 | search `0603 4.7nF C0G` — dielectric matters here; do not substitute X7R |
| C401 | 1 | 22 µF X5R 10 V (buck IN) | 0805/1206 | search `22uF X5R` in 0805/1206 |
| C402, C403 | 2 | 22 µF X5R (buck OUT) | 0805/1206 | search `22uF X5R` in 0805/1206 |
| C404 | 1 | 22 pF (buck feedforward) | 0603 | Basic: search `0603 22pF` |
| C501 | 1 | 22 µF (ESP32 supply) | 0805 | search `0805 22uF` |
| C502 | 1 | 0.1 µF (ESP32 supply) | 0603 | Basic: search `0603 100nF` |
| C503 | 1 | 1 µF (ESP32 EN RC) | 0603 | Basic: search `0603 1uF` |
| C504 | 1 | 0.1 µF (VBUS detect) | 0603 | Basic: search `0603 100nF` |
| C601 | 1 | 0.1 µF (CC1101 supply) | 0603 | Basic: search `0603 100nF` |
| C602 | 1 | 10 µF (CC1101 supply) | 0805 | Basic: search `0805 10uF` |
| C701 | 1 | 10 µF (nRF24 reservoir) | 0805 | Basic: search `0805 10uF` |
| C702 | 1 | 0.1 µF (nRF24 supply) | 0603 | Basic: search `0603 100nF` |
| C901 | 1 | 0.1 µF (SD supply) | 0603 | Basic: search `0603 100nF` |
| C902 | 1 | 10 µF (SD supply) | 0805 | Basic: search `0805 10uF` |
| C1001 | 1 | 1 µF (TSOP filter) | 0603 | Basic: search `0603 1uF` |
| C1101 | 1 | 0.1 µF (EEPROM VCC) | 0603 | Basic: search `0603 100nF` |
| TP | ~6 | Test pads: IO3, IO47, IO48, VSYS, 3V3, PGOOD | — | not parts — test pads drawn at PCB stage |
| Spring antenna | 0/1 | CC1101 spring antenna (DNP unless the SMA-whip path is deleted) | — | builder option — no LCSC pick (see §6) |

Builder-sourced (not on the PCB BOM): Raspberry Pi, 3.5″ color touch display, MHS35 class (ILI9486 + XPT2046, 50 FPS — plugs onto J1's pass-through pins), 5000 mAh 1S high-drain (≥3C) pouch cell with JST-PH lead, PN532 I2C NFC module (Elechouse-type, for J8), SMA whip (868/915), IPEX whip (2.4 GHz), enclosure.

*Plain terms for the last two rows: "TP" = test pads — bare copper pads (not parts at all) placed so you can touch a multimeter or oscilloscope probe to those signals during testing. "Builder-sourced" = things you buy separately that don't solder onto this PCB: the Pi itself, the display, the battery, the antennas and the case.*

---

# Part D — Placement rules summary

*What Part D is for: the short list of rules that matter when you arrange the physical parts on the board (the PCB layout step — after the schematic is done and checked). You do not need these while drawing the schematic. Each rule is stated first in its original wording, then translated: why it exists and what it physically means.*

The short list of layout-critical items. (DESIGN.md §6 has the full checklist; this is the distilled version, with the datasheet-derived items added.)

1. **Boost SW loop first.** TPS61088: L1 + C301–C304 within 5 mm of the VIN/SW pins; SW-node copper minimum area; thermal vias under U3's pad; FB/COMP/SS parts on the far side of the package from SW. ("Minimize the length and area of all traces connected to the SW pin" — SLVSCM8D §10.1.)
   - *In plain terms:* the boost converter's switching loop is the loudest, most interference-prone circuit on the board. Lay it out first, keep it tiny (inductor and input caps within 5 mm of the chip), keep the SW node's copper as small as possible, put heat vias under the chip, and put the quiet setting parts (FB/COMP/SS) on the opposite side of the chip from the SW pins.
2. **Decoupling proximity.** Every IC's caps within ~3 mm of their pins, via-free where possible: U1 (C101–C103), U2 (C201), U4 (C401 at IN, C402/403 at LX output), U5 (C501/C502 at pin 2), U6 (C601/C602), U7 (C701/C702), SD1 (C901/C902).
   - *In plain terms:* every chip's little power capacitors must sit within ~3 mm of the pins they serve, ideally connected by plain surface copper with no vias in between (a via adds a small coil-like effect that weakens the capacitor). This is the "at the pin" rule from Part A, collected in one place.
3. **NFC header J8.** J8 sits on a board edge, clear of the U6/U7 antenna zones, with its I2C run (ESP_SDA/ESP_SCL) short, direct, and away from the boost SW node. Nothing else — since 2026-10-18 the PN532 and its tuned antenna live on the external module; there is no on-board NFC matching network.
   - *In plain terms:* the NFC connector just needs a sensible seat at the board's edge and a short, quiet path back to the ESP32. All the RF cleverness moved off-board with the module.
4. **Antenna keep-outs.** ESP32 module antenna overhangs/edges the board with **zero copper on all layers** beneath it and ≥15 mm housing clearance; CC1101 (U6) and nRF24 (U7) at opposite corners from the ESP32 antenna and from each other where the outline allows (U7 and the ESP32 both live at 2.4 GHz); nothing on this board overhangs the **Pi's** WiFi antenna corner below.
   - *In plain terms:* antennas need empty space around them — copper underneath an antenna absorbs and detunes it. The ESP32's antenna hangs off the board edge; the two radio modules go in far corners away from it and from each other (two of the three radios share the 2.4 GHz band and would interfere); and no part of Loki may sit over the Pi's own WiFi antenna corner on the board below.
5. **USB pairs.** J2 D+/D−: 90 Ω ±10 % differential, length-matched, solid ground beneath, U10 immediately behind the connector, R507/R508 immediately behind U10. J2's VBUS run stays short and wide to U1 IN (it is the charger's input as well as the data port).
   - *In plain terms:* the two USB data wires for port #2 travel as a matched pair — same length, side by side, over unbroken ground — with the protection chip U10 right behind the connector and the little series resistors right behind U10. Port #1 has no data; just keep its power wire short and fat.
6. **Ground strategy.** 4-layer stackup, L2 solid GND, no splits under RF or the boost. AGND (U3 pin 20) ties into the plane at the pad; every module's ground pads stitched down (U6 has nine ground pads for a reason — PA/RF return currents).
   - *In plain terms:* the board is four copper layers; layer 2 is one unbroken sheet of ground. Don't cut slots in it under the radios or the boost — high-frequency and high currents return through that sheet directly under their paths. Every ground pad on the radio modules gets its own via(s) down into the sheet.
7. **High-current paths are pours, not traces.** Battery → F1 → VBAT → U1; VSYS → U3 VIN; 5V_SYS → header pins 2+4 (wide, via-stitched). Size for 5 A peaks, not averages.
   - *In plain terms:* any path that carries amps gets drawn as a wide filled copper area, not a thin line, and is sized for the 5 A peak current, not the average — thin traces would heat up and waste voltage.
8. **Bottom-side discipline.** Only low-profile parts (U9, U2, U10, passives) below, ≤ 1.2 mm within Pi keep-out zones (DESIGN.md §6.7); standoff budget is the enclosure's problem only if this rule holds.
   - *In plain terms:* the underside of the board faces the Pi with only a few millimetres of gap. Only flat parts may live there (the EEPROM, fuel gauge, ESD chip, passives, the backlight FET), nothing taller than 1.2 mm near the Pi. Keep this rule and the boards stack without touching.
9. **Edges are functional.** SD1 on the case edge (hot-swappable cards); D2–D4 aligned to enclosure light pipes (freeze with the case, §6.6); U11 at an edge with a clear IR view; J7 pigtail exit at the case edge. The touch display tops the stack, so the case face is built around it.
   - *In plain terms:* parts the user physically interacts with go at the edges: the SD slot so cards swap without opening the case ("hot-swappable"), the LEDs aligned with the case's light pipes (clear plastic rods that carry LED light to the case surface), the IR receiver where it can see out, and the antenna cable exit. These positions are frozen together with the enclosure design.

---

# Part E — Sources & verification status

*What Part E is for: the audit trail. First, the list of official documents every value in Part A came from. Second — the important part — the numbered double-check list: everything that could NOT be fully confirmed from an official source, why, and what to do about it. Nothing on this list blocks drawing the schematic. Most items resolve at BOM freeze (when the exact parts are picked) or on the first prototype. Each item below keeps its original wording and gains a plain-English "what this means / what you do" note.*

**Primary sources used for Part A values:** TI SLUS810N (bq24074); TI SLVSCM8D (TPS61088) + Absurd Industries "Boosty" repo BOM/design notes; Analog Devices MAX17048/49 datasheet doc. 19-6171 Rev 7; Silergy AN_SY8089/A Rev. 0.9A; Espressif ESP32-S3-WROOM-1U Datasheet + ESP32-S3 Hardware Design Guidelines; EBYTE E07-900M10S User Manual v1.0; EBYTE E01-ML01SP4 Datasheet V1.0 + E01 User Manual; NXP AN1445 Rev. 1.2, PN532/C1 Data Sheet Rev. 3.6, UM0701-02, AN10609; Vishay Doc. 82491 (TSOP384xx) Rev. 1.0/1.6/2.1; Raspberry Pi HAT specification (EEPROM/ID bus).

**Values that could NOT be verified from a primary source (double-check list for Justin):**

1. **bq24074 EN1/EN2 abs-max voltage** — the tie of EN2 to the 5 V IN net assumes the family's 7 V logic-pin class (verified for CHG/PGOOD in §8.1, not explicitly extracted for EN1/EN2).
   - *What you do:* at BOM freeze, open SLUS810N's absolute-maximum table and confirm EN1/EN2 are rated above 5 V. Expected to pass (the family's other logic pins are 7 V-class). §1.2.
2. **bq24074 K_ILIM** — the datasheet is internally inconsistent: 1550 A·Ω (design example) vs 1610 typ (electrical table). ILIM current therefore carries ±~10 % tolerance; the 1.5 A ceiling conclusion is unaffected.
   - *What you do:* nothing. TI's own document disagrees with itself slightly; either number gives ~1.4–1.5 A max input, and R102 = 1.1 kΩ stays as drawn.
3. **TPS61088 COMP values (R305/C311)** — Boosty's proven values; the datasheet prints only equations. Validate with a load-step test on proto #1.
   - *What you do:* draw as written (§3). On the first prototype, someone does a load-step test — suddenly change the boost's load and watch the 5.1 V output on a scope for ringing or slowness. If it misbehaves, these two values are the knobs.
4. **TPS61088 R_ILIM allowed range** — no explicit min/max in the datasheet; 100 kΩ is the datasheet's own example value.
   - *What you do:* nothing — R303 = 100 kΩ is TI's own worked-example value; the gap is only that TI never printed an allowed range for it.
5. **PN532 C1/C2/Rq/R2 (R801/R802, C811–C814, R804) — MOOT.** These were the AN1445 *worked-example* antenna-matching values for the bare-chip design, always intended as bench-tuning starting points. The bare PN532 was removed on 2026-10-18 (NFC is an external module on header J8, §8); the parts and the tuning question left with it — the module's antenna is factory-tuned.
   - *What you do:* nothing — the item is closed by the redesign.
6. **PN532 TX1/TX2/RX pad numbers — MOOT.** The bare PN532 was removed from the design on 2026-10-18 (NFC is an external module on header J8, §8); there are no on-board PN532 pads left to verify.
   - *What you do:* nothing — the item is closed by the redesign.
7. **PN532 Fig. 51 per-pin capacitor assignment — MOOT.** Same 2026-10-18 change: the bare-chip decoupling set (C801–C817) no longer exists.
   - *What you do:* nothing — the item is closed by the redesign.
8. **USBLC6-2SC6 pin numbering** — flow-through arrangement as standard for the part; confirm against ST's datasheet for the exact order code.
   - *What you do:* at BOM freeze, when the exact USBLC6 variant is picked, check its datasheet pinout against §5.1's description (pin 5 = VBUS, pin 2 = GND, flow-through I/O). A pre-order checklist item.
9. **ESP32 IO0 pull-up value (10 kΩ)** — the Hardware Design Guidelines require a pull-up but state no value; 10 kΩ is from DESIGN.md and Espressif reference designs.
   - *What you do:* nothing — draw R503 = 10 kΩ as written (§5). The value matches Espressif's own reference boards.
10. **E07-900M10S decoupling values (C601/C602)** — EBYTE requires "an external ceramic filter capacitor" at VCC but gives no value; §5's recommended-circuit diagram values were not legibly extractable.
    - *What you do:* nothing — draw the standard 0.1 µF + 10 µF pair (§6). Optionally, if a legible copy of the E07 manual's recommended circuit turns up, compare values then.
11. **E07-900M10S supply range** — the manual contradicts itself (1.8–3.6 V vs 3.0–3.6 V at pin 9). Our regulated 3.3 V satisfies all versions.
    - *What you do:* nothing — 3.3 V is inside every version of the spec.
12. **E01-ML01SP4 reservoir values (C701/C702)** — EBYTE specifies no values (π-filter + margin guidance only). 10 µF + 0.1 µF is DESIGN.md's requirement and standard PA-module practice.
    - *What you do:* nothing — draw as written (§7); the pair plus the 2 A rail covers the module's 120 mA bursts with margin.
13. **E01-ML01SP4 IPEX generation** (MHF1 vs U.FL compatibility) and the FCC datasheet's conflicting 1.5 dBm/PCB-antenna figures vs the manual's 20 dBm/IPEX — confirm the exact hardware revision when ordering modules.
    - *What you do:* when ordering the U7 modules, confirm the antenna connector type on the actual part (MHF1 vs U.FL) matches the whip/pigtail being bought, and that the part is the +20 dBm IPEX version (not a low-power PCB-antenna variant that appears in one FCC document). An ordering-time check, nothing in the schematic.
14. **microSD CD-contact polarity (R903/SD1)** — ✅ RESOLVED 2026-10-19: SD1 is the Hirose DM3D-SF, whose datasheet detection switch is normally open and closes with a card inserted. Switch A → CD net (ESP32 IO7 + R903 pull-up), B → GND — the schematic as drawn is correct; no firmware inversion needed.
    - *What you do:* at BOM freeze, read the chosen slot's datasheet card-detect description. If it's the opposite polarity, firmware inverts the reading — the board doesn't change. §9.
15. **Display module (J5) pin order and SD_CS routing — MOOT.** J5, its ILI9341 module and the SD_CS-on-GPIO7 routing were all removed on 2026-10-19; the display is now the stacked 3.5″ touch display on J1's pass-through pins (§11 note). The follow-up check ran 2026-10-19/20: the picked display (MHS35 / MHS3528) uses the pins in the LCDWiki MHS3528 table, now folded into §3.1; the one real conflict (touch IRQ on GPIO17) was resolved by moving ESP32 EN to GPIO26. ⚠️ The seller's bundled PDF manual shows a *different* pin table — verify against the physical display's printed pin labels when it arrives.
    - *What you do:* nothing — the item is closed by the redesign.
16. **IR LED V_f (R1002 = 18 Ω)** — calculated at V_f ≈ 1.35 V @ 100 mA for the 940 nm class; re-trim if the frozen LED part's datasheet says otherwise.
    - *What you do:* at BOM freeze, when D1's exact part is picked, check its datasheet forward voltage at 100 mA. If it's materially different from 1.35 V, R1002 gets recalculated with the §10.2 formula (a two-minute job — ask and it can be redone). Draw 18 Ω now.
17. **SY8089 EN-to-IN tie** — within the pin's abs-max (V_IN + 0.6 V) per the datasheet table; the datasheet prints no explicit "tie EN to IN" sentence.
    - *What you do:* nothing — §4's wiring keeps EN at the same voltage as the chip's own input pin, inside its rated limit. Recorded for honesty, not action.
18. **F1 PPTC sizing tension** (§13) — DESIGN.md's 3 A-hold choice vs its own 5.2 A worst-case draw estimate. A decision for Justin, not a calculation error.
    - *What you do:* this one is a real decision, deferred to prototype #1 (see §13's plain-terms note): keep the 3 A-hold fuse (stronger protection, rare worst-case may nuisance-trip) or uprate to a 5 A-hold 1812 part. Same footprint either way — the schematic doesn't change, only the ordered part. Flagged for Justin; do not silently change it.
