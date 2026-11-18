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
MESH_UI_FILE = Path(__file__).with_name("meshui.html")

_DONGLES_FALLBACK = """# Supported USB Wi-Fi dongles

The full list lives in docs/DONGLES.md in the Loki repo; this
install couldn't find that file, so here is the short version.

## Tier 1 — plug-and-play (in-kernel drivers)

| Adapter | Chipset | Bands | Notes |
|---|---|---|---|
| **ALFA AWUS036ACM** | MediaTek MT7612U | dual | **Recommended** — monitor + injection + active monitor |
| ALFA AWUS036ACHM / Panda PAU0B / ASUS USB-AC51 | MT7610U | dual | Same class, smaller |
| ALFA AWUS036NHA | Atheros AR9271 | 2.4 GHz | Long-capture reliability king |
| Panda PAU09 | Ralink RT5572 | dual | Cheaper dual-band |
| Panda PAU06 | Ralink RT5372 | 2.4 GHz | Cheapest solid option |
| TP-Link Archer T3U class | Realtek RTL8822BU | dual | The verified baseline — capture works, injection weak |

## Not supported

- TL-WN722N v2/v3, RTL8821CU/8811CU combo sticks, RTL8852AU,
  MT7921AU, anything Broadcom.
"""


def _md_inline(text: str) -> str:
    import html as _html
    import re as _re

    out = _html.escape(text)
    out = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    out = _re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = _re.sub(r"\*([^*]+)\*", r"<i>\1</i>", out)
    return out


def _md_to_html(md: str) -> str:
    """Just enough markdown for docs/DONGLES.md: headings,
    paragraphs, bold/code/italic, bullet lists, pipe tables."""
    lines = md.splitlines()
    out, i = [], 0

    def cells(row):
        return [c.strip() for c in row.strip().strip("|").split("|")]

    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("|") and i + 1 < len(lines) and \
                set(lines[i + 1].replace("|", "")
                    .replace(" ", "")) <= set("-:"):
            head = cells(line)
            rows = []
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(cells(lines[i]))
                i += 1
            out.append(
                "<table><tr>" + "".join(
                    f"<th>{_md_inline(c)}</th>" for c in head) + "</tr>"
                + "".join(
                    "<tr>" + "".join(
                        f"<td>{_md_inline(c)}</td>" for c in r) + "</tr>"
                    for r in rows) + "</table>")
            continue
        if line.startswith("## "):
            out.append(f"<h2>{_md_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(
                f"<h1 style=\"color:var(--gold-hi);"
                f"letter-spacing:3px\">{_md_inline(line[2:])}</h1>")
        elif line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{_md_inline(lines[i][2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif line.strip():
            out.append(f"<p>{_md_inline(line)}</p>")
        i += 1
    return "\n".join(out)


def _dongles_html() -> bytes:
    md_path = Path(__file__).resolve().parents[2] / "docs" \
        / "DONGLES.md"
    try:
        md = md_path.read_text()
        src = "Rendered live from docs/DONGLES.md in the Loki repo."
    except OSError:
        md = _DONGLES_FALLBACK
        src = "Bundled summary (repo doc not found in this install)."
    css = UI_FILE.read_text().split("<style>", 1)[1] \
        .split("</style>", 1)[0]
    page = (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, "
        "initial-scale=1\">"
        "<title>LOKI — Supported USB Wi-Fi Dongles</title>"
        f"<style>{css}</style></head><body><main>"
        f"{_md_to_html(md)}"
        f"<p class=\"dim\">{src}</p>"
        "<p><a href=\"/\" style=\"color:var(--cyan)\">"
        "← back to the portal</a></p>"
        "</main></body></html>")
    return page.encode()
ICON_FILE = Path(__file__).resolve().parents[2] / "app" \
    / "packaging" / "icon.png"

_jobs: dict = {}

REPO_DIR = Path(__file__).resolve().parents[3]
UPDATE_LOG = Path("/tmp/lokicz-update.log")


def _download_dirs() -> dict:
    from . import audit, capture, gpslog, probes, sniffer, wardrive

    return {"captures": capture.CAPTURE_DIR,
            "audits": audit.AUDIT_DIR,
            "subghz": Path.home() / "lokicz-subghz",
            "wardrives": wardrive.WARDRIVE_DIR,
            "tracks": gpslog.TRACK_DIR,
            "probes": probes.PROBE_DIR,
            "sniffs": sniffer.SNIFF_DIR}


def _repo_rev() -> str:
    import subprocess

    try:
        return subprocess.run(
            ["git", "-C", str(REPO_DIR), "rev-parse", "--short",
             "HEAD"], capture_output=True, text=True,
            timeout=10).stdout.strip() or "unknown"
    except Exception:
        return "unknown"
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
        "battery": _battery_status(),
        "web": {"ip": lan_ip(), "port": PORT},
    }


def _battery_status() -> dict:
    """The BQ27220 fuel gauge, for the portal status cards."""
    batt = Path("/sys/class/power_supply/bq27220-0")
    try:
        return {
            "pct": int((batt / "capacity").read_text().strip()),
            "status": (batt / "status").read_text().strip(),
            "voltage_mv":
                int((batt / "voltage_now").read_text().strip()) // 1000,
        }
    except (OSError, ValueError):
        return {"pct": None, "status": "unknown", "voltage_mv": None}


def _screenshot_png() -> bytes:
    """The LCD's current frame as a PNG, decoded from the
    framebuffer — what the Loki UI last drew. (When the stock
    desktop owns the panel it isn't in this buffer.)"""
    import io

    import numpy as np
    from PIL import Image

    raw = Path("/dev/fb_lcd").read_bytes()[:320 * 170 * 2]
    a = np.frombuffer(raw, dtype="<u2").reshape(170, 320)
    r = ((a >> 11) & 31).astype("uint8") * 255 // 31
    g = ((a >> 5) & 63).astype("uint8") * 255 // 63
    b = (a & 31).astype("uint8") * 255 // 31
    img = Image.fromarray(np.dstack([r, g, b]).astype("uint8"))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


# --- Jobs ---------------------------------------------------------------

def _new_job(action: str) -> dict:
    _job_seq[0] += 1
    job = {"id": _job_seq[0], "action": action, "state": "running",
           "message": "starting...", "started": time.time(),
           "result": None, "error": None}
    _jobs[job["id"]] = job
    # Prune finished history so the dict (and the /api/jobs list)
    # stays small; never drop a running job.
    if len(_jobs) > 20:
        for jid in sorted(_jobs):
            if len(_jobs) <= 20:
                break
            if _jobs[jid]["state"] != "running":
                del _jobs[jid]
    return job


def _run_job(job: dict, fn) -> None:
    if not _op_lock.acquire(blocking=False):
        job["state"] = "error"
        job["error"] = "another operation is already running"
        job["ended"] = time.time()
        return
    try:
        job["result"] = fn(job)
        job["state"] = "done"
        try:
            from . import avatar

            news = avatar.award_for(job["action"], job["result"])
            if news.get("xp_gained"):
                job["avatar"] = news
        except Exception:
            pass
    except Exception as exc:  # surface it; never die silently
        job["state"] = "error"
        job["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        job["ended"] = time.time()
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


def _act_gps(cfg, _seconds):
    def fn(job):
        from . import gpslog

        job["message"] = "recording GPS track (2 min)..."
        return gpslog.track(120)
    return fn


def _act_watchdog(cfg, _seconds):
    def fn(job):
        from . import watchdog

        return watchdog.run_once(
            cfg, progress=lambda m: job.__setitem__("message", m))
    return fn


def _act_probes(cfg, _seconds):
    def fn(job):
        from . import probes

        job["message"] = "listening for probe requests (60s)..."
        return probes.run_probes(60, cfg["capture_iface"])
    return fn


def _act_trackers(cfg, _seconds):
    def fn(job):
        from . import trackers

        job["message"] = "listening for trackers (90s)..."
        return trackers.watch(90)
    return fn


def _act_proximity(cfg, _seconds):
    def fn(job):
        from . import proximity

        job["message"] = "listening for nearby radios (25s)..."
        return proximity.scan(25)
    return fn


def _act_ook(cfg, seconds):
    def fn(job):
        import time as _time

        from . import subghz
        from .cc1101 import CC1101

        secs = seconds or 20
        job["message"] = f"listening on 433.92 MHz ({secs}s) — " \
                         "press the fob now..."
        stamp = _time.strftime("%Y%m%d-%H%M%S")
        path = subghz.SUBGHZ_DIR / f"ook-433.92MHz-{stamp}.sub"
        with CC1101() as radio:
            stats = radio.capture_ook(433.92, secs, str(path))
        job["message"] = "decoding..."
        stats["decode"] = subghz.decode_file(str(path))
        return stats
    return fn


def _act_replay(cfg, _seconds):
    def fn(job):
        from . import subghz
        from .cc1101 import CC1101

        caps_list = subghz.list_captures()
        if not caps_list:
            raise RuntimeError("no .sub captures yet — run an OOK "
                               "capture first")
        path = subghz.SUBGHZ_DIR / caps_list[0]["name"]
        job["message"] = f"replaying {path.name} (TX)..."
        with CC1101() as radio:
            return radio.replay_sub(str(path), 3)
    return fn


def _act_mesh_listen(cfg, seconds):
    def fn(job):
        from . import meshchat

        secs = seconds or 30
        job["message"] = f"listening for mesh texts ({secs}s)..."
        return meshchat.listen(cfg, secs)
    return fn


def _act_mesh_nodes(cfg, _seconds):
    def fn(job):
        from . import meshchat

        job["message"] = "asking meshtasticd for the node list..."
        return meshchat.nodes(cfg)
    return fn


def _act_mesh_send(cfg, text):
    def fn(job):
        from . import meshchat

        job["message"] = "sending mesh text..."
        return meshchat.send(cfg, text)
    return fn


def _act_mesh_setch(cfg, body):
    def fn(job):
        from . import meshchat

        job["message"] = "writing channel (node reboots)..."
        return meshchat.set_channel(cfg, body.get("index", 0),
                                    str(body.get("name", "")),
                                    body.get("psk"))
    return fn


def _act_mesh_delch(cfg, body):
    def fn(job):
        from . import meshchat

        job["message"] = "disabling channel (node reboots)..."
        return meshchat.del_channel(cfg, body.get("index", -1))
    return fn


def _act_mesh_setconfig(cfg, body):
    def fn(job):
        from . import meshchat

        job["message"] = "writing config (node reboots)..."
        return meshchat.set_config(cfg, str(body.get("section", "")),
                                   body.get("fields") or {})
    return fn


def _act_meshcore_setconfig(cfg, body):
    def fn(job):
        from . import meshcore

        job["message"] = "writing MeshCore config..."
        return meshcore.write_config(body.get("fields") or {})
    return fn


def _act_mesh_setname(cfg, body):
    def fn(job):
        from . import meshchat

        job["message"] = "setting node names (node reboots)..."
        return meshchat.set_name(cfg, str(body.get("long", "")),
                                 str(body.get("short", "")))
    return fn


def _act_nfc(cfg, _seconds):
    def fn(job):
        from . import nfc

        job["message"] = "NFC field on — hold a tag to the cap..."
        return nfc.scan_once()
    return fn


def _act_wpasec_sync(cfg, _seconds):
    def fn(job):
        from . import wpasec

        job["message"] = "syncing with wpa-sec..."
        return wpasec.sync(cfg)
    return fn


ACTIONS = {"capture": _act_capture, "wardrive": _act_wardrive,
           "sniff": _act_sniff, "sweep": _act_sweep,
           "audit": _act_audit, "wpasec-sync": _act_wpasec_sync,
           "proximity": _act_proximity,
           "trackers": _act_trackers,
           "probes": _act_probes,
           "watchdog": _act_watchdog,
           "gps": _act_gps,
           "ook": _act_ook, "replay": _act_replay,
           "nfc": _act_nfc, "mesh-listen": _act_mesh_listen,
           "mesh-nodes": _act_mesh_nodes}

DEFAULT_SECONDS = {"capture": "capture_seconds",
                   "wardrive": "wardrive_seconds",
                   "sniff": "sniff_seconds"}


# --- HTTP layer -----------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep the journal quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str,
              headers: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
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
        from . import audit, capture, config, flights, wpasec

        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            self._send(200, UI_FILE.read_bytes(),
                       "text/html; charset=utf-8")
        elif path == "/api/flights":
            self._json(200, flights.nearest(config.load()))
        elif path == "/api/trackers":
            from . import trackers

            self._json(200, trackers.known())
        elif path == "/api/watchdog":
            from . import watchdog

            self._json(200, watchdog.latest_state())
        elif path == "/api/tracks":
            from . import gpslog

            self._json(200, gpslog.list_tracks())
        elif path == "/icon.png" and ICON_FILE.exists():
            self._send(200, ICON_FILE.read_bytes(), "image/png")
        elif path == "/api/mesh":
            from . import meshchat, meshcore

            cfg = config.load()
            out = {"cap": cfg.get("cap"), **meshcore.status(),
                   "chat": None}
            if out["meshtastic"].get("api"):
                try:
                    out["chat"] = meshchat.info(cfg)
                except Exception as exc:
                    out["chat_error"] = str(exc)
            self._json(200, out)
        elif path == "/mesh":
            self._send(200, MESH_UI_FILE.read_bytes(),
                       "text/html; charset=utf-8")
        elif path == "/dongles":
            self._send(200, _dongles_html(),
                       "text/html; charset=utf-8")
        elif path == "/manifest.webmanifest":
            self._send(200, (
                '{"name": "LokiCZ — Cardputer Zero", '
                '"short_name": "LokiCZ", "start_url": "/", '
                '"scope": "/", "display": "standalone", '
                '"background_color": "#030a06", '
                '"theme_color": "#030a06", '
                '"icons": [{"src": "/icon.png", "sizes": "256x256", '
                '"type": "image/png", "purpose": "any"}]}'
            ).encode(), "application/manifest+json")
        elif path == "/api/mesh/messages":
            import json as _json
            import time as _time
            from pathlib import Path as _Path

            q = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query)
            try:
                limit = max(1, min(int(q.get("limit", ["200"])[0]),
                                   1000))
            except ValueError:
                limit = 200
            chan = q.get("channel", ["0"])[0]
            log_dir = _Path.home() / "lokicz-meshlog"
            msgs = []
            try:
                lines = (log_dir / "messages.jsonl") \
                    .read_text().splitlines()[-4000:]
                for line in lines:
                    try:
                        msgs.append(_json.loads(line))
                    except ValueError:
                        continue
            except OSError:
                pass
            total = len(msgs)
            if chan == "dm":
                msgs = [m for m in msgs if m.get("dm")]
            elif chan != "all":
                try:
                    want = int(chan)
                    msgs = [m for m in msgs
                            if not m.get("dm")
                            and (m.get("channel") or 0) == want]
                except ValueError:
                    pass
            try:
                age = _time.time() - (log_dir / "heartbeat") \
                    .stat().st_mtime
                collecting = age < 90
            except OSError:
                collecting = False
            self._json(200, {"messages": msgs[-limit:],
                             "total": total,
                             "collecting": collecting})
        elif path == "/api/mesh/config":
            from . import meshchat

            try:
                self._json(200, meshchat.get_config(config.load()))
            except Exception as exc:
                self._json(200, {"error": str(exc)})
        elif path == "/api/meshcore/config":
            from . import meshcore

            self._json(200, meshcore.read_config())
        elif path == "/api/mesh/channels":
            from . import meshchat

            try:
                self._json(200, meshchat.channels(config.load()))
            except Exception as exc:
                self._json(200, {"error": str(exc)})
        elif path == "/api/status":
            self._json(200, status_payload())
        elif path == "/api/jobs":
            # Recent jobs, newest first — a freshly loaded page
            # uses this to reattach to whatever is running (or
            # just finished) instead of losing the status box.
            recent = sorted(_jobs.values(),
                            key=lambda j: j["started"],
                            reverse=True)[:5]
            self._json(200, {"jobs": recent})
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
        elif path == "/api/files":
            out = {}
            for kind, folder in _download_dirs().items():
                files = []
                if folder.exists():
                    for p in sorted(folder.iterdir(),
                                    key=lambda p: p.stat().st_mtime,
                                    reverse=True):
                        if p.is_file():
                            files.append(
                                {"name": p.name,
                                 "kb": p.stat().st_size // 1024})
                out[kind] = files[:60]
            self._json(200, out)
        elif path.startswith("/api/download/"):
            parts = path.split("/")
            kind = parts[3] if len(parts) > 3 else ""
            name = parts[4] if len(parts) > 4 else ""
            folder = _download_dirs().get(kind)
            target = folder / name if folder else None
            if target is None or Path(name).name != name \
                    or not target.is_file() \
                    or target.resolve().parent != folder.resolve():
                return self._json(404, {"error": "no such file"})
            self._send(200, target.read_bytes(),
                       "application/octet-stream",
                       {"Content-Disposition":
                        f'attachment; filename="{name}"'})
        elif path == "/api/update/status":
            log = ""
            if UPDATE_LOG.exists():
                log = "\n".join(
                    UPDATE_LOG.read_text(errors="replace")
                    .splitlines()[-12:])
            self._json(200, {"rev": _repo_rev(), "log": log})
        elif path == "/api/avatar":
            from . import avatar

            self._json(200, avatar.state())
        elif path == "/api/avatar.png":
            from . import avatar, ui

            qs = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query)
            mood = qs.get("mood", ["idle"])[0]
            self._send(200, ui.render_avatar_png(
                avatar.load()["gear"],
                mood=mood if mood == "excited" else "idle"),
                "image/png")
        elif path == "/api/screenshot.png":
            try:
                self._send(200, _screenshot_png(), "image/png")
            except Exception as exc:
                self._json(500, {"error": f"screenshot failed: {exc}"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        from . import config

        path = urllib.parse.urlparse(self.path).path
        cfg = config.load()
        if path.startswith("/api/run/"):
            action = path.rsplit("/", 1)[1]
            body = self._body()
            if action == "mesh-send":  # takes {text}, not {seconds}
                job = _start(action, _act_mesh_send(
                    cfg, str(body.get("text", ""))))
                return self._json(202, {"job": job["id"]})
            if action == "mesh-setch":
                job = _start(action, _act_mesh_setch(cfg, body))
                return self._json(202, {"job": job["id"]})
            if action == "mesh-delch":
                job = _start(action, _act_mesh_delch(cfg, body))
                return self._json(202, {"job": job["id"]})
            if action == "mesh-setname":
                job = _start(action, _act_mesh_setname(cfg, body))
                return self._json(202, {"job": job["id"]})
            if action == "mesh-setconfig":
                job = _start(action, _act_mesh_setconfig(cfg, body))
                return self._json(202, {"job": job["id"]})
            if action == "meshcore-setconfig":
                job = _start(action,
                             _act_meshcore_setconfig(cfg, body))
                return self._json(202, {"job": job["id"]})
            if action not in ACTIONS:
                return self._json(404, {"error": "unknown action"})
            seconds = body.get("seconds")
            if action in DEFAULT_SECONDS:
                seconds = int(seconds or cfg[DEFAULT_SECONDS[action]])
                seconds = max(10, min(seconds, 1800))
            job = _start(action, ACTIONS[action](cfg, seconds))
            return self._json(202, {"job": job["id"]})
        if path == "/api/mesh/mode":
            from . import meshcore

            body = self._body()
            mode = str(body.get("mode", ""))
            if mode not in ("meshtastic", "meshcore", "off"):
                return self._json(400, {"error": "bad mode"})
            cfg["mesh_mode"] = mode
            config.save(cfg)
            return self._json(200, {"mode": mode, "result":
                                    meshcore.apply_mode(mode,
                                                        cfg["cap"])})
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
        if path == "/api/update":
            import subprocess

            script_path = Path("/tmp/lokicz-update.sh")
            script_path.write_text(
                "#!/bin/bash\n"
                "echo '--- update started'\n"
                f"git -C {REPO_DIR} pull --ff-only\n"
                "echo '--- restarting services'\n"
                "sleep 1\n"
                "sudo systemctl restart lokicz lokicz-web\n"
                "echo '--- update done'\n")
            subprocess.Popen(
                ["bash", "-c",
                 f"nohup bash {script_path} > {UPDATE_LOG} 2>&1 &"])
            return self._json(202, {"started": True,
                                    "from_rev": _repo_rev()})
        if path == "/api/avatar/equip":
            from . import avatar

            body = self._body()
            ok, why = avatar.equip(str(body.get("slot", "")),
                                   str(body.get("item", "")))
            return self._json(200 if ok else 400,
                              {"ok": ok, "reason": why,
                               "state": avatar.state()})
        self._json(404, {"error": "not found"})


def main() -> int:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"lokicz web portal on http://{lan_ip()}:{PORT}",
          flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
