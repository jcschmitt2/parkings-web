#!/usr/bin/env python3
"""Construit donnée/tour_de_france_2026_zones.geojson — zones de circulation
d'après l'arrêté préfectoral 2026 (arrivée du Tour à Paris).

Source officielle :
  Arrêté n°2026-00936 du 20 juillet 2026 (Préfecture de Police)
  https://cdn.paris.fr/paris/2026/07/20/arrete-tour-de-france-2026-NUrH.pdf

Les polygones sont des approximations des périmètres / corridors listés aux
articles 4 à 13 (circulation). Les annexes cartographiques PDF ne sont pas
vectorisées : les anneaux suivent les voies citées dans le texte.

Après modification : python3 construction_base/fab_tour_de_france.py
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

EVENT_DAY = "2026-07-26"
EVENT_DATE_NOTE = (
    "26 juillet 2026 — circulation d'après arrêté préfectoral n°2026-00936 "
    "du 20 juillet 2026 (polygones approximatifs des périmètres listés)"
)
SOURCE_URL = "https://cdn.paris.fr/paris/2026/07/20/arrete-tour-de-france-2026-NUrH.pdf"


def schedule_props(start_hhmm: str, end_hhmm: str, end_day: str | None = None) -> dict:
    """Horaires muraux Europe/Paris pour filtrage côté appli / routage."""
    end = end_day or EVENT_DAY
    return {
        "source": "tour_de_france",
        "active_start": f"{EVENT_DAY}T{start_hhmm}",
        "active_end": f"{end}T{end_hhmm}",
        "tz": "Europe/Paris",
        "arrete": "2026-00936",
    }


def buffer_polyline(points: list[tuple[float, float]], width_m: float) -> list[list[float]]:
    """Ligne centrale → polygone « saucisse » (approx. équirectangulaire locale)."""
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


def polygon_feature(ring: list, props: dict) -> dict:
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


# --- Art. 4 : Cours la Reine / Churchill / Clemenceau — 00:01 → 23:59 ---
ART4_RING = buffer_polyline(
    [
        (2.3145, 48.8648),  # Cours la Reine (ouest)
        (2.3185, 48.8642),  # Winston Churchill
        (2.3210, 48.8636),  # place Clemenceau
        (2.3235, 48.8638),  # vers Concorde
    ],
    width_m=180,
)

# --- Art. 6 : Champs-Élysées (Concorde → rond-point) + Marigny — 06:00 → 23:59 ---
ART6_CHAMPS = buffer_polyline(
    [
        (2.3210, 48.8650),  # Concorde / bas des Champs
        (2.3105, 48.8690),  # Clemenceau / FDR
        (2.3035, 48.8708),  # George V
        (2.2975, 48.8725),  # vers Étoile (rond-point Marcel Dassault ~)
    ],
    width_m=120,
)
ART6_MARIGNY = buffer_polyline(
    [
        (2.3175, 48.8690),  # avenue Gabriel
        (2.3145, 48.8665),  # Marigny
        (2.3130, 48.8655),  # Champs
    ],
    width_m=90,
)

# --- Art. 7 : berges + ponts (Alma → Concorde / Tuileries) — 06:00 → 23:59 ---
ART7_RING = buffer_polyline(
    [
        (2.3015, 48.8635),  # Alma / voie Pompidou
        (2.3100, 48.8630),  # pont Alexandre III
        (2.3165, 48.8625),  # pont des Invalides
        (2.3210, 48.8628),  # pont de la Concorde
        (2.3290, 48.8615),  # quai Tuileries / Aimé Césaire
        (2.3350, 48.8605),  # pont Royal / François Mitterrand
    ],
    width_m=160,
)

# --- Art. 8 : grand périmètre Alma → Maillot → Ternes → St-Honoré → Carrousel → Concorde
#     09:00 → 23:59 (voies de contour libres sauf celles marquées fermées) ---
ART8_RING = [
    [2.3010, 48.8640],  # place de l'Alma
    [2.2980, 48.8665],  # Président Wilson
    [2.2920, 48.8685],  # États-Unis / Belloy
    [2.2870, 48.8705],  # Victor Hugo
    [2.2825, 48.8730],  # Malakoff / Poincaré
    [2.2820, 48.8775],  # porte Maillot
    [2.2900, 48.8805],  # Pereire pair / Ternes
    [2.2980, 48.8785],  # place des Ternes
    [2.3050, 48.8750],  # Faubourg Saint-Honoré / Berryer / Friedland
    [2.3180, 48.8710],  # Faubourg Saint-Honoré vers centre
    [2.3300, 48.8660],  # Saint-Honoré / Rohan
    [2.3355, 48.8615],  # place du Carrousel
    [2.3290, 48.8610],  # quais fermés (Tuileries)
    [2.3210, 48.8630],  # Concorde
    [2.3140, 48.8645],  # Cours la Reine / Canada
    [2.3050, 48.8648],  # Cours Albert 1er
    [2.3010, 48.8640],  # fermeture Alma
]

# --- Art. 9 : Montmartre — 11:00 → 20:00 ---
ART9_RING = [
    [2.3275, 48.8835],  # Clichy / Caulaincourt
    [2.3335, 48.8838],  # Blanche / Abbesses sud
    [2.3385, 48.8845],  # Martyrs / Abbesses
    [2.3435, 48.8855],  # place Saint-Pierre
    [2.3450, 48.8875],  # Sacré-Cœur / Chevalier de la Barre
    [2.3410, 48.8895],  # Lamarck / Caulaincourt nord
    [2.3350, 48.8900],  # Damrémont / Marcadet
    [2.3290, 48.8885],  # Joseph de Maistre / Carrière
    [2.3275, 48.8835],  # fermeture
]

# --- Art. 10 : Ternes / Villiers / Clichy / Haussmann / Friedland — 13:00 → 20:00 ---
ART10_RING = [
    [2.2900, 48.8805],  # Pereire / Ternes
    [2.2955, 48.8835],  # Maréchal Juin
    [2.3050, 48.8850],  # Villiers / Catroux
    [2.3150, 48.8865],  # Legendre / Clichy
    [2.3250, 48.8900],  # Saint-Ouen / Etex
    [2.3280, 48.8860],  # Barrière Blanche / Maistre
    [2.3300, 48.8840],  # Caulaincourt / Clichy
    [2.3335, 48.8835],  # Fromentin / Douai / Blanche
    [2.3280, 48.8795],  # Liège / Europe / Rome
    [2.3220, 48.8755],  # Pépinière / Saint-Augustin
    [2.3100, 48.8740],  # Haussmann / Friedland
    [2.3000, 48.8765],  # Berryer / Ternes
    [2.2900, 48.8805],  # fermeture
]

# --- Art. 11 : boulevard des Invalides (Grenelle → Tourville) — 13:00 → 22:00 ---
ART11_RING = buffer_polyline(
    [
        (2.3145, 48.8575),
        (2.3135, 48.8550),
        (2.3128, 48.8530),
    ],
    width_m=80,
)

# --- Art. 12 : quais / ponts ouest (Issy → Alma) — 14:00 → 20:00 ---
ART12_RING = buffer_polyline(
    [
        (2.2740, 48.8455),  # Issy
        (2.2800, 48.8485),  # André Citroën
        (2.2855, 48.8520),  # Grenelle / Mirabeau
        (2.2885, 48.8555),  # Bir-Hakeim
        (2.2935, 48.8595),  # Iéna
        (2.3010, 48.8635),  # Alma / New-York / Pompidou
    ],
    width_m=140,
)

# --- Art. 13 : périmètre rive gauche (Balard → Eiffel → Solférino → quais) — 14:00 → 20:00
#     Ne doit PAS englober Bac / Montalembert (au sud de l'Université). ---
ART13_RING = [
    [2.2780, 48.8465],  # Balard / André Citroën
    [2.2755, 48.8490],  # Mirabeau
    [2.2820, 48.8505],  # Emile Zola / Peignot
    [2.2880, 48.8515],  # Emeriau / Finlay / Saint-Charles
    [2.2940, 48.8540],  # Fédération / Suffren
    [2.2970, 48.8570],  # Gustave Eiffel / Rapp
    [2.3100, 48.8600],  # Université (Rapp → Solférino) — limite sud du périmètre
    [2.3205, 48.8605],  # Solférino → quai Anatole France
    [2.3180, 48.8625],  # quai d'Orsay
    [2.3050, 48.8628],  # Branly / Chirac
    [2.2900, 48.8580],  # Grenelle quai
    [2.2800, 48.8520],  # André Citroën quai
    [2.2780, 48.8465],  # fermeture
]


def build_geojson() -> dict:
    common = {
        "type": "circulation_interdite",
        "exclure_recherche": True,
    }
    features = [
        polygon_feature(
            ART4_RING,
            {
                **common,
                **schedule_props("00:01", "23:59"),
                "zone_id": "art4_cours_la_reine_clemenceau",
                "nom": "Cours la Reine — Churchill — Clemenceau",
                "article": "4",
                "horaires": "26 juillet 2026, 0 h 01 à 23 h 59",
                "description": "Art. 4 — Cours la Reine, avenue Winston Churchill, place Clemenceau.",
            },
        ),
        polygon_feature(
            ART6_CHAMPS,
            {
                **common,
                **schedule_props("06:00", "23:59"),
                "zone_id": "art6_champs_elysees",
                "nom": "Avenue des Champs-Élysées (Concorde → rond-point)",
                "article": "6",
                "horaires": "26 juillet 2026, 6 h à 23 h 59",
                "description": (
                    "Art. 6 — Avenue des Champs-Élysées entre place de la Concorde et "
                    "rond-point des Champs-Élysées-Marcel Dassault."
                ),
            },
        ),
        polygon_feature(
            ART6_MARIGNY,
            {
                **common,
                **schedule_props("06:00", "23:59"),
                "zone_id": "art6_marigny",
                "nom": "Avenue de Marigny",
                "article": "6",
                "horaires": "26 juillet 2026, 6 h à 23 h 59",
                "description": "Art. 6 — Avenue de Marigny entre avenue Gabriel et les Champs-Élysées.",
            },
        ),
        polygon_feature(
            ART7_RING,
            {
                **common,
                **schedule_props("06:00", "23:59"),
                "zone_id": "art7_berges_ponts_concorde",
                "nom": "Berges et ponts (Alma → Concorde / Tuileries)",
                "article": "7",
                "horaires": "26 juillet 2026, 6 h à 23 h 59",
                "description": (
                    "Art. 7 — Voie Georges Pompidou, quais Tuileries / Aimé Césaire / "
                    "François Mitterrand, ponts Royal, Concorde, Alexandre III, Invalides."
                ),
            },
        ),
        polygon_feature(
            ART8_RING,
            {
                **common,
                **schedule_props("09:00", "23:59"),
                "zone_id": "art8_alma_maillot_concorde",
                "nom": "Périmètre Alma — Maillot — Ternes — Concorde",
                "article": "8",
                "horaires": "26 juillet 2026, 9 h à 23 h 59",
                "description": (
                    "Art. 8 — Grand périmètre formé par Alma, Wilson, Victor Hugo, Maillot, "
                    "Ternes, Faubourg Saint-Honoré, Carrousel, quais et Concorde "
                    "(voies de contour libres sauf mention contraire)."
                ),
            },
        ),
        polygon_feature(
            ART9_RING,
            {
                **common,
                **schedule_props("11:00", "20:00"),
                "zone_id": "art9_montmartre",
                "nom": "Périmètre Montmartre",
                "article": "9",
                "horaires": "26 juillet 2026, 11 h à 20 h",
                "description": (
                    "Art. 9 — Périmètre Montmartre (Caulaincourt, Clichy, Abbesses, "
                    "Saint-Pierre, Lamarck…)."
                ),
            },
        ),
        polygon_feature(
            ART10_RING,
            {
                **common,
                **schedule_props("13:00", "20:00"),
                "zone_id": "art10_ternes_clichy_haussmann",
                "nom": "Périmètre Ternes — Clichy — Haussmann",
                "article": "10",
                "horaires": "26 juillet 2026, 13 h à 20 h",
                "description": (
                    "Art. 10 — Périmètre 8e / 9e / 17e (Pereire, Villiers, Clichy, "
                    "Haussmann, Friedland, Ternes)."
                ),
            },
        ),
        polygon_feature(
            ART11_RING,
            {
                **common,
                **schedule_props("13:00", "22:00"),
                "zone_id": "art11_boulevard_invalides",
                "nom": "Boulevard des Invalides (segment)",
                "article": "11",
                "horaires": "26 juillet 2026, 13 h à 22 h",
                "description": "Art. 11 — Boulevard des Invalides entre rue de Grenelle et avenue de Tourville.",
            },
        ),
        polygon_feature(
            ART12_RING,
            {
                **common,
                **schedule_props("14:00", "20:00"),
                "zone_id": "art12_quais_ponts_ouest",
                "nom": "Quais et ponts ouest (Issy → Alma)",
                "article": "12",
                "horaires": "26 juillet 2026, 14 h à 20 h",
                "description": (
                    "Art. 12 — Quais Issy / Citroën et ponts Mirabeau, Grenelle, "
                    "Bir-Hakeim, Iéna, Alma."
                ),
            },
        ),
        polygon_feature(
            ART13_RING,
            {
                **common,
                **schedule_props("14:00", "20:00"),
                "zone_id": "art13_rive_gauche_eiffel",
                "nom": "Périmètre rive gauche (Eiffel — quais)",
                "article": "13",
                "horaires": "26 juillet 2026, 14 h à 20 h",
                "description": (
                    "Art. 13 — Périmètre 7e / 15e (Balard → Suffren → Université / "
                    "Solférino → quais d'Orsay, Branly, Grenelle)."
                ),
            },
        ),
    ]
    return {
        "type": "FeatureCollection",
        "name": "tour_de_france_2026_paris",
        "metadata": {
            "source": (
                "Arrêté préfectoral n°2026-00936 du 20 juillet 2026 — "
                "mesures de circulation (articles 4 à 13). "
                "Polygones approximatifs construits par ParkEco à partir de la liste "
                "des voies ; pas une numérisation des plans d'annexe."
            ),
            "source_url": SOURCE_URL,
            "event_date": EVENT_DATE_NOTE,
            "event_day": EVENT_DAY,
            "provisoire": False,
            "official_info": SOURCE_URL,
        },
        "features": features,
    }


def main() -> None:
    data = build_geojson()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Écrit : {OUT} — {len(data['features'])} zone(s)")


if __name__ == "__main__":
    main()
