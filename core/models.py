from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any, Set
import json
import time


@dataclass
class ScopeInfo:
    host: str
    ip: str
    url: str
    mode: str


@dataclass
class ReconResult:
    scope: ScopeInfo
    subdomains: List[str] = field(default_factory=list)
    base_ports: Dict[int, str] = field(default_factory=dict)
    web_ports: Dict[str, List[int]] = field(default_factory=dict)
    nuclei_raw: str = ""
    nuclei_urls: List[str] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)
    timings: Dict[str, float] = field(default_factory=dict)


@dataclass
class ReconContext:
    scope: ScopeInfo
    config: Dict[str, object]
    log: Callable[[str], None]
    http_client: Optional[object] = None
    session_manager: Optional[object] = None
    findings: List[str] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    state_path: Optional[str] = None
    subdomains: List[str] = field(default_factory=list)
    base_ports: Dict[int, str] = field(default_factory=dict)
    web_ports: Dict[str, List[int]] = field(default_factory=dict)
    nuclei_raw: str = ""
    nuclei_urls: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)
    timings: Dict[str, float] = field(default_factory=dict)
    progress_cb: Optional[Callable[[str, str], None]] = None
    _progress_seen: Dict[str, Set[str]] = field(default_factory=dict)
    verbose_logs: bool = False
    event_path: Optional[str] = None

    def emit(self, category: str, value: str) -> None:
        """
        Push incremental discoveries to the UI while de-duplicating per category.
        """
        if not category or not value:
            return
        cat = category.lower().strip()
        seen = self._progress_seen.setdefault(cat, set())
        if value in seen:
            return
        seen.add(value)
        # Write to event sink if configured
        if self.event_path:
            try:
                path = Path(self.event_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "ts": time.time(),
                    "category": cat,
                    "value": value,
                }
                with path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(payload) + "\n")
            except Exception:
                pass
        if self.progress_cb:
            try:
                self.progress_cb(cat, value)
            except Exception:
                pass
