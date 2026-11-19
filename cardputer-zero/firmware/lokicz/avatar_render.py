"""Layered avatar renderer for lokicz.

The character art is one generated sprite per mood, so the
wardrobe used to be invisible on him — armor showed only as a
ring BEHIND the sprite, and horns / gems / capes / the scepter
changed nothing at all (Justin's report, 2026-11-18). This
module composites real layers instead, in sprite space:

    cape + wings   (drawn behind the sprite)
    the sprite, palette-shifted in place:
        armor  — a palette swap of the outfit in the art, so
                 his clothes actually change per tier
        gem    — the helm stone recolored, or replaced by a
                 plain gold stud for "none"
        horns  — longhorns stretch the art's own horns;
                 crown / winged draw their piece on the helm
    scepter + cape clasps   (drawn in front)

Per-sprite landmarks live in _CFG (measured from the art on
2026-11-18). Expression sprites are face edits of base.png, so
they share base's landmarks. Pure PIL + numpy: renders
identically on the device and in a desktop test harness, and
any failure in here must never break the home screen — the
caller (ui.draw_loki) falls back to the plain sprite.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

_DIR = Path(__file__).with_name("sprites")

# Working-canvas padding: room for longhorns to grow and capes
# to flare without clipping. (left, top, right, bottom)
_PAD = (46, 58, 46, 14)

# Landmarks per sprite, in unpadded sprite pixels.
_CFG = {
    "base": {
        "chin_y": 348, "cx": 192,
        "gem_box": (174, 160, 210, 204),
        "horn_top_y": 190, "horn_erase_y": 148, "horn_split": 192,
        "crown_arc": [(118, 140), (150, 120), (192, 110),
                      (234, 120), (266, 140)],
        "horn_warp": [(62, 0.40, 58), (322, 0.40, 58)],
        "wing_L": (66, 228), "wing_R": (318, 228),
        "cape": [(118, 350), (266, 350), (288, 430), (300, 508),
                 (84, 508), (96, 430)],
        "cape_shoulders": [(130, 362), (254, 362)],
        "torso_box": (120, 352, 264, 452),
        "scepter_x": 304, "scepter_top": 330, "scepter_bot": 498,
        "sleeves": None,
    },
    "excited": {
        "chin_y": 340, "cx": 210,
        "gem_box": (186, 158, 224, 202),
        "horn_top_y": 186, "horn_erase_y": 146, "horn_split": 232,
        "crown_arc": [(140, 138), (172, 116), (214, 106),
                      (256, 116), (288, 138)],
        "horn_warp": [(60, 0.40, 60), (408, 0.40, 60)],
        "wing_L": (84, 224), "wing_R": (344, 224),
        "cape": [(140, 348), (288, 348), (310, 428), (322, 506),
                 (106, 506), (118, 428)],
        "cape_shoulders": [(154, 358), (274, 358)],
        "torso_box": (140, 348, 288, 448),
        "scepter_x": 356, "scepter_top": 330, "scepter_bot": 498,
        # raised arms: the sleeves live up the sides
        "sleeves": (238, 96, 368),
    },
}
# Expression sprites are edits of base.png — same canvas, same
# landmarks.
for _m in ("sleepy", "sneaky", "determined"):
    _CFG[_m] = _CFG["base"]

_SPRITES: dict = {}
_RENDER_CACHE: dict = {}

GOLD = (216, 168, 60)
GOLD_DARK = (146, 106, 32)
GOLD_HI = (240, 200, 92)


def _sprite(name: str):
    if name not in _SPRITES:
        try:
            _SPRITES[name] = Image.open(
                _DIR / f"{name}.png").convert("RGBA")
        except Exception:
            _SPRITES[name] = None
    return _SPRITES[name]


def _shift(arr, mask, hue=None, sat=1.0, val=1.0,
           sat_add=0, val_add=0):
    """HSV-shift the masked pixels of an HSV uint8 array.

    PIL hue is 0-255 for 0-360 degrees.
    """
    if not mask.any():
        return
    h = arr[..., 0][mask].astype(int)
    s = arr[..., 1][mask].astype(int)
    v = arr[..., 2][mask].astype(int)
    if hue is not None:
        h[:] = int(hue * 255 / 360)
    s = np.clip(s * sat + sat_add, 0, 255)
    v = np.clip(v * val + val_add, 0, 255)
    arr[..., 0][mask] = h
    arr[..., 1][mask] = s
    arr[..., 2][mask] = v


def _outfit_mask(a, cfg):
    """Clothing pixels: opaque, below the chin, not skin.

    Skin (face, neck, hands) is warm and red-dominant; the
    outfit is greens, blacks and gold trim.
    """
    r = a[..., 0].astype(int)
    g = a[..., 1].astype(int)
    b = a[..., 2].astype(int)
    alpha = a[..., 3] > 8
    skin = (r > 185) & (g > 130) & (b > 95) & (r - b > 32)
    H, W = alpha.shape
    below = np.zeros_like(alpha)
    below[cfg["chin_y"]:, :] = True
    mask = alpha & below & ~skin
    if cfg.get("sleeves"):
        y0, xside, xside2 = cfg["sleeves"]
        zone = np.zeros_like(alpha)
        zone[y0:, :xside] = True
        zone[y0:, xside2:] = True
        greenish = (g >= r - 6) & (g >= b - 18)
        mask |= alpha & zone & greenish & ~skin
    return mask


def _apply_armor(spr: Image.Image, tier: str, cfg) -> Image.Image:
    """Palette-swap the outfit in the art per armor tier."""
    if tier == "street":
        return spr
    a = np.asarray(spr).copy()
    outfit = _outfit_mask(a, cfg)
    if not outfit.any():
        return spr
    r = a[..., 0].astype(int)
    g = a[..., 1].astype(int)
    b = a[..., 2].astype(int)
    cloth = outfit & (g >= r - 4) & (g >= b - 16) & (a[..., 2] > 34)
    vest = outfit & (a[..., 2] <= 58) & ~cloth
    trim = outfit & (r > 108) & ((r - b) > 58) & (g > 66)
    hsv = np.asarray(
        Image.fromarray(a[..., :3]).convert("HSV")).copy()
    if tier == "leather":
        _shift(hsv, cloth, hue=26, sat=0.95, val=0.95, sat_add=8)
        _shift(hsv, vest, hue=24, sat_add=62, val=1.0)
        hsv[..., 1][vest] = np.clip(
            hsv[..., 1][vest], 60, 130)
        hsv[..., 2][vest] = np.clip(hsv[..., 2][vest], 34, 66)
        _shift(hsv, trim, sat=0.75, val=0.85)
    elif tier == "chain":
        _shift(hsv, outfit, sat=0.16, val=1.22, val_add=10)
    elif tier == "plate":
        _shift(hsv, cloth, hue=208, sat=0.55, val=1.22, val_add=10)
        _shift(hsv, vest, hue=210, sat=0.40, val=1.10)
    elif tier == "royal":
        _shift(hsv, cloth, hue=268, sat=1.10, val=0.98)
        _shift(hsv, vest, hue=268, sat_add=70)
        hsv[..., 1][vest] = np.clip(hsv[..., 1][vest], 70, 140)
        hsv[..., 2][vest] = np.clip(hsv[..., 2][vest], 26, 52)
        _shift(hsv, trim, sat=1.05, val=1.20, val_add=8)
    a[..., :3] = np.asarray(
        Image.fromarray(hsv, "HSV").convert("RGB"))
    out = Image.fromarray(a)
    if tier == "chain":
        # ring-mail rings over the torso, clipped to the outfit
        x0, y0, x1, y1 = cfg["torso_box"]
        sub = np.zeros((spr.height, spr.width), bool)
        sub[y0:y1, x0:x1] = True
        rings = Image.new("RGBA", spr.size, (0, 0, 0, 0))
        rd = ImageDraw.Draw(rings)
        step = 9
        row = 0
        yy = y0 + 5
        while yy < y1 - 2:
            xx = x0 + 5 + (step // 2 if row % 2 else 0)
            while xx < x1 - 2:
                if outfit[yy, xx]:
                    rd.ellipse([xx - 3, yy - 3, xx + 3, yy + 3],
                               outline=(208, 216, 224, 130), width=1)
                xx += step
            yy += step - 2
            row += 1
        out.alpha_composite(rings)
    return out


def _apply_gem(spr: Image.Image, gem: str, cfg) -> Image.Image:
    """Recolor the helm stone, or stud it over for 'none'."""
    if gem == "emerald":
        return spr
    x0, y0, x1, y1 = cfg["gem_box"]
    a = np.asarray(spr).copy()
    if gem in ("sapphire", "ruby"):
        # Rotate every green-hued pixel inside the gem box —
        # the stone's shaded facets included (a bright-core-only
        # mask left the stone reading green). The gold bezel is
        # yellow-hued and the band's corners barely intrude.
        hsv = np.asarray(
            Image.fromarray(a[..., :3]).convert("HSV")).copy()
        region = np.zeros(a.shape[:2], bool)
        region[y0:y1, x0:x1] = True
        hh = hsv[..., 0].astype(int)
        stone = region & (hh >= 40) & (hh <= 125) \
            & (hsv[..., 1] > 55) & (hsv[..., 2] > 38)
        if not stone.any():
            return spr
        _shift(hsv, stone, hue=222 if gem == "sapphire" else 352,
               sat=1.05)
        a[..., :3] = np.asarray(
            Image.fromarray(hsv, "HSV").convert("RGB"))
        return Image.fromarray(a)
    # "none": a plain gold stud where the stone sat
    out = spr.copy()
    d = ImageDraw.Draw(out, "RGBA")
    d.ellipse([x0 + 2, y0 + 2, x1 - 2, y1 - 2], fill=GOLD + (255,),
              outline=GOLD_DARK + (255,), width=2)
    d.ellipse([x0 + 8, y0 + 6, x0 + 15, y0 + 12],
              fill=(255, 240, 200, 150))
    return out


def _apply_longhorns(spr: Image.Image, cfg) -> Image.Image:
    """Stretch the art's own horns up and out.

    A smooth vertical warp of the whole top region: each column
    is stretched by a factor that peaks over the horn centers
    and eases back to 1.0 toward the middle, anchored at the
    horn base line. The horn — shading, outline and all — grows
    longer, and because the factor is continuous there is no
    seam where an earlier band-stretch met the untouched hair.
    """
    pl, pt, pr, pb = _PAD
    canvas = Image.new("RGBA",
                       (spr.width + pl + pr, spr.height + pt + pb),
                       (0, 0, 0, 0))
    canvas.alpha_composite(spr, (pl, pt))
    a = np.asarray(canvas).astype(np.float32)
    base = pt + cfg["horn_erase_y"]
    height = base - pt
    xs = np.arange(canvas.width, dtype=np.float32) - pl
    f = np.ones(canvas.width, dtype=np.float32)
    for center, strength, sigma in cfg["horn_warp"]:
        f += strength * np.exp(
            -((xs - center) ** 2) / (2.0 * sigma * sigma))
    out_top = max(0, int(base - height * float(f.max())) - 1)
    rows = np.arange(out_top, base)
    out = a.copy()
    region = a[pt:base]
    for x in range(canvas.width):
        src = base - (base - rows) / f[x]
        src = np.clip(src, pt, base - 1)
        lo = (src - pt).astype(int)
        frac = (src - pt - lo)[:, None]
        hi = np.minimum(lo + 1, height - 1)
        out[out_top:base, x] = region[lo, x] * (1 - frac) \
            + region[hi, x] * frac
    return Image.fromarray(out.astype(np.uint8))


def _draw_cape(draw, cape: str, cfg, off):
    ox, oy = off
    pts = [(x + ox, y + oy) for x, y in cfg["cape"]]
    if cape == "green":
        fill, fold, hem = (20, 96, 46), (12, 60, 28), None
    else:  # royal
        fill, fold, hem = (102, 38, 138), (66, 22, 92), GOLD
    draw.polygon(pts, fill=fill + (255,))
    (x0, y0), (x1, _) = pts[0], pts[1]
    (x3, y3), (x2, y2) = pts[-2], pts[-3]
    for f in (0.30, 0.50, 0.70):
        tx = x0 + (x1 - x0) * f
        bx = x3 + (x2 - x3) * f
        draw.line([(tx, y0 + 6), (bx, y2 - 4)], fill=fold + (255,),
                  width=5)
    if hem:
        draw.line([pts[-2], pts[-3]], fill=hem + (255,), width=4)


def _draw_wings(img, cfg, off):
    """Feathered wings fanning up and out from the helm sides.

    Drawn on the behind layer: the roots hide behind the head
    and the feather tips sweep out past the silhouette.
    """
    ox, oy = off
    for anchor, sign in ((cfg["wing_L"], -1), (cfg["wing_R"], 1)):
        ax, ay = anchor[0] + ox, anchor[1] + oy
        for i, (ln, ang) in enumerate(
                ((96, -38), (82, -10), (66, 16))):
            tile = Image.new("RGBA", (ln * 2, 40), (0, 0, 0, 0))
            td = ImageDraw.Draw(tile)
            td.ellipse([4, 8, ln + 18, 32], fill=(240, 236, 218, 255),
                       outline=(188, 150, 62, 255), width=2)
            tile = tile.rotate(ang if sign < 0 else -ang,
                               expand=True, resample=Image.BICUBIC)
            px = ax - tile.width // 2 + sign * int(ln * 0.38)
            py = ay - tile.height // 2 - i * 5
            img.alpha_composite(tile, (px, py))


def _draw_crown(draw, cfg, off):
    """A slim gold band on the hairline with five tall spikes."""
    ox, oy = off
    arc = [(x + ox, y + oy) for x, y in cfg["crown_arc"]]

    def arc_y(x):
        for (ax, ay), (bx, by) in zip(arc, arc[1:]):
            if ax <= x <= bx:
                t = (x - ax) / max(1, bx - ax)
                return ay + (by - ay) * t
        return arc[-1][1]

    cx = arc[len(arc) // 2][0]
    for sx, tall in ((arc[0][0] + 16, 20), (cx - 29, 24), (cx, 28),
                     (cx + 29, 24), (arc[-1][0] - 16, 20)):
        y = arc_y(sx)
        draw.polygon([(sx - 8, y + 6), (sx + 8, y + 6),
                      (sx, y - tall)],
                     fill=GOLD + (255,), outline=GOLD_DARK + (255,))
        draw.ellipse([sx - 3, y - tall - 6, sx + 3, y - tall],
                     fill=GOLD_HI + (255,))
    band = arc + [(arc[-1][0], arc[-1][1] + 9),
                  (arc[0][0], arc[0][1] + 9)]
    draw.polygon(band, fill=GOLD + (255,),
                 outline=GOLD_DARK + (255,))
    cy = arc_y(cx)
    draw.ellipse([cx - 4, cy + 1, cx + 4, cy + 9],
                 fill=(46, 196, 104, 255),
                 outline=GOLD_DARK + (255,))


def _draw_scepter(draw, cfg, off):
    ox, oy = off
    x = cfg["scepter_x"] + ox
    top, bot = cfg["scepter_top"] + oy, cfg["scepter_bot"] + oy
    draw.line([(x, top + 12), (x, bot)], fill=GOLD_DARK + (255,),
              width=7)
    draw.line([(x, top + 12), (x, bot)], fill=GOLD + (255,),
              width=4)
    draw.polygon([(x, top - 16), (x - 6, top - 2), (x + 6, top - 2)],
                 fill=GOLD + (255,), outline=GOLD_DARK + (255,))
    draw.ellipse([x - 13, top - 2, x + 13, top + 24],
                 fill=GOLD + (255,), outline=GOLD_DARK + (255,),
                 width=2)
    draw.ellipse([x - 6, top + 2, x + 1, top + 9],
                 fill=(255, 244, 205, 190))
    draw.ellipse([x - 4, top + 7, x + 4, top + 15],
                 fill=(46, 196, 104, 255))


def render(equipped: dict, mood: str = "base") -> Image.Image:
    """The character wearing `equipped`, as an RGBA image.

    Falls back to the base sprite for unknown moods. Raises on
    real trouble — ui.draw_loki catches and uses the plain
    sprite, so the home screen can never break on art.
    """
    name = mood if mood in _CFG else "base"
    if _sprite(name) is None:
        name = "base"
    gear = {k: (equipped or {}).get(k, d) for k, d in (
        ("horns", "classic"), ("armor", "street"),
        ("cape", "none"), ("gem", "none"), ("scepter", "none"))}
    key = (name, tuple(sorted(gear.items())))
    if key in _RENDER_CACHE:
        return _RENDER_CACHE[key]
    cfg = _CFG[name]
    spr = _sprite(name).copy()
    spr = _apply_armor(spr, gear["armor"], cfg)
    spr = _apply_gem(spr, gear["gem"], cfg)
    pl, pt, pr, pb = _PAD
    if gear["horns"] == "longhorn":
        work = _apply_longhorns(spr, cfg)
        off = (0, 0)
    else:
        work = Image.new(
            "RGBA", (spr.width + pl + pr, spr.height + pt + pb),
            (0, 0, 0, 0))
        work.alpha_composite(spr, (pl, pt))
        off = (pl, pt)
    behind = Image.new("RGBA", work.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(behind)
    # wings and cape sit behind the body
    if gear["horns"] == "winged":
        _draw_wings(behind, cfg, off)
    if gear["cape"] in ("green", "royal"):
        _draw_cape(bd, gear["cape"], cfg, off)
    work = Image.alpha_composite(behind, work)
    d = ImageDraw.Draw(work, "RGBA")
    if gear["horns"] == "crown":
        _draw_crown(d, cfg, off)
    if gear["cape"] in ("green", "royal"):
        for sx, sy in cfg["cape_shoulders"]:
            d.ellipse([sx + off[0] - 4, sy + off[1] - 4,
                       sx + off[0] + 4, sy + off[1] + 4],
                      fill=GOLD + (255,),
                      outline=GOLD_DARK + (255,))
    if gear["scepter"] == "scepter":
        _draw_scepter(d, cfg, off)
    bbox = work.getbbox()
    if bbox:
        work = work.crop((max(0, bbox[0] - 4), max(0, bbox[1] - 4),
                          min(work.width, bbox[2] + 4),
                          min(work.height, bbox[3] + 4)))
    if len(_RENDER_CACHE) > 24:
        _RENDER_CACHE.clear()
    _RENDER_CACHE[key] = work
    return work
