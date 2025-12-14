from typing import Protocol

import tkinter as tk


class Panel(Protocol):
    def update_content(self, text: str) -> None:
        ...


def set_text(widget: tk.Text, text: str) -> None:
    """Utility to safely replace all text content in a tk.Text widget."""
    widget.config(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", text)
    widget.config(state="disabled")
