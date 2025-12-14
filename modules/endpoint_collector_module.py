from __future__ import annotations

import asyncio
import subprocess
import shutil
from pathlib import Path
from typing import List, Set

from glauka.core.models import ReconContext


def _run_tool(cmd: List[str], timeout: int = 180) -> Set[str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        output = proc.stdout or ""
        return {line.strip() for line in output.splitlines() if line.strip()}
    except Exception:
        return set()


def _filter_urls(urls: Set[str], host: str) -> List[str]:
    filtered = []
    for u in urls:
        if host not in u:
            continue
        if not (u.startswith("http://") or u.startswith("https://")):
            continue
        if "?" not in u:
            continue
        filtered.append(u)
    return filtered


class EndpointCollectorModule:
    """
    Aggregates URLs with parameters for fuzzing using waybackurls/gau/katana/hakrawler when available.
    """

    name = "endpoint_collector"
    depends_on: list[str] = ["subdomains"]

    def __init__(self, enabled: bool = True, limit: int = 500):
        self.enabled = enabled
        self.limit = limit

    async def run(self, ctx: ReconContext) -> None:
        if not self.enabled:
            return
        hosts = ctx.subdomains or ([ctx.scope.host] if ctx.scope.host else [])
        hosts = [h for h in hosts if h]
        if not hosts:
            ctx.log("[Endpoints] No hosts to collect from.")
            return

        ctx.log(f"[Module] {self.name} starting ({len(hosts)} hosts)...")
        all_urls: Set[str] = set()

        def _collect_host(host: str) -> None:
            urls: Set[str] = set()
            if shutil.which("waybackurls"):
                urls |= _run_tool(["waybackurls", host])
            if shutil.which("gau"):
                urls |= _run_tool(["gau", host])
            if shutil.which("katana"):
                urls |= _run_tool(["katana", "-u", f"https://{host}", "-silent"])
            if shutil.which("hakrawler"):
                urls |= _run_tool(["hakrawler", "-domain", host, "-plain"])

            filtered = _filter_urls(urls, host)
            for u in filtered:
                if len(all_urls) < self.limit:
                    all_urls.add(u)
                    ctx.emit("endpoints", u)

        await asyncio.to_thread(lambda: [ _collect_host(h) for h in hosts ])

        ctx.extra["endpoints"] = sorted(all_urls)
        ctx.log(f"[Module] {self.name} complete ({len(all_urls)} endpoints)")
