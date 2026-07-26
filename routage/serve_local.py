#!/usr/bin/env python3
"""Serveur local pour tester le routage hybride (statique + proxy /api/route).

Usage :
  # Option A (recommandée) : fichier local ignoré par Git
  #   echo "votre_cle" > routage/.ors_api_key
  # Option B : variable d'environnement
  #   export ORS_API_KEY="votre_cle"
  python3 routage/serve_local.py

Puis ouvrir http://127.0.0.1:8766/routage/
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROUTAGE_DIR = Path(__file__).resolve().parent
# Même port que le reste de ParkEco (appli / article)
PORT = int(os.environ.get("PORT", "8766"))
ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
KEY_FILE = ROUTAGE_DIR / ".ors_api_key"


def load_ors_api_key() -> str:
    """Clé depuis l'environnement, sinon fichier local routage/.ors_api_key (gitignored)."""
    env = (os.environ.get("ORS_API_KEY") or "").strip()
    if env:
        return env
    if KEY_FILE.is_file():
        try:
            return KEY_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return ""


def features_to_multipolygon(avoid):
    if not avoid:
        return None
    if avoid.get("type") == "MultiPolygon":
        return avoid
    if avoid.get("type") == "Polygon":
        return {"type": "MultiPolygon", "coordinates": [avoid["coordinates"]]}
    features = []
    if avoid.get("type") == "FeatureCollection":
        features = avoid.get("features") or []
    elif avoid.get("type") == "Feature":
        features = [avoid]
    polygons = []
    for f in features:
        g = (f or {}).get("geometry") or {}
        if g.get("type") == "Polygon":
            polygons.append(g["coordinates"])
        elif g.get("type") == "MultiPolygon":
            polygons.extend(g["coordinates"])
    if not polygons:
        return None
    return {"type": "MultiPolygon", "coordinates": polygons}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
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
            self.send_error(404)
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
                {
                    "error": "ORS_API_KEY manquante. Placez la clé dans routage/.ors_api_key ou exportez ORS_API_KEY."
                },
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

        payload = {
            "coordinates": [[olon, olat], [dlon, dlat]],
            "radiuses": [1200, 1200],
        }
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

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    os.chdir(ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"ParkEco routage → http://127.0.0.1:{PORT}/routage/", flush=True)
    if load_ors_api_key():
        print("✓ Clé OpenRouteService chargée", flush=True)
    else:
        print("⚠  Pas de clé — créez routage/.ors_api_key ou export ORS_API_KEY=...", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.", flush=True)


if __name__ == "__main__":
    main()
