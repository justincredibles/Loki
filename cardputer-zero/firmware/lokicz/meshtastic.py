"""Meshtastic supervision — lokicz manages meshtasticd, never replaces it.

The daemon (Meshtastic's Linux build) owns the SX1262 on the LoRa
cap; lokicz's job is the honest status picture:

- installed? service running?
- Client API answering on 127.0.0.1:4403?
- **radio real or simulated?** portduino silently falls back to a
  fake radio when the config is wrong, so the ONLY trusted proof
  is `SX126x init result 0` in the journal of the *current*
  service invocation. This module checks exactly that.
"""

import socket
import subprocess

API_ADDR = ("127.0.0.1", 4403)


def _run(cmd: str, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True,
                          text=True, timeout=timeout)


def installed() -> bool:
    return _run("command -v meshtasticd").returncode == 0


def service_active() -> bool:
    return _run("systemctl is-active meshtasticd").stdout.strip() == "active"


def api_up() -> bool:
    try:
        with socket.create_connection(API_ADDR, timeout=2):
            return True
    except OSError:
        return False


def radio_ok() -> bool:
    """True only if THIS boot of the daemon really initialized the
    SX1262 — the anti-simradio check zeroradio's acceptance uses."""
    r = _run("systemctl show meshtasticd -p InvocationID --value")
    inv = r.stdout.strip()
    if not inv:
        return False
    r = _run(f"journalctl -u meshtasticd _SYSTEMD_INVOCATION_ID={inv} "
             "--no-pager -o cat", timeout=20)
    return "SX126x init result 0" in r.stdout


def status() -> dict:
    return {"installed": installed(), "service": service_active(),
            "api": api_up(), "radio": radio_ok()}


def main() -> int:
    s = status()
    lines = [
        "Meshtastic (meshtasticd)",
        f"installed: {'yes' if s['installed'] else 'NO'}",
        f"service:   {'active' if s['service'] else 'not running'}",
        f"API 4403:  {'answering' if s['api'] else 'silent'}",
        "radio:     " + ("SX1262 REAL (init result 0)" if s["radio"]
                         else "not proven — simradio or cap missing"),
    ]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
