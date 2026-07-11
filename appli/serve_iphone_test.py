#!/usr/bin/env python3
"""Serveur local pour tester ParkEco sur iPhone (même Wi‑Fi).

Usage HTTPS (certificat auto-signé, souvent bloqué par Safari iOS) :
  python3 serve_iphone_test.py 8767 cert.pem key.pem [root]

Usage HTTP (recommandé pour iPhone) :
  python3 serve_iphone_test.py --http 8768 [root]
"""
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


def serve_http(port: int, root: str) -> None:
    os.chdir(root)
    with socketserver.TCPServer(("0.0.0.0", port), ParkEcoRequestHandler) as httpd:
        httpd.serve_forever()


def serve_https(port: int, cert: str, key: str, root: str) -> None:
    os.chdir(root)
    with socketserver.TCPServer(("0.0.0.0", port), ParkEcoRequestHandler) as httpd:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        httpd.serve_forever()


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--http":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8768
        root = sys.argv[3] if len(sys.argv) > 3 else os.getcwd()
        serve_http(port, root)
        return

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8767
    cert = sys.argv[2]
    key = sys.argv[3]
    root = sys.argv[4] if len(sys.argv) > 4 else os.getcwd()
    serve_https(port, cert, key, root)


if __name__ == "__main__":
    main()
