from __future__ import annotations

import asyncio
import re
from typing import List

from glauka.core.models import ReconContext


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


class WebProbeModule:
    """
    Probes discovered web URLs to confirm liveness and extract basic metadata.
    """

    name = "web_probe"
    depends_on: list[str] = ["web_services"]

    def __init__(self, enabled: bool = True, timeout: float = 8.0):
        self.enabled = enabled
        self.timeout = timeout

    async def run(self, ctx: ReconContext) -> None:
        if not self.enabled:
            return
        urls: List[str] = list(ctx.nuclei_urls or [])
        if not urls:
            ctx.log("[WebProbe] No URLs to probe.")
            return

        ctx.log(f"[Module] {self.name} starting ({len(urls)} URLs)...")
        client = ctx.http_client
        if client is None:
            ctx.log("[WebProbe] HTTP client unavailable.")
            return

        semaphore = asyncio.Semaphore(10)
        results: list[dict] = []

        async def _probe(url: str) -> None:
            async with semaphore:
                try:
                    resp = await client.get(url, timeout=self.timeout)
                    title = _extract_title(resp.text)
                    server = resp.headers.get("Server", "") if isinstance(resp.headers, dict) else ""
                    entry = {
                        "url": resp.url or url,
                        "status": resp.status_code,
                        "title": title,
                        "server": server,
                    }
                    results.append(entry)
                    summary = f"{resp.status_code} {resp.url or url}"
                    if title:
                        summary += f" | {title[:80]}"
                    if server:
                        summary += f" (srv: {server[:40]})"
                    ctx.emit("web_info", summary)
                    if ctx.verbose_logs:
                        ctx.log(f"[WebProbe] {summary}")
                except Exception:
                    if ctx.verbose_logs:
                        ctx.log(f"[WebProbe] Failed: {url}")

        tasks = [asyncio.create_task(_probe(u)) for u in urls]
        if tasks:
            await asyncio.gather(*tasks)
        ctx.extra["web_probe"] = results
        ctx.log(f"[Module] {self.name} complete ({len(results)} alive)")
