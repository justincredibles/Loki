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

    An active scan needs CAP_NET_ADMIN, which a plain user lacks
    (confirmed on hardware 2026-11-17: "Operation not permitted"), so
    fall back to passwordless sudo where available, then to the
    kernel's cached scan results (`scan dump`, unprivileged).

    TODO: parse into structured AP records (ssid, bssid, channel,
    signal, security) and feed the UI + web UI, Pwnagotchi-style.
    """
    attempts = [
        ["iw", "dev", interface, "scan"],
        ["sudo", "-n", "iw", "dev", interface, "scan"],
        ["iw", "dev", interface, "scan", "dump"],
    ]
    for cmd in attempts:
        try:
            out = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if out.returncode == 0 and "BSS " in out.stdout:
            return out.stdout.splitlines()
    return []


def _channel(freq_mhz: int) -> int:
    if 2412 <= freq_mhz <= 2472:
        return (freq_mhz - 2407) // 5
    if freq_mhz == 2484:
        return 14
    if 5000 < freq_mhz < 5900:
        return (freq_mhz - 5000) // 5
    return 0


def scan_aps(interface: str = BUILTIN_INTERFACE) -> list[dict]:
    """Structured AP records from a managed-mode scan.

    Each record: {bssid, ssid, freq_mhz, channel, signal_dbm, auth}
    where auth is a WiGLE-style string like "[WPA2-PSK][ESS]" or
    "[ESS]" for an open network. Parsing is best-effort — `iw` output
    is a text format, not an API — but every field here is one the
    wardriving logger and the UI genuinely need.
    """
    aps: list[dict] = []
    current: dict | None = None
    in_rsn = in_wpa = False
    for line in list_access_points(interface):
        stripped = line.strip()
        if line.startswith("BSS "):
            if current:
                aps.append(current)
            current = {"bssid": stripped.split()[1].split("(")[0],
                       "ssid": "", "freq_mhz": 0, "channel": 0,
                       "signal_dbm": 0.0, "auth": "[ESS]"}
            in_rsn = in_wpa = False
            continue
        if current is None:
            continue
        if stripped.startswith("freq:"):
            current["freq_mhz"] = int(float(stripped.split()[1]))
            current["channel"] = _channel(current["freq_mhz"])
        elif stripped.startswith("signal:"):
            current["signal_dbm"] = float(stripped.split()[1])
        elif stripped.startswith("SSID:"):
            current["ssid"] = stripped[5:].strip()
        elif stripped.startswith("RSN:"):
            in_rsn, in_wpa = True, False
        elif stripped.startswith("WPA:"):
            in_wpa, in_rsn = True, False
        elif "Authentication suites:" in stripped:
            suites = stripped.split(":", 1)[1]
            if "SAE" in suites:
                current["auth"] = "[WPA3-SAE][ESS]"
            elif "PSK" in suites:
                current["auth"] = "[WPA2-PSK][ESS]" if in_rsn else "[WPA-PSK][ESS]"
            elif "802.1X" in suites:
                current["auth"] = "[WPA2-EAP][ESS]" if in_rsn else "[WPA-EAP][ESS]"
    if current:
        aps.append(current)
    return aps


def capture_available(capture_interface: str | None) -> bool:
    """True only if a capture-capable interface has been configured
    (i.e. a USB dongle). The built-in radio never qualifies."""
    return bool(capture_interface) and capture_interface != BUILTIN_INTERFACE


def start_handshake_capture(interface: str) -> None:
    """Handshake capture lives in lokicz.capture (hcxdumptool on the
    dongle). This guard stays so nobody mistakes the built-in radio
    for a capture device."""
    if not capture_available(interface):
        raise RuntimeError(
            "Handshake capture needs a monitor-mode USB Wi-Fi adapter; "
            "the built-in CYW43439 cannot do it (no nexmon patch exists)."
        )
    from .capture import run_capture

    run_capture(iface=interface)
