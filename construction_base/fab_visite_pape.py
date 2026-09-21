#!/usr/bin/env python3
"""Construit donnée/visite_pape_2026_zones.geojson — périmètres de la visite
du pape Léon XIV à Paris (24–26 septembre 2026).

Source : Préfecture de police — Voyage apostolique, périmètres.
https://www.prefecturedepolice.interieur.gouv.fr/actualites-et-presse/actualites/evenement/voyage-apostolique-les-perimetres

Les polygones sont des approximations ParkEco des secteurs officiels
(papamobile, Notre-Dame, UNESCO, Concorde). Le Stade de France
est à Saint-Denis, hors Paris : il n'est pas inclus.

Après modification : python3 construction_base/fab_visite_pape.py
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

OUT = DATA_DIR / "visite_pape_2026_zones.geojson"
SOURCE_URL = (
    "https://www.prefecturedepolice.interieur.gouv.fr/actualites-et-presse/"
    "actualites/evenement/voyage-apostolique-les-perimetres"
)

J24 = "2026-09-24"
J25 = "2026-09-25"
J26 = "2026-09-26"


def buffer_polyline(points: list[tuple[float, float]], width_m: float) -> list[list[float]]:
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


def close_ring(ring: list) -> list:
    pts = [list(p) for p in ring]
    if not pts:
        return pts
    if pts[0] != pts[-1]:
        pts.append(pts[0][:])
    return pts


def ring_signed_area(ring: list) -> float:
    closed = close_ring(ring)
    area = 0.0
    for i in range(len(closed) - 1):
        area += closed[i][0] * closed[i + 1][1] - closed[i + 1][0] * closed[i][1]
    return area / 2.0


def ring_ccw(ring: list) -> list:
    """GeoJSON / ORS : anneau extérieur dans le sens anti-horaire."""
    closed = close_ring(ring)
    if ring_signed_area(closed) < 0:
        closed = list(reversed(closed))
    return closed


def polygon_feature(ring: list, props: dict) -> dict:
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Polygon", "coordinates": [ring_ccw(ring)]},
    }


def zone_props(
    zone_id: str,
    nom: str,
    horaires: str,
    description: str,
    jours: list[str],
    *,
    zone_type: str = "circulation_interdite",
    circulation_start: str | None = None,
    circulation_end: str | None = None,
) -> dict:
    props = {
        "source": "visite_pape",
        "type": zone_type,
        "exclure_recherche": True,
        "zone_id": zone_id,
        "nom": nom,
        "horaires": horaires,
        "description": description,
        "jours": jours,
        "tz": "Europe/Paris",
        "active_start": f"{jours[0]}T00:00",
        "active_end": f"{jours[-1]}T23:59",
    }
    if circulation_start:
        props["circulation_start"] = circulation_start
    if circulation_end:
        props["circulation_end"] = circulation_end
    return props


# Papamobile : Notre-Dame-des-Champs → Saint-Michel
PAPAMOBILE_RING = buffer_polyline(
    [
        (2.3275, 48.8436),  # Notre-Dame-des-Champs
        (2.3328, 48.8434),  # boulevard du Montparnasse
        (2.3378, 48.8428),  # Vavin
        (2.3395, 48.8455),  # vers Luxembourg
        (2.3398, 48.8478),  # Luxembourg
        (2.3432, 48.8500),  # boulevard Saint-Michel
        (2.3440, 48.8534),  # place Saint-Michel
    ],
    width_m=220,
)

# Île de la Cité, partie île Saint-Louis, quais (Arts → Tournelle / Marie)
NOTRE_DAME_RING = [
    [2.3372, 48.8586],  # pont des Arts
    [2.3418, 48.8592],  # quai du Louvre
    [2.3465, 48.8578],  # Châtelet / quai de Gesvres
    [2.3518, 48.8554],  # Hôtel de Ville
    [2.3574, 48.8528],  # pont Marie
    [2.3586, 48.8515],  # île Saint-Louis est
    [2.3548, 48.8498],  # pont de la Tournelle
    [2.3478, 48.8504],  # quai de la Tournelle
    [2.3442, 48.8528],  # quai Saint-Michel
    [2.3408, 48.8546],  # Grands Augustins
    [2.3388, 48.8566],  # pont Neuf sud
    [2.3372, 48.8586],
]

# UNESCO / Fontenoy / Suffren / Ségur (7e-15e)
UNESCO_FONTENOY_RING = [
    [2.3004, 48.8522],  # Suffren / École militaire
    [2.3010, 48.8472],  # Suffren / Garibaldi
    [2.3062, 48.8466],  # Ségur sud
    [2.3136, 48.8474],  # Saxe / Breteuil
    [2.3142, 48.8506],  # Lowendal / Duquesne
    [2.3098, 48.8526],  # Duquesne
    [2.3004, 48.8522],
]

# UNESCO intérieur : Invalides / Vauban / Ségur
UNESCO_INVALIDES_RING = [
    [2.3118, 48.8582],  # Invalides / Grenelle
    [2.3126, 48.8534],  # Invalides / Sèvres
    [2.3172, 48.8516],  # Sèvres / Vauban
    [2.3206, 48.8532],  # place Vauban
    [2.3184, 48.8568],  # Tourville
    [2.3118, 48.8582],
]

# Concorde / bas des Champs — montage (dès le 16 sept., encore le 24)
CONCORDE_MONTAGE_RING = [
    [2.3196, 48.8674],  # rue Royale
    [2.3232, 48.8668],
    [2.3238, 48.8654],  # Concorde est
    [2.3212, 48.8636],  # Concorde sud
    [2.3178, 48.8646],  # Cours la Reine
    [2.3102, 48.8682],  # Clemenceau
    [2.3116, 48.8700],  # jardins des Champs
    [2.3196, 48.8674],
]

# Messe Concorde : périmètre élargi (les deux côtés des Champs, 8e, quais / ponts du 7e)
CONCORDE_MESSE_RING = [
    [2.2936, 48.8762],  # Étoile nord
    [2.3040, 48.8752],  # Friedland / Haussmann
    [2.3150, 48.8738],  # Saint-Honoré
    [2.3252, 48.8724],  # Madeleine
    [2.3272, 48.8682],  # rue Royale
    [2.3254, 48.8638],  # Concorde est
    [2.3232, 48.8604],  # Assemblée / quai
    [2.3180, 48.8576],  # Invalides
    [2.3048, 48.8598],  # Alma / Bourdonnais
    [2.2976, 48.8636],  # Iéna
    [2.2926, 48.8696],  # Kléber
    [2.2922, 48.8738],  # Étoile ouest
    [2.2936, 48.8762],
]


def build_geojson() -> dict:
    features = [
        polygon_feature(
            PAPAMOBILE_RING,
            zone_props(
                "papamobile_nd_des_champs_saint_michel",
                "Déambulation papamobile — Notre-Dame-des-Champs → Saint-Michel",
                "Stationnement : 24 sept. 11 h – 25 sept. 20 h. Circulation : 25 sept. 6 h – 20 h.",
                "Périmètre de la déambulation (5e, 6e, 14e). Accès riverains sur justificatif.",
                [J24, J25],
                circulation_start=f"2026-09-25T06:00",
                circulation_end=f"2026-09-25T20:00",
            ),
        ),
        polygon_feature(
            NOTRE_DAME_RING,
            zone_props(
                "notre_dame_ile_de_la_cite",
                "Notre-Dame — île de la Cité et quais",
                "Stationnement : 24 sept. 11 h – 25 sept. 20 h. Circulation : 25 sept. 6 h – 20 h.",
                "Île de la Cité, une partie de l'île Saint-Louis et les quais jusqu'aux ponts des Arts, de la Tournelle et Marie.",
                [J24, J25],
                circulation_start=f"2026-09-25T06:00",
                circulation_end=f"2026-09-25T20:00",
            ),
        ),
        polygon_feature(
            UNESCO_FONTENOY_RING,
            zone_props(
                "unesco_fontenoy_segur",
                "UNESCO — Fontenoy / Suffren / Ségur",
                "Stationnement dès le 24 sept. 11 h ou 22 h. Circulation le 25 sept. 13 h – 18 h.",
                "Abords de l'UNESCO dans le 7e et rues limitrophes du 15e.",
                [J24, J25],
                circulation_start=f"2026-09-25T13:00",
                circulation_end=f"2026-09-25T18:00",
            ),
        ),
        polygon_feature(
            UNESCO_INVALIDES_RING,
            zone_props(
                "unesco_invalides_vauban",
                "UNESCO — Invalides / Vauban / Ségur",
                "Stationnement : 24 sept. 11 h – 25 sept. 16 h 30. Circulation : 25 sept. 14 h 30 – 16 h 30.",
                "Second périmètre autour des Invalides, de la place Vauban et de l'avenue de Ségur.",
                [J24, J25],
                circulation_start=f"2026-09-25T14:30",
                circulation_end=f"2026-09-25T16:30",
            ),
        ),
        polygon_feature(
            CONCORDE_MONTAGE_RING,
            zone_props(
                "concorde_montage",
                "Place de la Concorde — montage de la scène",
                "Restrictions dès le 16 septembre ; bas des Champs-Élysées et Concorde encore fermés le 24 septembre.",
                "Place de la Concorde, rue Royale et bas de l'avenue des Champs-Élysées (Clemenceau → Concorde).",
                [J24],
                zone_type="stationnement_interdit",
            ),
        ),
        polygon_feature(
            CONCORDE_MESSE_RING,
            zone_props(
                "concorde_messe",
                "Messe place de la Concorde et Champs-Élysées",
                "Stationnement : 25 sept. 14 h – 26 sept. 20 h. Circulation élargie : 25 sept. 22 h – 26 sept. 20 h.",
                "Périmètre de la messe en plein air : Concorde, Champs-Élysées, 8e, quais et ponts du 7e.",
                [J25, J26],
                circulation_start=f"2026-09-25T22:00",
                circulation_end=f"2026-09-26T20:00",
            ),
        ),
    ]
    return {
        "type": "FeatureCollection",
        "name": "visite_pape_2026_paris",
        "metadata": {
            "source": (
                "Préfecture de police — Voyage apostolique Léon XIV, 25-26 septembre 2026. "
                "Polygones approximatifs ParkEco des périmètres officiels."
            ),
            "source_url": SOURCE_URL,
            "event_days": [J24, J25, J26],
            "official_info": SOURCE_URL,
        },
        "features": features,
    }


def main() -> None:
    data = build_geojson()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Écrit : {OUT} — {len(data['features'])} zone(s)")


if __name__ == "__main__":
    main()
