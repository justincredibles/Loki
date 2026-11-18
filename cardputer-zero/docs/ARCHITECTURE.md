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

## All-in-one scope (Justin's direction, 2026-11-17)

The fork is not just a Pwnagotchi/Ragnar port — the goal is one
pocket device that covers the whole field kit. Four more pillars,
all riding on the profile/mode model above (one cap at a time;
features declare which cap + radios they need):

| Pillar | Needs | Integration path |
|---|---|---|
| **Wardriving** | LoRa cap (GPS) + Wi-Fi | The LoRa cap's ATGM336H GPS sits on `/dev/ttyS0`; pair its fixes with Wi-Fi scans (built-in radio for breadth, dongle optional) and log WiGLE-style rows. Mode: `lora` profile, GPS + recon together. |
| **Meshtastic** | LoRa cap | Reuse, don't rewrite: native `meshtasticd` is already proven end-to-end on this exact cap (zeroradio). lokicz supervises it and speaks its client API. |
| **MeshCore** | LoRa cap | Same SX1262, alternate LoRa mode — Meshtastic and MeshCore are modes of the `lora` profile, never simultaneous on one radio. Exact Linux integration path (native build vs companion) is unverified — research before promising. |
| **Surveillance sniffer** | Wi-Fi + BLE (+ CC1101 as fitted) | Passive detection of surveillance tech by its wireless fingerprints: ALPR cameras (e.g. Flock-type) and other sensors advertise identifiable Wi-Fi/BLE signatures; DJI DroneID broadcasts are another known-detectable. A signature database built from public research, matched against the scans lokicz already does. Defensive/detection only — it spots the watchers, it doesn't jam or spoof them. |
| **Network audit (Bjorn-style)** | Wi-Fi (managed) | `lokicz/audit.py` (added 2026-11-17): nmap discovery of the connected LAN (ARP-enriched), top-100 port + service/version scan per host, and CVE correlation — each service's CPE is queried against the NVD API and every hit is stored with its CVSS score and canonical NVD link in a JSON report (`~/lokicz-audits/`). Findings from version-less CPE matches are flagged `version_unknown` (leads, not verdicts). Menu: page 1 → AUDIT, page 2 → LAST AUDIT. First live run on the home LAN: 14 hosts, 53 CVEs — the gateway's MiniUPnP 2.2.0 alone carried 51. |
| **Web portal** | Wi-Fi (managed) | `lokicz/web.py` + `webui.html` (added 2026-11-17): a stdlib HTTP server (`lokicz-web.service`, port 8420) exposing the whole app to any browser on the same LAN — status, capture, wardrive, sniff, sweep, audit, WPA-SEC, toggles, report browsing with clickable CVE links, captures + cracked list. Background jobs with progress; one hardware op at a time. LAN-open by design (Justin's call, Bjorn-style): no login, the network itself is the trust boundary. The LCD's page 2 shows the portal address. |

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

- NFC (ST25R3916) from Linux on the Zero: how mature is the driver path?
- MeshCore on Linux + this cap: native build or companion radio?
- ALPR/surveillance signature set: which fingerprints are reliable
  enough to ship without false-positive noise?

## Answered on hardware (2026-11-17)

- CC1101 GDO0 = GPIO14, RF_SW0 = GPIO15, RF_SW1 via CC1101 GDO2 —
  confirmed from M5Stack's official docs; chip live on SPI after the
  two-step power gate (see caps.py).
- USB capture dongle: Justin's TP-Link (Realtek RTL8822BU, in-kernel
  rtw88 driver) — monitor mode proven; it's the fork's capture radio.
- The shipped unit's Wi-Fi chip is the CYW43439 (`dmesg`: brcmfmac
  43439) — no nexmon, as designed for.
