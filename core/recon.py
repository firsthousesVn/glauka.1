from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Callable, Dict, List, Optional

from glauka.config import load_config, merge_dicts
from glauka.core.http_client import HttpClient
from .models import ReconContext, ReconResult, ScopeInfo
from .target import build_scope
from glauka.modules import (
    BasePortScanModule,
    NucleiModule,
    SubdomainModule,
    WebServicesModule,
    LfiScannerModule,
    SqlInjectionModule,
    RedirectTesterModule,
    ScreenshotModule,
    SecretsModule,
    WebProbeModule,
    EndpointCollectorModule,
)
from glauka.session_manager import SessionManager
from glauka.state_manager import load_state, save_state, to_result


def _noop_log(message: str) -> None:
    try:
        print(message)
    except Exception:
        pass


async def run_full_recon(
    target: str,
    mode: str = "passive",
    log_cb: Optional[Callable[[str], None]] = None,
    progress_cb: Optional[Callable[[str, str], None]] = None,
    config_overrides: Optional[Dict[str, object]] = None,
    resume: bool = False,
) -> ReconResult:
    """
    Orchestrate full recon. Handles scope building, subdomain enumeration,
    base port scan, web port scan, and nuclei scan. Returns structured data only.
    """
    log = log_cb or _noop_log
    start_total = time.perf_counter()
    mode_normalized = (mode or "passive").lower().strip()
    if mode_normalized not in ("passive", "hybrid", "active"):
        mode_normalized = "passive"

    config = load_config()
    if config_overrides:
        config = merge_dicts(config, config_overrides)

    state_path = str(config.get("state", {}).get("path", ".recon-state.json.gz"))
    if resume:
        state = load_state(state_path)
        if state:
            log("[State] Loaded previous run; returning cached result.")
            scope = ScopeInfo(**state.get("scope", {}))
            ctx = ReconContext(
                scope=scope,
                config=config,
                log=log,
                http_client=_build_http_client(config, log),
                session_manager=SessionManager(),
                progress_cb=progress_cb,
                timings=state.get("timings", {}),
            )
            ctx.subdomains = state.get("subdomains", [])
            ctx.base_ports = state.get("base_ports", {})
            ctx.web_ports = state.get("web_ports", {})
            ctx.nuclei_raw = state.get("nuclei_raw", "")
            ctx.nuclei_urls = state.get("nuclei_urls", [])
            ctx.findings = state.get("findings", [])
            ctx.screenshots = state.get("screenshots", [])
            ctx.extra = state.get("extra", {})
            return to_result(ctx)

    scope: ScopeInfo = build_scope(target, mode_normalized, log)
    _guard_internal_target(scope, config, log)
    ctx = ReconContext(
        scope=scope,
        config=config,
        log=log,
        http_client=_build_http_client(config, log),
        session_manager=SessionManager(),
        state_path=state_path,
        timings={},
        progress_cb=progress_cb,
        verbose_logs=bool(config.get("logging", {}).get("verbose", False)),
        event_path=str(config.get("logging", {}).get("event_path") or ""),
    )
    _apply_saved_session(ctx)

    modules = _build_module_chain(config)
    layers = _resolve_module_layers(modules, log)
    await _execute_layers(layers, ctx, log)

    ctx.timings["total"] = time.perf_counter() - start_total
    log(f"[Timing] Total recon duration: {ctx.timings['total']:.2f}s")

    save_state(ctx, state_path)

    return to_result(ctx)


def _apply_saved_session(ctx: ReconContext) -> None:
    scope = ctx.scope
    auth = ctx.session_manager.get_auth(scope.host or scope.ip or "")
    if auth and hasattr(ctx.http_client, "session"):
        ctx.http_client.session.auth = auth
    # Config-provided basic auth
    if ctx.config.get("auth", {}).get("basic"):
        basic = ctx.config["auth"]["basic"]
        if isinstance(basic, dict) and basic.get("username") and basic.get("password") and hasattr(ctx.http_client, "session"):
            ctx.http_client.session.auth = (basic["username"], basic["password"])
    cookies = ctx.session_manager.get_cookies(scope.host or scope.ip or "")
    if cookies and hasattr(ctx.http_client, "session"):
        ctx.http_client.session.cookies.update(cookies)
    headers = ctx.session_manager.get_headers(scope.host or scope.ip or "")
    if headers:
        ctx.http_client.default_headers.update(headers)


def _build_http_client(config: Dict[str, object], log: Callable[[str], None]) -> HttpClient:
    http_cfg = config.get("http", {}) if isinstance(config, dict) else {}
    return HttpClient(
        log_cb=log,
        proxies=http_cfg.get("proxies"),
        default_headers=http_cfg.get("headers", {}),
        debug=bool(http_cfg.get("debug", False)),
        max_retries=int(http_cfg.get("retries", 3) or 3),
        backoff_factor=float(http_cfg.get("backoff_factor", 0.5) or 0.5),
        jitter=float(http_cfg.get("jitter", 0.2) or 0.2),
        default_timeout=float(http_cfg.get("timeout", 20.0) or 20.0),
        throttle_on_429=bool(http_cfg.get("throttle_on_429", True)),
    )


def _guard_internal_target(scope: ScopeInfo, config: Dict[str, object], log: Callable[[str], None]) -> None:
    allow_internal = bool(config.get("safety", {}).get("allow_internal", False))
    ip = scope.ip or ""
    host = (scope.host or "").lower()
    blocked = ip.startswith("127.") or ip.startswith("169.254.") or host in ("localhost", "127.0.0.1")
    if blocked and not allow_internal:
        message = "[Safety] Target resolves to localhost/link-local; blocking scan. Set safety.allow_internal=true to override."
        log(message)
        raise ValueError(message)
    if blocked:
        log("[Safety] Target is local; proceeding because allow_internal is set.")


async def _execute_layers(layers: List[List[object]], ctx: ReconContext, log: Callable[[str], None]) -> None:
    errors: List[Dict[str, str]] = []
    for layer in layers:
        tasks = []
        for module in layer:
            tasks.append(asyncio.create_task(_run_module(module, ctx, log, errors)))
        if tasks:
            await asyncio.gather(*tasks)
    if errors:
        ctx.extra["module_errors"] = errors


async def _run_module(module: object, ctx: ReconContext, log: Callable[[str], None], errors: List[Dict[str, str]]) -> None:
    name = getattr(module, "name", module.__class__.__name__)
    if not getattr(module, "enabled", True):
        ctx.timings[name] = 0.0
        log(f"[Module] {name} disabled; skipping.")
        return
    started = time.perf_counter()
    try:
        await module.run(ctx)  # type: ignore[attr-defined]
    except Exception as exc:
        errors.append({"module": name, "error": str(exc)})
        log(f"[Module] {name} failed: {exc}")
    finally:
        duration = time.perf_counter() - started
        ctx.timings[name] = duration
        log(f"[Timing] {name} finished in {duration:.2f}s")


def _resolve_module_layers(modules: List[object], log: Callable[[str], None]) -> List[List[object]]:
    active = {m.name: m for m in modules if getattr(m, "enabled", True)}
    deps_map: Dict[str, List[str]] = {}
    for name, module in active.items():
        deps = list(getattr(module, "depends_on", []) or [])
        missing = [d for d in deps if d not in active]
        if missing:
            log(f"[Module] {name} missing deps {', '.join(missing)}; continuing without them.")
        deps_map[name] = [d for d in deps if d in active]

    indegree: Dict[str, int] = {name: len(deps) for name, deps in deps_map.items()}
    graph: Dict[str, List[str]] = defaultdict(list)
    for name, deps in deps_map.items():
        for dep in deps:
            graph[dep].append(name)

    layers: List[List[object]] = []
    ready = [name for name, deg in indegree.items() if deg == 0]
    visited = set()

    while ready:
        current_layer: List[object] = []
        next_ready: List[str] = []
        for name in ready:
            if name in visited:
                continue
            visited.add(name)
            module = active.get(name)
            if module:
                current_layer.append(module)
            for dep in graph.get(name, []):
                indegree[dep] -= 1
                if indegree[dep] == 0:
                    next_ready.append(dep)
        if current_layer:
            layers.append(current_layer)
        ready = next_ready

    if len(visited) != len(active):
        log("[Module] Dependency cycle or unresolved modules detected; using original order fallback.")
        return [[m] for m in modules if getattr(m, "enabled", True)]

    return layers


def _build_module_chain(config: Dict[str, object]):
    modules = []
    module_cfg = config.get("modules", {}) if isinstance(config, dict) else {}

    sub_cfg = module_cfg.get("subdomains", {})
    modules.append(SubdomainModule(enabled=sub_cfg.get("enabled", True)))

    bp_cfg = module_cfg.get("base_ports", {})
    modules.append(
        BasePortScanModule(
            enabled=bp_cfg.get("enabled", True),
            ports=bp_cfg.get("ports"),
            max_concurrent=config.get("concurrency", {}).get("max_connections", 200),
        )
    )

    ep_cfg = module_cfg.get("endpoint_collector", {})
    modules.append(
        EndpointCollectorModule(
            enabled=ep_cfg.get("enabled", True),
            limit=ep_cfg.get("limit", 500),
        )
    )

    web_cfg = module_cfg.get("web_services", {})
    modules.append(WebServicesModule(enabled=web_cfg.get("enabled", True)))

    probe_cfg = module_cfg.get("web_probe", {})
    modules.append(WebProbeModule(enabled=probe_cfg.get("enabled", True)))

    sec_cfg = module_cfg.get("secrets_scanner", {})
    modules.append(SecretsModule(enabled=sec_cfg.get("enabled", True)))

    nuc_cfg = module_cfg.get("nuclei", {})
    modules.append(
        NucleiModule(
            enabled=nuc_cfg.get("enabled", True),
            severity=nuc_cfg.get("severity", "low,medium,high,critical"),
        )
    )
    lfi_cfg = module_cfg.get("lfi_scanner", {})
    modules.append(LfiScannerModule(enabled=lfi_cfg.get("enabled", True)))

    sqli_cfg = module_cfg.get("sqli_scanner", {})
    modules.append(SqlInjectionModule(enabled=sqli_cfg.get("enabled", True)))

    redir_cfg = module_cfg.get("redirect_tester", {})
    modules.append(RedirectTesterModule(enabled=redir_cfg.get("enabled", True)))

    shot_cfg = module_cfg.get("screenshotter", {})
    modules.append(
        ScreenshotModule(
            enabled=shot_cfg.get("enabled", False),
            output_dir=shot_cfg.get("output_dir", "screenshots"),
            use_docker=bool(shot_cfg.get("use_docker", True)),
        )
    )
    return modules
