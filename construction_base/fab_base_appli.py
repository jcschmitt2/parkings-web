#!/usr/bin/env python3
"""Construit app_parkings.json à partir de parkings.csv et photos.csv."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chemins_projet import DATA_DIR

CSV_SEP = ";"
SCENE_PRIORITY = ("plaque_bleu", "tarif", "interieur", "paysage")
APP_PHOTO_PREFIX = "../donnée/"

TARIFF_CSV_COLUMNS = (
    ("price15mnEur", "tarif_15mn_eur"),
    ("price30mnEur", "tarif_30mn_eur"),
    ("price1hEur", "tarif_1h_eur"),
    ("price1h30Eur", "tarif_1h30_eur"),
    ("price2hEur", "tarif_2h_eur"),
    ("price3hEur", "tarif_3h_eur"),
    ("price4hEur", "tarif_4h_eur"),
    ("price7hEur", "tarif_7h_eur"),
    ("price8hEur", "tarif_8h_eur"),
    ("price9hEur", "tarif_9h_eur"),
    ("price10hEur", "tarif_10h_eur"),
    ("price11hEur", "tarif_11h_eur"),
    ("price12hEur", "tarif_12h_eur"),
    ("price24hEur", "tarif_24h_eur"),
)


def clean(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def to_optional_float(value) -> float | None:
    text = clean(value).replace(",", ".")
    if not text:
        return None
    try:
        n = float(text)
    except ValueError:
        return None
    return n if math.isfinite(n) else None


def to_optional_int(value) -> int | None:
    n = to_optional_float(value)
    if n is None:
        return None
    return int(round(n))


def is_true(value) -> bool:
    text = clean(value).lower()
    return text in {"true", "1", "oui", "yes"}


def normalize_scene_class(value: str) -> str:
    return clean(value).lower().replace(" ", "_")


def is_indigo_generic_row(photo_id: str, selected_role: str) -> bool:
    pid = clean(photo_id).lower()
    role = clean(selected_role).lower()
    return pid == "indigo_generic" or role == "indigo_generic"


def resolve_image_relpath(data_dir: Path, chemin_rel: str) -> str:
    rel = clean(chemin_rel)
    if not rel:
        return ""
    path = data_dir / rel
    if path.is_file():
        return rel.replace("\\", "/")
    alt = path.with_suffix(".png" if path.suffix.lower() == ".jpg" else ".jpg")
    if alt.is_file():
        return alt.relative_to(data_dir).as_posix()
    return rel.replace("\\", "/")


def app_photo_url(data_dir: Path, chemin_rel: str) -> str:
    rel = resolve_image_relpath(data_dir, chemin_rel)
    if not rel:
        return ""
    return f"{APP_PHOTO_PREFIX}{rel}"


def is_indigo_parking(
    parking_id: str,
    name: str,
    addr: str,
    operator: str,
    indigo_parking_ids: set[str],
) -> bool:
    if parking_id in indigo_parking_ids:
        return True
    if re.search(r"\bindigo\b", operator, re.I):
        return True
    blob = f"{name} {addr}"
    return bool(re.search(r"\bindigo\b", blob, re.I))


def load_photos_index(data_dir: Path, photos_path: Path):
    df = pd.read_csv(photos_path, sep=CSV_SEP, dtype=str).fillna("")
    photos_by_parking: dict[str, list[dict]] = {}
    global_indigo_url = ""
    indigo_by_parking: dict[str, str] = {}
    indigo_parking_ids: set[str] = set()

    for row in df.to_dict(orient="records"):
        photo_id = clean(row.get("photo_id"))
        parking_id = clean(row.get("parking_id"))
        scene_class = normalize_scene_class(row.get("scene_class"))
        selected_role = clean(row.get("selected_role"))
        chemin_rel = clean(row.get("chemin_rel"))
        url = app_photo_url(data_dir, chemin_rel)

        if is_indigo_generic_row(photo_id, selected_role):
            if url:
                if parking_id:
                    indigo_by_parking[parking_id] = url
                else:
                    global_indigo_url = url
            continue

        if not is_true(row.get("is_selected")):
            continue

        if parking_id and re.search(r"\bindigo\b", clean(row.get("label_pred")), re.I):
            indigo_parking_ids.add(parking_id)
        if parking_id and clean(row.get("selected_role")).lower() == "indigo":
            indigo_parking_ids.add(parking_id)

        if not parking_id or scene_class == "hors_sujet":
            continue

        photos_by_parking.setdefault(parking_id, []).append(
            {"photoId": photo_id, "url": url, "sceneClass": scene_class}
        )

    return photos_by_parking, global_indigo_url, indigo_by_parking, indigo_parking_ids


def pick_display_photo_url(
    parking_id: str,
    name: str,
    addr: str,
    operator: str,
    photos_by_parking: dict[str, list[dict]],
    global_indigo_url: str,
    indigo_by_parking: dict[str, str],
    indigo_parking_ids: set[str],
) -> str:
    photos = photos_by_parking.get(parking_id, [])

    def by_scene(scene: str) -> str:
        for photo in photos:
            if photo["sceneClass"] == scene and photo["url"]:
                return photo["url"]
        return ""

    for scene in SCENE_PRIORITY[:2]:
        url = by_scene(scene)
        if url:
            return url

    if is_indigo_parking(parking_id, name, addr, operator, indigo_parking_ids):
        generic = indigo_by_parking.get(parking_id) or global_indigo_url
        if generic:
            return generic

    for scene in SCENE_PRIORITY[2:]:
        url = by_scene(scene)
        if url:
            return url
    return ""


def build_parking_record(
    row: dict,
    data_dir: Path,
    photos_by_parking: dict[str, list[dict]],
    global_indigo_url: str,
    indigo_by_parking: dict[str, str],
    indigo_parking_ids: set[str],
) -> dict | None:
    parking_id = clean(row.get("parking_id"))
    lat = to_optional_float(row.get("latitude"))
    lon = to_optional_float(row.get("longitude"))
    if not parking_id or lat is None or lon is None:
        return None

    name = clean(row.get("nom")) or "Parking"
    addr = clean(row.get("adresse"))
    operator = clean(row.get("operateur"))

    record = {
        "id": parking_id,
        "name": name,
        "addr": addr,
        "lat": lat,
        "lon": lon,
        "operator": operator,
        "capacity": to_optional_int(row.get("nb_places")),
        "price1hEur": to_optional_float(row.get("tarif_1h_eur")),
        "entranceAddr": clean(row.get("adresse_entree")),
        "websiteUrl": clean(row.get("url_site")),
        "googleRating": to_optional_float(row.get("google_rating")),
        "googleRatingsCount": to_optional_int(row.get("google_user_ratings_total")),
        "photoUrl": pick_display_photo_url(
            parking_id,
            name,
            addr,
            operator,
            photos_by_parking,
            global_indigo_url,
            indigo_by_parking,
            indigo_parking_ids,
        ),
    }
    for json_key, csv_col in TARIFF_CSV_COLUMNS:
        if json_key == "price1hEur":
            continue
        value = to_optional_float(row.get(csv_col))
        if value is not None:
            record[json_key] = value
    return record


def build_bundle(data_dir: Path, parkings_path: Path, photos_path: Path) -> dict:
    photos_by_parking, global_indigo_url, indigo_by_parking, indigo_parking_ids = load_photos_index(
        data_dir, photos_path
    )

    parkings_df = pd.read_csv(parkings_path, sep=CSV_SEP, dtype=str).fillna("")
    parkings: list[dict] = []
    for row in parkings_df.to_dict(orient="records"):
        record = build_parking_record(
            row,
            data_dir,
            photos_by_parking,
            global_indigo_url,
            indigo_by_parking,
            indigo_parking_ids,
        )
        if record:
            parkings.append(record)

    return {
        "version": 1,
        "builtAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "count": len(parkings),
        "parkings": parkings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère app_parkings.json pour FindParking")
    parser.add_argument("--data-dir", default=str(DATA_DIR), help="Dossier contenant parkings.csv et photos.csv")
    parser.add_argument("--parkings", default="parkings.csv")
    parser.add_argument("--photos", default="photos.csv")
    parser.add_argument("--output", default="app_parkings.json")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    parkings_path = data_dir / args.parkings
    photos_path = data_dir / args.photos
    output_path = data_dir / args.output

    if not parkings_path.is_file():
        raise SystemExit(f"Fichier introuvable : {parkings_path}")
    if not photos_path.is_file():
        raise SystemExit(f"Fichier introuvable : {photos_path}")

    bundle = build_bundle(data_dir, parkings_path, photos_path)
    output_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with_photo = sum(1 for p in bundle["parkings"] if p.get("photoUrl"))
    print(f"Écrit : {output_path}")
    print(f"  - parkings : {bundle['count']}")
    print(f"  - avec photoUrl : {with_photo}")


if __name__ == "__main__":
    main()
