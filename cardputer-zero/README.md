# Loki — Cardputer Zero fork

A fork of the [Loki](../README.md) pocket security multi-tool, retargeted from
Loki's custom PCB to the **M5Stack Cardputer Zero**.

Loki's firmware idea — **Pwnagotchi's Wi-Fi brain + Bjorn/Ragnar's network
toolkit, in one pocket device** — carried onto a device you can buy off the
shelf: a pocket Linux computer with a keyboard, a colour screen, and swappable
radio caps on top.

## The one-paragraph version

The Cardputer Zero is **not** an ESP32 gadget. Inside is a **Raspberry Pi
Compute Module 0 (CM0)** — the same class of chip as a Pi Zero 2 W — running
Raspberry Pi OS (Debian, 64-bit) from a microSD card. So this fork is a
**Linux/Python port**, a sibling of Loki's existing Pi-side code in `../pi/`,
not a Bruce-style ESP32 firmware. (Bruce, Marauder and friends are ESP32-S3
firmware for the *original* Cardputer — they cannot run on the Zero.)

## What works, what's blocked — read this first

| Capability | Status on Cardputer Zero |
|---|---|
| Ragnar/Bjorn network tools (host scan, port scan, vuln scan, brute force, file stealing, web UI) | ✅ Maps cleanly — these only need a network connection, and the Zero has Wi-Fi **and** built-in Ethernet |
| Pwnagotchi-style recon + on-screen personality | ✅ In managed mode (normal Wi-Fi scanning) |
| **Pwnagotchi handshake / PMKID capture, deauth** | ❌ **Blocked on the built-in radio** — see below |
| Sub-GHz (Cap CC1101 fitted) | ✅ CC1101 on SPI, proven from Linux by M5Stack's own apps |
| LoRa / Meshtastic (Cap LoRa-1262 fitted) | ✅ SX1262 on SPI; native `meshtasticd` already proven on this exact cap |
| NFC (part of the CC1101 cap) | ⚠️ ST25R3916 on the cap; support on the Zero is the least mature piece |

**The monitor-mode problem, in plain English:** capturing Wi-Fi handshakes
needs the Wi-Fi chip to listen promiscuously ("monitor mode") and inject
frames. On the Pi Zero 2 W that works because the *nexmon* project patched
that chip's firmware. The Cardputer Zero's CM0 carries a **different Wi-Fi
chip (Cypress CYW43439)** and **nexmon has no patch for it** — so the built-in
radio can never do handshake capture. The workaround is the same one other Pi
tools use: plug a monitor-mode-capable **USB Wi-Fi adapter** into the USB-A
port and capture with that. First check on real hardware:
`dmesg | grep -i brcmfmac` confirms which chip/firmware your unit shipped.

**One cap at a time:** the Zero has a single expansion port and both caps
claim the same SPI chip-select, so the firmware treats the fitted cap as a
*radio profile* (CC1101 **or** LoRa **or** none) instead of Loki PCB's
all-radios-at-once design.

## Layout of this fork

- `docs/HARDWARE.md` — the device and both caps, with the exact pins and
  device paths, in plain English.
- `docs/ARCHITECTURE.md` — how Pwnagotchi + Bjorn/Ragnar features map onto
  this hardware, what carries over from Loki's Pi code, and the blockers.
- `docs/RESEARCH.md` — the full platform research with sources (2026-11-17).
- `firmware/` — the Python firmware skeleton (`lokicz` package).

## Status

Scaffold only (2026-11-17). The radio-profile layer, framebuffer UI and
managed-mode recon are stubbed with the verified hardware facts baked in;
nothing here has run on a physical Cardputer Zero yet.
