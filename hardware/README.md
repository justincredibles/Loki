# hardware/ — PCB and enclosure

- `pcb/` — KiCad project, gerbers, BOM, and PCBA notes for the Loki HAT
  (85.6 x 56.5 mm — full Raspberry Pi footprint, 40-pin header)
- `enclosure/` — Fusion 360 source and STL files for the 3D-printed case

Design constraints:

- PCBA-friendly: JLCPCB Assembly target, common-library parts, modules over
  bare ICs, single-sided assembly where possible, fab test points
- Power system sized for a Pi 5 under load (the Zero 2 W just sips)
- Dedicated hardware UART routed between Pi and ESP32-S3, plus an ESP32
  reset line so the Pi can reflash the coprocessor

Hardware is licensed under CERN-OHL-S.
- WiFi attacks run on the Pi's onboard radio with the nexmon patch — no
  external USB WiFi adapter, so USB ports and enclosure stay as designed
