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
    # The framebuffer expects raw RGB565 pixels on this panel.
    with open(FB_DEVICE, "wb") as fb:
        fb.write(img.convert("RGB").tobytes("raw", "BGR;16"))


def read_key() -> str | None:
    """TODO: open the TCA8418 evdev device and return the next key name.
    Stub for the skeleton — menu navigation lands with the real UI."""
    return None
