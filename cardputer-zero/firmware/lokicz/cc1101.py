"""CC1101 sub-GHz radio driver — Cap CC1101 (M5Stack U219).

Plain-English tour:
- The cap is DEAD until two power switches are flipped, in order:
  the Zero's EXT 5V rail (a sysfs switch, off by default) and the
  cap's POWER_EN pin (GPIO26). See caps.py for the full story.
- We talk to the chip over SPI (/dev/spidev0.1). "Strobes" are
  one-byte commands (reset, receive, idle). Config registers are
  one-byte reads/writes; status registers (part number, RSSI, state)
  are read with the burst bit set.
- Register base values come from TI's reference configuration via
  the SmartRC-CC1101 library (the same lineage as the CardputerZero
  org's SubG-Chat reference app).

This module is receive-only: frequency setting, an RSSI sweep
(the radio's "ears" — channel power across a band), an RSSI
activity listen (spikes = somebody transmitting), a FIFO packet
listen that collects packets carrying our sync word, and raw OOK
capture — the chip in async-serial mode, its demodulated bit
stream sampled off the GDO0 pin and saved as a Flipper .sub file.
Transmission lands later, behind the arm-token gate like every
other attack-class feature in Loki.
"""

import subprocess
import time

# --- Power -----------------------------------------------------------------
EXT_5V_NODE = "/sys/class/leds/ext_5v_out/brightness"
POWER_EN_GPIO = 26
GDO0_GPIO = 15  # the CC1101's data pin on this cap — EXPERIMENTALLY
# confirmed 2026-11-17: with GDO0 set to the crystal-clock output,
# GPIO15 toggled (2,168 edges/s of polling) while GPIO14/22/23 sat
# still. (Published pin tables said 14; the hardware says 15. The
# pin idles as the mini-UART's RXD1 — claiming it as a GPIO input
# is correct while this cap is fitted.)

# --- SPI / strobes -----------------------------------------------------------
SPI_BUS, SPI_CS = 0, 1  # /dev/spidev0.1 — SPI0 CS1, shared with the LCD
SRES, SRX, SIDLE, SFRX, SNOP = 0x30, 0x34, 0x36, 0x3A, 0x3D

# --- Registers ---------------------------------------------------------------
FREQ2, FREQ1, FREQ0 = 0x0D, 0x0E, 0x0F
PKTLEN, PKTCTRL1, PKTCTRL0 = 0x06, 0x07, 0x08
IOCFG2, IOCFG0 = 0x00, 0x02
MDMCFG2, FREND0 = 0x12, 0x22
RXFIFO = 0x3F

# Status registers (read with the burst bit, addr | 0xC0)
PARTNUM, VERSION, MARCSTATE, RSSI, RXBYTES = 0x30, 0x31, 0x35, 0x34, 0x3B

# Base RX configuration (TI reference values via SmartRC-CC1101's
# RegConfigSettings + packet-mode setCCMode branch).
BASE_CONFIG = {
    0x0B: 0x06,  # FSCTRL1
    0x13: 0x02,  # MDMCFG1
    0x14: 0xF8,  # MDMCFG0
    0x15: 0x47,  # DEVIATN
    0x21: 0x56,  # FREND1
    0x22: 0x10,  # FREND0 (GFSK)
    0x18: 0x18,  # MCSM0 — auto-calibrate on IDLE->RX/TX
    0x19: 0x16,  # FOCCFG
    0x1A: 0x1C,  # BSCFG
    0x1B: 0xC7,  # AGCCTRL2
    0x1C: 0x00,  # AGCCTRL1
    0x1D: 0xB2,  # AGCCTRL0
    0x23: 0xE9,  # FSCAL3
    0x24: 0x2A,  # FSCAL2
    0x25: 0x00,  # FSCAL1
    0x26: 0x1F,  # FSCAL0
    0x29: 0x59,  # FSTEST
    0x2C: 0x81,  # TEST2
    0x2D: 0x35,  # TEST1
    PKTCTRL1: 0x04,
    0x09: 0x00,  # ADDR
    IOCFG2: 0x0B,
    IOCFG0: 0x06,
    PKTCTRL0: 0x05,  # packet mode, fixed length (PKTLEN below)
    0x11: 0xF8,      # MDMCFG3
    0x10: 0x5B,      # MDMCFG4 — DRATE_E=11; pairs with MDMCFG3 above
    PKTLEN: 64,
    # GFSK, 30/32 sync-word detection + carrier sense (sync word is
    # the POR 0xD391). HARD-WON LESSON (2026-11-17): with sync
    # detection OFF (MDMCFG2=0x00) this receiver goes deaf — RSSI
    # freezes at a nonsense value and nothing is heard, on both
    # bands, while the library-exact sync settings hear fine.
    MDMCFG2: 0x03,
}


def _rail_on() -> None:
    """Switch the Zero's EXT 5V rail on (root write; sudo fallback)."""
    try:
        with open(EXT_5V_NODE, "w") as f:
            f.write("1")
        return
    except PermissionError:
        pass
    subprocess.run(
        f"echo 1 | sudo -n tee {EXT_5V_NODE}",
        shell=True, capture_output=True, timeout=10,
    )


class CC1101:
    """The fitted CC1101, powered and talking. Use as a context manager."""

    def __init__(self) -> None:
        self._spi = None
        self._pwr = None

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "CC1101":
        import spidev
        from gpiozero import OutputDevice

        _rail_on()
        self._pwr = OutputDevice(POWER_EN_GPIO)
        self._pwr.on()
        time.sleep(0.05)

        self._spi = spidev.SpiDev()
        self._spi.open(SPI_BUS, SPI_CS)
        self._spi.max_speed_hz = 1_000_000
        self._spi.mode = 0
        self.strobe(SRES)
        time.sleep(0.05)
        part, version = self.read_status(PARTNUM), self.read_status(VERSION)
        if part != 0x00 or version not in (0x04, 0x14):
            raise RuntimeError(
                f"CC1101 not answering (PARTNUM=0x{part:02X}, "
                f"VERSION=0x{version:02X}) — is the cap powered/seated?"
            )
        for reg, val in BASE_CONFIG.items():
            self.write_reg(reg, val)
        return self

    def __exit__(self, *exc) -> None:
        try:
            self.strobe(SIDLE)
            self._spi.close()
        finally:
            # Per M5Stack's own app guidance, the EXT rail stays ON
            # while the cap is fitted; POWER_EN is released with the
            # process and re-asserted on the next open.
            if self._pwr is not None:
                self._pwr.off()
                self._pwr.close()

    # -- SPI primitives ------------------------------------------------------
    def strobe(self, cmd: int) -> int:
        return self._spi.xfer2([cmd])[0]

    def write_reg(self, addr: int, val: int) -> None:
        self._spi.xfer2([addr, val])

    def read_status(self, addr: int) -> int:
        return self._spi.xfer2([addr | 0xC0, 0x00])[1]

    # -- radio ---------------------------------------------------------------
    def set_frequency(self, mhz: float) -> None:
        """Program the carrier (26 MHz crystal) and band tweak (TEST0)."""
        self.strobe(SIDLE)
        freq = int(mhz * 65536.0 / 26.0)
        self.write_reg(FREQ2, (freq >> 16) & 0xFF)
        self.write_reg(FREQ1, (freq >> 8) & 0xFF)
        self.write_reg(FREQ0, freq & 0xFF)
        # TEST0 VCO selection, per the reference library's Calibrate().
        self.write_reg(0x2E, 0x0B if (mhz < 322.88 or 378 <= mhz < 430.5
                                      or 779 <= mhz < 861) else 0x09)

    def rssi_dbm(self) -> float:
        """Current channel power. Offset 74 dB at this channel BW."""
        raw = self.read_status(RSSI)
        return ((raw - 256) / 2 - 74) if raw >= 128 else (raw / 2 - 74)

    def enter_rx(self) -> None:
        self.strobe(SFRX)
        self.strobe(SRX)
        time.sleep(0.02)

    def sweep(self, start_mhz: float, stop_mhz: float, step_mhz: float,
              dwell_s: float = 0.06) -> list[tuple[float, float]]:
        """Step across a band, recording the strongest RSSI per step."""
        results = []
        f = start_mhz
        while f <= stop_mhz + 1e-9:
            self.set_frequency(f)
            self.enter_rx()
            best = -120.0
            t_end = time.time() + dwell_s
            while time.time() < t_end:
                best = max(best, self.rssi_dbm())
                time.sleep(0.005)
            results.append((round(f, 3), best))
            f += step_mhz
        self.strobe(SIDLE)
        return results

    def listen_activity(self, seconds: float) -> tuple[float, float]:
        """Watch channel power for `seconds`; return (peak, mean) dBm.

        The honest "is anything transmitting here?" test: a key fob,
        weather station or meter shows up as a clear spike above the
        noise floor.
        """
        self.enter_rx()
        samples = []
        t_end = time.time() + seconds
        while time.time() < t_end:
            samples.append(self.rssi_dbm())
            time.sleep(0.01)
        self.strobe(SIDLE)
        return max(samples), sum(samples) / len(samples)

    def listen_fifo(self, seconds: float) -> bytes:
        """Collect packets carrying our sync word for `seconds`.

        Sync-word detection is ON (see BASE_CONFIG), so ambient
        traffic — which doesn't carry 0xD391 — never lands here.
        This is for talking to radios we've configured as peers;
        use listen_activity() to sense a band.
        """
        self.enter_rx()
        data = bytearray()
        t_end = time.time() + seconds
        while time.time() < t_end:
            n = self.read_status(RXBYTES) & 0x7F
            if n:
                data += bytes(self._spi.xfer2([RXFIFO | 0xFF] + [0] * n)[1:])
            time.sleep(0.02)
        self.strobe(SIDLE)
        return bytes(data)


    def capture_ook(self, freq_mhz: float, seconds: float,
                    out_path: str) -> dict:
        """Raw OOK capture: async-serial demodulated bits off GDO0.

        The chip is reconfigured for ASK/OOK async serial mode
        (MDMCFG2 mod-format 111, PKTCTRL0 async+infinite length,
        GDO0 = serial data out). A tight polling loop timestamps
        every edge on GPIO14; the run-length result is written as a
        Flipper Sub-GHz RAW (.sub) file — the lingua franca for
        sharing raw remote-control captures.
        """
        from gpiozero import DigitalInputDevice

        self.set_frequency(freq_mhz)
        self.write_reg(MDMCFG2, 0x73)   # OOK + 30/32 sync + carrier sense
        self.write_reg(PKTCTRL0, 0x32)  # async serial, infinite length
        self.write_reg(IOCFG0, 0x0D)    # GDO0 = async serial data
        self.strobe(SFRX)
        self.strobe(SRX)
        time.sleep(0.02)

        # Squelch first: an OOK demodulator with no signal outputs
        # pure slicer noise, so we measure the noise floor and gate
        # the recording on RSSI (floor + 10 dB), polled every ~4 ms
        # alongside the pin. Only gated-open stretches reach the file.
        floor_samples = []
        t_end = time.time() + 0.5
        while time.time() < t_end:
            floor_samples.append(self.rssi_dbm())
            time.sleep(0.01)
        floor = sorted(floor_samples)[len(floor_samples) // 2]
        threshold = floor + 10.0

        pin = DigitalInputDevice(GDO0_GPIO, pull_up=False)
        try:
            edges: list[tuple[int, int]] = []
            gate: list[tuple[int, bool]] = []
            level = pin.value
            start = time.perf_counter_ns()
            deadline = start + int(seconds * 1e9)
            next_poll = start
            while True:
                now = time.perf_counter_ns()
                if now >= deadline:
                    break
                if now >= next_poll:
                    gate.append((now, self.rssi_dbm() >= threshold))
                    next_poll = now + 4_000_000
                v = pin.value
                if v != level:
                    edges.append((now, v))
                    level = v
        finally:
            pin.close()
            self.strobe(SIDLE)

        # Gate state at time t (5 ms hangover so a burst's tail
        # isn't clipped), then edges -> run durations in µs
        # (signed: + = signal, - = gap, the Flipper RAW convention),
        # merging sub-60µs glitches and collapsing gated-off time
        # into plain gaps.
        def gate_open(t_ns: int) -> bool:
            state = False
            for gt, gv in gate:
                if gt > t_ns + 5_000_000:
                    break
                if gt <= t_ns:
                    state = gv
                elif gv:
                    state = True
            return state

        runs: list[int] = []
        timeline = [(start, 0)]
        for t_ns, lv in edges:
            if gate_open(t_ns):
                timeline.append((t_ns, lv))
            elif timeline[-1][1] != 0:
                timeline.append((t_ns, 0))
        timeline.append((deadline, 0))
        for (t0, lv), (t1, _n) in zip(timeline, timeline[1:]):
            dur = int((t1 - t0) / 1000)
            if dur <= 0:
                continue
            signed = dur if lv else -dur
            if runs and (runs[-1] > 0) == (signed > 0):
                runs[-1] += signed
            elif runs and abs(signed) < 60:
                runs[-1] += signed  # swallow a glitch into the last run
            else:
                runs.append(signed)

        from pathlib import Path

        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["Filetype: Flipper SubGhz RAW File", "Version: 1",
                 f"Frequency: {int(freq_mhz * 1_000_000)}",
                 "Preset: FuriHalSubGhzPresetOok650Async",
                 "Protocol: RAW"]
        for i in range(0, len(runs), 50):
            lines.append("RAW_Data: " + " ".join(
                str(r) for r in runs[i:i + 50]))
        path.write_text("\n".join(lines) + "\n")

        bursts = sum(1 for a, b in zip(runs, runs[1:])
                     if a < -10_000 and b > 0)
        pulses = [r for r in runs if r > 0]
        return {"file": str(path), "transitions": len(edges),
                "runs": len(runs), "bursts": bursts,
                "floor_dbm": floor, "threshold_dbm": threshold,
                "shortest_pulse_us": min(pulses) if pulses else 0,
                "longest_pulse_us": max(pulses) if pulses else 0}


def listen_test() -> None:
    """First-ears test: sweep both sub-GHz bands, then dwell-listen."""
    with CC1101() as radio:
        print("CC1101 verified live (PARTNUM/VERSION OK)")
        for start, stop in ((430.0, 437.0), (902.0, 928.0)):
            sweep = radio.sweep(start, stop, 0.2)
            floor = sorted(r for _, r in sweep)[len(sweep) // 2]
            peak_f, peak_r = max(sweep, key=lambda t: t[1])
            print(f"{start:.0f}-{stop:.0f} MHz: noise floor ~{floor:.0f} dBm, "
                  f"peak {peak_r:.0f} dBm at {peak_f:.1f} MHz")
        for mhz in (433.92, 915.0):
            radio.set_frequency(mhz)
            peak, mean = radio.listen_activity(5.0)
            print(f"{mhz} MHz dwell 5s: RSSI peak {peak:.0f} dBm, "
                  f"mean {mean:.0f} dBm")


if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) > 1 and sys.argv[1] == "ook":
        freq = float(sys.argv[2]) if len(sys.argv) > 2 else 433.92
        secs = float(sys.argv[3]) if len(sys.argv) > 3 else 6.0
        stamp = time.strftime("%Y%m%d-%H%M%S")
        out = (Path.home() / "lokicz-subghz" /
               f"ook-{freq:.2f}MHz-{stamp}.sub")
        with CC1101() as radio:
            stats = radio.capture_ook(freq, secs, str(out))
        print(f"OOK capture {freq} MHz, {secs:.0f}s: "
              f"{stats['transitions']} transitions, "
              f"{stats['runs']} runs, ~{stats['bursts']} bursts, "
              f"pulses {stats['shortest_pulse_us']}-"
              f"{stats['longest_pulse_us']} us")
        print(f"saved: {stats['file']}")
    else:
        listen_test()
