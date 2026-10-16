"""Epoch engine: Loki's central loop.

Everything (mood, modules, UI, web) consumes the orchestrator's epoch
snapshots; the orchestrator owns the ESP32 link lifecycle.

TODO: implement the epoch loop on top of loki.esp32link (Phase 3).
"""
