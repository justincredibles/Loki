"""MeshCore supervision — the alternate mesh mode for the LoRa cap.

Research verdict (docs/MESHCORE.md): upstream MeshCore has no
Linux build, but pyMC — a Python reimplementation of the protocol
with an SPI SX1262 driver and a systemd repeater daemon — is a
real, maintained route that matches lokicz's own shape.

This module is the supervisor half, mirroring meshtastic.py:
- `mesh_mode` in the config picks which mesh stack owns the
  SX1262: "meshtastic", "meshcore", or "off". ONE radio, ONE
  owner — apply_mode() stops the other daemon first, always.
- status() reports what's actually true: pyMC repeater service
  state, meshtasticd state, and the configured mode.

Radio-level proof LANDED 2026-11-17 (LoRa cap fitted): pyMC's
SX1262Radio initialized the cap's radio at 915 MHz with
reset_pin=-1 accepted (no reset line on this cap) and read a
live −99 dBm noise floor. The venv needs two extra packages
beyond pymc-core: python-periphery (GPIO) and spidev (LoRaRF's
SPI).

Service LANDED 2026-11-17 (evening): pyMC_Repeater upstream
became openHop Repeater (openhop-dev/openhop_repeater, built on
openhop_core); installed via its manage.sh (main branch) —
/opt/openhop_repeater, config /etc/openhop_repeater/config.yaml,
unit `openhop-repeater`, dashboard :8000. Radio config mirrors
the proven probe: spidev0.1, cs_pin -1, busy 22, dio1 23,
reset -1, DIO3 TCXO 1.8 V, DIO2 RF switch; US MeshCore air
params 915 MHz / BW 62.5 / SF8 / CR8 / sync 0x12. A systemd
drop-in runs cap-lora-init before start (the cap's power gate
and I2C RF switch are lokicz bring-up, not the repeater's job).
"""

import subprocess

PYMC_SERVICE = "openhop-repeater"  # pyMC_Repeater became openHop


def _run(cmd: str, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True,
                          text=True, timeout=timeout)


def pymc_installed() -> bool:
    """The repeater daemon's presence, by its systemd unit."""
    r = _run(f"systemctl list-unit-files {PYMC_SERVICE}.service")
    return PYMC_SERVICE in r.stdout


def pymc_active() -> bool:
    return _run(f"systemctl is-active {PYMC_SERVICE}").stdout.strip() == "active"


def apply_mode(mode: str, cap: str) -> str:
    """Make `mode` the mesh stack that owns the radio.

    Only meaningful with the LoRa cap fitted; with any other cap
    both daemons stay parked regardless of mode.
    """
    from . import meshtastic

    if cap != "lora":
        meshtastic.apply_profile(cap)
        _run(f"sudo -n systemctl stop {PYMC_SERVICE}")
        return f"mesh mode '{mode}' noted — LoRa cap not fitted, both parked"
    if mode == "meshcore":
        meshtastic.apply_profile("none")  # stops + disables meshtasticd
        if not pymc_installed():
            return ("mode set to meshcore + meshtasticd parked, but the "
                    "pyMC repeater service is not installed yet (the "
                    "pyMC radio layer itself is proven on this cap — "
                    "docs/MESHCORE.md)")
        _run(f"sudo -n systemctl enable --now {PYMC_SERVICE}")
        return "MeshCore (pyMC repeater) enabled; meshtasticd parked"
    if mode == "meshtastic":
        _run(f"sudo -n systemctl stop {PYMC_SERVICE}")
        _run(f"sudo -n systemctl disable {PYMC_SERVICE}")
        return meshtastic.apply_profile("lora")
    meshtastic.apply_profile("none")
    _run(f"sudo -n systemctl stop {PYMC_SERVICE}")
    _run(f"sudo -n systemctl disable {PYMC_SERVICE}")
    return "mesh off — both daemons parked"


def status() -> dict:
    from . import config, meshtastic

    return {"mode": config.load().get("mesh_mode", "meshtastic"),
            "pymc_installed": pymc_installed(),
            "pymc_active": pymc_active(),
            "meshtastic": meshtastic.status()}


def main() -> int:
    import sys

    if "--apply-mode" in sys.argv:
        from . import config

        cfg = config.load()
        print(apply_mode(cfg.get("mesh_mode", "meshtastic"), cfg["cap"]))
        return 0
    s = status()
    lines = [
        "MeshCore (pyMC)",
        f"configured mode: {s['mode']}",
        "pyMC repeater: " + ("active" if s["pymc_active"] else
                             "installed, stopped" if s["pymc_installed"]
                             else "not installed"),
        "meshtasticd: " + ("active" if s["meshtastic"]["service"]
                           else "parked"),
    ]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
