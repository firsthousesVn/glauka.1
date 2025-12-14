from __future__ import annotations

import math
import random
import logging
import tkinter as tk

from .base_panel import set_text
from glauka.ui.theme.crt_alien_theme import BG as THEME_BG, FG as THEME_FG, ACCENT1, ACCENT2

BG_BLACK = THEME_BG
GOLD_BRIGHT = THEME_FG
GOLD_INTENSE = ACCENT2
GOLD_MEDIUM = ACCENT1
GOLD_DIM = "#3a1a00"

DEFAULT_COLORS = {
    "bg": BG_BLACK,
    "bright": GOLD_BRIGHT,
    "intense": GOLD_INTENSE,
    "medium": GOLD_MEDIUM,
    "dim": GOLD_DIM,
}

DEFAULT_FONT_TITLE = ("Courier New", 9, "bold")
DEFAULT_FONT_SYMBOL = ("Courier New", 24, "bold")
DEFAULT_FONT_BODY = ("Courier New", 11)

logger = logging.getLogger(__name__)


class ReactiveGeometricCanvas(tk.Canvas):
    """Complex animated geometry that reacts to mouse movement."""

    def __init__(self, parent, colors: dict[str, str] | None = None, **kwargs):
        self.colors = colors or DEFAULT_COLORS
        super().__init__(parent, bg=self.colors["bg"], highlightthickness=0, **kwargs)
        self.mouse_x = 0
        self.mouse_y = 0
        self.time = 0.0
        self.particles = []
        self.nodes = []
        self._anim_error_logged = False

        for _ in range(100):
            self.particles.append(
                {
                    "x": random.randint(0, 1600),
                    "y": random.randint(0, 900),
                    "vx": random.uniform(-0.5, 0.5),
                    "vy": random.uniform(-0.5, 0.5),
                    "size": random.uniform(1, 3),
                }
            )

        for _ in range(30):
            self.nodes.append(
                {
                    "x": random.randint(0, 1600),
                    "y": random.randint(0, 900),
                    "vx": random.uniform(-0.3, 0.3),
                    "vy": random.uniform(-0.3, 0.3),
                }
            )

        self.bind("<Motion>", self._on_mouse_move)
        self._animate()

    def _on_mouse_move(self, event: tk.Event) -> None:
        self.mouse_x = event.x
        self.mouse_y = event.y

    def _animate(self) -> None:
        try:
            self.delete("all")
            w, h = self.winfo_width(), self.winfo_height()

            if w < 10 or h < 10:
                w, h = 1600, 900

            self.time += 0.025

            self._draw_hexagonal_layers(w, h)
            self._draw_sacred_circles(w, h)
            self._draw_node_network(w, h)
            self._draw_particles(w, h)
            self._draw_mouse_glow()
            self._draw_scan_lines(w, h)

            self.after(30, self._animate)
        except Exception:
            if not self._anim_error_logged:
                self._anim_error_logged = True
                logger.exception("ReactiveGeometricCanvas animation error")
            self.after(500, self._animate)

    def _draw_hexagonal_layers(self, w: int, h: int) -> None:
        for layer in range(3):
            hex_size = 60 + layer * 30
            rotation = self.time * (0.2 + layer * 0.1)

            for x in range(-hex_size, w + hex_size, int(hex_size * 1.5)):
                for y in range(-hex_size, h + hex_size, int(hex_size * math.sqrt(3))):
                    offset_y = (x // int(hex_size * 1.5)) % 2 * hex_size * math.sqrt(3) / 2

                    dx = self.mouse_x - x
                    dy = self.mouse_y - (y + offset_y)
                    dist = math.sqrt(dx * dx + dy * dy)

                    if dist < 300:
                        brightness = 0.4 + (1 - dist / 300) * 0.6
                        size_mult = 1 + (1 - dist / 300) * 0.3
                    else:
                        brightness = 0.15 + math.sin(self.time + x * 0.01) * 0.1
                        size_mult = 1.0

                    color = self._get_gold_color(brightness)
                    width = 3 if brightness > 0.7 else 2 if brightness > 0.4 else 1

                    points = []
                    for i in range(6):
                        angle = math.pi / 3 * i + rotation
                        pulse = 1 + math.sin(self.time * 2 + i) * 0.05
                        hx = x + hex_size * size_mult * pulse * math.cos(angle)
                        hy = y + offset_y + hex_size * size_mult * pulse * math.sin(angle)
                        points.extend([hx, hy])

                    if len(points) >= 6:
                        self.create_polygon(points, outline=color, fill="", width=width)

    def _draw_sacred_circles(self, w: int, h: int) -> None:
        cx, cy = w // 2, h // 2

        for i in range(6):
            radius = 80 + i * 70 + math.sin(self.time + i * 0.5) * 30

            dx = self.mouse_x - cx
            dy = self.mouse_y - cy
            mouse_dist = math.sqrt(dx * dx + dy * dy)

            brightness = 0.2 + (1 - min(mouse_dist / 500, 1)) * 0.4
            color = self._get_gold_color(brightness)
            width = 4 if brightness > 0.5 else 2

            self.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                outline=color,
                width=width,
            )

            if brightness > 0.4:
                for angle in [0, 90, 180, 270]:
                    rad = math.radians(angle + self.time * 20)
                    x1 = cx + radius * 0.9 * math.cos(rad)
                    y1 = cy + radius * 0.9 * math.sin(rad)
                    x2 = cx + radius * 1.1 * math.cos(rad)
                    y2 = cy + radius * 1.1 * math.sin(rad)
                    self.create_line(x1, y1, x2, y2, fill=color, width=2)

    def _draw_node_network(self, w: int, h: int) -> None:
        for node in self.nodes:
            node["x"] += node["vx"]
            node["y"] += node["vy"]

            if node["x"] < 0 or node["x"] > w:
                node["vx"] *= -1
            if node["y"] < 0 or node["y"] > h:
                node["vy"] *= -1

            dx = self.mouse_x - node["x"]
            dy = self.mouse_y - node["y"]
            dist = math.sqrt(dx * dx + dy * dy)

            if 0 < dist < 200:
                force = 0.0003
                node["vx"] += dx * force
                node["vy"] += dy * force

            node["vx"] *= 0.99
            node["vy"] *= 0.99

        for i, node1 in enumerate(self.nodes):
            for node2 in self.nodes[i + 1 :]:
                dx = node2["x"] - node1["x"]
                dy = node2["y"] - node1["y"]
                dist = math.sqrt(dx * dx + dy * dy)

                if dist < 180:
                    brightness = 0.4 * (1 - dist / 180)
                    color = self._get_gold_color(brightness)
                    width = 2 if brightness > 0.3 else 1
                    self.create_line(
                        node1["x"],
                        node1["y"],
                        node2["x"],
                        node2["y"],
                        fill=color,
                        width=width,
                    )

            size = 4
            self.create_oval(
                node1["x"] - size,
                node1["y"] - size,
                node1["x"] + size,
                node1["y"] + size,
                fill=self.colors["bright"],
                outline=self.colors["intense"],
                width=2,
            )

    def _draw_particles(self, w: int, h: int) -> None:
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]

            if p["x"] < 0:
                p["x"] = w
            if p["x"] > w:
                p["x"] = 0
            if p["y"] < 0:
                p["y"] = h
            if p["y"] > h:
                p["y"] = 0

            dx = self.mouse_x - p["x"]
            dy = self.mouse_y - p["y"]
            dist = math.sqrt(dx * dx + dy * dy)

            if 0 < dist < 150:
                p["vx"] += dx * 0.00008
                p["vy"] += dy * 0.00008

            p["vx"] *= 0.98
            p["vy"] *= 0.98

            if dist < 150:
                brightness = 0.7 + (1 - dist / 150) * 0.3
            else:
                brightness = 0.6

            color = self._get_gold_color(brightness)

            self.create_oval(
                p["x"] - p["size"],
                p["y"] - p["size"],
                p["x"] + p["size"],
                p["y"] + p["size"],
                fill=color,
                outline="",
            )

    def _draw_mouse_glow(self) -> None:
        if self.mouse_x > 0 and self.mouse_y > 0:
            for i in range(4):
                radius = 25 + i * 18
                brightness = 0.5 - i * 0.12
                color = self._get_gold_color(brightness)
                width = 3 if i == 0 else 2

                self.create_oval(
                    self.mouse_x - radius,
                    self.mouse_y - radius,
                    self.mouse_x + radius,
                    self.mouse_y + radius,
                    outline=color,
                    width=width,
                )

    def _draw_scan_lines(self, w: int, h: int) -> None:
        y = (self.time * 100) % h
        gradient_start = max(0, y - 50)
        gradient_end = min(h, y + 50)

        for i in range(int(gradient_start), int(gradient_end), 2):
            dist = abs(i - y)
            brightness = 0.3 * (1 - dist / 50)
            color = self._get_gold_color(brightness)
            self.create_line(0, i, w, i, fill=color, width=1)

        x = (self.time * 150) % w
        for i in range(int(max(0, x - 30)), int(min(w, x + 30)), 2):
            dist = abs(i - x)
            brightness = 0.25 * (1 - dist / 30)
            color = self._get_gold_color(brightness)
            self.create_line(i, 0, i, h, fill=color, width=1)

    def _get_gold_color(self, brightness: float) -> str:
        brightness = max(0.0, min(1.0, brightness))
        if brightness > 0.8:
            return self.colors["intense"]
        if brightness > 0.5:
            return self.colors["bright"]
        if brightness > 0.25:
            return self.colors["medium"]
        return self.colors["dim"]


class HUDPanel(tk.Frame):
    """Panel with mouse-reactive border and custom gold scrollbar."""

    def __init__(
        self,
        parent,
        title: str,
        symbol: str,
        *,
        colors: dict[str, str] | None = None,
        font_title=DEFAULT_FONT_TITLE,
        font_symbol=DEFAULT_FONT_SYMBOL,
        font_body=DEFAULT_FONT_BODY,
        **kwargs,
    ):
        self.colors = colors or DEFAULT_COLORS
        super().__init__(parent, bg=self.colors["bg"], **kwargs)

        self.title_text = title
        self.symbol = symbol
        self.mouse_x = 0
        self.mouse_y = 0
        self.mouse_inside = False

        self.border_canvas = tk.Canvas(self, bg=self.colors["bg"], highlightthickness=0)
        self.border_canvas.pack(fill="both", expand=True)

        self.content_frame = tk.Frame(self.border_canvas, bg=self.colors["bg"])
        self.content_window = self.border_canvas.create_window(
            10, 10, anchor="nw", window=self.content_frame
        )

        self.title_label = tk.Label(
            self.content_frame,
            text=title.upper(),
            bg=self.colors["bg"],
            fg=self.colors["bright"],
            font=font_title,
        )
        self.title_label.place(relx=1.0, y=8, anchor="ne")

        self.symbol_label = tk.Label(
            self.content_frame,
            text=symbol,
            bg=self.colors["bg"],
            fg=self.colors["intense"],
            font=font_symbol,
        )
        self.symbol_label.place(x=25, y=25)

        self.text_widget = tk.Text(
            self.content_frame,
            bg=self.colors["bg"],
            fg=self.colors["bright"],
            font=font_body,
            wrap="word",
            relief="flat",
            bd=0,
            insertbackground=self.colors["bright"],
            highlightthickness=0,
        )
        self.text_widget.place(x=20, y=85, relwidth=0.92, relheight=0.75)

        self.scroll_canvas = tk.Canvas(
            self.content_frame,
            bg=self.colors["bg"],
            highlightthickness=0,
            width=10,
        )
        self.scroll_canvas.place(relx=0.97, y=85, relheight=0.75, anchor="ne")

        self._scroll_first = 0.0
        self._scroll_last = 1.0

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Motion>", self._on_motion)
        self.border_canvas.bind("<Configure>", self._on_resize)

        self.text_widget.bind("<MouseWheel>", self._on_mousewheel)
        self.text_widget.bind("<Button-4>", self._on_mousewheel)
        self.text_widget.bind("<Button-5>", self._on_mousewheel)
        self.text_widget.configure(yscrollcommand=self._on_text_scroll)

        self.scroll_canvas.bind("<Button-1>", self._on_scrollbar_click)
        self.scroll_canvas.bind("<B1-Motion>", self._on_scrollbar_drag)

        self._draw_border()
        self._animate_symbol()
        self._draw_scrollbar()

    def _on_resize(self, event: tk.Event) -> None:
        self.content_frame.config(width=event.width - 20, height=event.height - 20)
        self.border_canvas.coords(self.content_window, 10, 10)
        self._draw_border()

    def _on_enter(self, _event: tk.Event) -> None:
        self.mouse_inside = True

    def _on_leave(self, _event: tk.Event) -> None:
        self.mouse_inside = False
        self._draw_border()

    def _on_motion(self, event: tk.Event) -> None:
        self.mouse_x = event.x
        self.mouse_y = event.y
        if self.mouse_inside:
            self._draw_border()

    def _draw_border(self) -> None:
        self.border_canvas.delete("border")

        w = self.border_canvas.winfo_width()
        h = self.border_canvas.winfo_height()

        if w < 10 or h < 10:
            return

        if self.mouse_inside and self.mouse_x > 0:
            edge_dist = min(
                self.mouse_x,
                self.mouse_y,
                w - self.mouse_x,
                h - self.mouse_y,
            )
            brightness = max(0.4, min(1.0, 1.2 - edge_dist / 100))
        else:
            brightness = 0.4

        if brightness > 0.85:
            color = self.colors["intense"]
            width = 6
        elif brightness > 0.6:
            color = self.colors["bright"]
            width = 5
        else:
            color = self.colors["medium"]
            width = 4

        margin = 45
        points = [
            0,
            margin,
            margin,
            0,
            w - margin,
            0,
            w,
            margin,
            w,
            h - margin,
            w - margin,
            h,
            margin,
            h,
            0,
            h - margin,
        ]

        self.border_canvas.create_polygon(
            points, outline=color, fill="", width=width, tags="border"
        )

        if brightness > 0.6:
            inner_margin = margin + 10
            inner_points = [
                10,
                inner_margin,
                inner_margin,
                10,
                w - inner_margin,
                10,
                w - 10,
                inner_margin,
                w - 10,
                h - inner_margin,
                w - inner_margin,
                h - 10,
                inner_margin,
                h - 10,
                10,
                h - inner_margin,
            ]
            self.border_canvas.create_polygon(
                inner_points, outline=self.colors["dim"], fill="", width=2, tags="border"
            )

        if brightness > 0.7:
            corner_size = 20
            for (x, y) in [
                (margin, margin),
                (w - margin, margin),
                (margin, h - margin),
                (w - margin, h - margin),
            ]:
                self.border_canvas.create_oval(
                    x - corner_size,
                    y - corner_size,
                    x + corner_size,
                    y + corner_size,
                    outline=self.colors["intense"],
                    width=2,
                    tags="border",
                )

    def _animate_symbol(self) -> None:
        try:
            colors = [self.colors["bright"], self.colors["intense"], self.colors["medium"]]
            current = self.symbol_label.cget("fg")
            try:
                idx = colors.index(current)
                next_color = colors[(idx + 1) % len(colors)]
            except ValueError:
                next_color = colors[0]

            self.symbol_label.config(fg=next_color)
            self.after(1200, self._animate_symbol)
        except Exception:
            if not hasattr(self, "_symbol_error_logged"):
                self._symbol_error_logged = True
                logger.exception("HUDPanel symbol animation error")

    def _on_text_scroll(self, first: str, last: str) -> None:
        try:
            self._scroll_first = float(first)
            self._scroll_last = float(last)
        except Exception:
            self._scroll_first = 0.0
            self._scroll_last = 1.0
        self._draw_scrollbar()

    def _on_mousewheel(self, event: tk.Event) -> str:
        if event.num == 4:
            delta = -1
        elif event.num == 5:
            delta = 1
        else:
            delta = -1 * int(event.delta / 120)

        self.text_widget.yview_scroll(delta, "units")
        self._force_scrollbar_update()
        return "break"

    def _force_scrollbar_update(self) -> None:
        first, last = self.text_widget.yview()
        self._on_text_scroll(str(first), str(last))

    def _draw_scrollbar(self) -> None:
        self.scroll_canvas.delete("all")

        w = self.scroll_canvas.winfo_width()
        h = self.scroll_canvas.winfo_height()
        if w < 2 or h < 10:
            return

        track_margin = 2
        self.scroll_canvas.create_line(
            w // 2,
            track_margin,
            w // 2,
            h - track_margin,
            fill=self.colors["dim"],
            width=2,
        )

        first = self._scroll_first
        last = self._scroll_last
        visible = max(0.05, last - first)

        thumb_height = max(18, h * visible)
        thumb_center = h * (first + visible / 2.0)
        y1 = max(track_margin, thumb_center - thumb_height / 2.0)
        y2 = min(h - track_margin, thumb_center + thumb_height / 2.0)

        x_center = w // 2
        pad = 3
        points = [
            x_center,
            y1 - pad,
            x_center + pad,
            (y1 + y2) / 2,
            x_center,
            y2 + pad,
            x_center - pad,
            (y1 + y2) / 2,
        ]
        self.scroll_canvas.create_polygon(
            points, outline=self.colors["bright"], fill=self.colors["medium"]
        )

    def _scrollbar_pos_to_fraction(self, y: int) -> float:
        h = self.scroll_canvas.winfo_height()
        if h <= 0:
            return 0.0
        frac = y / float(h)
        return max(0.0, min(1.0, frac))

    def _on_scrollbar_click(self, event: tk.Event) -> None:
        frac = self._scrollbar_pos_to_fraction(event.y)
        self.text_widget.yview_moveto(frac)
        self._force_scrollbar_update()

    def _on_scrollbar_drag(self, event: tk.Event) -> None:
        frac = self._scrollbar_pos_to_fraction(event.y)
        self.text_widget.yview_moveto(frac)
        self._force_scrollbar_update()

    def update_content(self, text: str) -> None:
        set_text(self.text_widget, text)

    def append_text(self, text: str) -> None:
        self.text_widget.config(state="normal")
        self.text_widget.insert("end", text + "\n")
        self.text_widget.see("end")
        self.text_widget.config(state="disabled")
        self._force_scrollbar_update()
