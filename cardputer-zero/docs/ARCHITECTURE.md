# Architecture — Pwnagotchi + Bjorn/Ragnar, on a Cardputer Zero

## The shape of the fork

Loki's main line is two halves: a Pi running Linux/Python tools, and an
ESP32 radio coprocessor. The Cardputer Zero collapses that into **one Linux
device**: the CM0 *is* the Pi-class computer, and the "coprocessors" are the
swappable caps on SPI. So this fork keeps Loki's Pi-side architecture
(Python services, a small core that coordinates tools, a local web UI) and
replaces the ESP32 half with a **cap profile layer**.

```
        ┌─────────────────────────────────────────────┐
        │  lokicz core (Python, systemd service)      │
        │  - job runner (arm-token safety, as in      │
        │    Loki's Pi↔ESP32 protocol, kept local)    │
        │  - web UI (status + tool control)           │
        ├──────────────┬──────────────┬───────────────┤
        │ Wi-Fi layer  │ Ragnar tools │ Cap profiles  │
        │ managed-mode │ scan/brute/  │ cc1101 | lora │
        │ recon now;   │ steal (LAN)  │ (one fitted)  │
        │ capture via  │              │               │
        │ USB dongle   │              │               │
        ├──────────────┴──────────────┴───────────────┤
        │ UI: framebuffer (/dev/fb_lcd) + evdev keys  │
        └─────────────────────────────────────────────┘
```

## Feature mapping

### From Pwnagotchi

| Feature | Verdict | Why |
|---|---|---|
| Network recon (see APs/clients) | ✅ Managed mode | Normal Wi-Fi scanning needs no special firmware |
| On-screen face/personality + stats | ✅ | Framebuffer UI; the Zero's colour LCD is nicer than e-paper |
| Handshake / PMKID capture | ❌ built-in radio · ✅ USB dongle | CYW43439 has no nexmon patch (see HARDWARE.md) |
| Deauth / frame injection | ❌ built-in radio · ✅ USB dongle | Same reason |
| bettercap underneath | ✅ (recon) | bettercap runs on Debian/arm64; its capture features inherit the radio limit |

### From Bjorn / Ragnar

| Feature | Verdict | Why |
|---|---|---|
| Host discovery, port scanning | ✅ | LAN-side; works over Wi-Fi or the built-in Ethernet |
| Vulnerability scanning | ✅ | Same — it's just network traffic |
| Brute force (SSH/FTP/etc.) | ✅ | Same |
| File stealing / exfil to device | ✅ | Same; mind the microSD size |
| Web UI | ✅ | Python web service, same as Ragnar's |
| Ragnar "advanced tools" tier | ❌ Out of scope | Ragnar's own installer already skips that tier on 512 MB-class hardware; the Zero has 512 MB total |

### From the caps (new vs Loki's PCB — same radios, new packaging)

| Cap | Loki-PCB equivalent | Notes |
|---|---|---|
| Cap CC1101 (CC1101) | Loki's EBYTE CC1101 module | Same chip family — Loki's sub-GHz plans carry over; SPI from Linux userspace instead of via the ESP32 |
| Cap CC1101 (ST25R3916 NFC) | Loki's external PN532 header | Different NFC chip, better specced; least mature software on the Zero — treat as experimental |
| Cap LoRa-1262 (SX1262 + GPS) | *(new — Loki has no LoRa)* | Meshtastic via native `meshtasticd` is already proven on this cap; a genuine addition, not a port |

## Design rules for this fork

1. **Radio profiles, not radio assumptions.** At startup the core loads
   exactly one cap profile (`cc1101`, `lora`, or `none`). Nothing in the
   core may assume a cap is present.
2. **The capture interface is configuration.** Wi-Fi capture code takes an
   interface name from config. Built-in radio = recon only; a USB dongle
   unlocks capture. Never hard-code `wlan0` as capturable.
3. **512 MB is the budget.** One Python core, tools run as short-lived jobs,
   no always-on extras. If it wouldn't fit on a Pi Zero 2 W, it doesn't ship.
4. **Own-lab use, same as Loki.** Arm-token gating for attack-class actions
   carries over from Loki's protocol design — a deliberate two-step before
   anything offensive runs.
5. **Reuse before rewrite.** Loki's `pi/loki` Python package is the starting
   point for the core; the CardputerZero org's SubG-Chat app is the reference
   for talking to the CC1101 cap; zeroradio's Meshtastic integration is the
   reference for the LoRa cap.

## Open questions (need hardware time)

- CC1101 GDO0 interrupt pin + one RF-switch line: unverified (HARDWARE.md).
- NFC (ST25R3916) from Linux on the Zero: how mature is the driver path?
- Which USB Wi-Fi dongles behave best on the CM0's USB hub for capture?
- Does the shipped OS image match the current CM0 datasheet's CYW43439, or
  did early units ship the CYW43459 named in datasheet Release 1? (The
  `dmesg` check answers this per-unit; the design doesn't change either way —
  neither chip has a nexmon port.)
