"""WPA-SEC addon — handshake sharing with wpa-sec.stanev.org.

What it does, in plain English:
- wpa-sec is a long-running community service that collects Wi-Fi
  handshake captures; volunteers around the world try to crack
  them, and the site hands the cracked passwords back to whoever
  uploaded the capture. You identify yourself with a personal API
  key (the site issues one — "issue your own key" on its front
  page; there is no account or password).
- When enabled, lokicz uploads each NEW capture file (the raw
  .pcapng, exactly as hcxdumptool wrote it — the site explicitly
  asks for captures unmodified) and downloads your cracked results
  into ~/lokicz-captures/wpa-sec.found, one line per network:
  bssid, station, ssid, password.
- A small state file remembers which captures were already sent,
  so nothing is uploaded twice. The site also answers
  "already submitted" for duplicates, which we treat as success.

Posture: this is OFF by default and stays off until the user turns
it on in the menu (key 9) AND sets an API key. Nothing leaves the
device before both are true. Uploading is also skipped entirely
while the capture master toggle is off — no captures, no uploads.

Protocol (the site's own API, as used by its ecosystem of tools):
- Upload:   POST https://wpa-sec.stanev.org/?putfile
            Cookie: key=<api key>; multipart field "file".
- Download: GET  https://wpa-sec.stanev.org/?api&dl=1
            Cookie: key=<api key>.
"""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from .capture import CAPTURE_DIR

BASE_URL = "https://wpa-sec.stanev.org"
STATE_PATH = Path.home() / ".config" / "lokicz" / "wpasec_state.json"
FOUND_PATH = CAPTURE_DIR / "wpa-sec.found"
TIMEOUT = 30


class WpasecError(Exception):
    """A sync step failed in a way the user should hear about."""


# --- state -----------------------------------------------------------------

def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except (OSError, ValueError):
        return {"uploaded": [], "last_sync": None}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


def api_key(cfg: dict) -> str:
    return cfg.get("wpasec_key") or os.environ.get("LOKICZ_WPASEC_KEY", "")


def pending_uploads(state: dict) -> list[Path]:
    done = set(state.get("uploaded", []))
    if not CAPTURE_DIR.exists():
        return []
    return sorted(p for p in CAPTURE_DIR.glob("*.pcapng")
                  if p.name not in done)


def cracked_lines() -> list[str]:
    try:
        return [ln for ln in FOUND_PATH.read_text().splitlines()
                if ln.strip()]
    except OSError:
        return []


def status(cfg: dict) -> dict:
    """Local facts only — no network. For the menu screen."""
    state = _load_state()
    return {"enabled": bool(cfg.get("wpasec_enabled")),
            "key_set": bool(api_key(cfg)),
            "pending": len(pending_uploads(state)),
            "uploaded": len(state.get("uploaded", [])),
            "cracked": len(cracked_lines()),
            "last_sync": state.get("last_sync")}


# --- network -----------------------------------------------------------------

def _request(url: str, key: str, body: bytes | None = None,
             content_type: str | None = None) -> str:
    req = urllib.request.Request(url, data=body, method="POST"
                                 if body is not None else "GET")
    req.add_header("Cookie", f"key={key}")
    req.add_header("User-Agent", "lokicz/0.1 (+wpa-sec addon)")
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        raise WpasecError(f"wpa-sec unreachable: {e.reason}") from e


def _upload_one(path: Path, key: str) -> str:
    boundary = f"----lokicz{int(time.time() * 1000)}"
    data = path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; '
        f'filename="{path.name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    text = _request(f"{BASE_URL}/?putfile", key, body,
                    f"multipart/form-data; boundary={boundary}")
    return "already submitted" if "already submitted" in text else "ok"


def _download_found(key: str) -> list[str]:
    text = _request(f"{BASE_URL}/?api&dl=1", key)
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


# --- the sync ------------------------------------------------------------------

def sync(cfg: dict) -> dict:
    """Upload new captures, then download cracked results.

    Returns a plain result dict; never raises for expected
    problems (off, no key, no network) — the reason is in the dict.
    """
    if not cfg.get("wpasec_enabled"):
        return {"ok": False, "reason": "WPA-SEC is off"}
    if not cfg.get("capture_enabled", True):
        return {"ok": False,
                "reason": "capture is off — nothing to sync"}
    key = api_key(cfg)
    if not key:
        return {"ok": False, "reason": "no API key set"}

    state = _load_state()
    uploaded_now, failures = 0, 0
    for path in pending_uploads(state):
        try:
            _upload_one(path, key)
            state["uploaded"].append(path.name)
            uploaded_now += 1
        except (WpasecError, OSError):
            failures += 1
    new_cracks = 0
    try:
        fresh = _download_found(key)
        known = set(cracked_lines())
        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        with FOUND_PATH.open("a") as f:
            for ln in fresh:
                if ln not in known:
                    f.write(ln + "\n")
                    new_cracks += 1
    except WpasecError:
        failures += 1
    state["last_sync"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_state(state)
    return {"ok": failures == 0, "uploaded": uploaded_now,
            "failures": failures, "cracked_new": new_cracks,
            "cracked_total": len(cracked_lines())}


def main() -> int:
    import sys

    from . import config

    cfg = config.load()
    if len(sys.argv) > 1 and sys.argv[1] == "sync":
        print(sync(cfg))
    else:
        print(status(cfg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
