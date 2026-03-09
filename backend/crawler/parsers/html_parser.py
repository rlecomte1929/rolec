"""
Parse HTML/JSON into normalized document structure.
Extracts title, main text, headings, links, optional schema.org data.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


@dataclass
class ParsedDocument:
    """Normalized document after parsing."""

    page_title: str
    meta_description: Optional[str] = None
    main_text: str = ""
    headings: List[Dict[str, Any]] = field(default_factory=list)  # [{level, text, id}]
    links: List[Dict[str, str]] = field(default_factory=list)  # [{href, text}]
    structured_data: Optional[Dict[str, Any]] = None  # schema.org etc.
    tables: List[List[List[str]]] = field(default_factory=list)  # [[[cell]]] per table
    language_code: Optional[str] = None
    parse_error: Optional[str] = None


def _extract_schema_ld(soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
    """Extract JSON-LD schema.org data if present."""
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
            if isinstance(data, dict) and data.get("@type"):
                return data
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type"):
                        return item
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def parse_html(html: str, url: str = "") -> ParsedDocument:
    """
    Parse HTML into normalized structure.
    Strips boilerplate, preserves headings and main content.
    """
    if not html or not html.strip():
        return ParsedDocument(page_title="", main_text="", parse_error="Empty content")

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        return ParsedDocument(page_title="", main_text="", parse_error=str(e))

    # Remove noise
    for tag in soup(["script", "style", "nav", "footer", "aside"]):
        tag.decompose()

    page_title = ""
    if soup.title and soup.title.string:
        page_title = soup.title.string.strip()
    meta_desc = None
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if meta and meta.get("content"):
        meta_desc = meta["content"].strip()

    # Main content area
    main = soup.find("main") or soup.find("article") or soup.find("div", class_=lambda c: c and "content" in str(c).lower()) or soup.body
    if not main:
        main = soup

    headings = []
    for h in main.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        level = int(h.name[1])
        text = h.get_text(strip=True)
        hid = h.get("id", "")
        if text:
            headings.append({"level": level, "text": text, "id": hid})

    links = []
    for a in main.find_all("a", href=True):
        href = a.get("href", "")
        if href.startswith("#") or href.startswith("javascript:"):
            continue
        text = a.get_text(strip=True)
        links.append({"href": href, "text": text[:200]})

    tables = []
    for table in main.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)

    main_text = main.get_text(separator=" ", strip=True) if main else ""
    main_text = " ".join(main_text.split())

    structured = _extract_schema_ld(soup)

    return ParsedDocument(
        page_title=page_title,
        meta_description=meta_desc,
        main_text=main_text,
        headings=headings,
        links=links,
        structured_data=structured,
        tables=tables,
    )


def parse_json_api(data: str) -> ParsedDocument:
    """Parse JSON API response into document-like structure."""
    try:
        obj = json.loads(data)
    except json.JSONDecodeError as e:
        return ParsedDocument(page_title="", main_text="", parse_error=str(e))

    title = ""
    if isinstance(obj, dict):
        title = obj.get("title") or obj.get("name") or obj.get("label") or ""
        body = obj.get("description") or obj.get("body") or obj.get("content") or ""
        if not body and isinstance(obj.get("text"), str):
            body = obj["text"]
        main_text = body if isinstance(body, str) else json.dumps(body)
    else:
        main_text = json.dumps(obj)

    return ParsedDocument(
        page_title=str(title)[:500],
        main_text=main_text[:50000],
        structured_data=obj if isinstance(obj, dict) else None,
    )
