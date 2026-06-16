"""
LLM-backed resource extraction fallback (CRAWL-01 / AIQ-1094).

The rule-based extractor (`resource_extractor.extract_resource_candidates`)
silently drops pages with ambiguous structure — no heading path, dense prose,
non-standard layouts — which are often the most valuable sources (local gov
portals, expat community sites). This LLM fallback is meant to run only when the
rule-based confidence is below threshold or yields nothing (wiring is CRAWL-02).

It returns the SAME `StagedResourceCandidate` dataclass as the rule-based path so
the staging writer, dedup, and admin review UI need zero changes — only
`extraction_method` differs ('llm_structured_extraction' vs 'rule_based').

GDPR (CLAUDE.md data-minimisation, Art. 28/44): every piece of page text is run
through `mask_pii()` before it is placed in the LLM prompt. No raw page text
reaches the provider.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, List

from backend.app.services import llm_client
from backend.app.services.pii_masker import mask_pii

from ..chunkers.chunker import Chunk
from ..config.models import CONTENT_DOMAIN_TO_CATEGORY, CrawlSource
from .models import StagedResourceCandidate

log = logging.getLogger(__name__)

# Cap each chunk before it enters the prompt (token/cost control) and bound the
# number of chunks so a long page can't blow up a single call.
MAX_CHARS_PER_CHUNK = 6000
MAX_CHUNKS = 5

# The exact string the admin UI + audit log use to distinguish LLM output from
# rule-based output. Must not change without updating those consumers.
EXTRACTION_METHOD = "llm_structured_extraction"

_DEFAULT_CONFIDENCE = 0.6

_SYSTEM = (
    "You extract structured relocation resource-guide entries from webpage text "
    "for people moving abroad. Output ONLY a JSON object of the form "
    '{"resources": [ ... ]}. Ground every entry strictly in the supplied text — '
    "do not invent facts, requirements, or links that are not present."
)


def _valid_categories() -> List[str]:
    """Category keys the LLM may use, deduped (the domain→category map is
    many-to-one, so `.values()` repeats)."""
    seen: set = set()
    out: List[str] = []
    for v in CONTENT_DOMAIN_TO_CATEGORY.values():
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _parse_resources(response: str) -> List[Any]:
    """Best-effort parse of the LLM text into a list of resource dicts.

    Tolerates: a JSON object with a 'resources' (or 'items') array, a bare JSON
    array, or a JSON array embedded in surrounding prose. Returns [] on anything
    unparseable — never raises (the fallback must degrade to zero recall, not an
    exception)."""
    if not response:
        return []
    try:
        data: Any = json.loads(response)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\[.*\]", response, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return []
    if isinstance(data, dict):
        data = data.get("resources") or data.get("items") or []
    return data if isinstance(data, list) else []


async def extract_resource_candidates_llm(
    chunks: List[Chunk],
    source: CrawlSource,
    source_url: str,
    page_title: str,
) -> List[StagedResourceCandidate]:
    """LLM fallback extractor. Same signature + return type as the rule-based
    `extract_resource_candidates`. Returns [] when there is nothing to extract or
    the LLM call/parse fails (so the crawler simply keeps the rule-based result).
    """
    if not chunks:
        return []

    # MANDATORY: mask PII in every chunk BEFORE it enters the prompt.
    combined_text = "\n\n".join(
        mask_pii((chunk.chunk_text or "")[:MAX_CHARS_PER_CHUNK])
        for chunk in chunks[:MAX_CHUNKS]
    )
    if not combined_text.strip():
        return []

    default_category = CONTENT_DOMAIN_TO_CATEGORY.get(source.content_domain, "admin_essentials")
    valid_categories = _valid_categories()

    user_prompt = (
        f"Relocation destination: {source.country_name or source.country_code}\n"
        f"Page title: {page_title}\n"
        f"Source: {source_url} (trust tier: {source.trust_tier})\n\n"
        "From the TEXT below, extract 1-3 distinct, self-contained resource-guide "
        "entries useful to someone relocating. Each entry must be a different topic "
        "(not a repetition) with at least one paragraph of actionable information.\n\n"
        'Return ONLY a JSON object: {"resources": [ {…}, … ]}. Each entry object '
        "must have:\n"
        "  title: string (clear, specific)\n"
        "  summary: string (1-2 sentences, max 300 chars)\n"
        "  body: string (50-2000 chars of actionable content)\n"
        f"  category_key: exactly one of {valid_categories}\n"
        "  confidence_score: float 0.0-1.0 (your confidence this is a useful "
        "relocation resource)\n"
        "  tags: array of up to 5 keyword strings\n\n"
        f"TEXT:\n{combined_text}"
    )

    try:
        response = await llm_client.complete_text(
            system=_SYSTEM,
            user=user_prompt,
            temperature=0.1,
            json_object=True,
        )
    except Exception as exc:  # provider/transport/key failure → degrade to no recall
        log.warning("LLM resource extraction failed for %s: %s", source_url, exc)
        return []

    raw = _parse_resources(response)

    candidates: List[StagedResourceCandidate] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        body = str(item.get("body") or "").strip()
        if not title or not body:
            continue

        category_key = item.get("category_key") or default_category
        if category_key not in valid_categories:
            category_key = default_category

        try:
            confidence = float(item.get("confidence_score", _DEFAULT_CONFIDENCE))
        except (TypeError, ValueError):
            confidence = _DEFAULT_CONFIDENCE
        confidence = min(max(confidence, 0.0), 1.0)

        tags = [str(t) for t in (item.get("tags") or [])][:5]

        candidates.append(
            StagedResourceCandidate(
                country_code=source.country_code,
                country_name=source.country_name,
                city_name=source.city_name,
                title=title,
                category_key=category_key,
                resource_type="guide",
                audience_type="all",
                summary=str(item.get("summary") or "")[:300],
                body=body,
                content_json={"sections": [{"heading": "Content", "text": body}]},
                tags=tags,
                source_url=source_url,
                source_name=source.source_name,
                trust_tier=source.trust_tier,
                confidence_score=confidence,
                extraction_method=EXTRACTION_METHOD,
                provenance={
                    "source_url": source_url,
                    "page_title": page_title,
                    "llm_model": "auto",
                },
            )
        )

    return candidates
