from __future__ import annotations

from typing import Any, Dict


def _update_panel(panel: Any, text: str) -> None:
    if hasattr(panel, "update_vuln_content"):
        panel.update_vuln_content(text)
    else:
        panel.update_content(text)


def apply_formatted_result(gui: Any, formatted: Dict[str, str]) -> None:
    gui.panel_scope.update_content(formatted.get("scope", "[No data]"))
    gui.panel_signal.update_content(formatted.get("signal", "[No data]"))
    gui.panel_subdomains.update_content(formatted.get("subdomains", "[No data]"))
    gui.panel_ports.update_content(formatted.get("ports", "[No data]"))
    _update_panel(gui.panel_vulns, formatted.get("vulns", "[No data]"))

    if hasattr(gui, "panel_bug_paths"):
        gui.panel_bug_paths.update_content(formatted.get("bug_paths", "[No data]"))
