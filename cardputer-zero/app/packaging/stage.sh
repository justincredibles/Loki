#!/usr/bin/env bash
# Stage phase: lay the lokicz Python package into the APPLaunch
# tree and write the launcher. The launcher runs the menu app with
# passwordless sudo when available (the radio work needs it:
# monitor mode, SPI, the cap power rail) and falls back to a plain
# unprivileged start otherwise.
set -euo pipefail

SRC="../firmware/lokicz"
install -d "$STAGE$APP_INSTALL_DIR/lokicz"
for f in "$SRC"/*.py "$SRC"/*.json "$SRC"/*.html; do
    install -m 0644 "$f" "$STAGE$APP_INSTALL_DIR/lokicz/"
done
install -d "$STAGE$APP_INSTALL_DIR/lokicz/sprites"
for f in "$SRC"/sprites/*.png; do
    install -m 0644 "$f" "$STAGE$APP_INSTALL_DIR/lokicz/sprites/"
done

tmp=$(mktemp)
cat >"$tmp" <<'EOF'
#!/bin/sh
# LokiCZ launcher — APPLaunch entry point.
export PYTHONPATH=/usr/share/APPLaunch/apps/lokicz
if sudo -n true 2>/dev/null; then
    exec sudo -n env PYTHONPATH="$PYTHONPATH" \
        /usr/bin/python3 -m lokicz.main --menu
fi
exec /usr/bin/python3 -m lokicz.main --menu
EOF
install -D -m 0755 "$tmp" "$STAGE$INSTALL_PREFIX/bin/lokicz"
rm -f "$tmp"
