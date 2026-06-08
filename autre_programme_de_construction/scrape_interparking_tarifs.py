#!/usr/bin/env python3
"""Scrape les tarifs « Tarif normal » depuis interparking.fr.

Ne modifie PAS parkings.csv — produit un Excel de vérification.
Utilise la colonne « Prix » (tarif sur place, sans réduction Pcard+).
"""
from __future__ import annotations

import argparse
import re
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chemins_projet import DATA_DIR, WORK_DIR

import pandas as pd

CSV_SEP = ";"
INTERPARKING_BASE = "https://www.interparking.fr/fr/parkings/paris"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) parking_ok/1.0"

SLUG_MANUAL = {
    "pk_0133_mazarine-odeon": "mazarine-odeon",
    "pk_0152_salpetriere-italie": "salpetriere-italie",
    "pk_0154_tour-montparnasse": "tour-montparnasse",
}

DURATION_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^15\s*minutes?$", re.I), "tarif_15mn_eur"),
    (re.compile(r"^30\s*minutes?$", re.I), "tarif_30mn_eur"),
    (re.compile(r"^1\s*heure$", re.I), "tarif_1h_eur"),
    (re.compile(r"^90\s*minutes?$", re.I), "tarif_1h30_eur"),
    (re.compile(r"^2\s*heures?$", re.I), "tarif_2h_eur"),
    (re.compile(r"^3\s*heures?$", re.I), "tarif_3h_eur"),
    (re.compile(r"^4\s*heures?$", re.I), "tarif_4h_eur"),
    (re.compile(r"^24\s*heures?$", re.I), "tarif_24h_eur"),
    (re.compile(r"^1\s*jour$", re.I), "tarif_24h_eur"),
]

TARIFF_COLS = sorted({col for _, col in DURATION_MAP})


def clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text.replace("\xa0", " ").replace("\u202f", " "))
    return "" if text.lower() == "nan" else text


def slug_from_nom(nom: str) -> str:
    text = nom.upper()
    text = re.sub(r"\bPARKING\b", "", text)
    text = re.sub(r"\bINTERPARKING\b", "", text)
    text = re.sub(r"\s*-\s*", " ", text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")


def fetch_html(url: str, timeout: float = 60.0) -> tuple[str, str]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "fr"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        final_url = resp.geturl()
        html = resp.read().decode("utf-8", errors="replace")
    time.sleep(0.4)
    return final_url, html


def parse_price(text: str) -> float | None:
    text = clean(text).replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    if not m:
        return None
    return round(float(m.group(1)), 2)


def strip_tags(text: str) -> str:
    return clean(re.sub(r"<[^>]+>", " ", text))


def parse_tarif_normal(html: str) -> tuple[dict[str, float], list[str]]:
    """Parse le tableau « Tarif normal » — colonne Prix (dernière colonne tarif)."""
    cap_m = re.search(
        r"Tarif normal</h3></caption><thead>.*?<tbody>(.*?)</tbody>",
        html,
        re.S | re.I,
    )
    if not cap_m:
        cap_m = re.search(
            r"Tarif normal.*?<tbody>(.*?)</tbody>",
            html,
            re.S | re.I,
        )
    if not cap_m:
        return {}, []

    tariffs: dict[str, float] = {}
    grille_parts: list[str] = []

    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", cap_m.group(1), re.S | re.I):
        cells = [
            strip_tags(c)
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)
        ]
        if len(cells) < 2:
            continue
        label = cells[0]
        if re.match(r"durée", label, re.I):
            continue
        # 3 colonnes : Durée | Pcard+ | Prix — on prend Prix
        price_text = cells[-1] if len(cells) >= 3 else cells[1]
        price = parse_price(price_text)
        if price is None:
            continue
        grille_parts.append(f"{label}={price}€")
        for pattern, col in DURATION_MAP:
            if pattern.match(label):
                tariffs[col] = price
                break

    return tariffs, grille_parts


def url_candidates(row: pd.Series) -> list[tuple[str, str]]:
    pid = clean(row.get("parking_id"))
    nom = clean(row.get("nom"))
    url_site = clean(row.get("url_site"))
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(url: str, method: str) -> None:
        if url and url not in seen:
            seen.add(url)
            out.append((url, method))

    if "interparking" in url_site.lower():
        add(url_site, "url_site_csv")

    if pid in SLUG_MANUAL:
        add(f"{INTERPARKING_BASE}/{SLUG_MANUAL[pid]}/", "slug_manuel")

    slug = slug_from_nom(nom)
    if slug:
        add(f"{INTERPARKING_BASE}/{slug}/", "slug_nom")

    return out


def resolve_interparking(row: pd.Series) -> dict:
    nom = clean(row.get("nom"))
    adresse = clean(row.get("adresse"))
    result = {
        "parking_id": clean(row.get("parking_id")),
        "nom": nom,
        "adresse": adresse,
        "operateur": clean(row.get("operateur")),
        "provenance": clean(row.get("provenance")),
        "url_site_base": clean(row.get("url_site")),
        "interparking_url": "",
        "methode_match": "",
        "titre_page": "",
        "statut": "pas_trouve",
        "grille_brute": "",
        **{c: "" for c in TARIFF_COLS},
    }

    for url, method in url_candidates(row):
        try:
            final_url, html = fetch_html(url)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            result["statut"] = f"erreur_http_{exc.code}"
            result["methode_match"] = method
            return result
        except Exception as exc:
            result["statut"] = f"erreur:{type(exc).__name__}"
            result["methode_match"] = method
            return result

        if "404" in html[:3000].lower() and "Tarif normal" not in html:
            continue

        title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
        titre = clean(title_m.group(1).split("|")[0]) if title_m else ""
        tariffs, grille = parse_tarif_normal(html)

        result["interparking_url"] = final_url
        result["methode_match"] = method
        result["titre_page"] = titre[:120]

        if tariffs:
            result["statut"] = "ok"
            for col, val in tariffs.items():
                result[col] = val
            result["grille_brute"] = " | ".join(grille)
            return result
        result["statut"] = "page_sans_tarifs"

    return result


def scrape_dataframe(df: pd.DataFrame, *, only_interparking: bool = True) -> pd.DataFrame:
    no_tarif = df[df["tarif_1h_eur"].astype(str).str.strip() == ""]
    if only_interparking:
        no_tarif = no_tarif[no_tarif["operateur"].astype(str).str.upper() == "INTERPARKING"]

    rows: list[dict] = []
    total = len(no_tarif)
    for i, (_, row) in enumerate(no_tarif.iterrows(), 1):
        print(f"  [{i}/{total}] {clean(row.get('nom'))[:50]}")
        rows.append(resolve_interparking(row))
    return pd.DataFrame(rows)


def to_excel(df: pd.DataFrame, path: Path) -> None:
    rename = {
        "parking_id": "ID parking",
        "nom": "Nom",
        "adresse": "Adresse",
        "operateur": "Opérateur",
        "provenance": "Provenance",
        "url_site_base": "URL base (parkings.csv)",
        "interparking_url": "URL Interparking",
        "methode_match": "Méthode rattachement",
        "titre_page": "Titre page",
        "statut": "Statut",
        "grille_brute": "Grille tarifaire (Prix)",
        "tarif_15mn_eur": "15 min (€)",
        "tarif_30mn_eur": "30 min (€)",
        "tarif_1h_eur": "1 h (€)",
        "tarif_1h30_eur": "1 h 30 (€)",
        "tarif_2h_eur": "2 h (€)",
        "tarif_3h_eur": "3 h (€)",
        "tarif_4h_eur": "4 h (€)",
        "tarif_24h_eur": "24 h (€)",
    }
    export = df.rename(columns=rename)
    col_order = list(rename.values())
    export = export[[c for c in col_order if c in export.columns]]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name="tarifs Interparking")
        ws = writer.sheets["tarifs Interparking"]
        ws.freeze_panes = "A2"
        for idx, col in enumerate(export.columns, 1):
            letter = chr(64 + idx) if idx <= 26 else "A"
            max_len = max(len(str(col)), export[col].astype(str).str.len().max() if len(export) else 0)
            ws.column_dimensions[letter].width = min(max_len + 2, 50)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape tarifs Interparking → Excel de vérification")
    parser.add_argument("--parkings", default=str(DATA_DIR / "parkings.csv"))
    parser.add_argument("--output", default=str(WORK_DIR / "parkings_tarifs_interparking_a_verifier.xlsx"))
    parser.add_argument("--all-operateurs", action="store_true")
    parser.add_argument("--parking-id", help="Un seul parking_id")
    args = parser.parse_args()

    parkings_path = Path(args.parkings).resolve()
    output_path = Path(args.output).resolve()
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(parkings_path, sep=CSV_SEP, dtype=str).fillna("")
    if args.parking_id:
        df = df[df["parking_id"] == args.parking_id]
        if df.empty:
            raise SystemExit(f"parking_id introuvable : {args.parking_id}")

    print("Scraping Interparking pour parkings sans tarif 1h…")
    scraped = scrape_dataframe(df, only_interparking=not args.all_operateurs and not args.parking_id)
    to_excel(scraped, output_path)

    ok = (scraped["statut"] == "ok").sum()
    vide = (scraped["statut"] == "page_sans_tarifs").sum()
    absent = (scraped["statut"] == "pas_trouve").sum()
    print(f"\nÉcrit : {output_path}")
    print(f"  lignes : {len(scraped)}")
    print(f"  tarifs OK : {ok}")
    print(f"  page sans tarifs : {vide}")
    print(f"  non trouvé : {absent}")
    print("\n⚠️  parkings.csv non modifié — vérifiez l'Excel avant intégration.")


if __name__ == "__main__":
    main()
