#!/usr/bin/env python3
"""Generate Loki custom KiCad footprints (KiCad 8 syntax, version 20240108).

Geometry sources:
- E07-900M10S: EBYTE User Manual v1.0 (body 14x20 mm, 1.27 mm half-hole
  interface, 22 pads, pin functions sec.3). Pad size / row inset / pin-1
  orientation NOT extractable from the manual text -> UNVERIFIED, flagged.
- E01-ML01SP4: EBYTE datasheet/manual (body 14.5x18 mm, 1.27 mm interface,
  10 pads, pin functions). Pad arrangement UNVERIFIED, flagged.
- TPS61088 RHL: TI package drawing RHL0020A (4219071/A) from datasheet
  SLVSE52A/SLVSCM8D: body 4.5x3.5, pitch 0.5, 7/3/7/3 pin split decoded
  from pin-function order, EP 3.05x2.05, land pads 0.6 long, outer span
  4.3 on the 7-pin sides.
- TSOP38438: Vishay Doc. 82491 family; lead pitch 2.54 nom, pin order
  1=OUT 2=GND 3=VS per PINOUT sec.10.1. Body outline approximate.
"""
import math
import os

OUT = os.path.expanduser(
    "~/workspace/goals/pwnagotchi-multi-radio-pcb-hat/hidden_files/kicad/loki.pretty"
)
os.makedirs(OUT, exist_ok=True)


def fmt(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s else "0"


def header(name, descr, tags, attr):
    return [
        f'(footprint "{name}"',
        "  (version 20240108)",
        '  (generator "custom")',
        '  (generator_version "1.0")',
        '  (layer "F.Cu")',
        f'  (descr "{descr}")',
        f'  (tags "{tags}")',
        f"  (attr {attr})",
        '  (fp_text reference "REF**" (at 0 0) (layer "F.SilkS")',
        "    (effects (font (size 1 1) (thickness 0.15)))",
        "  )",
        f'  (fp_text value "{name}" (at 0 0) (layer "F.Fab")',
        "    (effects (font (size 1 1) (thickness 0.15)))",
        "  )",
    ]


def line(x1, y1, x2, y2, layer="F.SilkS", w=0.12):
    return (f"  (fp_line (start {fmt(x1)} {fmt(y1)}) (end {fmt(x2)} {fmt(y2)})"
            f' (stroke (width {fmt(w)}) (type solid)) (layer "{layer}"))')


def rect(x1, y1, x2, y2, layer, w=0.12, fill="none"):
    return (f"  (fp_rect (start {fmt(x1)} {fmt(y1)}) (end {fmt(x2)} {fmt(y2)})"
            f' (stroke (width {fmt(w)}) (type solid)) (fill {fill}) (layer "{layer}"))')


def circle(cx, cy, r, layer="F.SilkS", w=0.12):
    return (f"  (fp_circle (center {fmt(cx)} {fmt(cy)}) (end {fmt(cx + r)} {fmt(cy)})"
            f' (stroke (width {fmt(w)}) (type solid)) (fill none) (layer "{layer}"))')


def pad_smd(num, x, y, sx, sy):
    return (f'  (pad "{num}" smd rect (at {fmt(x)} {fmt(y)}) (size {fmt(sx)} {fmt(sy)})'
            ' (layers "F.Cu" "F.Paste" "F.Mask"))')


def pad_tht(num, x, y, size, drill, shape="circle"):
    return (f'  (pad "{num}" thru_hole {shape} (at {fmt(x)} {fmt(y)}) (size {fmt(size)} {fmt(size)})'
            f' (drill {fmt(drill)}) (layers "*.Cu" "*.Mask"))')


def body_box(hx, hy, cx=0.0, cy=0.0):
    """Silkscreen body rectangle centred on (cx, cy)."""
    return [
        line(cx - hx, cy - hy, cx + hx, cy - hy),
        line(cx + hx, cy - hy, cx + hx, cy + hy),
        line(cx + hx, cy + hy, cx - hx, cy + hy),
        line(cx - hx, cy + hy, cx - hx, cy - hy),
    ]


def write(name, lines):
    path = os.path.join(OUT, name + ".kicad_mod")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n)\n")
    print("wrote", path)


# ---------------------------------------------------------------- E07-900M10S
name = "EBYTE_E07-900M10S"
descr = ("EBYTE E07-900M10S CC1101 stamp-hole module, 14x20 mm, 22 pads, 1.27 mm pitch. "
         "GEOMETRY UNVERIFIED: body size, pitch, pad count and pin functions are from the EBYTE "
         "E07-900M10S User Manual v1.0 sec.3; pad size, pad-row inset and pin-1 corner/numbering "
         "direction could NOT be extracted from the manual dimension drawing - VERIFY against the "
         "drawing or a physical module BEFORE fabrication. Pin 21 = ANT (stamp hole).")
L = header(name, descr, "EBYTE E07-900M10S CC1101 RF module stamp hole", "smd")
L += body_box(7.0, 10.0)                                   # silk body 14 x 20
L.append(rect(-7.85, -10.85, 7.85, 10.85, "F.CrtYd", 0.05))  # courtyard (pads reach x=+-7.7)
L.append(circle(-8.6, -10.0, 0.5))                          # pin-1 marker, left of pin 1
# refdes/value placement overrides: move texts clear of the body
L[8] = '  (fp_text reference "REF**" (at 0 -11.6) (layer "F.SilkS")'
L[11] = f'  (fp_text value "{name}" (at 0 11.6) (layer "F.Fab")'
for i in range(1, 23):
    if i <= 11:   # left column, top (pin 1) -> bottom (pin 11)
        x, y = -6.6, -6.35 + (i - 1) * 1.27
    else:         # right column, bottom (pin 12) -> top (pin 22)
        x, y = 6.6, 6.35 - (i - 12) * 1.27
    L.append(pad_smd(i, x, y, 2.2, 0.9))
write(name, L)

# ---------------------------------------------------------------- E01-ML01SP4
name = "EBYTE_E01-ML01SP4"
descr = ("EBYTE E01-ML01SP4 nRF24L01+ PA/LNA stamp-hole module, 14.5x18 mm, 10 pads, 1.27 mm pitch. "
         "GEOMETRY UNVERIFIED: body size, pitch, pad count and pin functions are from the EBYTE "
         "E01-ML01SP4 datasheet/manual; the two-row pad arrangement, pad size, row inset and pin-1 "
         "corner could NOT be extracted from the manual dimension drawing - VERIFY against the "
         "drawing or a physical module BEFORE fabrication. Pad order is NOT the DIP nRF24 order.")
L = header(name, descr, "EBYTE E01-ML01SP4 nRF24 PA LNA module stamp hole", "smd")
L += body_box(7.25, 9.0)                                    # silk body 14.5 x 18
L.append(rect(-7.85, -9.85, 7.85, 9.85, "F.CrtYd", 0.05))
L.append(circle(-8.6, -2.54, 0.5))                          # pin-1 marker
L[8] = '  (fp_text reference "REF**" (at 0 -10.6) (layer "F.SilkS")'
L[11] = f'  (fp_text value "{name}" (at 0 10.6) (layer "F.Fab")'
for i in range(1, 11):
    if i <= 5:    # left column, top (pin 1 VCC) -> bottom (pin 5 MOSI)
        x, y = -6.6, -2.54 + (i - 1) * 1.27
    else:         # right column, bottom (pin 6 MISO) -> top (pin 10 GND)
        x, y = 6.6, 2.54 - (i - 6) * 1.27
    L.append(pad_smd(i, x, y, 2.2, 0.9))
write(name, L)

# ---------------------------------------------------------------- TPS61088 RHL
name = "TPS61088_RHL_VQFN-20_3.5x4.5_P0.5"
descr = ("TI TPS61088RHLT VQFN-20 (RHL0020A), body 3.5x4.5 mm, 0.5 mm pitch, EP 2.05x3.05 = pad 21 (PGND). "
         "Geometry from TI package drawing RHL0020A (4219071/A) in datasheet SLVSE52A/SLVSCM8D: land pads "
         "0.28x0.6, 7-pin sides outer span 4.3. Pin split 7/3/7/3 and numbering decoded from the datasheet "
         "pin-function order (SW x4 = pins 4-7, VOUT x3 = pins 14-16). Top/bottom pad row inset assumes the "
         "same 0.4 mm toe as the sides - cross-check against the TI drawing before fabrication.")
L = header(name, descr, "TPS61088 VQFN-20 RHL boost", "smd")
L += body_box(1.75, 2.25)                                   # silk body 3.5 x 4.5
L.append(rect(-2.6, -2.9, 2.6, 2.9, "F.CrtYd", 0.05))
L.append(circle(-2.45, -2.25, 0.4))                          # pin-1 marker by pin 1 (top-left)
L[8] = '  (fp_text reference "REF**" (at 0 -3.4) (layer "F.SilkS")'
L[11] = f'  (fp_text value "{name}" (at 0 3.4) (layer "F.Fab")'
for i in range(1, 8):                                       # left side pins 1-7, top -> bottom
    L.append(pad_smd(i, -1.85, -1.5 + (i - 1) * 0.5, 0.6, 0.28))
for j, i in enumerate((8, 9, 10)):                          # bottom pins 8-10, left -> right
    L.append(pad_smd(i, -0.5 + j * 0.5, 2.35, 0.28, 0.6))
for i in range(11, 18):                                     # right side pins 11-17, bottom -> top
    L.append(pad_smd(i, 1.85, 1.5 - (i - 11) * 0.5, 0.6, 0.28))
for j, i in enumerate((18, 19, 20)):                        # top pins 18-20, right -> left
    L.append(pad_smd(i, 0.5 - j * 0.5, -2.35, 0.28, 0.6))
L.append(pad_smd(21, 0, 0, 2.05, 3.05))                     # EP / PGND
write(name, L)

# ---------------------------------------------------------------- TSOP38438
name = "TSOP38438_Minicast_THT"
descr = ("Vishay TSOP38438 IR receiver, Minicast leaded (THT). Lead pitch 2.54 nom and pin order "
         "1=OUT 2=GND 3=VS from Vishay Doc. 82491 family data (PINOUT sec.10.1). Pin 1 (OUT) is the "
         "leftmost lead with the lens facing you and leads pointing down; square pad + silk dot mark "
         "pin 1 - VERIFY orientation against the datasheet drawing before fabrication. Body outline "
         "on F.SilkS is approximate (sibling-family drawing); hole geometry is the critical part.")
L = header(name, descr, "TSOP38438 IR receiver Minicast THT", "through_hole")
# body: 6.0 wide (X) x 4.8 deep (Y), lens side toward -Y; leads on the centre line y=0
L += [line(-3.0, -4.2, 3.0, -4.2), line(3.0, -4.2, 3.0, 0.6),
      line(3.0, 0.6, -3.0, 0.6), line(-3.0, 0.6, -3.0, -4.2)]
L.append(rect(-3.6, -4.8, 3.6, 1.2, "F.CrtYd", 0.05))
L.append(circle(-3.9, -1.0, 0.4))                           # pin-1 marker
L[8] = '  (fp_text reference "REF**" (at 0 -5.6) (layer "F.SilkS")'
L[11] = f'  (fp_text value "{name}" (at 0 2.2) (layer "F.Fab")'
L.append(pad_tht(1, -2.54, 0, 1.8, 0.95, "rect"))           # OUT (square pad = pin 1)
L.append(pad_tht(2, 0, 0, 1.8, 0.95))                       # GND
L.append(pad_tht(3, 2.54, 0, 1.8, 0.95))                    # VS
write(name, L)

print("done")

# ---------------------------------------------------------------- Hirose DM3D-SF
name = "Hirose_DM3D-SF"
descr = ("Hirose DM3D-SF microSD card connector (HRS 609-0025-8), push-pull, top-mount, body 11.95x11.45 mm. "
         "Drawn from the 'Recommended PCB mounting pattern' + connector drawing in the Hirose DM3 Series datasheet "
         "(DM3D-SF): 8 contacts 0.7x1.75 mm on 1.1 mm pitch, pin 1 (DAT2) at the +X end of the contact row (front-elevation "
         "leader labels: 8=DAT1 at -X end ... 1=DAT2 at +X end); card-detection switch (normally open, closes with card "
         "inserted): pad 9 = switch (A), pad 10 = switch (B) per the top-view leaders; 4 shell solder tabs = MP. "
         "Card inserts from the +Y edge (contact-row side). Origin = connector body centre. Geometry extracted from the "
         "datasheet drawing's vector outlines and cross-checked on a 700-dpi render (scale 8.3052 pt/mm from the labelled "
         "1.1 mm pitch / 7.7 mm span); all values rounded to 0.01 mm. Note-3 'no conductive traces' zones are drawn on "
         "F.Fab for reference only. VERIFY against a physical connector before fabrication - see dm3d-sf-footprint-notes.md.")
L = header(name, descr, "Hirose DM3D-SF microSD card connector DM3", "smd")
L += body_box(5.975, 5.725)                                  # silk body 11.95 x 11.45
# inserted-card outline on silk: card is 11 wide, rear edge sits 4.35 mm proud of the front (+Y) body edge
for seg in [(-5.5, 5.725, -5.5, 10.075), (5.5, 5.725, 5.5, 10.075), (-5.5, 10.075, 5.5, 10.075)]:
    L.append(line(*seg))
# insertion arrow on silk: shaft + head pointing -Y (into the slot) at x=0, in the card area
L.append(line(0, 9.3, 0, 7.3))
L.append(line(0, 7.3, -0.45, 7.95))
L.append(line(0, 7.3, 0.45, 7.95))
L.append(rect(-6.65, -6.5, 6.65, 6.5, "F.CrtYd", 0.05))      # courtyard
L.append(circle(4.55, 5.35, 0.35))                           # pin-1 marker, right of pin 1 pad
# note-3 no-trace zones, reference only on F.Fab
L.append(rect(-1.97, -5.73, 0.52, -3.73, "F.Fab", 0.05))
L.append(rect(-4.93, -1.52, 3.58, 0.48, "F.Fab", 0.05))
L[8] = '  (fp_text reference "REF**" (at 0 -7.4) (layer "F.SilkS")'
L[11] = f'  (fp_text value "{name}" (at 0 11.4) (layer "F.Fab")'
# contacts, y = +5.35 (front edge row), 0.7 x 1.75, pitch 1.1; pin 1 at +X end
for n, x in [(1, 3.18), (2, 2.08), (3, 0.98), (4, -0.12), (5, -1.22), (6, -2.32), (7, -3.42), (8, -4.52)]:
    L.append(pad_smd(n, x, 5.35, 0.7, 1.75))
L.append(pad_smd(9, 5.58, -5.45, 1.0, 1.55))                  # switch (A)
L.append(pad_smd(10, -5.66, -3.89, 1.45, 1.0))                # switch (B)
L.append(pad_smd("MP", -5.73, 5.23, 1.3, 1.5))                # shell tab, front-left
L.append(pad_smd("MP", 5.63, 5.23, 1.49, 1.5))                # shell tab, front-right
L.append(pad_smd("MP", -5.98, -2.38, 0.8, 1.49))              # shell tab, left side
L.append(pad_smd("MP", 5.97, -3.03, 0.8, 1.4))                # shell tab, right side
write(name, L)
