from __future__ import annotations

import socket
from typing import Callable

COMMON_SUBDOMAIN_NAMES = [
    "www",
    "api",
    "app",
    "dev",
    "test",
    "stage",
    "staging",
    "beta",
    "admin",
    "portal",
    "internal",
    "intranet",
    "cdn",
    "static",
    "assets",
    "files",
    "mail",
    "smtp",
    "vpn",
    "gateway",
    "auth",
    "login",
    "secure",
]


def enum_subdomains_common(domain: str, log: Callable[[str], None], on_found: Callable[[str], None] | None = None) -> set[str]:
    found: set[str] = set()
    log("[Subdomains] Common-name enumeration...")
    for name in COMMON_SUBDOMAIN_NAMES:
        sub = f"{name}.{domain}"
        try:
            socket.gethostbyname(sub)
            found.add(sub.lower())
            if on_found:
                on_found(sub.lower())
        except OSError:
            continue
    log(f"[Subdomains] Common-name found: {len(found)}")
    return found
