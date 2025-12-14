from __future__ import annotations

import asyncio

from glauka.core.models import ReconContext
from glauka.core.nuclei import nuclei_scan


class NucleiModule:
    name = "nuclei"
    depends_on: list[str] = ["web_services"]

    def __init__(self, enabled: bool = True, severity: str = "low,medium,high,critical"):
        self.enabled = enabled
        self.severity = severity

    async def run(self, ctx: ReconContext) -> None:
        if not self.enabled:
            return
        ctx.log(f"[Module] {self.name} starting...")
        nuc_cfg = ctx.config.get("modules", {}).get("nuclei", {}) if isinstance(ctx.config, dict) else {}
        severity = nuc_cfg.get("severity", self.severity)
        disable_etags = bool(
            nuc_cfg.get("disable_etags", False) or nuc_cfg.get("disable_exclude_tags", False)
        )
        ctx.nuclei_raw = await asyncio.to_thread(
            nuclei_scan,
            ctx.nuclei_urls,
            ctx.log,
            severity,
            tags=nuc_cfg.get("tags"),
            exclude_tags=nuc_cfg.get("exclude_tags"),
            disable_exclude_tags=disable_etags,
            update_templates=bool(nuc_cfg.get("update_templates", True)),
            templates=nuc_cfg.get("templates", []),
            concurrency=nuc_cfg.get("concurrency"),
            rate_limit=nuc_cfg.get("rate_limit"),
            progress_cb=ctx.emit,
            verbose=ctx.verbose_logs,
        )
        ctx.log(f"[Module] {self.name} complete")
