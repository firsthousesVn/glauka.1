from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional


def _find_amass_binary() -> Optional[str]:
    """
    Prefer a real OWASP Amass binary (e.g., from GOPATH) over any python 'amass' shim in venv.
    """
    candidates = [
        Path.home() / "go" / "bin" / "amass.exe",
        Path.home() / "go" / "bin" / "amass",
    ]
    for cand in candidates:
        if cand.exists():
            return str(cand)
    return shutil.which("amass")


def _detect_amass_version(log: Callable[[str], None]) -> tuple[int | None, str]:
    """
    Attempt to detect the installed Amass version. Returns (major_version, raw_output).
    """
    amass_bin = _find_amass_binary()
    if amass_bin is None:
        log("[Amass] Not installed, skipping.")
        return None, ""
    try:
        proc = subprocess.run(
            [amass_bin, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        raw = (proc.stdout or proc.stderr or "").strip()
        if raw:
            log(f"[Amass] Detected version: {raw}")
        if "Usage: amass [OPTIONS] COMMAND [ARGS]" in raw:
            log("[Amass] Detected non-OWASP CLI shim; will try to upgrade/replace.")
            return None, raw
        match = re.search(r"v?(\d+)\.(\d+)\.(\d+)", raw)
        if match:
            major = int(match.group(1))
            return major, raw
        return None, raw
    except Exception as exc:
        log(f"[Amass] Version check failed: {exc}")
        return None, ""


def enum_subdomains_amass(domain: str, mode: str, log: Callable[[str], None], on_found: Callable[[str], None] | None = None) -> set[str]:
    """
    Robust Amass wrapper.
    Attempts modern 'enum' command first. If that fails, tries legacy syntax.
    If active/brute flags are rejected, falls back to a minimal passive scan.
    """
    amass_bin = _find_amass_binary()
    if amass_bin is None:
        log("[Amass] Not installed, skipping.")
        return set()

    major_version, _ = _detect_amass_version(log)
    legacy_amass = major_version is not None and major_version < 4
    if legacy_amass:
        log(
            "[Amass] Legacy Amass detected (<v4); attempting upgrade via "
            "`go install github.com/owasp-amass/amass/v4/...@latest`"
        )
        try:
            upgrade = subprocess.run(
                ["go", "install", "github.com/owasp-amass/amass/v4/...@latest"],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if upgrade.returncode != 0:
                log(f"[Amass] Auto-upgrade failed: {upgrade.stderr.strip() or upgrade.stdout.strip()}")
                log("[Amass] Falling back to passive mode with current binary.")
            else:
                log("[Amass] Upgrade successful; re-checking version.")
                major_version, _ = _detect_amass_version(log)
                legacy_amass = major_version is not None and major_version < 4
        except Exception as exc:
            log(f"[Amass] Auto-upgrade error: {exc}")
            log("[Amass] Continuing with existing binary in passive mode.")

    base_flags = ["-nocolor", "-d", domain]
    # Prefer passive unless confirmed v4+ and requested active
    if legacy_amass or mode == "passive":
        flags = ["-passive", *base_flags]
    elif mode == "active":
        flags = ["-active", "-brute", *base_flags]
    else:
        flags = ["-brute", *base_flags]

    subs: set[str] = set()

    def _handle_line(raw_line: str) -> None:
        line = raw_line.strip()
        if "[" in line and "m" in line:
            parts = line.split()
            if parts:
                line = parts[-1]
        if line and line.endswith(domain) and "." in line:
            host = line.lower()
            if host not in subs:
                subs.add(host)
                if on_found:
                    on_found(host)

    def _run(cmd: list[str], timeout: int = 420) -> tuple[int, str]:
        log("[Amass] Running: " + " ".join(cmd))
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout_buf: list[str] = []
        start = time.monotonic()
        try:
            while True:
                if proc.stdout is None:
                    break
                line = proc.stdout.readline()
                if line:
                    stdout_buf.append(line)
                    _handle_line(line)
                elif proc.poll() is not None:
                    break
                if time.monotonic() - start > timeout:
                    log("[Amass] Timed out, killing process.")
                    proc.kill()
                    return -1, "timeout"
                time.sleep(0.05)
            stderr = ""
            if proc.stderr:
                stderr = proc.stderr.read() or ""
            return proc.returncode, stderr
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            return -1, "error"

    try:
        # Preferred (newer Amass): `amass enum ...`
        rc, stderr = _run([amass_bin, "enum", *flags])

        # Legacy fallback (older Amass without 'enum')
        if rc != 0 and ("No such command" in stderr or "flag provided but not defined" in stderr):
            log("[Amass] 'enum' command failed; retrying legacy syntax.")
            rc, stderr = _run([amass_bin, *flags])

        # Safe-mode fallback: drop active/brute flags if they are rejected
        if rc != 0 and ("No such option" in stderr or "flag" in stderr):
            log("[Amass] Active/Brute flags rejected; forcing SAFE passive scan.")
            rc, stderr = _run([amass_bin, "-d", domain], timeout=120)
            if "No such option: -d" in stderr:
                log(
                    "[Amass] Installed binary appears too old for enum/-d. "
                    "Upgrade via `go install github.com/owasp-amass/amass/v4/...@latest`."
                )

        if stderr and rc != 0:
            last_err = stderr.strip().splitlines()[-1] if stderr.strip() else "Unknown error"
            log(f"[Amass] Final attempt failed: {last_err}")
            if not legacy_amass and "enum" in last_err.lower() and "command" in last_err.lower():
                log(
                    "[Amass] The installed version may lack modern enum support. "
                    "Try upgrading with `go install github.com/owasp-amass/amass/v4/...@latest`."
                )
            if legacy_amass and "flag" in last_err.lower():
                log(
                    "[Amass] Legacy flags rejected; please upgrade: "
                    "`go install github.com/owasp-amass/amass/v4/...@latest`."
                )

        log(f"[Amass] Found: {len(subs)}")
        return subs
    except Exception as e:
        log(f"[Amass] Error: {e}")
        return set()
