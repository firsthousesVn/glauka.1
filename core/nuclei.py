from __future__ import annotations
import shutil
import subprocess
import time
from pathlib import Path
import tempfile
from typing import Callable, List, Tuple
from urllib.parse import urlparse


def _noop_log(_: str) -> None:
    return


def _detect_nuclei_template_dirs(log: Callable[[str], None]) -> List[str]:
    """
    Attempt to find common nuclei-templates directory locations.
    """
    candidates = [
        Path.home() / "nuclei-templates",
        Path.home() / ".local" / "share" / "nuclei-templates",
        Path.home() / ".nuclei-templates",
    ]
    existing: List[str] = []
    for base in candidates:
        if base.exists() and base.is_dir():
            subdirs = [
                "cves",
                "exposures",
                "misconfiguration",
                "default-logins",
                "panels",
                "technologies",
            ]
            for sub in subdirs:
                path = base / sub
                if path.exists():
                    existing.append(str(path))
            if not existing:
                existing.append(str(base))
            break

    if existing:
        log(f"[Nuclei] Using templates from: {', '.join(existing)}")
    else:
        log("[Nuclei] No template directory auto-detected; using Nuclei defaults.")
    return existing


def _update_nuclei_templates(log: Callable[[str], None]) -> bool:
    """
    Attempt to update/download nuclei templates using the built-in updater.
    """
    log("[Nuclei] Updating templates (nuclei -update-templates)...")
    try:
        proc = subprocess.run(
            ["nuclei", "-update-templates"],
            capture_output=True,
            text=True,
            timeout=240,
            check=False,
        )
        if proc.returncode != 0:
            last_err = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:]
            msg = last_err[0] if last_err else "unknown error"
            log(f"[Nuclei] Template update failed (rc={proc.returncode}): {msg}")
            return False
    except Exception as exc:
        log(f"[Nuclei] Template update failed: {exc}")
        return False

    log("[Nuclei] Templates updated/downloaded.")
    return True


def _prepare_template_dirs(
    user_templates: List[str] | None,
    log: Callable[[str], None],
    auto_update: bool = True,
) -> List[str]:
    """
    Combine user-provided template paths with auto-detected ones.
    If nothing is found and auto_update is True, attempt nuclei -update-templates.
    """
    template_dirs: List[str] = []
    for tpl in user_templates or []:
        path = Path(tpl).expanduser()
        if path.is_dir():
            template_dirs.append(str(path))
        else:
            log(f"[Nuclei] Template path not found: {path}")

    if not template_dirs:
        template_dirs = _detect_nuclei_template_dirs(log)

    if not template_dirs and auto_update:
        if _update_nuclei_templates(log):
            template_dirs = _detect_nuclei_template_dirs(log)

    if not template_dirs:
        log("[Nuclei] Proceeding with Nuclei-managed templates (no local directories found).")

    return template_dirs


def _dynamic_nuclei_limits(urls: List[str]) -> Tuple[str, str, int]:
    """
    Choose concurrency (-c) and rate-limit (-rl) based on target volume.
    Designed to avoid 'concurrency > max-host-error' spam.
    """
    host_set = set()
    for u in urls:
        try:
            host = urlparse(u).hostname
        except Exception:
            host = None
        if host:
            host_set.add(host)

    host_count = len(host_set)

    if host_count <= 5:
        return "15", "15", host_count
    if host_count <= 20:
        return "10", "10", host_count
    if host_count <= 50:
        return "8", "8", host_count
    return "5", "5", host_count


def nuclei_scan(
    urls: List[str],
    log: Callable[[str], None] | None = None,
    severities: str = "low,medium,high,critical",
    tags: str | None = "sqli,xss,lfi,rce,takeover",
    exclude_tags: str | None = "ssl,tls,info,tech",
    disable_exclude_tags: bool = False,
    update_templates: bool = True,
    templates: List[str] | None = None,
    concurrency: int | str | None = None,
    rate_limit: int | str | None = None,
    progress_cb: Callable[[str, str], None] | None = None,
    verbose: bool = False,
) -> str:
    """
    Run Nuclei against a list of URLs.

    - urls: list of full URLs (http/https)
    - severities: severity filter passed directly to nuclei (comma-separated).
    - tags: optional nuclei tag filter for higher-value findings.
    - exclude_tags: tags to omit (set disable_exclude_tags=True to skip -etags).
    - update_templates: attempt to download nuclei-templates if none are found locally.
    - templates: optional list of template directories.
    - concurrency/rate_limit: override auto scaling (-c/-rl).
    """
    log = log or _noop_log
    safe_urls: List[str] = []
    for u in urls:
        cleaned = (u or "").strip().replace("\r", "").replace("\n", "")
        if cleaned:
            safe_urls.append(cleaned)
    if not safe_urls:
        return "No HTTP services discovered for Nuclei scan."

    if shutil.which("nuclei") is None:
        log("[Nuclei] Not installed, skipping scan.")
        return "[!] Nuclei is not installed on this system."

    targets_file: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
            tmp.write("\n".join(sorted(set(safe_urls))))
            targets_file = Path(tmp.name)
    except Exception as exc:
        log(f"[Nuclei] Failed to write targets file: {exc}")
        return "[!] Failed to write nuclei targets file."

    try:
        template_dirs = _prepare_template_dirs(templates or [], log, auto_update=update_templates)
        c_auto, rl_auto, host_count = _dynamic_nuclei_limits(safe_urls)
        c = str(concurrency or c_auto)
        rl = str(rate_limit or rl_auto)
        log(f"[Nuclei] Target hosts: ~{host_count}; using -c {c}, -rl {rl}. Override via config.modules.nuclei.")
        if host_count > 40 and concurrency is None:
            log("[Nuclei] Tip: set modules.nuclei.concurrency/rate_limit to tune speed for large scopes.")

        def _clean_csv(value: str | None) -> str:
            parts = []
            for part in (value or "").split(","):
                p = part.strip()
                if p:
                    parts.append(p)
            return ",".join(parts)

        severity_selected = _clean_csv(severities) or "medium,high,critical"
        tag_filter = _clean_csv(tags)
        etag_filter = _clean_csv(exclude_tags)

        cmd = [
            "nuclei",
            "-l", str(targets_file),
            "-severity", severity_selected,
            "-silent",
            "-nc",
            "-c", c,
            "-rl", rl,
        ]
        if tag_filter:
            cmd.extend(["-tags", tag_filter])
            log(f"[Nuclei] Applying tag focus: {tag_filter} (clear modules.nuclei.tags to broaden).")
        if etag_filter and not disable_exclude_tags:
            cmd.extend(["-etags", etag_filter])
            log(f"[Nuclei] Excluding tags: {etag_filter} (set disable_exclude_tags=true to disable).")
        for tdir in template_dirs:
            cmd.extend(["-t", tdir])

        log("[Nuclei] Running nuclei scan...")

        start = time.monotonic()
        timeout_seconds = 1200

        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
        except Exception as e:
            log(f"[Nuclei] Failed to start: {e}")
            return f"[!] Nuclei failed to start: {e}"

        lines: List[str] = []
        malformed = 0
        try:
            while True:
                if proc.stdout is None:
                    break
                line = proc.stdout.readline()
                if line:
                    line = line.rstrip("\n")
                    lines.append(line)
                    if " @ None" in line or "@ None" in line:
                        malformed += 1
                    if verbose:
                        log(f"[Nuclei] {line}")
                    if progress_cb:
                        try:
                            progress_cb("finding", line)
                        except Exception:
                            pass
                elif proc.poll() is not None:
                    break

                if time.monotonic() - start > timeout_seconds:
                    log("[Nuclei] Global timeout reached; terminating.")
                    proc.kill()
                    return "[!] Nuclei scan timed out."

                time.sleep(0.05)

            try:
                if proc.stderr:
                    stderr = proc.stderr.read().strip()
                    if stderr:
                        last_err = stderr.splitlines()[-1]
                        log(f"[Nuclei] stderr: {last_err}")
            except Exception:
                pass
            rc = proc.poll()
            if rc not in (0, None):
                log(f"[Nuclei] Exited with code {rc}")

        except Exception as e:
            log(f"[Nuclei] Error during scan: {e}")
            try:
                proc.kill()
            except Exception:
                pass
            return f"[!] Nuclei error: {e}"

        if not lines:
            log("[Nuclei] Empty output; filters or template coverage may be too restrictive.")
            return "Nuclei completed. No vulnerabilities reported at selected severities/tags."

        if malformed:
            log(f"[Nuclei] Detected {malformed} malformed result lines (missing target).")

        return "\n".join(lines)
    finally:
        if targets_file:
            try:
                targets_file.unlink(missing_ok=True)
            except Exception:
                pass


def summarize_nuclei_output(text: str) -> str:
    """
    Rough severity summary from nuclei output lines.
    Looks for [info], [low], [medium], [high], [critical].
    """
    if not text:
        return "Nuclei: no output."

    counts = {
        "info": 0,
        "low": 0,
        "medium": 0,
        "high": 0,
        "critical": 0,
    }

    for line in text.splitlines():
        lowered = line.lower()
        for sev in counts.keys():
            token = f"[{sev}]"
            if token in lowered:
                counts[sev] += 1

    total = sum(counts.values())
    if total == 0:
        return "Nuclei: no findings at selected severities."

    parts = [f"{sev.capitalize()}={count}" for sev, count in counts.items() if count > 0]
    return "Nuclei Findings: " + ", ".join(parts)
