#!/usr/bin/env python3
"""Retire les rattachements open data erronés (paris_od_id, URL, tarifs copiés).

Règles :
- Un paris_od_id ne doit appartenir qu'à un parking public_paris (le plus légitime).
- Les parkings privés (parkopedia, complement_parko, …) perdent les données open data.
- Les corrections manuelles (tarif affiche, correction manuelle) sont conservées.
- Les tarifs Parkopedia déjà présents sont conservés si l'open data est retiré.
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chemins_projet import DATA_DIR, WORK_DIR

import pandas as pd

CSV_SEP = ";"
REF_PATH = Path(__file__).resolve().parents[2] / "parking principal" / "donnée" / "parkings_final.csv"

TARIFF_COLS = [
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


def clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def has_manual_tariffs(info_source: str) -> bool:
    src = clean(info_source).lower()
    return "tarif affiche" in src or "correction manuelle" in src


def has_parkopedia_tariffs(info_source: str) -> bool:
    return "parkopedia.xlsx" in clean(info_source).lower()


def strip_opendata_from_info_source(info_source: str) -> str:
    src = clean(info_source)
    if not src:
        return ""
    parts = [p.strip() for p in re.split(r"\s*\+\s*", src) if p.strip()]
    kept = [
        p
        for p in parts
        if "opendata.paris.fr" not in p.lower() and "opendata.saemes.fr" not in p.lower()
    ]
    return " + ".join(kept)


def od_owners(df: pd.DataFrame) -> dict[str, str | None]:
    groups: dict[str, list[str]] = defaultdict(list)
    for _, row in df.iterrows():
        od = clean(row.get("paris_od_id"))
        if od:
            groups[od].append(clean(row["parking_id"]))

    owners: dict[str, str | None] = {}
    by_id = df.set_index("parking_id")
    for od, pids in groups.items():
        public = [p for p in pids if clean(by_id.loc[p, "provenance"]) == "public_paris"]
        if len(public) == 1:
            owners[od] = public[0]
        elif len(public) > 1:
            owners[od] = sorted(public)[0]
        else:
            owners[od] = None
    return owners


def should_strip_row(row: pd.Series, owners: dict[str, str | None]) -> bool:
    pid = clean(row["parking_id"])
    od = clean(row.get("paris_od_id"))
    prov = clean(row.get("provenance"))
    src = clean(row.get("info_source")).lower()

    if not od and "opendata.paris.fr" not in src and "opendata.saemes.fr" not in src:
        return False

    if od:
        owner = owners.get(od)
        if owner is None or owner != pid:
            return True

    if prov != "public_paris" and (
        od or "opendata.paris.fr" in src or "opendata.saemes.fr" in src
    ):
        return True

    return False


def clean_dataframe(df: pd.DataFrame, ref: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    out = df.copy()
    ref_by = ref.set_index("parking_id")
    owners = od_owners(out)
    logs: list[str] = []

    for idx, row in out.iterrows():
        if not should_strip_row(row, owners):
            continue

        pid = clean(row["parking_id"])
        nom = clean(row["nom"])
        manual = has_manual_tariffs(row.get("info_source", ""))
        parkopedia = has_parkopedia_tariffs(row.get("info_source", ""))

        out.at[idx, "paris_od_id"] = ""
        out.at[idx, "url_site"] = ""

        if not manual and not parkopedia:
            for col in TARIFF_COLS:
                out.at[idx, col] = ""

        new_src = strip_opendata_from_info_source(row.get("info_source", ""))
        if pid in ref_by.index:
            ref_src = clean(ref_by.loc[pid, "info_source"])
            if not new_src:
                new_src = ref_src
            ref_places = clean(ref_by.loc[pid, "nb_places"])
            if ref_places:
                out.at[idx, "nb_places"] = ref_places
            if not manual and not parkopedia:
                ref_tarif = clean(ref_by.loc[pid, "tarif_1h_eur"])
                if ref_tarif:
                    out.at[idx, "tarif_1h_eur"] = ref_tarif
            ref_op = clean(ref_by.loc[pid, "operateur"])
            if ref_op:
                out.at[idx, "operateur"] = ref_op
        out.at[idx, "info_source"] = new_src

        logs.append(f"  {pid} | {nom[:45]}")

    return out, logs


def main() -> None:
    parser = argparse.ArgumentParser(description="Nettoie les rattachements open data erronés")
    parser.add_argument("--parkings", default=str(DATA_DIR / "parkings.csv"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    parkings_path = Path(args.parkings).resolve()
    if not parkings_path.is_file():
        raise SystemExit(f"Fichier introuvable : {parkings_path}")
    if not REF_PATH.is_file():
        raise SystemExit(f"Référence introuvable : {REF_PATH}")

    df = pd.read_csv(parkings_path, sep=CSV_SEP, dtype=str).fillna("")
    ref = pd.read_csv(REF_PATH, sep=CSV_SEP, dtype=str).fillna("")

    before_od = (df["paris_od_id"].astype(str).str.strip() != "").sum()
    before_tarif = pd.to_numeric(df["tarif_1h_eur"], errors="coerce").notna().sum()

    cleaned, logs = clean_dataframe(df, ref)

    after_od = (cleaned["paris_od_id"].astype(str).str.strip() != "").sum()
    after_tarif = pd.to_numeric(cleaned["tarif_1h_eur"], errors="coerce").notna().sum()

    print(f"Nettoyage : {len(logs)} parkings")
    print(f"  paris_od_id : {before_od} -> {after_od}")
    print(f"  tarif 1h    : {before_tarif} -> {after_tarif}")
    if logs:
        print("\nDétail :")
        print("\n".join(logs[:40]))
        if len(logs) > 40:
            print(f"  ... et {len(logs) - 40} autres")

    if args.dry_run:
        print("\n(dry-run — fichier non écrit)")
        return

    cleaned.to_csv(parkings_path, sep=CSV_SEP, index=False)
    print(f"\nÉcrit : {parkings_path}")


if __name__ == "__main__":
    main()
