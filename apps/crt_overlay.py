import random
import tkinter as tk


class CRTOverlay(tk.Canvas):
    """Subtle scanlines and shimmer overlay."""

    def __init__(self, parent, opacity: float = 0.08, **kwargs):
        kwargs.setdefault("bg", "#0d0d1a")
        super().__init__(parent, highlightthickness=0, bd=0, **kwargs)
        self.opacity = opacity
        self.scan_spacing = 4
        self.noise_points = []
        self._animate()

    def _animate(self):
        self.delete("all")
        w = max(1, self.winfo_width())
        h = max(1, self.winfo_height())
        # scanlines
        for y in range(0, h, self.scan_spacing):
            alpha = self.opacity * (0.6 if (y // self.scan_spacing) % 2 == 0 else 0.3)
            color = self._fade("#ffd700", alpha)
            self.create_line(0, y, w, y, fill=color)

        # shimmer noise
        self.noise_points = [
            (random.randint(0, w), random.randint(0, h))
            for _ in range(60)
        ]
        for (x, y) in self.noise_points:
            self.create_oval(x, y, x + 1, y + 1, fill=self._fade("#ffd700", self.opacity * 0.8), outline="")

        self.after(90, self._animate)

    @staticmethod
    def _fade(color: str, alpha: float) -> str:
        color = color.lstrip("#")
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        r = int(r * alpha)
        g = int(g * alpha)
        b = int(b * alpha)
        return f"#{r:02x}{g:02x}{b:02x}"
