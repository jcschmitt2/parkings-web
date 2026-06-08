#!/usr/bin/env python3
"""Scrape les tarifs « sur place » depuis effia.com pour les parkings sans tarif 1h.

Ne modifie PAS parkings.csv — produit un Excel de vérification.
Source : section HTML « Extrait des tarifs » sur chaque fiche parking EFFIA.
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
EFFIA_BASE = "https://www.effia.com/parking"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) parking_ok/1.0"

DURATION_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^15\s*minutes?$", re.I), "tarif_15mn_eur"),
    (re.compile(r"^30\s*minutes?$", re.I), "tarif_30mn_eur"),
    (re.compile(r"^1\s*heure$", re.I), "tarif_1h_eur"),
    (re.compile(r"^90\s*minutes?$", re.I), "tarif_1h30_eur"),
    (re.compile(r"^2\s*heures?$", re.I), "tarif_2h_eur"),
    (re.compile(r"^3\s*heures?$", re.I), "tarif_3h_eur"),
    (re.compile(r"^4\s*heures?$", re.I), "tarif_4h_eur"),
    (re.compile(r"^7\s*heures?$", re.I), "tarif_7h_eur"),
    (re.compile(r"^8\s*heures?$", re.I), "tarif_8h_eur"),
    (re.compile(r"^12\s*heures?$", re.I), "tarif_12h_eur"),
    (re.compile(r"^24\s*heures?$", re.I), "tarif_24h_eur"),
]

TARIFF_COLS = sorted({col for _, col in DURATION_MAP})


def clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def slug_part(nom: str, *, drop_apostrophe: bool = False) -> str:
    text = nom.upper()
    text = re.sub(r"\bPARKING\b", "", text)
    text = re.sub(r"\s*-\s*EFFIA\s*$", "", text, flags=re.I)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    if drop_apostrophe:
        text = text.replace("'", "")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return text


def effia_url_candidates(nom: str, url_site: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(url: str, method: str) -> None:
        url = clean(url)
        if not url or url in seen:
            return
        seen.add(url)
        out.append((url, method))

    if url_site and "effia.com" in url_site.lower():
        add(url_site, "url_site_csv")

    for drop_apo in (False, True):
        slug = slug_part(nom, drop_apostrophe=drop_apo)
        if not slug:
            continue
        method = "slug_nom" if not drop_apo else "slug_nom_sans_apostrophe"
        add(f"{EFFIA_BASE}/parking-{slug}-effia", method)

    return out


def fetch_html(url: str, timeout: float = 90.0) -> tuple[str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "fr"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        final_url = resp.geturl()
        html = resp.read().decode("utf-8", errors="replace")
    time.sleep(0.5)
    return final_url, html


def parse_price(text: str) -> float | None:
    text = clean(text).replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    if not m:
        return None
    return round(float(m.group(1)), 2)


def parse_hourly_tariffs(html: str) -> tuple[dict[str, float], list[str]]:
    block = re.search(
        r"hourly-rates-content.*?<ul class=\"list row\">(.*?)</ul>",
        html,
        re.S | re.I,
    )
    if not block:
        return {}, []

    pairs = re.findall(
        r"<span class=\"small-9[^\"]*\">([^<]+)</span>\s*"
        r"<span class=\"small-3[^\"]*\">([^<]+)</span>",
        block.group(1),
    )

    tariffs: dict[str, float] = {}
    grille_parts: list[str] = []
    for label, price_text in pairs:
        label = clean(label)
        if re.search(r"forfait|abonnement|tranche|mois", label, re.I):
            continue
        price = parse_price(price_text)
        if price is None:
            continue
        grille_parts.append(f"{label}={price}€")
        for pattern, col in DURATION_MAP:
            if pattern.match(label):
                tariffs[col] = price
                break
    return tariffs, grille_parts


def resolve_effia(row: pd.Series) -> dict:
    nom = clean(row.get("nom"))
    adresse = clean(row.get("adresse"))
    url_site = clean(row.get("url_site"))

    result = {
        "parking_id": clean(row.get("parking_id")),
        "nom": nom,
        "adresse": adresse,
        "operateur": clean(row.get("operateur")),
        "provenance": clean(row.get("provenance")),
        "url_site_base": url_site,
        "effia_url": "",
        "methode_match": "",
        "titre_page": "",
        "statut": "pas_trouve",
        "grille_brute": "",
        **{c: "" for c in TARIFF_COLS},
    }

    for url, method in effia_url_candidates(nom, url_site):
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

        title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
        title = clean(title_m.group(1)) if title_m else ""
        if "404" in title.lower() or "page non trouvée" in html.lower()[:5000]:
            continue

        tariffs, grille_parts = parse_hourly_tariffs(html)
        result["effia_url"] = final_url
        result["methode_match"] = method
        result["titre_page"] = title[:120]

        if tariffs:
            result["statut"] = "ok"
            for col, val in tariffs.items():
                result[col] = val
            result["grille_brute"] = " | ".join(grille_parts)
        else:
            result["statut"] = "page_sans_tarifs"
        return result

    return result


def scrape_dataframe(df: pd.DataFrame, *, only_effia: bool = True) -> pd.DataFrame:
    no_tarif = df[df["tarif_1h_eur"].astype(str).str.strip() == ""]
    if only_effia:
        no_tarif = no_tarif[no_tarif["operateur"].astype(str).str.upper() == "EFFIA"]

    rows: list[dict] = []
    total = len(no_tarif)
    for i, (_, row) in enumerate(no_tarif.iterrows(), 1):
        print(f"  [{i}/{total}] {clean(row.get('nom'))[:50]}")
        rows.append(resolve_effia(row))
    return pd.DataFrame(rows)


def to_excel(df: pd.DataFrame, path: Path) -> None:
    rename = {
        "parking_id": "ID parking",
        "nom": "Nom",
        "adresse": "Adresse",
        "operateur": "Opérateur",
        "provenance": "Provenance",
        "url_site_base": "URL base (parkings.csv)",
        "effia_url": "URL EFFIA",
        "methode_match": "Méthode rattachement",
        "titre_page": "Titre page EFFIA",
        "statut": "Statut",
        "grille_brute": "Grille tarifaire",
        "tarif_15mn_eur": "15 min (€)",
        "tarif_30mn_eur": "30 min (€)",
        "tarif_1h_eur": "1 h (€)",
        "tarif_1h30_eur": "1 h 30 (€)",
        "tarif_2h_eur": "2 h (€)",
        "tarif_3h_eur": "3 h (€)",
        "tarif_4h_eur": "4 h (€)",
        "tarif_7h_eur": "7 h (€)",
        "tarif_8h_eur": "8 h (€)",
        "tarif_12h_eur": "12 h (€)",
        "tarif_24h_eur": "24 h (€)",
    }
    export = df.rename(columns=rename)
    col_order = list(rename.values())
    export = export[[c for c in col_order if c in export.columns]]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name="tarifs EFFIA")
        ws = writer.sheets["tarifs EFFIA"]
        ws.freeze_panes = "A2"
        for idx, col in enumerate(export.columns, 1):
            letter = chr(64 + idx) if idx <= 26 else "A"
            max_len = max(len(str(col)), export[col].astype(str).str.len().max() if len(export) else 0)
            ws.column_dimensions[letter].width = min(max_len + 2, 50)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape tarifs EFFIA → Excel de vérification")
    parser.add_argument("--parkings", default=str(DATA_DIR / "parkings.csv"))
    parser.add_argument("--output", default=str(WORK_DIR / "parkings_tarifs_effia_a_verifier.xlsx"))
    parser.add_argument("--all-operateurs", action="store_true")
    parser.add_argument("--parking-id", help="Un seul parking_id à tester")
    args = parser.parse_args()

    parkings_path = Path(args.parkings).resolve()
    output_path = Path(args.output).resolve()
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(parkings_path, sep=CSV_SEP, dtype=str).fillna("")
    if args.parking_id:
        df = df[df["parking_id"] == args.parking_id]
        if df.empty:
            raise SystemExit(f"parking_id introuvable : {args.parking_id}")

    print("Scraping EFFIA pour parkings sans tarif 1h…")
    scraped = scrape_dataframe(df, only_effia=not args.all_operateurs and not args.parking_id)
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
