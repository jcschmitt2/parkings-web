#!/usr/bin/env python3
"""Construit donnée/14_juillet_2026_zones.geojson à partir de l'arrêté préfectoral 2026.

Périmètre de circulation interdite (14 juillet 6 h–15 h) : polygone intérieur délimité
par les voies restées ouvertes (liste Préfecture de Police, reprise par Sortiraparis /
mairies de Paris, juillet 2026).

Source documentaire :
- https://www.sortiraparis.com/actualites/14-juillet/articles/316106-...
- Arrêté préfectoral modifiant provisoirement circulation et stationnement (2026)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chemins_projet import DATA_DIR

OUT = DATA_DIR / "14_juillet_2026_zones.geojson"

# Anneau (lon, lat) — voies limites restées ouvertes, sens horaire
CIRCULATION_RING = [
    [2.282087, 48.877633],  # Place de la Porte Maillot
    [2.289500, 48.876500],  # Avenue de Malakoff / Raymond Poincaré
    [2.285068, 48.869791],  # Place Victor Hugo
    [2.288610, 48.869267],  # Rue Copernic
    [2.292792, 48.868387],  # Place des États-Unis
    [2.293614, 48.864657],  # Place d'Iéna
    [2.292035, 48.859833],  # Pont d'Iéna
    [2.297115, 48.859583],  # Avenue de la Bourdonnais
    [2.312600, 48.856600],  # Boulevard des Invalides
    [2.318500, 48.858500],  # Rue de Grenelle
    [2.325754, 48.855182],  # Rue du Bac
    [2.329916, 48.860120],  # Pont Royal
    [2.331226, 48.862575],  # Avenue du Général Lemonnier
    [2.332508, 48.870787],  # Place de l'Opéra
    [2.319794, 48.874838],  # Boulevard Haussmann
    [2.297377, 48.877927],  # Avenue des Ternes
    [2.292000, 48.877500],  # Boulevard Pereire
    [2.282087, 48.877633],
]

# Secteur Champs-Élysées / Étoile / Concorde — stationnement interdit (approx.)
PARKING_RING = [
    [2.294800, 48.874200],
    [2.300500, 48.872800],
    [2.310000, 48.869500],
    [2.318000, 48.867000],
    [2.322000, 48.865800],
    [2.318000, 48.864500],
    [2.305000, 48.867500],
    [2.296000, 48.871000],
    [2.294800, 48.874200],
]


def polygon_feature(ring: list, props: dict) -> dict:
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


def build_geojson() -> dict:
    return {
        "type": "FeatureCollection",
        "name": "14_jillet_2026_paris",
        "metadata": {
            "source": "Arrêté préfectoral défilé 14 juillet 2026 — périmètres approximés ParkEco",
            "event_date": "2026-07-14",
            "official_info": "https://www.paris.fr/",
        },
        "features": [
            polygon_feature(
                CIRCULATION_RING,
                {
                    "zone_id": "circulation_interdite",
                    "nom": "Circulation interdite — défilé 14 juillet",
                    "type": "circulation_interdite",
                    "horaires": "Mardi 14 juillet 2026, 6 h à 15 h",
                    "description": (
                        "Périmètre intérieur où la circulation est interdite pendant le défilé "
                        "(voies limites restées ouvertes selon arrêté préfectoral)."
                    ),
                    "exclure_recherche": True,
                },
            ),
            polygon_feature(
                PARKING_RING,
                {
                    "zone_id": "stationnement_interdit",
                    "nom": "Stationnement interdit — secteur Champs-Élysées",
                    "type": "stationnement_interdit",
                    "horaires": "13 juil. 7 h – 14 juil. 15 h et 14 juil. 4 h 30 – 15 h",
                    "description": (
                        "Zone élargie de stationnement interdit autour des Champs-Élysées, "
                        "place de l'Étoile et Concorde."
                    ),
                    "exclure_recherche": False,
                },
            ),
        ],
    }


def main() -> None:
    data = build_geojson()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Écrit : {OUT} — {len(data['features'])} zone(s)")


if __name__ == "__main__":
    main()
