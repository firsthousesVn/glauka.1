from __future__ import annotations

import asyncio
import threading
from typing import Callable, Optional, Dict

from glauka.core.recon import run_full_recon
from glauka.core.models import ReconResult


def run_scan_async(
    target: str,
    mode: str,
    on_result: Callable[[ReconResult], None],
    on_log: Callable[[str], None],
    *,
    config_overrides: Optional[Dict[str, object]] = None,
    resume: bool = False,
    export_cb: Optional[Callable[[ReconResult], None]] = None,
    on_progress: Optional[Callable[[str, str], None]] = None,
) -> threading.Thread:
    """
    Spawn a background recon scan. Invokes on_log as recon emits messages,
    then on_result with the ReconResult once complete.
    """

    def worker():
        result: ReconResult | None = None
        try:
            result = asyncio.run(
                run_full_recon(
                    target,
                    mode=mode,
                    log_cb=on_log,
                    progress_cb=on_progress,
                    config_overrides=config_overrides,
                    resume=resume,
                )
            )
            if export_cb and result:
                export_cb(result)
        except Exception as exc:
            on_log(f"[Error] {exc}")
        finally:
            on_result(result)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread
