from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests
import yaml


def _noop(_: str) -> None:
    return


@dataclass
class AuthContext:
    name: str
    session: requests.Session
    cookies: Dict[str, str]
    headers: Dict[str, str]


class LoginManager:
    """
    Loads login configuration, authenticates, and returns session-bound auth contexts.
    """

    def __init__(self, config_path: str | Path, log=_noop):
        self.config_path = Path(config_path)
        self.log = log or _noop
        self.users: List[Dict[str, object]] = self._load_config()

    def _load_config(self) -> List[Dict[str, object]]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Login config not found: {self.config_path}")
        data = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        if isinstance(data, dict) and "users" in data:
            users = data.get("users") or []
        elif isinstance(data, list):
            users = data
        else:
            users = []
        if not isinstance(users, list):
            raise ValueError("Login config must contain a list of users.")
        return users

    def login_all(self) -> Dict[str, AuthContext]:
        contexts: Dict[str, AuthContext] = {}
        for user in self.users:
            name = str(user.get("name") or "user")
            try:
                ctx = self._login_entry(user)
                contexts[name] = ctx
                self.log(f"[Login] {name} authenticated.")
            except Exception as exc:
                self.log(f"[Login] {name} failed: {exc}")
        return contexts

    def login_user(self, name: str) -> AuthContext:
        entry = next((u for u in self.users if u.get("name") == name), None)
        if not entry:
            raise ValueError(f"User '{name}' not found in config.")
        return self._login_entry(entry)

    def _login_entry(self, entry: Dict[str, object]) -> AuthContext:
        login_url = entry.get("login_url")
        if not login_url:
            raise ValueError("Missing login_url in config entry.")
        username = entry.get("username")
        password = entry.get("password")
        if username is None or password is None:
            raise ValueError("Missing username or password in config entry.")

        session = requests.Session()
        headers = {str(k): str(v) for k, v in (entry.get("headers") or {}).items()}
        session.headers.update(headers)

        username_field = str(entry.get("username_field") or "username")
        password_field = str(entry.get("password_field") or "password")
        payload = dict(entry.get("payload") or {})
        if not payload:
            payload = {username_field: username, password_field: password}
        for k, v in (entry.get("extra_params") or {}).items():
            payload[str(k)] = v

        timeout = float(entry.get("timeout", 15) or 15)
        verify = bool(entry.get("verify", True))
        resp = session.post(str(login_url), data=payload, timeout=timeout, verify=verify)
        if resp.status_code >= 400:
            raise ValueError(f"Login HTTP {resp.status_code}")

        cookies = dict(session.cookies.get_dict())
        return AuthContext(
            name=str(entry.get("name") or "user"),
            session=session,
            cookies=cookies,
            headers=dict(session.headers),
        )
