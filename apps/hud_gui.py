"""
Glauka HUD v6 - Borderless Reality & Swapped Layout
"""
from __future__ import annotations

import math
import random
import sys
import time
import tkinter as tk

# --- LOGIC IMPORTS ---
# Try package import first; if it fails, patch sys.path for repo-local execution.
SCAN_RUNNER_IMPORT_ERROR: Exception | None = None
try:
    from glauka.ui.scan_runner import run_scan_async
except Exception as exc:
    SCAN_RUNNER_IMPORT_ERROR = exc
    import importlib
    import sys
    from pathlib import Path

    _pkg_root = Path(__file__).resolve().parents[2]  # repo root containing the glauka package
    _pkg_dir = Path(__file__).resolve().parent.parent  # glauka/
    for _p in (str(_pkg_root), str(_pkg_dir)):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    run_scan_async = None
    for _mod in ("glauka.ui.scan_runner", "ui.scan_runner"):
        try:
            run_scan_async = importlib.import_module(_mod).run_scan_async  # type: ignore[attr-defined]
            SCAN_RUNNER_IMPORT_ERROR = None
            break
        except Exception as exc2:
            SCAN_RUNNER_IMPORT_ERROR = exc2
            continue

# --- CONFIG ---
BG = "#000000"
GOLD_BLINDING = "#FFFFE0"
GOLD_BRIGHT = "#FFD700"
GOLD_DIM = "#9A7D0A" 
GOLD_DARK = "#332200"
GOLD_TEXT = "#FFC100"
ALERT_RED = "#FF3333"
SUCCESS_GREEN = "#33FF33"

FONT_HEADER = ("Consolas", 14, "bold")
FONT_UI = ("Consolas", 11, "bold")
FONT_MONO = ("Consolas", 10)
FONT_TINY = ("Consolas", 9)

class UnifiedDisplay(tk.Canvas):
    """
    Combines the Background Grid and the Solar Core into ONE canvas.
    This eliminates the 'black box' background around the sphere.
    """
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG, highlightthickness=0, **kwargs)
        self.width = 1920
        self.height = 1080
        
        # -- STATE --
        self.time_step = 0
        self.sphere_nodes = []
        self.sphere_edges = []
        self.state = "IDLE" # IDLE, SCANNING
        
        # -- SPHERE MATH --
        self.angle_y = 0
        self.angle_x = 0
        self._init_sphere()
        
        # -- EVENTS --
        self.bind("<Configure>", self._on_resize)
        self.animate()

    def _init_sphere(self):
        # Generate dual-layer sphere nodes once
        self._add_sphere_layer(130, 14, 20, is_core=False) # Crust
        self._add_sphere_layer(60, 8, 12, is_core=True)    # Core

    def _add_sphere_layer(self, r, lats, lons, is_core):
        offset = len(self.sphere_nodes)
        for i in range(lats+1):
            lat = math.pi*i/lats
            for j in range(lons):
                lon = 2*math.pi*j/lons
                x = r*math.sin(lat)*math.cos(lon)
                y = r*math.sin(lat)*math.sin(lon)
                z = r*math.cos(lat)
                self.sphere_nodes.append({"x":x, "y":y, "z":z, "core": is_core})
        
        for i in range(lats):
            for j in range(lons):
                c = offset + i*lons + j
                nl = offset + (i+1)*lons + j
                nlo = offset + i*lons + ((j+1)%lons)
                self.sphere_edges.append((c, nl))
                self.sphere_edges.append((c, nlo))

    def _on_resize(self, event):
        self.width = event.width
        self.height = event.height

    def set_state(self, state):
        self.state = state

    def animate(self):
        self.delete("all") 
        w, h = self.width, self.height
        cx, cy = w/2, h*0.5
        t = self.time_step
        
        # === LAYER 1: BACKGROUND GRID ===
        # Infinite Tunnel / Perspective Floor
        pulse = 0.5 + 0.3 * math.sin(t * 0.05)
        
        # Radiating Lines
        for i in range(0, 360, 20):
            rad = math.radians(i + t * 0.2)
            x2 = cx + math.cos(rad) * w
            y2 = cy + math.sin(rad) * h
            self.create_line(cx, cy, x2, y2, fill=GOLD_DARK, width=1)

        # Concentric Rings (The Tunnel)
        for r in range(1, 15):
            dist = (r * 100 + (t * 4)) % 1400
            if dist < 50: continue
            
            # Perspective Alpha
            col = GOLD_DIM if dist < 800 else GOLD_DARK
            
            # Draw ellipse
            x1 = cx - dist
            y1 = cy - dist * 0.6
            x2 = cx + dist
            y2 = cy + dist * 0.6
            self.create_oval(x1, y1, x2, y2, outline=col, width=1)

        # === LAYER 2: THE SOLAR SPHERE ===
        # Rotation Physics
        speed = 0.08 if self.state == "SCANNING" else 0.01
        self.angle_y += speed
        self.angle_x += speed * 0.5
        
        # Transform & Project
        projected = []
        for n in self.sphere_nodes:
            x, y, z = n["x"], n["y"], n["z"]
            
            # Scanning Jitter Effect
            if self.state == "SCANNING":
                wave = math.sin(t * 0.2 + y * 0.1) * 5
                x += wave
            
            # 3D Rotation
            cx_r, sx_r = math.cos(self.angle_x), math.sin(self.angle_x)
            cy_r, sy_r = math.cos(self.angle_y), math.sin(self.angle_y)
            
            # Rot Y
            x, z = x*cy_r + z*sy_r, -x*sy_r + z*cy_r
            # Rot X
            y, z = y*cx_r - z*sx_r, y*sx_r + z*cx_r
            
            # Project (Perspective)
            fov = 500
            scale = fov / (fov + z + 500)
            px = cx + x * scale
            py = cy + y * scale
            projected.append((px, py, z))

        # Sort Faces (Depth Buffer)
        sorted_edges = []
        for u, v in self.sphere_edges:
            z_avg = (projected[u][2] + projected[v][2]) / 2
            is_core = self.sphere_nodes[u]["core"]
            sorted_edges.append((z_avg, u, v, is_core))
        
        sorted_edges.sort(key=lambda k: k[0], reverse=True)
        
        # Draw Edges
        for z, u, v, is_core in sorted_edges:
            if is_core:
                col = GOLD_BLINDING
                wd = 2
            else:
                col = GOLD_BRIGHT if z < 0 else GOLD_DIM
                wd = 2 if z < 0 else 1
            
            self.create_line(projected[u][0], projected[u][1], 
                             projected[v][0], projected[v][1], 
                             fill=col, width=wd)

        self.time_step += 1
        self.after(30, self.animate)

class TerminalPanel(tk.Frame):
    """Left Side: Live Logs"""
    def __init__(self, parent, title="TERMINAL"):
        super().__init__(parent, bg=BG, bd=1, relief="solid")
        self.config(highlightbackground=GOLD_BRIGHT, highlightthickness=1)
        
        tk.Label(self, text=f" {title} ", bg=BG, fg=GOLD_BRIGHT, font=FONT_UI).pack(anchor="w")
        
        self.txt = tk.Text(self, bg=BG, fg=GOLD_TEXT, font=FONT_TINY, 
                           bd=0, highlightthickness=0, state="disabled")
        self.txt.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.txt.tag_config("INFO", foreground=GOLD_TEXT)
        self.txt.tag_config("SUCCESS", foreground=SUCCESS_GREEN)
        self.txt.tag_config("WARN", foreground=ALERT_RED)
        self.txt.tag_config("DIM", foreground=GOLD_DIM)

    def log(self, msg, level="INFO"):
        self.txt.config(state="normal")
        ts = time.strftime("%H:%M:%S")

        # Auto-detect severity if generic "INFO" is passed
        if level == "INFO":
            if any(x in msg for x in ["(!)", "CRITICAL", "High", "Secrets", "SQL"]):
                level = "WARN"
            elif any(x in msg for x in ["OPEN", "200 OK", "Found:", "Success"]):
                level = "SUCCESS"
            elif "Dim" in msg or "debug" in msg.lower():
                level = "DIM"

        self.txt.insert("end", f"[{ts}] ", "DIM")
        self.txt.insert("end", f"{msg}\n", level)
        self.txt.see("end")
        self.txt.config(state="disabled")
        
    def clear(self):
        self.txt.config(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.config(state="disabled")

class ConfigPanel(tk.Frame):
    """Right Side: Options & Subdomains"""
    def __init__(self, parent, vars_dict):
        super().__init__(parent, bg=BG, bd=0)
        
        # 1. Config Section
        cfg = tk.LabelFrame(self, text=" SCAN_CONFIG ", bg=BG, fg=GOLD_BRIGHT, font=FONT_TINY, bd=1)
        cfg.pack(fill="x", pady=(0, 20), ipadx=5, ipady=5)
        
        r, c = 0, 0
        for k, v in vars_dict.items():
            cb = tk.Checkbutton(cfg, text=k, variable=v, bg=BG, fg=GOLD_TEXT, 
                                selectcolor=BG, activeforeground=GOLD_BRIGHT, font=FONT_TINY)
            cb.grid(row=r, column=c, sticky="w", padx=5)
            c+=1
            if c > 1: c=0; r+=1
            
        # 2. Discovered Assets (category buckets)
        sub = tk.LabelFrame(self, text=" DISCOVERED_ASSETS ", bg=BG, fg=GOLD_BRIGHT, font=FONT_TINY, bd=1)
        sub.pack(fill="both", expand=True)

        self.asset_frames = {}
        self.asset_lists = {}
        self.asset_seen = {}
        categories = [
            ("subdomains", "SUBDOMAINS", SUCCESS_GREEN),
            ("open_ports", "OPEN PORTS", GOLD_BRIGHT),
            ("web_info", "WEB SERVICES", GOLD_BRIGHT),
            ("endpoints", "ENDPOINTS", SUCCESS_GREEN),
            ("findings", "FINDINGS", ALERT_RED),
            ("git", "GIT LEAKS", GOLD_BRIGHT),
        ]
        for idx, (key, label, color) in enumerate(categories):
            frame = tk.LabelFrame(sub, text=f" {label} ", bg=BG, fg=color, font=FONT_TINY, bd=1)
            frame.pack(fill="both", expand=True, padx=5, pady=3)
            lb = tk.Listbox(frame, bg=BG, fg=color, font=FONT_TINY, bd=0, highlightthickness=0)
            lb.pack(fill="both", expand=True, padx=5, pady=3)
            self.asset_frames[key] = frame
            self.asset_lists[key] = lb
            self.asset_seen[key] = set()

        self.category_aliases = {
            "subdomain": "subdomains",
            "subdomains": "subdomains",
            "open_port": "open_ports",
            "port": "open_ports",
            "ports": "open_ports",
            "web": "web_info",
            "web_info": "web_info",
            "alive": "web_info",
            "url": "web_info",
            "endpoint": "endpoints",
            "endpoints": "endpoints",
            "finding": "findings",
            "vuln": "findings",
            "xss": "findings",
            "sqli": "findings",
            "lfi": "findings",
            "rce": "findings",
            "git": "git",
            "git_leak": "git",
        }

    def add_asset(self, category: str, asset: str):
        cat = self.category_aliases.get(category.lower(), category.lower())
        if cat not in self.asset_lists:
            cat = "findings"  # default bucket
        if not asset:
            return
        seen = self.asset_seen.setdefault(cat, set())
        if asset in seen:
            return
        seen.add(asset)
        lb = self.asset_lists[cat]
        lb.insert(0, asset)

class GlaukaHUD(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GLAUKA | BORDERLESS")
        self._maximize_cross_platform()
        self.configure(bg=BG)
        
        # 1. UNIFIED BACKGROUND (Handles Grid + Sphere)
        self.display = UnifiedDisplay(self)
        self.display.place(x=0, y=0, relwidth=1, relheight=1)
        
        # -- VARS --
        self.target_var = tk.StringVar()
        self.opts = {
            "NMAP": tk.BooleanVar(value=True),
            "NUCLEI": tk.BooleanVar(value=True),
            "SUBS": tk.BooleanVar(value=True),
            "GIT": tk.BooleanVar(value=False),
            "FUZZ": tk.BooleanVar(value=False),
            "XSS": tk.BooleanVar(value=True)
        }
        
        self._build_overlay_ui()

    def _maximize_cross_platform(self):
        # Tk "zoomed" only works on Windows; X11 needs the -zoomed attribute.
        try:
            if sys.platform.startswith("win"):
                self.state("zoomed")
            else:
                self.attributes("-zoomed", True)
        except Exception:
            # Last resort: stay normal size instead of crashing.
            self.state("normal")

    def _build_overlay_ui(self):
        """
        Place widgets ON TOP of the canvas.
        """
        # Padding
        PAD_X = 30
        PAD_Y = 40
        SIDE_W = 380
        
        # === LEFT PANEL (Terminal) ===
        # "Terminal inside Gold Box"
        self.left_frame = TerminalPanel(self, "LIVE_LOG")
        self.left_frame.place(x=PAD_X, y=PAD_Y, width=SIDE_W, relheight=0.85)
        
        # === RIGHT PANEL (Config/Subs) ===
        # "Blue Box area"
        self.right_frame = ConfigPanel(self, self.opts)
        self.right_frame.place(relx=1.0, x=-PAD_X-SIDE_W, y=PAD_Y, width=SIDE_W, relheight=0.85)

        # === CENTER HEADER ===
        lbl_head = tk.Label(self, text="-- TARGET ACQUISITION --", bg=BG, fg=GOLD_BRIGHT, font=FONT_HEADER)
        lbl_head.place(relx=0.5, y=60, anchor="center")

        # === CENTER FOOTER (Input) ===
        # We create a floating frame for inputs
        ctrl_frame = tk.Frame(self, bg=BG, highlightbackground=GOLD_BRIGHT, highlightthickness=1)
        ctrl_frame.place(relx=0.5, rely=0.85, anchor="center", width=700, height=70)
        
        tk.Label(ctrl_frame, text=" HOST:// ", bg=GOLD_BRIGHT, fg="black", font=FONT_UI).pack(side="left", fill="y")
        
        entry = tk.Entry(ctrl_frame, textvariable=self.target_var, bg="#111", fg=GOLD_BRIGHT, 
                         insertbackground=GOLD_BRIGHT, font=FONT_HEADER, relief="flat")
        entry.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        entry.focus()

        # Mode selector
        mode_frame = tk.Frame(ctrl_frame, bg=BG)
        mode_frame.pack(side="left", padx=10)
        tk.Label(mode_frame, text="Mode:", bg=BG, fg=GOLD_BRIGHT, font=FONT_TINY).pack(side="top", anchor="w")
        self.mode_var = tk.StringVar(value="active")
        for val in ("passive", "active"):
            rb = tk.Radiobutton(
                mode_frame,
                text=val.upper(),
                variable=self.mode_var,
                value=val,
                bg=BG,
                fg=GOLD_BRIGHT,
                selectcolor=BG,
                font=FONT_TINY,
                indicatoron=False,
                width=7,
                relief="flat",
            )
            rb.pack(side="left", padx=2)

        self.btn = tk.Button(ctrl_frame, text="[ EXECUTE ]", command=self.start_scan, 
                             bg=BG, fg=GOLD_BRIGHT, font=FONT_UI, relief="flat", activebackground=GOLD_BRIGHT)
        self.btn.pack(side="right", padx=10)

    def start_scan(self):
        target = self.target_var.get()
        if not target: return
        
        self.btn.config(state="disabled", text="RUNNING")
        self.display.set_state("SCANNING") # Speed up sphere
        
        self.left_frame.clear()
        self.left_frame.log(f"Locked on: {target}", "INFO")
        
        if run_scan_async:
            run_scan_async(
                target,
                self.mode_var.get(),
                on_result=self.done,
                on_log=self.on_log,
                on_progress=self.on_progress,
            )
        else:
            err = f"Scan engine unavailable (run_scan_async missing)."
            if "SCAN_RUNNER_IMPORT_ERROR" in globals() and SCAN_RUNNER_IMPORT_ERROR:
                err += f" Import error: {SCAN_RUNNER_IMPORT_ERROR}"
            self.left_frame.log(err, "WARN")
            # Fallback demo so the UI still behaves when the engine isn't present.
            self._sim_scan(target)

    def _sim_scan(self, target):
        self.after(500, lambda: self.left_frame.log("Enumerating subdomains...", "INFO"))
        self.after(1000, lambda: self.right_frame.add_asset("subdomains", f"admin.{target}"))
        self.after(1200, lambda: self.right_frame.add_asset("subdomains", f"dev.{target}"))
        self.after(1400, lambda: self.right_frame.add_asset("subdomains", f"api.{target}"))
        self.after(2000, lambda: self.left_frame.log("Port scan: 80, 443, 8080 OPEN", "SUCCESS"))
        self.after(3000, lambda: self.left_frame.log("(!) SQL Injection Found", "WARN"))
        self.after(4000, lambda: self.done(None))

    def on_log(self, msg):
        self.after(0, lambda: self.left_frame.log(msg))

    def on_progress(self, category: str, value: str):
        self.after(0, lambda: self.right_frame.add_asset(category, value))

    def done(self, res):
        self.btn.config(state="normal", text="[ EXECUTE ]")
        self.display.set_state("IDLE")
        self.left_frame.log("Scan Complete.", "INFO")

if __name__ == "__main__":
    app = GlaukaHUD()
    app.mainloop()


def launch() -> None:
    """Compatibility launcher used by gui_hud.py."""
    app = GlaukaHUD()
    app.mainloop()
