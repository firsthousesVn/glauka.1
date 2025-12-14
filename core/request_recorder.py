from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests


def _noop(_: str) -> None:
    return


@dataclass
class RequestTemplate:
    method: str
    url: str
    headers: Dict[str, str]
    cookies: Dict[str, str]
    body: Optional[str]
    params: Dict[str, str]
    auth_context: str


class RequestRecorder:
    """
    Records request/response metadata for later replay and IDOR scanning.
    """

    def __init__(self, store_path: str | Path = "reports/request_templates.json", log=_noop):
        self.store_path = Path(store_path)
        self.log = log or _noop
        self.templates: List[RequestTemplate] = self._load_existing()
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_existing(self) -> List[RequestTemplate]:
        if not self.store_path.exists():
            return []
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        templates: List[RequestTemplate] = []
        for item in data or []:
            if not isinstance(item, dict):
                continue
            templates.append(
                RequestTemplate(
                    method=item.get("method", "GET"),
                    url=item.get("url", ""),
                    headers=item.get("headers") or {},
                    cookies=item.get("cookies") or {},
                    body=item.get("body"),
                    params=item.get("params") or {},
                    auth_context=item.get("auth_context", ""),
                )
            )
        return templates

    def record_request(
        self,
        method: str,
        url: str,
        session: requests.Session,
        auth_context: str,
        *,
        params: Optional[Dict[str, str]] = None,
        data: Optional[object] = None,
        json_body: Optional[object] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> requests.Response:
        resp = session.request(
            method=method,
            url=url,
            params=params,
            data=data,
            json=json_body,
            headers=headers,
            allow_redirects=True,
            timeout=20,
        )
        body_str: Optional[str] = None
        if isinstance(data, str):
            body_str = data
        elif data is not None:
            body_str = str(data)
        if json_body is not None:
            try:
                body_str = json.dumps(json_body)
            except Exception:
                body_str = str(json_body)

        tpl = RequestTemplate(
            method=method.upper(),
            url=url,
            headers={**(session.headers or {}), **(headers or {})},
            cookies=dict(session.cookies.get_dict()),
            body=body_str,
            params={k: str(v) for k, v in (params or {}).items()},
            auth_context=auth_context,
        )
        self.templates.append(tpl)
        self._save()
        self.log(f"[Recorder] Captured {method.upper()} {url} ({auth_context}) -> {resp.status_code}")
        return resp

    def _save(self) -> None:
        serializable = []
        for tpl in self.templates:
            serializable.append(asdict(tpl))
        self.store_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")

    @staticmethod
    def load_templates(path: str | Path) -> List[RequestTemplate]:
        return RequestRecorder(path)._load_existing()
