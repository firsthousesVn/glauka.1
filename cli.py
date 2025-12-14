from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

try:
    from rich.console import Console
except Exception:
    Console = None  # type: ignore

from glauka.config import load_config, merge_dicts
from glauka.core.idor_scanner import IDORScanner
from glauka.core.login_manager import LoginManager
from glauka.core.recon import run_full_recon
from glauka.core.request_recorder import RequestRecorder
from glauka.presentation.exporter import (
    export_csv,
    export_html,
    export_json,
    export_markdown,
    export_webhook,
    render_cli_summary,
)


def _printer() -> callable:
    console = Console() if Console else None

    def _print(msg: str):
        if console:
            console.print(msg, style="cyan")
        else:
            print(msg)

    return _print


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Glauka CLI")
    subparsers = parser.add_subparsers(dest="command")

    recon = subparsers.add_parser("recon", help="Run full recon (default)")
    recon.add_argument("target", help="Target domain/IP/URL")
    recon.add_argument("--mode", default="passive", choices=["passive", "hybrid", "active"])
    recon.add_argument("--config", help="Path to config.yaml")
    recon.add_argument("--severity", help="Override nuclei severity (comma-separated)")
    recon.add_argument("--max-concurrent", type=int, help="Max concurrent connections for port scan")
    recon.add_argument("--threads", type=int, help="Alias for --max-concurrent")
    recon.add_argument("--output", help="Output file path")
    recon.add_argument("--format", default="json", choices=["json", "csv", "md", "html", "cli"], help="Export format")
    recon.add_argument("--resume", action="store_true", help="Resume from saved state")
    recon.add_argument("--auth", help="Basic auth in user:pass format")
    recon.add_argument("--webhook", help="Webhook URL to push JSON findings to external dashboards")

    login = subparsers.add_parser("login", help="Authenticate users from YAML config")
    login.add_argument("--config", required=True, help="Path to logins.yaml")

    crawl = subparsers.add_parser("crawl", help="Record requests for a user into templates store")
    crawl.add_argument("--config", required=True, help="Path to logins.yaml")
    crawl.add_argument("--auth", required=True, help="User name from login config")
    crawl.add_argument("--urls", nargs="+", required=True, help="URLs to fetch and record")
    crawl.add_argument("--method", default="GET", help="HTTP method to use")
    crawl.add_argument("--store", default="reports/request_templates.json", help="Template store path")

    scan = subparsers.add_parser("scan-idor", help="Replay recorded requests to detect IDOR")
    scan.add_argument("--config", required=True, help="Path to logins.yaml")
    scan.add_argument("--templates", default="reports/request_templates.json", help="Recorded templates path")
    scan.add_argument("--against", required=True, help="User to replay as (different user)")
    scan.add_argument("--output", default="reports/idor_results.json", help="Path to write IDOR findings")

    return parser


def _handle_recon(args) -> None:
    _print = _printer()
    config = load_config(args.config)
    overrides = {}
    if getattr(args, "severity", None):
        overrides.setdefault("modules", {}).setdefault("nuclei", {})["severity"] = args.severity
    max_conn = (getattr(args, "max_concurrent", None) or getattr(args, "threads", None))
    if max_conn:
        overrides.setdefault("concurrency", {})["max_connections"] = max_conn

    if getattr(args, "auth", None) and ":" in args.auth:
        user, pwd = args.auth.split(":", 1)
        overrides.setdefault("http", {})["headers"] = {}
        overrides.setdefault("auth", {})["basic"] = {"username": user, "password": pwd}

    if overrides:
        config = merge_dicts(config, overrides)

    _print(f"[+] Starting recon for {args.target} ({args.mode})")
    result = asyncio.run(
        run_full_recon(args.target, mode=args.mode, config_overrides=config, resume=args.resume)
    )

    if getattr(args, "webhook", None):
        try:
            export_webhook(result, args.webhook)
            _print(f"[+] Exported to webhook {args.webhook}")
        except Exception as exc:
            _print(f"[!] Webhook export failed: {exc}")

    if getattr(args, "output", None):
        out_path = Path(args.output)
        if args.format == "json":
            export_json(result, out_path)
        elif args.format == "csv":
            export_csv(result, out_path)
        elif args.format == "md":
            export_markdown(result, out_path)
        elif args.format == "html":
            export_html(result, out_path)
        else:
            out_path.write_text(render_cli_summary(result, args.target), encoding="utf-8")
        _print(f"[+] Exported results to {out_path}")
    else:
        export_json(result, Path("glauka_results.json"))
        _print("[+] Results saved to glauka_results.json")
        _print(render_cli_summary(result, args.target))


def _handle_login(args) -> None:
    _print = _printer()
    manager = LoginManager(args.config, log=_print)
    contexts = manager.login_all()
    _print(f"[+] Authenticated {len(contexts)} users")


def _handle_crawl(args) -> None:
    _print = _printer()
    manager = LoginManager(args.config, log=_print)
    ctx = manager.login_user(args.auth)
    recorder = RequestRecorder(args.store, log=_print)
    for url in args.urls:
        try:
            recorder.record_request(args.method.upper(), url, ctx.session, ctx.name)
        except Exception as exc:
            _print(f"[!] Failed to record {url}: {exc}")
    _print(f"[+] Recorded {len(recorder.templates)} templates to {recorder.store_path}")


def _handle_scan_idor(args) -> None:
    _print = _printer()
    manager = LoginManager(args.config, log=_print)
    contexts = manager.login_all()
    scanner = IDORScanner(args.templates, log=_print)
    results = scanner.scan(contexts, against_user=args.against, output_path=args.output)
    _print(f"[+] IDOR findings: {len(results)} (saved to {args.output})")


def main():
    raw_args = sys.argv[1:]
    commands = {"recon", "login", "crawl", "scan-idor"}
    if raw_args and raw_args[0] not in commands:
        raw_args = ["recon"] + raw_args
    parser = _build_parser()
    args = parser.parse_args(raw_args)

    if args.command in (None, "recon"):
        _handle_recon(args)
    elif args.command == "login":
        _handle_login(args)
    elif args.command == "crawl":
        _handle_crawl(args)
    elif args.command == "scan-idor":
        _handle_scan_idor(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
