from __future__ import annotations

import asyncio
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from glauka.core.models import ReconContext


class RedirectTesterModule:
    """Detect potential open redirects by injecting external destination into known params."""

    name = "redirect_tester"
    depends_on: list[str] = ["web_services"]

    PARAM_KEYS = ["next", "url", "redirect", "redir", "dest", "destination", "to"]
    PAYLOAD = "https://example.org/glauka-open-redirect-test"

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    async def run(self, ctx: ReconContext) -> None:
        if not self.enabled:
            return
        if not ctx.nuclei_urls:
            ctx.log("[Redirect] No URLs to test.")
            return
        client = ctx.http_client
        if client is None:
            ctx.log("[Redirect] HTTP client unavailable.")
            return

        ctx.log("[Module] redirect_tester starting...")
        semaphore = asyncio.Semaphore(10)

        async def _probe(target_url: str) -> None:
            async with semaphore:
                try:
                    resp = await client.get(target_url, timeout=8)
                except Exception:
                    return
                location = resp.headers.get("Location", "") if hasattr(resp, "headers") else ""
                if self.PAYLOAD in location or resp.url.startswith(self.PAYLOAD):
                    finding = f"[Redirect] Potential open redirect at {target_url}"
                    ctx.findings.append(finding)
                    ctx.log(finding)

        tasks = []
        for url in ctx.nuclei_urls:
            parsed = urlparse(url)
            query = dict(parse_qsl(parsed.query))
            targets = []
            for key in self.PARAM_KEYS:
                if key in query:
                    mutated = query.copy()
                    mutated[key] = self.PAYLOAD
                    new_query = urlencode(mutated, doseq=True)
                    targets.append(urlunparse(parsed._replace(query=new_query)))

            for target_url in targets:
                tasks.append(asyncio.create_task(_probe(target_url)))

        if tasks:
            await asyncio.gather(*tasks)
        ctx.log("[Module] redirect_tester complete")
