#!/usr/bin/env python3
"""Serveur local pour tester ParkEco sur iPhone (même Wi‑Fi).

Usage HTTP (recommandé pour iPhone) :
  python3 serve_iphone_test.py --http 8768 [root]

Inclut POST /api/route (OpenRouteService) comme routage/serve_local.py.
"""
from __future__ import annotations

import http.server
import json
import os
import socketserver
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Réutilise la logique clé / polygones du serveur routage
ROOT_DEFAULT = Path(__file__).resolve().parent.parent
if str(ROOT_DEFAULT) not in sys.path:
    sys.path.insert(0, str(ROOT_DEFAULT / "routage"))
try:
    from serve_local import (  # type: ignore
        ORS_URL,
        features_to_multipolygon,
        load_ors_api_key,
    )
except ImportError:
    # Fallback si import relative échoue : chemins absolus
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "serve_local", ROOT_DEFAULT / "routage" / "serve_local.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    ORS_URL = mod.ORS_URL
    features_to_multipolygon = mod.features_to_multipolygon
    load_ors_api_key = mod.load_ors_api_key


class ParkEcoRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Désactive le cache agressif de Safari iOS ; proxy /api/route."""

    def end_headers(self):
        path = self.path.split("?", 1)[0].lower()
        if path.endswith((".html", ".js", ".json")) or path in ("", "/"):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_OPTIONS(self):
        if self.path.split("?", 1)[0] == "/api/route":
            self.send_response(204)
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            return
        self.send_error(404)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path != "/api/route":
            self.send_error(501, "Unsupported method ('POST')")
            return

        key = load_ors_api_key()
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._json(400, {"error": "JSON invalide"})
            return

        if not key:
            self._json(
                503,
                {"error": "Clé OpenRouteService manquante (routage/.ors_api_key)."},
            )
            return

        origin = body.get("origin") or {}
        dest = body.get("destination") or {}
        try:
            olat, olon = float(origin["lat"]), float(origin["lon"])
            dlat, dlon = float(dest["lat"]), float(dest["lon"])
        except (KeyError, TypeError, ValueError):
            self._json(400, {"error": "origin et destination {lat, lon} requis"})
            return

        payload = {"coordinates": [[olon, olat], [dlon, dlat]], "radiuses": [1200, 1200]}
        avoid = features_to_multipolygon(body.get("avoid"))
        if avoid:
            payload["options"] = {"avoid_polygons": avoid}

        req = urllib.request.Request(
            ORS_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": key,
                "Content-Type": "application/json",
                "Accept": "application/json, application/geo+json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(detail)
                msg = (
                    (parsed.get("error") or {}).get("message")
                    if isinstance(parsed.get("error"), dict)
                    else parsed.get("error")
                ) or detail[:300]
            except json.JSONDecodeError:
                msg = detail[:300]
            self._json(502, {"error": str(msg)})
            return
        except Exception as e:
            self._json(502, {"error": f"Erreur réseau ORS: {e}"})
            return

        feature = (data.get("features") or [None])[0]
        if not feature or not feature.get("geometry"):
            self._json(502, {"error": "Itinéraire vide"})
            return
        summary = (feature.get("properties") or {}).get("summary") or {}
        self._json(
            200,
            {
                "coordinates": feature["geometry"]["coordinates"],
                "distanceM": summary.get("distance"),
                "durationS": summary.get("duration"),
            },
        )

    def _json(self, code: int, obj: dict):
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def serve_http(port: int, root: str) -> None:
    os.chdir(root)
    with socketserver.ThreadingTCPServer(("0.0.0.0", port), ParkEcoRequestHandler) as httpd:
        key_ok = bool(load_ors_api_key())
        print(f"ParkEco iPhone → http://0.0.0.0:{port}/  (routage: /routage/)", flush=True)
        print(
            "✓ Clé ORS chargée" if key_ok else "⚠ Pas de clé ORS (routage/.ors_api_key)",
            flush=True,
        )
        httpd.serve_forever()


def serve_https(port: int, cert: str, key: str, root: str) -> None:
    os.chdir(root)
    with socketserver.ThreadingTCPServer(("0.0.0.0", port), ParkEcoRequestHandler) as httpd:
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
