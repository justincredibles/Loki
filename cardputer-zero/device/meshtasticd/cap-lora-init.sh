#!/bin/bash
# Cap LoRa-1262 pre-meshtasticd init:
#  1. drive PI4IOE5V6408 (i2c-1 0x43) P0 high = LoRa antenna RF switch on.
#     Register map per the vendor driver (m5stack/uiflow-micropython, base/echo.py):
#     0x03 IO direction (1 = output), 0x05 output state, 0x07 output High-Z (0 = drive).
#  2. wake the GP-02 GNSS from CASIC standby. meshtasticd duty-cycles the GPS
#     with $PCAS12 (HARDSLEEP); that state survives a daemon restart (and even a
#     power cycle — the cap has a VBAT backup cell), and the baud autoprobe
#     cannot detect a sleeping module. A benign product-info query at the
#     module's 115200 baud wakes it without touching its state.
set -eu

# The cap is dead until the Zero's EXT 5V rail and the cap's
# POWER_EN (GPIO26) are on — the same two-step power gate the
# CC1101 cap needs. Proven on hardware 2026-11-17: with the gate
# off, the expander below never answers and this script fails;
# zeroradio's own image evidently held the gate on already, so
# their version of this script never had to.
echo 1 > /sys/class/leds/ext_5v_out/brightness 2>/dev/null || true
pinctrl set 26 op dh 2>/dev/null || true
sleep 1

BUS=1
ADDR=0x43
GNSS=/dev/ttyS0

# The expander enumerates with the I2C bus; retry briefly so a boot-time race
# with device creation cannot silently skip the RF switch.
for attempt in 1 2 3 4 5; do
    if dir="$(i2cget -y "$BUS" "$ADDR" 0x03 2>/dev/null)"; then
        break
    fi
    [ "$attempt" -eq 5 ] && { echo "cap-lora-init: expander 0x43 not reachable" >&2; exit 1; }
    sleep 1
done
case "$dir" in 0x*) ;; *) echo "cap-lora-init: bad i2cget output: $dir" >&2; exit 1 ;; esac

out="$(i2cget -y "$BUS" "$ADDR" 0x05)"
hiz="$(i2cget -y "$BUS" "$ADDR" 0x07)"
i2cset -y "$BUS" "$ADDR" 0x03 $(( dir | 1 ))
i2cset -y "$BUS" "$ADDR" 0x05 $(( out | 1 ))
i2cset -y "$BUS" "$ADDR" 0x07 $(( hiz & 0xFE ))

if [ -c "$GNSS" ]; then
    stty -F "$GNSS" 115200 raw
    printf '$PCAS06,0*1B\r\n' > "$GNSS"
    sleep 1
fi
