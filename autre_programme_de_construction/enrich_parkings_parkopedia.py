#!/usr/bin/env python3
"""Complète les tarifs manquants depuis parkings-parkopedia.xlsx (source secondaire)."""
from __future__ import annotations

import argparse
import math
import re
import unicodedata
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chemins_projet import DATA_DIR, WORK_DIR
from typing import Any

import pandas as pd

CSV_SEP = ";"
PLACEHOLDER_LAT = 48.893579

TARIFF_COLUMNS = [
    "tarif_15mn_eur",
    "tarif_30mn_eur",
    "tarif_1h_eur",
    "tarif_1h30_eur",
    "tarif_2h_eur",
    "tarif_3h_eur",
    "tarif_4h_eur",
    "tarif_7h_eur",
    "tarif_8h_eur",
    "tarif_9h_eur",
    "tarif_10h_eur",
    "tarif_11h_eur",
    "tarif_12h_eur",
    "tarif_24h_eur",
]

DURATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^15\s*min", re.I), "tarif_15mn_eur"),
    (re.compile(r"^30\s*min", re.I), "tarif_30mn_eur"),
    (re.compile(r"^1\s*heure", re.I), "tarif_1h_eur"),
    (re.compile(r"^90\s*min", re.I), "tarif_1h30_eur"),
    (re.compile(r"^2\s*heures?", re.I), "tarif_2h_eur"),
    (re.compile(r"^3\s*heures?", re.I), "tarif_3h_eur"),
    (re.compile(r"^4\s*heures?", re.I), "tarif_4h_eur"),
    (re.compile(r"^7\s*heures?", re.I), "tarif_7h_eur"),
    (re.compile(r"^8\s*heures?", re.I), "tarif_8h_eur"),
    (re.compile(r"^9\s*heures?", re.I), "tarif_9h_eur"),
    (re.compile(r"^10\s*heures?", re.I), "tarif_10h_eur"),
    (re.compile(r"^11\s*heures?", re.I), "tarif_11h_eur"),
    (re.compile(r"^12\s*heures?", re.I), "tarif_12h_eur"),
    (re.compile(r"^24\s*heures?", re.I), "tarif_24h_eur"),
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
    if not math.isfinite(n) or n < 0:
        return None
    return round(n, 2)


def norm_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", clean(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Z0-9 ]", " ", text.upper())
    text = re.sub(
        r"\b(PARKING|PARC DE STATIONNEMENT|PARC DE|GARAGE|STATIONNEMENT|INDIGO|SAEMES|PARIS)\b",
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


def is_placeholder_coord(lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return True
    return abs(lat - PLACEHOLDER_LAT) < 0.00001


def has_hourly_tariff(row: dict[str, Any]) -> bool:
    return to_float(row.get("tarif_1h_eur")) is not None


def cell_has_tariff(value) -> bool:
    return to_float(value) is not None


def parse_parkopedia_tariffs(text: str) -> dict[str, float]:
    result: dict[str, float] = {}
    if not clean(text):
        return result

    for chunk in re.split(r"\s*\|\s*", clean(text)):
        if ":" not in chunk:
            continue
        label, price_text = chunk.split(":", 1)
        label = label.strip()
        price = to_float(price_text)
        if price is None:
            continue

        for pattern, col in DURATION_PATTERNS:
            if pattern.search(label) and col not in result:
                result[col] = price
                break
    return result


def best_parkopedia_match(
    nom: str,
    lat: float | None,
    lon: float | None,
    parkopedia_rows: list[dict],
) -> dict | None:
    best: dict | None = None
    best_key = (-1.0, 9999.0)

    csv_placeholder = is_placeholder_coord(lat, lon)

    for record in parkopedia_rows:
        pnom = clean(record.get("nom"))
        ns = name_score(nom, pnom)
        if ns < 0.4:
            continue

        plat = to_float(record.get("Ylat"))
        plon = to_float(record.get("Xlong"))
        dist = 9999.0
        if lat is not None and lon is not None and plat is not None and plon is not None:
            dist = haversine_m(lat, lon, plat, plon)

        p_placeholder = is_placeholder_coord(plat, plon)

        if csv_placeholder or p_placeholder:
            key = (ns, dist)
            if ns >= 0.5 and key > best_key:
                best_key = key
                best = record
            continue

        if dist > 200:
            continue
        if ns < 0.25 and dist > 80:
            continue
        key = (ns, dist)
        if key > best_key:
            best_key = key
            best = record

    if not best:
        return None

    ns, dist = best_key
    if ns >= 0.5:
        return best
    if dist <= 80 and ns >= 0.4:
        return best
    return None


def enrich_from_parkopedia(target: dict[str, Any], source: dict) -> int:
    tariffs = parse_parkopedia_tariffs(clean(source.get("tarifs")))
    filled = 0
    for col, price in tariffs.items():
        if cell_has_tariff(target.get(col)):
            continue
        target[col] = price
        filled += 1

    if filled and not clean(target.get("info_source")):
        target["info_source"] = "parkopedia.xlsx"
    elif filled and "parkopedia" not in clean(target.get("info_source")).lower():
        target["info_source"] = f"{clean(target['info_source'])} + parkopedia.xlsx"

    return filled


def enrich_dataframe(df: pd.DataFrame, parkopedia_df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    out = df.copy()
    parkopedia_rows = parkopedia_df.to_dict(orient="records")
    logs: list[str] = []
    enriched_count = 0

    for idx, row in out.iterrows():
        if has_hourly_tariff(row.to_dict()):
            continue

        nom = clean(row.get("nom"))
        lat = to_float(row.get("latitude"))
        lon = to_float(row.get("longitude"))
        match = best_parkopedia_match(nom, lat, lon, parkopedia_rows)
        if not match:
            continue

        updates: dict[str, Any] = dict(row.to_dict())
        filled = enrich_from_parkopedia(updates, match)
        if not filled:
            continue

        for key, value in updates.items():
            if key not in TARIFF_COLUMNS and key != "info_source":
                continue
            if value == "" or value is None:
                continue
            if isinstance(value, (int, float)):
                text = str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)
                out.at[idx, key] = text
            else:
                out.at[idx, key] = str(value)

        enriched_count += 1
        logs.append(
            f"  {clean(row.get('parking_id'))} | {nom[:40]} "
            f"<- {clean(match.get('nom'))[:40]} (+{filled} tarifs)"
        )

    print(f"Parkopedia : {enriched_count} parkings complétés")
    return out, logs


def main() -> None:
    parser = argparse.ArgumentParser(description="Complète les tarifs via parkings-parkopedia.xlsx")
    parser.add_argument("--parkings", default=str(DATA_DIR / "parkings.csv"))
    parser.add_argument("--parkopedia", default=str(WORK_DIR / "parkings-parkopedia.xlsx"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    parkings_path = Path(args.parkings).resolve()
    parkopedia_path = Path(args.parkopedia).resolve()

    if not parkings_path.is_file():
        raise SystemExit(f"Fichier introuvable : {parkings_path}")
    if not parkopedia_path.is_file():
        raise SystemExit(f"Fichier introuvable : {parkopedia_path}")

    df = pd.read_csv(parkings_path, sep=CSV_SEP, dtype=str).fillna("")
    parkopedia_df = pd.read_excel(parkopedia_path, sheet_name=0, dtype=str).fillna("")

    before = sum(1 for _, r in df.iterrows() if has_hourly_tariff(r.to_dict()))
    enriched, logs = enrich_dataframe(df, parkopedia_df)
    after = sum(1 for _, r in enriched.iterrows() if has_hourly_tariff(r.to_dict()))

    print(f"Tarif 1h : {before} -> {after} (+{after - before})")
    if logs:
        print("\nDétail :")
        print("\n".join(logs[:30]))
        if len(logs) > 30:
            print(f"  ... et {len(logs) - 30} autres")

    if args.dry_run:
        print("\n(dry-run — fichier non écrit)")
        return

    enriched.to_csv(parkings_path, sep=CSV_SEP, index=False)
    print(f"\nÉcrit : {parkings_path}")


if __name__ == "__main__":
    main()
