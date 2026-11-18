"""Screen + keyboard for the Cardputer Zero.

The 320x170 ST7789v3 LCD is a plain Linux framebuffer at /dev/fb_lcd
(driver fb_st7789v): draw an image with Pillow, write its pixels to the
framebuffer, done. The 46-key keyboard (TCA8418) is a standard evdev
input device — read it like any USB keyboard.
"""

FB_DEVICE = "/dev/fb_lcd"
SCREEN_W, SCREEN_H = 320, 170


def show_text(lines: list[str]) -> None:
    """Draw simple status text to the LCD.

    TODO: replace with the real face/status UI (Pwnagotchi-style mood +
    recon stats), reusing Loki's Pi-side UI ideas at 320x170.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (SCREEN_W, SCREEN_H), "black")
    draw = ImageDraw.Draw(img)
    y = 8
    for line in lines:
        draw.text((8, y), line, fill="white")
        y += 18
    # The framebuffer expects raw RGB565 pixels on this panel. Pack them
    # by hand: Pillow's "BGR;16" raw encoder is missing from some builds
    # (confirmed on the Zero's stock image, 2026-11-17).
    with open(FB_DEVICE, "wb") as fb:
        fb.write(_to_rgb565(img))


def _to_rgb565(img) -> bytes:
    """Pack an RGB Pillow image into little-endian RGB565 bytes."""
    data = img.convert("RGB").tobytes()
    out = bytearray(SCREEN_W * SCREEN_H * 2)
    for i in range(SCREEN_W * SCREEN_H):
        r, g, b = data[3 * i], data[3 * i + 1], data[3 * i + 2]
        v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        out[2 * i] = v & 0xFF
        out[2 * i + 1] = v >> 8
    return bytes(out)


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
