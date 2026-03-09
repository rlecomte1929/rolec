"""
Rule-based resource extraction from chunks.
Produces StagedResourceCandidate records.
"""
import logging
from typing import List, Optional

from ..chunkers.chunker import Chunk
from ..config.models import CONTENT_DOMAIN_TO_CATEGORY, CrawlSource
from .models import StagedResourceCandidate

log = logging.getLogger(__name__)

# Minimum lengths for validation
MIN_TITLE_LEN = 3
MIN_BODY_LEN_FOR_GUIDE = 50
MIN_CONFIDENCE = 0.3


def extract_resource_candidates(
    chunks: List[Chunk],
    source: CrawlSource,
    source_url: str,
    page_title: str,
) -> List[StagedResourceCandidate]:
    """
    Extract resource candidates from chunks using rule-based heuristics.
    """
    candidates: List[StagedResourceCandidate] = []
    category_key = CONTENT_DOMAIN_TO_CATEGORY.get(source.content_domain, "admin_essentials")

    for chunk in chunks:
        text = chunk.chunk_text.strip()
        if len(text) < MIN_BODY_LEN_FOR_GUIDE:
            continue

        title = _infer_title(chunk, page_title)
        if len(title) < MIN_TITLE_LEN:
            title = page_title or chunk.heading_path or source.source_name

        summary = _truncate(text, 300)
        confidence = _compute_confidence(chunk, source, title, text)

        if confidence < MIN_CONFIDENCE:
            continue

        provenance = {
            "source_url": source_url,
            "document_chunk_index": chunk.chunk_index,
            "heading_path": chunk.heading_path,
            "extracted_snippet": text[:500],
            "chunk_hash": chunk.chunk_hash,
        }

        candidates.append(
            StagedResourceCandidate(
                country_code=source.country_code,
                country_name=source.country_name,
                city_name=source.city_name,
                title=title,
                category_key=category_key,
                resource_type="guide",
                audience_type="all",
                summary=summary,
                body=text,
                content_json={"sections": [{"heading": chunk.heading_path or "Content", "text": text}]},
                tags=[],
                source_url=source_url,
                source_name=source.source_name,
                trust_tier=source.trust_tier,
                confidence_score=confidence,
                extraction_method="rule_based",
                provenance=provenance,
            )
        )

    return candidates


def _infer_title(chunk: Chunk, page_title: str) -> str:
    if chunk.heading_path:
        parts = chunk.heading_path.split(" > ")
        return parts[-1].strip() if parts else page_title
    first_line = chunk.chunk_text.split("\n")[0].strip()
    if len(first_line) <= 120 and len(first_line) >= MIN_TITLE_LEN:
        return first_line
    return page_title or ""


def _truncate(s: str, max_len: int) -> str:
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3].rsplit(" ", 1)[0] + "..."


def _compute_confidence(chunk: Chunk, source: CrawlSource, title: str, text: str) -> float:
    """Heuristic confidence based on signal strength."""
    score = 0.5
    if source.trust_tier == "T0":
        score += 0.2
    elif source.trust_tier == "T1":
        score += 0.1
    if len(text) >= 200:
        score += 0.15
    if chunk.heading_path:
        score += 0.1
    if len(title) >= 10:
        score += 0.05
    return min(1.0, score)
