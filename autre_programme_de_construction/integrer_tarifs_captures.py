#!/usr/bin/env python3
"""Intègre les tarifs lus sur les captures d'écran (juin 2026)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chemins_projet import DATA_DIR, WORK_DIR

CSV_SEP = ";"
INFO_PART = "tarif capture ecran"

# parking_id → {colonne csv: valeur}
# Colonne « Prix » (Interparking) ou tarif sur place / voiture standard
TARIFFS: dict[str, dict[str, str]] = {
    "pk_0182_parking-pyrenees-du-clos": {
        "tarif_1h_eur": "4.5",
        "tarif_2h_eur": "9",
        "tarif_3h_eur": "13",
        "tarif_4h_eur": "17",
        "tarif_7h_eur": "21",
        "tarif_24h_eur": "29.9",
    },
    "pk_0130_place-des-fetes": {
        "tarif_1h_eur": "4.5",
        "tarif_2h_eur": "9",
        "tarif_3h_eur": "13",
        "tarif_4h_eur": "17",
        "tarif_7h_eur": "21",
        "tarif_24h_eur": "29.9",
    },
    "pk_0125_clichy-montmartre": {
        "tarif_15mn_eur": "1.5",
        "tarif_30mn_eur": "2.5",
        "tarif_1h_eur": "3.9",
        "tarif_2h_eur": "8.3",
        "tarif_3h_eur": "13.3",
        "tarif_24h_eur": "28.6",
    },
    "pk_0124_cambronne-rue-du-commerce": {
        "tarif_15mn_eur": "0.9",
        "tarif_30mn_eur": "1.8",
        "tarif_1h_eur": "3.6",
        "tarif_2h_eur": "7.2",
        "tarif_3h_eur": "10.8",
        "tarif_24h_eur": "27",
    },
    "pk_0168_cardinet-batignolles": {
        "tarif_15mn_eur": "1.2",
        "tarif_1h_eur": "5.2",
        "tarif_7h_eur": "28.5",
        "tarif_24h_eur": "45.6",
    },
    "pk_0143_garage-de-la-place-saint-georges": {
        "tarif_1h_eur": "7.5",
        "tarif_2h_eur": "10.7",
        "tarif_24h_eur": "45",
    },
    "pk_0172_montmartre-garage": {
        "tarif_1h_eur": "6",
        "tarif_2h_eur": "10",
    },
    "pk_0164_parc-de-l-aquaboulevard-equinoxe": {
        "tarif_1h_eur": "3.6",
        "tarif_2h_eur": "7.2",
        "tarif_24h_eur": "36",
    },
    "pk_0127_wurtz": {
        "tarif_15mn_eur": "1",
        "tarif_30mn_eur": "2",
        "tarif_1h_eur": "4",
        "tarif_1h30_eur": "5.9",
        "tarif_2h_eur": "7.9",
        "tarif_3h_eur": "11.9",
        "tarif_4h_eur": "15.4",
        "tarif_7h_eur": "26",
        "tarif_8h_eur": "29.5",
        "tarif_12h_eur": "38.7",
        "tarif_24h_eur": "38.7",
    },
    "pk_0145_ledru-rollin": {
        "tarif_1h_eur": "5.2",
        "tarif_24h_eur": "50",
    },
    "pk_0175_cur-montmartre-marche-st-pierre": {
        "tarif_15mn_eur": "1.1",
        "tarif_30mn_eur": "2.2",
        "tarif_1h_eur": "4.4",
        "tarif_2h_eur": "8.8",
        "tarif_3h_eur": "13.2",
        "tarif_24h_eur": "39.6",
    },
    "pk_0153_massena": {
        "tarif_15mn_eur": "0.9",
        "tarif_30mn_eur": "1.8",
        "tarif_1h_eur": "3.6",
        "tarif_1h30_eur": "5.4",
        "tarif_2h_eur": "7.2",
        "tarif_3h_eur": "11.4",
        "tarif_4h_eur": "15.6",
        "tarif_24h_eur": "41.8",
    },
    "pk_0176_pigalle-theatres": {
        "tarif_15mn_eur": "2",
        "tarif_30mn_eur": "3",
        "tarif_1h_eur": "5",
        "tarif_2h_eur": "9",
        "tarif_3h_eur": "13",
        "tarif_4h_eur": "17",
        "tarif_7h_eur": "29",
        "tarif_8h_eur": "33",
        "tarif_12h_eur": "48",
        "tarif_24h_eur": "48",
    },
}

FILE_MAP = [
    ("PARKING_PYRÉNÉES_DU_CLOS_-_PARIS_FRANCE_PARKING_20ÈME.png", "pk_0182_parking-pyrenees-du-clos", "France Parking — tarif internet"),
    ("PARKING_PLACE_DES_FÊTES_-_PARIS_FRANCE_PARKING_19ÈME.png", "pk_0130_place-des-fetes", "France Parking — tarif internet"),
    ("Clichy_Montmartre.png", "pk_0125_clichy-montmartre", "Interparking — colonne Prix"),
    ("Cambronne___Rue_du_Commerce.png", "pk_0124_cambronne-rue-du-commerce", "Interparking — colonne Prix"),
    ("Q-PARK_CARDINET_BATIGNOLLES.png", "pk_0168_cardinet-batignolles", "Q-Park — tarifs sur place"),
    ("GARAGE_DE_LA_PLACE_SAINT-GEORGES.png", "pk_0143_garage-de-la-place-saint-georges", "Site parking-clauzel — voiture"),
    ("PARKING_MONTMARTRE_GARAGE.png", "pk_0172_montmartre-garage", "Parkopedia — tarif jour"),
    ("PARKING_INDIGO_PARIS_AQUABOULEVARD.png", "pk_0164_parc-de-l-aquaboulevard-equinoxe", "Parkopedia / fiche"),
    ("Wurtz.png", "pk_0127_wurtz", "Affiche Interparking sur place"),
    ("LEDRU_ROLLIN_PARKING.png", "pk_0145_ledru-rollin", "Site parkingledrurollin — 1h=4×1,30€, forfait 24h"),
    ("CŒUR_MONTMARTRE_MARCHÉ_ST-PIERRE.png", "pk_0175_cur-montmartre-marche-st-pierre", "Site parkingcoeurmontmartre"),
    ("PARKING_INDIGO_PARIS_MASSÉNA_13.png", "pk_0153_massena", "Parkopedia"),
    ("PARKING_BLANCHE_PIGALLE.png", "pk_0176_pigalle-theatres", "Site parking-blanche-pigalle — grille gauche"),
    ("Capture_d_écran_2026-06-06_à_12.39.22.png", "", "Non associé (voiture 7,50€ / moto 4,50€ — 1h seulement)"),
]


def merge_info_source(existing: str, part: str) -> str:
    src = (existing or "").strip()
    if not src:
        return part
    if part.lower() in src.lower():
        return src
    return f"{src} + {part}"


def main() -> None:
    path = DATA_DIR / "parkings.csv"
    df = pd.read_csv(path, sep=CSV_SEP, dtype=str).fillna("")

    updated = 0
    for pid, tariffs in TARIFFS.items():
        mask = df["parking_id"] == pid
        if not mask.any():
            print(f"  ⚠️  introuvable : {pid}")
            continue
        idx = df.index[mask][0]
        for col, val in tariffs.items():
            df.at[idx, col] = val
        df.at[idx, "info_source"] = merge_info_source(df.at[idx, "info_source"], INFO_PART)
        updated += 1
        print(f"  ✓ {pid} — 1h={tariffs.get('tarif_1h_eur', '?')}€")

    df.to_csv(path, sep=CSV_SEP, index=False)
    print(f"\n{updated} parkings mis à jour dans parkings.csv")

    # Excel liste des captures
    rows = []
    for fname, pid, source in FILE_MAP:
        nom = ""
        statut = "non associé"
        t1h = ""
        if pid:
            m = df["parking_id"] == pid
            if m.any():
                r = df[m].iloc[0]
                nom = r["nom"]
                t1h = r.get("tarif_1h_eur", "")
                statut = "intégré" if pid in TARIFFS else "en attente"
        rows.append({
            "Fichier capture": fname,
            "ID parking": pid,
            "Nom": nom,
            "Source tarif": source,
            "Statut": statut,
            "1 h (€)": t1h,
        })
    listing = pd.DataFrame(rows)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    out = WORK_DIR / "captures_tarifs_liste.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        listing.to_excel(w, index=False, sheet_name="captures")
        w.sheets["captures"].freeze_panes = "A2"
    print(f"Liste écrite : {out}")


if __name__ == "__main__":
    main()
