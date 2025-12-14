from __future__ import annotations

from typing import Callable
from urllib.parse import urlparse

import requests


def enum_subdomains_wayback(domain: str, log: Callable[[str], None], on_found: Callable[[str], None] | None = None) -> set[str]:
    """
    Enumerate hostnames via Wayback Machine CDX API.
    Extract hosts from archived URLs matching *.domain.
    """
    found: set[str] = set()
    log("[Subdomains] Wayback Machine enumeration...")
    try:
        cdx_url = (
            "http://web.archive.org/cdx/search/cdx"
            f"?url=*.{domain}&output=json&fl=original&collapse=urlkey"
        )
        resp = requests.get(cdx_url, timeout=25)
        if resp.status_code != 200:
            log(f"[Subdomains] Wayback: HTTP {resp.status_code}")
            return set()

        try:
            data = resp.json()
        except Exception:
            log("[Subdomains] Wayback: failed to parse JSON")
            return set()

        for row in data[1:]:
            if not row:
                continue
            url = row[0]
            parsed = urlparse(url if "://" in url else "http://" + url)
            host = parsed.hostname
            if host and host.lower().endswith(domain.lower()):
                h = host.lower()
                if h not in found:
                    found.add(h)
                    if on_found:
                        on_found(h)
        log(f"[Subdomains] Wayback found: {len(found)}")
    except Exception as e:
        log(f"[Subdomains] Wayback error: {e}")
    return found
