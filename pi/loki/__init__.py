"""Loki Pi-side software.

Loki is a pocket security multi-tool: a Raspberry Pi (Zero 2 W minimum,
Pi 4/5 supported) running this package, plus an ESP32-S3 coprocessor on the
Loki HAT running a fork of Bruce firmware. The two halves communicate over a
hardware UART using the Pi-ESP32 serial protocol (see docs/protocol/ in the
repo). This package is the ONLY code that talks to the ESP32, and it does so
exclusively through :mod:`loki.esp32link`.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
