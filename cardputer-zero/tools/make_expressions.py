#!/usr/bin/env python3
"""Build expression sprites for the lokicz avatar by editing
the generated base sprite's face in place.

New character art cannot be generated on demand (the image
pipeline declines this character), so expressions are careful
pixel edits of sprites/base.png instead — same canvas, so all
of avatar_render's landmarks keep working:

  sleepy — each eye's interior is repainted with cheek skin
           and a sagging lid line + lashes drawn over it; the
           grin is repainted away and an open yawn drawn in;
           two Z's float by the horn.
  sneaky — each iris disc is cut and shifted sideways inside
           a repainted sclera for a side-glance; the smug grin
           already suits it, so the mouth is untouched.

(The first sleepy attempt patched the eyes with a forehead
strip — which at eye height is helm band, not skin — and left
gold streaks. Repainting with sampled cheek tones is the fix.)

Face landmarks (base.png, 384x512), measured from the art:
  left eye  bbox (100, 238)-(182, 302), iris center (141, 272)
  right eye bbox (203, 238)-(285, 302), iris center (245, 272)
  grin      bbox (146, 300)-(242, 338)

Run from anywhere:  python3 tools/make_expressions.py
Writes sprites/sleepy.png and sprites/sneaky.png.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SPRITES = Path(__file__).resolve().parent.parent \
    / "firmware" / "lokicz" / "sprites"

EYES = [((100, 238), (182, 302), (141, 272), (108, 306, 140, 330)),
        ((203, 238), (285, 302), (245, 272), (245, 306, 277, 330))]
GRIN = (146, 300, 242, 338)
CHIN = (168, 342, 218, 356)
LID = (74, 44, 30)


def _median_rgb(img: Image.Image, box):
    a = np.asarray(img)[box[1]:box[3], box[0]:box[2]]
    px = a[a[..., 3] > 0][:, :3]
    return np.median(px, axis=0)


def _mask(shape, draw_fn, blur=1.4):
    m = Image.new("L", shape, 0)
    draw_fn(ImageDraw.Draw(m))
    return np.asarray(m.filter(ImageFilter.GaussianBlur(blur)),
                      dtype=float) / 255.0


def _fill_gradient(img: Image.Image, mask, top_rgb, bot_rgb):
    """Blend a vertical color gradient in where mask > 0."""
    a = np.asarray(img).astype(float)
    ys = np.where(mask.max(axis=1) > 0.01)[0]
    if len(ys) == 0:
        return img
    y0, y1 = ys.min(), ys.max()
    t = np.clip((np.arange(a.shape[0]) - y0)
                / max(1, y1 - y0), 0, 1)[:, None, None]
    grad = top_rgb[None, None, :] * (1 - t) \
        + bot_rgb[None, None, :] * t
    m = mask[..., None]
    a[..., :3] = a[..., :3] * (1 - m) + grad * m
    return Image.fromarray(a.astype(np.uint8))


def _lid(draw: ImageDraw.ImageDraw, bbox, center):
    """A closed eye: a soft sagging arc plus lash ticks."""
    (x0, y0), (x1, y1) = bbox
    cx, cy = center
    pts = []
    for i in range(17):
        t = i / 16
        x = x0 + 7 + (x1 - x0 - 14) * t
        y = cy - 2 + math.sin(t * math.pi) * 13
        pts.append((x, y))
    draw.line(pts, fill=LID + (255,), width=5, joint="curve")
    for fx in (0.68, 0.80, 0.90):
        lx = x0 + 7 + (x1 - x0 - 14) * fx
        ly = cy - 2 + math.sin(fx * math.pi) * 13
        draw.line([(lx, ly), (lx + 3, ly + 6)],
                  fill=LID + (255,), width=3)


def make_sleepy(base: Image.Image) -> Image.Image:
    img = base.copy()
    for idx, ((x0, y0), (x1, y1), (cx, cy), cheek) in \
            enumerate(EYES):
        tone = _median_rgb(base, cheek)
        # The eyes' outer corners flick up past the measured
        # bbox — stretch the fill toward the temple side.
        grow = 52 if idx == 1 else 40
        grow_l = 52 if idx == 0 else 40
        mask = _mask(img.size, lambda d: d.ellipse(
            [cx - grow_l, cy - 36, cx + grow, cy + 30],
            fill=255))
        img = _fill_gradient(img, mask, tone * 0.94, tone)
    d = ImageDraw.Draw(img, "RGBA")
    for corner0, corner1, center, _cheek in EYES:
        _lid(d, (corner0, corner1), center)
    # Cheek tone beside the mouth, not the chin: the chin sits
    # in the jaw shadow and its tone ringed the yawn like a
    # smudge.
    tone = _median_rgb(base, (116, 306, 142, 332))
    mask = _mask(img.size, lambda d: d.ellipse(
        [134, 297, 254, 341], fill=255), blur=2.2)
    img = _fill_gradient(img, mask, tone * 0.97, tone)
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = 194, 320
    d.ellipse([cx - 17, cy - 13, cx + 17, cy + 13],
              fill=(96, 36, 34, 255), outline=LID + (255,),
              width=3)
    d.pieslice([cx - 13, cy - 2, cx + 13, cy + 13], 0, 180,
               fill=(172, 84, 76, 255))
    try:
        f1 = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            30)
        f2 = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            42)
    except Exception:
        f1 = f2 = ImageFont.load_default()
    d.text((300, 196), "z", font=f1, fill=(168, 178, 235, 235))
    d.text((322, 152), "Z", font=f2, fill=(168, 178, 235, 235))
    return img


def make_sneaky(base: Image.Image) -> Image.Image:
    a = np.asarray(base).astype(int)
    out = np.array(base).astype(int)
    H, W = a.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    r = a[..., 0]
    g = a[..., 1]
    b = a[..., 2]
    # Only pixels that already ARE eye (bright sclera, green
    # iris, dark pupil) may be repainted — never the outline,
    # lids or skin. (Anatomical masks kept spilling onto them.)
    whitish = (r > 198) & (g > 198) & (b > 188)
    greenish = (g > r + 18) & (g >= b - 8)
    for (x0, y0), (x1, y1), (cx, cy), _cheek in EYES:
        bbox_m = np.zeros((H, W), bool)
        bbox_m[y0:y1, x0:x1] = True
        pupil = (((xx - cx) / 19.0) ** 2
                 + ((yy - cy) / 19.0) ** 2) < 1
        eye_px = bbox_m & (whitish | greenish | pupil)
        soft = np.asarray(
            Image.fromarray((eye_px * 255).astype(np.uint8))
            .filter(ImageFilter.GaussianBlur(1.2)),
            dtype=float) / 255.0
        sclera = np.zeros((H, W, 4), int)
        sclera[..., 0] = 242
        sclera[..., 1] = 244
        sclera[..., 2] = 240
        sclera[..., 3] = 255
        m = soft[..., None]
        out = (out * (1 - m) + sclera * m).astype(int)
        disc_m = (((xx - cx) / 26.0) ** 2
                  + ((yy - cy) / 26.0) ** 2) < 1
        disc = np.zeros((H, W, 4), int)
        disc[disc_m] = a[disc_m]
        dx, dy = 8, 2
        shifted = np.zeros((H, W, 4), int)
        shifted[dy:, dx:] = disc[:-dy, :-dx]
        sm = (shifted[..., 3] > 0) & (soft > 0.35)
        out[sm] = shifted[sm]
    return Image.fromarray(out.astype(np.uint8))


def main() -> None:
    base = Image.open(SPRITES / "base.png").convert("RGBA")
    make_sleepy(base).save(SPRITES / "sleepy.png")
    make_sneaky(base).save(SPRITES / "sneaky.png")
    print("wrote sleepy.png + sneaky.png")


if __name__ == "__main__":
    main()
