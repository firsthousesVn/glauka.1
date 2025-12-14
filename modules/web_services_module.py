from __future__ import annotations

import asyncio

from glauka.core.models import ReconContext
from glauka.core.ports import scan_web_services


class WebServicesModule:
    name = "web_services"
    depends_on: list[str] = ["subdomains"]

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    async def run(self, ctx: ReconContext) -> None:
        if not self.enabled:
            return
        hosts = ctx.subdomains or ([ctx.scope.host] if ctx.scope.host else [])
        if not hosts:
            ctx.log("[Web Ports] Skipping web service scan (no hosts).")
            return
        ctx.log(f"[Module] {self.name} starting...")
        ctx.web_ports, ctx.nuclei_urls = await asyncio.to_thread(
            scan_web_services,
            hosts,
            ctx.log,
            lambda host, port: ctx.emit("open_port", f"{host}:{port}"),
        )
        for url in ctx.nuclei_urls:
            ctx.emit("web", url)
        ctx.log(f"[Module] {self.name} complete ({len(ctx.web_ports)} web hosts)")
