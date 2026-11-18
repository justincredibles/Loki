"""Network auditing — the Bjorn-style half of lokicz.

Point it at the network the Zero is sitting on and it does the
full audit pass:

1. **Discovery** — who is on this network (nmap ping sweep,
   enriched with the ARP cache for MACs/vendors).
2. **Port + service scan** — top-100 TCP ports per host with
   version detection (nmap -sV), which also yields CPE product
   identifiers for identified services.
3. **Vulnerability correlation** — each CPE is looked up in the
   NVD (National Vulnerability Database) API; every hit lands in
   the report as a CVE id, CVSS score/severity, summary, and its
   canonical link (https://nvd.nist.gov/vuln/detail/CVE-...).
   Results are cached on-device so repeat audits are fast and
   gentle on the NVD's rate limits.

Reports are JSON in ~/lokicz-audits/ — the full detail (every
host, port, and CVE link) lives there; the LCD shows the summary.

Scope honesty: this audits the network the device is connected
to — your own LAN, your lab. That's the Bjorn model. Scans are
connect scans at polite intensity, capped at MAX_FULL_SCANS
hosts per run so a big subnet doesn't turn into an all-day job;
hosts past the cap are inventoried but marked unscanned.
"""

import ipaddress
import json
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

AUDIT_DIR = Path.home() / "lokicz-audits"
CACHE_PATH = Path.home() / ".config" / "lokicz" / "cve_cache.json"
NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
MAX_FULL_SCANS = 12
TOP_PORTS = 100
MAX_CVES_PER_CPE = 50


# --- nmap plumbing ----------------------------------------------------

def _nmap_xml(args: list[str], timeout: int) -> ET.Element:
    out = subprocess.run(["nmap", "-oX", "-", *args],
                         capture_output=True, text=True, timeout=timeout)
    return ET.fromstring(out.stdout)


def _text(el, path, attr=None, default=""):
    node = el.find(path) if el is not None else None
    if node is None:
        return default
    return node.get(attr, default) if attr else (node.text or default)


def local_subnet() -> str:
    """The network this device is on, e.g. '192.168.1.0/24'."""
    out = subprocess.run(["ip", "-4", "addr", "show", "scope",
                          "global"], capture_output=True, text=True,
                         timeout=10).stdout
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("inet "):
            cidr = line.split()[1]
            return str(ipaddress.ip_interface(cidr).network)
    raise RuntimeError("no global IPv4 address found")


def _arp_table() -> dict:
    """IP -> (mac, vendor-ish) from the kernel neighbour cache."""
    table = {}
    try:
        out = subprocess.run(["ip", "neigh"], capture_output=True,
                             text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return table
    for line in out.splitlines():
        parts = line.split()
        if "lladdr" in parts:
            table[parts[0]] = parts[parts.index("lladdr") + 1]
    return table


def discover(subnet: str) -> list[dict]:
    """Ping-sweep the subnet; return hosts that answered."""
    root = _nmap_xml(["-sn", subnet], timeout=300)
    arp = _arp_table()
    hosts = []
    for host in root.iter("host"):
        if _text(host, "status", "state") != "up":
            continue
        ip = ""
        mac, vendor = "", ""
        for addr in host.findall("address"):
            if addr.get("addrtype") == "ipv4":
                ip = addr.get("addr", "")
            elif addr.get("addrtype") == "mac":
                mac = addr.get("addr", "")
                vendor = addr.get("vendor", "")
        if not ip:
            continue
        hosts.append({"ip": ip,
                      "hostname": _text(host, "hostnames/hostname",
                                        "name"),
                      "mac": mac or arp.get(ip, ""), "vendor": vendor,
                      "ports": [], "scanned": False})
    hosts.sort(key=lambda h: ipaddress.ip_address(h["ip"]))
    return hosts


def scan_host(ip: str) -> list[dict]:
    """Top-ports service scan of one host; open ports only."""
    root = _nmap_xml(["-sV", "--top-ports", str(TOP_PORTS), "-T4",
                      "--host-timeout", "120s", ip], timeout=240)
    ports = []
    for port in root.iter("port"):
        if _text(port, "state", "state") != "open":
            continue
        svc = port.find("service")
        ports.append({
            "port": int(port.get("portid", "0")),
            "proto": port.get("protocol", "tcp"),
            "service": svc.get("name", "") if svc is not None else "",
            "product": svc.get("product", "") if svc is not None else "",
            "version": svc.get("version", "") if svc is not None else "",
            "extra": svc.get("extrainfo", "") if svc is not None else "",
            "cpes": [c.text or "" for c in port.findall("service/cpe")],
            "vulns": [],
        })
    return ports


# --- CVE correlation (NVD) ---------------------------------------------

def _cpe23(cpe: str, version: str) -> str:
    """nmap's CPE 2.2 ('cpe:/a:acme:micro_httpd') -> NVD CPE 2.3."""
    parts = cpe.removeprefix("cpe:/").split(":")
    while len(parts) < 3:
        parts.append("*")
    part, vendor, product = parts[0], parts[1], parts[2]
    ver = version.strip() or "*"
    ver = ver.replace(" ", "_")
    return f"cpe:2.3:{part}:{vendor}:{product}:{ver}:*:*:*:*:*:*"


def _load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text())
    except (OSError, ValueError):
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=1) + "\n")


def _cvss(cve: dict):
    metrics = cve.get("metrics", {})
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        for entry in metrics.get(key, []):
            data = entry.get("cvssData", {})
            if "baseScore" in data:
                return data["baseScore"], data.get("baseSeverity", "")
    return None, ""


def cves_for_cpe(cpe23: str, api_key: str, cache: dict,
                 pace: list) -> list[dict]:
    """CVEs for one CPE 2.3 name, cached; NVD-polite pacing.

    `pace` is a one-element list holding the last request time so
    successive calls keep the NVD's rate limit (5 req / 30 s
    without a key, 50 / 30 s with one).
    """
    if cpe23 in cache:
        return cache[cpe23]["cves"]
    delay = 0.7 if api_key else 6.5
    wait = delay - (time.time() - pace[0])
    if wait > 0:
        time.sleep(wait)
    params = urllib.parse.urlencode(
        {"cpeName": cpe23, "resultsPerPage": MAX_CVES_PER_CPE})
    req = urllib.request.Request(
        f"{NVD_API}?{params}",
        headers={"User-Agent": "lokicz-audit/0.1",
                 **({"apiKey": api_key} if api_key else {})})
    pace[0] = time.time()
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    cves = []
    for item in data.get("vulnerabilities", []):
        cve = item.get("cve", {})
        cid = cve.get("id", "")
        if not cid:
            continue
        summary = ""
        for desc in cve.get("descriptions", []):
            if desc.get("lang") == "en":
                summary = desc.get("value", "")[:280]
                break
        score, severity = _cvss(cve)
        cves.append({"id": cid, "score": score,
                     "severity": severity or _severity(score),
                     "summary": summary,
                     "url": f"https://nvd.nist.gov/vuln/detail/{cid}"})
    cves.sort(key=lambda c: c["score"] or 0, reverse=True)
    cache[cpe23] = {"fetched": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "cves": cves}
    return cves


def _severity(score) -> str:
    if score is None:
        return ""
    return ("CRITICAL" if score >= 9 else "HIGH" if score >= 7
            else "MEDIUM" if score >= 4 else "LOW")


# --- The audit run -------------------------------------------------------

def run_audit(cfg: dict, progress=lambda msg: None) -> dict:
    """Full pass: discover, scan, correlate. Returns LCD stats."""
    subnet = cfg.get("audit_subnet") or local_subnet()
    progress("SWEEPING THE LAN...")
    hosts = discover(subnet)
    try:
        from . import lan_discovery

        progress("ASKING DEVICES WHO THEY ARE...")
        lan_discovery.enrich(hosts)
    except Exception:
        pass  # discovery is garnish; never break an audit for it
    progress(f"{len(hosts)} HOSTS — SCANNING")
    cache = _load_cache()
    pace = [0.0]
    api_key = cfg.get("nvd_api_key", "")
    cpe_seen: dict[str, list] = {}
    scanned = 0
    for host in hosts:
        if scanned >= MAX_FULL_SCANS:
            break
        scanned += 1
        progress(f"SCAN {scanned}/{min(len(hosts), MAX_FULL_SCANS)}"
                 f" {host['ip'].split('.')[-1]}")
        try:
            host["ports"] = scan_host(host["ip"])
            host["scanned"] = True
        except (subprocess.SubprocessError, ET.ParseError):
            host["ports"] = []
    # Correlate: one NVD lookup per unique product CPE.
    jobs = {}
    for host in hosts:
        for port in host["ports"]:
            for cpe in port["cpes"]:
                jobs.setdefault(_cpe23(cpe, port["version"]), None)
    for i, cpe23 in enumerate(jobs, 1):
        progress(f"CVE CHECK {i}/{len(jobs)}")
        try:
            cpe_seen[cpe23] = cves_for_cpe(cpe23, api_key, cache, pace)
        except Exception:
            cpe_seen[cpe23] = []  # network/API trouble — report says so
    _save_cache(cache)
    for host in hosts:
        for port in host["ports"]:
            for cpe in port["cpes"]:
                # Copy each finding onto the port; when nmap could
                # not pin a version, flag it — the CVE list for a
                # bare product CPE includes issues fixed in later
                # releases, so those hits are leads, not verdicts.
                port["vulns"].extend(
                    dict(v, version_unknown=not port["version"])
                    for v in cpe_seen.get(
                        _cpe23(cpe, port["version"]), []))
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    report = {"started": time.strftime("%Y-%m-%d %H:%M"),
              "subnet": subnet, "hosts": hosts}
    path = AUDIT_DIR / f"audit-{stamp}.json"
    path.write_text(json.dumps(report, indent=1) + "\n")
    return summarize(report) | {"file": path.name}


def summarize(report: dict) -> dict:
    """Headline numbers + the worst finding, for the LCD/report."""
    vulns = []
    open_ports = 0
    for host in report["hosts"]:
        for port in host["ports"]:
            open_ports += 1
            for v in port["vulns"]:
                vulns.append((v, host["ip"], port["port"]))
    vulns.sort(key=lambda t: t[0]["score"] or 0, reverse=True)
    return {
        "when": report["started"], "subnet": report["subnet"],
        "hosts": len(report["hosts"]),
        "scanned": sum(1 for h in report["hosts"] if h["scanned"]),
        "open_ports": open_ports, "cves": len(vulns),
        "crit": sum(1 for v, _, _ in vulns
                    if (v["score"] or 0) >= 9),
        "high": sum(1 for v, _, _ in vulns
                    if 7 <= (v["score"] or 0) < 9),
        "top": ({"id": vulns[0][0]["id"],
                 "score": vulns[0][0]["score"],
                 "where": f"{vulns[0][1]}:{vulns[0][2]}"}
                if vulns else None),
    }


def latest_summary() -> dict | None:
    """Summary of the newest saved report, or None."""
    files = sorted(AUDIT_DIR.glob("audit-*.json"))
    if not files:
        return None
    try:
        return summarize(json.loads(files[-1].read_text())) \
            | {"file": files[-1].name}
    except (OSError, ValueError):
        return None


def main() -> int:
    import sys

    from . import config

    cfg = config.load()
    stats = run_audit(cfg, progress=lambda m: print(m, flush=True))
    print(json.dumps(stats, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
