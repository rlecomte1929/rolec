"""[AIQ-1090 / P4-01] Requirement fact extraction — pure LLM service.

Given an official immigration source URL, fetch the page, mask any PII, and ask the LLM
to extract structured requirement facts (documents, fees, timelines, eligibility). This
is the Phase-4 foundation: P4-02 (endpoint) persists the results, P4-04 (eval harness)
scores them. Keeping extraction PURE (no DB imports) makes it testable without a database
and lets the API layer own the transaction boundary.

GDPR (Art. 28): fetched URL content may contain user-submitted free text, so it MUST pass
through ``mask_pii`` before reaching the LLM sub-processor (CLAUDE.md hard rule). Never log
the raw/fetched content.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, List, Optional

import httpx

from ...crawler.parsers import immigration_page_parser
from .llm_client import complete_text
from .pii_masker import mask_pii

log = logging.getLogger(__name__)

# requirement_type is constrained to this set (CLAUDE.md / brief); anything else → 'other'.
ALLOWED_REQUIREMENT_TYPES = ("document", "fee", "timeline", "eligibility", "other")

_FETCH_TIMEOUT_S = 30.0
_MAX_CONTENT_CHARS = 24_000  # cap the masked text fed to the prompt (token control)
_DEFAULT_CONFIDENCE = 0.5

_SYSTEM_PROMPT = (
    "You are an immigration-requirements extraction assistant. From the official source "
    "text provided, extract discrete, factual requirements. Return JSON only — no prose. "
    "Each fact's requirement_type MUST be one of: document, fee, timeline, eligibility, other. "
    "confidence_score is your confidence the fact is correct and present in the text, in the "
    "range (0, 1]. source_quote is the verbatim sentence the fact came from. Do NOT invent "
    "facts that are not supported by the text; if the text contains no requirements, return "
    'an empty list. Shape: {"facts": [{"text": str, "requirement_type": str, '
    '"source_quote": str, "confidence_score": number}]}'
)


@dataclass
class RequirementFact:
    """One structured requirement fact extracted from a source URL (pre-persistence)."""

    text: str
    requirement_type: str
    corridor: str
    confidence_score: float
    source_quote: str
    source_url: str
    extraction_method: str = "llm"


async def fetch_url_content(url: str, *, timeout: float = _FETCH_TIMEOUT_S) -> str:
    """Fetch a URL and return its readable article text.

    [AIQ-1821] Returns PARSED text, not raw HTML. Returning `resp.text` fed the model
    `<head>`, stylesheet links and the nav menu: on a modern government page the article
    starts well past `_MAX_CONTENT_CHARS`, so the body never reached the prompt at all
    (measured on skatteetaten.no: `<main>` at ~35,000 chars vs a 24,000-char cap → zero
    facts, every time). The crawler's immigration-page parser strips chrome and keeps
    headings, lists and tables as markdown, which is where requirement semantics live.
    """
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "ReloPass-RequirementExtractor/1.0"})
        resp.raise_for_status()
        html = resp.text
    parsed = (immigration_page_parser.parse(html).get("text") or "").strip()
    # A JS-only shell parses to nothing; fall back to the raw body rather than returning
    # an empty string, so the caller sees the same "no facts" outcome either way.
    return parsed or html


def _build_user_prompt(masked_content: str, corridor: str, source_url: str) -> str:
    return (
        f"Corridor: {corridor or 'unspecified'}\n"
        f"Source URL: {source_url}\n\n"
        f"Source text (PII-masked):\n{masked_content}\n\n"
        "Extract the requirement facts as JSON per the schema."
    )


def _coerce_confidence(value: Any) -> float:
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return _DEFAULT_CONFIDENCE
    # Clamp into (0, 1] — never 0, never >1.
    if conf <= 0:
        return _DEFAULT_CONFIDENCE
    return min(conf, 1.0)


def _parse_facts(raw_json: str, *, corridor: str, source_url: str) -> List[RequirementFact]:
    """Parse the LLM's JSON text into RequirementFacts. Malformed JSON → [] (fail-soft)."""
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        log.warning("requirement_fact_extractor: malformed JSON from LLM; returning [] (url=%s)", source_url)
        return []

    if isinstance(data, dict):
        items = data.get("facts")
    elif isinstance(data, list):
        items = data
    else:
        items = None

    out: List[RequirementFact] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue  # a fact with no text is not a fact
        rtype = str(item.get("requirement_type") or "other").strip().lower()
        if rtype not in ALLOWED_REQUIREMENT_TYPES:
            rtype = "other"
        out.append(
            RequirementFact(
                text=text,
                requirement_type=rtype,
                corridor=corridor,
                confidence_score=_coerce_confidence(item.get("confidence_score")),
                source_quote=str(item.get("source_quote") or "").strip(),
                source_url=source_url,
                extraction_method="llm",
            )
        )
    return out


async def extract_requirement_facts(
    url: str,
    *,
    corridor: str = "",
    content: Optional[str] = None,
) -> List[RequirementFact]:
    """Fetch (or accept) source text → mask PII → LLM → List[RequirementFact].

    ``content`` lets callers (and tests) pass already-fetched text to skip the network.
    PII is masked BEFORE the LLM call — mandatory, no exceptions.
    """
    raw = content if content is not None else await fetch_url_content(url)
    masked = mask_pii(raw or "")[:_MAX_CONTENT_CHARS]
    user_prompt = _build_user_prompt(masked, corridor, url)
    raw_json = await complete_text(system=_SYSTEM_PROMPT, user=user_prompt, json_object=True)
    return _parse_facts(raw_json, corridor=corridor, source_url=url)
