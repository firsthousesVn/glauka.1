from __future__ import annotations

from typing import Callable, List, Set

from .amass import enum_subdomains_amass
from .brute import brute_dns
from .common import enum_subdomains_common
from .ctlogs import enum_subdomains_ct
from .subfinder import enum_subdomains_subfinder
from .wayback import enum_subdomains_wayback

__all__ = [
    "enum_subdomains_common",
    "enum_subdomains_ct",
    "enum_subdomains_wayback",
    "enum_subdomains_subfinder",
    "enum_subdomains_amass",
    "brute_dns",
    "enumerate_all_sources",
]


def _log(log_fn: Callable[[str], None] | None, message: str) -> None:
    if log_fn:
        try:
            log_fn(message)
        except Exception:
            pass
    else:
        print(message)


def enumerate_all_sources(
    domain: str,
    mode: str,
    log: Callable[[str], None] | None,
    on_found: Callable[[str], None] | None = None,
) -> List[str]:
    """Aggregate subdomain enumeration from multiple sources with streaming emit."""
    domain = (domain or "").replace("\r", "").replace("\n", "").strip()
    _log(log, f"Enumerating subdomains in {mode.upper()} mode...")
    subs: Set[str] = set()

    emit = on_found or (lambda _s: None)

    def _capture(found: Set[str]) -> None:
        for sub in found:
            if sub not in subs:
                subs.add(sub)
                emit(sub)

    _capture(enum_subdomains_common(domain, lambda m: _log(log, m), emit))
    _capture(enum_subdomains_ct(domain, lambda m: _log(log, m), emit))
    _capture(enum_subdomains_wayback(domain, lambda m: _log(log, m), emit))

    _capture(enum_subdomains_subfinder(domain, lambda m: _log(log, m), emit))
    _capture(enum_subdomains_amass(domain, mode, lambda m: _log(log, m), emit))

    if mode in ("hybrid", "active"):
        _capture(brute_dns(domain, lambda m: _log(log, m), emit))

    _log(log, f"[Subdomains] Total unique: {len(subs)}")
    return sorted(subs)
