from __future__ import annotations

import json
import time
from typing import Callable

import requests


def enum_subdomains_ct(domain: str, log: Callable[[str], None], on_found: Callable[[str], None] | None = None) -> set[str]:
    """Enumerate subdomains via Certificate Transparency logs (crt.sh)."""
    found: set[str] = set()
    log("[Subdomains] CT log enumeration via crt.sh...")
    url = f"https://crt.sh/?q=%25.{domain}&output=json"

    def _fetch_with_backoff(max_attempts: int = 4) -> requests.Response | None:
        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.get(url, timeout=20)
            except Exception as exc:
                log(f"[Subdomains] CT request error: {exc}")
                return None

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else min(30, 2 ** attempt)
                log(f"[Subdomains] CT rate limited (429); backing off {delay:.1f}s (attempt {attempt}/{max_attempts}).")
                time.sleep(delay)
                continue

            if resp.status_code >= 500:
                log(f"[Subdomains] CT server error HTTP {resp.status_code} (attempt {attempt}/{max_attempts}).")
                time.sleep(min(10, 2 ** attempt))
                continue

            return resp
        log("[Subdomains] CT logs: exhausted retries.")
        return None

    try:
        resp = _fetch_with_backoff()
        if not resp:
            return set()
        if resp.status_code != 200:
            log(f"[Subdomains] CT logs: HTTP {resp.status_code}")
            return set()

        try:
            data = resp.json()
        except Exception:
            try:
                data = json.loads(resp.text.replace("\n", ""))
            except Exception:
                log("[Subdomains] Failed to parse CT JSON")
                return set()

        for entry in data:
            name_val = str(entry.get("name_value", "")).lower()
            for line in name_val.split("\n"):
                line = line.strip()
                if line.endswith(domain.lower()):
                    if line not in found:
                        found.add(line)
                        if on_found:
                            on_found(line)
        log(f"[Subdomains] CT logs found: {len(found)}")
    except Exception as e:
        log(f"[Subdomains] CT error: {e}")
    return found
