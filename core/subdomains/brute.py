from __future__ import annotations

import socket
from pathlib import Path
from typing import Callable

import requests


DEFAULT_WORDLIST_URL = (
    "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/DNS/"
    "subdomains-top1million-110000.txt"
)


def _ensure_wordlist(wordlist_path: Path, log: Callable[[str], None]) -> bool:
    """
    Download a sane default subdomain wordlist if the expected file is missing.
    """
    if wordlist_path.exists():
        return True

    log(f"[Brute] {wordlist_path} not found; downloading default SecLists wordlist...")
    wordlist_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        resp = requests.get(DEFAULT_WORDLIST_URL, timeout=20)
        resp.raise_for_status()
        wordlist_path.write_text(resp.text, encoding="utf-8")
        line_count = resp.text.count("\n")
        log(f"[Brute] Downloaded {line_count} entries to {wordlist_path}")
        return True
    except Exception as exc:
        log(f"[Brute] Failed to download default wordlist: {exc}")
        return False


def brute_dns(domain: str, log: Callable[[str], None], on_found: Callable[[str], None] | None = None) -> set[str]:
    """
    Optional brute-force DNS using a local wordlist at wordlists/subdomains.txt.
    """
    wordlist_path = Path("wordlists/subdomains.txt")
    if not _ensure_wordlist(wordlist_path, log):
        log("[Brute] Unable to obtain wordlist; skipping brute-force.")
        return set()

    found: set[str] = set()
    log(f"[Brute] DNS brute-force using {wordlist_path}...")
    try:
        with wordlist_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                name = line.strip()
                if not name or name.startswith("#"):
                    continue
                sub = f"{name}.{domain}"
                try:
                    socket.gethostbyname(sub)
                    sub_l = sub.lower()
                    if sub_l not in found:
                        found.add(sub_l)
                        if on_found:
                            on_found(sub_l)
                except OSError:
                    continue
    except Exception as e:
        log(f"[Brute] Error: {e}")

    log(f"[Brute] Found: {len(found)}")
    return found
