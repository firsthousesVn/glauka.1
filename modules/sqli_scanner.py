from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List

from glauka.core.models import ReconContext

REPORT_PATH = Path("reports") / "active_findings.json"


class SqlInjectionModule:
    """
    Aggressive SQLi verification via nuclei. Runs a single high-performance batch,
    streams matches into ctx.findings, and writes JSONL findings for the GUI.
    """

    name = "sqli_scanner"
    depends_on: list[str] = ["web_services"]

    def __init__(self, enabled: bool = True, timeout: int = 1500) -> None:
        self.enabled = enabled
        self.timeout = timeout

    async def run(self, ctx: ReconContext) -> None:
        if not self.enabled:
            return

        targets = self._collect_targets(ctx)
        if not targets:
            ctx.log("[SQLi] No URLs to test.")
            return

        nuclei_bin = shutil.which("nuclei")
        if nuclei_bin is None:
            ctx.log("[SQLi] Nuclei not installed; skipping.")
            return

        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        if REPORT_PATH.exists():
            REPORT_PATH.unlink(missing_ok=True)

        ctx.log(
            f"[Module] sqli_scanner starting aggressive batch ({len(targets)} URLs)..."
        )

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
            tmp.write("\n".join(targets))
            target_file = Path(tmp.name)

        try:
            await asyncio.to_thread(
                self._run_batch_scan, nuclei_bin, target_file, REPORT_PATH, ctx
            )
        finally:
            if target_file.exists():
                target_file.unlink()

        if not REPORT_PATH.exists():
            REPORT_PATH.write_text("", encoding="utf-8")

        ctx.log("[Module] sqli_scanner complete")

    def _collect_targets(self, ctx: ReconContext) -> list[str]:
        urls = list(ctx.nuclei_urls or [])
        for host, ports in (ctx.web_ports or {}).items():
            for port in ports:
                scheme = "https" if port in (443, 8443) else "http"
                if port in (80, 443):
                    urls.append(f"{scheme}://{host}")
                else:
                    urls.append(f"{scheme}://{host}:{port}")
        deduped = []
        seen = set()
        for url in urls:
            normalized = url.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)
        return deduped

    def _detect_templates(self, ctx: ReconContext) -> list[Path]:
        candidates = [
            Path.home() / "nuclei-templates",
            Path.home() / ".local" / "share" / "nuclei-templates",
        ]
        found: list[Path] = []
        for path in candidates:
            if path.is_dir():
                found.append(path)
        if found:
            ctx.log(f"[SQLi] Using nuclei templates at {found[0]}")
        return found

    def _build_command(
        self, nuclei_bin: str, targets: Path, report: Path, templates: list[Path]
    ) -> list[str]:
        cmd = [
            nuclei_bin,
            "-l",
            str(targets),
            "-jsonl",
            "-o",
            str(report),
            "-severity",
            "medium,high,critical",
            "-tags",
            "sqli,sql-injection,database",
            "-dast",
            "-bulk-size",
            "50",
            "-timeout",
            "8",
            "-retries",
            "1",
            "-stats",
        ]
        for base in templates:
            cve_dir = base / "cves"
            if cve_dir.is_dir():
                cmd.extend(["-t", str(cve_dir)])
            else:
                cmd.extend(["-t", str(base)])
        return cmd

    def _run_batch_scan(
        self, nuclei_bin: str, targets: Path, report: Path, ctx: ReconContext
    ) -> None:
        cmd = self._build_command(
            nuclei_bin,
            targets,
            report,
            self._detect_templates(ctx),
        )
        ctx.log(f"[SQLi] Executing nuclei: {' '.join(cmd)}")

        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as exc:
            ctx.log(f"[SQLi] Failed to start nuclei: {exc}")
            return

        assert process.stdout is not None
        try:
            for line in process.stdout:
                clean = line.strip()
                if not clean:
                    continue
                self._process_finding(clean, ctx)
            process.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            ctx.log("[SQLi] Scan timed out; terminating nuclei.")
            process.kill()
        except Exception as exc:  # pragma: no cover - defensive
            ctx.log(f"[SQLi] Execution failed: {exc}")
        finally:
            if process and process.poll() is None:
                process.kill()

    def _process_finding(self, line: str, ctx: ReconContext) -> None:
        entry = self._parse_json_line(line)
        if not entry:
            return

        info = entry.get("info", {}) or {}
        severity = str(info.get("severity") or entry.get("severity") or "UNKNOWN").upper()
        url = entry.get("matched-at") or entry.get("host") or entry.get("url") or ""
        name = info.get("name") or entry.get("template-id") or "SQL Injection"

        if not url:
            ctx.log(f"[SQLi] Ignored malformed finding (missing target): {name}")
            return

        msg = f"[SQLi] {severity}: {name} @ {url}"
        if msg not in ctx.findings:
            ctx.findings.append(msg)
            ctx.emit("sqli", msg)
            if ctx.verbose_logs:
                ctx.log(msg)

    def _parse_json_line(self, line: str) -> dict | None:
        try:
            return json.loads(line)
        except Exception:
            return None


def load_findings_for_gui(file_path: str) -> List[Dict[str, str]]:
    """
    Safe loader for the HUD/GUI. Returns a list of dicts with keys:
    severity, url, name. Handles partially-written JSONL gracefully.
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return []

    try:
        raw_lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []

    parsed: List[Dict[str, str]] = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue

        info = entry.get("info", {}) or {}
        severity = str(info.get("severity") or entry.get("severity") or "UNKNOWN").upper()
        url = entry.get("matched-at") or entry.get("host") or entry.get("url") or ""
        name = info.get("name") or entry.get("template-id") or "SQL Injection"

        if not url:
            continue

        parsed.append({"severity": severity, "url": url, "name": name})

    return parsed
