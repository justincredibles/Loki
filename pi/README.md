# pi/ — Loki Pi software

Loki's original, clean-room Pi-side software (MIT). Behavior was studied from
reference projects (Pwnagotchi, Ragnar); no code is copied from them.

## Layout (planned)

- `loki/orchestrator/` — epoch engine: the central loop everything consumes
- `loki/mood/` — personality / state machine (clean-room reimplementation)
- `loki/modules/` — wrappers around the pinned engines (see `installer/engines.lock`)
- `loki/esp32link/` — the ONLY code that talks to the ESP32, via the serial protocol in `docs/protocol/`
- `loki/plugins/` — single-file plugins with `on_*` hooks
- `loki/ui/` — display drivers (ILI9341-class first) and 4-button navigation
- `loki/web/` — web UI for remote config and control
- `config/` — TOML defaults
- `systemd/` — unit files (engines run as independent services)
- `installer/` — install script, engine pins, image builder
- `tests/`

## Key decisions

- WiFi monitor mode: nexmon firmware patch on the Pi's onboard radio — no
  external USB WiFi adapter in the design. (Decided 2026-10-16.)
