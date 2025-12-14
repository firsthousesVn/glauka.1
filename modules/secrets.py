from __future__ import annotations

import asyncio
import re
from typing import List

import aiohttp


class SecretsModule:
    name = "secrets_scanner"
    depends_on: List[str] = ["web_services"]

    PATTERNS = {
        "Google API": r"AIza[0-9A-Za-z\\-_]{35}",
        "Slack Token": r"xox[baprs]-([0-9a-zA-Z]{10,48})",
        "AWS Access Key": r"AKIA[0-9A-Z]{16}",
        "Generic API Key": r"(?i)(api_key|apikey|access_token)[\"\'\s:=]+([a-zA-Z0-9]{20,})",
    }

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    async def run(self, ctx) -> None:
        if not self.enabled:
            return
        if not ctx.web_ports:
            return

        urls = []
        for host, ports in ctx.web_ports.items():
            for p in ports:
                scheme = "https" if p in [443, 8443] else "http"
                urls.append(f"{scheme}://{host}:{p}")

        ctx.log(f"[Secrets] Scanning {len(urls)} endpoints for leaked tokens...")

        async with aiohttp.ClientSession() as session:
            tasks = [self._scan_url(session, u, ctx) for u in urls]
            await asyncio.gather(*tasks)

    async def _scan_url(self, session, url, ctx):
        try:
            async with session.get(url, timeout=5, ssl=False) as resp:
                text = await resp.text()
                for name, pattern in self.PATTERNS.items():
                    if re.search(pattern, text):
                        msg = f"(!) {name} found at {url}"
                        ctx.findings.append(msg)
                        ctx.log(f"[Secrets] {msg}")
        except Exception:
            pass
