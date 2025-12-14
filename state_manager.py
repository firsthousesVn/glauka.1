from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Dict, List

try:
    from pydantic import BaseModel, ValidationError  # type: ignore
    _HAS_PYDANTIC = True
except Exception:  # pragma: no cover - optional dependency fallback
    BaseModel = None  # type: ignore
    ValidationError = Exception  # type: ignore
    _HAS_PYDANTIC = False

from glauka.core.models import ReconContext, ReconResult


if _HAS_PYDANTIC:
    class ScopeState(BaseModel):  # type: ignore[misc]
        host: str = ""
        ip: str = ""
        url: str = ""
        mode: str = "passive"

        class Config:
            extra = "ignore"
else:
    class ScopeState:  # minimal fallback
        def __init__(self, host: str = "", ip: str = "", url: str = "", mode: str = "passive", **_: Any) -> None:
            self.host = host
            self.ip = ip
            self.url = url
            self.mode = mode


if _HAS_PYDANTIC:
    class ReconStateModel(BaseModel):  # type: ignore[misc]
        scope: ScopeState
        config: Dict[str, Any] = {}
        subdomains: List[str] = []
        base_ports: Dict[int, str] = {}
        web_ports: Dict[str, List[int]] = {}
        nuclei_raw: str = ""
        nuclei_urls: List[str] = []
        findings: List[str] = []
        screenshots: List[str] = []
        extra: Dict[str, Any] = {}
        timings: Dict[str, float] = {}

        class Config:
            extra = "ignore"


def _model_to_dict(model: BaseModel) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[attr-defined]
    if hasattr(model, "dict"):
        return model.dict()  # type: ignore[call-arg]
    return dict(model)  # type: ignore[arg-type]


def save_state(ctx: ReconContext, path: str | Path = ".recon-state.json.gz") -> Path:
    p = Path(path)
    state = {
        "scope": ctx.scope.__dict__,
        "config": ctx.config,
        "subdomains": ctx.subdomains,
        "base_ports": ctx.base_ports,
        "web_ports": ctx.web_ports,
        "nuclei_raw": ctx.nuclei_raw,
        "nuclei_urls": ctx.nuclei_urls,
        "findings": ctx.findings,
        "screenshots": ctx.screenshots,
        "extra": ctx.extra,
        "timings": ctx.timings,
    }
    payload = json.dumps(state, indent=2)
    compressed = gzip.compress(payload.encode("utf-8"))
    p.write_bytes(compressed)
    return p


def load_state(path: str | Path = ".recon-state.json.gz") -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        raw = p.read_bytes()
    except Exception:
        return {}

    text: str | None = None
    try:
        text = gzip.decompress(raw).decode("utf-8")
    except Exception:
        try:
            text = raw.decode("utf-8")
        except Exception:
            return {}

    try:
        data = json.loads(text)
    except Exception:
        return {}

    if _HAS_PYDANTIC:
        try:
            validated = ReconStateModel(**data)  # type: ignore[arg-type]
            return _model_to_dict(validated)
        except ValidationError:
            return {}
    return data if isinstance(data, dict) else {}


def to_result(ctx: ReconContext) -> ReconResult:
    return ReconResult(
        scope=ctx.scope,
        subdomains=ctx.subdomains,
        base_ports=ctx.base_ports,
        web_ports=ctx.web_ports,
        nuclei_raw=ctx.nuclei_raw,
        nuclei_urls=ctx.nuclei_urls,
        findings=ctx.findings,
        screenshots=ctx.screenshots,
        extra=ctx.extra,
        timings=ctx.timings,
    )
