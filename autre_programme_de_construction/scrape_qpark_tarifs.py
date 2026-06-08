#!/usr/bin/env python3
"""Scrape les tarifs Q-Park via l'API GetTariffsForFacility.

Ne modifie PAS parkings.csv — produit un Excel de vérification.
Source page : https://www.q-park.fr/fr-fr/villes/{ville}/{slug}/
API : /api/ParkingFacility/GetTariffsForFacility?facilityId={uuid}&countryCode=FR
"""
from __future__ import annotations

import argparse
import json
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
QPARK_BASE = "https://www.q-park.fr/fr-fr/villes"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) parking_ok/1.0"

SLUG_MANUAL: dict[str, tuple[str, str]] = {
    "pk_0146_bastille-saint-antoine": ("paris", "bastille-saint-antoine"),
    "pk_0166_parchamp": ("boulogne-billancourt", "parchamp"),
    "pk_0177_villette-musique": ("paris", "cité-de-la-musique-la-villette"),
    "pk_0178_philharmonie": ("paris", "philharmonie"),
}

DURATION_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^15\s*minutes?$", re.I), "tarif_15mn_eur"),
    (re.compile(r"^30\s*minutes?$", re.I), "tarif_30mn_eur"),
    (re.compile(r"^1\s*heure$", re.I), "tarif_1h_eur"),
    (re.compile(r"^2\s*heures?$", re.I), "tarif_2h_eur"),
    (re.compile(r"^3\s*heures?$", re.I), "tarif_3h_eur"),
    (re.compile(r"^4\s*heures?$", re.I), "tarif_4h_eur"),
    (re.compile(r"^24\s*heures?$", re.I), "tarif_24h_eur"),
]

SKIP_NAMES = re.compile(r"ticket perdu|forfait|abonnement", re.I)
TARIFF_COLS = sorted({col for _, col in DURATION_MAP})


def clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def slug_from_nom(nom: str) -> str:
    text = nom.upper()
    text = re.sub(r"\bQ-PARK\b", "", text)
    text = re.sub(r"\bPARKING\b", "", text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")


def city_from_adresse(adresse: str) -> str:
    addr = clean(adresse).lower()
    if "boulogne" in addr:
        return "boulogne-billancourt"
    return "paris"


def fetch(url: str, *, accept_json: bool = False, referer: str = "") -> str:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "fr"}
    if accept_json:
        headers["Accept"] = "application/json"
        headers["Content-Type"] = "application/json"
        headers["X-Requested-With"] = "XMLHttpRequest"
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    time.sleep(0.35)
    return data.decode("utf-8", errors="replace") if not accept_json else data.decode("utf-8")


def parse_price(text: str) -> float | None:
    text = clean(text).replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    if not m:
        return None
    return round(float(m.group(1)), 2)


def extract_facility_uuid(html: str) -> str:
    m = re.search(r'"FacilityId"\s*:\s*"([a-f0-9-]{36})"', html, re.I)
    return m.group(1) if m else ""


def qpark_url(city: str, slug: str) -> str:
    from urllib.parse import quote
    return f"{QPARK_BASE}/{city}/{quote(slug)}/"


def fetch_tariffs_api(facility_uuid: str, referer: str) -> list[dict]:
    url = (
        "https://www.q-park.fr/api/ParkingFacility/GetTariffsForFacility"
        f"?facilityId={facility_uuid}&countryCode=FR"
    )
    raw = fetch(url, accept_json=True, referer=referer)
    data = json.loads(raw)
    return data if isinstance(data, list) else []


def parse_tariff_groups(groups: list[dict]) -> tuple[dict[str, float], list[str]]:
    tariffs: dict[str, float] = {}
    grille: list[str] = []

    for group in groups:
        gname = clean(group.get("GroupName"))
        if gname and "sur place" not in gname.lower() and "tarif" not in gname.lower():
            continue
        for item in group.get("Tariffs") or []:
            name = clean(item.get("Name"))
            if SKIP_NAMES.search(name):
                continue
            price = parse_price(clean(item.get("FormattedPrice")))
            if price is None:
                continue
            grille.append(f"{name}={price}€")
            for pattern, col in DURATION_MAP:
                if pattern.match(name):
                    tariffs[col] = price
                    break

    return tariffs, grille


def url_candidates(row: pd.Series) -> list[tuple[str, str, str]]:
    pid = clean(row.get("parking_id"))
    nom = clean(row.get("nom"))
    adresse = clean(row.get("adresse"))
    url_site = clean(row.get("url_site"))
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    def add(city: str, slug: str, method: str) -> None:
        url = qpark_url(city, slug)
        if url not in seen:
            seen.add(url)
            out.append((url, method, city))

    if "q-park.fr" in url_site.lower():
        add_from_url = url_site
        m = re.search(r"/villes/([^/]+)/([^/?#]+)", add_from_url, re.I)
        if m:
            add(m.group(1), m.group(2), "url_site_csv")

    if pid in SLUG_MANUAL:
        city, slug = SLUG_MANUAL[pid]
        add(city, slug, "slug_manuel")

    city = city_from_adresse(adresse)
    slug = slug_from_nom(nom)
    if slug:
        add(city, slug, "slug_nom")

    return out


def resolve_qpark(row: pd.Series) -> dict:
    nom = clean(row.get("nom"))
    adresse = clean(row.get("adresse"))
    result = {
        "parking_id": clean(row.get("parking_id")),
        "nom": nom,
        "adresse": adresse,
        "operateur": clean(row.get("operateur")),
        "provenance": clean(row.get("provenance")),
        "url_site_base": clean(row.get("url_site")),
        "qpark_url": "",
        "qpark_facility_id": "",
        "methode_match": "",
        "titre_page": "",
        "statut": "pas_trouve",
        "grille_brute": "",
        **{c: "" for c in TARIFF_COLS},
    }

    for page_url, method, _city in url_candidates(row):
        try:
            html = fetch(page_url, referer=page_url)
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

        facility_uuid = extract_facility_uuid(html)
        if not facility_uuid:
            result["statut"] = "pas_facility_id"
            result["qpark_url"] = page_url
            result["methode_match"] = method
            continue

        title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
        titre = clean(title_m.group(1).split("|")[0]) if title_m else ""

        try:
            groups = fetch_tariffs_api(facility_uuid, page_url)
        except Exception as exc:
            result["statut"] = f"erreur_api:{type(exc).__name__}"
            result["qpark_url"] = page_url
            result["qpark_facility_id"] = facility_uuid
            result["methode_match"] = method
            return result

        tariffs, grille = parse_tariff_groups(groups)
        result["qpark_url"] = page_url
        result["qpark_facility_id"] = facility_uuid
        result["methode_match"] = method
        result["titre_page"] = titre[:120]

        if tariffs:
            result["statut"] = "ok"
            for col, val in tariffs.items():
                result[col] = val
            result["grille_brute"] = " | ".join(grille)
            return result
        result["statut"] = "api_sans_tarifs"

    return result


def scrape_dataframe(df: pd.DataFrame, *, only_qpark: bool = True) -> pd.DataFrame:
    no_tarif = df[df["tarif_1h_eur"].astype(str).str.strip() == ""]
    if only_qpark:
        no_tarif = no_tarif[no_tarif["operateur"].astype(str).str.upper() == "Q-PARK"]

    rows: list[dict] = []
    total = len(no_tarif)
    for i, (_, row) in enumerate(no_tarif.iterrows(), 1):
        print(f"  [{i}/{total}] {clean(row.get('nom'))[:50]}")
        rows.append(resolve_qpark(row))
    return pd.DataFrame(rows)


def to_excel(df: pd.DataFrame, path: Path) -> None:
    rename = {
        "parking_id": "ID parking",
        "nom": "Nom",
        "adresse": "Adresse",
        "operateur": "Opérateur",
        "provenance": "Provenance",
        "url_site_base": "URL base (parkings.csv)",
        "qpark_url": "URL Q-Park",
        "qpark_facility_id": "ID facility Q-Park",
        "methode_match": "Méthode rattachement",
        "titre_page": "Titre page",
        "statut": "Statut",
        "grille_brute": "Grille tarifaire",
        "tarif_15mn_eur": "15 min (€)",
        "tarif_30mn_eur": "30 min (€)",
        "tarif_1h_eur": "1 h (€)",
        "tarif_2h_eur": "2 h (€)",
        "tarif_3h_eur": "3 h (€)",
        "tarif_4h_eur": "4 h (€)",
        "tarif_24h_eur": "24 h (€)",
    }
    export = df.rename(columns=rename)
    col_order = list(rename.values())
    export = export[[c for c in col_order if c in export.columns]]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name="tarifs Q-Park")
        ws = writer.sheets["tarifs Q-Park"]
        ws.freeze_panes = "A2"
        for idx, col in enumerate(export.columns, 1):
            letter = chr(64 + idx) if idx <= 26 else "A"
            max_len = max(len(str(col)), export[col].astype(str).str.len().max() if len(export) else 0)
            ws.column_dimensions[letter].width = min(max_len + 2, 50)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape tarifs Q-Park → Excel de vérification")
    parser.add_argument("--parkings", default=str(DATA_DIR / "parkings.csv"))
    parser.add_argument("--output", default=str(WORK_DIR / "parkings_tarifs_qpark_a_verifier.xlsx"))
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

    print("Scraping Q-Park pour parkings sans tarif 1h…")
    scraped = scrape_dataframe(df, only_qpark=not args.all_operateurs and not args.parking_id)
    to_excel(scraped, output_path)

    ok = (scraped["statut"] == "ok").sum()
    vide = (scraped["statut"] == "api_sans_tarifs").sum()
    absent = (scraped["statut"] == "pas_trouve").sum()
    print(f"\nÉcrit : {output_path}")
    print(f"  lignes : {len(scraped)}")
    print(f"  tarifs OK : {ok}")
    print(f"  API sans tarifs : {vide}")
    print(f"  non trouvé : {absent}")
    print("\n⚠️  parkings.csv non modifié — vérifiez l'Excel avant intégration.")


if __name__ == "__main__":
    main()
