#!/usr/bin/env python3
"""Scrape les tarifs Indigo Neo (api.opngo.com) pour les parkings sans tarif 1h.

Ne modifie PAS parkings.csv — produit un Excel de vérification.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chemins_projet import DATA_DIR, WORK_DIR

import pandas as pd

CSV_SEP = ";"
API_KEY = "QqdFIYjcqh5HK1EWHzdSH28Q3AvzoCHkY4cYMKM2"
API_BASE = "https://api.opngo.com"
INDIGO_BASE = "https://www.indigoneo.fr/fr/parkings"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) parking_ok/1.0"

DURATION_MAP = {
    "PT15M": "tarif_15mn_eur",
    "PT30M": "tarif_30mn_eur",
    "PT1H": "tarif_1h_eur",
    "PT2H": "tarif_2h_eur",
    "PT4H": "tarif_4h_eur",
    "PT8H": "tarif_8h_eur",
    "PT12H": "tarif_12h_eur",
    "PT24H": "tarif_24h_eur",
}

TARIFF_COLS = list(DURATION_MAP.values())


def clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def norm_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", clean(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Z0-9 ]", " ", text.upper())
    text = re.sub(
        r"\b(PARKING|PARC|DE|DU|LA|LE|LES|INDIGO|PARIS|STATIONNEMENT|GARE)\b",
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


def api_get(path: str, params: dict | None = None, pause: float = 0.25) -> dict | list:
    url = f"{API_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {
        "Accept": "application/json",
        "Accept-Language": "fr",
        "x-api-key": API_KEY,
        "Origin": "https://www.indigoneo.fr",
        "User-Agent": USER_AGENT,
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read())
    time.sleep(pause)
    return data


def follow_parkindigo(url: str) -> tuple[str | None, str]:
    if not url:
        return None, ""
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
    try:
        resp = opener.open(req, timeout=20)
        final = resp.geturl()
        m = re.search(r"/parkings/(\d+)/", final)
        if m:
            return m.group(1), "parkindigo_redirect"
        return None, f"redirect_sans_id:{final[:80]}"
    except Exception as exc:
        return None, f"erreur_redirect:{exc}"


def asset_id_from_url(url: str) -> str | None:
    url = clean(url)
    if not url:
        return None
    m = re.search(r"/parkings/(\d+)/", url)
    return m.group(1) if m else None


def search_queries(nom: str, adresse: str) -> list[str]:
    queries: list[str] = []
    nom_clean = re.sub(r"\bINDIGO\b", "", nom, flags=re.I).strip(" -")
    if nom_clean:
        queries.append(nom_clean)
    short = " ".join(tokens(nom))
    if short and short not in queries:
        queries.append(short)
    addr_tokens = [t for t in tokens(adresse) if t not in {"PARIS", "RUE", "AV", "BD", "PLACE"}]
    if addr_tokens:
        queries.append(" ".join(addr_tokens[:4]))
    # dédoublonnage en gardant l'ordre
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        q = q.strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out[:4]


def find_asset_by_search(
    nom: str,
    adresse: str,
    lat: float,
    lon: float,
    *,
    max_dist_m: float = 500.0,
) -> tuple[str | None, str, float, float, str]:
    best: tuple[str, str, float, float] | None = None
    for query in search_queries(nom, adresse):
        try:
            results = api_get("/asset", {"searchText": query, "countryCode": "FR"})
        except Exception:
            continue
        if not isinstance(results, list):
            continue
        for item in results:
            loc = item.get("location") or {}
            rlat = loc.get("latitude")
            rlon = loc.get("longitude")
            if rlat is None or rlon is None:
                continue
            dist = haversine_m(lat, lon, float(rlat), float(rlon))
            if dist > max_dist_m:
                continue
            ns = name_score(nom, clean(item.get("assetName")))
            if dist <= 120 and ns >= 0.2:
                ok = True
            elif dist <= 250 and ns >= 0.35:
                ok = True
            elif dist <= 400 and ns >= 0.5:
                ok = True
            else:
                ok = False
            if not ok:
                continue
            key = (ns, -dist)
            if best is None or key > (best[2], -best[3]):
                best = (
                    str(item.get("id")),
                    clean(item.get("assetName")),
                    ns,
                    dist,
                )
    if best:
        aid, aname, ns, dist = best
        return aid, aname, ns, dist, f"api_search:{aname}"
    return None, "", 0.0, 0.0, ""


def slugify_asset_name(nom: str) -> str:
    text = unicodedata.normalize("NFKD", clean(nom)).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def fetch_pricing_grid(asset_id: str) -> tuple[dict[str, float], str, str]:
    try:
        data = api_get(f"/quotes/asset/{asset_id}/pricingGrid", {"assetId": asset_id})
    except Exception as exc:
        return {}, "", f"erreur_api:{exc}"
    if not isinstance(data, dict):
        return {}, "", "reponse_invalide"
    tariffs: dict[str, float] = {}
    extra: list[str] = []
    for row in data.get("pricing", []) or []:
        duration = clean(row.get("payingDuration"))
        price = row.get("regularPrice") or {}
        amount = price.get("amount") if isinstance(price, dict) else None
        if amount is None:
            continue
        col = DURATION_MAP.get(duration)
        if col:
            tariffs[col] = float(amount)
        else:
            extra.append(f"{duration}={amount}")
    grille_txt = " | ".join(
        f"{d}:{tariffs[c]}€" for d, c in DURATION_MAP.items() if c in tariffs
    )
    if extra:
        grille_txt += (" | " if grille_txt else "") + " | ".join(extra)
    computed = clean(data.get("computedDate"))
    if not tariffs:
        return {}, computed, "grille_vide"
    return tariffs, computed, "ok"


def resolve_asset(row: pd.Series) -> dict:
    nom = clean(row.get("nom"))
    adresse = clean(row.get("adresse"))
    url_site = clean(row.get("url_site"))
    lat = float(clean(row.get("latitude")) or 0)
    lon = float(clean(row.get("longitude")) or 0)

    asset_id: str | None = None
    method = ""
    match_name = ""
    match_score = 0.0
    match_dist = 0.0

    asset_id = asset_id_from_url(url_site)
    if asset_id:
        method = "url_site_indigoneo"
    elif "parkindigo.com" in url_site.lower():
        asset_id, method = follow_parkindigo(url_site)
        time.sleep(0.2)

    if not asset_id and lat and lon:
        asset_id, match_name, match_score, match_dist, method = find_asset_by_search(
            nom, adresse, lat, lon
        )

    indigo_url = f"{INDIGO_BASE}/{asset_id}/parking-{slugify_asset_name(nom)}" if asset_id else ""

    tariffs: dict[str, float] = {}
    computed = ""
    status = "pas_trouve"
    if asset_id:
        tariffs, computed, status = fetch_pricing_grid(asset_id)
        if status == "ok" and not tariffs:
            status = "grille_vide"

    result = {
        "parking_id": clean(row.get("parking_id")),
        "nom": nom,
        "adresse": adresse,
        "operateur": clean(row.get("operateur")),
        "provenance": clean(row.get("provenance")),
        "url_site_base": url_site,
        "indigo_asset_id": asset_id or "",
        "indigo_url": indigo_url,
        "methode_match": method,
        "match_nom_indigo": match_name,
        "match_score": round(match_score, 2) if match_score else "",
        "match_distance_m": round(match_dist) if match_dist else "",
        "statut": status,
        "date_calcul_indigo": computed,
        "grille_brute": "",
        **{c: "" for c in TARIFF_COLS},
    }
    for col, val in tariffs.items():
        result[col] = val
    if tariffs:
        result["grille_brute"] = " | ".join(
            f"{k.replace('tarif_', '').replace('_eur', '')}={v}€" for k, v in tariffs.items()
        )
    return result


def scrape_dataframe(df: pd.DataFrame, *, only_indigo: bool = True) -> pd.DataFrame:
    no_tarif = df[df["tarif_1h_eur"].astype(str).str.strip() == ""]
    if only_indigo:
        no_tarif = no_tarif[no_tarif["operateur"].astype(str).str.upper() == "INDIGO"]
    rows: list[dict] = []
    total = len(no_tarif)
    for i, (_, row) in enumerate(no_tarif.iterrows(), 1):
        print(f"  [{i}/{total}] {clean(row.get('nom'))[:50]}")
        rows.append(resolve_asset(row))
    return pd.DataFrame(rows)


def to_excel(df: pd.DataFrame, path: Path) -> None:
    rename = {
        "parking_id": "ID parking",
        "nom": "Nom",
        "adresse": "Adresse",
        "operateur": "Opérateur",
        "provenance": "Provenance",
        "url_site_base": "URL base (parkings.csv)",
        "indigo_asset_id": "ID Indigo Neo",
        "indigo_url": "URL Indigo Neo",
        "methode_match": "Méthode rattachement",
        "match_nom_indigo": "Nom Indigo trouvé",
        "match_score": "Score nom",
        "match_distance_m": "Distance (m)",
        "statut": "Statut",
        "date_calcul_indigo": "Date calcul tarifs",
        "grille_brute": "Grille tarifaire",
        "tarif_15mn_eur": "15 min (€)",
        "tarif_30mn_eur": "30 min (€)",
        "tarif_1h_eur": "1 h (€)",
        "tarif_2h_eur": "2 h (€)",
        "tarif_4h_eur": "4 h (€)",
        "tarif_8h_eur": "8 h (€)",
        "tarif_12h_eur": "12 h (€)",
        "tarif_24h_eur": "24 h (€)",
    }
    export = df.rename(columns=rename)
    col_order = list(rename.values())
    export = export[[c for c in col_order if c in export.columns]]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name="tarifs Indigo Neo")
        ws = writer.sheets["tarifs Indigo Neo"]
        ws.freeze_panes = "A2"
        for idx, col in enumerate(export.columns, 1):
            letter = chr(64 + idx) if idx <= 26 else "A"
            max_len = max(len(str(col)), export[col].astype(str).str.len().max() if len(export) else 0)
            ws.column_dimensions[letter].width = min(max_len + 2, 45)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape tarifs Indigo Neo → Excel de vérification")
    parser.add_argument("--parkings", default=str(DATA_DIR / "parkings.csv"))
    parser.add_argument("--output", default=str(WORK_DIR / "parkings_tarifs_indigoneo_a_verifier.xlsx"))
    parser.add_argument("--all-operateurs", action="store_true", help="Inclure non-Indigo sans tarif")
    args = parser.parse_args()

    parkings_path = Path(args.parkings).resolve()
    output_path = Path(args.output).resolve()
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(parkings_path, sep=CSV_SEP, dtype=str).fillna("")
    print(f"Scraping Indigo Neo pour parkings sans tarif 1h…")
    scraped = scrape_dataframe(df, only_indigo=not args.all_operateurs)
    to_excel(scraped, output_path)

    ok = (scraped["statut"] == "ok").sum()
    vide = (scraped["statut"] == "grille_vide").sum()
    absent = (scraped["statut"] == "pas_trouve").sum()
    print(f"\nÉcrit : {output_path}")
    print(f"  lignes : {len(scraped)}")
    print(f"  tarifs OK : {ok}")
    print(f"  grille vide : {vide}")
    print(f"  non trouvé : {absent}")
    print("\n⚠️  parkings.csv non modifié — vérifiez l'Excel avant intégration.")


if __name__ == "__main__":
    main()
