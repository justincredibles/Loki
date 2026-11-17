# lokicz — Cardputer Zero firmware (skeleton)

Python firmware for the Loki Cardputer Zero fork. Runs on the device's
Raspberry Pi OS as a normal Python package — there is no flashing step;
install it, run it as a systemd service, done.

## Modules

| File | Job |
|---|---|
| `lokicz/caps.py` | Radio profiles for the expansion caps (CC1101 / LoRa / none) with the verified pins and device paths |
| `lokicz/wifi_recon.py` | Wi-Fi recon in managed mode; capture is gated behind a configured USB-dongle interface |
| `lokicz/ui.py` | Screen (framebuffer `/dev/fb_lcd`) and keyboard (evdev) helpers |
| `lokicz/main.py` | Entry point: detect cap, start core, print status |

## Run it (on the device)

```sh
pip install -r requirements.txt
python -m lokicz.main
```

## Status

Skeleton, 2026-11-17. The hardware constants are the verified ones from
`../docs/HARDWARE.md`; the tool implementations (Ragnar-style scanners,
bettercap integration) are stubs marked TODO, to be ported from Loki's
`pi/loki` package and Ragnar's published behaviour — for use on your own
lab networks, same rule as the rest of Loki.
