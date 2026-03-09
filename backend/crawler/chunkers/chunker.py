"""
Chunk document into extraction-friendly units.
Preserves heading hierarchy and semantic coherence.
"""
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..parsers.html_parser import ParsedDocument

log = logging.getLogger(__name__)

MIN_CHUNK_CHARS = 80
MAX_CHUNK_CHARS = 3000
TARGET_CHUNK_CHARS = 1500


@dataclass
class Chunk:
    """Single chunk for extraction."""

    chunk_index: int
    heading_path: str
    chunk_text: str
    chunk_hash: str
    source_url: str = ""
    page_title: str = ""
    country_code: str = ""
    city_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def chunk_document(
    doc: ParsedDocument,
    source_url: str = "",
    page_title: str = "",
    country_code: str = "",
    city_name: str = "",
) -> List[Chunk]:
    """
    Split document into chunks by heading hierarchy.
    Each chunk carries heading path for context.
    """
    chunks: List[Chunk] = []
    text = doc.main_text
    if not text or len(text.strip()) < MIN_CHUNK_CHARS:
        if text.strip():
            h = _compute_hash(text.strip())
            chunks.append(
                Chunk(
                    chunk_index=0,
                    heading_path="",
                    chunk_text=text.strip(),
                    chunk_hash=h,
                    source_url=source_url,
                    page_title=page_title,
                    country_code=country_code,
                    city_name=city_name,
                )
            )
        return chunks

    headings = doc.headings or []
    heading_path = ""
    if headings:
        heading_path = " > ".join(h.get("text", "") for h in headings[:5])

    return _split_by_size(
        text,
        source_url,
        page_title,
        country_code,
        city_name,
        default_heading_path=heading_path,
    )


def _split_by_size(
    text: str,
    source_url: str,
    page_title: str,
    country_code: str,
    city_name: str,
    default_heading_path: str = "",
) -> List[Chunk]:
    """Split text by size with semantic breaks where possible."""
    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = min(start + TARGET_CHUNK_CHARS, len(text))
        if end < len(text):
            # Try to break at sentence
            for sep in [". ", "\n\n", "\n", " "]:
                pos = text.rfind(sep, start, end)
                if pos > start + MIN_CHUNK_CHARS:
                    end = pos + len(sep)
                    break
        segment = text[start:end].strip()
        if segment:
            h = _compute_hash(segment)
            chunks.append(
                Chunk(
                    chunk_index=idx,
                    heading_path=default_heading_path if idx == 0 else "",
                    chunk_text=segment,
                    chunk_hash=h,
                    source_url=source_url,
                    page_title=page_title,
                    country_code=country_code,
                    city_name=city_name,
                )
            )
            idx += 1
        start = end
    return chunks
