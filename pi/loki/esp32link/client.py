"""Synchronous client for the ESP32-S3 coprocessor.

Implements the Pi side of the Pi <-> ESP32 serial protocol v0.2
(``docs/protocol/pi-esp32-serial.md``). A background reader thread demultiplexes
the line stream: responses are matched to in-flight requests by ``id``, and
unsolicited async events are collected for :meth:`Esp32Client.poll_events`
(and/or pushed to an optional ``on_event`` callback).

Typical use::

    client = Esp32Client(SerialTransport("/dev/ttyAMA0"))
    hello = client.connect()          # 'loki begin' + hello handshake
    token = client.arm("badusb", {"path": "/payloads/demo.txt"})
    job = client.run("badusb", {"path": "/payloads/demo.txt"}, arm_token=token)
    ...
    client.close()
"""

from __future__ import annotations

import json
import threading
from typing import Any, Callable, Dict, List, Optional

from . import protocol
from .transport import Transport


class Esp32Error(Exception):
    """The ESP32 answered a request with ``ok: false`` (spec section 3)."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message


class ProtocolError(Exception):
    """The link itself failed: timeout, malformed traffic, or a protocol
    version mismatch during the handshake (spec section 4)."""


EventCallback = Callable[[str, Dict[str, Any]], None]


class _Pending:
    __slots__ = ("event", "response")

    def __init__(self) -> None:
        self.event = threading.Event()
        self.response: Optional[Dict[str, Any]] = None


class Esp32Client:
    """Drives the ESP32 over a :class:`~loki.esp32link.transport.Transport`."""

    def __init__(
        self,
        transport: Transport,
        timeout: float = 10.0,
        on_event: Optional[EventCallback] = None,
    ) -> None:
        self._transport = transport
        self._timeout = timeout
        self._on_event = on_event

        self._write_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._pending: Dict[int, _Pending] = {}
        self._next_id = 0
        self._events: List[Dict[str, Any]] = []

        self._reader: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._connected = False

        #: Data dict from the ``hello`` handshake, set by :meth:`connect`.
        self.hello_info: Optional[Dict[str, Any]] = None

    # -- lifecycle ------------------------------------------------------------

    def connect(self) -> Dict[str, Any]:
        """Enter structured mode and perform the ``hello`` handshake.

        Raises :class:`ProtocolError` if the ESP32 reports a protocol major
        version different from the one this package implements (spec
        section 4) -- the Pi refuses to drive an incompatible coprocessor.
        """
        if self._connected:
            raise ProtocolError("client is already connected")
        self._stop.clear()
        self._reader = threading.Thread(
            target=self._reader_loop, name="esp32link-reader", daemon=True
        )
        self._reader.start()
        self._write_line(protocol.BEGIN_COMMAND)
        info = self.hello()
        try:
            major = protocol.major_of(info["protocol"])
        except (KeyError, ValueError, AttributeError) as exc:
            raise ProtocolError(f"malformed hello response: {info!r}") from exc
        if major != protocol.PROTOCOL_MAJOR:
            raise ProtocolError(
                "protocol version mismatch: ESP32 reports "
                f"{info['protocol']!r}, this package implements "
                f"{protocol.PROTOCOL_VERSION} (major {protocol.PROTOCOL_MAJOR})"
            )
        self.hello_info = info
        self._connected = True
        return info

    def close(self) -> None:
        """Leave structured mode (``loki end``) and close the transport."""
        if self._connected:
            try:
                self._write_line(protocol.END_COMMAND)
            except Exception:
                pass  # best effort: the link may already be gone
        self._connected = False
        self._stop.set()
        try:
            self._transport.close()
        finally:
            if self._reader is not None:
                self._reader.join(timeout=1.0)
                self._reader = None

    def __enter__(self) -> "Esp32Client":
        self.connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- core request/response -------------------------------------------------

    def request(
        self,
        cmd: str,
        args: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Send one structured command and wait for its response.

        Returns the response's ``data`` payload. Raises :class:`Esp32Error`
        for an ``ok: false`` answer and :class:`ProtocolError` on timeout.
        """
        if self._reader is None or self._stop.is_set():
            raise ProtocolError("client is not connected")
        with self._state_lock:
            self._next_id += 1
            request_id = self._next_id
            pending = _Pending()
            self._pending[request_id] = pending

        message: Dict[str, Any] = {"id": request_id, "cmd": cmd}
        if args is not None:
            message["args"] = args
        self._write_line(json.dumps(message))

        wait = self._timeout if timeout is None else timeout
        if not pending.event.wait(wait):
            with self._state_lock:
                self._pending.pop(request_id, None)
            raise ProtocolError(
                f"timed out after {wait:.1f}s waiting for response to {cmd!r} "
                f"(id {request_id})"
            )
        response = pending.response or {}
        if response.get("ok"):
            return response.get("data")
        error = response.get("error") or {}
        raise Esp32Error(
            str(error.get("code", protocol.ERR_INTERNAL)),
            str(error.get("message", "")),
        )

    # -- events -----------------------------------------------------------------

    def poll_events(self) -> List[Dict[str, Any]]:
        """Drain the async events received since the last call.

        Each event is the raw message dict: ``{"event": name, "data": {...}}``.
        """
        with self._state_lock:
            events, self._events = self._events, []
        return events

    # -- command surface (spec section 5) ---------------------------------------

    def hello(self) -> Dict[str, Any]:
        """Handshake / version check. Returns the hello data dict."""
        return self.request("hello")

    def list(self, type: str) -> Any:  # noqa: A003 - mirrors the spec's command name
        """Enumerate ``modules``, ``payloads`` or ``files``."""
        return self.request("list", {"type": type})

    def status(self) -> Any:
        """Current activity: idle, or running module + job id + elapsed."""
        return self.request("status")

    def arm(self, module: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Arm a destructive action; returns the ``arm_token`` (valid 10 s)."""
        data = self.request("arm", {"module": module, "params": params or {}})
        return data["arm_token"]

    def run(
        self,
        module: str,
        params: Optional[Dict[str, Any]] = None,
        arm_token: Optional[str] = None,
    ) -> int:
        """Start an action; returns immediately with the job id.

        Attack-class modules require a fresh ``arm_token`` from :meth:`arm`;
        without one the ESP32 answers ``not_armed`` (raised as
        :class:`Esp32Error`).
        """
        args: Dict[str, Any] = {"module": module, "params": params or {}}
        if arm_token is not None:
            args["arm_token"] = arm_token
        data = self.request("run", args)
        return data["job"]

    def stop(self) -> Any:
        """Abort the running action (firmware-wide abort flag)."""
        return self.request("stop")

    def badusb_run(
        self,
        path: Optional[str] = None,
        data: Optional[str] = None,
        layout: Optional[str] = None,
        arm_token: Optional[str] = None,
    ) -> Any:
        """Run a DuckyScript payload via the Bruce ``badusb`` composite.

        Pass ``path`` for a payload file on the ESP32 (SD / LittleFS) or
        ``data`` for an inline payload buffer. BadUSB is attack-class, so a
        fresh ``arm_token`` may be supplied the same way as for :meth:`run`.
        """
        if (path is None) == (data is None):
            raise ValueError("badusb_run requires exactly one of path= or data=")
        args: Dict[str, Any] = {}
        if path is not None:
            args.update(source="file", path=path)
        else:
            args.update(source="buffer", data=data)
        if layout is not None:
            args["layout"] = layout
        if arm_token is not None:
            args["arm_token"] = arm_token
        return self.request("badusb.run", args)

    def storage_list(self, path: str = "/") -> Any:
        """List a directory on the ESP32's SD / LittleFS storage."""
        return self.request("storage.list", {"path": path})

    def storage_read(self, path: str) -> Any:
        """Read a file from ESP32 storage (binary payloads are base64)."""
        return self.request("storage.read", {"path": path})

    def storage_write(self, path: str, data: str) -> Any:
        """Write a file on ESP32 storage."""
        return self.request("storage.write", {"path": path, "data": data})

    def storage_delete(self, path: str) -> Any:
        """Delete a file on ESP32 storage."""
        return self.request("storage.delete", {"path": path})

    def settings_get(self, key: str) -> Any:
        """Read a device setting."""
        return self.request("settings.get", {"key": key})

    def settings_set(self, key: str, value: Any) -> Any:
        """Write a device setting."""
        return self.request("settings.set", {"key": key, "value": value})

    def power(self, action: str) -> Any:
        """Power control: ``action`` is ``reboot`` or ``sleep``."""
        return self.request("power", {"action": action})

    # -- internals ----------------------------------------------------------------

    def _write_line(self, line: str) -> None:
        with self._write_lock:
            self._transport.write_line(line)

    def _reader_loop(self) -> None:
        while not self._stop.is_set():
            try:
                line = self._transport.read_line(timeout=0.2)
            except Exception:
                if self._stop.is_set():
                    break
                continue
            if line is None:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                # Human-mode noise or a partial line: not structured traffic.
                continue
            if not isinstance(message, dict):
                continue
            if "event" in message:
                data = message.get("data") or {}
                with self._state_lock:
                    self._events.append(message)
                if self._on_event is not None:
                    try:
                        self._on_event(str(message["event"]), data)
                    except Exception:
                        pass  # a broken callback must not kill the reader
            elif "id" in message:
                with self._state_lock:
                    pending = self._pending.pop(message["id"], None)
                if pending is not None:
                    pending.response = message
                    pending.event.set()
