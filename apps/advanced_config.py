from __future__ import annotations

import customtkinter as ctk


def build_advanced_config(parent):
    """
    Build an advanced scan configuration panel with intensity, nmap profile, and nuclei tag filters.
    Returns (frame, state) where state holds control variables.
    """
    frame = ctk.CTkFrame(parent, corner_radius=8, fg_color="transparent")
    for col in range(3):
        frame.grid_columnconfigure(col, weight=1, uniform="cfg")

    state = {}

    # Scan Intensity
    intensity_label = ctk.CTkLabel(frame, text="Requests Per Second", anchor="w")
    intensity_label.grid(row=0, column=0, sticky="w", padx=8, pady=(6, 2))

    rps_var = ctk.IntVar(value=50)
    rps_value_lbl = ctk.CTkLabel(frame, text=str(rps_var.get()), width=40, anchor="e")
    rps_value_lbl.grid(row=0, column=2, sticky="e", padx=8, pady=(6, 2))

    def _on_rps_change(val):
        rps_value_lbl.configure(text=str(int(float(val))))
        rps_var.set(int(float(val)))

    rps_slider = ctk.CTkSlider(
        frame, from_=1, to=100, number_of_steps=99, command=_on_rps_change
    )
    rps_slider.set(rps_var.get())
    rps_slider.grid(row=0, column=1, sticky="ew", padx=6, pady=(6, 2))
    state["rps"] = rps_var

    # Nmap Profile
    nmap_label = ctk.CTkLabel(frame, text="Nmap Profile", anchor="w")
    nmap_label.grid(row=1, column=0, sticky="w", padx=8, pady=(6, 2))

    profiles = ["Quick (Top 100)", "Standard (Top 1000)", "Full Range (0-65535)", "Stealth (SYN only)"]
    nmap_var = ctk.StringVar(value=profiles[1])
    nmap_menu = ctk.CTkOptionMenu(frame, values=profiles, variable=nmap_var)
    nmap_menu.grid(row=1, column=1, columnspan=2, sticky="ew", padx=6, pady=(6, 2))
    state["nmap_profile"] = nmap_var

    # Nuclei Filters
    filters_label = ctk.CTkLabel(frame, text="Nuclei Filters", anchor="w")
    filters_label.grid(row=2, column=0, sticky="w", padx=8, pady=(10, 2))

    tags = ["CVEs", "Misconfigurations", "Default Logins", "Exposed Tokens"]
    filter_vars = {}
    filters_frame = ctk.CTkFrame(frame, fg_color="transparent")
    filters_frame.grid(row=2, column=1, columnspan=2, sticky="ew", padx=6, pady=(6, 8))
    for i, tag in enumerate(tags):
        var = ctk.BooleanVar(value=True)
        cb = ctk.CTkCheckBox(filters_frame, text=tag, variable=var)
        cb.grid(row=i // 2, column=i % 2, sticky="w", padx=6, pady=2)
        filter_vars[tag] = var
    state["nuclei_filters"] = filter_vars

    return frame, state
