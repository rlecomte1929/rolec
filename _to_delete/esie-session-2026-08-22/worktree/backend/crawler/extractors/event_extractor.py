"""
Rule-based and schema.org event extraction.
Produces StagedEventCandidate records.
"""
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..chunkers.chunker import Chunk
from ..parsers.html_parser import ParsedDocument
from ..config.models import CrawlSource
from .models import StagedEventCandidate

log = logging.getLogger(__name__)

EVENT_TYPE_KEYWORDS = {
    "cinema": ["film", "movie", "cinema", "screening"],
    "concert": ["concert", "live", "music", "performance"],
    "festival": ["festival", "celebration"],
    "museum": ["museum", "exhibition", "exhibit"],
    "theater": ["theater", "theatre", "play", "drama"],
    "family_activity": ["family", "kids", "children", "family-friendly"],
    "community_event": ["event", "meetup", "community", "workshop"],
}
DEFAULT_EVENT_TYPE = "community_event"


def extract_event_candidates(
    chunks: List[Chunk],
    doc: ParsedDocument,
    source: CrawlSource,
    source_url: str,
    page_title: str,
) -> List[StagedEventCandidate]:
    """
    Extract event candidates from chunks and structured data.
    """
    candidates: List[StagedEventCandidate] = []

    if doc.structured_data:
        for evt in _parse_schema_events(doc.structured_data, source, source_url):
            if evt:
                candidates.append(evt)

    for chunk in chunks:
        evts = _extract_from_text(chunk, source, source_url, page_title)
        candidates.extend(evts)

    return candidates


def _parse_schema_events(data: Dict[str, Any], source: CrawlSource, source_url: str) -> List[Optional[StagedEventCandidate]]:
    """Parse schema.org Event or ItemList of events."""
    out: List[Optional[StagedEventCandidate]] = []
    if data.get("@type") == "Event":
        c = _schema_event_to_candidate(data, source, source_url)
        if c:
            out.append(c)
    elif data.get("@type") == "ItemList" and "itemListElement" in data:
        for item in data["itemListElement"] or []:
            if isinstance(item, dict) and item.get("@type") == "Event":
                c = _schema_event_to_candidate(item, source, source_url)
                if c:
                    out.append(c)
    return out


def _schema_event_to_candidate(evt: Dict[str, Any], source: CrawlSource, source_url: str) -> Optional[StagedEventCandidate]:
    name = evt.get("name") or evt.get("title", "")
    if not name or len(name) < 3:
        return None

    start = evt.get("startDate")
    end = evt.get("endDate")
    loc = evt.get("location") or {}
    if isinstance(loc, dict):
        venue = loc.get("name", "")
        address = loc.get("address")
        if isinstance(address, dict):
            address = address.get("streetAddress") or address.get("name", "")
    else:
        venue = str(loc) if loc else ""
        address = None

    desc = evt.get("description", "")
    if isinstance(desc, list):
        desc = desc[0] if desc else ""

    event_type = _infer_event_type(name, desc)
    is_free = _infer_free(evt)

    provenance = {
        "source_url": source_url,
        "extraction_method": "schema_parser",
        "schema_type": evt.get("@type"),
    }

    return StagedEventCandidate(
        country_code=source.country_code,
        country_name=source.country_name,
        city_name=source.city_name or "",
        title=name,
        event_type=event_type,
        description=desc or None,
        venue_name=venue or None,
        address=address,
        start_datetime=start,
        end_datetime=end,
        is_free=is_free,
        source_url=source_url,
        source_name=source.source_name,
        trust_tier=source.trust_tier,
        confidence_score=0.85,
        extraction_method="schema_parser",
        provenance=provenance,
    )


def _extract_from_text(
    chunk: Chunk,
    source: CrawlSource,
    source_url: str,
    page_title: str,
) -> List[StagedEventCandidate]:
    """Heuristic extraction from plain text (limited)."""
    candidates = []
    text = chunk.chunk_text
    if len(text) < 100:
        return candidates

    event_type = _infer_event_type(text, "")
    title = chunk.heading_path.split(" > ")[-1] if chunk.heading_path else page_title
    if not title or len(title) < 5:
        return candidates

    provenance = {
        "source_url": source_url,
        "chunk_index": chunk.chunk_index,
        "heading_path": chunk.heading_path,
        "extraction_method": "rule_based",
    }

    candidates.append(
        StagedEventCandidate(
            country_code=source.country_code,
            country_name=source.country_name,
            city_name=source.city_name or "",
            title=title,
            event_type=event_type,
            description=_truncate(text, 500),
            source_url=source_url,
            source_name=source.source_name,
            trust_tier=source.trust_tier,
            confidence_score=0.5,
            extraction_method="rule_based",
            provenance=provenance,
        )
    )
    return candidates


def _infer_event_type(title: str, description: str) -> str:
    combined = (title + " " + description).lower()
    for etype, keywords in EVENT_TYPE_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return etype
    return DEFAULT_EVENT_TYPE


def _infer_free(evt: Dict[str, Any]) -> bool:
    offer = evt.get("offers") or {}
    if isinstance(offer, list):
        offer = offer[0] if offer else {}
    price = offer.get("price", offer.get("lowPrice", ""))
    if price == "0" or price == 0:
        return True
    return "free" in str(offer.get("name", "")).lower()


def _truncate(s: str, max_len: int) -> str:
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3].rsplit(" ", 1)[0] + "..."
