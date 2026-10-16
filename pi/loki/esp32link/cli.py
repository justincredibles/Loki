"""Bench tool for the ESP32 link.

Usage::

    python -m loki.esp32link.cli --port /dev/ttyAMA0 hello
    python -m loki.esp32link.cli --port /dev/ttyAMA0 status
    python -m loki.esp32link.cli --port /dev/ttyAMA0 list --type payloads
    python -m loki.esp32link.cli --port /dev/ttyAMA0 stop

Prints the response data as JSON. Exits non-zero on Esp32Error /
ProtocolError, with the error on stderr.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from . import protocol
from .client import Esp32Client, Esp32Error, ProtocolError
from .transport import SerialTransport


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="loki.esp32link.cli",
        description="Bench tool for the Pi <-> ESP32 serial protocol "
        f"v{protocol.PROTOCOL_VERSION}.",
    )
    parser.add_argument("--port", required=True, help="UART device, e.g. /dev/ttyAMA0")
    parser.add_argument(
        "--baud", type=int, default=protocol.BAUD_RATE, help="baud rate (default 115200)"
    )
    parser.add_argument(
        "--timeout", type=float, default=10.0, help="per-request timeout in seconds"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("hello", help="handshake / version check")
    sub.add_parser("status", help="current ESP32 activity")
    list_parser = sub.add_parser("list", help="enumerate modules / payloads / files")
    list_parser.add_argument(
        "--type",
        default="modules",
        choices=["modules", "payloads", "files"],
        help="what to enumerate (default: modules)",
    )
    sub.add_parser("stop", help="abort the running action")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    client = Esp32Client(
        SerialTransport(args.port, baudrate=args.baud), timeout=args.timeout
    )
    try:
        hello = client.connect()
        if args.command == "hello":
            result = hello
        elif args.command == "status":
            result = client.status()
        elif args.command == "list":
            result = client.list(args.type)
        elif args.command == "stop":
            result = client.stop()
        else:  # pragma: no cover - argparse enforces the choices
            raise AssertionError(args.command)
    except (Esp32Error, ProtocolError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
