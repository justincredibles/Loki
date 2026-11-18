"""Sub-GHz OOK decode — turn raw .sub timings into protocol data.

The CC1101 capture path records *when* the air was hot, as
signed microsecond runs (Flipper .sub RAW format). This module
is the brains that read those runs back:

- **PWM pair decoding** — the EV1527 / PT2262 remote family and
  its many clones: every bit is one mark + one space of constant
  total length; a long mark means 1, a short mark means 0. A
  24-bit result is reported as the EV1527 family (20-bit address
  + 4-bit data); other lengths as generic PWM remotes.
- **Manchester decoding** — many weather sensors and utility
  meters send Manchester-coded frames. Chips are recovered from
  the run lengths, paired into bits, and reported as hex.
- Anything else is reported honestly as unknown OOK, with the
  pulse statistics that were measured (dominant cell length,
  bits per burst) — a lead for a human, not a fake verdict.

Remotes repeat their frame several times per press, so the
decoder segments the stream into bursts and lets identical
frames vote: the most-repeated clean frame is the answer, and
repetition is what earns a "high" confidence.
"""

from pathlib import Path

SUBGHZ_DIR = Path.home() / "lokicz-subghz"

# A silence longer than this (µs) separates two bursts/frames.
SPLIT_GAP_US = 1500


def parse_sub(path) -> tuple[int, list[int]]:
    """Read a Flipper .sub RAW file → (frequency Hz, signed runs)."""
    freq_hz = 0
    runs: list[int] = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line.startswith("Frequency:"):
            freq_hz = int(line.split(":", 1)[1].strip())
        elif line.startswith("RAW_Data:"):
            runs += [int(v) for v in line.split(":", 1)[1].split()]
    return freq_hz, runs


def split_bursts(runs: list[int],
                 gap_us: int = SPLIT_GAP_US) -> list[list[int]]:
    """Split a run stream into bursts at long silences.

    Each returned burst starts with a mark (positive run) and
    alternates; fragments of leading/trailing silence are dropped.
    """
    bursts: list[list[int]] = []
    current: list[int] = []
    for run in runs:
        if run < 0 and -run >= gap_us:
            if current:
                bursts.append(current)
                current = []
            continue
        if not current and run < 0:
            continue  # leading silence inside a burst window
        if current and (current[-1] > 0) == (run > 0):
            current[-1] += run  # merge same-sign neighbours
        else:
            current.append(run)
    if current:
        bursts.append(current)
    return bursts


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _decode_pwm(burst: list[int]) -> dict | None:
    """EV1527-style: constant mark+space cells, mark width = bit."""
    pairs = []
    seq = burst if burst[0] > 0 else burst[1:]
    for i in range(0, len(seq) - 1, 2):
        mark, space = seq[i], -seq[i + 1]
        if mark > 0 and space > 0:
            pairs.append((mark, space))
    if len(pairs) < 8:
        return None
    cells = [m + s for m, s in pairs]
    cell = _median(cells)
    if cell <= 0:
        return None
    # Real PWM remotes are metronomes: nearly every cell lands
    # within ±25% of the median. (A loose check here once let
    # Manchester frames "decode" as garbage PWM — tightened
    # after exactly that failure in testing.)
    in_tolerance = sum(1 for c in cells if 0.75 * cell <= c <= 1.3 * cell)
    if in_tolerance < 0.9 * len(cells):
        return None
    bits = "".join("1" if m > cell / 2 else "0" for m, _ in pairs)
    # Both mark clusters should exist (all-0/all-1 codes are
    # implausible for a remote and usually mean a misread cell).
    marks = [m for m, _ in pairs]
    if min(marks) > cell / 2 or max(marks) < cell / 2:
        return None
    return {"kind": "pwm", "bits": bits, "cell_us": round(cell)}


def _decode_manchester(burst: list[int]) -> dict | None:
    """Manchester: runs are 1 or 2 chips; chip pairs form bits."""
    durations = [abs(r) for r in burst]
    if len(durations) < 16:
        return None
    chip = _median(sorted(durations)[: max(4, len(durations) // 4)])
    if chip <= 0:
        return None
    chips: list[int] = []
    for run in burst:
        n = round(abs(run) / chip)
        if n < 1 or n > 8 or abs(abs(run) - n * chip) > 0.35 * chip:
            return None
        chips += [1 if run > 0 else 0] * n
    if len(chips) < 32 or len(chips) % 2:
        return None
    for one_is in ((1, 0), (0, 1)):
        bits = []
        ok = True
        for i in range(0, len(chips), 2):
            pair = (chips[i], chips[i + 1])
            if pair == one_is:
                bits.append("1")
            elif pair == (one_is[1], one_is[0]):
                bits.append("0")
            else:
                ok = False
                break
        if ok:
            return {"kind": "manchester", "bits": "".join(bits),
                    "cell_us": round(chip * 2)}
    return None


def _bits_to_hex(bits: str) -> str:
    padded = bits + "0" * (-len(bits) % 4)
    return "".join(f"{int(padded[i:i + 4], 2):X}"
                   for i in range(0, len(padded), 4))


def decode_runs(runs: list[int]) -> dict:
    """Decode a signed-run stream. See module header for honesty
    rules: repetition across bursts is what earns confidence."""
    bursts = split_bursts(runs)
    frames: dict[str, dict] = {}
    decoded_bursts = 0
    for burst in bursts:
        hit = _decode_pwm(burst) or _decode_manchester(burst)
        if hit is None:
            continue
        decoded_bursts += 1
        entry = frames.setdefault(hit["bits"],
                                  {"count": 0, "kind": hit["kind"],
                                   "cell_us": hit["cell_us"]})
        entry["count"] += 1
    base = {"bursts": len(bursts), "decoded_bursts": decoded_bursts,
            "protocol": "Unknown OOK", "bits": None, "code_hex": None,
            "bit_count": 0, "confidence": "low", "frames": []}
    if not frames:
        # Pulse statistics are still a useful lead.
        marks = [r for r in runs if r > 0]
        if marks:
            base["pulse_us"] = {
                "min": min(marks), "max": max(marks),
                "median": round(_median(marks))}
        return base
    ranked = sorted(frames.items(), key=lambda kv: (-kv[1]["count"],
                                                     -len(kv[0])))
    base["frames"] = [{"bits": b, "count": e["count"], "kind": e["kind"]}
                      for b, e in ranked[:4]]
    bits, entry = ranked[0]
    base.update({"bits": bits, "bit_count": len(bits),
                 "code_hex": _bits_to_hex(bits),
                 "cell_us": entry["cell_us"]})
    if entry["kind"] == "pwm":
        base["protocol"] = ("EV1527/PT2262 family (PWM remote)"
                            if len(bits) == 24 else
                            "PWM remote (generic)")
    else:
        base["protocol"] = "Manchester-coded frame"
    if entry["count"] >= 2:
        base["confidence"] = "high"
    elif decoded_bursts >= 1:
        base["confidence"] = "medium"
    return base


def decode_file(path) -> dict:
    """Decode one .sub file; adds file/frequency context."""
    freq_hz, runs = parse_sub(path)
    out = decode_runs(runs)
    out["file"] = str(path)
    out["frequency_hz"] = freq_hz
    out["runs"] = len(runs)
    return out


def list_captures() -> list[dict]:
    """Recorded .sub files, newest first."""
    if not SUBGHZ_DIR.exists():
        return []
    files = sorted(SUBGHZ_DIR.glob("*.sub"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "size": p.stat().st_size,
             "mtime": int(p.stat().st_mtime)} for p in files]


def main() -> int:
    import sys

    if len(sys.argv) > 1:
        r = decode_file(sys.argv[1])
        if r["bits"]:
            print(f"{r['protocol']} — {r['bit_count']} bits, "
                  f"code 0x{r['code_hex']} "
                  f"(confidence {r['confidence']}, "
                  f"{r['decoded_bursts']}/{r['bursts']} bursts decoded)")
        else:
            print(f"No protocol decoded ({r['bursts']} bursts, "
                  f"pulse stats {r.get('pulse_us')})")
        return 0
    print("usage: python3 -m lokicz.subghz <file.sub>")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
