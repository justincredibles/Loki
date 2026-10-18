#!/usr/bin/env python3
"""Generate the four Loki custom symbols and merge them into loki.kicad_sym.

Pin numbers are taken from PINOUT.md (which mirrors the footprint pad maps in
loki.pretty/): E07-900M10S §6, E01-ML01SP4 §7, TPS61088 §3, TSOP38438 §10.
The existing SY8089AAAC symbol in loki.kicad_sym is preserved; the four new
symbols are inserted before the library's closing paren. KiCad 7 symbol
format (20211014), readable by KiCad 7/8/9.
"""
import re
import sys

LIB = "/home/hatch/workspace/goals/pwnagotchi-multi-radio-pcb-hat/hidden_files/kicad/loki.kicad_sym"


def fmt(v):
    return "%g" % v


def pin(name, num, ptype, x, y, ang):
    return f"""      (pin {ptype} line
        (at {fmt(x)} {fmt(y)} {ang})
        (length 2.54)
        (name "{name}"
          (effects
            (font
              (size 1.27 1.27)
            )
          )
        )
        (number "{num}"
          (effects
            (font
              (size 1.27 1.27)
            )
          )
        )
      )"""


def prop(name, value, x, y, hide=False):
    h = "\n        hide" if hide else ""
    return f"""    (property "{name}" "{value}"
      (at {fmt(x)} {fmt(y)} 0)
      (effects
        (font
          (size 1.27 1.27)
        ){h}
      )
    )"""


def symbol(name, value, footprint, descr, keywords, body, pins, ref_y, val_y):
    x1, y1, x2, y2 = body
    pin_txt = "\n".join(pin(*p) for p in pins)
    return f"""  (symbol "{name}"
    (in_bom yes)
    (on_board yes)
{prop("Reference", "U", 0, ref_y)}
{prop("Value", value, 0, val_y)}
{prop("Footprint", footprint, 0, val_y - 2.54, hide=True)}
{prop("Datasheet", "", 0, 0, hide=True)}
{prop("Description", descr, 0, 0, hide=True)}
{prop("ki_keywords", keywords, 0, 0, hide=True)}
    (symbol "{name}_0_1"
      (rectangle
        (start {fmt(x1)} {fmt(y1)})
        (end {fmt(x2)} {fmt(y2)})
        (stroke
          (width 0.254)
          (type default)
        )
        (fill
          (type background)
        )
      )
    )
    (symbol "{name}_1_1"
{pin_txt}
    )
  )"""


PI, IN, OUT, PAS = "power_input", "input", "output", "passive"

SYMBOLS = []

# ---------------------------------------------------------------- E07-900M10S
pins = [
    ("VCC", 9, PI, -10.16, 10.16, 0),
    ("CSN", 19, IN, -10.16, 7.62, 0),
    ("SCK", 18, IN, -10.16, 5.08, 0),
    ("MOSI", 17, IN, -10.16, 2.54, 0),
    ("GND", 1, PI, -10.16, 0, 0),
    ("GND", 2, PI, -10.16, -2.54, 0),
    ("GND", 3, PI, -10.16, -5.08, 0),
    ("GND", 4, PI, -10.16, -7.62, 0),
    ("GND", 5, PI, -10.16, -10.16, 0),
    ("MISO/GDO1", 16, OUT, 10.16, 10.16, 180),
    ("GDO0", 15, OUT, 10.16, 7.62, 180),
    ("GDO2", 14, OUT, 10.16, 5.08, 180),
    ("ANT", 21, PAS, 10.16, 2.54, 180),
    ("NC", 6, PAS, 10.16, 0, 180),
    ("NC", 7, PAS, 10.16, -2.54, 180),
    ("NC", 8, PAS, 10.16, -5.08, 180),
    ("NC", 10, PAS, 10.16, -7.62, 180),
    ("NC", 13, PAS, 10.16, -10.16, 180),
    ("GND", 11, PI, -3.81, -13.97, 90),
    ("GND", 12, PI, -1.27, -13.97, 90),
    ("GND", 20, PI, 1.27, -13.97, 90),
    ("GND", 22, PI, 3.81, -13.97, 90),
]
SYMBOLS.append(symbol(
    "EBYTE_E07-900M10S", "E07-900M10S", "Loki:EBYTE_E07-900M10S",
    "EBYTE E07-900M10S CC1101 sub-GHz module (also E07-400M10S). Pad map per PINOUT.md sec.6: 9=VCC, 19=CSN, 18=SCK, 17=MOSI, 16=MISO/GDO1, 15=GDO0, 14=GDO2, 21=ANT, GND=1-5/11/12/20/22, NC=6/7/8/10/13. Loki U6.",
    "cc1101 sub-ghz rf module ebyte", (-7.62, 11.43, 7.62, -11.43), pins, 13.97, -16.51))

# ---------------------------------------------------------------- E01-ML01SP4
pins = [
    ("VCC", 1, PI, -7.62, 3.81, 0),
    ("CE", 2, IN, -7.62, 1.27, 0),
    ("CSN", 3, IN, -7.62, -1.27, 0),
    ("SCK", 4, IN, -7.62, -3.81, 0),
    ("MOSI", 5, IN, 7.62, 3.81, 180),
    ("MISO", 6, OUT, 7.62, 1.27, 180),
    ("IRQ", 7, OUT, 7.62, -1.27, 180),
    ("GND", 8, PI, -2.54, -8.89, 90),
    ("GND", 9, PI, 0, -8.89, 90),
    ("GND", 10, PI, 2.54, -8.89, 90),
]
SYMBOLS.append(symbol(
    "EBYTE_E01-ML01SP4", "E01-ML01SP4", "Loki:EBYTE_E01-ML01SP4",
    "EBYTE E01-ML01SP4 nRF24L01+ PA/LNA module. Pad map per PINOUT.md sec.7: 1=VCC, 2=CE, 3=CSN, 4=SCK, 5=MOSI, 6=MISO, 7=IRQ, 8/9/10=GND. Loki U7.",
    "nrf24 2.4ghz rf module ebyte pa lna", (-5.08, 6.35, 5.08, -6.35), pins, 8.89, -11.43))

# ---------------------------------------------------------------- TPS61088
pins = [
    ("VIN", 9, PI, -10.16, 6.35, 0),
    ("EN", 2, IN, -10.16, 3.81, 0),
    ("MODE", 13, IN, -10.16, 1.27, 0),
    ("FSW", 3, PAS, -10.16, -1.27, 0),
    ("SS", 10, PAS, -10.16, -3.81, 0),
    ("ILIM", 19, PAS, -10.16, -6.35, 0),
    ("VOUT", 14, "power_output", 10.16, 6.35, 180),
    ("VOUT", 15, "power_output", 10.16, 3.81, 180),
    ("VOUT", 16, "power_output", 10.16, 1.27, 180),
    ("FB", 17, IN, 10.16, -1.27, 180),
    ("COMP", 18, PAS, 10.16, -3.81, 180),
    ("VCC", 1, "power_output", 10.16, -6.35, 180),
    ("SW", 4, OUT, -5.08, 10.16, 270),
    ("SW", 5, OUT, -2.54, 10.16, 270),
    ("SW", 6, OUT, 0, 10.16, 270),
    ("SW", 7, OUT, 2.54, 10.16, 270),
    ("BOOT", 8, PAS, 5.08, 10.16, 270),
    ("NC", 11, PAS, -5.08, -10.16, 90),
    ("NC", 12, PAS, -2.54, -10.16, 90),
    ("AGND", 20, PI, 0, -10.16, 90),
    ("PGND", 21, PI, 2.54, -10.16, 90),
]
SYMBOLS.append(symbol(
    "TPS61088", "TPS61088", "Loki:TPS61088_RHL_VQFN-20_3.5x4.5_P0.5",
    "TI TPS61088 10 A boost converter, VQFN-20 RHL + EP. Pin map per PINOUT.md sec.3: SW=4-7, VOUT=14-16, NC 11/12 tie to GND, EP pad 21=PGND. Loki U3.",
    "boost dc-dc converter", (-7.62, 7.62, 7.62, -7.62), pins, 12.7, -12.7))

# ---------------------------------------------------------------- TSOP38438
pins = [
    ("VS", 3, PI, -6.35, 2.54, 0),
    ("OUT", 1, OUT, 6.35, 2.54, 180),
    ("GND", 2, PI, 0, -6.35, 90),
]
SYMBOLS.append(symbol(
    "TSOP38438", "TSOP38438", "Loki:TSOP38438_Minicast_THT",
    "Vishay TSOP38438 38 kHz IR receiver, Minicast leaded. Pins per PINOUT.md sec.10: 1=OUT, 2=GND, 3=VS. Loki U11.",
    "ir receiver 38khz", (-3.81, 3.81, 3.81, -3.81), pins, 6.35, -8.89))

# ---------------------------------------------------------------- merge + check
src = open(LIB).read()
assert "SY8089AAAC" in src, "SY8089AAAC symbol missing from library!"
for s in SYMBOLS:
    name = re.search(r'\(symbol "([^"]+)"', s).group(1)
    assert f'(symbol "{name}"' not in src, f"{name} already present"
    nums = sorted(int(n) for n in re.findall(r'\(number "(\d+)"', s))
    expect = {"EBYTE_E07-900M10S": list(range(1, 23)),
              "EBYTE_E01-ML01SP4": list(range(1, 11)),
              "TPS61088": list(range(1, 22)),
              "TSOP38438": [1, 2, 3]}[name]
    assert nums == expect, f"{name}: pin numbers {nums} != pads {expect}"
    print(f"{name}: pins OK ({len(nums)} pads)")

stripped = src.rstrip()
assert stripped.endswith(")")
merged = stripped[:-1].rstrip() + "\n" + "\n".join(SYMBOLS) + "\n)\n"

depth = 0
for ch in merged:
    depth += (ch == "(") - (ch == ")")
    assert depth >= 0
assert depth == 0, "paren imbalance"
open(LIB, "w").write(merged)
print(f"merged library written: {len(merged)} bytes")
