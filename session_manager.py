from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv():
        return

try:  # pragma: no cover - optional dependency handling
    import tldextract
except Exception:  # pragma: no cover
    tldextract = None  # type: ignore

from glauka.core.target import is_ip


def _base_domain(target: str) -> str:
    host = (target or "").split(":")[0].strip().lower()
    if not host:
        return ""
    if is_ip(host):
        return host
    if tldextract:
        try:
            extracted = tldextract.extract(host)
            if extracted.domain and extracted.suffix:
                return f"{extracted.domain}.{extracted.suffix}".lower()
        except Exception:
            return host
    return host


class SessionManager:
    """
    Manage per-target auth credentials and cookies.
    Loads from .env or secrets.json if present; can be augmented at runtime.
    Uses base-domain normalization so subdomains share cookies/auth.
    """

    def __init__(self, secrets_path: str | None = None):
        self.sessions: Dict[str, Dict[str, object]] = {}
        self._load_env()
        self._load_secrets(secrets_path or "secrets.json")

    def _load_env(self) -> None:
        try:
            load_dotenv()
        except Exception:
            return

    def _load_secrets(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for target, info in data.items():
                    if isinstance(info, dict):
                        self.sessions[_base_domain(target)] = info
        except Exception:
            return

    def get_auth(self, target: str) -> Optional[tuple[str, str]]:
        key = _base_domain(target)
        entry = self.sessions.get(key, {}) or self.sessions.get(target, {})
        user = entry.get("username") or os.getenv("GLAUKA_USER")
        pwd = entry.get("password") or os.getenv("GLAUKA_PASSWORD")
        if user and pwd:
            return (str(user), str(pwd))
        return None

    def get_headers(self, target: str) -> Dict[str, str]:
        key = _base_domain(target)
        entry = self.sessions.get(key, {}) or self.sessions.get(target, {})
        headers = entry.get("headers") or os.getenv("GLAUKA_HEADERS")
        if isinstance(headers, dict):
            return {str(k): str(v) for k, v in headers.items()}
        return {}

    def get_cookies(self, target: str) -> Dict[str, str]:
        key = _base_domain(target)
        entry = self.sessions.get(key, {}) or self.sessions.get(target, {})
        cookies = entry.get("cookies")
        if isinstance(cookies, dict):
            return {str(k): str(v) for k, v in cookies.items()}
        return {}

    def set_cookies(self, target: str, cookies: Dict[str, str]) -> None:
        key = _base_domain(target)
        self.sessions.setdefault(key or target, {})["cookies"] = cookies
