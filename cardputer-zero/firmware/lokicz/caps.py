"""Radio cap profiles for the Cardputer Zero's EXT expansion port.

Plain-English version: the Zero takes ONE cap at a time on its top port.
Both caps share the same SPI bus (SPI0) and the same chip-select line
(CS1, CM0 GPIO7) that the LCD doesn't use, so the firmware loads exactly
one profile — "cc1101", "lora", or "none" — and everything else in the
program talks to the profile, never to pins directly.

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

NONE = CapProfile(name="none", description="No cap fitted")

PROFILES = {p.name: p for p in (CC1101, LORA, NONE)}


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
    bring-up). So: LoRa fitted → the overlay line is parked as
    '<line>.disabled' in config.txt; CC1101 fitted → restored.
    Takes effect at the next boot. Returns what it did.
    """
    try:
        lines = BOOT_CONFIG.read_text().splitlines()
    except OSError:
        return "boot config unreadable — overlay not synced"
    parked = NFC_OVERLAY + ".disabled"
    changed = False
    out = []
    for ln in lines:
        if cap == "lora" and ln == NFC_OVERLAY:
            out.append(parked)
            changed = True
        elif cap != "lora" and ln == parked:
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
    return (f"boot overlay {'parked' if cap == 'lora' else 'restored'} "
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
