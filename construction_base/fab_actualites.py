#!/usr/bin/env python3
"""Génère une page par article d'actualité dans /actu/<slug>/index.html.

Source : donnée/parkeco_actualites.json (un Word par article converti en entrée).
Appelé aussi par fab_seo_pages.py pour inclure les articles dans le sitemap.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chemins_projet import DATA_DIR

ACTUALITES_JSON = DATA_DIR / "parkeco_actualites.json"
ACTU_DIR = ROOT / "actu"
SITE_ORIGIN = "https://parkeco.fr"

MONTHS_FR = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
    7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
}

TYPE_META = {
    "news": {"label": "News", "class": "type-news"},
    "guide": {"label": "Guide", "class": "type-guide"},
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
    .article-cta a {
      display:inline-flex;
      align-items:center;
      gap:8px;
      padding:11px 18px;
      border-radius:12px;
      background:#2563eb;
      border:1px solid #60a5fa;
      color:#fff;
      font-weight:600;
      text-decoration:none;
    }
    .article-cta a:hover { background:#1d4ed8; }
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
    footer.site a { color:#9aa9ff; }
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
      <div class="article-body">@@CONTENU@@</div>
      @@ENCADRES@@
      <p class="article-cta"><a href="@@CTA_HREF@@">@@CTA_LABEL@@</a></p>
    </article>
    @@RELATED@@
  </main>
  <footer class="site">
    <a href="/">Accueil</a> · <a href="/faq.html">FAQ</a> — ParkEco, le parking public le plus proche à Paris.
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


def build_related_html(article: dict, all_articles: list[dict]) -> str:
    slug = article["slug"]
    others = [a for a in all_articles if a.get("slug") != slug][:2]
    if not others:
        return ""
    items = []
    for other in others:
        other_slug = other["slug"]
        titre = html.escape(other.get("titre", ""))
        items.append(f'<li><a href="/actu/{html.escape(other_slug)}/">{titre}</a></li>')
    return (
        '<section class="article-related" aria-label="Autres actualités">'
        "<h2>Autres actualités</h2>"
        f"<ul>{''.join(items)}</ul>"
        "</section>"
    )


def build_article_html(article: dict, all_articles: list[dict]) -> str:
    slug = article["slug"]
    titre = article["titre"]
    resume = article.get("resume") or titre
    canonical = f"{SITE_ORIGIN}/actu/{slug}"
    title_tag = f"{titre} | ParkEco"
    type_meta = article_type_meta(article)
    contenu = article.get("contenu_html") or f"<p>{html.escape(resume)}</p>"
    cta_href, cta_label = build_cta(article)
    repl = {
        "@@STYLES@@": ARTICLE_STYLES,
        "@@TITLE@@": html.escape(title_tag, quote=True),
        "@@DESCRIPTION@@": html.escape(resume, quote=True),
        "@@CANONICAL@@": canonical,
        "@@OG_TITLE@@": html.escape(titre, quote=True),
        "@@TYPE_CLASS@@": type_meta["class"],
        "@@TYPE_LABEL@@": html.escape(type_meta["label"]),
        "@@DATE_ISO@@": html.escape(article.get("date", ""), quote=True),
        "@@DATE_HUMAN@@": html.escape(human_date(article.get("date", ""))),
        "@@TITRE@@": html.escape(titre),
        "@@CHAPO@@": build_chapo_html(article),
        "@@CONTENU@@": contenu,
        "@@ENCADRES@@": build_encadres_html(article),
        "@@CTA_HREF@@": html.escape(cta_href, quote=True),
        "@@CTA_LABEL@@": html.escape(cta_label),
        "@@RELATED@@": build_related_html(article, all_articles),
    }
    out = ARTICLE_TEMPLATE
    for token, value in repl.items():
        out = out.replace(token, value)
    return out


def generate_article_pages() -> list[dict]:
    """Écrit les pages /actu/<slug>/index.html et renvoie les infos sitemap."""
    data = load_actualites()
    articles = valid_articles(data)
    sitemap_entries: list[dict] = []
    for article in articles:
        slug = article["slug"]
        out_dir = ACTU_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(
            build_article_html(article, articles),
            encoding="utf-8",
        )
        print(f"Écrit : {out_dir / 'index.html'}")
        sitemap_entries.append(
            {
                "loc": f"{SITE_ORIGIN}/actu/{slug}",
                "changefreq": "monthly",
                "priority": "0.7",
            }
        )
    return sitemap_entries


if __name__ == "__main__":
    entries = generate_article_pages()
    print(f"  - articles d'actualité : {len(entries)}")
