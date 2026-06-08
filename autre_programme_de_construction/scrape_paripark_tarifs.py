#!/usr/bin/env python3
"""Scrape les tarifs horaires depuis paripark.fr.

Ne modifie PAS parkings.csv — produit un Excel de vérification.
Les 4 parkings Paripark sont listés sur https://www.paripark.fr/fr
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
PARIPARK_BASE = "https://www.paripark.fr/fr"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) parking_ok/1.0"

KNOWN_SLUGS = [
    "haxo",
    "haut-de-belleville-olivier-metra",
    "jardin-des-plantes",
    "moulin-des-pres",
]

DURATION_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^1\s*h\s*$", re.I), "tarif_1h_eur"),
    (re.compile(r"^2\s*h\s*$", re.I), "tarif_2h_eur"),
    (re.compile(r"^3\s*h\s*$", re.I), "tarif_3h_eur"),
    (re.compile(r"^4\s*h\s*$", re.I), "tarif_4h_eur"),
    (re.compile(r"^10\s*h\s*$", re.I), "tarif_10h_eur"),
    (re.compile(r"^12\s*h\s*$", re.I), "tarif_12h_eur"),
    (re.compile(r"^1\s*j\s*$", re.I), "tarif_24h_eur"),
]

TARIFF_COLS = sorted({col for _, col in DURATION_MAP})

SKIP_LABEL = re.compile(
    r"sous-sol|box|moto|vélo|velo|utilitaire|borne|véhicule|vehicule|rdc|sem|semaine|fermé|ferme",
    re.I,
)


def clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text.replace("\xa0", " "))
    return "" if text.lower() == "nan" else text


def norm_addr(value: str) -> str:
    text = unicodedata.normalize("NFKD", clean(value)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def fetch_html(url: str, timeout: float = 60.0) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "fr"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    time.sleep(0.4)
    return html


def discover_slugs(html: str) -> list[str]:
    slugs = re.findall(r'href="/fr/([a-z0-9-]+)"', html)
    skip = {
        "book", "contact", "legal-notice", "news", "services", "service", "user", "page",
    }
    found = [s for s in dict.fromkeys(slugs) if s not in skip and not s.startswith("page/")]
    return found or KNOWN_SLUGS


def parse_price(text: str) -> float | None:
    text = clean(text).replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    if not m:
        return None
    return round(float(m.group(1)), 2)


def parse_hourly_section(html: str) -> tuple[dict[str, float], list[str], str]:
    """Retourne (tarifs colonnes CSV, grille brute, prix 3h entête)."""
    header_3h = ""
    m3 = re.search(r"Prix pour 3h\s*:\s*([\d.]+)", html, re.I)
    if m3:
        header_3h = m3.group(1)

    block_m = re.search(
        r'<div id="subscriptionContent">(.*?)<div id="(?:bookButtonContainer|managerContactInformations)"',
        html,
        re.S | re.I,
    )
    block = block_m.group(1) if block_m else ""
    pairs = re.findall(
        r'<span class="duration">([^<]+)</span><span>([^<]+)</span>',
        block,
    )

    tariffs: dict[str, float] = {}
    grille_parts: list[str] = []

    for label, price_text in pairs:
        label = clean(label)
        if SKIP_LABEL.search(label):
            continue
        price = parse_price(price_text)
        if price is None:
            continue
        grille_parts.append(f"{label}={price}€")
        for pattern, col in DURATION_MAP:
            if pattern.match(label):
                tariffs[col] = price
                break

    if header_3h and "tarif_3h_eur" not in tariffs:
        p3 = parse_price(header_3h)
        if p3 is not None:
            tariffs["tarif_3h_eur"] = p3
            grille_parts.append(f"3 h (entête)={p3}€")

    return tariffs, grille_parts, header_3h


def slug_name_score(slug: str, nom: str) -> float:
    slug_tokens = {t for t in slug.split("-") if len(t) > 2}
    nom_norm = norm_addr(nom)
    nom_tokens = {t for t in nom_norm.split() if len(t) > 2}
    if not slug_tokens or not nom_tokens:
        return 0.0
    return len(slug_tokens & nom_tokens) / len(slug_tokens)


def match_parking_id(slug: str, titre: str, adresse: str, df: pd.DataFrame) -> tuple[str, str]:
    manual = {
        "haut-de-belleville-olivier-metra": "pk_0181_hauts-de-belleville-olivier-metr",
        "moulin-des-pres": "pk_0151_moulin-des-pres",
    }
    if slug in manual:
        return manual[slug], "slug_manuel"

    addr_n = norm_addr(adresse)
    addr_num = re.search(r"\b(\d+)\b", addr_n)
    best_id = ""
    best_score = 0.0
    best_method = ""

    for _, row in df.iterrows():
        row_addr = norm_addr(row.get("adresse", ""))
        if addr_num and row_addr:
            if addr_num.group(1) not in row_addr.split():
                continue

        score = 0.0
        method = ""
        if addr_n and row_addr:
            ta = set(addr_n.split())
            tb = set(row_addr.split())
            overlap = len(ta & tb) / max(len(ta), len(tb)) if ta and tb else 0.0
            if overlap >= 0.55:
                score = overlap
                method = f"adresse score={overlap:.2f}"

        ns = slug_name_score(slug, clean(row.get("nom")))
        if ns >= 0.4:
            score = max(score, ns)
            method = f"nom score={ns:.2f}"

        if score > best_score:
            best_score = score
            best_id = clean(row.get("parking_id"))
            best_method = method

    if best_id and best_score >= 0.55:
        return best_id, best_method
    return "", "non_trouve_base"


def parse_page(slug: str, df: pd.DataFrame) -> dict:
    url = f"{PARIPARK_BASE}/{slug}"
    result = {
        "paripark_slug": slug,
        "parking_id": "",
        "nom_paripark": "",
        "adresse_paripark": "",
        "nom_base": "",
        "adresse_base": "",
        "methode_match": "",
        "paripark_url": url,
        "statut": "pas_trouve",
        "prix_3h_entete": "",
        "grille_brute": "",
        **{c: "" for c in TARIFF_COLS},
    }

    try:
        html = fetch_html(url)
    except urllib.error.HTTPError as exc:
        result["statut"] = f"erreur_http_{exc.code}"
        return result
    except Exception as exc:
        result["statut"] = f"erreur:{type(exc).__name__}"
        return result

    title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
    titre = clean(title_m.group(1).split("|")[0]) if title_m else slug
    result["nom_paripark"] = titre

    addr_m = re.search(
        r'<div class="parking-lot-address[^"]*">([^<]+)</div>',
        html,
        re.I,
    )
    if not addr_m:
        addr_m = re.search(r"(\d+[^<\n]{5,60}750\d{2}\s*Paris)", html, re.I)
    adresse = clean(addr_m.group(1)) if addr_m else ""
    result["adresse_paripark"] = adresse

    tariffs, grille_parts, header_3h = parse_hourly_section(html)
    result["prix_3h_entete"] = header_3h

    pid, method = match_parking_id(slug, titre, adresse, df)
    result["parking_id"] = pid
    result["methode_match"] = method
    if pid:
        row = df[df["parking_id"] == pid]
        if not row.empty:
            result["nom_base"] = clean(row.iloc[0]["nom"])
            result["adresse_base"] = clean(row.iloc[0]["adresse"])

    if tariffs:
        result["statut"] = "ok" if pid else "ok_hors_base"
        for col, val in tariffs.items():
            result[col] = val
        result["grille_brute"] = " | ".join(grille_parts)
    else:
        result["statut"] = "pas_tarifs_horaires" if pid or slug in KNOWN_SLUGS else "pas_trouve"

    return result


def scrape_all(df: pd.DataFrame, slugs: list[str] | None = None) -> pd.DataFrame:
    if not slugs:
        home = fetch_html(PARIPARK_BASE)
        slugs = discover_slugs(home)
    rows = []
    total = len(slugs)
    for i, slug in enumerate(slugs, 1):
        print(f"  [{i}/{total}] {slug}")
        rows.append(parse_page(slug, df))
    return pd.DataFrame(rows)


def to_excel(df: pd.DataFrame, path: Path) -> None:
    rename = {
        "parking_id": "ID parking (base)",
        "nom_base": "Nom (parkings.csv)",
        "adresse_base": "Adresse (parkings.csv)",
        "paripark_slug": "Slug Paripark",
        "nom_paripark": "Nom Paripark",
        "adresse_paripark": "Adresse Paripark",
        "paripark_url": "URL Paripark",
        "methode_match": "Méthode rattachement",
        "statut": "Statut",
        "prix_3h_entete": "Prix 3h (entête page)",
        "grille_brute": "Grille tarifaire",
        "tarif_1h_eur": "1 h (€)",
        "tarif_2h_eur": "2 h (€)",
        "tarif_3h_eur": "3 h (€)",
        "tarif_4h_eur": "4 h (€)",
        "tarif_10h_eur": "10 h (€)",
        "tarif_12h_eur": "12 h (€)",
        "tarif_24h_eur": "24 h / 1-2 j (€)",
    }
    export = df.rename(columns=rename)
    col_order = list(rename.values())
    export = export[[c for c in col_order if c in export.columns]]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name="tarifs Paripark")
        ws = writer.sheets["tarifs Paripark"]
        ws.freeze_panes = "A2"
        for idx, col in enumerate(export.columns, 1):
            letter = chr(64 + idx) if idx <= 26 else "A"
            max_len = max(len(str(col)), export[col].astype(str).str.len().max() if len(export) else 0)
            ws.column_dimensions[letter].width = min(max_len + 2, 50)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape tarifs Paripark → Excel de vérification")
    parser.add_argument("--parkings", default=str(DATA_DIR / "parkings.csv"))
    parser.add_argument("--output", default=str(WORK_DIR / "parkings_tarifs_paripark_a_verifier.xlsx"))
    parser.add_argument("--slug", action="append", help="Un slug Paripark (ex. haut-de-belleville-olivier-metra)")
    args = parser.parse_args()

    parkings_path = Path(args.parkings).resolve()
    output_path = Path(args.output).resolve()
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(parkings_path, sep=CSV_SEP, dtype=str).fillna("")
    slugs = args.slug if args.slug else None

    print("Scraping paripark.fr…")
    scraped = scrape_all(df, slugs)
    to_excel(scraped, output_path)

    ok = scraped["statut"].isin(["ok", "ok_hors_base"]).sum()
    no_hourly = (scraped["statut"] == "pas_tarifs_horaires").sum()
    print(f"\nÉcrit : {output_path}")
    print(f"  parkings Paripark : {len(scraped)}")
    print(f"  tarifs horaires OK : {ok}")
    print(f"  sans tarifs horaires : {no_hourly}")
    print("\n⚠️  parkings.csv non modifié — vérifiez l'Excel avant intégration.")


if __name__ == "__main__":
    main()
