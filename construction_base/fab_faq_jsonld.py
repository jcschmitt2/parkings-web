#!/usr/bin/env python3
"""Injecte le balisage JSON-LD FAQPage (Schema.org) dans faq.html depuis parkeco_faq.json."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chemins_projet import DATA_DIR

FAQ_JSON = DATA_DIR / "parkeco_faq.json"
FAQ_HTML = ROOT / "faq.html"
MARKER_START = "<!-- faq-jsonld:start -->"
MARKER_END = "<!-- faq-jsonld:end -->"


def answer_for_schema(text: str) -> str:
    return " ".join(str(text or "").split())


def build_faq_schema(items: list[dict]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": str(item.get("question", "")).strip(),
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": answer_for_schema(item.get("answer", "")),
                },
            }
            for item in items
            if str(item.get("question", "")).strip()
        ],
    }


def render_jsonld_block(schema: dict) -> str:
    payload = json.dumps(schema, ensure_ascii=False, indent=2)
    return (
        f"{MARKER_START}\n"
        f'  <script type="application/ld+json" id="faq-jsonld">\n'
        f"{payload}\n"
        f"  </script>\n"
        f"  {MARKER_END}"
    )


def update_faq_html(html: str, block: str) -> str:
    pattern = re.compile(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    if pattern.search(html):
        return pattern.sub(block, html, count=1)
    insert_at = html.find("</head>")
    if insert_at == -1:
        raise RuntimeError("Balise </head> introuvable dans faq.html")
    return html[:insert_at] + block + "\n" + html[insert_at:]


def main() -> int:
    if not FAQ_JSON.is_file():
        print(f"Fichier introuvable : {FAQ_JSON}", file=sys.stderr)
        return 1
    if not FAQ_HTML.is_file():
        print(f"Fichier introuvable : {FAQ_HTML}", file=sys.stderr)
        return 1

    items = json.loads(FAQ_JSON.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        print("parkeco_faq.json doit être un tableau JSON.", file=sys.stderr)
        return 1

    schema = build_faq_schema(items)
    block = render_jsonld_block(schema)
    html = FAQ_HTML.read_text(encoding="utf-8")
    FAQ_HTML.write_text(update_faq_html(html, block), encoding="utf-8")
    print(f"FAQPage JSON-LD mis à jour ({len(schema['mainEntity'])} questions) → {FAQ_HTML.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
