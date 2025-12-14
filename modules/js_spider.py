from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urljoin

import httpx


class JsSpiderModule:
    """
    Fetch HTML, crawl script src links, and hunt for API keys in JS.
    """

    name = "js_spider"
    depends_on: list[str] = []

    PATTERNS = {
        "Google API": r"AIza[0-9A-Za-z\-_]{35}",
        "Slack Token": r"xox[baprs]-([0-9a-zA-Z]{10,48})",
        "AWS Access Key": r"AKIA[0-9A-Z]{16}",
        "Generic API Key": r"(?i)(api_key|apikey|access_token)[\"'\s:=]+([a-zA-Z0-9]{20,})",
    }

    def __init__(self, url: str, enabled: bool = True, timeout: float = 8.0):
        self.url = url
        self.enabled = enabled
        self.timeout = timeout

    async def run(self, ctx) -> None:
        if not self.enabled or not self.url:
            return

        log = getattr(ctx, "log", lambda m: None)
        findings = getattr(ctx, "findings", None)

        async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=self.timeout) as client:
            try:
                resp = await client.get(self.url)
                html = resp.text
            except httpx.HTTPError as exc:
                log(f"[JS Spider] Failed to fetch {self.url}: {exc}")
                return

            script_urls = self._extract_scripts(html, self.url)
            if not script_urls:
                log(f"[JS Spider] No script tags found at {self.url}")
                return

            log(f"[JS Spider] Fetching {len(script_urls)} scripts from {self.url}")

            for s_url in script_urls:
                try:
                    s_resp = await client.get(s_url)
                    js_body = s_resp.text
                except httpx.HTTPError:
                    log(f"[JS Spider] Failed to fetch script: {s_url}")
                    continue

                hits = self._find_secrets(js_body)
                for hit in hits:
                    msg = f"[JS Spider] {hit} found in {s_url}"
                    log(msg)
                    if isinstance(findings, list):
                        findings.append(msg)

    def _extract_scripts(self, html: str, base_url: str) -> List[str]:
        matches = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
        scripts = []
        for m in matches:
            scripts.append(urljoin(base_url, m.strip()))
        return list(dict.fromkeys(scripts))

    def _find_secrets(self, text: str) -> List[str]:
        hits: List[str] = []
        for name, pattern in self.PATTERNS.items():
            if re.search(pattern, text):
                hits.append(name)
        return hits
