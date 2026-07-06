#!/usr/bin/env python3
"""Télécharge et filtre les secteurs Paris Respire (open data Ville de Paris).

Conserve uniquement les secteurs de quartiers intra-muros (exclut Bois de Boulogne
et Bois de Vincennes, hors périmètre utile ParkEco).
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chemins_projet import DATA_DIR

SOURCE_URL = (
    "https://opendata.paris.fr/api/explore/v2.1/catalog/"
    "datasets/secteurs-paris-respire/exports/geojson?limit=-1"
)
OUT = DATA_DIR / "paris_respire_secteurs.geojson"

# Paris intra-muros (approx.) : ouest, sud, est, nord
PARIS_BBOX = (2.252, 48.815, 2.422, 48.902)


def is_urban_paris_respire_sector(props: dict) -> bool:
    nom = (props.get("nom") or "").strip()
    if nom.startswith("Bois de "):
        return False
    pt = props.get("geo_point_2d") or {}
    lat, lon = pt.get("lat"), pt.get("lon")
    if lat is None or lon is None:
        return True
    west, south, east, north = PARIS_BBOX
    return west <= lon <= east and south <= lat <= north


def filter_geojson(data: dict) -> dict:
    features = [
        f for f in data.get("features", [])
        if is_urban_paris_respire_sector(f.get("properties") or {})
    ]
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    print(f"Téléchargement : {SOURCE_URL}")
    with urllib.request.urlopen(SOURCE_URL, timeout=120) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    filtered = filter_geojson(raw)
    OUT.write_text(json.dumps(filtered, ensure_ascii=False), encoding="utf-8")
    print(
        f"Écrit : {OUT} — {len(filtered['features'])} secteurs "
        f"(sur {len(raw.get('features', []))} bruts)"
    )


if __name__ == "__main__":
    main()
