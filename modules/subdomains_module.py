from __future__ import annotations

import asyncio

from glauka.core.models import ReconContext
from glauka.core.subdomains import enumerate_all_sources


class SubdomainModule:
    name = "subdomains"
    depends_on: list[str] = []

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    async def run(self, ctx: ReconContext) -> None:
        if not self.enabled:
            return
        if not ctx.scope.host:
            ctx.log("[Subdomains] Skipping enumeration (no host).")
            return
        ctx.log(f"[Module] {self.name} starting...")
        ctx.subdomains = await asyncio.to_thread(
            enumerate_all_sources,
            ctx.scope.host,
            ctx.scope.mode,
            ctx.log,
            lambda s: ctx.emit("subdomains", s),
        )
        ctx.log(f"[Module] {self.name} complete ({len(ctx.subdomains)} found)")
