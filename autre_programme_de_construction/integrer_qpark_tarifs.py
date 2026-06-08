#!/usr/bin/env python3
"""Intègre les tarifs validés depuis parkings_tarifs_qpark_a_verifier.xlsx → parkings.csv."""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chemins_projet import DATA_DIR, WORK_DIR

import pandas as pd

CSV_SEP = ";"
INFO_PART = "q-park.fr"

EXCEL_TO_CSV = {
    "15 min (€)": "tarif_15mn_eur",
    "30 min (€)": "tarif_30mn_eur",
    "1 h (€)": "tarif_1h_eur",
    "2 h (€)": "tarif_2h_eur",
    "3 h (€)": "tarif_3h_eur",
    "4 h (€)": "tarif_4h_eur",
    "24 h (€)": "tarif_24h_eur",
}


def clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def fmt_tariff(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    num = float(value)
    return f"{num:g}"


def merge_info_source(existing: str, part: str) -> str:
    src = clean(existing)
    if not src:
        return part
    if part.lower() in src.lower():
        return src
    return f"{src} + {part}"


def integrate(parkings_path: Path, excel_path: Path) -> int:
    parkings = pd.read_csv(parkings_path, sep=CSV_SEP, dtype=str).fillna("")
    scraped = pd.read_excel(excel_path)
    ok = scraped[scraped["Statut"].astype(str).str.strip() == "ok"]

    updated = 0
    for _, row in ok.iterrows():
        pid = clean(row.get("ID parking"))
        if not pid:
            continue
        mask = parkings["parking_id"] == pid
        if not mask.any():
            print(f"  ⚠️  ID introuvable : {pid}")
            continue

        idx = parkings.index[mask][0]
        for excel_col, csv_col in EXCEL_TO_CSV.items():
            val = fmt_tariff(row.get(excel_col))
            if val != "":
                parkings.at[idx, csv_col] = val

        qpark_url = clean(row.get("URL Q-Park"))
        if qpark_url:
            parkings.at[idx, "url_site"] = qpark_url

        parkings.at[idx, "info_source"] = merge_info_source(
            parkings.at[idx, "info_source"], INFO_PART
        )
        updated += 1
        print(f"  ✓ {pid} — 1h={parkings.at[idx, 'tarif_1h_eur']}€")

    parkings.to_csv(parkings_path, sep=CSV_SEP, index=False)
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Intègre tarifs Q-Park validés dans parkings.csv")
    parser.add_argument("--parkings", default=str(DATA_DIR / "parkings.csv"))
    parser.add_argument("--input", default=str(WORK_DIR / "parkings_tarifs_qpark_a_verifier.xlsx"))
    args = parser.parse_args()

    parkings_path = Path(args.parkings).resolve()
    excel_path = Path(args.input).resolve()

    print(f"Intégration depuis {excel_path.name}…")
    n = integrate(parkings_path, excel_path)
    print(f"\n{parkings_path.name} mis à jour : {n} parkings")


if __name__ == "__main__":
    main()
