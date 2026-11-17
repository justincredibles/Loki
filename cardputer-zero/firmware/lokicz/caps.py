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
        # Verified from the CardputerZero org's SubG-Chat app:
        "Cap power enable is CM0 GPIO26 (POWER_EN) — cap is dead until set.",
        "NFC chip select is a GPIO22 device-tree overlay (not kernel CS1).",
        # TODO-VERIFY: GDO0 interrupt pin (evidence points at GPIO14/15)
        # and one RF-switch control line are not yet confirmed on hardware.
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
