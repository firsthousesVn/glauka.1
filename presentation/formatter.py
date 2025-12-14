from __future__ import annotations

from typing import Dict

from glauka.core.models import ReconResult, ScopeInfo
from glauka.core.nuclei import summarize_nuclei_output


def _fmt_scope_line(key: str, value: str) -> str:
    return f"{key:<15}: {value or 'N/A'}"


def format_scope(scope: ScopeInfo, target_input: str) -> str:
    lines = [
        _fmt_scope_line("Target Input", target_input),
        _fmt_scope_line("Recon Mode", scope.mode.upper()),
        "",
        _fmt_scope_line("Normalized Host", scope.host),
        _fmt_scope_line("IP Address", scope.ip),
        _fmt_scope_line("URL", scope.url),
    ]
    return "\n".join(lines)


def format_subdomains(result: ReconResult) -> str:
    if result.subdomains:
        return "\n".join(result.subdomains)
    return "No subdomains discovered."


def format_ports(result: ReconResult) -> str:
    lines = []

    if result.base_ports and result.scope.ip:
        lines.append(f"Base IP: {result.scope.ip}")
        for port in sorted(result.base_ports):
            service = result.base_ports[port]
            lines.append(f"  {result.scope.ip}:{port} ({service})")
        lines.append("")
    elif result.scope.ip:
        lines.append(f"No common ports open on {result.scope.ip}.")
        lines.append("")

    if result.web_ports:
        lines.append("Per-Host Web Ports:")
        for host, ports in sorted(result.web_ports.items()):
            port_str = ", ".join(str(p) for p in ports)
            lines.append(f"  {host} : {port_str}")
    else:
        lines.append("No web-exposed hosts discovered on common ports.")

    return "\n".join(lines)


def format_findings(result: ReconResult, target_input: str) -> str:
    lines = []
    lines.append("SUMMARY")
    lines.append("------")
    lines.append(f"Target       : {result.scope.host or target_input}")
    lines.append(f"IP Address   : {result.scope.ip or 'N/A'}")
    lines.append(f"Subdomains   : {len(result.subdomains)} discovered")
    lines.append(f"Web Hosts    : {len(result.web_ports)} with HTTP/HTTPS exposure")
    lines.append("")
    lines.append("Highlights:")
    if result.subdomains:
        lines.append("  - Subdomain enumeration identified additional attack surface.")
    if result.scope.ip and (result.base_ports or result.web_ports):
        lines.append("  - Open ports detected; investigate exposed services.")
    if not (result.subdomains or result.scope.ip):
        lines.append("  - Limited signal: unable to resolve IP or subdomains.")
    lines.append("")
    lines.append("(Nuclei summary will be appended after scan.)")
    lines.append("")
    lines.append(summarize_nuclei_output(result.nuclei_raw))
    lines.append("")
    return "\n".join(lines)


def format_vulns(result: ReconResult) -> str:
    return result.nuclei_raw or "No vulnerability data."


def format_bug_paths() -> str:
    bug_paths = [
        "SUGGESTED BUG PATHS",
        "--------------------",
        "1. Subdomains & DNS",
        "   - Review all discovered subdomains for staging/admin panels.",
        "   - Check for legacy or forgotten hosts (old apps, beta, dev).",
        "",
        "2. Network & Services",
        "   - For each open port, identify the service and version.",
        "   - Look for weak services (FTP, outdated SSH, exposed DBs).",
        "",
        "3. Web Apps & Nuclei Findings",
        "   - Prioritize HIGH/CRITICAL Nuclei findings.",
        "   - Validate Nuclei results manually before reporting.",
        "",
        "4. Deeper Enumeration",
        "   - Run a full nmap scan for deeper port/service coverage.",
        "   - Expand wordlists and re-run hybrid/active subdomain discovery.",
    ]
    return "\n".join(bug_paths)


def format_all_panels(result: ReconResult, target_input: str) -> Dict[str, str]:
    bug_paths_text = format_bug_paths()
    formatted = {
        "scope": format_scope(result.scope, target_input),
        "signal": format_findings(result, target_input),
        "subdomains": format_subdomains(result),
        "ports": format_ports(result),
        "vulns": f"{format_vulns(result)}\n\n{bug_paths_text}",
        "bug_paths": bug_paths_text,
    }
    return formatted
