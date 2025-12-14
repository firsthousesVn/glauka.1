from __future__ import annotations

import shutil
import subprocess
import time
from typing import Callable


def enum_subdomains_subfinder(domain: str, log: Callable[[str], None], on_found: Callable[[str], None] | None = None) -> set[str]:
    """
    Enumerate subdomains using Subfinder, if installed.

    Requires the `subfinder` binary available in PATH.
    """
    if shutil.which("subfinder") is None:
        log("[Subfinder] Not installed, skipping.")
        return set()

    cmd = ["subfinder", "-d", domain, "-silent"]
    log("[Subfinder] Running: " + " ".join(cmd))
    subs: set[str] = set()
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        start = time.monotonic()
        while True:
            if proc.stdout is None:
                break
            line = proc.stdout.readline()
            if line:
                line = line.strip()
                if line and line.endswith(domain):
                    host = line.lower()
                    if host not in subs:
                        subs.add(host)
                        if on_found:
                            on_found(host)
            elif proc.poll() is not None:
                break
            if time.monotonic() - start > 240:
                log("[Subfinder] Timed out, killing process.")
                proc.kill()
                break
        if proc.stderr:
            stderr = proc.stderr.read().strip()
            if stderr:
                last_err = stderr.splitlines()[-1]
                log(f"[Subfinder] stderr: {last_err}")
        log(f"[Subfinder] Found: {len(subs)}")
        return subs
    except Exception as e:
        log(f"[Subfinder] Error: {e}")
        try:
            proc.kill()
        except Exception:
            pass
        return subs
