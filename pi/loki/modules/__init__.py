"""Attack / tool modules: wrappers around the pinned engines.

Engines are pinned in ``pi/installer/engines.lock`` (bettercap, aircrack-ng,
hcxdumptool/hcxtools, Scapy). Radio work that belongs on the coprocessor is
dispatched through loki.esp32link instead of being reimplemented here.

TODO: engine wrappers (Phase 3+).
"""
