#!/usr/bin/env python3
"""Serveur HTTPS local pour tester ParkEco sur iPhone (même Wi‑Fi)."""
import http.server
import os
import socketserver
import ssl
import sys

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    cert = sys.argv[2]
    key = sys.argv[3]
    root = sys.argv[4] if len(sys.argv) > 4 else os.getcwd()
    os.chdir(root)
    with socketserver.TCPServer(("0.0.0.0", port), http.server.SimpleHTTPRequestHandler) as httpd:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        httpd.serve_forever()

if __name__ == "__main__":
    main()
