from __future__ import annotations

import customtkinter as ctk


def create_asset_table(parent):
    """
    Build a scrollable, spreadsheet-style asset table with dummy data populated.
    Returns (frame, add_asset_row) so callers can add more rows.
    """
    table = ctk.CTkScrollableFrame(parent, fg_color="transparent")

    headers = ["Asset", "Status", "Tech Stack", "Open Ports"]
    for col, title in enumerate(headers):
        lbl = ctk.CTkLabel(
            table,
            text=title,
            font=("Consolas", 12, "bold"),
            anchor="w",
        )
        lbl.grid(row=0, column=col, sticky="nsew", padx=(4 if col else 0, 4), pady=(2, 6))
        table.grid_columnconfigure(col, weight=1, uniform="asset_cols")

    row_idx = {"value": 1}

    def add_asset_row(url: str, status: str, tech: str, ports: str) -> None:
        color = None
        status_clean = (status or "").strip()
        status_code = status_clean.split()[0] if status_clean else ""
        if status_code == "200":
            color = "#3EC16F"
        elif status_code in ("403", "500"):
            color = "#E24C4B"
        elif status_code == "404":
            color = "#A0A0A0"

        row = row_idx["value"]
        ctk.CTkLabel(table, text=url, anchor="w").grid(row=row, column=0, sticky="nsew", padx=(4, 4), pady=2)
        ctk.CTkLabel(table, text=status, anchor="w", text_color=color).grid(
            row=row, column=1, sticky="nsew", padx=(4, 4), pady=2
        )
        ctk.CTkLabel(table, text=tech, anchor="w").grid(row=row, column=2, sticky="nsew", padx=(4, 4), pady=2)
        ctk.CTkLabel(table, text=ports, anchor="w").grid(row=row, column=3, sticky="nsew", padx=(4, 4), pady=2)
        row_idx["value"] += 1

    # Dummy rows to seed the table
    sample_rows = [
        ("api.scopely.com", "200 OK", "Nginx/1.18", "80, 443"),
        ("admin.scopely.com", "403 Forbidden", "Cloudflare", "443"),
        ("dev.scopely.com", "404 Not Found", "Unknown", "-"),
        ("jenkins.scopely.com", "200 OK", "Jenkins 2.452", "8080"),
        ("cdn.scopely.com", "500 Server Error", "Varnish", "80, 443"),
    ]
    for url, status, tech, ports in sample_rows:
        add_asset_row(url, status, tech, ports)

    return table, add_asset_row
