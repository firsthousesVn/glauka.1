from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


DEFAULT_CONFIG: Dict[str, Any] = {
    "modules": {
        "subdomains": {"enabled": True},
        "base_ports": {"enabled": True, "ports": [21, 22, 25, 53, 80, 110, 143, 443, 3306, 5432, 6379, 8080, 8443]},
        "web_services": {"enabled": True},
        "endpoint_collector": {"enabled": True, "limit": 500},
        "web_probe": {"enabled": True},
        "nuclei": {
            "enabled": True,
            "severity": "low,medium,high,critical",
            "templates": [],
            "tags": "sqli,xss,lfi,rce,takeover",
            "exclude_tags": "ssl,tls,info,tech",
            "disable_etags": False,
            "update_templates": True,
            "concurrency": None,
            "rate_limit": None,
        },
        "lfi_scanner": {"enabled": True},
        "sqli_scanner": {"enabled": True},
        "redirect_tester": {"enabled": True},
        "screenshotter": {"enabled": False, "output_dir": "screenshots"},
    },
    "logging": {"verbose": False, "event_path": "reports/live_events.jsonl"},
    "concurrency": {"max_connections": 200},
    "http": {
        "proxies": {},
        "headers": {},
        "debug": False,
        "timeout": 20,
        "retries": 3,
        "backoff_factor": 0.6,
        "jitter": 0.3,
        "throttle_on_429": True,
    },
    "state": {"path": ".recon-state.json.gz"},
    "safety": {"allow_internal": False},
}


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    path = Path(config_path) if config_path else Path("config.yaml")
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return merge_dicts(DEFAULT_CONFIG, data)
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = json.loads(json.dumps(base))
    for key, value in override.items():
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result
