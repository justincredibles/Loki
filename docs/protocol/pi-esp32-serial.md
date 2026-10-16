# Pi - ESP32 Serial Protocol

Version: 0.1 (draft)
Status: Phase 2 — to be finalized before firmware work begins

## Transport

- Dedicated hardware UART between the Raspberry Pi and the ESP32-S3 (not USB-CDC:
  the ESP32-S3's single native USB is reserved for BadUSB HID and re-initializes
  during BadUSB runs).
- Baud rate and framing: TBD in v0.2.

## Command set (draft)

| Command   | Purpose |
|-----------|---------|
| `list`    | List available modules / payloads |
| `select`  | Select a module or payload |
| `arm`     | Arm a selected action (safety gate) |
| `run`     | Execute the armed action |
| `stop`    | Abort the running action |
| `status`  | Report current activity / state |
| `results` | Retrieve result files from ESP32 storage |

## Responses

- Machine-readable structured responses (format TBD — JSON lines under evaluation).
- Long-running actions must honor `stop` via a shared abort flag in the firmware.

## Notes

This protocol is the boundary between Loki's MIT-licensed Pi software and the
AGPL-3.0 Bruce fork. The two sides communicate only through this document.
