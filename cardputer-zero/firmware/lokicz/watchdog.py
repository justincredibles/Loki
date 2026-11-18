"""Audit watchdog — scheduled audits, diffed, with alerts.

One watchdog run = one full audit + a diff against the previous
report. The diff is the alert surface:

- NEW HOSTS — a device joined the network since last time
  (the headline alert: unknown hardware on your LAN)
- GONE HOSTS — something left or stopped answering
- NEW PORTS — a known host opened something new
- NEW CVEs — findings that weren't in the last report
- FIXED — CVE count that disappeared (patching works)

Hosts are keyed by MAC when known (IPs get recycled by DHCP;
MACs don't move). Diffs land beside the reports in
~/lokicz-audits/diff-<stamp>.json; the newest diff summary is
kept in ~/.config/lokicz/watchdog_state.json for the LCD status
screen and the portal.

Runs three ways: the portal's WATCHDOG job, `python3 -m
lokicz.watchdog`, and the lokicz-watchdog systemd timer
(nightly). A first-ever run has nothing to diff against — it
just establishes the baseline.
"""

import json
import time
from pathlib import Path

from . import audit

STATE_PATH = Path.home() / ".config" / "lokicz" / "watchdog_state.json"


def _host_key(host: dict) -> str:
    return (host.get("mac") or host["ip"]).upper()


def _cve_index(report: dict) -> dict:
    """(host_key, port) -> set of CVE ids."""
    index = {}
    for host in report["hosts"]:
        for port in host["ports"]:
            ids = {v["id"] for v in port["vulns"]}
            if ids:
                index[(_host_key(host), port["port"])] = ids
    return index


def _port_index(report: dict) -> dict:
    """host_key -> {(port, service)}."""
    index = {}
    for host in report["hosts"]:
        index[_host_key(host)] = {
            (p["port"], p["service"]) for p in host["ports"]}
    return index


def diff_reports(old: dict, new: dict) -> dict:
    old_hosts = {_host_key(h): h for h in old["hosts"]}
    new_hosts = {_host_key(h): h for h in new["hosts"]}

    def brief(h):
        return {"ip": h["ip"], "mac": h.get("mac", ""),
                "hostname": h.get("hostname", "")}

    new_host_list = [brief(new_hosts[k])
                     for k in new_hosts.keys() - old_hosts.keys()]
    gone_list = [brief(old_hosts[k])
                 for k in old_hosts.keys() - new_hosts.keys()]

    old_ports, new_ports = _port_index(old), _port_index(new)
    port_changes = []
    for key in new_hosts.keys() & old_hosts.keys():
        for port, svc in sorted(new_ports.get(key, set())
                                - old_ports.get(key, set())):
            port_changes.append({"ip": new_hosts[key]["ip"],
                                 "port": port, "service": svc})

    old_cves, new_cves = _cve_index(old), _cve_index(new)
    cve_changes = []
    fixed = unseen = 0
    scores = {}
    for host in new["hosts"]:
        for port in host["ports"]:
            for v in port["vulns"]:
                scores[v["id"]] = v["score"]
    for key, ids in new_cves.items():
        for cid in ids - old_cves.get(key, set()):
            cve_changes.append({"host_key": key[0], "port": key[1],
                                "id": cid, "score": scores.get(cid)})
    for key, ids in old_cves.items():
        gone = ids - new_cves.get(key, set())
        if key in new_cves or key in {
                (_host_key(h), p["port"])
                for h in new["hosts"] for p in h["ports"]}:
            # The port itself was re-scanned and the CVE is gone:
            # that's a fix (or a version change). 
            fixed += len(gone)
        else:
            # The port wasn't re-detected at all — nmap variance
            # on a busy LAN says nothing about patching. Counted
            # separately, never as 'fixed'.
            unseen += len(gone)
    cve_changes.sort(key=lambda c: c["score"] or 0, reverse=True)

    return {"new_hosts": new_host_list, "gone_hosts": gone_list,
            "new_ports": port_changes, "new_cves": cve_changes,
            "fixed_cves": fixed, "unseen_cves": unseen,
            "counts": {"new_hosts": len(new_host_list),
                       "gone_hosts": len(gone_list),
                       "new_ports": len(port_changes),
                       "new_cves": len(cve_changes),
                       "fixed_cves": fixed,
                       "unseen_cves": unseen}}


def _report_files() -> list[Path]:
    return sorted(audit.AUDIT_DIR.glob("audit-*.json"))


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def latest_state() -> dict | None:
    try:
        return json.loads(STATE_PATH.read_text())
    except (OSError, ValueError):
        return None


def run_once(cfg: dict, progress=lambda msg: None) -> dict:
    """Audit, diff against the previous report, persist both."""
    files = _report_files()
    baseline_path = files[-1] if files else None
    baseline = _load(baseline_path) if baseline_path else None

    stats = audit.run_audit(cfg, progress=progress)
    new_report = _load(audit.AUDIT_DIR / stats["file"])
    stamp = time.strftime("%Y%m%d-%H%M%S")

    if baseline is None or new_report is None:
        diff = None
        summary = {"baseline": True, "counts": None,
                   "note": "first watchdog run — baseline set"}
    else:
        diff = diff_reports(baseline, new_report)
        summary = {"baseline": False, "counts": diff["counts"],
                   "new_hosts": diff["new_hosts"],
                   "new_cves": diff["new_cves"][:10],
                   "note": ""}
        audit.AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        (audit.AUDIT_DIR / f"diff-{stamp}.json").write_text(
            json.dumps({"from": baseline_path.name,
                        "to": stats["file"], **diff}, indent=1) + "\n")
    state = {"last_run": time.strftime("%Y-%m-%d %H:%M"),
             "report": stats["file"], **summary}
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=1) + "\n")
    return {**stats, "watchdog": summary}


def main() -> int:
    from . import config

    result = run_once(config.load(),
                      progress=lambda m: print(m, flush=True))
    print(json.dumps(result["watchdog"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
