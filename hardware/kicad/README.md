# Loki custom KiCad footprints

`loki.pretty/` holds the footprints that don't exist in KiCad's standard libraries
or in a manufacturer library. The full part-by-part mapping is in
[`hardware/FOOTPRINTS.md`](../FOOTPRINTS.md) — read its "Unverified geometry"
section before ordering boards.

## Contents

| Footprint | Part | Status |
|---|---|---|
| `EBYTE_E07-900M10S` | U6 — EBYTE E07-900M10S / E07-400M10S CC1101 module | ⚠️ Pad placement unverified (see FOOTPRINTS.md) |
| `EBYTE_E01-ML01SP4` | U7 — EBYTE E01-ML01SP4 nRF24 PA/LNA module | ⚠️ Pad arrangement unverified (see FOOTPRINTS.md) |
| `TPS61088_RHL_VQFN-20_3.5x4.5_P0.5` | U3 — TI TPS61088 boost | From TI drawing RHL0020A; one assumed dimension flagged |
| `TSOP38438_Minicast_THT` | U11 — Vishay TSOP38438 IR receiver | Hole pitch/pin order from datasheet; body silk approximate |

All files are KiCad 8 footprint format (version 20240108).

## Add the library in KiCad

1. In the PCB Editor (or Footprint Editor): **Preferences → Manage Footprint Libraries…**
   (KiCad 8/9: *Settings → Manage Footprint Libraries* in some builds.)
2. Open the **Project Specific Libraries** tab (so the library travels with the project).
3. Click **+**, set:
   - **Nickname:** `Loki`
   - **Library Path:** `${KIPRJMOD}/hardware/kicad/loki.pretty`
     (adjust if you cloned the repo somewhere else — the path must point at the
     `loki.pretty` **folder**; its type is auto-detected as KiCad).
4. OK. Footprints are now referenceable as `Loki:EBYTE_E07-900M10S`, etc.

## ESP32-S3-WROOM-1 (U5) — Espressif's library

U5 is deliberately **not** vendored here. Use Espressif's official KiCad library:

- Easiest: **Tools → Plugin and Content Manager** → install **"Espressif KiCad Library"**.
- Or clone https://github.com/espressif/kicad-libraries and add its
  `footprints/Espressif.pretty` (nickname `Espressif`) the same way as above, plus
  its symbol library for `ESP32-S3-WROOM-1`.

Assign U5 the footprint `Espressif:ESP32-S3-WROOM-1`. Don't use KiCad's standard
`RF_Module:ESP32-WROOM-32` — different module, different pad map.

## Re-linking footprints

FOOTPRINTS.md uses the canonical `Library:Name` for every part. If your schematic
was started with different footprint assignments (e.g. a guessed QFN for U3, or a
placeholder for U6/U7):

1. In the schematic, select the symbol(s) → **Edit → Change Footprints…** or edit the
   Footprint field per symbol to the name from FOOTPRINTS.md.
2. In the PCB editor, run **Tools → Update PCB from Schematic** with
   "Re-link footprints based on reference designators" as needed, or select a placed
   footprint → Properties → swap its library footprint, then
   **Edit → Update Footprints from Library…** to refresh all instances.
3. The EBYTE modules: if you already placed a hand-made footprint under a different
   name, just point U6/U7 at `Loki:EBYTE_E07-900M10S` / `Loki:EBYTE_E01-ML01SP4` —
   pad numbers match PINOUT.md §6/§7, so nets follow automatically.

## Still missing

**SD1 (microSD push-push slot, LCSC C91145 / C112217)** has no footprint anywhere
yet — it must be drawn from the chosen slot's LCSC datasheet land pattern.
Details in FOOTPRINTS.md, "Unverified geometry" item 5.
