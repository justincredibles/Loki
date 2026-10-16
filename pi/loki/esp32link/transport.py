"""Line-oriented transports for the ESP32 link.

A transport moves whole lines of text between the Pi and the ESP32-S3.
The real hardware transport is :class:`SerialTransport` (UART via pyserial);
tests use :class:`FakeTransport`, an in-memory transport driven by a handler
callback that simulates the firmware.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable, Iterable, Optional, Protocol, runtime_checkable

from . import protocol


@runtime_checkable
class Transport(Protocol):
    """A bidirectional, line-oriented channel to the ESP32.

    Lines are exchanged without their trailing newline; implementations add
    and strip framing themselves.
    """

    def write_line(self, line: str) -> None:
        """Send one line to the ESP32."""
        ...

    def read_line(self, timeout: Optional[float] = None) -> Optional[str]:
        """Return the next line from the ESP32, or None on timeout."""
        ...

    def close(self) -> None:
        """Release the underlying channel."""
        ...


class SerialTransport:
    """UART transport backed by pyserial.

    pyserial is imported lazily inside ``__init__`` so this module (and the
    whole esp32link package) can be imported on machines without pyserial
    installed -- e.g. developer workstations running the test-suite against
    :class:`FakeTransport`.
    """

    def __init__(self, port: str, baudrate: int = protocol.BAUD_RATE) -> None:
        import serial  # lazy import: only needed on real hardware

        self._serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.05,
        )
        self._buf = bytearray()

    def write_line(self, line: str) -> None:
        self._serial.write(line.encode("utf-8") + b"\n")
        self._serial.flush()

    def read_line(self, timeout: Optional[float] = None) -> Optional[str]:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            idx = self._buf.find(b"\n")
            if idx >= 0:
                raw = bytes(self._buf[:idx])
                del self._buf[: idx + 1]
                return raw.decode("utf-8", errors="replace").rstrip("\r")
            if deadline is not None and time.monotonic() >= deadline:
                return None
            chunk = self._serial.read(256)
            if chunk:
                self._buf.extend(chunk)

    def close(self) -> None:
        self._serial.close()


#: Handler signature for FakeTransport: given one line written by the client,
#: return the lines the simulated firmware sends back (may be empty / None).
FakeHandler = Callable[[str], Optional[Iterable[str]]]


class FakeTransport:
    """In-memory transport for tests.

    Every line the client writes is recorded in :attr:`written` and passed to
    the handler; any lines the handler returns are queued for the client to
    read, in order. Use :meth:`feed` to inject an unsolicited line (e.g. an
    async event) at any moment.
    """

    def __init__(self, handler: Optional[FakeHandler] = None) -> None:
        self._handler = handler
        self.written: list[str] = []
        self._queue: deque[str] = deque()
        self._cond = threading.Condition()
        self.closed = False

    # -- test-side helpers ---------------------------------------------------

    def feed(self, line: str) -> None:
        """Queue a line as if the ESP32 had sent it spontaneously."""
        with self._cond:
            self._queue.append(line)
            self._cond.notify_all()

    # -- Transport interface --------------------------------------------------

    def write_line(self, line: str) -> None:
        with self._cond:
            self.written.append(line)
        if self._handler is not None:
            replies = self._handler(line)
            if replies:
                for reply in replies:
                    self.feed(reply)

    def read_line(self, timeout: Optional[float] = None) -> Optional[str]:
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._cond:
            while not self._queue:
                if deadline is None:
                    self._cond.wait()
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return None
                    self._cond.wait(remaining)
            return self._queue.popleft()

    def close(self) -> None:
        self.closed = True
        with self._cond:
            self._cond.notify_all()
