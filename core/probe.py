from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx


@dataclass
class ProbeResult:
    status_code: Optional[int]
    title: Optional[str]
    server: Optional[str]
    content_length: Optional[int]
    technologies: List[str]


class SmartProbe:
    """
    Lightweight active probe using httpx (async) to collect quick intel.
    """

    def __init__(
        self,
        timeout: float = 8.0,
        verify_ssl: bool = False,
        default_headers: Optional[Dict[str, str]] = None,
    ):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.default_headers = default_headers or {
            "User-Agent": "GlaukaSmartProbe/1.0",
            "Accept": "*/*",
        }

    async def probe_url(self, url: str) -> ProbeResult:
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=self.timeout,
                verify=self.verify_ssl,
                headers=self.default_headers,
            ) as client:
                resp = await client.get(url)
        except httpx.TimeoutException:
            return ProbeResult(None, None, None, None, ["timeout"])
        except httpx.HTTPError:
            # Includes SSL errors, connection failures, DNS issues, etc.
            return ProbeResult(None, None, None, None, [])

        text = resp.text or ""
        server = resp.headers.get("Server")
        content_length = self._extract_content_length(resp)
        title = self._extract_title(text)
        technologies = self._detect_technologies(text, resp.headers)

        return ProbeResult(
            status_code=resp.status_code,
            title=title,
            server=server,
            content_length=content_length,
            technologies=technologies,
        )

    def _extract_title(self, body: str) -> Optional[str]:
        match = re.search(r"<title[^>]*>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        title = re.sub(r"\s+", " ", match.group(1)).strip()
        return title or None

    def _extract_content_length(self, resp: httpx.Response) -> Optional[int]:
        header_len = resp.headers.get("Content-Length")
        if header_len:
            try:
                return int(header_len)
            except (ValueError, TypeError):
                pass
        try:
            return len(resp.content)
        except Exception:
            return None

    def _detect_technologies(self, body: str, headers: httpx.Headers) -> List[str]:
        techs = set()
        body_l = body.lower()

        server_hdr = headers.get("Server", "")
        powered_by = headers.get("X-Powered-By", "")

        if "wp-content" in body_l or "wp-json" in body_l:
            techs.add("WordPress")
        if headers.get("X-Jenkins"):
            techs.add("Jenkins")
        if "drupal.settings" in body_l or "drupal" in powered_by.lower():
            techs.add("Drupal")
        if "joomla" in body_l:
            techs.add("Joomla")
        if "express" in powered_by.lower():
            techs.add("Express")
        if "laravel" in body_l or "laravel" in powered_by.lower():
            techs.add("Laravel")
        if "nginx" in server_hdr.lower():
            techs.add("Nginx")
        if "apache" in server_hdr.lower():
            techs.add("Apache")
        if "cloudflare" in server_hdr.lower():
            techs.add("Cloudflare")

        return sorted(techs)
