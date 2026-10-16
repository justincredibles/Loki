# firmware/ — ESP32-S3 firmware

Loki's ESP32-S3 runs a fork of Bruce firmware (AGPL-3.0-or-later), extended
with a serial command API so the Pi can drive it — see
`docs/protocol/pi-esp32-serial.md`.

**Fork:** [justincredibles/bruce-loki](https://github.com/justincredibles/bruce-loki)
(forked from [BruceDevices/firmware](https://github.com/BruceDevices/firmware), 2026-10-16)

The fork lives in its own repository so source-offer and release obligations
stay clean. It will be linked here as a git submodule when firmware work
begins:

```
git submodule add https://github.com/justincredibles/bruce-loki.git firmware/bruce-loki
```

Loki's board definition goes in as `boards/loki-hat/` in the fork,
upstream-style.

Key firmware work:

- Structured (machine-readable) response mode for Bruce's existing serial CLI
- Shared abort flag so `stop` works during long-running actions
- Headless operation (no physical button required)
- BadUSB via native USB HID (DuckyScript payloads on SD / LittleFS)
