from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from glauka.core.login_manager import AuthContext
from glauka.core.request_recorder import RequestTemplate, RequestRecorder


def _noop(_: str) -> None:
    return


@dataclass
class ScanFinding:
    url: str
    original_user: str
    unauth_result: str
    user2_result: str
    tampered_id: str
    response_diff: str
    notes: str


class IDORScanner:
    """
    Replays recorded requests under different auth contexts to surface IDOR/access-control issues.
    """

    KEYWORDS = ["unauthorized", "forbidden", "access denied", "email", "account", "profile", "admin"]

    def __init__(self, templates_path: str | Path = "reports/request_templates.json", log=_noop):
        self.templates_path = Path(templates_path)
        self.log = log or _noop
        self.templates = RequestRecorder.load_templates(self.templates_path)

    def scan(
        self,
        auth_contexts: Dict[str, AuthContext],
        against_user: str,
        output_path: str | Path = "reports/idor_results.json",
    ) -> List[Dict[str, object]]:
        findings: List[Dict[str, object]] = []
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        target_session = auth_contexts.get(against_user)
        if not target_session:
            raise ValueError(f"Auth context '{against_user}' not available.")

        for tpl in self.templates:
            base_ctx = auth_contexts.get(tpl.auth_context)
            if not base_ctx:
                self.log(f"[IDOR] Skipping {tpl.url}: missing auth '{tpl.auth_context}'")
                continue

            baseline = self._send(tpl, base_ctx.session)
            other = self._send(tpl, target_session.session)
            tampered_url, tampered_params, tampered_id = self._tamper_id(tpl.url, tpl.params)
            tampered_tpl = RequestTemplate(
                method=tpl.method,
                url=tampered_url,
                headers=tpl.headers,
                cookies=tpl.cookies,
                body=tpl.body,
                params=tampered_params,
                auth_context=tpl.auth_context,
            )
            tampered_resp = self._send(tampered_tpl, target_session.session)
            unauth_resp = self._send(tpl, requests.Session())

            result = self._evaluate(tpl, baseline, other, tampered_resp, unauth_resp, tampered_id, against_user)
            if result:
                findings.append(result)

        out_path.write_text(json.dumps(findings, indent=2), encoding="utf-8")
        self.log(f"[IDOR] Results written to {out_path} ({len(findings)} findings)")
        return findings

    def _send(self, tpl: RequestTemplate, session: requests.Session) -> requests.Response:
        headers = {**(session.headers or {}), **(tpl.headers or {})}
        cookies = tpl.cookies or {}
        session.cookies.update(cookies)
        data = tpl.body
        params = tpl.params or {}
        resp = session.request(
            method=tpl.method,
            url=tpl.url,
            headers=headers,
            data=data,
            params=params,
            timeout=20,
            allow_redirects=True,
        )
        return resp

    def _tamper_id(self, url: str, params: Dict[str, str]) -> Tuple[str, Dict[str, str], str]:
        tampered_params = dict(params or {})
        tampered_id = ""
        if "id" in tampered_params:
            try:
                val = int(tampered_params["id"])
                tampered_params["id"] = str(val + 1)
                tampered_id = tampered_params["id"]
            except Exception:
                pass

        new_url = url
        match = re.search(r"(\d+)(?!.*\d)", url)
        if match:
            original = match.group(1)
            tampered_id = str(int(original) + 1)
            new_url = url[: match.start(1)] + tampered_id + url[match.end(1) :]

        return new_url, tampered_params, tampered_id

    def _evaluate(
        self,
        tpl: RequestTemplate,
        baseline: requests.Response,
        other: requests.Response,
        tampered_resp: requests.Response,
        unauth_resp: requests.Response,
        tampered_id: str,
        against_user: str,
    ) -> Optional[Dict[str, object]]:
        base_len = len(baseline.text or "")
        other_len = len(other.text or "")
        tampered_len = len(tampered_resp.text or "")
        unauth_len = len(unauth_resp.text or "")

        anomalies: List[str] = []
        if baseline.status_code != other.status_code:
            anomalies.append(f"user swap status {baseline.status_code}->{other.status_code}")
        if abs(base_len - other_len) > 200 and other.status_code == 200:
            anomalies.append(f"content delta vs user: {other_len - base_len}")
        if baseline.status_code in (401, 403) and other.status_code == 200:
            anomalies.append("restricted for original, allowed for other user")
        if abs(base_len - tampered_len) > 200 and tampered_resp.status_code == 200:
            anomalies.append(f"tamper content delta {tampered_len - base_len}")
        if tampered_resp.status_code != baseline.status_code:
            anomalies.append(f"tamper status {baseline.status_code}->{tampered_resp.status_code}")
        if unauth_resp.status_code == 200 and baseline.status_code in (401, 403):
            anomalies.append("unauthenticated access allowed")
        if self._contains_keywords(other.text):
            anomalies.append("keywords in other user response")
        if self._contains_keywords(tampered_resp.text):
            anomalies.append("keywords in tampered response")

        if not anomalies:
            return None

        diff_summary = f"len base={base_len}, other={other_len}, tampered={tampered_len}, unauth={unauth_len}"
        return {
            "url": tpl.url,
            "original_user": tpl.auth_context,
            "unauth_result": str(unauth_resp.status_code),
            "user2_result": str(other.status_code),
            "tampered_id": tampered_id or "",
            "response_diff": diff_summary,
            "notes": "; ".join(anomalies),
            "against_user": against_user,
        }

    def _contains_keywords(self, text: str) -> bool:
        lowered = (text or "").lower()
        return any(kw in lowered for kw in self.KEYWORDS)
