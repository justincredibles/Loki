"""Radio cap profiles for the Cardputer Zero's EXT expansion port.

Plain-English version: the Zero takes ONE cap at a time on its top port.
Both caps share the same SPI bus (SPI0) and the same chip-select line
(CS1, CM0 GPIO7) that the LCD doesn't use, so the firmware loads exactly
one profile — "cc1101", "lora", "tft", or "none" — and everything else
in the program talks to the profile, never to pins directly.

Every constant below is a verified hardware fact from docs/HARDWARE.md.
Anything not yet verified on real hardware is marked TODO-VERIFY.
"""

from dataclasses import dataclass, field


@dataclass
class CapProfile:
    """What the core needs to know about the fitted cap."""

    name: str
    description: str
    spi_device: str = "/dev/spidev0.1"  # SPI0, chip-select 1 — both caps
    notes: list = field(default_factory=list)


# --- Cap CC1101 (M5Stack U219): TI CC1101 sub-GHz + ST25R3916 NFC ---------
CC1101 = CapProfile(
    name="cc1101",
    description="TI CC1101 sub-GHz (315/433/868/915 MHz) + ST25R3916 NFC",
    notes=[
        # Power is a TWO-STEP software gate (M5Stack official docs,
        # proven on hardware 2026-11-17):
        "1) EXT 5V rail ON: echo 1 > /sys/class/leds/ext_5v_out/brightness"
        " (root; the rail is OFF by default and the cap is dead without it).",
        "2) Cap power enable = CM0 GPIO26 (POWER_EN), held high.",
        "Leave BOTH enables on while the cap is fitted — the cap shares"
        " SPI0 with the LCD and cutting its power can freeze the display.",
        # RE-CONFIRMED the hard way 2026-11-18: the code cycled
        # POWER_EN per radio session anyway, and the panel froze
        # after EVERY session — app healthy behind a still frame,
        # driver rebinds useless, only a reboot revived it.
        # cc1101._power_on() now holds the line for good.
        "POWER_EN is held, never cycled per session (2026-11-18).",
        # Confirmed on our hardware 2026-11-17 after enabling power:
        "CC1101 answers on spidev0.1: PARTNUM 0x00, VERSION 0x14,"
        " MARCSTATE 0x01 (idle) — a genuine, live chip.",
        # GDO0 pin — CORRECTED by experiment 2026-11-17: published
        # tables say GPIO14, but with GDO0 set to the crystal-clock
        # output only GPIO15 toggled (2,168 edges/s of polling;
        # 14/22/23 sat still). The pin idles as the mini-UART's
        # RXD1; claiming it as a GPIO input is correct while this
        # cap is fitted. GPIO14's role on this cap is unconfirmed.
        "GDO0 = GPIO15 (proven by the clock-output test, 2026-11-17).",
        "RF_SW1 is NOT a host pin: it is the CC1101's GDO2, set over SPI"
        " via IOCFG2. Bands (SW0/SW1): 0/0=315, 0/1=433, 1/1=868/915 MHz.",
        "NFC chip select is a GPIO22 device-tree overlay (not kernel CS1).",
    ],
)

# --- Cap LoRa-1262 (M5Stack U214): Semtech SX1262 + ATGM336H GPS ----------
LORA = CapProfile(
    name="lora",
    description="Semtech SX1262 LoRa (868-923 MHz, region set in software) + GPS",
    notes=[
        # Verified on real hardware by the zeroradio project:
        "DIO1 interrupt = GPIO23, BUSY = GPIO22.",
        "RESET is NOT wired — recover the radio by re-init over SPI.",
        "TCXO reference: the driver MUST be configured for a TCXO.",
        "RF switch: PI4IOE5V6408 I2C expander at 0x43, pin P0 held high.",
        "GPS (ATGM336H) appears on /dev/ttyS0.",
        "Antenna on the RP-SMA connector is mandatory before transmitting.",
    ],
)

# --- Display hat: HiLetgo 2.8" ILI9341 SPI touch panel (not a radio) ------
TFT = CapProfile(
    name="tft",
    description='2.8" ILI9341 SPI display hat (240x320, run 320x240 '
                "landscape) + XPT2046 resistive touch — no radio",
    notes=[
        # Wiring map lives in docs/DISPLAY-HAT.md (EXT header labels
        # confirmed from Justin's unit, 2026-11-19):
        "Display on spidev0.1 (SPI0 CS1): RESET = GPIO22, DC = GPIO23,"
        " MOSI/SCK/MISO shared with the bus. Touch (phase 2):"
        " T_CS = GPIO15, T_IRQ = GPIO14.",
        # GPIO22 is the panel's RESET line in this profile, so the
        # NFC chip-select overlay (which claims GPIO22) must stay
        # PARKED — sync_boot_overlay() treats 'tft' like 'lora'.
        "NFC overlay parked in this profile (GPIO22 is spoken for).",
        # Same shared-bus power rule as the radio caps:
        "Power: EXT 5V rail + GPIO26 POWER_EN on once and held — the"
        " driver reuses cc1101._power_on(); cycling cap power desyncs"
        " the built-in LCD on the shared SPI0 bus (release 0.36).",
        "Driver: lokicz/ili9341.py — PROVEN on the real panel"
        " 2026-11-19 (test pattern correct at 40 MHz, MADCTL"
        " 0x28); the app renders to it in the tft profile (0.40).",
    ],
)

NONE = CapProfile(name="none", description="No cap fitted")

PROFILES = {p.name: p for p in (CC1101, LORA, TFT, NONE)}


import subprocess
from pathlib import Path

BOOT_CONFIG = Path("/boot/firmware/config.txt")
NFC_OVERLAY = "dtoverlay=spi0-spidev2-gpio22-overlay"


def sync_boot_overlay(cap: str) -> str:
    """Keep the NFC chip-select overlay in step with the fitted cap.

    The NFC overlay claims GPIO22 as an SPI chip-select. On the
    LoRa cap that same pin is the SX1262's BUSY line — with the
    overlay loaded, meshtasticd's GPIO request fails and the
    daemon aborts (proven live 2026-11-17, at the first LoRa
    bring-up). On the display hat the same pin is the panel's
    RESET line, claimed by the ili9341 driver — same collision,
    same remedy. So: LoRa or display hat fitted → the overlay
    line is parked as '<line>.disabled' in config.txt; anything
    else fitted → restored. Takes effect at the next boot.
    Returns what it did.
    """
    # Profiles where GPIO22 belongs to the fitted hardware, so
    # the NFC overlay must stay parked.
    parks = cap in ("lora", "tft")
    try:
        lines = BOOT_CONFIG.read_text().splitlines()
    except OSError:
        return "boot config unreadable — overlay not synced"
    parked = NFC_OVERLAY + ".disabled"
    changed = False
    out = []
    for ln in lines:
        if parks and ln == NFC_OVERLAY:
            out.append(parked)
            changed = True
        elif not parks and ln == parked:
            out.append(NFC_OVERLAY)
            changed = True
        else:
            out.append(ln)
    if not changed:
        return "boot overlay already matches the cap profile"
    r = subprocess.run("sudo -n tee /boot/firmware/config.txt >/dev/null",
                       shell=True, input="\n".join(out) + "\n",
                       capture_output=True, text=True)
    if r.returncode != 0:
        return "boot overlay edit FAILED (sudo refused?)"
    return (f"boot overlay {'parked' if parks else 'restored'} "
            f"for the {cap} cap — applies at next boot")


def detect_cap(configured: str | None = None) -> CapProfile:
    """Return the active cap profile.

    There is no reliable electrical auto-detection on the EXT port yet,
    so for now the profile comes from configuration (set at install time
    or from the on-device menu). TODO: probe SPI for the SX1262/CC1101
    part numbers and auto-detect when both probes prove safe.
    """
    if configured is None:
        return NONE
    return PROFILES.get(configured.lower(), NONE)
