from __future__ import annotations

import math
import random
import tkinter as tk
from typing import Callable


class WaveformCanvas(tk.Canvas):
    """Scrolling sine wave bar."""

    def __init__(self, parent, color: str = "#FF9900", bg: str = "#000000", **kwargs):
        super().__init__(parent, bg=bg, highlightthickness=0, **kwargs)
        self.color = color
        self.offset = 0
        self.running = False
        self.after_id = None

    def start(self):
        self.running = True
        self._tick()

    def stop(self):
        self.running = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.delete("all")

    def _tick(self):
        if not self.running:
            return
        self.delete("wave")
        w = self.winfo_width() or 600
        h = self.winfo_height() or 40
        amp = 10
        mid = h // 2
        for x in range(w):
            y = int(amp * math.sin((x + self.offset) / 8.0))
            self.create_line(x, mid + y, x + 1, mid + y + 1, fill=self.color, tags="wave")
        self.offset += 4
        self.after_id = self.after(60, self._tick)


class PulseOverlay(tk.Canvas):
    """Expanding pulse overlay for scan trigger."""

    def __init__(self, parent, color: str = "#FFB347", bg: str = "#000000", **kwargs):
        super().__init__(parent, bg=bg or "#000000", highlightthickness=0, **kwargs)
        self.color = color

    def pulse(self, duration: int = 900):
        self.delete("all")
        w = self.winfo_width() or 800
        h = self.winfo_height() or 600
        max_r = int((w + h) / 2)
        steps = max(6, duration // 30)
        self._expand(0, max_r, steps)

    def _expand(self, step: int, max_r: int, steps: int):
        self.delete("pulse")
        w = self.winfo_width() or 800
        h = self.winfo_height() or 600
        r = int(max_r * (step / steps))
        alpha = max(0, 1 - (step / steps))
        color = self._fade(self.color, alpha)
        self.create_oval(
            w // 2 - r,
            h // 2 - r,
            w // 2 + r,
            h // 2 + r,
            outline=color,
            width=2,
            tags="pulse",
        )
        if step < steps:
            self.after(30, lambda: self._expand(step + 1, max_r, steps))
        else:
            self.delete("pulse")

    def _fade(self, hex_color: str, alpha: float) -> str:
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = int(r * alpha)
        g = int(g * alpha)
        b = int(b * alpha)
        return f"#{r:02x}{g:02x}{b:02x}"


def corrupt_text(text: str) -> str:
    corrupt_map = {"E": "Ξ", "A": "∆", "O": "Φ", "T": "⊥", "S": "5", "I": "¡"}
    return "".join(corrupt_map.get(c, c) for c in text.upper())
