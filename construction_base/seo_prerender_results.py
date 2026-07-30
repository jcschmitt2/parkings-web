"""Prérendu HTML des résultats parkings pour landings SEO /parking-proche-*.

Reproduit la logique distance / rayon / cartes de index.html (sans Paris Respire
au build, comme lorsque aucune zone active n'est chargée). Mode arrondissement :
filtre par code postal, sans distance.
"""
from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path

from chemins_projet import DATA_DIR

APP_PARKINGS_JSON = DATA_DIR / "app_parkings.json"
SEARCH_RADIUS_M = 1000


def should_prerender(landing: dict) -> bool:
    """Prérendu HTML + JSON-LD pour toutes les landings /parking-proche-*."""
    slug = str(landing.get("slug") or "")
    return slug.startswith("parking-proche-")


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p = math.pi / 180.0
    dphi = (lat2 - lat1) * p
    dl = (lon2 - lon1) * p
    a = math.sin(dphi / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fmt_dist(m: float) -> str:
    if m < 1000:
        return f"{round(m)} m"
    return f"{(m / 1000):.2f} km"


def fmt_walk_time(m: float) -> str:
    minutes = max(1, round(m / 80))
    if minutes < 60:
        return f"{minutes} min"
    h = minutes // 60
    rest = minutes % 60
    return f"{h} h {rest} min" if rest else f"{h} h"


def clean_csv_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def display_parking_name(value) -> str:
    text = clean_csv_text(value or "Parking") or "Parking"
    lower = text.lower()
    return lower[:1].upper() + lower[1:]


def escape_html(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def format_place_parking_line(place_name: str, count: int) -> str:
    place = (place_name or "Lieu").strip()
    n = int(count) or 0
    word = "parkings" if n > 1 else "parking"
    return f"{place} : {n} {word}"


def parking_info_html(p: dict) -> str:
    parts: list[str] = []
    operator = clean_csv_text(p.get("operator"))
    if operator:
        parts.append(escape_html(operator))
    capacity = p.get("capacity")
    if capacity is not None:
        try:
            cap = round(float(capacity))
            parts.append(f"{escape_html(cap)} places")
        except (TypeError, ValueError):
            pass
    if not parts:
        return ""
    sep = '<span class="info-sep">·</span>'
    return f'<div class="parking-info">{sep.join(parts)}</div>'


def parking_result_card(p: dict, idx: int, *, title: str = "", marker_class: str = "") -> str:
    show_dist = p.get("distance_m") is not None
    marker_class = marker_class or ("result-marker-best" if idx == 0 else "result-marker-alt")
    if marker_class == "result-marker-best":
        marker_text = "P"
    elif not show_dist:
        marker_text = str(idx + 1)
    else:
        marker_text = f"P{idx}"
    show_title_in_header = bool(title) and title != marker_text
    dist_block = ""
    if show_dist:
        dist_m = float(p["distance_m"])
        dist_block = (
            '<div class="result-meta">'
            f'<span class="badge">{escape_html(fmt_dist(dist_m))}</span>'
            f'<span class="walk-time"><span class="walk-icon" aria-hidden="true">🚶</span> '
            f"{escape_html(fmt_walk_time(dist_m))}</span>"
            "</div>"
        )
    parking_id = escape_html(p.get("id") or "")
    name = display_parking_name(p.get("name"))
    title_html = escape_html(title) if show_title_in_header else ""
    return f"""
        <div class="item item-clickable" data-parking-id="{parking_id}" role="button" tabindex="0" aria-label="Voir le détail — {escape_html(name)}">
          <div style="display:flex;align-items:center;gap:8px;justify-content:space-between;">
            <strong class="result-title">
              <span class="result-marker {marker_class}">{marker_text}</span>
              {title_html}
            </strong>
            {dist_block}
          </div>
          <div>{escape_html(name)}</div>
          {parking_info_html(p)}
          <div class="item-hint">Appuyer pour adresse, photo et avis</div>
        </div>"""


def select_nearby(pool: list[dict], min_radius_m: float = SEARCH_RADIUS_M) -> list[dict]:
    """Équivalent de selectNearbyEnsuringAccessible(pool, [], minRadiusM)."""
    if not pool:
        return []
    min_r = max(0.0, float(min_radius_m or 0))
    nearby = [p for p in pool if p["distance_m"] <= min_r]
    if nearby:
        return nearby
    radius_m = pool[0]["distance_m"]
    return [p for p in pool if p["distance_m"] <= radius_m]


def load_parkings() -> list[dict]:
    bundle = json.loads(APP_PARKINGS_JSON.read_text(encoding="utf-8"))
    rows = []
    for r in bundle.get("parkings") or []:
        try:
            lat = float(r["lat"])
            lon = float(r["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(lat) or not math.isfinite(lon):
            continue
        price_1h = r.get("price1hEur")
        try:
            price_1h = float(price_1h) if price_1h is not None else None
        except (TypeError, ValueError):
            price_1h = None
        if price_1h is not None and not math.isfinite(price_1h):
            price_1h = None
        rows.append(
            {
                "id": str(r.get("id") or "").strip(),
                "name": r.get("name") or "Parking",
                "addr": r.get("addr") or "",
                "lat": lat,
                "lon": lon,
                "operator": clean_csv_text(r.get("operator")),
                "capacity": r.get("capacity"),
                "price1hEur": price_1h,
            }
        )
    return rows


def nearby_for_origin(lat: float, lon: float, radius_m: float = SEARCH_RADIUS_M) -> list[dict]:
    pool = []
    for p in load_parkings():
        d = haversine_meters(lat, lon, p["lat"], p["lon"])
        pool.append({**p, "distance_m": d})
    pool.sort(key=lambda x: x["distance_m"])
    return select_nearby(pool, radius_m)


def parking_in_postcode(p: dict, postcode: str) -> bool:
    """Équivalent JS parkingInPostcode (filtre adresse)."""
    addr = str(p.get("addr") or "").lower()
    codes = ["75016", "75116"] if postcode == "75016" else [postcode]
    return any(re.search(rf"\b{re.escape(code)}\b", addr) for code in codes)


def parkings_for_arrondissement(postcode: str) -> list[dict]:
    """Tous les parkings du code postal, triés par nom (comme showArrondissementParkings)."""
    rows = [p for p in load_parkings() if parking_in_postcode(p, postcode)]
    rows.sort(key=lambda p: str(p.get("name") or "").casefold())
    return rows


def nearby_for_landing(landing: dict) -> list[dict] | None:
    """Parkings pour une landing (lieu par distance, ou arrondissement par CP)."""
    if landing.get("mode") == "arrondissement":
        postcode = clean_csv_text(landing.get("postcode") or landing.get("searchQuery"))
        if not postcode:
            return None
        rows = parkings_for_arrondissement(postcode)
        return rows or None
    try:
        lat = float(landing["lat"])
        lon = float(landing["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not math.isfinite(lat) or not math.isfinite(lon):
        return None
    nearby = nearby_for_origin(lat, lon)
    return nearby or None


def build_results_heading_html(place_name: str, count: int) -> str:
    line = format_place_parking_line(place_name, count)
    return (
        '<div class="muted results-summary" style="margin-bottom:10px;">'
        f'<h1 class="results-seo-heading">{escape_html(line)}</h1>'
        "</div>"
    )


def extract_postal_code(addr: str) -> str | None:
    match = re.search(r"\b(75\d{3})\b", addr or "")
    return match.group(1) if match else None


def parking_facility_schema(p: dict) -> dict:
    """Objet schema.org ParkingFacility (sans @context — utilisé dans @graph)."""
    name = display_parking_name(p.get("name"))
    schema: dict = {"@type": "ParkingFacility", "name": name}
    addr = clean_csv_text(p.get("addr"))
    if addr:
        postal = extract_postal_code(addr)
        address: dict = {
            "@type": "PostalAddress",
            "streetAddress": addr,
            "addressLocality": "Paris",
            "addressCountry": "FR",
        }
        if postal:
            address["postalCode"] = postal
        schema["address"] = address
    try:
        lat = float(p["lat"])
        lon = float(p["lon"])
    except (KeyError, TypeError, ValueError):
        lat = lon = None
    if lat is not None and lon is not None and math.isfinite(lat) and math.isfinite(lon):
        schema["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
        }
    price = p.get("price1hEur")
    if price is not None:
        try:
            price_f = float(price)
        except (TypeError, ValueError):
            price_f = None
        if price_f is not None and math.isfinite(price_f):
            schema["offers"] = {
                "@type": "Offer",
                "price": f"{price_f:.2f}",
                "priceCurrency": "EUR",
                "description": "Tarif 1 heure",
            }
    return schema


def build_prerendered_parking_jsonld_html(landing: dict) -> str | None:
    """Bloc <script type=application/ld+json> des ParkingFacility, ou None."""
    if not should_prerender(landing):
        return None
    nearby = nearby_for_landing(landing)
    if not nearby:
        return None
    schema = {
        "@context": "https://schema.org",
        "@graph": [parking_facility_schema(p) for p in nearby],
    }
    payload = json.dumps(schema, ensure_ascii=False, indent=2)
    return (
        '  <script type="application/ld+json" id="seo-parking-jsonld">\n'
        f"{payload}\n"
        "  </script>\n"
    )


def build_prerendered_results_inner_html(landing: dict) -> str | None:
    """HTML intérieur de #results (heading + cartes), ou None si impossible."""
    nearby = nearby_for_landing(landing)
    if not nearby:
        return None
    place = landing.get("placeLabel") or "Lieu"
    parts = [build_results_heading_html(place, len(nearby))]
    if landing.get("mode") == "arrondissement":
        # Comme showArrondissementParkings : pas de distance, numéros 1..n
        for i, p in enumerate(nearby):
            parts.append(parking_result_card(p, i, marker_class="result-marker-alt"))
        return "".join(parts)
    best_title = "Parking le plus proche"
    best = nearby[0]
    alts = nearby[1:]
    parts.append(
        parking_result_card(
            best,
            0,
            title=best_title,
            marker_class="result-marker-best",
        )
    )
    for i, p in enumerate(alts):
        parts.append(parking_result_card(p, i + 1))
    return "".join(parts)
