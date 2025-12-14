"""
Glauka Terminal UI - solar geometric themed TUI with literal labels.
"""

from __future__ import annotations

import os
import select
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional, Tuple

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from glauka.presentation.formatter import format_all_panels
from glauka.ui.scan_runner import run_scan_async

console = Console()


def _msvcrt_getch() -> Optional[str]:
    try:
        import msvcrt

        if msvcrt.kbhit():
            return msvcrt.getwch()
    except Exception:
        return None
    return None


def _stdin_getch() -> Optional[str]:
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        readable, _, _ = select.select([sys.stdin], [], [], 0.05)
        if readable:
            ch = sys.stdin.read(1)
            return ch
    except Exception:
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return None


def _getch() -> Optional[str]:
    if os.name == "nt":
        return _msvcrt_getch()
    return _stdin_getch()


@dataclass
class TUIState:
    target: str = "localhost"
    mode: str = "passive"
    scanning: bool = False
    orb_phase: int = 0
    logs: Deque[str] = field(default_factory=lambda: deque(maxlen=120))
    modules: Dict[str, Tuple[str, bool]] = field(
        default_factory=lambda: {
            "1": ("Subdomains", True),
            "2": ("Ports", True),
            "3": ("LFI", True),
            "4": ("SQLi", True),
            "5": ("Redirect", True),
            "6": ("Screenshots", False),
        }
    )
    status: str = "idle"


class GlaukaTUI:
    def __init__(self, target: Optional[str] = None):
        self.state = TUIState(target=target or "localhost")
        self._stop = threading.Event()

    # ---- life-cycle -------------------------------------------------
    def start(self) -> None:
        with Live(self._render(), console=console, refresh_per_second=10) as live:
            self._live = live
            threading.Thread(target=self._animate_loop, daemon=True).start()
            threading.Thread(target=self._input_loop, daemon=True).start()
            while not self._stop.is_set():
                time.sleep(0.1)

    # ---- interaction ------------------------------------------------
    def _input_loop(self) -> None:
        while not self._stop.is_set():
            ch = _getch()
            if not ch:
                continue
            if ch.lower() == "q":
                self._stop.set()
            elif ch.lower() in {"s", " "}:
                self._start_scan()
            elif ch.lower() == "m":
                self._rotate_mode()
            elif ch.lower() == "t":
                self.state.target = self._prompt_target(self.state.target)
            elif ch in self.state.modules:
                name, active = self.state.modules[ch]
                self.state.modules[ch] = (name, not active)
            if hasattr(self, "_live"):
                self._live.update(self._render())

    def _prompt_target(self, current: str) -> str:
        console.show_cursor(True)
        console.print("\nTarget: ", end="", style="yellow")
        try:
            new_value = input().strip() or current
        except EOFError:
            new_value = current
        console.show_cursor(False)
        return new_value

    def _rotate_mode(self) -> None:
        order = ["passive", "hybrid", "active"]
        idx = order.index(self.state.mode)
        self.state.mode = order[(idx + 1) % len(order)]
        self.state.status = f"mode: {self.state.mode}"

    # ---- animation --------------------------------------------------
    def _animate_loop(self) -> None:
        while not self._stop.is_set():
            self.state.orb_phase = (self.state.orb_phase + 1) % 4
            if hasattr(self, "_live"):
                self._live.update(self._render())
            time.sleep(0.35 if not self.state.scanning else 0.18)

    # ---- scanning ---------------------------------------------------
    def _start_scan(self) -> None:
        if self.state.scanning:
            self.state.status = "scan already running"
            return
        self.state.scanning = True
        self.state.status = f"scanning {self.state.target}"
        self.state.logs.append(f"[gold1]SCAN[/] {self.state.target}")

        def log_cb(msg: str) -> None:
            self.state.logs.append(f"[grey85]{msg}[/]")

        def on_result(res):
            def finish():
                self.state.scanning = False
                if res is None:
                    self.state.status = "scan failed"
                    self.state.logs.append("[red]FAIL[/] scan halted")
                    return
                formatted = format_all_panels(res, self.state.target)
                self.state.status = "scan complete"
                self._apply_formatted(formatted)
            finish()

        run_scan_async(
            self.state.target,
            self.state.mode,
            on_result=on_result,
            on_log=log_cb,
        )

    def _apply_formatted(self, formatted: Dict[str, str]) -> None:
        subs = formatted.get("subdomains", "")
        if subs:
            for line in subs.splitlines():
                if line.strip():
                    self.state.logs.append(f"[gold1]SUB[/] {line.strip()}")
        signal = formatted.get("signal", "")
        if signal:
            self.state.logs.append(f"[gold1]SIG[/] {signal[:180]}")

    # ---- render -----------------------------------------------------
    def _render(self):
        layout = Layout()
        layout.split_column(
            Layout(name="top", size=3),
            Layout(name="middle", ratio=1),
            Layout(name="bottom", size=10),
        )
        layout["middle"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1),
        )

        layout["top"].update(self._render_title())
        layout["left"].update(self._render_left())
        layout["right"].update(self._render_right())
        layout["bottom"].update(self._render_log())

        return layout

    def _render_title(self) -> Panel:
        orb = ["◐", "◓", "◑", "◒"][self.state.orb_phase]
        title = Text.assemble(
            (" GLAUKA ", "bold gold1"),
            (" | Terminal Scanner ", "grey78"),
            (" ",),
            (orb, "gold1"),
        )
        return Panel(title, border_style="grey35", padding=(0, 1))

    def _render_left(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="left")
        grid.add_row(Text(f"Target: {self.state.target}", style="bold gold1"))
        grid.add_row(Text(f"Mode:   {self.state.mode}", style="grey78"))
        grid.add_row("")
        grid.add_row(Text("Modules (1-6 to toggle)", style="grey70"))

        for key, (name, active) in self.state.modules.items():
            marker = "◉" if active else "○"
            style = "gold1" if active else "grey50"
            grid.add_row(Text.from_markup(f"[{style}]{key}:{marker}[/] {name}"))

        # geometric frame (solar ring)
        ring = Text("◯ " * 16, style="gold1", justify="center")
        grid.add_row("")
        grid.add_row(ring)
        return Panel(grid, title="Target & Modules", border_style="grey35")

    def _render_right(self) -> Panel:
        orb = ["◐", "◓", "◑", "◒"][self.state.orb_phase]
        phase_bar = Text.from_markup(f"[gold1]{orb}[/] status: {self.state.status}")
        mode_bar = Text.from_markup(f"[grey78]mode[/]: [gold1]{self.state.mode}[/]")

        spiral = self._solar_spiral()
        group = Group(phase_bar, mode_bar, spiral)
        return Panel(group, title="Status", border_style="gold1")

    def _solar_spiral(self) -> Text:
        # structured, rhythmic radial motif
        rings = [
            "    ◐───◯───◐    ",
            "  ◯───────────◯  ",
            " ◐─────────────◐ ",
            "  ◯───────────◯  ",
            "    ◐───◯───◐    ",
        ]
        style = "gold1" if self.state.scanning else "grey50"
        return Text("\n".join(rings), style=style, justify="center")

    def _render_log(self) -> Panel:
        lines = list(self.state.logs)[-8:]
        if not lines:
            lines = ["waiting for scan output"]
        body = Text.from_markup("\n".join(lines), justify="left")
        return Panel(body, title="Output Log", border_style="grey35")


def run():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    tui = GlaukaTUI(target=target)
    try:
        console.clear()
        console.show_cursor(False)
        tui.start()
    finally:
        console.show_cursor(True)


if __name__ == "__main__":
    run()
