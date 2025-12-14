from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import requests


@dataclass
class HttpRequest:
    method: str
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    data: Optional[Any] = None
    json: Optional[Any] = None
    auth: Optional[tuple[str, str]] = None
    cookies: Optional[Dict[str, str]] = None
    proxies: Optional[Dict[str, str]] = None
    verify: bool = True
    timeout: Optional[float] = None
    max_retries: Optional[int] = None
    backoff_factor: Optional[float] = None
    jitter: Optional[float] = None


@dataclass
class HttpResponse:
    status_code: int
    headers: Dict[str, str]
    text: str
    url: str


class HttpClient:
    """
    HTTP wrapper around requests.Session with logging, proxy, auth, and cookie support.
    Adds async entrypoints, retries with jitter, and 429 throttling.
    """

    def __init__(
        self,
        log_cb=None,
        proxies: Optional[Dict[str, str]] = None,
        default_headers: Optional[Dict[str, str]] = None,
        debug: bool = False,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        jitter: float = 0.2,
        default_timeout: float = 20.0,
        throttle_on_429: bool = True,
    ):
        self.session = requests.Session()
        self.log_cb = log_cb
        self.proxies = proxies or {}
        self.default_headers = default_headers or {}
        self.debug = debug
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.default_timeout = default_timeout
        self.throttle_on_429 = throttle_on_429

    def _log(self, message: str) -> None:
        if self.log_cb:
            try:
                self.log_cb(message)
            except Exception:
                pass

    async def request(self, req: HttpRequest) -> HttpResponse:
        attempts = max(1, req.max_retries or self.max_retries)
        backoff = req.backoff_factor if req.backoff_factor is not None else self.backoff_factor
        jitter = req.jitter if req.jitter is not None else self.jitter
        timeout = req.timeout if req.timeout is not None else self.default_timeout

        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                resp = await asyncio.to_thread(self._send_once, req, timeout)
                if resp.status_code >= 500 and attempt < attempts:
                    delay = self._compute_backoff(attempt, backoff, jitter)
                    self._log(f"[HTTP] {resp.status_code} server error; retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)
                    continue
                if resp.status_code == 429 and self.throttle_on_429:
                    delay = self._retry_after_delay(resp.headers, attempt, backoff, jitter)
                    self._log(f"[HTTP] 429 Too Many Requests; backing off {delay:.2f}s")
                    await asyncio.sleep(delay)
                    continue
                return resp
            except Exception as exc:
                last_exc = exc
                self._log(f"[HTTP] Attempt {attempt} failed: {exc}")

            if attempt < attempts:
                delay = self._compute_backoff(attempt, backoff, jitter)
                self._log(f"[HTTP] Retrying in {delay:.2f}s (attempt {attempt + 1}/{attempts})")
                await asyncio.sleep(delay)

        if last_exc:
            raise last_exc
        raise RuntimeError("HTTP request failed with no response")

    def _compute_backoff(self, attempt: int, backoff_factor: float, jitter: float) -> float:
        base = backoff_factor * (2 ** (attempt - 1))
        return base + random.uniform(0, max(0.0, jitter))

    def _retry_after_delay(self, headers: Dict[str, str], attempt: int, backoff_factor: float, jitter: float) -> float:
        retry_after = headers.get("Retry-After") if headers else None
        if retry_after:
            try:
                return max(float(retry_after), 0.1)
            except Exception:
                pass
        return self._compute_backoff(attempt, backoff_factor, jitter)

    def _send_once(self, req: HttpRequest, timeout: float) -> HttpResponse:
        headers = {**self.default_headers, **(req.headers or {})}
        self._log(f"[HTTP] {req.method.upper()} {req.url}")
        if self.debug:
            self._log(f"[HTTP] Headers: {headers}")
            if req.params:
                self._log(f"[HTTP] Params: {req.params}")
            if req.data:
                self._log(f"[HTTP] Data: {req.data}")
            if req.json is not None:
                self._log(f"[HTTP] JSON: {req.json}")
        start = time.perf_counter()
        resp = self.session.request(
            method=req.method,
            url=req.url,
            headers=headers or None,
            params=req.params or None,
            data=req.data,
            json=req.json,
            auth=req.auth,
            cookies=req.cookies,
            proxies=req.proxies or self.proxies or None,
            timeout=timeout,
            verify=req.verify,
            allow_redirects=True,
        )
        elapsed = time.perf_counter() - start
        if self.debug:
            self._log(f"[HTTP] <- {resp.status_code} {resp.reason} in {elapsed:.2f}s")
            self._log(f"[HTTP] Resp headers: {dict(resp.headers)}")
            preview = resp.text[:500].replace("\n", "\\n")
            self._log(f"[HTTP] Resp body (trunc): {preview}")
        else:
            self._log(f"[HTTP] -> {resp.status_code} ({len(resp.text)} bytes) in {elapsed:.2f}s")

        return HttpResponse(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            text=resp.text,
            url=resp.url,
        )

    async def get(self, url: str, **kwargs) -> HttpResponse:
        return await self.request(HttpRequest(method="GET", url=url, **kwargs))

    async def post(self, url: str, **kwargs) -> HttpResponse:
        return await self.request(HttpRequest(method="POST", url=url, **kwargs))

    async def put(self, url: str, **kwargs) -> HttpResponse:
        return await self.request(HttpRequest(method="PUT", url=url, **kwargs))

    async def delete(self, url: str, **kwargs) -> HttpResponse:
        return await self.request(HttpRequest(method="DELETE", url=url, **kwargs))
