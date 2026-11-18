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
    if right:
        f = _font("mono", 10)
        tw = draw.textlength(right, font=f)
        draw.text((SCREEN_W - 10 - tw, 12), right, font=f, fill=DIM)
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
        x = 8 + (i % cols) * (cw + gap)
        y = top + (i // cols) * (ch + 3)
        edge = FRAME if tone != "off" else (90, 40, 40)
        draw.rectangle([x, y, x + cw, y + ch], fill=PANEL, outline=edge)
        draw.text((x + 4, y + 1), key, font=_font("mono", 11),
                  fill=GOLD_HI if tone != "off" else DIM)
        draw.text((x + 15, y + 2), label, font=_font("mono", 9),
                  fill=TONES.get(tone, TEXT))


# --- Screens ----------------------------------------------------------

def show_screen(title: str, rows: list, chips=None, right: str = ""):
    """A themed screen.

    rows: ("kv", label, value, tone) | ("text", s, tone)
          | ("big", s, tone) | ("bar", frac, tone) | ("gap", px)
    chips: [(key, label[, tone]), ...] drawn as the footer grid.
    """
    img, draw = _base()
    _frame(draw, title, right)
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
        name = evdev.ecodes.KEY[event.code]
        if isinstance(name, list):
            name = name[0]
        simple = name.removeprefix("KEY_")
        if len(simple) == 1:
            return simple.lower()
        return {"ENTER": "enter", "ESC": "esc", "SPACE": "space",
                "UP": "up", "DOWN": "down", "LEFT": "left",
                "RIGHT": "right"}.get(simple, name)
    return None
