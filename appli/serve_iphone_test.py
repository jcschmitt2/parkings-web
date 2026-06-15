#!/usr/bin/env python3
"""Serveur HTTPS local pour tester ParkEco sur iPhone (même Wi‑Fi)."""
from __future__ import annotations

import http.server
import os
import socketserver
import ssl
import sys


class ParkEcoRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Désactive le cache agressif de Safari iOS sur HTML/JS/JSON."""

    def end_headers(self):
        path = self.path.split("?", 1)[0].lower()
        if path.endswith((".html", ".js", ".json")) or path in ("", "/"):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8767
    cert = sys.argv[2]
    key = sys.argv[3]
    root = sys.argv[4] if len(sys.argv) > 4 else os.getcwd()
    os.chdir(root)
    with socketserver.TCPServer(("0.0.0.0", port), ParkEcoRequestHandler) as httpd:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
