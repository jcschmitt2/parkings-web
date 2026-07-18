#!/usr/bin/env python3
"""Génère une page par article d'actualité dans /actu/<slug>/index.html.

Source : donnée/parkeco_actualites.json (un Word par article converti en entrée).
Appelé aussi par fab_seo_pages.py pour inclure les articles dans le sitemap.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chemins_projet import DATA_DIR

ACTUALITES_JSON = DATA_DIR / "parkeco_actualites.json"
INDEX_HTML = ROOT / "index.html"
ACTU_DIR = ROOT / "actu"
SITE_ORIGIN = "https://parkeco.fr"


def article_path_parts(article: dict) -> tuple[str, ...]:
    """Segments de chemin relatif à ROOT (ex. actu/slug ou 14-juillet-...)."""
    custom = (article.get("path") or "").strip().strip("/")
    if custom:
        return tuple(p for p in custom.split("/") if p)
    slug = article.get("slug", "")
    return ("actu", slug) if slug else tuple()


def article_public_href(article: dict) -> str:
    parts = article_path_parts(article)
    if not parts:
        return "/"
    return "/" + "/".join(parts) + "/"


def article_canonical_url(article: dict) -> str:
    parts = article_path_parts(article)
    if not parts:
        return canonical_page_url()
    return canonical_page_url(*parts)


def article_all_path_tuples() -> set[tuple[str, ...]]:
    """Chemins relatifs (segments dossiers) de toutes les pages actualité."""
    out: set[tuple[str, ...]] = set()
    for article in load_actualites().get("articles", []) or []:
        parts = article_path_parts(article)
        if parts:
            out.add(parts)
    return out


def article_root_slugs() -> set[str]:
    """Slugs de dossiers à la racine pour les articles hors /actu/."""
    out: set[str] = set()
    for article in load_actualites().get("articles", []) or []:
        parts = article_path_parts(article)
        if parts and parts[0] != "actu":
            out.add(parts[0])
    return out


def canonical_page_url(*parts: str) -> str:
    path = "/".join(p.strip("/") for p in parts if p and p.strip("/"))
    return f"{SITE_ORIGIN}/" if not path else f"{SITE_ORIGIN}/{path}/"

MONTHS_FR = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
    7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
}

TYPE_META = {
    "news": {"label": "News", "class": "type-news"},
    "guide": {"label": "Guide", "class": "type-guide"},
    "tool": {"label": "Outil", "class": "type-tool"},
}
TYPE_ALIASES = {"alerte": "news", "tarifs": "guide"}

ENCADRE_META = {
    "retenir": {"label": "À retenir", "class": "encadre-retenir"},
    "savoir": {"label": "Bon à savoir", "class": "encadre-savoir"},
    "parker": {"label": "Et pour vous garer ?", "class": "encadre-parker"},
}

ARTICLE_STYLES = """
    * { box-sizing:border-box; }
    html {
      height:auto;
      -webkit-text-size-adjust:100%;
    }
    body {
      margin:0;
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      color:#e7eaff;
      background:linear-gradient(180deg,#0b1020,#0e153a);
      min-height:100dvh;
      overflow-x:hidden;
      overflow-y:auto;
      -webkit-overflow-scrolling:touch;
      padding-bottom:max(18px, env(safe-area-inset-bottom));
    }
    a { color:#7dd3fc; }
    header.site {
      padding:16px 22px;
      border-bottom:1px solid #263069;
      background:rgba(11,16,32,.95);
    }
    .brand {
      display:inline-flex;
      align-items:center;
      gap:8px;
      text-decoration:none;
      color:#e7eaff;
      font-size:1.4rem;
      font-weight:700;
    }
    .brand-eco { color:#7dd3fc; }
    .brand svg { width:30px; height:30px; }
    main.article {
      max-width:720px;
      margin:0 auto;
      padding:28px 20px 60px;
    }
    .article-card {
      background:rgba(14,20,64,.55);
      border:1px solid #2b376f;
      border-radius:16px;
      padding:22px 20px 24px;
      box-shadow:0 10px 30px rgba(0,0,0,.2);
    }
    .article-card.type-news { border-top:3px solid #f59e0b; }
    .article-card.type-guide { border-top:3px solid #22c55e; }
    .article-card.type-tool { border-top:3px solid #7c89e8; }
    .article-meta {
      display:flex;
      flex-wrap:wrap;
      align-items:center;
      gap:8px;
      margin:0 0 12px;
    }
    .article-type {
      display:inline-flex;
      align-items:center;
      padding:3px 10px;
      border-radius:999px;
      font-size:.72rem;
      font-weight:700;
      letter-spacing:.02em;
      text-transform:uppercase;
    }
    .type-news .article-type { background:#451a03; color:#fde68a; border:1px solid #f59e0b; }
    .type-guide .article-type { background:#14532d; color:#bbf7d0; border:1px solid #22c55e; }
    .type-tool .article-type { background:#1e1b4b; color:#c7d2fe; border:1px solid #7c89e8; }
    .article-date { color:#7d8fd6; font-size:.82rem; margin:0; }
    main.article h1 { font-size:1.65rem; line-height:1.25; margin:0 0 16px; color:#fff; }
    .article-chapo {
      font-size:1.02rem;
      line-height:1.5;
      color:#c7d2fe;
      margin:0 0 18px;
      padding:12px 14px;
      background:#0e1440;
      border:1px solid #3d508f;
      border-radius:12px;
    }
    .article-body { font-size:1rem; line-height:1.62; color:#dbe2ff; }
    .article-body p { margin:0 0 14px; }
    .article-body h2 { font-size:1.15rem; margin:22px 0 10px; color:#fff; }
    .article-body ul,
    .article-body ol { padding-left:20px; margin:0 0 14px; }
    .article-body li { margin:0 0 6px; }
    .encadre {
      margin:16px 0;
      padding:12px 14px;
      border-radius:12px;
      border:1px solid #2b376f;
      background:#0e1440;
    }
    .encadre-label {
      display:block;
      font-size:.74rem;
      font-weight:700;
      text-transform:uppercase;
      letter-spacing:.03em;
      margin:0 0 6px;
    }
    .encadre p { margin:0; font-size:.92rem; line-height:1.5; color:#dbe2ff; }
    .encadre-retenir { border-color:#22c55e; background:#0f1f17; }
    .encadre-retenir .encadre-label { color:#86efac; }
    .encadre-savoir { border-color:#3b82f6; background:#0f1530; }
    .encadre-savoir .encadre-label { color:#93c5fd; }
    .encadre-parker { border-color:#7dd3fc; background:#0c1a2e; }
    .encadre-parker .encadre-label { color:#7dd3fc; }
    .article-cta { margin-top:24px; }
    .article-cta--top { margin:0 0 20px; }
    .article-cta-stack {
      display:flex;
      flex-direction:column;
      gap:10px;
      margin:0 0 20px;
    }
    .article-cta-stack .article-cta { margin:0; }
    .article-cta a {
      display:inline-flex;
      align-items:center;
      justify-content:center;
      gap:8px;
      padding:11px 18px;
      border-radius:12px;
      background:#2563eb;
      border:1px solid #60a5fa;
      color:#fff;
      font-weight:600;
      text-decoration:none;
      text-align:center;
    }
    .article-cta-stack a { display:flex; width:100%; box-sizing:border-box; }
    .article-cta a:hover { background:#1d4ed8; }
    .cta-grid {
      display:grid;
      grid-template-columns:1fr 1fr;
      gap:12px;
      margin:0 0 20px;
    }
    @media (max-width:560px){
      .cta-grid { grid-template-columns:1fr; }
    }
    .cta-box {
      display:flex;
      flex-direction:column;
      gap:8px;
      padding:14px 16px;
      border-radius:14px;
      border:1px solid #2b376f;
      background:#0e1440;
      text-decoration:none;
      color:#e7eaff;
    }
    .cta-box:hover { border-color:#3b82f6; background:#122058; }
    .cta-box .cta-title { font-weight:700; font-size:.95rem; color:#fff; }
    .cta-box .cta-desc { font-size:.82rem; line-height:1.4; color:#c7d2fe; }
    .cta-box .cta-action { margin-top:auto; font-size:.82rem; font-weight:700; color:#7dd3fc; }
    .article-related {
      margin-top:28px;
      padding-top:18px;
      border-top:1px solid #263069;
    }
    .article-related h2 {
      font-size:.95rem;
      margin:0 0 10px;
      color:#c7d2fe;
      font-weight:700;
    }
    .article-related ul {
      list-style:none;
      margin:0;
      padding:0;
      display:flex;
      flex-direction:column;
      gap:8px;
    }
    .article-related a {
      display:block;
      padding:10px 12px;
      border-radius:10px;
      border:1px solid #2b376f;
      background:#0e1440;
      text-decoration:none;
      color:#e7eaff;
      font-size:.88rem;
      line-height:1.35;
    }
    .article-related a:hover { background:#1a2253; border-color:#3b82f6; }
    footer.site {
      border-top:1px solid #263069;
      padding:18px 22px;
      color:#7d8fd6;
      font-size:.8rem;
      text-align:center;
    }
    footer.site a { color:#9aa9ff; font-weight:600; text-decoration:none; }
    footer.site a:hover { text-decoration:underline; }
"""

ARTICLE_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-1N384T5FXL"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-1N384T5FXL');
  </script>
  <title>@@TITLE@@</title>
  <meta name="description" content="@@DESCRIPTION@@" />
  <link rel="canonical" href="@@CANONICAL@@" />
  <meta property="og:title" content="@@OG_TITLE@@" />
  <meta property="og:description" content="@@DESCRIPTION@@" />
  <meta property="og:url" content="@@CANONICAL@@" />
  <meta property="og:type" content="article" />
  <meta property="og:locale" content="fr_FR" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <link rel="icon" href="/favicon.ico" sizes="48x48" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <link rel="apple-touch-icon" href="/favicon-96.png" />
  <script type="application/ld+json">@@JSONLD@@</script>
  <style>@@STYLES@@</style>
</head>
<body>
  <header class="site">
    <a class="brand" href="/" aria-label="ParkEco — accueil">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" aria-hidden="true"><defs><linearGradient id="actu-pk" x1="18%" y1="12%" x2="88%" y2="92%"><stop offset="0%" stop-color="#c7d2fe"/><stop offset="55%" stop-color="#a7b4ff"/><stop offset="100%" stop-color="#7c89e8"/></linearGradient></defs><circle cx="16" cy="16" r="13" fill="url(#actu-pk)" stroke="#ffffff" stroke-width="2"/><text x="16" y="21.5" text-anchor="middle" fill="#ffffff" font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif" font-size="15" font-weight="800">P</text></svg>
      <span>Park<span class="brand-eco">Eco</span></span>
    </a>
  </header>
  <main class="article">
    <article class="article-card @@TYPE_CLASS@@">
      <div class="article-meta">
        <span class="article-type">@@TYPE_LABEL@@</span>
        <time class="article-date" datetime="@@DATE_ISO@@">@@DATE_HUMAN@@</time>
      </div>
      <h1>@@TITRE@@</h1>
      @@CHAPO@@
      @@CTA_TOP@@
      <div class="article-body">@@CONTENU@@</div>
      @@ENCADRES@@
      <p class="article-cta"><a href="@@CTA_HREF@@">@@CTA_LABEL@@</a></p>
    </article>
    @@RELATED@@
  </main>
  <footer class="site-footer" aria-label="Pied de page ParkEco">
    <a href="/">Accueil</a> · <a href="/zones-desservies/">Toutes les zones desservies</a> · <a href="/faq.html">FAQ</a> — ParkEco, le parking public le plus proche à Paris.
  </footer>
</body>
</html>
"""


def load_actualites() -> dict:
    if not ACTUALITES_JSON.exists():
        return {"articles": []}
    return json.loads(ACTUALITES_JSON.read_text(encoding="utf-8"))


def valid_articles(data: dict) -> list[dict]:
    articles = data.get("articles", []) or []
    out = [a for a in articles if a.get("slug") and a.get("titre")]
    out.sort(key=lambda a: str(a.get("date", "")), reverse=True)
    return out


def human_date(iso: str) -> str:
    try:
        y, m, d = (int(x) for x in iso.split("-"))
        return f"{d} {MONTHS_FR.get(m, '')} {y}".strip()
    except Exception:
        return iso or ""


def article_type_meta(article: dict) -> dict:
    raw = article.get("type", "guide")
    article_type = TYPE_ALIASES.get(raw, raw)
    return TYPE_META.get(article_type, TYPE_META["guide"])


def build_encadres_html(article: dict) -> str:
    blocks = article.get("encadres") or []
    parts: list[str] = []
    for block in blocks:
        kind = block.get("kind", "savoir")
        meta = ENCADRE_META.get(kind, ENCADRE_META["savoir"])
        text = (block.get("texte") or "").strip()
        if not text:
            continue
        parts.append(
            f'<aside class="encadre {meta["class"]}">'
            f'<span class="encadre-label">{html.escape(meta["label"])}</span>'
            f"<p>{html.escape(text)}</p>"
            f"</aside>"
        )
    return "\n      ".join(parts)


def build_chapo_html(article: dict) -> str:
    resume = (article.get("resume") or "").strip()
    if not resume:
        return ""
    return f'<p class="article-chapo">{html.escape(resume)}</p>'


def build_cta(article: dict) -> tuple[str, str]:
    cta = article.get("cta") or {}
    label = (cta.get("label") or "Trouver un parking proche").strip()
    href = (cta.get("href") or "/").strip()
    if not href.startswith("/"):
        href = "/" + href
    return href, label


def build_cta_top_html(article: dict) -> str:
    """Un CTA haut (cta_haut) ou plusieurs boutons bleus (cta_hauts)."""
    multi = article.get("cta_hauts") or []
    if multi:
        buttons: list[str] = []
        for item in multi:
            label = (item.get("label") or "").strip()
            href = (item.get("href") or "").strip()
            if not label or not href:
                continue
            if not href.startswith("/"):
                href = "/" + href
            buttons.append(
                f'<p class="article-cta article-cta--top">'
                f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>'
                f"</p>"
            )
        if buttons:
            return f'<div class="article-cta-stack">{"".join(buttons)}</div>'

    cta = article.get("cta_haut") or {}
    label = (cta.get("label") or "").strip()
    href = (cta.get("href") or "").strip()
    if not label or not href:
        return ""
    if not href.startswith("/"):
        href = "/" + href
    return (
        f'<p class="article-cta article-cta--top">'
        f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>'
        f"</p>"
    )


def build_jsonld(article: dict, titre: str, description: str, canonical: str) -> str:
    date_pub = (article.get("date") or "").strip()
    date_mod = (article.get("date_modified") or date_pub).strip()
    data = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": titre,
        "description": description,
        "datePublished": date_pub,
        "dateModified": date_mod,
        "inLanguage": "fr-FR",
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": canonical,
        },
        "author": {"@type": "Organization", "name": "ParkEco"},
        "publisher": {
            "@type": "Organization",
            "name": "ParkEco",
            "url": SITE_ORIGIN + "/",
        },
    }
    return json.dumps(data, ensure_ascii=False)


def build_related_html(article: dict, all_articles: list[dict]) -> str:
    slug = article["slug"]
    by_slug = {a["slug"]: a for a in all_articles if a.get("slug")}
    linked_slugs = [s for s in (article.get("articles_lies") or []) if s in by_slug and s != slug]
    if linked_slugs:
        others = [by_slug[s] for s in linked_slugs]
    else:
        article_path = (article.get("path") or "").strip("/").split("/")[0]
        others = []
        for a in all_articles:
            if a.get("slug") == slug:
                continue
            if a.get("liste_accueil") is False:
                continue
            other_path = (a.get("path") or "").strip("/").split("/")[0]
            if article_path and other_path == article_path:
                continue
            others.append(a)
            if len(others) >= 2:
                break
    if not others:
        return ""
    items = []
    for other in others:
        titre = html.escape(other.get("titre", ""))
        href = html.escape(article_public_href(other), quote=True)
        items.append(f'<li><a href="{href}">{titre}</a></li>')
    return (
        '<section class="article-related" aria-label="Autres actualités">'
        "<h2>Autres actualités</h2>"
        f"<ul>{''.join(items)}</ul>"
        "</section>"
    )


def replace_element_inner_by_id(page_html: str, elem_id: str, content: str) -> str:
  pattern = rf'(<[^>]+id="{re.escape(elem_id)}"[^>]*>)(.*?)(</[^>]+>)'
  escaped = html.escape(content)
  return re.sub(pattern, lambda m: f"{m.group(1)}{escaped}{m.group(3)}", page_html, count=1, flags=re.DOTALL)


def reorder_actu_app_header(page_html: str) -> str:
    """H1 avant chapô, comme l'article initial (SEO + lecture)."""
    marker_lead = '<p class="header-intro header-intro--lead" id="copy-lead">'
    marker_body = '<h1 class="header-intro header-intro--body" id="copy-body">'
    i_lead = page_html.find(marker_lead)
    i_body = page_html.find(marker_body)
    if i_lead < 0 or i_body < 0 or i_lead >= i_body:
        return page_html
    end_lead = page_html.find("</p>", i_lead) + 4
    end_body = page_html.find("</h1>", i_body) + 5
    lead_block = page_html[i_lead:end_lead]
    body_block = page_html[i_body:end_body]
    return page_html[:i_lead] + body_block + page_html[end_lead:i_body] + lead_block + page_html[end_body:]


def actu_app_runtime_config(article: dict) -> dict:
    slug = article["slug"]
    titre = article["titre"]
    resume = article.get("resume") or titre
    # Chapo visible = resume ; meta/og peuvent rester plus longs via meta_description
    meta_desc = (article.get("meta_description") or resume).strip()
    return {
        "slug": slug,
        "titre": titre,
        "h1": titre,
        "resume": resume,
        "title": f"{titre} | ParkEco",
        "description": meta_desc,
        "canonical": article_canonical_url(article),
        "og_title": titre,
        "og_description": meta_desc,
    }


def build_actu_tool_seo_html(article: dict) -> str:
    """Bloc HTML statique (H1 déjà dans le header) : paragraphe + liens crawlables."""
    parts: list[str] = []
    extra = (article.get("seo_extra_html") or "").strip()
    if extra:
        parts.append(extra)
    cta = article.get("cta") or {}
    cta_href = (cta.get("href") or "").strip()
    cta_label = (cta.get("label") or "").strip()
    if cta_href and cta_label:
        if not cta_href.startswith("/"):
            cta_href = "/" + cta_href
        parts.append(
            f'<p class="actu-tool-seo-back"><a href="{html.escape(cta_href, quote=True)}">'
            f"{html.escape(cta_label)}</a></p>"
        )
    if not parts:
        return ""
    return (
        '<section class="actu-tool-seo" aria-label="Informations">'
        f'{"".join(parts)}'
        "</section>"
    )


def build_actu_app_html(article: dict, template: str) -> str:
    from construction_base.fab_seo_pages import (
        replace_canonical,
        replace_meta_name,
        replace_meta_property,
        replace_tag_content,
    )

    cfg = actu_app_runtime_config(article)
    page = template
    page = replace_tag_content(page, "title", cfg["title"])
    page = replace_meta_name(page, "description", cfg["description"])
    page = replace_canonical(page, cfg["canonical"])
    page = replace_meta_property(page, "og:title", cfg["og_title"])
    page = replace_meta_property(page, "og:description", cfg["og_description"])
    page = replace_meta_property(page, "og:url", cfg["canonical"])
    page = replace_meta_property(page, "og:type", "article")
    inject = (
        f'  <base href="/" />\n'
        f'  <script>window.PARKECO_ACTU_APP = {json.dumps(cfg, ensure_ascii=False)};</script>\n'
    )
    page = page.replace("<head>", f"<head>\n{inject}", 1)
    page = page.replace("<body>", '<body class="actu-app">', 1)
    page = replace_element_inner_by_id(page, "copy-subtitle", "")
    page = replace_element_inner_by_id(page, "copy-body", cfg["h1"])
    page = replace_element_inner_by_id(page, "copy-lead", cfg["resume"])
    page = replace_element_inner_by_id(page, "copy-trust", "")
    page = reorder_actu_app_header(page)
    seo = build_actu_tool_seo_html(article)
    if seo:
        # Insérer après le header welcome, avant news-panel si possible
        marker = '<section id="news-panel"'
        if marker in page:
            page = page.replace(marker, seo + "\n    " + marker, 1)
        else:
            page = page.replace("</header>", "</header>\n    " + seo, 1)
    return page


def build_article_html(article: dict, all_articles: list[dict]) -> str:
    slug = article["slug"]
    titre = article["titre"]
    resume = article.get("resume") or titre
    meta_desc = (article.get("meta_description") or resume).strip()
    meta_title = (article.get("meta_title") or f"{titre} | ParkEco").strip()
    if not meta_title.endswith("ParkEco"):
        # garder | ParkEco si absent
        if "| ParkEco" not in meta_title:
            meta_title = f"{meta_title} | ParkEco"
    canonical = article_canonical_url(article)
    type_meta = article_type_meta(article)
    contenu = article.get("contenu_html") or f"<p>{html.escape(resume)}</p>"
    cta_href, cta_label = build_cta(article)
    repl = {
        "@@STYLES@@": ARTICLE_STYLES,
        "@@TITLE@@": html.escape(meta_title, quote=True),
        "@@DESCRIPTION@@": html.escape(meta_desc, quote=True),
        "@@CANONICAL@@": canonical,
        "@@OG_TITLE@@": html.escape(titre, quote=True),
        "@@TYPE_CLASS@@": type_meta["class"],
        "@@TYPE_LABEL@@": html.escape(type_meta["label"]),
        "@@DATE_ISO@@": html.escape(article.get("date", ""), quote=True),
        "@@DATE_HUMAN@@": html.escape(human_date(article.get("date", ""))),
        "@@TITRE@@": html.escape(titre),
        "@@CHAPO@@": build_chapo_html(article),
        "@@CTA_TOP@@": build_cta_top_html(article),
        "@@CONTENU@@": contenu,
        "@@ENCADRES@@": build_encadres_html(article),
        "@@CTA_HREF@@": html.escape(cta_href, quote=True),
        "@@CTA_LABEL@@": html.escape(cta_label),
        "@@RELATED@@": build_related_html(article, all_articles),
        "@@JSONLD@@": build_jsonld(article, titre, meta_desc, canonical),
    }
    out = ARTICLE_TEMPLATE
    for token, value in repl.items():
        out = out.replace(token, value)
    return out


def generate_article_pages(index_template: str | None = None) -> list[dict]:
    """Écrit les pages /actu/<slug>/index.html et renvoie les infos sitemap."""
    data = load_actualites()
    articles = valid_articles(data)
    template = index_template if index_template is not None else INDEX_HTML.read_text(encoding="utf-8")
    sitemap_entries: list[dict] = []
    for article in articles:
        slug = article["slug"]
        parts = article_path_parts(article)
        if not parts:
            continue
        out_dir = ROOT.joinpath(*parts)
        out_dir.mkdir(parents=True, exist_ok=True)
        if article.get("layout") == "app":
            page_html = build_actu_app_html(article, template)
        else:
            page_html = build_article_html(article, articles)
        (out_dir / "index.html").write_text(page_html, encoding="utf-8")
        print(f"Écrit : {out_dir / 'index.html'}")
        sitemap_entries.append(
            {
                "loc": article_canonical_url(article).rstrip("/"),
                "changefreq": "monthly",
                "priority": "0.7",
            }
        )
    return sitemap_entries


if __name__ == "__main__":
    entries = generate_article_pages()
    print(f"  - articles d'actualité : {len(entries)}")
