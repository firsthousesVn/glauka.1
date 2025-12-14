from __future__ import annotations

import asyncio
from typing import List, Set

from glauka.core.probe import SmartProbe
from glauka.core.decision_engine import DecisionEngine, ScanTask
from glauka.modules import BypassModule, FuzzerModule, JsSpiderModule


class TaskContext:
    def __init__(self, log_cb=None):
        self.log_cb = log_cb or print
        self.findings: List[str] = []
        self.new_endpoints: List[str] = []

    def log(self, message: str) -> None:
        try:
            self.log_cb(message)
        except Exception:
            pass


async def _execute_task(task: ScanTask, target: str, ctx: TaskContext) -> None:
    ttype = task.task_type.upper()
    if ttype == "403_BYPASS":
        await BypassModule(target).run(ctx)
    elif ttype == "FUZZING":
        await FuzzerModule(target).run(ctx)
    elif ttype == "JS_ANALYSIS":
        await JsSpiderModule(target).run(ctx)
    else:
        ctx.log(f"[Task] {ttype} not implemented in Task Queue; skipping.")


def _normalize_target(target: str) -> str:
    if target.startswith("http://") or target.startswith("https://"):
        return target.rstrip("/")
    return f"http://{target}".rstrip("/")


async def run_task_queue(initial_targets: List[str], log_cb=None) -> TaskContext:
    """
    Task-queue driven recon loop. Continuously probes and enqueues new endpoints
    discovered by downstream tasks (e.g., fuzzing).
    """
    queue: List[str] = [_normalize_target(t) for t in initial_targets or []]
    seen: Set[str] = set()
    ctx = TaskContext(log_cb=log_cb)
    probe = SmartProbe()
    decider = DecisionEngine()

    while queue:
        target = queue.pop(0)
        if target in seen:
            continue
        seen.add(target)

        ctx.log(f"[Queue] Probing {target}")
        probe_result = await probe.probe_url(target)
        ctx.log(f"[Probe] {target} -> {probe_result.status_code} {probe_result.title or ''}".strip())

        tasks = decider.evaluate(probe_result)
        ctx.log(f"[Queue] {len(tasks)} follow-up tasks for {target}")

        for task in tasks:
            await _execute_task(task, target, ctx)
            # Enqueue any new endpoints discovered during this task.
            if ctx.new_endpoints:
                for ep in ctx.new_endpoints:
                    if ep not in seen and ep not in queue:
                        queue.append(ep)
                ctx.new_endpoints.clear()

    return ctx


def run(initial_targets: List[str], log_cb=None) -> TaskContext:
    return asyncio.run(run_task_queue(initial_targets, log_cb=log_cb))


__all__ = ["run_task_queue", "run", "TaskContext"]
