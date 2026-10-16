"""Tests for loki.esp32link against a simulated ESP32.

The simulator (FakeEsp32) implements the firmware side of the Pi <-> ESP32
serial protocol v0.2 (docs/protocol/pi-esp32-serial.md): the hello handshake,
list, the arm gate for attack-class modules, run/stop with async events, and
the spec's error codes.
"""

from __future__ import annotations

import json
import time

import pytest

from loki.esp32link import (
    Esp32Client,
    Esp32Error,
    FakeTransport,
    ProtocolError,
    protocol,
)


class FakeEsp32:
    """Minimal simulated Bruce-fork firmware speaking protocol v0.2."""

    ATTACK_MODULES = {"badusb", "wifi.deauth", "rf.tx"}
    MODULES = ["badusb", "wifi.deauth", "wifi.scan", "rf.tx", "ir.rx", "rfid.read"]
    PAYLOADS = ["/payloads/demo.txt", "/payloads/rickroll.txt"]

    def __init__(self, protocol_version: str = protocol.PROTOCOL_VERSION) -> None:
        self.protocol_version = protocol_version
        self._tokens: dict[str, str] = {}  # arm_token -> module
        self._token_seq = 0
        self._job_seq = 0
        self.running_job: int | None = None

    # -- FakeTransport handler -------------------------------------------------

    def __call__(self, line: str) -> list[str]:
        line = line.strip()
        if line in (protocol.BEGIN_COMMAND, protocol.END_COMMAND):
            return []
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            return [json.dumps({"ok": False, "error": {"code": "bad_request"}})]
        request_id = request.get("id")
        cmd = request.get("cmd", "")
        args = request.get("args") or {}
        handler = getattr(self, f"_cmd_{cmd.replace('.', '_')}", None)
        if handler is None:
            return [self._error(request_id, protocol.ERR_UNKNOWN_COMMAND, f"unknown cmd {cmd!r}")]
        return handler(request_id, args)

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _ok(request_id, data) -> str:
        return json.dumps({"id": request_id, "ok": True, "data": data})

    @staticmethod
    def _error(request_id, code, message="") -> str:
        return json.dumps(
            {"id": request_id, "ok": False, "error": {"code": code, "message": message}}
        )

    @staticmethod
    def _event(name, data) -> str:
        return json.dumps({"event": name, "data": data})

    # -- commands ----------------------------------------------------------------

    def _cmd_hello(self, request_id, args):
        return [
            self._ok(
                request_id,
                {
                    "protocol": self.protocol_version,
                    "firmware": "bruce-loki 0.1.0",
                    "board": "loki-hat",
                    "device": "esp32-s3",
                },
            )
        ]

    def _cmd_list(self, request_id, args):
        type_ = args.get("type")
        if type_ == "modules":
            data = list(self.MODULES)
        elif type_ == "payloads":
            data = list(self.PAYLOADS)
        elif type_ == "files":
            data = []
        else:
            return [self._error(request_id, protocol.ERR_BAD_REQUEST, f"bad list type {type_!r}")]
        return [self._ok(request_id, data)]

    def _cmd_status(self, request_id, args):
        if self.running_job is None:
            data = {"state": "idle"}
        else:
            data = {"state": "running", "job": self.running_job, "elapsed_s": 1}
        return [self._ok(request_id, data)]

    def _cmd_arm(self, request_id, args):
        self._token_seq += 1
        token = f"arm-{self._token_seq}"
        self._tokens[token] = args.get("module", "")
        return [self._ok(request_id, {"arm_token": token, "expires_in": 10})]

    def _cmd_run(self, request_id, args):
        module = args.get("module")
        if module not in self.MODULES:
            return [self._error(request_id, protocol.ERR_NO_SUCH_MODULE, module or "")]
        if module in self.ATTACK_MODULES:
            token = args.get("arm_token")
            if self._tokens.get(token) != module:
                return [self._error(request_id, protocol.ERR_NOT_ARMED, "arm required")]
        if self.running_job is not None:
            return [self._error(request_id, protocol.ERR_BUSY, "an action is already running")]
        self._job_seq += 1
        job = self._job_seq
        self.running_job = job
        return [
            self._ok(request_id, {"job": job}),
            self._event(protocol.EVENT_ACTION_STARTED, {"job": job, "module": module}),
            self._event(protocol.EVENT_ACTION_DONE, {"job": job, "results": []}),
        ]

    def _cmd_stop(self, request_id, args):
        replies = [self._ok(request_id, {"stopped": self.running_job})]
        if self.running_job is not None:
            replies.append(
                self._event(protocol.EVENT_ACTION_ABORTED, {"job": self.running_job})
            )
            self.running_job = None
        return replies

    def _cmd_badusb_run(self, request_id, args):
        return [self._ok(request_id, {"job": 99})]


# -- fixtures --------------------------------------------------------------------


@pytest.fixture()
def sim() -> FakeEsp32:
    return FakeEsp32()


@pytest.fixture()
def transport(sim) -> FakeTransport:
    return FakeTransport(sim)


@pytest.fixture()
def client(transport) -> Esp32Client:
    c = Esp32Client(transport, timeout=5.0)
    c.connect()
    yield c
    c.close()


def wait_for_event(client: Esp32Client, name: str, timeout: float = 2.0):
    deadline = time.monotonic() + timeout
    seen = []
    while time.monotonic() < deadline:
        for event in client.poll_events():
            seen.append(event)
            if event.get("event") == name:
                return event
        time.sleep(0.01)
    raise AssertionError(f"event {name!r} not received; saw {seen!r}")


# -- tests -------------------------------------------------------------------------


def test_handshake_ok(client, transport):
    assert transport.written[0] == protocol.BEGIN_COMMAND
    assert client.hello_info is not None
    assert client.hello_info["protocol"] == protocol.PROTOCOL_VERSION
    assert client.hello_info["board"] == "loki-hat"
    assert client.hello_info["device"] == "esp32-s3"


def test_handshake_version_mismatch_raises():
    sim = FakeEsp32(protocol_version="1.0")
    client = Esp32Client(FakeTransport(sim), timeout=5.0)
    try:
        with pytest.raises(ProtocolError):
            client.connect()
    finally:
        client.close()


def test_list_modules(client):
    modules = client.list("modules")
    assert "badusb" in modules
    assert "wifi.deauth" in modules


def test_list_payloads(client):
    assert client.list("payloads") == FakeEsp32.PAYLOADS


def test_run_attack_module_without_arm_fails(client):
    with pytest.raises(Esp32Error) as excinfo:
        client.run("wifi.deauth", {"bssid": "aa:bb:cc:dd:ee:ff"})
    assert excinfo.value.code == protocol.ERR_NOT_ARMED


def test_run_attack_module_with_arm_succeeds(client):
    token = client.arm("wifi.deauth", {"bssid": "aa:bb:cc:dd:ee:ff"})
    job = client.run("wifi.deauth", {"bssid": "aa:bb:cc:dd:ee:ff"}, arm_token=token)
    assert isinstance(job, int) and job >= 1
    status = client.status()
    assert status["state"] == "running"
    assert status["job"] == job


def test_run_readonly_module_needs_no_arm(client):
    job = client.run("wifi.scan", {})
    assert isinstance(job, int)


def test_unknown_command_error_code(client):
    with pytest.raises(Esp32Error) as excinfo:
        client.request("bogus.command")
    assert excinfo.value.code == protocol.ERR_UNKNOWN_COMMAND


def test_unknown_module_error_code(client):
    with pytest.raises(Esp32Error) as excinfo:
        client.run("does.not.exist", {})
    assert excinfo.value.code == protocol.ERR_NO_SUCH_MODULE


def test_action_done_event_delivered(client):
    token = client.arm("badusb", {"path": "/payloads/demo.txt"})
    job = client.run("badusb", {"path": "/payloads/demo.txt"}, arm_token=token)
    event = wait_for_event(client, protocol.EVENT_ACTION_DONE)
    assert event["data"]["job"] == job


def test_event_callback_invoked(sim):
    received = []
    client = Esp32Client(
        FakeTransport(sim),
        timeout=5.0,
        on_event=lambda name, data: received.append((name, data)),
    )
    client.connect()
    try:
        token = client.arm("badusb", {"path": "/payloads/demo.txt"})
        job = client.run("badusb", {"path": "/payloads/demo.txt"}, arm_token=token)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if any(name == protocol.EVENT_ACTION_DONE for name, _ in received):
                break
            time.sleep(0.01)
        done = [data for name, data in received if name == protocol.EVENT_ACTION_DONE]
        assert done and done[0]["job"] == job
    finally:
        client.close()


def test_stop_aborts_running_action(client):
    client.run("wifi.scan", {})
    result = client.stop()
    assert result["stopped"] is not None
    event = wait_for_event(client, protocol.EVENT_ACTION_ABORTED)
    assert "job" in event["data"]
    assert client.status()["state"] == "idle"


def test_badusb_run_from_file(client):
    result = client.badusb_run(path="/payloads/demo.txt", layout="en-US")
    assert result["job"] == 99


def test_close_sends_end_command(client, transport):
    client.close()
    assert transport.written[-1] == protocol.END_COMMAND
    assert transport.closed


def test_request_timeout_raises_protocol_error():
    # A transport whose firmware never answers anything: connect() must
    # surface the dead link as a ProtocolError, not hang forever.
    client = Esp32Client(FakeTransport(lambda line: []), timeout=0.3)
    try:
        with pytest.raises(ProtocolError):
            client.connect()
    finally:
        client.close()
