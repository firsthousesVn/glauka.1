from __future__ import annotations

from glauka.core.models import ReconContext
from glauka.core.ports import quick_port_scan_async


class BasePortScanModule:
    name = "base_ports"
    depends_on: list[str] = []

    def __init__(self, enabled: bool = True, ports: list[int] | None = None, max_concurrent: int = 200):
        self.enabled = enabled
        self.ports = ports
        self.max_concurrent = max_concurrent

    async def run(self, ctx: ReconContext) -> None:
        if not self.enabled:
            return
        if not ctx.scope.ip:
            ctx.log("[Ports] Skipping base port scan (no IP).")
            return
        ctx.log(f"[Module] {self.name} starting...")
        ports = self.ports or ctx.config.get("modules", {}).get("base_ports", {}).get("ports")
        max_conn = ctx.config.get("concurrency", {}).get("max_connections", self.max_concurrent)
        ctx.base_ports = await quick_port_scan_async(
            ctx.scope.ip,
            ports or [],
            ctx.log,
            max_conn,
            on_found=lambda port, service: ctx.emit("open_port", f"{ctx.scope.ip}:{port} ({service})"),
            verbose=ctx.verbose_logs,
        )
        if ctx.base_ports:
            details = ", ".join(f"{p}/{svc}" for p, svc in sorted(ctx.base_ports.items()))
            ctx.log(f"[Ports] Open on {ctx.scope.ip}: {details}")
        else:
            ctx.log(f"[Ports] No open base ports detected on {ctx.scope.ip}.")
        ctx.log(f"[Module] {self.name} complete ({len(ctx.base_ports)} open)")
