# MeshCore on the Cardputer Zero — research verdict (2026-11-17)

## The question

Meshtastic runs on the LoRa cap through `meshtasticd`. Can MeshCore
— a different mesh protocol, normally ESP32/nRF52 firmware — also
run natively on the Zero, as an alternate mode of the same SX1262
profile (never both at once; one radio, one owner)?

## What exists (researched 2026-11-17)

- **Upstream MeshCore has no Linux build.** Its platform families
  are ESP32 / nRF52 / RP2040 / STM32; the only `native` PlatformIO
  env is unit tests with mocked radios.
- **pyMC / pymc_core — the best route.** A Python reimplementation
  of the MeshCore protocol for Raspberry Pi-class Linux
  (`pip install pymc-core[hardware]`, pyMC-dev/pyMC_core), with an
  SPI SX1262 driver and a repeater daemon (pyMC_Repeater, lately
  also "openHop Repeater") that runs under systemd and exposes the
  MeshCore companion TCP interface. Actively maintained, US 915
  supported, protocol-compatible with the C++ reference. It is the
  same shape as lokicz itself: Python, a daemon, a supervisor.
- **ArduLinux repeater (PR #2025 to upstream, by l5yth).** The
  simple-repeater firmware compiled for Pi SBCs via an Arduino
  compatibility layer, RadioLib SX1262 driver, INI config, systemd
  unit. A live repeater runs it on a Pi 4B. Repeater-only, C++
  build chain, unmerged — a solid fallback, heavier than pyMC.
- **Native C++ ports** (dabeani/MeshCoreRPI, emergencyhamnet's
  meshcore-pi-port, ZephCore's Linux mode) prove the core runs on
  Pi-class hardware but are alpha, HAT-specific, and more work to
  own than pyMC.

## The cap problem (why it's an adaptation, not an install)

Every Linux route assumes a HAT-style SX1262 with some mix of:
a wired RESET line, GPIO chip-select, TXEN/RXEN pins. The Cap
LoRa-1262 (per zeroradio's verified hardware map) differs:

| Need | Cap reality | pyMC adaptation |
| --- | --- | --- |
| Chip select | kernel-managed, `/dev/spidev0.1` | use spidev CS, not a GPIO CS |
| RESET | **not wired** (power-on reset only) | reset pin = none; rely on POR |
| BUSY / DIO1 | GPIO22 / GPIO23 | matches wrapper parameters |
| TCXO | on DIO3, **mandatory** (else XOSC_START_ERR) | enable TCXO in SX126x config |
| RF switch | DIO2_AS_RF_SWITCH **and** PI4IOE expander P0 (I2C 0x43) | reuse `cap-lora-init.sh` for the expander half |
| Band plan | US 915 | pyMC US preset values |

## lokicz design

- Config gains `mesh_mode`: `meshtastic` | `meshcore` | `off`.
- `lokicz/meshcore.py` supervises the pyMC repeater service and
  enforces the one-radio rule: applying a mode stops the other
  daemon first. Meshtastic keeps its existing supervisor.
- Radio bring-up is deliberately **not** attempted until the LoRa
  cap is fitted (with its antenna — an unloaded PA can be damaged
  by TX). Until then: research ✓, supervisor ✓, pymc_core import
  smoke-tested on the device ✓, radio ✗ (needs the cap).

## Verdict

**Route exists — pyMC.** MeshCore mode is a cap-swap-day task:
fit cap + antenna, add the cap platform entry to pymc_core's
SX1262 wrapper, set `mesh_mode: meshcore`, apply, and verify
against a known MeshCore node (or the companion app).
