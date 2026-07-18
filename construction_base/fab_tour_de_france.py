#!/usr/bin/env python3
"""Construit donnée/tour_de_france_2026_zones.geojson — périmètres approximés
pour l'arrivée du Tour de France à Paris.

⚠️ IMPORTANT — géométrie PROVISOIRE :
Les données officielles 2026 (arrêté préfectoral, date exacte, tracé exact)
n'étaient pas encore publiées à la création de ce script. Les polygones
ci-dessous reproduisent, en version approximative, le tracé de l'édition 2025
(source : paris.fr, arrivée du 27 juillet 2025 — Champs-Élysées + boucle
Montmartre) afin de permettre un premier outil de test.

À corriger dès la publication de l'arrêté préfectoral 2026 :
- date exacte de l'arrivée
- tracé exact (le parcours peut changer chaque année)
- horaires précis d'activation/désactivation par secteur

Source documentaire (édition 2025, reprise à titre d'approximation) :
- https://www.paris.fr/pages/les-restrictions-de-circulation-et-de-stationnement-pour-le-tour-de-france-2025-31895
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chemins_projet import DATA_DIR

OUT = DATA_DIR / "tour_de_france_2026_zones.geojson"

# Date d'arrivée 2026 (article ParkEco) — horaires encore approximés (base 2025)
EVENT_DAY = "2026-07-26"
EVENT_DATE_NOTE = "26 juillet 2026 (horaires de secteurs approximés d'après l'édition 2025 — à confirmer par arrêté)"


def schedule_props(start_hhmm: str, end_hhmm: str) -> dict:
    """Horaires structurés (heure murale Europe/Paris) pour filtrage côté appli."""
    return {
        "source": "tour_de_france",
        "active_start": f"{EVENT_DAY}T{start_hhmm}",
        "active_end": f"{EVENT_DAY}T{end_hhmm}",
        "tz": "Europe/Paris",
    }


def buffer_polyline(points: list[tuple[float, float]], width_m: float) -> list[list[float]]:
    """Transforme une ligne centrale (lon, lat) en polygone "saucisse" de largeur width_m.

    Approximation simple (pas de vrai calcul géodésique, suffisant à l'échelle de Paris) :
    on convertit en mètres via une projection équirectangulaire locale, on décale
    perpendiculairement à chaque segment, puis on reconvertit en lon/lat.
    """
    lat0 = sum(p[1] for p in points) / len(points)
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat0))

    def to_xy(lon: float, lat: float) -> tuple[float, float]:
        return (lon * m_per_deg_lon, lat * m_per_deg_lat)

    def to_lonlat(x: float, y: float) -> list[float]:
        return [x / m_per_deg_lon, y / m_per_deg_lat]

    xy = [to_xy(lon, lat) for lon, lat in points]
    half = width_m / 2.0

    left_side: list[tuple[float, float]] = []
    right_side: list[tuple[float, float]] = []

    for i in range(len(xy) - 1):
        x1, y1 = xy[i]
        x2, y2 = xy[i + 1]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length * half, dx / length * half
        left_side.append((x1 + nx, y1 + ny))
        left_side.append((x2 + nx, y2 + ny))
        right_side.append((x1 - nx, y1 - ny))
        right_side.append((x2 - nx, y2 - ny))

    ring_xy = left_side + list(reversed(right_side))
    ring_xy.append(ring_xy[0])
    return [to_lonlat(x, y) for x, y in ring_xy]


# --- Zone A : Étoile / Champs-Élysées / Concorde / Madeleine / Louvre / quais ---
ZONE_A_RING = [
    [2.2950, 48.8745],  # Place Charles-de-Gaulle (Étoile)
    [2.3260, 48.8790],  # Boulevard Malesherbes, niveau Madeleine
    [2.3370, 48.8660],  # Louvre / rue de Rivoli, côté nord
    [2.3370, 48.8580],  # Louvre / quai François-Mitterrand, côté sud
    [2.3130, 48.8560],  # Quai d'Orsay / Pont Alexandre-III
    [2.2950, 48.8560],  # Quai Branly
    [2.2760, 48.8420],  # Quai d'Issy-les-Moulineaux / Quai André-Citroën
    [2.2850, 48.8620],  # Quai de Grenelle
    [2.2950, 48.8745],  # fermeture (Étoile)
]

# --- Zone B : corridor Malesherbes → Courcelles → Batignolles → Clichy ---
ZONE_B_CENTERLINE = [
    (2.3246, 48.8790),  # Boulevard Malesherbes, niveau Madeleine
    (2.3090, 48.8800),  # Boulevard de Courcelles
    (2.3140, 48.8828),  # Boulevard des Batignolles
    (2.3268, 48.8830),  # Place de Clichy
]
ZONE_B_RING = buffer_polyline(ZONE_B_CENTERLINE, width_m=260)

# --- Zone C : boucle Montmartre (Clichy / Blanche / butte) ---
ZONE_C_RING = [
    [2.3268, 48.8830],  # Place de Clichy
    [2.3325, 48.8838],  # Place Blanche
    [2.3360, 48.8850],  # Rue Lepic (milieu)
    [2.3431, 48.8867],  # Sacré-Cœur / butte
    [2.3400, 48.8882],  # Rue Caulaincourt / Lamarck (nord)
    [2.3300, 48.8865],  # Rue Norvins / Coustou
    [2.3268, 48.8830],  # fermeture (Place de Clichy)
]


def polygon_feature(ring: list, props: dict) -> dict:
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


def build_geojson() -> dict:
    common = {
        "type": "circulation_interdite",
        "exclure_recherche": True,
    }
    return {
        "type": "FeatureCollection",
        "name": "tour_de_france_2026_paris",
        "metadata": {
            "source": (
                "Périmètres approximés ParkEco, basés sur le tracé de l'arrivée "
                "du Tour de France à Paris le 27 juillet 2025 (paris.fr). "
                "Géométrie et horaires 2026 à confirmer dès publication de "
                "l'arrêté préfectoral."
            ),
            "event_date": EVENT_DATE_NOTE,
            "event_day": EVENT_DAY,
            "provisoire": True,
            "official_info": (
                "https://www.paris.fr/pages/les-restrictions-de-circulation-et-de"
                "-stationnement-pour-le-tour-de-france-2025-31895"
            ),
        },
        "features": [
            polygon_feature(
                ZONE_A_RING,
                {
                    **common,
                    **schedule_props("06:00", "23:59"),
                    "zone_id": "champs_elysees_concorde_louvre",
                    "nom": "Champs-Élysées — Concorde — Étoile — Madeleine — Louvre",
                    "horaires": "Dimanche 26 juillet 2026, 6 h à 23 h 59 (approx. — à confirmer)",
                    "description": (
                        "Périmètre central de l'arrivée : Étoile, avenue des Champs-Élysées, "
                        "place de la Concorde, place de la Madeleine, Louvre et quais proches. "
                        "Circulation interdite aux véhicules motorisés."
                    ),
                },
            ),
            polygon_feature(
                ZONE_B_RING,
                {
                    **common,
                    **schedule_props("09:00", "23:59"),
                    "zone_id": "malesherbes_batignolles",
                    "nom": "Corridor Malesherbes — Courcelles — Batignolles — Clichy",
                    "horaires": "Dimanche 26 juillet 2026, 9 h à 23 h 59 (approx. — à confirmer)",
                    "description": (
                        "Axe de liaison entre le secteur Madeleine et le secteur Montmartre : "
                        "boulevards Malesherbes, de Courcelles, des Batignolles, jusqu'à la "
                        "place de Clichy. Circulation interdite aux véhicules motorisés."
                    ),
                },
            ),
            polygon_feature(
                ZONE_C_RING,
                {
                    **common,
                    **schedule_props("13:00", "20:30"),
                    "zone_id": "montmartre",
                    "nom": "Boucle Montmartre — Clichy — Blanche — Butte",
                    "horaires": "Dimanche 26 juillet 2026, 13 h à 20 h 30 (approx. — à confirmer)",
                    "description": (
                        "Boucle empruntée trois fois par la course : place de Clichy, place "
                        "Blanche, rues Lepic, Norvins, Coustou, Puget et la butte Montmartre. "
                        "Circulation interdite aux véhicules motorisés, piétons filtrés."
                    ),
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
