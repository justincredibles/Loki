# Pi - ESP32 Serial Protocol

Version: 0.2
Status: Phase 2 baseline — firmware and Pi-side development build against this

## 1. Transport

- Dedicated hardware UART on the HAT (Pi UART to ESP32-S3 UART), 3.3 V TTL.
- 115200 baud, 8N1 (matches Bruce's serial default; revisit only if throughput hurts).
- NOT USB-CDC: the ESP32-S3's single native USB is reserved for BadUSB HID and
  re-initializes during BadUSB runs.
- Line-based: one message per line, LF-terminated. Max line length 512 bytes
  (matches Bruce's serial command-queue packet size).

## 2. Modes

- **Human mode** (default at boot): Bruce's existing text CLI, unchanged — for
  debugging from a terminal.
- **Structured mode**: entered by sending `loki begin`; every response becomes
  JSON Lines (section 3). `loki end` returns to human mode. The Pi always uses
  structured mode.

## 3. Structured message format

Request (Pi to ESP32):

```json
{"id": 7, "cmd": "run", "args": {"module": "badusb", "path": "/payloads/demo.txt"}}
```

Response (ESP32 to Pi):

```json
{"id": 7, "ok": true, "data": {"job": 3}}
{"id": 7, "ok": false, "error": {"code": "not_armed", "message": "arm required"}}
```

Async event (ESP32 to Pi, unsolicited):

```json
{"event": "action.done", "data": {"job": 3, "results": ["/loot/demo.pcap"]}}
```

Rules: `id` increments per session and is echoed in the response; malformed
JSON gets `bad_request`; an unknown `cmd` gets `unknown_command`.

## 4. Handshake

First structured command after `loki begin` is `hello`:

```json
{"id": 1, "cmd": "hello"}
{"id": 1, "ok": true, "data": {"protocol": "0.2", "firmware": "bruce-loki 0.1.0", "board": "loki-hat", "device": "esp32-s3"}}
```

The protocol major version must match what the Pi expects; on mismatch the Pi
refuses to drive the ESP32 and surfaces the mismatch in its UI.

## 5. Command set (v1 scope)

| Command | Args | Purpose |
|---------|------|---------|
| `hello` | — | Handshake / version check |
| `list` | `type`: `modules` \| `payloads` \| `files` | Enumerate; module list derives from Bruce's MainMenu table |
| `status` | — | Current activity: idle, or running module + job id + elapsed time |
| `arm` | `module`, `params` | Arm a destructive action; returns `arm_token` (valid 10 s) |
| `run` | `module`, `params`, `arm_token` when required | Start an action; returns immediately with a `job` id |
| `stop` | — | Abort the running action (shared abort flag) |
| `badusb.run` | `source`: `file` \| `buffer`, `path` or `data`, `layout` | Run a DuckyScript payload (Bruce `badusb` composite) |
| `storage.list` / `storage.read` / `storage.write` / `storage.delete` | `path`, ... | File ops on SD / LittleFS (Bruce storage commands) |
| `settings.get` / `settings.set` | `key`, `value` | Device settings |
| `power` | `action`: `reboot` \| `sleep` | Power control |

The arm gate mirrors Loki's on-device confirmation: attack-class actions
(BadUSB, RF transmit, deauth, etc.) require a fresh `arm_token`; read-only
commands (`list`, `status`, `storage.read`, `settings.get`) never do. The
ESP32 enforces the gate, not the Pi.

## 6. Long-running actions and stop

- `run` returns immediately; progress and completion arrive as events:
  `action.started`, `action.progress`, `action.done`, `action.aborted`,
  `action.error`.
- `stop` sets the firmware-wide abort flag; long-running module loops check it
  and exit, then emit `action.aborted`. Only one action runs at a time — a
  second `run` while busy gets `busy`.

## 7. Results

- Modules write results as files (PCAP, `.sub`, logs) to SD / LittleFS —
  Bruce's existing file-out pattern.
- The Pi retrieves them with `storage.list` + `storage.read` (binary payloads
  base64-encoded, chunked); CRC32 from Bruce's storage commands verifies
  transfers.

## 8. Error codes

`bad_request`, `unknown_command`, `not_armed`, `busy`, `no_such_module`,
`no_such_file`, `aborted`, `internal`.

## 9. Versioning

The protocol version is reported by `hello`. Any change to this document bumps
the version and adds a changelog line below. This spec is the boundary between
Loki's MIT-licensed Pi software and the AGPL-3.0 Bruce fork: the two sides
communicate only through this protocol.

## Changelog

- **0.2** (2026-10-16): transport fixed (hardware UART, 115200 8N1, 512-byte
  lines); structured JSON-Lines mode; handshake; job/event model; arm gate;
  error codes.
- **0.1**: initial draft (transport and framing TBD).
