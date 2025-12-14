"""
Glauka Classic GUI - retains original visuals while using shared recon engine.
"""

from __future__ import annotations

import math
import random
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from parser import get_report_stats, parse_report
from glauka.presentation.formatter import format_all_panels
from glauka.ui.panel_update import apply_formatted_result
from glauka.ui.panels.basic_panel import (
    BG_BLACK,
    GOLD_BRIGHT,
    GOLD_DIM,
    GOLD_INTENSE,
    GOLD_MEDIUM,
    CollapsiblePanel,
    FONT_HEADER,
)
from glauka.ui.scan_runner import run_scan_async

FONT_MONO = ("Consolas", 11, "bold")
FONT_TITLE = ("Consolas", 16, "bold")


class GeometricBackground(tk.Canvas):
    """Animated geometric background with hexagons and particles."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_BLACK, highlightthickness=0, **kwargs)
        self.time = 0
        self.particles = []

        for _ in range(50):
            self.particles.append(
                {
                    "x": random.randint(0, 1200),
                    "y": random.randint(0, 750),
                    "vx": random.uniform(-0.3, 0.3),
                    "vy": random.uniform(-0.3, 0.3),
                    "size": random.uniform(1, 2),
                }
            )

        self._animate()

    def _animate(self):
        try:
            self.delete("all")
            w, h = self.winfo_width(), self.winfo_height()
            if w < 10 or h < 10:
                w, h = 1200, 750

            self.time += 0.02

            hex_size = 60
            for x in range(-hex_size, w + hex_size, int(hex_size * 1.5)):
                for y in range(-hex_size, h + hex_size, int(hex_size * math.sqrt(3))):
                    offset_y = (x // int(hex_size * 1.5)) % 2 * hex_size * math.sqrt(3) / 2

                    brightness = 0.15 + math.sin(self.time + x * 0.01 + y * 0.01) * 0.1
                    color = self._get_gold(brightness)

                    points = []
                    for i in range(6):
                        angle = math.pi / 3 * i + self.time * 0.1
                        hx = x + hex_size * 0.8 * math.cos(angle)
                        hy = y + offset_y + hex_size * 0.8 * math.sin(angle)
                        points.extend([hx, hy])

                    if len(points) >= 6:
                        self.create_polygon(points, outline=color, fill="", width=1)

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

                color = GOLD_BRIGHT if random.random() > 0.5 else GOLD_MEDIUM
                self.create_oval(
                    p["x"] - p["size"],
                    p["y"] - p["size"],
                    p["x"] + p["size"],
                    p["y"] + p["size"],
                    fill=color,
                    outline="",
                )

            self.after(40, self._animate)
        except Exception:
            pass

    def _get_gold(self, brightness):
        if brightness > 0.3:
            return GOLD_MEDIUM
        elif brightness > 0.15:
            return GOLD_DIM
        else:
            return "#3D3410"


class GlaukaApp(tk.Tk):
    """Main Glauka application."""

    def __init__(self):
        super().__init__()

        self.title("Glauka ƒ? Active Recon Scanner")
        self.geometry("1200x750")
        self.configure(bg=BG_BLACK)

        self.is_scanning = False
        self.current_report = ""
        self.report_sections = {}

        self._build_ui()

    def _build_ui(self):
        self.bg_canvas = GeometricBackground(self)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        main_container = tk.Frame(self, bg=BG_BLACK)
        main_container.place(relx=0.02, rely=0.02, relwidth=0.96, relheight=0.96)

        control_frame = tk.Frame(main_container, bg=BG_BLACK, height=100)
        control_frame.pack(fill="x", pady=(0, 10))
        control_frame.pack_propagate(False)

        title_frame = tk.Frame(control_frame, bg=BG_BLACK)
        title_frame.pack(side="left", padx=20, pady=10)

        self.main_symbol = tk.Label(
            title_frame,
            text="ƒ-^",
            bg=BG_BLACK,
            fg=GOLD_INTENSE,
            font=("Consolas", 36, "bold"),
        )
        self.main_symbol.pack(side="left", padx=(0, 15))
        self._animate_main_symbol()

        title_label = tk.Label(
            title_frame,
            text="GLAUKA",
            bg=BG_BLACK,
            fg=GOLD_BRIGHT,
            font=FONT_TITLE,
        )
        title_label.pack(side="left")

        input_frame = tk.Frame(control_frame, bg=BG_BLACK)
        input_frame.pack(side="left", expand=True, padx=30)

        input_label = tk.Label(
            input_frame,
            text="TARGET:",
            bg=BG_BLACK,
            fg=GOLD_MEDIUM,
            font=("Consolas", 10, "bold"),
        )
        input_label.pack(anchor="w")

        self.target_input = tk.Entry(
            input_frame,
            bg=BG_BLACK,
            fg=GOLD_BRIGHT,
            font=("Consolas", 13, "bold"),
            relief="flat",
            bd=0,
            insertbackground=GOLD_BRIGHT,
        )
        self.target_input.pack(fill="x", pady=(5, 0))

        input_line = tk.Frame(input_frame, bg=GOLD_BRIGHT, height=2)
        input_line.pack(fill="x")

        btn_frame = tk.Frame(control_frame, bg=BG_BLACK)
        btn_frame.pack(side="right", padx=20)

        self.scan_btn = self._create_button(btn_frame, "ƒ-%\nSCAN", self._start_scan)
        self.scan_btn.pack(side="left", padx=5)

        load_btn = self._create_button(btn_frame, "ƒ-Z\nLOAD", self._load_file)
        load_btn.pack(side="left", padx=5)

        clear_btn = self._create_button(btn_frame, "ƒ-O\nCLEAR", self._clear_all)
        clear_btn.pack(side="left", padx=5)

        content_wrapper = tk.Frame(main_container, bg=BG_BLACK)
        content_wrapper.pack(fill="both", expand=True)

        panels_frame = tk.Frame(content_wrapper, bg=BG_BLACK)
        panels_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.panels = {}
        panel_data = [
            ("Scope", "ƒª­", "No scan yet. Enter target and click SCAN."),
            ("DNS Records", "ƒª›", "DNS resolution results will appear here."),
            ("Subdomains", "ƒª", "Discovered subdomains will be listed here."),
            ("Open Ports", "ƒª", "Open ports will be detected here."),
            ("Attack Vectors", "ƒªÝ", "Attack vectors will appear here."),
        ]

        for title, symbol, placeholder in panel_data:
            panel = CollapsiblePanel(panels_frame, title, symbol)
            panel.pack(fill="x", pady=5)
            panel.update_content(placeholder)
            self.panels[title] = panel

        terminal_frame = tk.Frame(content_wrapper, bg=GOLD_BRIGHT, width=350)
        terminal_frame.pack(side="right", fill="both", padx=(10, 0))
        terminal_frame.pack_propagate(False)

        terminal_inner = tk.Frame(terminal_frame, bg=BG_BLACK)
        terminal_inner.pack(fill="both", expand=True, padx=3, pady=3)

        terminal_header = tk.Frame(terminal_inner, bg=GOLD_BRIGHT, height=35)
        terminal_header.pack(fill="x")
        terminal_header.pack_propagate(False)

        tk.Label(
            terminal_header,
            text="ƒªœ  TERMINAL",
            bg=GOLD_BRIGHT,
            fg=BG_BLACK,
            font=FONT_HEADER,
        ).pack(side="left", padx=15)

        self.terminal_widget = tk.Text(
            terminal_inner,
            bg=BG_BLACK,
            fg=GOLD_BRIGHT,
            font=("Courier New", 10),
            wrap="word",
            relief="flat",
            bd=0,
            insertbackground=GOLD_BRIGHT,
        )
        self.terminal_widget.pack(fill="both", expand=True, padx=10, pady=10)
        self.terminal_widget.config(state="disabled")

        status_frame = tk.Frame(main_container, bg=BG_BLACK, height=30)
        status_frame.pack(fill="x", pady=(10, 0))
        status_frame.pack_propagate(False)

        status_line = tk.Frame(status_frame, bg=GOLD_DIM, height=1)
        status_line.pack(fill="x", pady=(0, 10))

        self.status_dot = tk.Canvas(status_frame, width=15, height=15, bg=BG_BLACK, highlightthickness=0)
        self.status_dot.pack(side="left", padx=10)
        self.status_dot.create_oval(2, 2, 13, 13, fill=GOLD_BRIGHT, outline=GOLD_INTENSE, width=2)
        self._animate_status_dot()

        self.status_label = tk.Label(
            status_frame,
            text="Ready | Enter target and click SCAN",
            bg=BG_BLACK,
            fg=GOLD_MEDIUM,
            font=("Consolas", 10),
        )
        self.status_label.pack(side="left", padx=10)

        self.panel_scope = self.panels["Scope"]
        self.panel_signal = self.panels["DNS Records"]
        self.panel_subdomains = self.panels["Subdomains"]
        self.panel_ports = self.panels["Open Ports"]
        self.panel_vulns = self.panels["Attack Vectors"]

    def _create_button(self, parent, text, command):
        btn_frame = tk.Frame(parent, bg=GOLD_BRIGHT)
        btn_frame.pack_propagate(False)
        btn_frame.config(width=70, height=70)

        btn_inner = tk.Frame(btn_frame, bg=BG_BLACK)
        btn_inner.place(relx=0.05, rely=0.05, relwidth=0.9, relheight=0.9)

        btn = tk.Label(
            btn_inner,
            text=text,
            bg=BG_BLACK,
            fg=GOLD_BRIGHT,
            font=("Consolas", 11, "bold"),
            cursor="hand2",
            justify="center",
        )
        btn.pack(expand=True)

        def on_enter(_e):
            btn.config(fg=GOLD_INTENSE)
            btn_frame.config(bg=GOLD_INTENSE)

        def on_leave(_e):
            btn.config(fg=GOLD_BRIGHT)
            btn_frame.config(bg=GOLD_BRIGHT)

        def on_click(_e):
            command()

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        btn.bind("<Button-1>", on_click)

        return btn_frame

    def _animate_main_symbol(self):
        try:
            colors = [GOLD_BRIGHT, GOLD_INTENSE, GOLD_MEDIUM]
            current = self.main_symbol.cget("fg")
            idx = colors.index(current)
            next_color = colors[(idx + 1) % len(colors)]
            self.main_symbol.config(fg=next_color)
            self.after(700, self._animate_main_symbol)
        except Exception:
            pass

    def _animate_status_dot(self):
        try:
            self.status_dot.delete("all")
            colors = [GOLD_BRIGHT, GOLD_INTENSE]
            import time

            color = colors[int(time.time() * 2) % 2]
            self.status_dot.create_oval(2, 2, 13, 13, fill=color, outline=GOLD_INTENSE, width=2)
            self.after(500, self._animate_status_dot)
        except Exception:
            pass

    def _append_terminal(self, text: str):
        try:
            self.terminal_widget.config(state="normal")
            self.terminal_widget.insert("end", text + "\n")
            self.terminal_widget.see("end")
            self.terminal_widget.config(state="disabled")
        except Exception:
            pass

    def _clear_terminal(self):
        try:
            self.terminal_widget.config(state="normal")
            self.terminal_widget.delete("1.0", "end")
            self.terminal_widget.config(state="disabled")
        except Exception:
            pass

    def _start_scan(self):
        target = self.target_input.get().strip()

        if not target:
            messagebox.showwarning("No Target", "Enter a domain or IP")
            return

        if self.is_scanning:
            messagebox.showinfo("Scanning", "Scan already in progress")
            return

        self.is_scanning = True
        self._clear_terminal()
        self._append_terminal(f"> Starting scan for {target}")
        self.status_label.config(text=f"Scanning {target}...")

        run_scan_async(target, "passive", self._on_scan_result, self._log_from_worker)

    def _on_scan_result(self, result):
        def update_ui():
            if result is None:
                self.status_label.config(text="Scan error")
                return
            formatted = format_all_panels(result, self.target_input.get().strip())
            apply_formatted_result(self, formatted)
            self.status_label.config(text=f"ƒo Scan complete for {self.target_input.get().strip()}")

        self.after(0, update_ui)
        self.is_scanning = False

    def _log_from_worker(self, msg: str):
        try:
            self.after(0, lambda m=msg: self._append_terminal(m))
        except Exception:
            pass

    def _load_file(self):
        file_path = filedialog.askopenfilename(
            title="Open Recon Report", filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )

        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self._process_report(content, f"Loaded: {Path(file_path).name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load:\n{e}")

    def _process_report(self, text: str, source: str):
        self.current_report = text
        self.report_sections = parse_report(text)

        formatted = {
            "scope": self.report_sections.get("Scope", "[No data]"),
            "signal": self.report_sections.get("High-Signal Findings", "[No data]"),
            "subdomains": self.report_sections.get("Keys", "[No data]"),
            "ports": self.report_sections.get("Ports") or self.report_sections.get("Bug Paths", "[No data]"),
            "vulns": self.report_sections.get("Vulnerabilities") or self.report_sections.get("Bug Paths", "[No data]"),
            "bug_paths": self.report_sections.get("Bug Paths", "[No data]"),
        }

        apply_formatted_result(self, formatted)

        lines, chars = get_report_stats(text)
        self.status_label.config(text=f"ƒo {source} | Lines: {lines} | Chars: {chars}")

    def _clear_all(self):
        self.current_report = ""
        self.report_sections = {}
        self.target_input.delete(0, "end")

        placeholder = "No data"
        for panel in self.panels.values():
            panel.update_content(placeholder)

        self._clear_terminal()
        self.status_label.config(text="Cleared | Ready")


def launch():
    app = GlaukaApp()
    app.mainloop()


if __name__ == "__main__":
    launch()
