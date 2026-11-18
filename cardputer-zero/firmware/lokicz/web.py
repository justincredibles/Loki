"""The lokicz web portal — the whole app, in a browser.

Anyone on the same network as the Cardputer Zero can open
http://<the zero's IP>:8420 and drive lokicz: status, capture,
wardriving, sniffing, sub-GHz sweep, the network audit (with
clickable CVE links), WPA-SEC, and the saved reports. That
LAN-open model is deliberate (Justin's call — the portal is for
the home/lab network, like Bjorn's and Ragnar's web UIs); there
is no login, so treat the Wi-Fi password as the door key.

Stdlib only (http.server) — the Zero has better things to do
with its 512 MB than host a framework. Long operations run as
background jobs with progress; one hardware job at a time.
"""

import json
import re
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 8420
UI_FILE = Path(__file__).with_name("webui.html")
ICON_FILE = Path(__file__).resolve().parents[2] / "app" \
    / "packaging" / "icon.png"

_jobs: dict = {}
_op_lock = threading.Lock()
_job_seq = [0]


def lan_ip() -> str:
    """This device's LAN address (UDP connect trick — no traffic
    is actually sent, the kernel just picks the source IP)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


# --- Status -----------------------------------------------------------

def status_payload() -> dict:
    from . import app as lcd_app
    from . import audit, caps, config, meshtastic, meshcore
    from . import wifi_recon, wpasec

    cfg = config.load()
    profile = caps.detect_cap(cfg["cap"])
    w = wpasec.status(cfg)
    m = meshcore.status()
    return {
        "cap": profile.name,
        "cap_description": profile.description,
        "capture_enabled": cfg.get("capture_enabled", True),
        "capture_iface": cfg["capture_iface"],
        "dongle": wifi_recon.capture_available(cfg["capture_iface"]),
        "hashes": lcd_app._total_hashes(),
        "wpasec": w,
        "mesh": {"mode": m["mode"],
                 "meshtastic_active": m["meshtastic"]["service"],
                 "radio_proven": m["meshtastic"]["radio"],
                 "pymc_active": m["pymc_active"]},
        "last_audit": audit.latest_summary(),
        "web": {"ip": lan_ip(), "port": PORT},
    }


# --- Jobs ---------------------------------------------------------------

def _new_job(action: str) -> dict:
    _job_seq[0] += 1
    job = {"id": _job_seq[0], "action": action, "state": "running",
           "message": "starting...", "started": time.time(),
           "result": None, "error": None}
    _jobs[job["id"]] = job
    return job


def _run_job(job: dict, fn) -> None:
    if not _op_lock.acquire(blocking=False):
        job["state"] = "error"
        job["error"] = "another operation is already running"
        return
    try:
        job["result"] = fn(job)
        job["state"] = "done"
    except Exception as exc:  # surface it; never die silently
        job["state"] = "error"
        job["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        _op_lock.release()


def _start(action: str, fn) -> dict:
    job = _new_job(action)
    threading.Thread(target=_run_job, args=(job, fn),
                     daemon=True).start()
    return job


def _act_capture(cfg, seconds):
    def fn(job):
        from . import capture, wpasec

        if not cfg.get("capture_enabled", True):
            raise RuntimeError("capture is OFF (toggle it on first)")
        job["message"] = f"capturing {seconds}s on " \
                         f"{cfg['capture_iface']}..."
        stats = capture.run_capture(seconds, cfg["capture_iface"])
        if cfg.get("wpasec_enabled"):
            job["message"] = "wpa-sec auto-sync..."
            r = wpasec.sync(cfg)
            stats["wpasec"] = r
        return stats
    return fn


def _act_wardrive(cfg, seconds):
    def fn(job):
        from . import wardrive

        job["message"] = f"wardriving {seconds}s..."
        return wardrive.run_wardrive(seconds)
    return fn


def _act_sniff(cfg, seconds):
    def fn(job):
        from . import sniffer

        job["message"] = f"sniffing {seconds}s (passive)..."
        return sniffer.run_sniff(seconds)
    return fn


def _act_sweep(cfg, _seconds):
    def fn(job):
        from .cc1101 import CC1101

        job["message"] = "sweeping 430-437 + 902-928 MHz..."
        out = []
        with CC1101() as radio:
            for start, stop in ((430.0, 437.0), (902.0, 928.0)):
                sweep = radio.sweep(start, stop, 0.5, dwell_s=0.05)
                floor = sorted(r for _, r in sweep)[len(sweep) // 2]
                peak_f, peak_r = max(sweep, key=lambda t: t[1])
                out.append({"band": f"{start:.0f}-{stop:.0f} MHz",
                            "floor_dbm": round(floor),
                            "peak_dbm": round(peak_r),
                            "peak_mhz": round(peak_f, 1)})
        return {"bands": out}
    return fn


def _act_audit(cfg, _seconds):
    def fn(job):
        from . import audit

        return audit.run_audit(
            cfg, progress=lambda m: job.__setitem__("message", m))
    return fn


def _act_wpasec_sync(cfg, _seconds):
    def fn(job):
        from . import wpasec

        job["message"] = "syncing with wpa-sec..."
        return wpasec.sync(cfg)
    return fn


ACTIONS = {"capture": _act_capture, "wardrive": _act_wardrive,
           "sniff": _act_sniff, "sweep": _act_sweep,
           "audit": _act_audit, "wpasec-sync": _act_wpasec_sync}

DEFAULT_SECONDS = {"capture": "capture_seconds",
                   "wardrive": "wardrive_seconds",
                   "sniff": "sniff_seconds"}


# --- HTTP layer -----------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep the journal quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj).encode(),
                   "application/json")

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, OSError):
            return {}

    def do_GET(self):
        from . import audit, capture, wpasec

        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            self._send(200, UI_FILE.read_bytes(),
                       "text/html; charset=utf-8")
        elif path == "/icon.png" and ICON_FILE.exists():
            self._send(200, ICON_FILE.read_bytes(), "image/png")
        elif path == "/api/status":
            self._json(200, status_payload())
        elif path.startswith("/api/jobs/"):
            try:
                job = _jobs.get(int(path.rsplit("/", 1)[1]))
            except ValueError:
                job = None
            self._json(200 if job else 404, job or {"error": "no job"})
        elif path == "/api/audits":
            out = []
            for f in sorted(audit.AUDIT_DIR.glob("audit-*.json")):
                try:
                    out.append(audit.summarize(
                        json.loads(f.read_text())) | {"file": f.name})
                except (OSError, ValueError):
                    pass
            self._json(200, out)
        elif path.startswith("/api/audits/"):
            name = path.rsplit("/", 1)[1]
            if not re.fullmatch(r"audit-\d{8}-\d{6}\.json", name):
                return self._json(400, {"error": "bad report name"})
            f = audit.AUDIT_DIR / name
            if f.exists():
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._json(404, {"error": "no such report"})
        elif path == "/api/captures":
            files = [{"name": p.name,
                      "kb": p.stat().st_size // 1024}
                     for p in sorted(capture.CAPTURE_DIR.glob("*"))
                     if p.is_file()]
            found = []
            if wpasec.FOUND_PATH.exists():
                for line in wpasec.FOUND_PATH.read_text().splitlines():
                    parts = line.split(",", 3)
                    if len(parts) == 4:
                        found.append({"bssid": parts[0],
                                      "station": parts[1],
                                      "ssid": parts[2],
                                      "password": parts[3]})
            self._json(200, {"files": files, "cracked": found})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        from . import config

        path = urllib.parse.urlparse(self.path).path
        cfg = config.load()
        if path.startswith("/api/run/"):
            action = path.rsplit("/", 1)[1]
            if action not in ACTIONS:
                return self._json(404, {"error": "unknown action"})
            body = self._body()
            seconds = body.get("seconds")
            if action in DEFAULT_SECONDS:
                seconds = int(seconds or cfg[DEFAULT_SECONDS[action]])
                seconds = max(10, min(seconds, 1800))
            job = _start(action, ACTIONS[action](cfg, seconds))
            return self._json(202, {"job": job["id"]})
        if path == "/api/toggle/capture":
            cfg["capture_enabled"] = not cfg.get("capture_enabled",
                                                 True)
            config.save(cfg)
            return self._json(200, {"capture_enabled":
                                    cfg["capture_enabled"]})
        if path == "/api/toggle/wpasec":
            cfg["wpasec_enabled"] = not cfg.get("wpasec_enabled",
                                                False)
            config.save(cfg)
            return self._json(200, {"wpasec_enabled":
                                    cfg["wpasec_enabled"]})
        self._json(404, {"error": "not found"})


def main() -> int:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"lokicz web portal on http://{lan_ip()}:{PORT}",
          flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
