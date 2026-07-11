#!/usr/bin/env python3
"""Génère les pages SEO /parking-proche-* et met à jour sitemap.xml + index.html."""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chemins_projet import DATA_DIR
from construction_base.fab_actualites import generate_article_pages, load_actualites

LANDINGS_JSON = DATA_DIR / "parkeco_seo_landings.json"
ACCORDIONS_JSON = DATA_DIR / "parkeco_seo_accordions.json"
SEO_KNOW_MORE_MARKER = "<!-- SEO_KNOW_MORE -->"
ZONES_HUB_SLUG = "zones-desservies"
SITE_FOOTER_HTML = (
    '<footer class="site-footer" aria-label="Pied de page ParkEco">\n'
    '    <p><a href="/zones-desservies/">Toutes les zones desservies</a>'
    ' · <a href="/faq.html">FAQ</a> · <a href="/">Accueil</a></p>\n'
    "  </footer>"
)
INDEX_HTML = ROOT / "index.html"
SITEMAP_XML = ROOT / "sitemap.xml"
SITE_ORIGIN = "https://parkeco.fr"
SEO_BLOCK_BEGIN = "// SEO_LANDINGS:BEGIN"
SEO_BLOCK_END = "// SEO_LANDINGS:END"


def canonical_page_url(*parts: str) -> str:
    """URL canonique avec slash final (pages dossier, pas fichiers .html)."""
    path = "/".join(p.strip("/") for p in parts if p and p.strip("/"))
    return f"{SITE_ORIGIN}/" if not path else f"{SITE_ORIGIN}/{path}/"


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


def load_accordions() -> dict[str, dict]:
    if not ACCORDIONS_JSON.is_file():
        return {}
    data = json.loads(ACCORDIONS_JSON.read_text(encoding="utf-8"))
    return data.get("accordions", {})


def build_seo_accordion_html(slug: str, accordions: dict[str, dict]) -> str:
    accordion = accordions.get(slug)
    if not accordion:
        return ""
    title = html.escape(accordion.get("title", ""))
    intro = html.escape(accordion.get("intro", ""))
    faq_parts: list[str] = []
    for item in accordion.get("faqs", []):
        question = html.escape(item.get("question", ""))
        answer = html.escape(item.get("answer", ""))
        if not question or not answer:
            continue
        faq_parts.append(
            f'<div class="seo-know-more-faq">'
            f"<h3>{question}</h3>"
            f"<p>{answer}</p>"
            f"</div>"
        )
    faq_html = "\n    ".join(faq_parts)
    return (
        f'<details class="seo-know-more">\n'
        f'  <summary class="seo-know-more-summary">{title}</summary>\n'
        f'  <div class="seo-know-more-body">\n'
        f"    <p>{intro}</p>\n"
        f"    {faq_html}\n"
        f"  </div>\n"
        f"</details>"
    )


def landing_link_label(landing: dict) -> str:
    label = landing.get("placeLabel") or landing.get("slug", "")
    if landing.get("mode") == "arrondissement":
        return f"Parking public {label}"
    return f"Parking proche {label}"


def build_zones_hub_link_items(landings: list[dict]) -> tuple[list[str], list[str]]:
    places: list[tuple[str, str]] = []
    arrondissements: list[tuple[str, str]] = []
    for landing in landings:
        slug = landing["slug"]
        href = f"/{slug}/"
        text = html.escape(landing_link_label(landing))
        item = f'        <li><a href="{href}">{text}</a></li>'
        if landing.get("mode") == "arrondissement":
            arrondissements.append((landing.get("postcode", ""), item))
        else:
            places.append((landing.get("placeLabel", slug), item))
    places.sort(key=lambda x: x[0].lower())
    arrondissements.sort(key=lambda x: x[0])
    return [item for _, item in places], [item for _, item in arrondissements]


def build_zones_hub_html(landings: list[dict]) -> str:
    canonical = canonical_page_url(ZONES_HUB_SLUG)
    place_items, arr_items = build_zones_hub_link_items(landings)
    places_ul = "\n".join(place_items)
    arr_ul = "\n".join(arr_items)
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <title>Toutes les zones desservies — Parkings publics à Paris | ParkEco</title>
  <meta name="description" content="Accès direct à toutes les pages ParkEco par lieu et arrondissement : parkings publics à Paris, carte interactive et tarifs." />
  <link rel="canonical" href="{canonical}" />
  <meta property="og:title" content="Toutes les zones desservies | ParkEco" />
  <meta property="og:description" content="Liste des pages ParkEco par lieu et arrondissement à Paris." />
  <meta property="og:url" content="{canonical}" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="icon" href="/favicon.ico" sizes="48x48" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <style>
    :root {{ --bg:#0b1020; --card:#121733; --text:#e7eaff; --accent:#7dd3fc; }}
    * {{ box-sizing:border-box; }}
    html, body {{
      margin:0;
      min-height:100dvh;
      font-family:system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      color:var(--text);
      background:linear-gradient(180deg,#0b1020,#0e153a);
    }}
    a {{ color:var(--accent); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .hub-header {{
      padding:18px max(18px, env(safe-area-inset-right)) 14px max(18px, env(safe-area-inset-left));
      padding-top:max(18px, env(safe-area-inset-top));
      border-bottom:1px solid #263069;
      background:rgba(11,16,32,.95);
    }}
    .hub-top {{
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      margin-bottom:14px;
    }}
    .hub-back {{
      display:inline-flex;
      align-items:center;
      gap:6px;
      padding:8px 12px;
      min-height:44px;
      box-sizing:border-box;
      border-radius:999px;
      border:1px solid #2b376f;
      background:#0e1440;
      color:#9aa9ff;
      font-size:.84rem;
      font-weight:600;
      text-decoration:none;
      touch-action:manipulation;
      -webkit-tap-highlight-color:rgba(125,211,252,.25);
    }}
    .hub-back:hover {{ color:#fff; text-decoration:none; border-color:#5b72c9; }}
    .hub-brand {{ font-size:1.35rem; font-weight:700; color:#fff; }}
    .brand-eco {{ color:#c7d2fe; }}
    .hub-main {{
      max-width:760px;
      margin:0 auto;
      padding:20px max(16px, env(safe-area-inset-right)) 32px max(16px, env(safe-area-inset-left));
    }}
    .hub-panel {{
      background:var(--card);
      border:1px solid #263069;
      border-radius:16px;
      padding:20px 18px 16px;
      box-shadow:0 10px 30px rgba(0,0,0,.25);
    }}
    .hub-title {{
      margin:0 0 10px;
      font-size:1.25rem;
      font-weight:700;
      color:#fff;
      line-height:1.35;
    }}
    .hub-intro {{
      margin:0 0 20px;
      color:#9aa9ff;
      font-size:.92rem;
      line-height:1.5;
    }}
    .hub-section {{ margin-bottom:22px; }}
    .hub-section:last-child {{ margin-bottom:0; }}
    .hub-section h2 {{
      margin:0 0 10px;
      font-size:1rem;
      font-weight:700;
      color:#c7d2fe;
    }}
    .hub-links {{
      margin:0;
      padding:0;
      list-style:none;
      display:flex;
      flex-direction:column;
      gap:6px;
    }}
    .hub-links a {{
      display:block;
      padding:12px 14px;
      min-height:48px;
      box-sizing:border-box;
      line-height:1.35;
      border-radius:8px;
      border:1px solid #2b376f;
      background:#0f1530;
      color:#e7eaff;
      font-size:.9rem;
      touch-action:manipulation;
      -webkit-tap-highlight-color:rgba(125,211,252,.25);
    }}
    .hub-links a:hover {{
      border-color:#5b72c9;
      background:#111845;
      text-decoration:none;
    }}
    .site-footer {{
      border-top:1px solid #263069;
      padding:4px 12px;
      padding-bottom:max(4px, env(safe-area-inset-bottom));
      text-align:center;
      font-size:.7rem;
      line-height:1.25;
      color:#7d8fd6;
      background:rgba(11,16,32,.95);
    }}
    .site-footer p {{ margin:0; }}
    .site-footer a {{
      color:#9aa9ff;
      font-weight:600;
      text-decoration:none;
      touch-action:manipulation;
    }}
    .site-footer a:hover {{ text-decoration:underline; }}
  </style>
</head>
<body>
  <header class="hub-header">
    <div class="hub-top">
      <a class="hub-back" href="/">← Accueil ParkEco</a>
      <div class="hub-brand">Park<span class="brand-eco">Eco</span></div>
    </div>
  </header>
  <main class="hub-main">
    <article class="hub-panel">
      <h1 class="hub-title">Toutes les zones desservies</h1>
      <p class="hub-intro">Accès direct aux pages ParkEco par lieu et arrondissement : parkings publics à Paris, carte interactive, distances et tarifs.</p>
      <section class="hub-section" aria-labelledby="hub-places-title">
        <h2 id="hub-places-title">Lieux et monuments</h2>
        <ul class="hub-links">
{places_ul}
        </ul>
      </section>
      <section class="hub-section" aria-labelledby="hub-arr-title">
        <h2 id="hub-arr-title">Arrondissements de Paris</h2>
        <ul class="hub-links">
{arr_ul}
        </ul>
      </section>
    </article>
  </main>
  {SITE_FOOTER_HTML}
</body>
</html>
"""


def write_zones_hub_page(landings: list[dict]) -> Path:
    out_dir = ROOT / ZONES_HUB_SLUG
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "index.html"
    out_path.write_text(build_zones_hub_html(landings), encoding="utf-8")
    return out_path


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
        "canonical": canonical_page_url(slug),
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


def build_seo_accordions_js(accordions: dict[str, dict]) -> str:
    return f"    const SEO_ACCORDIONS_BY_SLUG = {json.dumps(accordions, ensure_ascii=False)};"


def patch_index_seo_block(index_html: str, landings: list[dict], accordions: dict[str, dict]) -> str:
    pattern = re.compile(
        rf"{re.escape(SEO_BLOCK_BEGIN)}.*?{re.escape(SEO_BLOCK_END)}",
        re.DOTALL,
    )
    replacement = (
        f"{SEO_BLOCK_BEGIN}\n"
        f"{build_seo_landing_js(landings)}\n"
        f"{build_seo_accordions_js(accordions)}\n"
        f"    {SEO_BLOCK_END}"
    )
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
    pattern = r'<h1([^>]*id="copy-body"[^>]*)>(.*?)</h1>'
    return re.sub(pattern, r"<p\1>\2</p>", html, count=1, flags=re.DOTALL)


def build_landing_html(template: str, landing: dict, accordions: dict[str, dict]) -> str:
    slug = landing["slug"]
    canonical = canonical_page_url(slug)
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
    if SEO_KNOW_MORE_MARKER in html:
        accordion_html = build_seo_accordion_html(slug, accordions)
        html = html.replace(SEO_KNOW_MORE_MARKER, accordion_html, 1)
    inject = (
        f'  <base href="/" />\n'
        f'  <script>window.PARKECO_SEO_LANDING = {json.dumps(runtime, ensure_ascii=False)};</script>\n'
    )
    html = html.replace("<head>", f"<head>\n{inject}", 1)
    return html


CANONICAL_RE = re.compile(r'<link\s+rel="canonical"\s+href="([^"]+)"\s*/?>', re.I)
EXCLUDE_PARTS = frozenset({
    "sauvegarde locale",
    "appli",
    "construction_base",
    "autre_programme_de_construction",
    "donnée de travail",
    ".dev-iphone-certs",
    ".git",
    "node_modules",
})
ROOT_HTML_PAGES = frozenset({"index.html", "faq.html"})


def extract_canonical(html: str) -> str | None:
    match = CANONICAL_RE.search(html)
    return match.group(1).strip() if match else None


def path_to_public_url(rel_path: Path) -> str | None:
    parts = rel_path.parts
    if len(parts) == 1 and rel_path.name == "index.html":
        return f"{SITE_ORIGIN}/"
    if len(parts) == 1 and rel_path.name == "faq.html":
        return f"{SITE_ORIGIN}/faq.html"
    if len(parts) == 2 and rel_path.name == "index.html":
        if parts[0] == ZONES_HUB_SLUG:
            return f"{SITE_ORIGIN}/{ZONES_HUB_SLUG}/"
        return f"{SITE_ORIGIN}/{parts[0]}"
    if len(parts) == 3 and parts[0] == "actu" and rel_path.name == "index.html":
        return f"{SITE_ORIGIN}/actu/{parts[1]}"
    return None


def normalize_sitemap_url(url: str) -> str:
    """Force un slash final pour les URLs de page (sauf home et fichiers .ext)."""
    if not url.startswith(SITE_ORIGIN):
        return url
    if url == f"{SITE_ORIGIN}/":
        return url
    path = url[len(SITE_ORIGIN):]
    if not path:
        return f"{SITE_ORIGIN}/"
    if path.endswith("/"):
        return url
    tail = path.rsplit("/", 1)[-1]
    if "." in tail:
        return url
    return f"{url}/"


def discover_public_html_files() -> list[Path]:
    pages: list[Path] = []
    for path in sorted(ROOT.rglob("*.html")):
        if any(part in EXCLUDE_PARTS for part in path.parts):
            continue
        rel = path.relative_to(ROOT)
        if len(rel.parts) == 1:
            if rel.name in ROOT_HTML_PAGES:
                pages.append(rel)
            continue
        if len(rel.parts) == 2 and rel.name == "index.html" and rel.parts[0].startswith("parking-proche-"):
            pages.append(rel)
            continue
        if len(rel.parts) == 2 and rel.name == "index.html" and rel.parts[0] == ZONES_HUB_SLUG:
            pages.append(rel)
            continue
        if len(rel.parts) == 3 and rel.parts[0] == "actu" and rel.name == "index.html":
            pages.append(rel)
    return pages


def sitemap_meta_for_url(url: str) -> tuple[str, str]:
    if url == f"{SITE_ORIGIN}/":
        return "weekly", "1.0"
    if url.endswith("/faq.html"):
        return "monthly", "0.8"
    if f"/{ZONES_HUB_SLUG}/" in url:
        return "monthly", "0.8"
    if "/actu/" in url:
        return "monthly", "0.7"
    if "/parking-proche-paris-" in url:
        return "weekly", "0.85"
    if "/parking-proche-" in url:
        return "weekly", "0.9"
    return "monthly", "0.5"


def lastmod_for_page(rel_path: Path, article_dates: dict[str, str]) -> str:
    if len(rel_path.parts) == 3 and rel_path.parts[0] == "actu":
        slug = rel_path.parts[1]
        if slug in article_dates:
            return article_dates[slug]
    return date.fromtimestamp((ROOT / rel_path).stat().st_mtime).isoformat()


def build_sitemap_entries(article_dates: dict[str, str] | None = None) -> list[dict]:
    article_dates = article_dates or {}
    seen: set[str] = set()
    entries: list[dict] = []
    for rel in discover_public_html_files():
        html = (ROOT / rel).read_text(encoding="utf-8")
        url = extract_canonical(html) or path_to_public_url(rel)
        if url:
            url = normalize_sitemap_url(url)
        if not url or not url.startswith(SITE_ORIGIN):
            print(f"  ⚠ ignoré (URL invalide) : {rel}")
            continue
        if url in seen:
            print(f"  ⚠ doublon ignoré : {url} ({rel})")
            continue
        seen.add(url)
        changefreq, priority = sitemap_meta_for_url(url)
        entries.append(
            {
                "loc": url,
                "lastmod": lastmod_for_page(rel, article_dates),
                "changefreq": changefreq,
                "priority": priority,
            }
        )
    entries.sort(key=lambda e: (-float(e["priority"]), e["loc"]))
    return entries


def verify_sitemap_coverage(entries: list[dict]) -> None:
    sitemap_urls = {e["loc"] for e in entries}
    expected: list[str] = []
    missing: list[str] = []
    for rel in discover_public_html_files():
        html = (ROOT / rel).read_text(encoding="utf-8")
        url = extract_canonical(html) or path_to_public_url(rel)
        if url:
            url = normalize_sitemap_url(url)
        if url:
            expected.append(url)
            if url not in sitemap_urls:
                missing.append(f"{url} ({rel})")
    extra = sorted(sitemap_urls - set(expected))
    if missing:
        print("  ⚠ URLs manquantes dans le sitemap :")
        for item in missing:
            print(f"    - {item}")
    if extra:
        print("  ⚠ URLs en trop dans le sitemap :")
        for url in extra:
            print(f"    - {url}")
    if not missing and not extra:
        print(f"  ✓ couverture complète : {len(sitemap_urls)} URLs publiques")


def write_sitemap(entries: list[dict]) -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for entry in entries:
        lines.extend(
            [
                "  <url>",
                f"    <loc>{entry['loc']}</loc>",
                f"    <lastmod>{entry['lastmod']}</lastmod>",
                f"    <changefreq>{entry['changefreq']}</changefreq>",
                f"    <priority>{entry['priority']}</priority>",
                "  </url>",
            ]
        )
    lines.append("</urlset>")
    lines.append("")
    SITEMAP_XML.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    landings = load_landings()
    accordions = load_accordions()
    index_html = INDEX_HTML.read_text(encoding="utf-8")
    index_html = patch_index_seo_block(index_html, landings, accordions)
    INDEX_HTML.write_text(index_html, encoding="utf-8")

    for landing in landings:
        slug = landing["slug"]
        out_dir = ROOT / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        page_html = build_landing_html(index_html, landing, accordions)
        (out_dir / "index.html").write_text(page_html, encoding="utf-8")
        print(f"Écrit : {out_dir / 'index.html'}")

    hub_path = write_zones_hub_page(landings)
    print(f"Écrit : {hub_path}")

    article_entries = generate_article_pages(index_html)
    article_dates = {
        a["slug"]: a["date"]
        for a in load_actualites().get("articles", [])
        if a.get("slug") and a.get("date")
    }

    sitemap_entries = build_sitemap_entries(article_dates)
    write_sitemap(sitemap_entries)
    print(f"Écrit : {SITEMAP_XML}")
    print(f"  - landings SEO : {len(landings)} (dont {len(build_arrondissement_landings())} arrondissements)")
    print(f"  - articles d'actualité : {len(article_entries)}")
    print(f"  - URLs dans le sitemap : {len(sitemap_entries)}")
    verify_sitemap_coverage(sitemap_entries)


if __name__ == "__main__":
    main()
