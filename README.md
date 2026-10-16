# Loki

An all-in-one pocket cybersecurity multi-tool for your own lab — a Raspberry Pi brain plus an ESP32-S3 radio coprocessor on one custom HAT.

## What it is

Loki combines Wi-Fi network attacks and handshake capture, BLE, sub-GHz (CC1101), 2.4 GHz (nRF24L01+), infrared, NFC/RFID, and BadUSB into a single pocket device with a color display, 4-button navigation, a web UI, and a rechargeable battery.

- **Brain:** Raspberry Pi Zero 2 W (minimum), Pi 4, or Pi 5 — running Loki's own software on Raspberry Pi OS Lite
- **Coprocessor:** ESP32-S3 running a fork of Bruce firmware, driven by the Pi over a serial link
- **Board:** custom full-footprint PCB (85.6 x 56.5 mm — same size as the Pi itself) — display, radios, power management, USB-C charging
- **Kit model:** buy the assembled PCB, attach your own Pi, 3D-print the case, flash the image, go

## Status

Phase 1 (research) complete. Phase 2 (foundations) in progress.

## Repository layout

- `docs/` — architecture, research, build guide, and the Pi-ESP32 serial protocol spec
- `pi/` — Loki's original Pi software (clean-room; MIT)
- `firmware/` — ESP32-S3 firmware: our fork of Bruce (AGPL-3.0), linked as a submodule
- `hardware/` — PCB design files and enclosure (CERN-OHL-S)
- `payloads/` — sample BadUSB / sub-GHz payload files

## Licensing

- Loki Pi software and original code: MIT
- Hardware (PCB, schematics, enclosure): CERN-OHL-S
- Bruce fork: AGPL-3.0-or-later (see `firmware/`)

## Responsible use

Loki is a tool for learning and for testing networks and devices you own or are authorized to test.
