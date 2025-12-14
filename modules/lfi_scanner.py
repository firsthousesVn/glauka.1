from __future__ import annotations

import asyncio
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from glauka.core.models import ReconContext


class LfiScannerModule:
    """Naive LFI detection by injecting path traversal payloads into query parameters."""

    name = "lfi_scanner"
    depends_on: list[str] = ["web_services"]

    PAYLOADS = [
        "../../../../../../etc/passwd",
        "../../etc/passwd",
        "..%2f..%2f..%2f..%2fetc%2fpasswd",
    ]

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    async def run(self, ctx: ReconContext) -> None:
        if not self.enabled:
            return
        if not ctx.nuclei_urls:
            ctx.log("[LFI] No URLs to test.")
            return
        client = ctx.http_client
        if client is None:
            ctx.log("[LFI] HTTP client unavailable.")
            return

        ctx.log("[Module] lfi_scanner starting...")
        semaphore = asyncio.Semaphore(10)

        async def _probe(target_url: str) -> None:
            async with semaphore:
                try:
                    resp = await client.get(target_url, timeout=12)
                except Exception:
                    return
                if "root:x:0:0" in resp.text or "etc/passwd" in resp.text:
                    finding = f"[LFI] Potential LFI at {target_url}"
                    ctx.findings.append(finding)
                    ctx.emit("lfi", finding)
                    if ctx.verbose_logs:
                        ctx.log(finding)

        tasks = []
        for url in ctx.nuclei_urls:
            parsed = urlparse(url)
            query = dict(parse_qsl(parsed.query))
            if not query:
                continue
            for key in list(query.keys()):
                for payload in self.PAYLOADS:
                    mutated = query.copy()
                    mutated[key] = payload
                    new_query = urlencode(mutated, doseq=True)
                    target_url = urlunparse(parsed._replace(query=new_query))
                    tasks.append(asyncio.create_task(_probe(target_url)))

        if tasks:
            await asyncio.gather(*tasks)
        ctx.log("[Module] lfi_scanner complete")
