"""
Alien CRT / ritual HUD theming helpers.
Provides scanline overlays, animated borders, and glyph pulses.
"""

from __future__ import annotations

import math
import random
import tkinter as tk
from dataclasses import dataclass
from typing import Tuple


# Core palette
BG = "#050505"
FG = "#FFA533"
ACCENT1 = "#FF6600"
ACCENT2 = "#FFC266"
DIM = "#4A2A0A"

FONT_PRIMARY = ("Share Tech Mono", 11)
FONT_SYMBOL = ("Share Tech Mono", 16, "bold")
FONT_TINY = ("Share Tech Mono", 9)


@dataclass
class AnimatedGlyph:
    symbol: str
    alt_symbols: Tuple[str, ...] = ()
    angle: float = 0.0
    pulse: float = 1.0


class ScanlineOverlay(tk.Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG, highlightthickness=0, **kwargs)
        self.lines = []
        self._animate()

    def _animate(self):
        try:
            self.delete("all")
            w, h = self.winfo_width(), self.winfo_height()
            if w <= 2 or h <= 2:
                self.after(60, self._animate)
                return
            for y in range(0, h, 4):
                color = "#0A0A0A" if (y // 4) % 2 == 0 else "#0F0F0F"
                self.create_line(0, y, w, y, fill=color)
            self.after(80, self._animate)
        except Exception:
            pass


class PulsingFrame(tk.Frame):
    """Frame with animated border glows and corner sigils."""

    def __init__(self, parent, title: str = "", symbol: str = "", **kwargs):
        super().__init__(parent, bg=BG, **kwargs)
        self.symbol = AnimatedGlyph(symbol, alt_symbols=(symbol, "⚚", "✶"))
        self.title = title
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._redraw())
        self._tick()

    def _redraw(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        margin = 6
        # frame rectangle
        self.canvas.create_rectangle(
            margin,
            margin,
            w - margin,
            h - margin,
            outline=ACCENT1,
            width=2,
        )
        # corner sigils
        for (x, y) in [
            (margin + 8, margin + 8),
            (w - margin - 8, margin + 8),
            (margin + 8, h - margin - 8),
            (w - margin - 8, h - margin - 8),
        ]:
            self._draw_triangle(x, y, size=10, angle=self.symbol.angle)
        # title and symbol
        if self.title:
            self.canvas.create_text(
                w // 2,
                margin + 4,
                text=self.title,
                fill=FG,
                font=FONT_PRIMARY,
            )
        if self.symbol.symbol:
            self.canvas.create_text(
                margin + 14,
                margin + 4,
                text=self.symbol.symbol,
                fill=ACCENT2,
                font=FONT_SYMBOL,
                anchor="w",
            )

    def _draw_triangle(self, cx: int, cy: int, size: int, angle: float):
        pts = []
        for i in range(3):
            ang = angle + i * (2 * math.pi / 3)
            pts.append((cx + size * math.cos(ang), cy + size * math.sin(ang)))
        self.canvas.create_polygon(
            pts, outline=ACCENT2, fill="", width=1.5
        )

    def _tick(self):
        try:
            self.symbol.angle += 0.12
            # pulse color
            if random.random() > 0.7 and self.symbol.alt_symbols:
                self.symbol.symbol = random.choice(self.symbol.alt_symbols)
            self._redraw()
        except Exception:
            pass
        self.after(180, self._tick)
