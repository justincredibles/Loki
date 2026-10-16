"""The ONLY Loki code that talks to the ESP32-S3 coprocessor.

Everything Pi-side reaches the ESP32 through :class:`Esp32Client`, speaking
the Pi <-> ESP32 serial protocol (``docs/protocol/pi-esp32-serial.md``) over a
:class:`~loki.esp32link.transport.Transport`. No other module may open the
UART or format protocol messages.
"""

from . import protocol
from .client import Esp32Client, Esp32Error, ProtocolError
from .transport import FakeTransport, SerialTransport, Transport

__all__ = [
    "Esp32Client",
    "Esp32Error",
    "ProtocolError",
    "Transport",
    "SerialTransport",
    "FakeTransport",
    "protocol",
]
