import tkinter as tk

BG_BLACK = "#000000"
GOLD_BRIGHT = "#FFE55C"
GOLD_INTENSE = "#FFF59D"
GOLD_MEDIUM = "#FFD54F"
GOLD_DIM = "#6B5D1A"

FONT_MONO_SMALL = ("Consolas", 10, "bold")
FONT_HEADER = ("Consolas", 12, "bold")


class CollapsiblePanel(tk.Frame):
    """Collapsible panel with geometric styling."""

    def __init__(self, parent, title: str, symbol: str, **kwargs):
        super().__init__(parent, bg=BG_BLACK, **kwargs)

        self.title = title
        self.symbol = symbol
        self.is_expanded = True

        self.border_frame = tk.Frame(self, bg=GOLD_BRIGHT, highlightthickness=0)
        self.border_frame.pack(fill="both", expand=True)

        self.inner_frame = tk.Frame(self.border_frame, bg=BG_BLACK, highlightthickness=0)
        self.inner_frame.pack(fill="both", expand=True, padx=3, pady=3)

        self.header_frame = tk.Frame(self.inner_frame, bg=GOLD_BRIGHT, height=40, highlightthickness=0)
        self.header_frame.pack(fill="x")
        self.header_frame.pack_propagate(False)

        self.toggle_label = tk.Label(
            self.header_frame,
            text="ƒ-¬",
            bg=GOLD_BRIGHT,
            fg=BG_BLACK,
            font=("Consolas", 12, "bold"),
            width=3,
            cursor="hand2",
        )
        self.toggle_label.pack(side="left", padx=10)

        self.symbol_label = tk.Label(
            self.header_frame,
            text=symbol,
            bg=GOLD_BRIGHT,
            fg=BG_BLACK,
            font=("Consolas", 16, "bold"),
            cursor="hand2",
        )
        self.symbol_label.pack(side="left", padx=5)

        self.title_label = tk.Label(
            self.header_frame,
            text=title,
            bg=GOLD_BRIGHT,
            fg=BG_BLACK,
            font=FONT_HEADER,
            cursor="hand2",
        )
        self.title_label.pack(side="left", padx=10, fill="x", expand=True)

        self.header_frame.bind("<Button-1>", self._toggle)
        self.toggle_label.bind("<Button-1>", self._toggle)
        self.symbol_label.bind("<Button-1>", self._toggle)
        self.title_label.bind("<Button-1>", self._toggle)

        self.content_frame = tk.Frame(self.inner_frame, bg=BG_BLACK, highlightthickness=0)
        self.content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.text_widget = tk.Text(
            self.content_frame,
            bg=BG_BLACK,
            fg=GOLD_BRIGHT,
            font=FONT_MONO_SMALL,
            height=10,
            wrap="word",
            relief="flat",
            bd=0,
            insertbackground=GOLD_BRIGHT,
        )
        self.text_widget.pack(fill="both", expand=True, side="left")

        scrollbar = tk.Scrollbar(self.content_frame, command=self.text_widget.yview)
        scrollbar.pack(side="right", fill="y")
        self.text_widget.config(yscrollcommand=scrollbar.set)
        self.text_widget.config(state="disabled")

        self._animate_symbol()

    def _toggle(self, _event=None):
        self.is_expanded = not self.is_expanded

        if self.is_expanded:
            self.toggle_label.configure(text="ƒ-¬")
            self.content_frame.pack(fill="both", expand=True, padx=10, pady=10)
        else:
            self.toggle_label.configure(text="ƒ-")
            self.content_frame.pack_forget()

    def update_content(self, text: str):
        self.text_widget.config(state="normal")
        self.text_widget.delete("1.0", "end")
        self.text_widget.insert("1.0", text)
        self.text_widget.config(state="disabled")

    def _animate_symbol(self):
        try:
            colors = [BG_BLACK, "#1A1A00"]
            current = self.symbol_label.cget("fg")
            next_color = colors[1] if current == colors[0] else colors[0]
            self.symbol_label.config(fg=next_color)
            self.after(1000, self._animate_symbol)
        except Exception:
            pass
