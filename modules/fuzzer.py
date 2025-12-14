from __future__ import annotations

import shutil
import subprocess
import tempfile
from typing import Iterable, List, Optional


class FuzzerModule:
    """
    Lightweight wrapper around ffuf/feroxbuster for quick content discovery.
    """

    name = "fuzzer"
    depends_on: list[str] = []

    def __init__(self, url: str, wordlist: Optional[Iterable[str]] = None, enabled: bool = True):
        self.url = url.rstrip("/")
        self.wordlist = list(wordlist) if wordlist else ["admin", ".git", "backup", "old", "test", "dev", "login"]
        self.enabled = enabled

    async def run(self, ctx) -> None:
        if not self.enabled or not self.url:
            return

        log = getattr(ctx, "log", lambda m: None)

        tool, cmd = self._build_command()
        if not cmd:
            log("[Fuzzer] Neither ffuf nor feroxbuster found; skipping.")
            return

        with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as tmp:
            tmp.write("\n".join(self.wordlist))
            tmp.flush()
            cmd = [c.replace("{WORDLIST}", tmp.name).replace("{URL}", self.url) for c in cmd]

            log(f"[Fuzzer] Running {tool}: {' '.join(cmd)}")
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            except Exception as exc:
                log(f"[Fuzzer] Failed to start {tool}: {exc}")
                return

            discovered = []
            if proc.stdout:
                for line in proc.stdout:
                    clean = line.strip()
                    if not clean:
                        continue
                    log(f"[Fuzzer] {clean}")
                    hit = self._extract_endpoint(clean)
                    if hit:
                        discovered.append(hit)
            try:
                proc.wait(timeout=300)
            except Exception:
                proc.kill()
                log(f"[Fuzzer] {tool} timed out and was terminated.")

        if discovered:
            if hasattr(ctx, "new_endpoints") and isinstance(ctx.new_endpoints, list):
                for hit in discovered:
                    if hit not in ctx.new_endpoints:
                        ctx.new_endpoints.append(hit)
            if hasattr(ctx, "findings") and isinstance(ctx.findings, list):
                for hit in discovered:
                    ctx.findings.append(f"[Fuzzer] Found endpoint {hit}")

    def _build_command(self) -> tuple[str, List[str] | None]:
        if shutil.which("ffuf"):
            return (
                "ffuf",
                [
                    "ffuf",
                    "-u",
                    "{URL}/FUZZ",
                    "-w",
                    "{WORDLIST}",
                    "-mc",
                    "200,204,301,302,307,401,403",
                    "-fs",
                    "0",
                ],
            )
        if shutil.which("feroxbuster"):
            return (
                "feroxbuster",
                [
                    "feroxbuster",
                    "-u",
                    "{URL}",
                    "-w",
                    "{WORDLIST}",
                    "--quiet",
                    "--no-recursion",
                    "--status-codes",
                    "200,204,301,302,307,401,403",
                ],
            )
        return ("", None)

    def _extract_endpoint(self, line: str) -> Optional[str]:
        token = line.split()[0]
        if token.startswith("http"):
            return token
        if token.startswith("::"):
            return None
        token = token.lstrip("/")
        if not token:
            return None
        return f"{self.url}/{token}"
