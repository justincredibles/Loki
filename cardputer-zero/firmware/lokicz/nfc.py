"""NFC — ST25R3916 driver: probe + ISO14443A inventory.

The CC1101 cap (U219) also carries an ST25R3916 NFC frontend.
Reaching it took three discoveries, all verified on hardware
2026-11-17:

1. **Its chip-select is GPIO22**, provided by a stock firmware
   overlay with a trap in its name: the file is
   `spi0-spidev2-gpio22-overlay.dtbo`, and the overlay only loads
   when config.txt (or the runtime `dtoverlay` command) uses the
   FULL name — the short form silently loads nothing. Loaded, it
   creates /dev/spidev0.2 on the shared SPI0 bus.
2. **It speaks SPI mode 1**, not mode 0. In mode 0 the identity
   register reads 0x15 — the true value bit-shifted by one, the
   classic wrong-clock-phase tell. In mode 1 it reads 0x2A.
3. **0x2A is the ST25R3916's IC identity** (register 0x3F: type
   bits 00101 + revision). The chip is present, powered by the
   cap's usual two-step gate, and answering.

The inventory driver (init, field on, WUPA, anticollision,
SELECT, UID) follows the register recipe proven by ESPHome's
st25r component, which itself mirrors ST's RFAL NFC-A 106 kbps
analog profile — register tables below are theirs, credited.
SPI transport details that matter:

- Register read: 0x40|addr, then clock out the value; register
  write: addr, then the value. Addresses with bit 6 set live in
  "space B" and need a 0xFB prefix byte first.
- Direct commands are single bytes (0xC1 Set Default, 0xC8 NFC
  Initial Field ON, ...). FIFO load is 0x80 + data; FIFO read
  is 0x9F + clocked-out data.
- IRQ status is POLLED from the Main IRQ register (0x1A) — the
  cap routes the chip's IRQ to GPIO23, but polling the register
  is simpler and is what ESPHome's transceive path does too.

Inventory scope: one tag at a time. A genuine anticollision
collision (two tags answering at once) is reported as such,
not resolved bit-by-bit — that is the honest v1 limit.
"""

import subprocess
import time

SPIDEV_PATH = "/dev/spidev0.2"
IDENTITY_REG = 0x3F
ST25R3916_IDENTITY_MASK = 0xF8
ST25R3916_IDENTITY = 0x28

# --- Registers (space A unless noted) ---------------------------------------
REG_IO_CONF1 = 0x00
REG_IO_CONF2 = 0x01
REG_OP_CONTROL = 0x02
REG_MODE = 0x03
REG_BIT_RATE = 0x04
REG_ISO14443A = 0x05
REG_PASSIVE_TARGET = 0x08
REG_AUX = 0x0A
REG_RX_CONF1 = 0x0B
REG_RX_CONF2 = 0x0C
REG_RX_CONF3 = 0x0D
REG_RX_CONF4 = 0x0E
REG_MASK_MAIN = 0x16
REG_MASK_TIMER = 0x17
REG_IRQ_MAIN = 0x1A
REG_IRQ_TIMER = 0x1B
REG_IRQ_ERROR = 0x1C
REG_FIFO_STATUS1 = 0x1E
REG_NUM_TX_BYTES1 = 0x22
REG_NUM_TX_BYTES2 = 0x23
REG_AD_CONV_RESULT = 0x25
REG_ANT_TUNE_A = 0x26
REG_ANT_TUNE_B = 0x27
REG_TX_DRIVER_CONF = 0x28
REG_PT_MOD = 0x29
REG_FIELD_THRESH_ACTV = 0x2A
REG_FIELD_THRESH_DEACTV = 0x2B
REG_REGULATOR_CONTROL = 0x2C
# Space B (0xFB prefix on the wire)
REG_EMD_SUP_CONF = 0x45
REG_CORR_CONF1 = 0x4C
REG_CORR_CONF2 = 0x4D
REG_AUX_MOD = 0x68
REG_RES_AM_MOD = 0x6A
REG_OVERSHOOT_CONF1 = 0x70
REG_OVERSHOOT_CONF2 = 0x71
REG_UNDERSHOOT_CONF1 = 0x72
REG_UNDERSHOOT_CONF2 = 0x73

# --- Direct commands ---------------------------------------------------------
CMD_SET_DEFAULT = 0xC1
CMD_CLEAR_FIFO = 0xC3
CMD_TRANSMIT_WITH_CRC = 0xC4
CMD_TRANSMIT_WITHOUT_CRC = 0xC5
CMD_TRANSMIT_REQA = 0xC6
CMD_TRANSMIT_WUPA = 0xC7
CMD_FIELD_ON = 0xC8
CMD_RESET_RX_GAIN = 0xD5
CMD_ADJUST_REGULATORS = 0xD6
CMD_MEASURE_VDD = 0xDF

# --- IRQ_MAIN bits -------------------------------------------------------------
IRQ_RXE = 0x10   # receive complete
IRQ_TXE = 0x08   # transmit complete
IRQ_COL = 0x04   # collision detected

# RFAL NFC-A 106 kbps profile (via ESPHome's st25r component).
_PROFILE_RX = [
    (REG_MODE, 0x08), (REG_BIT_RATE, 0x00), (REG_RX_CONF1, 0x08),
    (REG_RX_CONF2, 0x2D), (REG_RX_CONF3, 0x00), (REG_RX_CONF4, 0x00),
    (REG_MASK_MAIN, 0x00), (REG_MASK_TIMER, 0x00),
    (REG_ISO14443A, 0x00),
]
_PROFILE_TX = [
    (REG_ANT_TUNE_A, 0x80), (REG_ANT_TUNE_B, 0x40),
    (REG_AUX_MOD, 0x10), (REG_RES_AM_MOD, 0x80),
    (REG_FIELD_THRESH_ACTV, 0x11), (REG_FIELD_THRESH_DEACTV, 0x00),
    (REG_PASSIVE_TARGET, 0x50), (REG_PT_MOD, 0x51),
    (REG_EMD_SUP_CONF, 0x40),
    (REG_OVERSHOOT_CONF1, 0x40), (REG_OVERSHOOT_CONF2, 0x03),
    (REG_UNDERSHOOT_CONF1, 0x40), (REG_UNDERSHOOT_CONF2, 0x03),
]
_PROFILE_CORR = [
    (REG_RX_CONF4, 0x00), (REG_CORR_CONF1, 0x51), (REG_CORR_CONF2, 0x00),
]

SEL_CMDS = (0x93, 0x95, 0x97)  # anticollision SELECT per cascade level


def ensure_spidev() -> bool:
    """Make sure /dev/spidev0.2 exists, loading the overlay live
    if the boot-time load didn't happen."""
    from pathlib import Path

    if Path(SPIDEV_PATH).exists():
        return True
    subprocess.run(["sudo", "-n", "dtoverlay",
                    "spi0-spidev2-gpio22-overlay"],
                   capture_output=True, timeout=15)
    time.sleep(0.5)
    return Path(SPIDEV_PATH).exists()


class ST25R3916:
    """The cap's NFC frontend, powered and initialized.

    Use as a context manager; inventory() is the payload.
    """

    def __init__(self) -> None:
        self._spi = None
        self.identity = None
        self.vdd_mv = None

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "ST25R3916":
        import spidev

        from .cc1101 import _power_on

        if not ensure_spidev():
            raise RuntimeError("/dev/spidev0.2 missing — NFC overlay "
                               "not loaded (is the CC1101 cap fitted?)")
        _power_on()

        self._spi = spidev.SpiDev()
        self._spi.open(0, 2)
        self._spi.max_speed_hz = 1_000_000
        self._spi.mode = 1  # the 3916 samples on the falling edge
        self.identity = self.read_reg(IDENTITY_REG)
        if (self.identity & ST25R3916_IDENTITY_MASK) != ST25R3916_IDENTITY:
            raise RuntimeError(
                f"ST25R3916 not answering (identity 0x{self.identity:02X}) "
                "— is the cap powered/seated?")
        self._init_reader()
        return self

    def __exit__(self, *exc) -> None:
        if self._spi is not None:
            self.write_reg(REG_OP_CONTROL, 0x00)  # field + osc off
            self._spi.close()
        # POWER_EN stays asserted — see cc1101._power_on.

    # -- SPI transport -------------------------------------------------------
    def read_reg(self, addr: int) -> int:
        frame = ([0xFB] if addr & 0x40 else []) + [0x40 | (addr & 0x3F), 0x00]
        return self._spi.xfer2(frame)[-1]

    def write_reg(self, addr: int, val: int) -> None:
        frame = ([0xFB] if addr & 0x40 else []) + [addr & 0x3F, val]
        self._spi.xfer2(frame)

    def command(self, cmd: int) -> None:
        self._spi.xfer2([cmd])

    def write_fifo(self, data: bytes) -> None:
        self._spi.xfer2([0x80] + list(data))

    def read_fifo(self, n: int) -> bytes:
        if n <= 0:
            return b""
        return bytes(self._spi.xfer2([0x9F] + [0x00] * n)[1:])

    def fifo_count(self) -> int:
        return self.read_reg(REG_FIFO_STATUS1)

    # -- reader init (ESPHome reset_chip_ + field_on_ recipe) ---------------
    def _init_reader(self) -> None:
        self.command(CMD_SET_DEFAULT)
        time.sleep(0.01)
        self.write_reg(REG_OP_CONTROL, 0x80)  # oscillator on
        time.sleep(0.01)
        # Measure the supply to set the 3.3 V / 5 V regulator flag.
        reg_ctrl = self.read_reg(REG_REGULATOR_CONTROL)
        self.write_reg(REG_REGULATOR_CONTROL, reg_ctrl & ~0x07)
        self.command(CMD_MEASURE_VDD)
        time.sleep(0.005)
        raw = self.read_reg(REG_AD_CONV_RESULT)
        sup3v = True
        if raw:
            self.vdd_mv = int(raw * 23 + (raw * 4 + 5) / 10)
            sup3v = self.vdd_mv < 3600
        self.write_reg(REG_IO_CONF1, 0x07)
        self.write_reg(REG_IO_CONF2, (0x80 if sup3v else 0x00) | 0x18 | 0x20)
        for reg, val in _PROFILE_RX:
            self.write_reg(reg, val)
        self.write_reg(REG_TX_DRIVER_CONF, 0x00)  # max drive
        for reg, val in _PROFILE_TX:
            self.write_reg(reg, val)
        aux = self.read_reg(REG_AUX)
        self.write_reg(REG_AUX, aux & ~0x04)
        for reg, val in _PROFILE_CORR:
            self.write_reg(reg, val)
        # Field on: TX driver up, initial-field-on command (RF
        # collision avoidance), receiver on, regulator adjust.
        self.write_reg(REG_OP_CONTROL, 0x88)
        time.sleep(0.01)
        self.command(CMD_FIELD_ON)
        time.sleep(0.01)
        self.write_reg(REG_OP_CONTROL, 0xC8)
        self.command(CMD_ADJUST_REGULATORS)

    def field_off(self) -> None:
        self.write_reg(REG_OP_CONTROL, 0x80)  # oscillator stays, field off

    # -- exchange plumbing -----------------------------------------------------
    def _clear_irqs(self) -> None:
        self.command(CMD_CLEAR_FIFO)
        self.read_reg(REG_IRQ_MAIN)
        self.read_reg(REG_IRQ_TIMER)
        self.read_reg(REG_IRQ_ERROR)

    def _wait_irq(self, mask: int, timeout_ms: int) -> int:
        """Poll Main IRQ until one of `mask`'s bits sets; return the
        last status read (0 on timeout)."""
        deadline = time.time() + timeout_ms / 1000.0
        status = 0
        while time.time() < deadline:
            status = self.read_reg(REG_IRQ_MAIN)
            if status & mask:
                return status
            time.sleep(0.001)
        return status

    def _transceive_crc(self, frame: bytes, timeout_ms: int = 150) -> bytes:
        """Send `frame` with CRC; return the response (CRC included
        in the tail, as the chip leaves it in the FIFO)."""
        self._clear_irqs()
        self.command(CMD_RESET_RX_GAIN)
        n = len(frame)
        self.write_reg(REG_NUM_TX_BYTES1, (n >> 5) & 0xFF)
        self.write_reg(REG_NUM_TX_BYTES2, (n & 0x1F) << 3)
        self.write_fifo(frame)
        self.command(CMD_TRANSMIT_WITH_CRC)
        out = bytearray()
        tx_done = False
        deadline = time.time() + timeout_ms / 1000.0
        while time.time() < deadline:
            irq = self.read_reg(REG_IRQ_MAIN)
            if irq & IRQ_TXE:
                tx_done = True
            if tx_done:
                count = self.fifo_count()
                if count:
                    out += self.read_fifo(count)
                    deadline = time.time() + 0.05
            if irq & IRQ_RXE:
                break
            time.sleep(0.001)
        count = self.fifo_count()
        if count:
            out += self.read_fifo(count)
        return bytes(out)

    # -- ISO14443A inventory ---------------------------------------------------
    def inventory(self, timeout_s: float = 3.0) -> dict:
        """Poll for one ISO14443A tag; return its ATQA/UID/SAK.

        {"found": False} when the field stays silent. A two-tag
        collision is reported, not resolved (see module header).
        """
        result = {"found": False, "atqa": None, "uid": None,
                  "sak": None, "collision": False}
        self._clear_irqs()
        self.command(CMD_RESET_RX_GAIN)
        time.sleep(0.005)  # ISO14443 guard time in the field
        self.command(CMD_TRANSMIT_WUPA)
        status = self._wait_irq(IRQ_RXE | IRQ_COL,
                                int(timeout_s * 1000))
        if not (status & (IRQ_RXE | IRQ_COL)):
            return result
        atqa_bytes = self.read_fifo(min(self.fifo_count(), 2))
        if len(atqa_bytes) == 2:
            result["atqa"] = atqa_bytes.hex()

        uid = bytearray()
        for level, sel in enumerate(SEL_CMDS):
            # Anticollision frame: SEL + NVB 0x20, no CRC, with the
            # chip's anticollision bit set (it then also receives
            # without CRC, which anticollision answers require).
            self.write_reg(REG_ISO14443A, 0x01)
            self._clear_irqs()
            self.write_fifo(bytes([sel, 0x20]))
            self.write_reg(REG_NUM_TX_BYTES1, 0x00)
            self.write_reg(REG_NUM_TX_BYTES2, 0x10)  # 2 bytes, 0 bits
            self.command(CMD_TRANSMIT_WITHOUT_CRC)
            status = self._wait_irq(IRQ_RXE | IRQ_COL | IRQ_TXE, 100)
            if status & IRQ_COL:
                result["collision"] = True
                if self.fifo_count():
                    self.read_fifo(min(self.fifo_count(), 8))
                return result
            if self.fifo_count() < 5:
                return result
            resp = self.read_fifo(5)
            bcc = resp[0] ^ resp[1] ^ resp[2] ^ resp[3]
            if bcc != resp[4]:
                return result  # garbled answer — report not-found
            part = resp[1:4] if resp[0] == 0x88 else resp[0:4]
            uid += part
            # SELECT the tag at this cascade level (with CRC).
            self.write_reg(REG_ISO14443A, 0x00)
            sak_resp = self._transceive_crc(
                bytes([sel, 0x70]) + bytes(resp[0:4]) + bytes([bcc]))
            if not sak_resp:
                return result
            sak = sak_resp[0]
            result["sak"] = sak
            if not (sak & 0x04):
                break  # UID complete
            if level == len(SEL_CMDS) - 1:
                return result  # cascade overflow — bail honestly
        if len(uid) in (4, 7, 10):
            result["found"] = True
            result["uid"] = bytes(uid).hex()
        return result


def probe() -> dict:
    """Power the cap and ask the NFC chip who it is."""
    import spidev

    from .cc1101 import _power_on

    result = {"spidev": ensure_spidev(), "identity": None,
              "found": False}
    if not result["spidev"]:
        return result
    _power_on()
    spi = spidev.SpiDev()
    spi.open(0, 2)
    spi.max_speed_hz = 1_000_000
    spi.mode = 1  # the 3916 samples on the falling edge — see header
    try:
        # Register read framing: 0b01 + 6-bit address, then data.
        reads = [spi.xfer2([0x40 | IDENTITY_REG, 0x00])[1]
                 for _ in range(3)]
    finally:
        spi.close()
    result["identity"] = reads[0]
    result["stable"] = len(set(reads)) == 1
    result["found"] = (reads[0] & ST25R3916_IDENTITY_MASK) == ST25R3916_IDENTITY
    return result


def scan_once() -> dict:
    """Full inventory attempt with the driver (init + WUPA + UID)."""
    with ST25R3916() as nfc:
        out = nfc.inventory()
        out["identity"] = nfc.identity
        out["vdd_mv"] = nfc.vdd_mv
        nfc.field_off()
        return out


def main() -> int:
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        try:
            r = scan_once()
        except RuntimeError as exc:
            print(f"NFC scan failed: {exc}")
            return 1
        if r["found"]:
            print(f"TAG FOUND — UID {r['uid']}  ATQA {r['atqa']}  "
                  f"SAK 0x{r['sak']:02X}")
        elif r.get("collision"):
            print("NFC: collision — two or more tags answered at "
                  "once (v1 reads one tag at a time)")
        else:
            print("NFC: no tag in the field "
                  f"(chip 0x{r['identity']:02X}, VDD {r['vdd_mv']} mV)")
        return 0
    r = probe()
    if not r["spidev"]:
        print("NFC: /dev/spidev0.2 missing and overlay load failed")
        return 1
    if r["found"]:
        print(f"NFC: ST25R3916 FOUND — identity 0x{r['identity']:02X} "
              f"(stable across reads: {r['stable']})")
        return 0
    print(f"NFC: chip answered 0x{r['identity']:02X}, not the "
          "ST25R3916 identity — check seating/power")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
