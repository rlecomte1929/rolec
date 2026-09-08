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
#: Stripped before the content root is chosen. `form` is NOT here — see `_is_widget_form`.
_NOISE_TAGS = ("script", "style", "nav", "footer", "aside", "noscript")

#: Below this, a <form>'s text is a widget label rather than a document.
_FORM_CONTENT_CHARS = 200


def _is_widget_form(form) -> bool:
    """True when a <form> is a search box / signup rather than the page itself.

    ASP.NET WebForms wraps the ENTIRE document in one `<form runat="server">`, so decomposing
    every form deletes the whole page. Measured 2026-08-21 on enterprise.gov.ie's employment
    permit fees page: 32,292 chars of HTML containing `€1,000` eight times, parsed down to 308
    characters of cookie banner, because the fee table's parent chain runs
    article > div > div > section > div > FORM.

    That is worse than losing the evidence. 308 clears `fact_evidence.MIN_USABLE_SOURCE_CHARS`
    (200), so the checker reads a cookie notice as a usable source and returns UNVERIFIED
    ("we have the source, the quote is not in it") rather than NO_SOURCE. A correct fee is
    recorded as a disproved claim.

    So the test is what the form CONTAINS, not that it is a form: anything carrying a heading, a
    table, or a document's worth of prose is page content.
    """
    if form.find(["h1", "h2", "h3", "h4", "h5", "h6"]) is not None:
        return False
    if form.find("table") is not None:
        return False
    if len(form.get_text(" ", strip=True)) >= _FORM_CONTENT_CHARS:
        return False
    return True


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
    # Drop only the forms that are widgets; a form wrapping the document is the document.
    for form in soup.find_all("form"):
        if _is_widget_form(form):
            form.decompose()

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
