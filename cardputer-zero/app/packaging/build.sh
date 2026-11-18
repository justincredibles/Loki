#!/usr/bin/env bash
# Build phase: byte-compile the lokicz package so a syntax error
# fails the .deb build instead of the first launch.
set -euo pipefail
python3 -m py_compile ../firmware/lokicz/*.py
