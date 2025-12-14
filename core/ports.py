from __future__ import annotations

import asyncio
import socket
from typing import Callable, Dict, List, Tuple

COMMON_TCP_PORTS = [
    21,
    22,
    23,
    25,
    53,
    80,
    81,
    110,
    111,
    135,
    139,
    143,
    300,
    443,
    445,
    591,
    593,
    832,
    981,
    1099,
    1118,
    2082,
    2083,
    2087,
    2095,
    2096,
    3000,
    3128,
    3306,
    3389,
    4243,
    4567,
    4711,
    4712,
    5000,
    5104,
    5432,
    5800,
    5900,
    6379,
    7000,
    7001,
    8000,
    8001,
    8008,
    8080,
    8081,
    8181,
    8443,
    8888,
    9200,
    9443,
    9000,
    9090,
    10000,
]

# Focused set for web service discovery
COMMON_WEB_PORTS = [80, 443, 8080, 8443]


def _noop_log(_: str) -> None:
    return


# --- TCP quick scan (kept for backward compatibility) -----------------

def scan_tcp_port(host: str, port: int, timeout: float = 0.7) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


async def _scan_single(
    ip: str,
    port: int,
    log: Callable[[str], None],
    semaphore: asyncio.Semaphore,
    on_found: Callable[[int, str], None] | None = None,
    verbose: bool = False,
) -> Tuple[int, str] | None:
    service_map = {
        21: "ftp",
        22: "ssh",
        25: "smtp",
        53: "dns",
        80: "http",
        110: "pop3",
        143: "imap",
        443: "https",
        3306: "mysql",
        5432: "postgresql",
        6379: "redis",
        8080: "http-alt",
        8443: "https-alt",
    }
    async with semaphore:
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=1.0)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            service = service_map.get(port, "unknown")
            if verbose:
                log(f"[Ports] {ip}:{port} open ({service})")
            if on_found:
                on_found(port, service)
            return port, service
        except Exception:
            return None


async def quick_port_scan_async(
    ip: str,
    ports: List[int],
    log: Callable[[str], None],
    max_concurrent: int = 200,
    on_found: Callable[[int, str], None] | None = None,
    verbose: bool = False,
) -> Dict[int, str]:
    open_ports: Dict[int, str] = {}
    semaphore = asyncio.Semaphore(max(1, max_concurrent))
    log(f"[Ports] Quick scan on {ip} ({len(ports)} ports, max {max_concurrent} concurrent)...")
    tasks = [_scan_single(ip, port, log, semaphore, on_found, verbose) for port in ports]
    for result in await asyncio.gather(*tasks):
        if result:
            port, service = result
            open_ports[port] = service
    return open_ports


def async_quick_port_scan(ip: str, ports: List[int], log: Callable[[str], None] | None = None, max_concurrent: int = 200) -> Dict[int, str]:
    log = log or _noop_log
    try:
        return asyncio.run(quick_port_scan_async(ip, ports, log, max_concurrent))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(quick_port_scan_async(ip, ports, log, max_concurrent))
        finally:
            loop.close()
    except Exception:
        return {}


# --- High-performance web port scanner (async) ------------------------

async def check_port(host: str, port: int, timeout: float = 1.0) -> int | None:
    try:
        conn = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(conn, timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return port
    except Exception:
        return None


async def scan_host_async(host: str, ports: List[int], semaphore: asyncio.Semaphore) -> Tuple[str, List[int]]:
    async with semaphore:
        tasks = [check_port(host, p) for p in ports]
        results = await asyncio.gather(*tasks)
    return host, [p for p in results if p is not None]


async def run_batch_scan(
    subdomains: List[str],
    log: Callable[[str], None],
    on_found: Callable[[str, int], None] | None = None,
) -> Tuple[Dict[str, List[int]], List[str]]:
    port_map: Dict[str, List[int]] = {}
    urls: List[str] = []
    semaphore = asyncio.Semaphore(100)

    log(f"[Web Ports] Async scanning {len(subdomains)} hosts...")

    tasks = [scan_host_async(host, COMMON_WEB_PORTS, semaphore) for host in subdomains]
    results = await asyncio.gather(*tasks)

    for host, open_ports in results:
        if open_ports:
            port_map[host] = sorted(open_ports)
            for port in open_ports:
                scheme = "https" if port in (443, 8443) else "http"
                if port in (80, 443):
                    url = f"{scheme}://{host}"
                else:
                    url = f"{scheme}://{host}:{port}"
                urls.append(url)
                if on_found:
                    on_found(host, port)
    return port_map, urls


def scan_web_services(
    subdomains: List[str],
    log: Callable[[str], None] | None = None,
    on_found: Callable[[str, int], None] | None = None,
) -> Tuple[Dict[str, List[int]], List[str]]:
    log = log or _noop_log
    if not subdomains:
        return {}, []

    try:
        return asyncio.run(run_batch_scan(subdomains, log, on_found))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_batch_scan(subdomains, log, on_found))
        loop.close()
        return result
