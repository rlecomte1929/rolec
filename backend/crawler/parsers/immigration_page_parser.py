"""
N1 / AIQ-840 — immigration government-page HTML -> structured plain text.

Distinct from the generic crawler/parsers/html_parser.py: this preserves
document STRUCTURE as lightweight markdown so the N2 chunker keeps headings,
lists and tables intact (they carry the requirement semantics on gov pages):
  - headings  -> '#'/'##'/'###' by level
  - unordered list items -> '- '
  - tables    -> pipe rows ('col1 | col2 | col3')

UTF-8 throughout, so Norwegian (ø, å, æ) and German (ü, ö, ä, ß) survive.

parse(html) -> {'title': str, 'text': str, 'word_count': int}
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_HEADING_TAGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "###", "h5": "###", "h6": "###"}
_NOISE_TAGS = ("script", "style", "nav", "footer", "aside", "form", "noscript")


def _table_to_pipes(table) -> List[str]:
    """Render an HTML <table> as pipe-delimited text rows."""
    rows: List[str] = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c != ""]
        if cells:
            rows.append(" | ".join(cells))
    return rows


def parse(html: str) -> Dict[str, Any]:
    """Parse a government immigration page into structured plain text."""
    if not html or not html.strip():
        return {"title": "", "text": "", "word_count": 0}

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(list(_NOISE_TAGS)):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(" ", strip=True)

    root = soup.find("main") or soup.find("article") or soup.body or soup

    blocks: List[str] = []
    # Walk block-level elements in document order; emit structured markdown.
    for el in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table"]):
        name = el.name
        if name in _HEADING_TAGS:
            text = el.get_text(" ", strip=True)
            if text:
                blocks.append(f"{_HEADING_TAGS[name]} {text}")
        elif name == "li":
            # Skip nav-ish list items with no real text.
            text = el.get_text(" ", strip=True)
            if text:
                blocks.append(f"- {text}")
        elif name == "table":
            rows = _table_to_pipes(el)
            blocks.extend(rows)
        else:  # p
            text = el.get_text(" ", strip=True)
            if text:
                blocks.append(text)

    text = "\n".join(blocks).strip()
    # Fallback: if structure extraction yielded nothing, use flat text.
    if not text:
        text = " ".join((root.get_text(" ", strip=True) or "").split())

    word_count = len(text.split())
    return {"title": title, "text": text, "word_count": word_count}
