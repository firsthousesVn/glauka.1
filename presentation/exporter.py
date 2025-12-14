from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional

import requests

from glauka.core.models import ReconResult


def export_json(result: ReconResult, path: str | Path) -> Path:
    out_path = Path(path)
    data = _as_dict(result)
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out_path


def export_csv(result: ReconResult, path: str | Path) -> Path:
    out_path = Path(path)
    rows: List[Dict[str, str]] = []
    for sub in result.subdomains:
        rows.append({"type": "subdomain", "value": sub})
    for host, ports in result.web_ports.items():
        rows.append({"type": "web_host", "value": host, "ports": ",".join(str(p) for p in ports)})
    for port, service in result.base_ports.items():
        rows.append({"type": "base_port", "value": f"{port}", "service": service})
    for finding in result.findings:
        rows.append({"type": "finding", "value": finding})

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["type", "value", "ports", "service"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return out_path


def export_markdown(result: ReconResult, path: str | Path) -> Path:
    out_path = Path(path)
    lines = [
        f"# Recon Report: {result.scope.host or result.scope.ip}",
        "",
        "## Scope",
        f"- Host: {result.scope.host or 'N/A'}",
        f"- IP: {result.scope.ip or 'N/A'}",
        f"- URL: {result.scope.url or 'N/A'}",
        f"- Mode: {result.scope.mode}",
        "",
        "## Subdomains",
    ]
    lines += [f"- {s}" for s in result.subdomains] or ["- None"]
    lines += [
        "",
        "## Base Ports",
    ]
    lines += [f"- {port}: {service}" for port, service in result.base_ports.items()] or ["- None"]
    lines += [
        "",
        "## Web Hosts",
    ]
    lines += [f"- {host}: {', '.join(str(p) for p in ports)}" for host, ports in result.web_ports.items()] or ["- None"]
    lines += [
        "",
        "## Findings",
    ]
    lines += [f"- {f}" for f in result.findings] or ["- None"]
    lines += [
        "",
        "## Nuclei Output",
        "```",
        result.nuclei_raw or "No vulnerability data.",
        "```",
    ]
    if result.timings:
        lines += ["", "## Timings"]
        for name, duration in result.timings.items():
            lines.append(f"- {name}: {duration:.2f}s")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def export_html(result: ReconResult, path: str | Path) -> Path:
    out_path = Path(path)
    rows_ports = "".join(
        f"<li>{host}: {', '.join(str(p) for p in ports)}</li>" for host, ports in result.web_ports.items()
    ) or "<li>None</li>"
    rows_subs = "".join(f"<li>{sub}</li>" for sub in result.subdomains) or "<li>None</li>"
    rows_findings = "".join(f"<li>{finding}</li>" for finding in result.findings) or "<li>None</li>"
    timings = "".join(f"<li>{k}: {v:.2f}s</li>" for k, v in result.timings.items()) or "<li>N/A</li>"
    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>Glauka Recon Report</title>
<style>
body {{ font-family: Arial, sans-serif; background:#0f111a; color:#e8e8f0; padding:24px; }}
h1, h2 {{ color:#ffbf00; }}
section {{ margin-bottom:18px; padding:12px 14px; background:#161927; border-radius:8px; border:1px solid #232842; }}
code, pre {{ background:#10131f; color:#d9dcee; padding:8px; display:block; border-radius:6px; white-space:pre-wrap; }}
</style>
</head>
<body>
<h1>Recon Report: {result.scope.host or result.scope.ip or 'Unknown target'}</h1>
<section>
  <h2>Scope</h2>
  <ul>
    <li>Host: {result.scope.host or 'N/A'}</li>
    <li>IP: {result.scope.ip or 'N/A'}</li>
    <li>URL: {result.scope.url or 'N/A'}</li>
    <li>Mode: {result.scope.mode}</li>
  </ul>
</section>
<section>
  <h2>Subdomains</h2>
  <ul>{rows_subs}</ul>
</section>
<section>
  <h2>Web Hosts</h2>
  <ul>{rows_ports}</ul>
</section>
<section>
  <h2>Findings</h2>
  <ul>{rows_findings}</ul>
</section>
<section>
  <h2>Nuclei Output</h2>
  <pre>{(result.nuclei_raw or 'No vulnerability data.').replace('<','&lt;').replace('>','&gt;')}</pre>
</section>
<section>
  <h2>Timings</h2>
  <ul>{timings}</ul>
</section>
</body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")
    return out_path


def render_cli_summary(result: ReconResult, target_input: str) -> str:
    lines = [
        f"Target       : {result.scope.host or target_input}",
        f"IP Address   : {result.scope.ip or 'N/A'}",
        f"Mode         : {result.scope.mode}",
        f"Subdomains   : {len(result.subdomains)}",
        f"Web Hosts    : {len(result.web_ports)}",
        f"Findings     : {len(result.findings)}",
    ]
    if result.timings:
        total = result.timings.get("total")
        if total is not None:
            lines.append(f"Total Time   : {total:.2f}s")
    if result.findings:
        lines.append("Key Findings :")
        for finding in result.findings[:5]:
            lines.append(f"  - {finding}")
    return "\n".join(lines)


def export_webhook(result: ReconResult, url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 10.0) -> None:
    headers = headers or {"Content-Type": "application/json"}
    payload = _as_dict(result)
    requests.post(url, headers=headers, json=payload, timeout=timeout)


def _as_dict(result: ReconResult) -> Dict[str, object]:
    return {
        "scope": {
            "host": result.scope.host,
            "ip": result.scope.ip,
            "url": result.scope.url,
            "mode": result.scope.mode,
        },
        "subdomains": result.subdomains,
        "base_ports": result.base_ports,
        "web_ports": result.web_ports,
        "nuclei_raw": result.nuclei_raw,
        "nuclei_urls": result.nuclei_urls,
        "findings": result.findings,
        "screenshots": result.screenshots,
        "extra": result.extra,
        "timings": result.timings,
    }
