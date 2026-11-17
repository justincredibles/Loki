"""Wi-Fi layer — recon now, capture only through a USB dongle.

The Cardputer Zero's built-in Wi-Fi chip (Cypress CYW43439) has NO
monitor mode and NO frame injection: the nexmon firmware-patch project
covers the Pi Zero 2 W's chip, not this one. So:

- Recon (listing access points and clients) uses the built-in radio in
  its normal "managed" mode — that always works.
- Handshake/PMKID capture (the Pwnagotchi core trick) is only possible
  through a monitor-mode-capable USB Wi-Fi adapter in the USB-A port.
  The capture interface is therefore a CONFIG setting, never assumed.

Sanity check on a real unit:  dmesg | grep -i brcmfmac
(expect a brcmfmac43439 firmware line).
"""

import subprocess

BUILTIN_INTERFACE = "wlan0"  # CYW43439 — recon only, forever (no nexmon)


def list_access_points(interface: str = BUILTIN_INTERFACE) -> list[str]:
    """Managed-mode scan: SSIDs visible to `interface`. Works on the
    built-in radio. Returns raw scan lines for now.

    TODO: parse into structured AP records (ssid, bssid, channel,
    signal, security) and feed the UI + web UI, Pwnagotchi-style.
    """
    out = subprocess.run(
        ["iw", "dev", interface, "scan"],
        capture_output=True, text=True, timeout=30,
    )
    return out.stdout.splitlines()


def capture_available(capture_interface: str | None) -> bool:
    """True only if a capture-capable interface has been configured
    (i.e. a USB dongle). The built-in radio never qualifies."""
    return bool(capture_interface) and capture_interface != BUILTIN_INTERFACE


def start_handshake_capture(interface: str) -> None:
    """TODO: drive hcxdumptool/bettercap on the configured USB dongle
    interface. Refuse the built-in radio explicitly so nobody mistakes
    a silent no-op for a working capture."""
    if not capture_available(interface):
        raise RuntimeError(
            "Handshake capture needs a monitor-mode USB Wi-Fi adapter; "
            "the built-in CYW43439 cannot do it (no nexmon patch exists)."
        )
    raise NotImplementedError("capture driver not ported yet")
