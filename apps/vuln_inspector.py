from __future__ import annotations

import customtkinter as ctk


SEVERITY_COLORS = {
    "CRITICAL": "#B32224",
    "HIGH": "#D7431A",
    "MEDIUM": "#D99A1A",
    "LOW": "#5A9BD5",
    "INFO": "#4B5563",
}


def build_vuln_inspector(parent, severity: str = "CRITICAL"):
    """
    Build a vulnerability inspector widget with request/response tabs,
    severity badge, and a copy-to-clipboard action.
    """
    frame = ctk.CTkFrame(parent, fg_color="transparent")

    tab = ctk.CTkTabview(frame, fg_color="transparent")
    tab.add("Request")
    tab.add("Response")
    tab.pack(fill="both", expand=True, pady=(0, 8))

    mono = ("Consolas", 11)

    request_box = ctk.CTkTextbox(tab.tab("Request"), font=mono, width=600, height=250)
    request_box.pack(fill="both", expand=True, padx=6, pady=6)

    response_box = ctk.CTkTextbox(tab.tab("Response"), font=mono, width=600, height=250)
    response_box.pack(fill="both", expand=True, padx=6, pady=6)

    sample_request = (
        "POST /login HTTP/1.1\n"
        "Host: target.internal\n"
        "Content-Type: application/x-www-form-urlencoded\n"
        "User-Agent: Glauka/Inspector\n"
        "Content-Length: 42\n"
        "\n"
        "username=admin&password=admin' OR '1'='1"
    )
    sample_response = (
        "HTTP/1.1 200 OK\n"
        "Server: nginx/1.18.0\n"
        "Content-Type: text/html; charset=UTF-8\n"
        "Content-Length: 512\n"
        "\n"
        "<html><body><h1>Welcome admin</h1></body></html>"
    )

    request_box.insert("1.0", sample_request)
    response_box.insert("1.0", sample_response)

    # Controls under the tabs
    controls = ctk.CTkFrame(frame, fg_color="transparent")
    controls.pack(fill="x", expand=False, padx=4, pady=(0, 4))

    severity_norm = severity.upper().strip()
    bg = SEVERITY_COLORS.get(severity_norm, "#4B5563")
    severity_lbl = ctk.CTkLabel(
        controls,
        text=severity_norm,
        fg_color=bg,
        corner_radius=6,
        font=("Consolas", 12, "bold"),
        padx=10,
        pady=6,
    )
    severity_lbl.pack(side="left", padx=(2, 8))

    def copy_curl():
        curl_cmd = (
            "curl -X POST https://target.internal/login "
            "-H 'Content-Type: application/x-www-form-urlencoded' "
            "-d \"username=admin&password=admin' OR '1'='1\""
        )
        frame.clipboard_clear()
        frame.clipboard_append(curl_cmd)

    copy_btn = ctk.CTkButton(controls, text="Copy cURL to Clipboard", command=copy_curl)
    copy_btn.pack(side="left")

    return frame, request_box, response_box, severity_lbl, copy_btn
