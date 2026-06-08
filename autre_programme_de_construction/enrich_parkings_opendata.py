#!/usr/bin/env python3
"""Enrichit parkings.csv depuis opendata.paris.fr (stationnement-en-ouvrage).

Ajoute ou met à jour : paris_od_id, tarifs horaires (15 min → 24 h), nb_places,
url_site, opérateur. Ne modifie jamais adresse ni adresse_entree.
Chaque paris_od_id n'est attribué qu'à un seul parking (meilleur score nom+GPS).
Ne crée aucun parking.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
import urllib.request
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chemins_projet import DATA_DIR, WORK_DIR
from typing import Any

import pandas as pd

CSV_SEP = ";"
USER_AGENT = "parking_ok/1.0"

PARIS_TARIFF_MAP = {
    "tarif_15mn_eur": "tf_15mn_e",
    "tarif_30mn_eur": "tf_30mn_e",
    "tarif_1h_eur": "tarif_1h",
    "tarif_1h30_eur": "tf_1h30_e",
    "tarif_2h_eur": "tarif_2h",
    "tarif_3h_eur": "tarif_3h",
    "tarif_4h_eur": "tarif_4h",
    "tarif_7h_eur": "tf_7h_e",
    "tarif_8h_eur": "tf_8h_e",
    "tarif_9h_eur": "tf_9h_e",
    "tarif_10h_eur": "tf_10h_e",
    "tarif_11h_eur": "tf_11h_e",
    "tarif_12h_eur": "tf_12h_e",
    "tarif_24h_eur": "tarif_24h",
}

SAEMES_TARIFF_MAP = {
    "tarif_15mn_eur": "horaire_vl_15mn_15_min",
    "tarif_1h_eur": "horaire_vl_1h00_1_hr",
    "tarif_3h_eur": "horaire_vl_3h00_3_hr",
    "tarif_24h_eur": "horaire_vl_24h00_24_hr",
}

ENRICH_COLUMNS = [
    "paris_od_id",
    "url_site",
    *PARIS_TARIFF_MAP.keys(),
]


def clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def to_float(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str):
        text = value.strip().replace(",", ".")
        text = re.sub(r"[^0-9.]", "", text)
        if not text:
            return None
        try:
            n = float(text)
        except ValueError:
            return None
    else:
        try:
            n = float(value)
        except (TypeError, ValueError):
            return None
    if not math.isfinite(n) or n <= 0:
        return None
    return round(n, 2)


def to_int(value: Any) -> int | None:
    n = to_float(value)
    if n is None:
        return None
    return int(round(n))


def fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def fetch_all_opendatasoft(base_url: str, dataset: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        url = (
            f"{base_url}/api/explore/v2.1/catalog/datasets/{dataset}/records"
            f"?limit=100&offset={offset}"
        )
        data = fetch_json(url)
        batch = data.get("results", [])
        rows.extend(batch)
        if len(batch) < 100:
            break
        offset += 100
    return rows


def norm_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", clean(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Z0-9 ]", " ", text.upper())
    text = re.sub(
        r"\b(PARKING|PARC DE STATIONNEMENT|PARC DE|GARAGE|STATIONNEMENT)\b",
        " ",
        text,
    )
    return re.sub(r"\s+", " ", text).strip()


def tokens(value: str) -> set[str]:
    return {t for t in norm_text(value).split() if len(t) > 2}


def name_score(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    x = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


def postcode_from_insee(insee: str, arrdt: str) -> str:
    code = clean(insee)
    # Codes INSEE Paris : 75101…75120 (arrondissements), pas des codes postaux.
    if len(code) == 5 and code.startswith("751"):
        arr = code[3:]
        if arr.isdigit() and 1 <= int(arr) <= 20:
            return f"750{arr.zfill(2)}"
    if len(code) == 5 and code.startswith("750"):
        return code
    arr = clean(arrdt)
    if arr.isdigit() and 1 <= int(arr) <= 20:
        return f"750{arr.zfill(2)}"
    return "75000"


def format_address_line(street: str, postcode: str) -> str:
    street = clean(street).lower()
    street = re.sub(r"\s+", " ", street)
    street = re.sub(r"\s*,\s*", " ", street)
    street = re.sub(r"\bparis\b", "paris", street)
    if not street:
        return ""
    if postcode and postcode not in street:
        return f"{street} {postcode} paris"
    if "paris" not in street:
        return f"{street} paris"
    return street


def paris_full_address(record: dict) -> str:
    raw = clean(record.get("adresse"))
    if raw:
        text = raw.lower()
        text = re.sub(r"\s*,\s*", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if "paris" not in text:
            pc = re.search(r"\b75\d{3}\b", text)
            if pc:
                text = f"{text} paris"
        return text.replace(" Paris", " paris")

    entrances = record.get("adress_geo_entrees") or []
    if entrances:
        pc = postcode_from_insee(record.get("insee", ""), record.get("arrdt", ""))
        return format_address_line(str(entrances[0]), pc)
    return ""


def paris_entrance_address(record: dict) -> str:
    entrances = record.get("adress_geo_entrees") or []
    if not entrances:
        return paris_full_address(record)
    pc = postcode_from_insee(record.get("insee", ""), record.get("arrdt", ""))
    return format_address_line(str(entrances[0]), pc)


def paris_match_candidate(
    nom: str,
    lat: float,
    lon: float,
    paris_rows: list[dict],
    max_dist_m: float = 200.0,
) -> tuple[dict, float, float] | None:
    best: dict | None = None
    best_key = (-1.0, 9999.0)
    for record in paris_rows:
        rlat = to_float(record.get("ylat"))
        rlon = to_float(record.get("xlong"))
        if rlat is None or rlon is None:
            continue
        dist = haversine_m(lat, lon, rlat, rlon)
        if dist > max_dist_m:
            continue
        ns = name_score(nom, clean(record.get("nom")))
        if not _paris_match_acceptable(ns, dist):
            continue
        key = (ns, -dist)
        if key > best_key:
            best_key = key
            best = record
    if not best:
        return None
    ns, neg_dist = best_key
    return best, ns, -neg_dist


def _paris_match_acceptable(ns: float, dist: float) -> bool:
    if dist <= 40 and ns >= 0.25:
        return True
    if dist <= 80 and ns >= 0.35:
        return True
    if dist <= 120 and ns >= 0.45:
        return True
    if dist <= 200 and ns >= 0.55:
        return True
    return False


def assign_unique_paris_matches(
    df: pd.DataFrame,
    paris_rows: list[dict],
) -> dict[int, dict]:
    """Retourne idx -> record Paris OD (un OD = un seul parking)."""
    candidates: list[tuple[int, str, dict, float, float]] = []
    for idx, row in df.iterrows():
        if has_manual_tariffs(clean(row.get("info_source"))):
            continue
        nom = clean(row.get("nom"))
        lat = to_float(row.get("latitude"))
        lon = to_float(row.get("longitude"))
        if lat is None or lon is None:
            continue
        hit = paris_match_candidate(nom, lat, lon, paris_rows)
        if not hit:
            continue
        record, ns, dist = hit
        candidates.append((idx, clean(record.get("id")), record, ns, dist))

    by_od: dict[str, list[tuple[int, dict, float, float]]] = {}
    for idx, od_id, record, ns, dist in candidates:
        by_od.setdefault(od_id, []).append((idx, record, ns, dist))

    winners: dict[int, dict] = {}
    for entries in by_od.values():
        idx, record, _ns, _dist = max(entries, key=lambda x: (x[2], -x[3]))
        winners[idx] = record
    return winners


def saemes_lat_lon(record: dict) -> tuple[float | None, float | None]:
    geo = record.get("geo") or {}
    if isinstance(geo, dict):
        lat = to_float(geo.get("lat"))
        lon = to_float(geo.get("lon"))
        if lat is not None and lon is not None:
            return lat, lon
        coords = geo.get("coordinates")
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            return to_float(coords[1]), to_float(coords[0])
    return (
        to_float(record.get("gps_lattitude_acces_vehicules_1")),
        to_float(record.get("gps_longitude_acces_vehicules_1")),
    )


def best_saemes_match(
    nom: str,
    lat: float,
    lon: float,
    saemes_rows: list[dict],
    max_dist_m: float = 250.0,
) -> dict | None:
    best_geo: dict | None = None
    best_geo_key = (-1.0, 9999.0)
    best_name: dict | None = None
    best_name_score = 0.0

    for record in saemes_rows:
        label = clean(record.get("nom_parking")) or clean(record.get("nom"))
        ns = name_score(nom, label)
        if ns > best_name_score:
            best_name_score = ns
            best_name = record

        rlat, rlon = saemes_lat_lon(record)
        if rlat is None or rlon is None:
            continue
        dist = haversine_m(lat, lon, rlat, rlon)
        if dist > max_dist_m:
            continue
        if ns < 0.2 and dist > 80:
            continue
        key = (ns, -dist)
        if key > best_geo_key:
            best_geo_key = key
            best_geo = record

    if best_geo:
        ns, neg_dist = best_geo_key
        dist = -neg_dist
        if ns >= 0.35 or dist <= 80 or (dist <= 150 and ns >= 0.25):
            return best_geo

    if best_name and best_name_score >= 0.45:
        return best_name
    return None


def is_saemes_candidate(row: dict[str, Any], nom: str) -> bool:
    operateur = clean(row.get("operateur")).upper()
    if operateur == "SAEMES":
        return True
    return "SAEMES" in clean(nom).upper()


def has_hourly_tariff(row: dict[str, Any]) -> bool:
    return to_float(row.get("tarif_1h_eur")) is not None


def has_manual_tariffs(info_source: str) -> bool:
    src = clean(info_source).lower()
    return "tarif affiche" in src or "correction manuelle" in src


def merge_info_source(existing: str, part: str) -> str:
    parts = [p.strip() for p in re.split(r"\s*\+\s*", clean(existing)) if p.strip()]
    if part not in parts:
        parts.append(part)
    return " + ".join(parts)


def apply_tariffs_from_mapping(target: dict[str, Any], source: dict, mapping: dict[str, str]) -> int:
    filled = 0
    for col, src_key in mapping.items():
        price = to_float(source.get(src_key))
        if price is not None:
            target[col] = price
            filled += 1
    return filled


def enrich_from_paris(row: dict[str, Any], paris: dict) -> None:
    manual = has_manual_tariffs(clean(row.get("info_source")))
    row["info_source"] = merge_info_source(clean(row.get("info_source")), "opendata.paris.fr")

    if not manual:
        row["paris_od_id"] = clean(paris.get("id"))
        url = clean(paris.get("url"))
        if url:
            row["url_site"] = url
        places = to_int(paris.get("nb_places"))
        if places is not None:
            row["nb_places"] = places
        deleg = clean(paris.get("deleg")).upper()
        if deleg == "Q PARK":
            deleg = "Q-PARK"
        if deleg:
            row["operateur"] = deleg
        apply_tariffs_from_mapping(row, paris, PARIS_TARIFF_MAP)
    else:
        for col, src_key in PARIS_TARIFF_MAP.items():
            if to_float(row.get(col)) is not None:
                continue
            price = to_float(paris.get(src_key))
            if price is not None:
                row[col] = price


def enrich_from_saemes(row: dict[str, Any], saemes: dict, *, complement: bool = False) -> None:
    if complement and row.get("info_source"):
        row["info_source"] = f"{clean(row['info_source'])} + opendata.saemes.fr"
    elif not row.get("info_source"):
        row["info_source"] = "opendata.saemes.fr"

    url = clean(saemes.get("lien_web_parking")) or clean(saemes.get("site_web"))
    if url and not row.get("url_site"):
        if url.startswith("www."):
            url = f"https://{url}"
        row["url_site"] = url

    places = to_int(saemes.get("nombre_de_places"))
    if places is not None and (not row.get("nb_places") or pd.isna(row.get("nb_places"))):
        row["nb_places"] = places

    if not clean(row.get("operateur")):
        row["operateur"] = "SAEMES"

    for col, src_key in SAEMES_TARIFF_MAP.items():
        if row.get(col) not in (None, "", float("nan")) and not pd.isna(row.get(col)):
            continue
        price = to_float(saemes.get(src_key))
        if price is not None:
            row[col] = price


def enrich_dataframe(df: pd.DataFrame, paris_rows: list[dict], saemes_rows: list[dict]) -> pd.DataFrame:
    out = df.copy()
    for col in ENRICH_COLUMNS:
        if col not in out.columns:
            out[col] = ""

    stats = {"paris": 0, "saemes": 0, "saemes_complement": 0, "unchanged": 0}
    paris_winners = assign_unique_paris_matches(out, paris_rows)

    for idx, row in out.iterrows():
        nom = clean(row.get("nom"))
        lat = to_float(row.get("latitude"))
        lon = to_float(row.get("longitude"))
        if lat is None or lon is None:
            stats["unchanged"] += 1
            continue

        updates: dict[str, Any] = dict(row.to_dict())
        saemes_primary = False
        paris = paris_winners.get(idx)
        if paris:
            enrich_from_paris(updates, paris)
            stats["paris"] += 1
        elif is_saemes_candidate(row.to_dict(), nom):
            saemes = best_saemes_match(nom, lat, lon, saemes_rows)
            if saemes:
                enrich_from_saemes(updates, saemes)
                stats["saemes"] += 1
                saemes_primary = True

        changed = False
        if paris:
            changed = True
        elif saemes_primary:
            changed = True

        if not has_hourly_tariff(updates) and is_saemes_candidate(row.to_dict(), nom):
            saemes = best_saemes_match(nom, lat, lon, saemes_rows)
            if saemes:
                if paris:
                    enrich_from_saemes(updates, saemes, complement=True)
                    stats["saemes_complement"] += 1
                elif not saemes_primary:
                    enrich_from_saemes(updates, saemes)
                    stats["saemes"] += 1
                changed = True

        if changed:
            for key, value in updates.items():
                if key in {"adresse", "adresse_entree"}:
                    continue
                if value == "" or value is None:
                    continue
                if isinstance(value, (int, float)):
                    text = (
                        str(int(value))
                        if isinstance(value, float) and value.is_integer()
                        else str(value)
                    )
                    out.at[idx, key] = text
                else:
                    out.at[idx, key] = str(value)
        else:
            stats["unchanged"] += 1

    print(
        f"Enrichissement : {stats['paris']} via Paris OD, "
        f"{stats['saemes']} via Saemes, "
        f"{stats['saemes_complement']} complétés Saemes, "
        f"{stats['unchanged']} inchangés"
    )
    dup = out["paris_od_id"].astype(str).str.strip()
    dup = dup[dup != ""].duplicated().sum()
    print(f"  paris_od_id dupliqués après enrichissement : {dup}")
    return out


def report_coverage(df: pd.DataFrame) -> None:
    n = len(df)
    print(f"\nCouverture sur {n} parkings :")
    print(f"  - url_site          : {(df['url_site'].astype(str).str.strip() != '').sum()}")
    print(f"  - adresse_entree    : {(df['adresse_entree'].astype(str).str.strip() != '').sum()}")
    print(f"  - nb_places         : {pd.to_numeric(df['nb_places'], errors='coerce').notna().sum()}")
    for col in PARIS_TARIFF_MAP:
        if col in df.columns:
            count = pd.to_numeric(df[col], errors="coerce").notna().sum()
            print(f"  - {col:18}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrichit parkings.csv depuis les open data Paris")
    parser.add_argument("--parkings", default=str(DATA_DIR / "parkings.csv"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    parkings_path = Path(args.parkings).resolve()
    if not parkings_path.is_file():
        raise SystemExit(f"Fichier introuvable : {parkings_path}")

    print("Téléchargement opendata.paris.fr (stationnement-en-ouvrage)…")
    paris_rows = fetch_all_opendatasoft("https://opendata.paris.fr", "stationnement-en-ouvrage")
    print(f"  {len(paris_rows)} ouvrages")

    print("Téléchargement opendata.saemes.fr (référentiel)…")
    saemes_rows = fetch_all_opendatasoft("https://opendata.saemes.fr", "referentiel-parkings-saemes")
    print(f"  {len(saemes_rows)} parkings Saemes")

    df = pd.read_csv(parkings_path, sep=CSV_SEP, dtype=str).fillna("")
    enriched = enrich_dataframe(df, paris_rows, saemes_rows)
    report_coverage(enriched)

    if args.dry_run:
        print("\n(dry-run — fichier non écrit)")
        sample = enriched[
            ["parking_id", "nom", "adresse", "adresse_entree", "url_site", "nb_places", "tarif_1h_eur"]
        ].head(8)
        print(sample.to_string(index=False))
        return

    enriched.to_csv(parkings_path, sep=CSV_SEP, index=False)
    print(f"\nÉcrit : {parkings_path}")


if __name__ == "__main__":
    main()
