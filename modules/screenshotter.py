from __future__ import annotations

import asyncio
import os
import random
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from glauka.core.models import ReconContext


class ScreenshotModule:
    """Capture screenshots for discovered web URLs using selenium + headless Chrome if available."""

    name = "screenshotter"
    depends_on: list[str] = ["web_services"]

    def __init__(self, enabled: bool = False, output_dir: str = "screenshots", use_docker: bool = True):
        self.enabled = enabled
        self.output_dir = Path(output_dir)
        self.use_docker = use_docker
        self._docker_container: Optional[str] = None
        self._remote_port: int = 9515 + random.randint(1, 200)  # avoid clobbering existing instances

    async def run(self, ctx: ReconContext) -> None:
        if not self.enabled:
            return
        if not ctx.nuclei_urls:
            ctx.log("[Screenshots] No URLs to capture.")
            return
        await asyncio.to_thread(self._capture_all, ctx)

    def _capture_all(self, ctx: ReconContext) -> None:
        driver = self._init_driver(ctx)
        if driver is None:
            ctx.log("[Screenshots] Selenium/Chrome not available; skipping.")
            return
        self.output_dir.mkdir(parents=True, exist_ok=True)
        ctx.log("[Module] screenshotter starting...")
        for url in ctx.nuclei_urls:
            filename = self._name_from_url(url)
            out_path = self.output_dir / filename
            try:
                driver.get(url)
                driver.set_window_size(1600, 1200)
                driver.save_screenshot(str(out_path))
                ctx.screenshots.append(str(out_path))
                ctx.log(f"[Screenshots] Saved {out_path}")
            except Exception as exc:
                ctx.log(f"[Screenshots] Failed {url}: {exc}")
        try:
            driver.quit()
        except Exception:
            pass
        self._stop_docker_container(ctx)
        ctx.log("[Module] screenshotter complete")

    def _init_driver(self, ctx: ReconContext):
        if self.use_docker:
            driver = self._init_docker_driver(ctx)
            if driver:
                return driver
            ctx.log("[Screenshots] Docker sandbox unavailable; trying local driver.")
        return self._init_local_driver(ctx)

    def _init_docker_driver(self, ctx: ReconContext):
        if shutil.which("docker") is None:
            return None
        container_name = f"glauka-shot-{os.getpid()}-{int(time.time())}"
        remote_url = f"http://127.0.0.1:{self._remote_port}/wd/hub"
        cmd = [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            container_name,
            "-p",
            f"{self._remote_port}:4444",
            "-e",
            "SE_OPTS=--session-timeout 300",
            "selenium/standalone-chrome:latest",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25, check=False)
            if proc.returncode != 0:
                ctx.log(f"[Screenshots] Docker sandbox failed: {proc.stderr.strip() or proc.stdout.strip()}")
                return None
            self._docker_container = container_name
        except Exception as exc:
            ctx.log(f"[Screenshots] Docker sandbox exception: {exc}")
            return None

        # Wait briefly for the remote driver to be ready
        ready_deadline = time.time() + 15
        last_exc: Optional[Exception] = None
        while time.time() < ready_deadline:
            try:
                driver = self._remote_driver(remote_url)
                if driver:
                    ctx.log(f"[Screenshots] Using sandboxed Chrome at {remote_url}")
                    return driver
            except Exception as exc:  # pragma: no cover - best-effort
                last_exc = exc
            time.sleep(1.2)
        ctx.log(f"[Screenshots] Remote Chrome not ready: {last_exc}")
        self._stop_docker_container(ctx)
        return None

    def _remote_driver(self, remote_url: str):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        return webdriver.Remote(command_executor=remote_url, options=options)

    def _stop_docker_container(self, ctx: ReconContext) -> None:
        if not self._docker_container or shutil.which("docker") is None:
            return
        try:
            subprocess.run(["docker", "rm", "-f", self._docker_container], capture_output=True, text=True, timeout=10)
        except Exception as exc:
            ctx.log(f"[Screenshots] Failed to clean sandbox: {exc}")
        finally:
            self._docker_container = None

    def _init_local_driver(self, ctx: ReconContext):
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except Exception:
            return None

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        try:
            driver = webdriver.Chrome(options=options)
            return driver
        except Exception as exc:
            ctx.log(f"[Screenshots] Chrome driver init failed: {exc}")
            return None

    @staticmethod
    def _name_from_url(url: str) -> str:
        safe = url.replace("://", "_").replace("/", "_").replace(":", "_")
        return f"{safe}.png"
