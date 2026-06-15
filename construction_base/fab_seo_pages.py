#!/usr/bin/env python3
"""Génère les pages SEO /parking-proche-* et met à jour sitemap.xml + index.html."""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chemins_projet import DATA_DIR

LANDINGS_JSON = DATA_DIR / "parkeco_seo_landings.json"
INDEX_HTML = ROOT / "index.html"
SITEMAP_XML = ROOT / "sitemap.xml"
SITE_ORIGIN = "https://parkeco.fr"
SEO_BLOCK_BEGIN = "// SEO_LANDINGS:BEGIN"
SEO_BLOCK_END = "// SEO_LANDINGS:END"


def arrondissement_short_label(n: int) -> str:
    return "Paris 1er" if n == 1 else f"Paris {n}e"


def arrondissement_slug(n: int) -> str:
    return "parking-proche-paris-1er" if n == 1 else f"parking-proche-paris-{n}e"


def build_arrondissement_landings() -> list[dict]:
    landings: list[dict] = []
    for n in range(1, 21):
        postcode = f"750{n:02d}"
        label = arrondissement_short_label(n)
        slug = arrondissement_slug(n)
        landings.append(
            {
                "slug": slug,
                "mode": "arrondissement",
                "postcode": postcode,
                "searchQuery": postcode,
                "placeLabel": label,
                "title": f"Parking public {label} — tarifs et carte | Parkeco",
                "description": (
                    f"Trouvez tous les parkings publics de {label} à Paris. "
                    "Carte, tarifs et comparaison avec la voirie : évitez jusqu'à 18 €/h."
                ),
                "og_title": f"Parking public {label} | Parkeco",
                "og_description": (
                    f"Parkings publics de {label} à Paris : carte interactive, "
                    "tarifs et comparaison avec le stationnement en voirie."
                ),
                "priority": 0.85,
                "changefreq": "weekly",
            }
        )
    return landings


def load_landings() -> list[dict]:
    data = json.loads(LANDINGS_JSON.read_text(encoding="utf-8"))
    places = data.get("landings", [])
    if not places:
        raise SystemExit("Aucune landing dans parkeco_seo_landings.json")
    arrondissements = build_arrondissement_landings()
    return places + arrondissements


def landing_runtime_config(landing: dict) -> dict:
    slug = landing["slug"]
    cfg: dict = {
        "title": landing["title"],
        "description": landing["description"],
        "canonical": f"{SITE_ORIGIN}/{slug}",
        "og_title": landing.get("og_title") or landing["title"],
        "og_description": landing.get("og_description") or landing["description"],
    }
    mode = landing.get("mode", "place")
    cfg["mode"] = mode
    if landing.get("placeLabel"):
        cfg["placeLabel"] = landing["placeLabel"]
    if mode == "arrondissement":
        cfg["postcode"] = landing["postcode"]
        cfg["searchQuery"] = landing.get("searchQuery") or landing["postcode"]
    else:
        cfg["searchQuery"] = landing["searchQuery"]
        if landing.get("lat") is not None:
            cfg["lat"] = landing["lat"]
        if landing.get("lon") is not None:
            cfg["lon"] = landing["lon"]
    if landing.get("hintLabel"):
        cfg["hintLabel"] = landing["hintLabel"]
    return cfg


def build_seo_landing_js(landings: list[dict]) -> str:
    by_path: dict[str, dict] = {}
    for landing in landings:
        slug = landing["slug"]
        cfg = landing_runtime_config(landing)
        by_path[f"/{slug}"] = cfg
    lines = ["    const SEO_LANDING_BY_PATH = {"]
    for path, cfg in by_path.items():
        lines.append(f'      "{path}": {{')
        for key, value in cfg.items():
            if value is None:
                continue
            if isinstance(value, str):
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'        {key}: "{escaped}",')
            else:
                lines.append(f"        {key}: {value},")
        lines.append("      },")
    lines.append("    };")
    return "\n".join(lines)


def patch_index_seo_block(index_html: str, landings: list[dict]) -> str:
    pattern = re.compile(
        rf"{re.escape(SEO_BLOCK_BEGIN)}.*?{re.escape(SEO_BLOCK_END)}",
        re.DOTALL,
    )
    replacement = f"{SEO_BLOCK_BEGIN}\n{build_seo_landing_js(landings)}\n    {SEO_BLOCK_END}"
    if not pattern.search(index_html):
        raise SystemExit(f"Bloc {SEO_BLOCK_BEGIN} introuvable dans index.html")
    return pattern.sub(replacement, index_html, count=1)


def replace_tag_content(html: str, tag: str, content: str) -> str:
    return re.sub(
        rf"<{tag}[^>]*>.*?</{tag}>",
        f"<{tag}>{content}</{tag}>",
        html,
        count=1,
        flags=re.DOTALL,
    )


def replace_meta_name(html: str, name: str, content: str) -> str:
    pattern = rf'<meta\s+name="{re.escape(name)}"\s+content="[^"]*"\s*/?>'
    replacement = f'<meta name="{name}" content="{content}" />'
    if re.search(pattern, html):
        return re.sub(pattern, replacement, html, count=1)
    return html.replace("</head>", f'  {replacement}\n</head>', 1)


def replace_meta_property(html: str, prop: str, content: str) -> str:
    pattern = rf'<meta\s+property="{re.escape(prop)}"\s+content="[^"]*"\s*/?>'
    replacement = f'<meta property="{prop}" content="{content}" />'
    if re.search(pattern, html):
        return re.sub(pattern, replacement, html, count=1)
    return html.replace("</head>", f'  {replacement}\n</head>', 1)


def replace_canonical(html: str, href: str) -> str:
    pattern = r'<link\s+rel="canonical"\s+href="[^"]*"\s*/?>'
    replacement = f'<link rel="canonical" href="{href}" />'
    if re.search(pattern, html):
        return re.sub(pattern, replacement, html, count=1)
    return html.replace("</head>", f'  {replacement}\n</head>', 1)


def inject_seo_results_heading(html: str, landing: dict) -> str:
    place = landing.get("placeLabel") or "Lieu"
    heading = (
        f'<div class="muted results-summary" style="margin-bottom:10px;">'
        f'<h1 class="results-seo-heading">{place} : parkings publics</h1></div>'
    )
    patterns = [
        '<div class="list" id="results"><div class="muted">Chargement de la base…</div></div>',
        '<div class="list" id="results"><div class="muted">Chargement de la base...</div></div>',
    ]
    for pattern in patterns:
        if pattern in html:
            return html.replace(
                pattern,
                f'<div class="list" id="results">{heading}<div class="muted">Chargement de la base…</div></div>',
                1,
            )
    return html


def demote_welcome_headings_for_seo(html: str) -> str:
    """Un seul H1 par landing SEO : les intros d'accueil passent en <p>."""
    for el_id in ("copy-mac-body", "copy-iphone-body"):
        pattern = rf'<h1([^>]*id="{el_id}"[^>]*)>(.*?)</h1>'
        html = re.sub(pattern, r"<p\1>\2</p>", html, count=1, flags=re.DOTALL)
    return html


def build_landing_html(template: str, landing: dict) -> str:
    slug = landing["slug"]
    canonical = f"{SITE_ORIGIN}/{slug}"
    runtime = landing_runtime_config(landing)
    html = template
    html = replace_tag_content(html, "title", landing["title"])
    html = replace_meta_name(html, "description", landing["description"])
    html = replace_canonical(html, canonical)
    html = replace_meta_property(html, "og:title", landing.get("og_title") or landing["title"])
    html = replace_meta_property(
        html,
        "og:description",
        landing.get("og_description") or landing["description"],
    )
    html = replace_meta_property(html, "og:url", canonical)
    html = inject_seo_results_heading(html, landing)
    html = demote_welcome_headings_for_seo(html)
    inject = (
        f'  <base href="/" />\n'
        f'  <script>window.PARKECO_SEO_LANDING = {json.dumps(runtime, ensure_ascii=False)};</script>\n'
    )
    html = html.replace("<head>", f"<head>\n{inject}", 1)
    return html


def write_sitemap(landings: list[dict]) -> None:
    today = date.today().isoformat()
    static_urls = [
        ("https://parkeco.fr/", "weekly", "1.0"),
        ("https://parkeco.fr/faq.html", "monthly", "0.8"),
    ]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, changefreq, priority in static_urls:
        lines.extend(
            [
                "  <url>",
                f"    <loc>{loc}</loc>",
                f"    <lastmod>{today}</lastmod>",
                f"    <changefreq>{changefreq}</changefreq>",
                f"    <priority>{priority}</priority>",
                "  </url>",
            ]
        )
    for landing in landings:
        loc = f"{SITE_ORIGIN}/{landing['slug']}"
        changefreq = landing.get("changefreq", "weekly")
        priority = str(landing.get("priority", 0.9))
        lines.extend(
            [
                "  <url>",
                f"    <loc>{loc}</loc>",
                f"    <lastmod>{today}</lastmod>",
                f"    <changefreq>{changefreq}</changefreq>",
                f"    <priority>{priority}</priority>",
                "  </url>",
            ]
        )
    lines.append("</urlset>")
    lines.append("")
    SITEMAP_XML.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    landings = load_landings()
    index_html = INDEX_HTML.read_text(encoding="utf-8")
    index_html = patch_index_seo_block(index_html, landings)
    INDEX_HTML.write_text(index_html, encoding="utf-8")

    for landing in landings:
        slug = landing["slug"]
        out_dir = ROOT / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        page_html = build_landing_html(index_html, landing)
        (out_dir / "index.html").write_text(page_html, encoding="utf-8")
        print(f"Écrit : {out_dir / 'index.html'}")

    write_sitemap(landings)
    print(f"Écrit : {SITEMAP_XML}")
    print(f"  - landings SEO : {len(landings)} (dont {len(build_arrondissement_landings())} arrondissements)")


if __name__ == "__main__":
    main()
