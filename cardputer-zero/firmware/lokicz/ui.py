"""Screen + keyboard for the Cardputer Zero — the Asgard theme.

The 320x170 ST7789v3 LCD is a plain Linux framebuffer at /dev/fb_lcd
(driver fb_st7789v): draw an image with Pillow, write its pixels to
the framebuffer, done. The 46-key keyboard (TCA8418) is a standard
evdev input device — read it like any USB keyboard.

The look: deep green-black glass, emerald HUD framing with gold
corner brackets, a horned-helmet emblem, and DejaVu Mono readouts —
a sci-fi terminal worthy of the name on the case. Rendering packs
RGB565 with numpy when available (~15 ms a frame, fast enough for
a live progress spinner), with the original pure-Python packer as
fallback.
"""

import threading
import time
from pathlib import Path

FB_DEVICE = "/dev/fb_lcd"
SCREEN_W, SCREEN_H = 320, 170

# --- Asgard palette -------------------------------------------------
BG = (3, 10, 6)            # near-black green glass
BG_LINE = (7, 22, 12)      # scanline tint
PANEL = (6, 24, 13)        # chip fill
FRAME = (22, 110, 58)      # emerald frame lines
EMERALD = (64, 255, 138)   # bright signal green
GREEN_DIM = (46, 140, 82)
TEXT = (214, 255, 226)     # pale mint
DIM = (116, 168, 132)      # secondary text
GOLD = (232, 179, 60)      # Loki gold
GOLD_HI = (255, 214, 96)   # polished gold
GOLD_DARK = (122, 86, 24)
CYAN = (96, 228, 255)      # data accent
# Cap-compat bars (Justin's scheme): dark blue = the feature
# needs the CC1101 cap, magenta/pink = needs the LoRa cap, a
# split bar = works with either fitted.
CAP_CC1101 = (38, 64, 190)
CAP_LORA = (219, 49, 164)


def _cap_bar_h(draw, x0, x1, y, cap, h=3) -> None:
    """Horizontal cap bar from x0..x1 at y (split = blue|pink)."""
    if cap == "cc1101":
        draw.rectangle([x0, y, x1, y + h - 1], fill=CAP_CC1101)
    elif cap == "lora":
        draw.rectangle([x0, y, x1, y + h - 1], fill=CAP_LORA)
    elif cap == "both":
        mid = (x0 + x1) // 2
        draw.rectangle([x0, y, mid, y + h - 1], fill=CAP_CC1101)
        draw.rectangle([mid + 1, y, x1, y + h - 1], fill=CAP_LORA)


def _cap_bar_v(draw, x, y0, y1, cap, w=3) -> None:
    """Vertical cap bar (split = blue over pink)."""
    if cap == "cc1101":
        draw.rectangle([x, y0, x + w - 1, y1], fill=CAP_CC1101)
    elif cap == "lora":
        draw.rectangle([x, y0, x + w - 1, y1], fill=CAP_LORA)
    elif cap == "both":
        mid = (y0 + y1) // 2
        draw.rectangle([x, y0, x + w - 1, mid], fill=CAP_CC1101)
        draw.rectangle([x, mid + 1, x + w - 1, y1], fill=CAP_LORA)
RED = (255, 82, 82)
AMBER = (255, 176, 66)

TONES = {"ok": EMERALD, "gold": GOLD_HI, "dim": DIM, "text": TEXT,
         "warn": AMBER, "bad": RED, "off": RED, "cyan": CYAN,
         "green": GREEN_DIM}

_FONT_DIR = "/usr/share/fonts/truetype/dejavu"
_fonts: dict = {}


def _font(kind: str, size: int):
    """Cached DejaVu faces: 'mono' (HUD text), 'sans' (display)."""
    key = (kind, size)
    if key not in _fonts:
        from PIL import ImageFont

        name = {"mono": "DejaVuSansMono-Bold.ttf",
                "sans": "DejaVuSans-Bold.ttf"}.get(kind,
                                                   "DejaVuSansMono-Bold.ttf")
        try:
            _fonts[key] = ImageFont.truetype(f"{_FONT_DIR}/{name}", size)
        except OSError:
            _fonts[key] = ImageFont.load_default()
    return _fonts[key]


def _to_rgb565(img) -> bytes:
    """Pack an RGB Pillow image into little-endian RGB565 bytes."""
    try:
        import numpy as np

        a = np.asarray(img.convert("RGB"), dtype=np.uint16)
        v = ((a[:, :, 0] >> 3) << 11) | ((a[:, :, 1] >> 2) << 5) \
            | (a[:, :, 2] >> 3)
        return v.astype("<u2").tobytes()
    except Exception:
        pass  # fall through to the slow packer
    data = img.convert("RGB").tobytes()
    out = bytearray(SCREEN_W * SCREEN_H * 2)
    for i in range(SCREEN_W * SCREEN_H):
        r, g, b = data[3 * i], data[3 * i + 1], data[3 * i + 2]
        v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        out[2 * i] = v & 0xFF
        out[2 * i + 1] = v >> 8
    return bytes(out)


def _push(img) -> None:
    with open(FB_DEVICE, "wb") as fb:
        fb.write(_to_rgb565(img))


# --- Drawing primitives ----------------------------------------------

def _base():
    """Fresh canvas: green-black glass with faint scanlines."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (SCREEN_W, SCREEN_H), BG)
    draw = ImageDraw.Draw(img)
    for y in range(0, SCREEN_H, 4):
        draw.line([(0, y), (SCREEN_W, y)], fill=BG_LINE)
    return img, draw


def _horn_points(side: int, cx: float, base_y: float, w: float,
                 h: float):
    """Points along one horn's curve: up, out, then curving in."""
    import math

    pts = []
    for i in range(31):
        t = i / 30
        x = cx + side * w * (0.32 + 0.24 * math.sin(1.35 * t)
                             - 0.27 * t * t)
        y = base_y - h * (t ** 0.9)
        r = max(0.8, w * 0.058 * (1 - t) ** 0.8)
        pts.append((x, y, r))
    return pts


def _helm_patch(w: int, h: int):
    """Loki's horned HELMET as a shaded RGBA patch — the helm only,
    never a face (Justin's call). Flat gold read as clip-art, so
    the metal is shaded: a vertical gold gradient (pale at the
    crown, bronze at the band), a soft light falloff from the
    upper left, a blurred drop shadow, pale edge highlights along
    the horns, and a faceted emerald gem with a sparkle. The empty
    space under the dome is the point — a helmet, worn by nobody.

    Anchor: the band's base line sits at y = pad + h in the patch.
    """
    from PIL import Image, ImageDraw, ImageFilter

    pad = 10
    pw = int(w * 1.24) + 2 * pad
    ph = int(h + w * 0.24) + 2 * pad
    cx, base_y = pw // 2, pad + h

    # Silhouette masks: gold parts and the gem, drawn separately.
    gold_mask = Image.new("L", (pw, ph), 0)
    gd = ImageDraw.Draw(gold_mask)
    for side in (-1, 1):
        for x, y, r in _horn_points(side, cx, base_y, w, h):
            gd.ellipse([x - r, y - r, x + r, y + r], fill=255)
    dw, dome_h = w * 0.30, w * 0.21
    gd.pieslice([cx - dw, base_y - dome_h, cx + dw,
                 base_y + dome_h * 0.55], 180, 360, fill=255)
    bw, bh = w * 0.36, max(3, w * 0.11)
    gd.polygon([(cx - bw, base_y + bh), (cx + bw, base_y + bh),
                (cx + bw * 0.82, base_y - bh * 0.4),
                (cx - bw * 0.82, base_y - bh * 0.4)], fill=255)
    g = max(2, w * 0.055)
    gem = [(cx, base_y - g), (cx + g, base_y + bh * 0.35),
           (cx, base_y + bh * 0.9), (cx - g, base_y + bh * 0.35)]
    gem_mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(gem_mask).polygon(gem, fill=255)

    patch = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    # Drop shadow from the gold silhouette.
    shadow = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    sh_mask = gold_mask.filter(ImageFilter.GaussianBlur(3))
    shadow.paste((0, 0, 0, 120), (0, 4), sh_mask)
    patch.alpha_composite(shadow)

    try:
        import numpy as np

        t = np.linspace(0, 1, ph, dtype=np.float32)[:, None]
        stops = [(0.0, (255, 228, 152)), (0.35, (255, 214, 96)),
                 (0.72, (232, 179, 60)), (1.0, (148, 104, 34))]
        grad = np.zeros((ph, pw, 3), dtype=np.float32)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            m = np.clip((t - t0) / (t1 - t0), 0, 1)
            seg = (np.array(c0) * (1 - m) + np.array(c1) * m)
            grad = np.where(((t >= t0) & (t <= t1))[..., None],
                            seg, grad)
        xs = np.linspace(0, 1, pw, dtype=np.float32)[None, :]
        light = 1.06 - 0.16 * ((xs - 0.36) ** 2
                               + (t - 0.30) ** 2) ** 0.5
        grad = np.clip(grad * light[..., None], 0, 255)
        gold_img = Image.fromarray(grad.astype("uint8"), "RGB")
        gt = np.linspace(0, 1, ph, dtype=np.float32)[:, None]
        gem_grad = (np.array((110, 255, 178)) * (1 - gt)
                    + np.array((10, 148, 74)) * gt)
        gem_img = Image.fromarray(
            np.repeat(gem_grad[:, None, :], pw, axis=1)
            .astype("uint8"), "RGB")
    except Exception:
        gold_img = Image.new("RGB", (pw, ph), GOLD)
        gem_img = Image.new("RGB", (pw, ph), EMERALD)
    patch.paste(gold_img, (0, 0), gold_mask)
    patch.paste(gem_img, (0, 0), gem_mask)

    # Painted detail on top: horn edge light, dome arc, band bevel,
    # gem facet + sparkle.
    d = ImageDraw.Draw(patch, "RGBA")
    for side in (-1, 1):
        pts = [(x + side * w * 0.016, y)
               for x, y, _ in _horn_points(side, cx, base_y, w, h)]
        d.line(pts, fill=(255, 243, 200, 165),
               width=max(1, int(w * 0.016)))
        inner = [(x - side * w * 0.020, y)
                 for x, y, _ in _horn_points(side, cx, base_y, w, h)]
        d.line(inner, fill=(110, 76, 18, 150),
               width=max(1, int(w * 0.020)))
    d.arc([cx - dw * 0.86, base_y - dome_h * 0.92, cx + dw * 0.86,
           base_y + dome_h * 0.30], 195, 300,
          fill=(255, 240, 190, 150), width=max(1, int(w * 0.016)))
    d.arc([cx - dw * 0.78, base_y - dome_h * 0.76, cx + dw * 0.78,
           base_y + dome_h * 0.4], 180, 360,
          fill=(120, 84, 22, 200), width=max(1, int(w * 0.014)))
    d.line([(cx - bw, base_y + bh), (cx + bw, base_y + bh)],
           fill=(96, 66, 16, 220), width=max(1, int(w * 0.012)))
    d.line([(gem[3][0], gem[3][1]), (cx, gem[2][1]), (gem[1][0],
           gem[1][1])], fill=(6, 110, 54, 160), width=1)
    sx, sy = cx - g * 0.34, base_y + bh * 0.02
    d.ellipse([sx - 1.4, sy - 1.4, sx + 1.4, sy + 1.4],
              fill=(255, 255, 255, 235))
    return patch, pad


def _mini_helm(draw, cx: int, base_y: int) -> None:
    """The header-sized helm: at ~24 px the stamped horns merge
    into a blob, so this one is stroked — two tapering polylines,
    a band, and the gem."""
    import math

    w, h = 24, 21
    for side in (-1, 1):
        pts = []
        for i in range(13):
            t = i / 12
            x = cx + side * w * (0.32 + 0.24 * math.sin(1.35 * t)
                                 - 0.27 * t * t)
            y = base_y - h * (t ** 0.9)
            pts.append((x, y))
        draw.line(pts, fill=GOLD, width=2)
    draw.arc([cx - 8, base_y - 10, cx + 8, base_y + 2], 180, 360,
             fill=GOLD, width=2)
    draw.rectangle([cx - 8, base_y - 2, cx + 8, base_y + 2], fill=GOLD)
    draw.polygon([(cx, base_y - 3), (cx + 2, base_y), (cx, base_y + 3),
                  (cx - 2, base_y)], fill=EMERALD)


_BATT_DIR = Path("/sys/class/power_supply/bq27220-0")
_batt_cache = (0.0, None, False)


def _battery():
    """(percent, on_external_power) from the BQ27220 fuel
    gauge, cached ~10 s so animation frames don't hammer
    sysfs. (None, False) when the gauge is unreadable."""
    global _batt_cache
    now = time.time()
    if now - _batt_cache[0] < 10:
        return _batt_cache[1], _batt_cache[2]
    pct, ext = None, False
    try:
        pct = int((_BATT_DIR / "capacity").read_text().strip())
        status = (_BATT_DIR / "status").read_text().strip()
        ext = status in ("Charging", "Full")
    except (OSError, ValueError):
        pass
    _batt_cache = (now, pct, ext)
    return pct, ext


def _status_cluster(draw, right: str) -> None:
    """The header's right side: [right label] [clock] [battery].
    Every screen wears it — drawn by _frame."""
    f = _font("mono", 10)
    x = SCREEN_W - 10
    pct, ext = _battery()
    if pct is not None:
        tone = EMERALD if pct > 30 else \
            (GOLD if pct > 15 else (255, 92, 82))
        label = f"{pct}%"
        tw = draw.textlength(label, font=f)
        draw.text((x - tw, 12), label, font=f, fill=tone)
        x -= int(tw) + 3
        ix = x - 16
        draw.rectangle([ix, 13, ix + 14, 21], outline=FRAME)
        draw.rectangle([ix + 15, 16, ix + 16, 18], fill=FRAME)
        fillw = int(12 * max(0, min(100, pct)) / 100)
        if fillw:
            draw.rectangle([ix + 2, 15, ix + 1 + fillw, 19],
                           fill=tone)
        if ext:  # gold bolt over the cell = on external power
            draw.polygon([(ix + 9, 14), (ix + 5, 18), (ix + 7, 18),
                          (ix + 6, 21), (ix + 11, 16), (ix + 8, 16)],
                         fill=GOLD_HI)
        x = ix - 7
    clock = time.strftime("%H:%M")
    tw = draw.textlength(clock, font=f)
    draw.text((x - tw, 12), clock, font=f, fill=TEXT)
    x -= int(tw)
    if right:
        tw = draw.textlength(right, font=f)
        draw.text((x - 8 - tw, 12), right, font=f, fill=DIM)


def _frame(draw, title: str, right: str = "") -> None:
    """Emerald border, gold corner brackets, header band."""
    draw.rectangle([1, 1, SCREEN_W - 2, SCREEN_H - 2], outline=FRAME)
    for x, y, dx, dy in ((2, 2, 1, 1), (SCREEN_W - 3, 2, -1, 1),
                         (2, SCREEN_H - 3, 1, -1),
                         (SCREEN_W - 3, SCREEN_H - 3, -1, -1)):
        draw.line([(x, y), (x + dx * 13, y)], fill=GOLD, width=2)
        draw.line([(x, y), (x, y + dy * 13)], fill=GOLD, width=2)
    _mini_helm(draw, 21, 26)
    draw.text((40, 8), title, font=_font("mono", 15), fill=GOLD_HI)
    _status_cluster(draw, right)
    draw.line([(8, 30), (SCREEN_W - 8, 30)], fill=GOLD_DARK)
    draw.line([(8, 32), (SCREEN_W - 8, 32)], fill=FRAME)


def _chips(draw, chips, top: int) -> None:
    """The menu as a 3x3 grid of key chips: gold digit, mint label."""
    cols, rows = 3, 3
    gap = 4
    cw = (SCREEN_W - 16 - gap * (cols - 1)) // cols
    ch = 13
    for i, chip in enumerate(chips[:9]):
        key, label = chip[0], chip[1]
        tone = chip[2] if len(chip) > 2 else "text"
        cap = chip[3] if len(chip) > 3 else None
        x = 8 + (i % cols) * (cw + gap)
        y = top + (i // cols) * (ch + 3)
        edge = FRAME if tone != "off" else (90, 40, 40)
        draw.rectangle([x, y, x + cw, y + ch], fill=PANEL, outline=edge)
        if cap:
            _cap_bar_v(draw, x, y, y + ch, cap)
        draw.text((x + 4, y + 1), key, font=_font("mono", 11),
                  fill=GOLD_HI if tone != "off" else DIM)
        draw.text((x + 15, y + 2), label, font=_font("mono", 9),
                  fill=TONES.get(tone, TEXT))


# --- Screens ----------------------------------------------------------

def show_screen(title: str, rows: list, chips=None, right: str = "",
                cap: str | None = None):
    """A themed screen.

    rows: ("kv", label, value, tone) | ("text", s, tone)
          | ("big", s, tone) | ("bar", frac, tone) | ("gap", px)
    chips: [(key, label[, tone[, cap]]), ...] drawn as the footer
    grid. `cap` ("cc1101" | "lora" | "both") draws a cap-compat
    strip under the header for whole-screen features.
    """
    img, draw = _base()
    _frame(draw, title, right)
    if cap:
        _cap_bar_h(draw, 8, SCREEN_W - 8, 34, cap, h=3)
    y = 38
    for row in rows:
        kind = row[0]
        if kind == "kv":
            _, label, value, *rest = row
            tone = rest[0] if rest else "text"
            f = _font("mono", 11)
            draw.text((10, y), label, font=f, fill=DIM)
            tw = draw.textlength(value, font=f)
            draw.text((SCREEN_W - 10 - tw, y), value, font=f,
                      fill=TONES.get(tone, TEXT))
            lx = 12 + draw.textlength(label, font=f)
            for dx in range(int(lx) + 4, int(SCREEN_W - 14 - tw), 7):
                draw.point((dx, y + 9), fill=(30, 70, 44))
            y += 16
        elif kind == "text":
            _, s, *rest = row
            tone = rest[0] if rest else "text"
            draw.text((10, y), s, font=_font("mono", 11),
                      fill=TONES.get(tone, TEXT))
            y += 16
        elif kind == "big":
            _, s, *rest = row
            tone = rest[0] if rest else "gold"
            f = _font("sans", 27)
            tw = draw.textlength(s, font=f)
            draw.text(((SCREEN_W - tw) / 2, y), s, font=f,
                      fill=TONES.get(tone, GOLD_HI))
            y += 36
        elif kind == "bar":
            _, frac, *rest = row
            tone = rest[0] if rest else "ok"
            draw.rectangle([10, y + 2, SCREEN_W - 10, y + 11],
                           outline=FRAME)
            fill_w = int((SCREEN_W - 24) * max(0.0, min(1.0, frac)))
            if fill_w:
                draw.rectangle([12, y + 4, 12 + fill_w, y + 9],
                               fill=TONES.get(tone, EMERALD))
            y += 16
        elif kind == "gap":
            y += row[1] if len(row) > 1 else 8
    if chips:
        _chips(draw, chips, SCREEN_H - 50)
    _push(img)


def radar_screen(title: str, blips: list, rows: list,
                 right: str = "") -> str:
    """A radar scope: blips at (bearing_deg, frac_of_range, tone)
    around home center, data rows down the right side. Returns
    the key pressed (any key goes back)."""
    import math

    img, draw = _base()
    _frame(draw, title, right)
    cx, cy, r = 84, 102, 58
    for frac in (1.0, 0.66, 0.33):
        rr = r * frac
        draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                     outline=FRAME if frac == 1.0 else GOLD_DARK)
    draw.line([(cx - r, cy), (cx + r, cy)], fill=GOLD_DARK)
    draw.line([(cx, cy - r), (cx, cy + r)], fill=GOLD_DARK)
    draw.text((cx - 3, cy - r - 12), "N", font=_font("mono", 10),
              fill=GOLD_HI)
    draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], outline=GOLD_HI)
    for bearing, frac, tone in blips:
        a = math.radians(bearing)
        d = r * min(max(frac, 0.0), 1.0)
        x = cx + math.sin(a) * d
        y = cy - math.cos(a) * d
        c = TONES.get(tone, TEXT)
        draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=c)
    y = 40
    f = _font("mono", 11)
    for row in rows:
        if row[0] == "kv":
            _, label, value, *rest = row
            tone = rest[0] if rest else "text"
            draw.text((152, y), label, font=f, fill=DIM)
            tw = draw.textlength(value, font=f)
            draw.text((SCREEN_W - 10 - tw, y), value, font=f,
                      fill=TONES.get(tone, TEXT))
            y += 16
        elif row[0] == "text":
            tone = row[2] if len(row) > 2 else "text"
            draw.text((152, y), row[1], font=f,
                      fill=TONES.get(tone, TEXT))
            y += 16
        elif row[0] == "gap":
            y += row[1] if len(row) > 1 else 8
    _push(img)
    return read_key()


_ARMOR = {"street": ((43, 52, 64), (31, 120, 60)),
          "leather": ((122, 82, 44), (84, 56, 28)),
          "chain": ((148, 163, 184), (100, 116, 139)),
          "plate": ((6, 95, 70), GOLD),
          "royal": (GOLD, (6, 95, 70))}
_GEM_COLORS = {"emerald": (34, 220, 110), "sapphire": (80, 150, 255),
               "ruby": (255, 80, 80)}
_SKIN = (240, 194, 151)
_HAIR = (16, 22, 18)


# --- Cartoon sprites (generated art; the shape renderer below is
# the fallback when the sprite files are missing) -------------------
_SPRITES: dict = {}
_SPRITE_DIR = Path(__file__).with_name("sprites")
# Armor tiers read as a glow disc behind the sprite: the wardrobe
# still shows on the character even though the art is one drawing.
_AURA = {"street": None, "leather": (146, 102, 52),
         "chain": (168, 178, 188), "plate": (46, 204, 130),
         "royal": (244, 200, 84)}


def _sprite(name: str):
    """Load (and cache) a character sprite PNG, or None."""
    if name not in _SPRITES:
        try:
            from PIL import Image

            _SPRITES[name] = Image.open(
                _SPRITE_DIR / f"{name}.png").convert("RGBA")
        except Exception:
            _SPRITES[name] = None
    return _SPRITES[name]


def draw_loki(img, draw, box, gear: dict, mood: str = "idle",
              bob: int = 0) -> None:
    """The little Loki, wearing `gear`, drawn into box=(x, y, w, h).

    Prefers the cartoon sprites (sprites/base.png, or excited.png
    when `mood` says so) over a tier-tinted aura disc; `bob` shifts
    him a pixel or two for the idle animation. Falls back to the
    layered flat-shape renderer when no sprite file is present.
    """
    x0, y0, w, h = box
    cx = x0 + w // 2
    spr = _sprite("excited" if mood == "excited" else "base")
    if spr is not None:
        aura = _AURA.get(gear.get("armor", "street"))
        if aura:
            r = min(w, h) // 2 - 1
            dim = tuple(int(c * 0.30) for c in aura)
            draw.ellipse([cx - r, y0 + h - 2 * r - 2 + bob,
                          cx + r, y0 + h - 2 + bob], fill=dim,
                         outline=aura)
        scale = min(w / spr.width, h / spr.height)
        sw = max(1, int(spr.width * scale))
        sh = max(1, int(spr.height * scale))
        key = (mood, sw, sh)
        frame = _SPRITES.get(key)
        if frame is None:
            from PIL import Image

            frame = spr if (sw, sh) == spr.size else spr.resize(
                (sw, sh), Image.LANCZOS)
            _SPRITES[key] = frame
        img.paste(frame, (cx - sw // 2, y0 + h - sh + bob), frame)
        return
    main, trim = _ARMOR.get(gear.get("armor", "street"),
                            _ARMOR["street"])
    dark = tuple(max(0, c - 18) for c in main)

    if gear.get("cape") in ("green", "royal"):
        cape = (18, 92, 46) if gear["cape"] == "green" else (24, 110, 54)
        draw.polygon([(cx - w * 0.30, y0 + h * 0.50),
                      (cx + w * 0.30, y0 + h * 0.50),
                      (cx + w * 0.46, y0 + h * 0.99),
                      (cx - w * 0.46, y0 + h * 0.99)], fill=cape)
        if gear["cape"] == "royal":
            draw.line([(cx - w * 0.46, y0 + h * 0.99),
                       (cx + w * 0.46, y0 + h * 0.99)],
                      fill=GOLD, width=2)
    # arms
    for side in (-1, 1):
        ax = cx + side * w * 0.335 - w * 0.055
        draw.rounded_rectangle([ax, y0 + h * 0.56, ax + w * 0.11,
                                y0 + h * 0.94], radius=4, fill=dark)
    # torso
    draw.rounded_rectangle([cx - w * 0.30, y0 + h * 0.52,
                            cx + w * 0.30, y0 + h * 0.99],
                           radius=6, fill=main)
    draw.line([(cx, y0 + h * 0.54), (cx, y0 + h * 0.97)],
              fill=trim, width=2)
    draw.line([(cx - w * 0.30, y0 + h * 0.80),
               (cx + w * 0.30, y0 + h * 0.80)], fill=trim, width=2)
    if gear.get("armor") == "chain":
        for ry in range(4):
            for rx in range(5):
                px = cx - w * 0.22 + rx * w * 0.11
                py = y0 + h * (0.58 + ry * 0.10)
                draw.ellipse([px - 2, py - 2, px + 2, py + 2],
                             outline=trim)
    if gear.get("armor") == "street":
        draw.line([(cx - w * 0.28, y0 + h * 0.60),
                   (cx + w * 0.28, y0 + h * 0.74)], fill=trim, width=3)
    # hair (sides + back sweep), then head
    draw.rounded_rectangle([cx - w * 0.30, y0 + h * 0.20,
                            cx + w * 0.30, y0 + h * 0.55],
                           radius=12, fill=_HAIR)
    draw.ellipse([cx - w * 0.25, y0 + h * 0.14,
                  cx + w * 0.25, y0 + h * 0.54], fill=_SKIN)
    # face: eyes, raised brows, smirk
    ey = y0 + h * 0.355
    for side in (-1, 1):
        ex = cx + side * w * 0.115
        draw.ellipse([ex - w * 0.045, ey - h * 0.028,
                      ex + w * 0.045, ey + h * 0.028],
                     fill=(255, 255, 255))
        draw.ellipse([ex - w * 0.020, ey - h * 0.014,
                      ex + w * 0.020, ey + h * 0.014],
                     fill=(24, 120, 60))
        draw.line([(ex - w * 0.055, ey - h * 0.075),
                   (ex + w * 0.055, ey - h * 0.095)],
                  fill=(40, 26, 16), width=2)
    draw.arc([cx - w * 0.11, y0 + h * 0.415,
              cx + w * 0.13, y0 + h * 0.50], start=15, end=80,
             fill=(120, 60, 40), width=2)
    # helm (the approved shaded patch) + variants
    helm_w, helm_h = int(w * 0.66), int(h * 0.17)
    patch, pad = _helm_patch(helm_w, helm_h)
    brow_y = int(y0 + h * 0.235)
    img.paste(patch, (cx - patch.width // 2,
                      brow_y - (pad + helm_h)), patch)
    horns = gear.get("horns", "classic")
    if horns == "longhorn":
        for side in (-1, 1):
            for i in range(4):
                t = i / 3.0
                px = cx + side * (w * 0.30 + t * w * 0.17)
                py = y0 + h * (0.10 - t * 0.085)
                r = max(2, int(w * 0.045 * (1 - t * 0.5)))
                draw.ellipse([px - r, py - r, px + r, py + r],
                             fill=GOLD_HI)
    elif horns == "crown":
        by = y0 + h * 0.015
        draw.rectangle([cx - w * 0.20, by + h * 0.05,
                        cx + w * 0.20, by + h * 0.085], fill=GOLD)
        for i in range(5):
            sx = cx - w * 0.20 + i * w * 0.10
            draw.polygon([(sx, by + h * 0.05),
                          (sx + w * 0.05, by + h * 0.05),
                          (sx + w * 0.025, by)], fill=GOLD_HI)
    elif horns == "winged":
        for side in (-1, 1):
            for i in range(3):
                wy = y0 + h * (0.16 + i * 0.055)
                draw.polygon([(cx + side * w * 0.27, wy),
                              (cx + side * w * 0.47,
                               wy - h * 0.03 + i * h * 0.012),
                              (cx + side * w * 0.28,
                               wy + h * 0.045)], fill=GOLD)
    # chest gem
    gem = gear.get("gem", "none")
    if gem in _GEM_COLORS:
        gx, gy, gr = cx, y0 + h * 0.665, max(3, int(w * 0.05))
        draw.ellipse([gx - gr, gy - gr, gx + gr, gy + gr],
                     fill=_GEM_COLORS[gem], outline=GOLD_HI)
        draw.point((gx - 1, gy - 1), fill=(255, 255, 255))
    # scepter
    if gear.get("scepter") == "scepter":
        sx = x0 + w * 0.90
        draw.line([(sx, y0 + h * 0.99), (sx, y0 + h * 0.30)],
                  fill=GOLD, width=3)
        draw.ellipse([sx - 6, y0 + h * 0.30 - 12, sx + 6,
                      y0 + h * 0.30], outline=CYAN, width=2)
        draw.ellipse([sx - 3, y0 + h * 0.30 - 9, sx + 3,
                      y0 + h * 0.30 - 3], fill=CYAN)


def _wrap(text: str, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        if len(cur) + len(word) + 1 > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines


def _home_img(item_label: str, level: int, title: str,
              frac: float, xp_text: str, saying_text: str,
              equipped: dict, bob: int = 0, cap: str | None = None):
    """One frame of Justin's home layout: avatar left, LV box +
    XP bar top right, a saying, and the PREV / item / NEXT
    carousel over keys 4 / 6 / 8."""
    img, draw = _base()
    _frame(draw, "LOKI", right=title.upper())
    draw.rectangle([6, 36, 112, 138], outline=FRAME, fill=PANEL)
    draw_loki(img, draw, (8, 38, 102, 98), equipped, bob=bob)
    draw.rectangle([120, 36, 162, 74], outline=GOLD_DARK, fill=PANEL)
    f_lv = _font("mono", 8)
    lv = "LEVEL"
    draw.text((141 - draw.textlength(lv, font=f_lv) / 2, 39), lv,
              font=f_lv, fill=DIM)
    f_num = _font("mono-bold", 20)
    num = str(level)
    draw.text((141 - draw.textlength(num, font=f_num) / 2, 47), num,
              font=f_num, fill=GOLD_HI)
    draw.rectangle([170, 38, 314, 52], outline=GOLD_DARK)
    fill_w = int((314 - 170 - 4) * max(0.0, min(1.0, frac)))
    if fill_w:
        draw.rectangle([172, 40, 172 + fill_w, 50], fill=GOLD)
    f_xp = _font("mono", 9)
    draw.text((170, 56), xp_text, font=f_xp, fill=DIM)
    f_say = _font("mono", 11)
    y = 80
    for line in _wrap(saying_text, 29)[:4]:
        draw.text((120, y), line, font=f_say, fill=TEXT)
        y += 15
    draw.line([(6, 141), (314, 141)], fill=FRAME)
    f_lab = _font("mono-bold", 11)
    draw.text((10, 145), "PREV", font=f_lab, fill=DIM)
    tw = draw.textlength(item_label.upper(), font=f_lab)
    if cap:
        _cap_bar_h(draw, int(160 - tw / 2), int(160 + tw / 2), 142,
                   cap, h=2)
    draw.text((160 - tw / 2, 145), item_label.upper(), font=f_lab,
              fill=GOLD_HI)
    nxt = "NEXT"
    draw.text((310 - draw.textlength(nxt, font=f_lab), 145), nxt,
              font=f_lab, fill=DIM)
    f_key = _font("mono", 8)
    for label, kx in (("KEY 4", 10), ("KEY 6", 148), ("KEY 8", 286)):
        draw.text((kx, 158), label, font=f_key, fill=GOLD_DARK)
    return img


def home_screen(item_label: str, level: int, title: str,
                frac: float, xp_text: str, saying_text: str,
                equipped: dict, saying_fn=None,
                cap: str | None = None) -> str:
    """The home screen, alive: Loki bobs gently while he waits,
    and his saying rotates every few seconds (via `saying_fn`
    when given). Returns the key pressed."""
    bobs = (0, 1, 2, 1)
    frame = 0
    saying = saying_text
    while True:
        _push(_home_img(item_label, level, title, frac, xp_text,
                        saying, equipped, bob=bobs[frame % 4],
                        cap=cap))
        key = read_key_timeout(0.85)
        if key is not None:
            return key
        frame += 1
        if saying_fn is not None and frame % 5 == 0:
            try:
                saying = saying_fn()
            except Exception:
                pass


def celebrate(lines: list[str]) -> None:
    """Level-up / achievement cut-in: the excited sprite, big,
    next to the news. Waits for any key."""
    img, draw = _base()
    _frame(draw, "LOKI", right="")
    draw.rectangle([6, 36, 128, 164], outline=GOLD_DARK, fill=PANEL)
    draw_loki(img, draw, (8, 38, 118, 124), {}, mood="excited")
    f_big = _font("mono-bold", 15)
    f_txt = _font("mono", 11)
    y = 52
    for i, line in enumerate(lines[:6]):
        draw.text((140, y), line, font=f_big if i == 0 else f_txt,
                  fill=GOLD_HI if i == 0 else TEXT)
        y += 22 if i == 0 else 17
    draw.text((140, 152), "ANY KEY", font=_font("mono", 8),
              fill=GOLD_DARK)
    _push(img)
    read_key()


def render_avatar_png(equipped: dict, w: int = 240,
                      h: int = 300, mood: str = "idle") -> bytes:
    """The portrait as a PNG (portal wardrobe preview)."""
    import io

    from PIL import Image, ImageDraw

    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([4, 4, w - 5, h - 5], outline=FRAME)
    draw_loki(img, draw, (14, 12, w - 28, h - 24), equipped,
              mood=mood)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def show_text(lines: list[str]) -> None:
    """Legacy plain-text screen, now wearing the theme."""
    show_screen("LOKI", [("text", line) for line in lines])


def splash(seconds: float = 1.8) -> None:
    """Boot emblem: the horned helm over a gold LOKI wordmark."""
    img, draw = _base()
    helm, pad = _helm_patch(120, 56)
    img.paste(helm, (SCREEN_W // 2 - helm.width // 2, 68 - pad - 56),
              helm)
    f = _font("sans", 44)
    tw = draw.textlength("LOKI", font=f)
    x = (SCREEN_W - tw) / 2
    draw.text((x + 2, 92), "LOKI", font=f, fill=(10, 60, 30))
    draw.text((x, 90), "LOKI", font=f, fill=GOLD_HI)
    sub = "POCKET SECURITY MULTI-TOOL"
    f2 = _font("mono", 10)
    tw2 = draw.textlength(sub, font=f2)
    draw.text(((SCREEN_W - tw2) / 2, 140), sub, font=f2, fill=DIM)
    draw.rectangle([60, 156, SCREEN_W - 60, 161], outline=FRAME)
    draw.rectangle([62, 158, 62 + int((SCREEN_W - 124) * 0.72), 159],
                   fill=GOLD)
    _push(img)
    time.sleep(seconds)


class Spinner:
    """Animated working screen for long operations.

    `with ui.Spinner("CAPTURE", "listening...", expected=90):` —
    a gold progress bar (real fraction when `expected` seconds is
    known, a sliding block when it isn't) plus an elapsed clock,
    redrawn by a background thread until the block exits.
    """

    def __init__(self, title: str, message: str, expected: float = 0):
        self.title, self.message, self.expected = title, message, expected
        self._stop = threading.Event()
        self._thread = None
        self._t0 = 0.0

    def _frame_img(self):
        img, draw = _base()
        _frame(draw, self.title, right="WORKING")
        elapsed = time.time() - self._t0
        draw.text((10, 44), self.message, font=_font("mono", 11),
                  fill=TEXT)
        if self.expected:
            frac = min(0.99, elapsed / self.expected)
            note = f"{elapsed:.0f}s / {self.expected:.0f}s"
        else:
            frac = (elapsed % 2.4) / 2.4
            note = f"{elapsed:.0f}s"
        draw.rectangle([10, 76, SCREEN_W - 10, 90], outline=FRAME)
        w = int((SCREEN_W - 24) * frac)
        draw.rectangle([12, 78, 12 + w, 88], fill=GOLD)
        draw.text((10, 100), note, font=_font("mono", 11), fill=DIM)
        tick = "▮" if int(elapsed * 2) % 2 else "▯"
        draw.text((SCREEN_W - 24, 100), tick, font=_font("mono", 11),
                  fill=EMERALD)
        return img

    def _loop(self):
        while not self._stop.is_set():
            try:
                _push(self._frame_img())
            except OSError:
                return
            self._stop.wait(0.25)

    def __enter__(self):
        self._t0 = time.time()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        return False


# --- Keyboard (unchanged) ----------------------------------------------

_keyboard = None


def _open_keyboard():
    """Find the TCA8418 keyboard among the evdev devices (cached)."""
    global _keyboard
    if _keyboard is None:
        import evdev

        for path in evdev.list_devices():
            dev = evdev.InputDevice(path)
            if "tca8418" in dev.name.lower():
                _keyboard = dev
                break
        else:
            raise RuntimeError("TCA8418 keyboard not found in /dev/input")
    return _keyboard


def _key_name(code) -> str:
    """Map an evdev key code to read_key()'s simple name."""
    import evdev

    name = evdev.ecodes.KEY[code]
    if isinstance(name, list):
        name = name[0]
    simple = name.removeprefix("KEY_")
    if len(simple) == 1:
        return simple.lower()
    return {"ENTER": "enter", "ESC": "esc", "SPACE": "space",
            "UP": "up", "DOWN": "down", "LEFT": "left",
            "RIGHT": "right"}.get(simple, name)


def read_key() -> str | None:
    """Block until a key is pressed; return its simple name.

    Digits come back as "1".."9"/"0", letters lowercase, and the
    specials as "enter", "esc", "space", "up"/"down"/"left"/"right".
    Anything else returns its evdev name (e.g. "KEY_F1") so callers
    can ignore what they don't care about.
    """
    import evdev

    dev = _open_keyboard()
    for event in dev.read_loop():
        if event.type != evdev.ecodes.EV_KEY or event.value != 1:
            continue  # only key-down events count
        return _key_name(event.code)
    return None


def read_key_timeout(timeout: float) -> str | None:
    """Like read_key(), but returns None after `timeout` seconds —
    the home screen's animation loop lives on this."""
    import select

    import evdev

    dev = _open_keyboard()
    deadline = time.time() + timeout
    while True:
        left = deadline - time.time()
        if left <= 0:
            return None
        ready, _, _ = select.select([dev.fd], [], [], left)
        if not ready:
            return None
        event = dev.read_one()
        if event is None:
            continue
        if event.type != evdev.ecodes.EV_KEY or event.value != 1:
            continue
        return _key_name(event.code)
