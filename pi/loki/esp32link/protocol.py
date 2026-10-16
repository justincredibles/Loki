"""Constants for the Pi <-> ESP32 serial protocol, version 0.2.

This module mirrors the specification in ``docs/protocol/pi-esp32-serial.md``
(repo root). That document is the single source of truth; if it changes, this
module changes with it and PROTOCOL_VERSION is bumped to match.
"""

from __future__ import annotations

# --- Protocol identity -----------------------------------------------------

#: Protocol version implemented by this package (reported by the ESP32 in
#: the ``hello`` handshake; see spec section 4).
PROTOCOL_VERSION = "0.2"

#: Expected protocol major version. The client refuses to drive an ESP32
#: whose ``hello`` reports a different major version (spec section 4).
PROTOCOL_MAJOR = 0

# --- Transport (spec section 1) ---------------------------------------------

#: UART baud rate: 115200 8N1 over the dedicated Pi <-> ESP32-S3 hardware UART.
BAUD_RATE = 115200

#: Maximum line length in bytes (matches Bruce's serial command-queue packet).
MAX_LINE_LENGTH = 512

# --- Mode switching (spec section 2) ----------------------------------------

#: Line that switches the ESP32 from human mode into structured (JSON Lines)
#: mode.
BEGIN_COMMAND = "loki begin"

#: Line that returns the ESP32 to human mode.
END_COMMAND = "loki end"

# --- Error codes (spec section 8) -------------------------------------------

ERR_BAD_REQUEST = "bad_request"
ERR_UNKNOWN_COMMAND = "unknown_command"
ERR_NOT_ARMED = "not_armed"
ERR_BUSY = "busy"
ERR_NO_SUCH_MODULE = "no_such_module"
ERR_NO_SUCH_FILE = "no_such_file"
ERR_ABORTED = "aborted"
ERR_INTERNAL = "internal"

#: All error codes defined by the spec.
ERROR_CODES = frozenset(
    {
        ERR_BAD_REQUEST,
        ERR_UNKNOWN_COMMAND,
        ERR_NOT_ARMED,
        ERR_BUSY,
        ERR_NO_SUCH_MODULE,
        ERR_NO_SUCH_FILE,
        ERR_ABORTED,
        ERR_INTERNAL,
    }
)

# --- Async events (spec section 6) ------------------------------------------

EVENT_ACTION_STARTED = "action.started"
EVENT_ACTION_PROGRESS = "action.progress"
EVENT_ACTION_DONE = "action.done"
EVENT_ACTION_ABORTED = "action.aborted"
EVENT_ACTION_ERROR = "action.error"

#: All async event names defined by the spec.
EVENT_NAMES = frozenset(
    {
        EVENT_ACTION_STARTED,
        EVENT_ACTION_PROGRESS,
        EVENT_ACTION_DONE,
        EVENT_ACTION_ABORTED,
        EVENT_ACTION_ERROR,
    }
)


def major_of(version: str) -> int:
    """Extract the major version number from a ``"MAJOR.MINOR"`` string."""
    return int(str(version).split(".", 1)[0])
