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


CONFIG_PATH = "/etc/openhop_repeater/config.yaml"
_SECRET_HINTS = ("secret", "password", "jwt", "private_key")
MASK = "__MASKED__"


def _flatten(obj, prefix: str = "") -> dict:
    """Nested config dict -> {dotted.path: scalar} leaves."""
    out = {}
    for key, val in (obj or {}).items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(val, dict):
            out.update(_flatten(val, path))
        else:
            out[path] = val
    return out


def read_config() -> dict:
    """The openHop config as flat dotted fields. Secret-looking
    values are masked — the portal never needs to see them, and
    a save that leaves the mask in place keeps the real value."""
    import yaml

    try:
        raw = open(CONFIG_PATH).read()
    except OSError as exc:
        return {"error": f"cannot read {CONFIG_PATH}: {exc}"}
    data = yaml.safe_load(raw) or {}
    fields = {}
    for path, val in _flatten(data).items():
        leaf = path.rsplit(".", 1)[-1].lower()
        if any(h in leaf for h in _SECRET_HINTS):
            fields[path] = MASK
        else:
            fields[path] = val
    return {"fields": fields, "active": pymc_active(),
            "installed": pymc_installed()}


def write_config(changes: dict) -> dict:
    """Apply dotted-path changes to the openHop YAML: validate,
    back up to config.yaml.lokicz-bak, install, and restart the
    repeater when it's running. Masked values are skipped (the
    real secret stays)."""
    import subprocess as sp

    import yaml

    data = yaml.safe_load(open(CONFIG_PATH).read()) or {}
    applied = []
    for path, raw in (changes or {}).items():
        if raw == MASK:
            continue
        node = data
        parts = path.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
            if not isinstance(node, dict):
                raise RuntimeError(f"{path}: blocked by a non-map value")
        leaf = parts[-1]
        current = node.get(leaf)
        if isinstance(current, bool):
            node[leaf] = raw is True or raw == "true"
        elif isinstance(current, int):
            node[leaf] = int(raw)
        elif isinstance(current, float):
            node[leaf] = float(raw)
        else:
            node[leaf] = str(raw)
        applied.append(path)
    if not applied:
        return {"applied": [], "note": "nothing changed"}
    text = yaml.safe_dump(data, sort_keys=True)
    yaml.safe_load(text)  # never install YAML we can't re-parse
    tmp = "/tmp/openhop-config-new.yaml"
    open(tmp, "w").write(text)
    sp.run(f"sudo -n cp {CONFIG_PATH} {CONFIG_PATH}.lokicz-bak",
           shell=True, capture_output=True, timeout=15)
    r = sp.run(f"sudo -n cp {tmp} {CONFIG_PATH}", shell=True,
               capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        raise RuntimeError("install failed: " + r.stderr.strip()[:160])
    note = "saved (backup at config.yaml.lokicz-bak)"
    if pymc_active():
        sp.run(f"sudo -n systemctl restart {PYMC_SERVICE}",
               shell=True, capture_output=True, timeout=30)
        note += "; repeater restarted"
    else:
        note += "; applies when the repeater next starts"
    return {"applied": sorted(applied), "note": note}


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
