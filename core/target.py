from __future__ import annotations

import socket
from typing import Callable, Optional, Tuple
from urllib.parse import urlparse

from .models import ScopeInfo


def _noop_log(_: str) -> None:
    return


def is_ip(value: str) -> bool:
    try:
        socket.inet_aton(value)
        return True
    except OSError:
        return False


def normalize_target(target: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Normalize input into: (domain_or_host, ip_address, url)

    - If it's already a URL, return parsed host and URL.
    - If it's an IP, return ip+None URL.
    - If it's a bare domain, attempt to resolve IP and build http:// URL.
    """
    target = (target or "").strip()

    parsed = urlparse(target)
    if parsed.scheme and parsed.netloc:
        host = parsed.hostname
        if host is None:
            return None, None, target
        if is_ip(host):
            return host, host, target
        ip = None
        try:
            ip = socket.gethostbyname(host)
        except OSError:
            ip = None
        return host, ip, target

    if is_ip(target):
        return target, target, f"http://{target}"

    domain = target
    ip = None
    try:
        ip = socket.gethostbyname(domain)
    except OSError:
        ip = None
    return domain, ip, f"http://{domain}"


def build_scope(target: str, mode: str, log: Optional[Callable[[str], None]] = None) -> ScopeInfo:
    log = log or _noop_log
    domain_or_host, ip_address, url = normalize_target(target)
    log(f"[Scope] Target: {target} | Mode: {mode.upper()}")
    return ScopeInfo(
        host=domain_or_host or "",
        ip=ip_address or "",
        url=url or "",
        mode=(mode or "passive").lower().strip() or "passive",
    )
