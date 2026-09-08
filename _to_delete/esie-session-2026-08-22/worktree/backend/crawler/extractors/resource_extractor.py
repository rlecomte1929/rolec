"""
Rule-based resource extraction from chunks.
Produces StagedResourceCandidate records.

[CRAWL-QUALITY-1 / AIQ-1145] Quality gates so the rule-based extractor stops
staging un-publishable output. A 2026-06-17 review of the first 19 staged
candidates published 0 and rejected all 19 — bot-walls, 12 duplicate chunks of
one page (all titled with the raw HTML <title>), and nav/boilerplate dumps. The
gates below reject those classes. When a page yields nothing after the gates the
caller's LLM fallback fires (pipeline only falls back on an empty rule-based
result), so making this stricter also *enables* the fallback on low-quality pages.
"""
import logging
import re
from typing import List

from ..chunkers.chunker import Chunk
from ..config.models import CONTENT_DOMAIN_TO_CATEGORY, CrawlSource
from .models import StagedResourceCandidate

log = logging.getLogger(__name__)

# Minimum lengths for validation
MIN_TITLE_LEN = 3
MIN_BODY_LEN_FOR_GUIDE = 50
MIN_CONFIDENCE = 0.3
MAX_TITLE_LEN = 120
# At most this many distinct resources per page — guards against one page being
# chunked into many near-identical candidates (the 12-fragment case).
MAX_CANDIDATES_PER_PAGE = 6

# Bot-detection / interstitial / error pages must never be staged as content.
_BOT_WALL_HOST_MARKERS = (
    "validate.perfdrive.com",
    "challenges.cloudflare.com",
    "/cdn-cgi/challenge",
    "captcha",
)
_BOT_WALL_TEXT_MARKERS = (
    "we apologize for the inconvenience",
    "verify you are human",
    "verifying you are human",
    "are you a robot",
    "enable javascript to continue",
    "please enable cookies",
    "access denied",
    "checking your browser",
    "ddos protection",
    "request unsuccessful",
    "incapsula incident",
    "perfdrive",
)

# Site-name separators commonly appended to a page <title> ("Page | Site : tag").
_TITLE_SEPARATORS = (" | ", " : ", " — ", " - ", " · ", " // ")

# Page-scaffolding / meta-navigation phrases: signal a page INTRO or index ("read
# the checklist at the end of the page", "here you can find out…"), not guidance.
_SCAFFOLD_MARKERS = (
    "at the end of the page",
    "at the end of this page",
    "checklist at the end",
    "here you can find out",
    "here, you can find",
    "find out below",
    "see below",
    "scroll down",
    "on this page you",
    "in this article",
    "read more below",
    "table of contents",
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def extract_resource_candidates(
    chunks: List[Chunk],
    source: CrawlSource,
    source_url: str,
    page_title: str,
) -> List[StagedResourceCandidate]:
    """
    Extract resource candidates from chunks using rule-based heuristics.

    Returns [] (so the pipeline's LLM fallback can take over) when the page is a
    bot-wall / error page, or when every chunk is nav/boilerplate or untitled.
    """
    category_key = CONTENT_DOMAIN_TO_CATEGORY.get(source.content_domain, "admin_essentials")

    joined = " ".join(c.chunk_text for c in chunks[:5])[:2000]
    if _is_bot_wall_or_error(page_title, source_url, joined):
        log.info("resource_extractor: skipping bot-wall/error page %s", source_url)
        return []

    clean_page_title = _clean_page_title(page_title)
    candidates: List[StagedResourceCandidate] = []

    for chunk in chunks:
        text = chunk.chunk_text.strip()
        if len(text) < MIN_BODY_LEN_FOR_GUIDE:
            continue
        # Reject nav menus / link-lists / homepage dumps — they pass the length
        # check but are not guidance.
        if _looks_like_nav_or_boilerplate(text):
            continue
        # Reject page intros / FAQ-heading lists / scaffolding (a real heading over
        # a non-answer body). These previously slipped through *and* suppressed the
        # LLM fallback (which only fires when rule-based returns nothing) — so
        # rejecting them sends the page to the LLM extractor instead.
        if _looks_like_page_index(text):
            continue

        title = _infer_title(chunk)
        if not title:
            # No real per-chunk heading — don't fall back to the raw page <title>
            # (that produced 12 identical 'Renting a flat | Handbook Germany'
            # candidates). Skip; the LLM fallback handles untitled dense pages.
            continue
        # A title that's just the site/page branding isn't a resource heading.
        if clean_page_title and _norm(title) == _norm(clean_page_title):
            continue
        if _norm(title) == _norm(page_title):
            continue

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
                summary=_truncate(text, 300),
                body=text,
                content_json={"sections": [{"heading": chunk.heading_path or title, "text": text}]},
                tags=[],
                source_url=source_url,
                source_name=source.source_name,
                trust_tier=source.trust_tier,
                confidence_score=confidence,
                extraction_method="rule_based",
                provenance=provenance,
            )
        )

    return _dedupe_and_cap(candidates)


def _is_bot_wall_or_error(page_title: str, source_url: str, sample_text: str) -> bool:
    """True if the fetched page is a bot-detection / CAPTCHA / error interstitial
    rather than real content."""
    url_l = (source_url or "").lower()
    if any(m in url_l for m in _BOT_WALL_HOST_MARKERS):
        return True
    hay = (_norm(page_title) + " " + _norm(sample_text))
    return any(m in hay for m in _BOT_WALL_TEXT_MARKERS)


def _looks_like_nav_or_boilerplate(text: str) -> bool:
    """True for nav menus, link-label lists and homepage dumps: many short lines
    with almost no sentences."""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return True
    sentences = text.count(". ") + text.count(".\n") + (1 if text.rstrip().endswith(".") else 0)
    short_lines = sum(1 for ln in lines if len(ln) < 40)
    # A wall of short fragments with barely any sentences = nav / link list.
    if len(lines) >= 5 and short_lines / len(lines) > 0.7 and sentences < 2:
        return True
    # Long-ish blob that contains essentially no sentences = boilerplate.
    if len(text) > 200 and sentences == 0:
        return True
    return False


def _looks_like_page_index(text: str) -> bool:
    """True for a page intro / FAQ-heading list / scaffolding blob: a real heading
    over a body that is a string of sub-questions or 'see the rest of this page'
    meta-text rather than a single answer."""
    low = text.lower()
    # Many questions strung together = an FAQ/heading index, not one answer.
    if text.count("?") >= 3:
        return True
    if any(m in low for m in _SCAFFOLD_MARKERS):
        return True
    return False


def _clean_page_title(page_title: str) -> str:
    """Strip a trailing site-name suffix from a page <title>."""
    t = (page_title or "").strip()
    for sep in _TITLE_SEPARATORS:
        if sep in t:
            t = t.split(sep)[0].strip()
            break
    return t


def _infer_title(chunk: Chunk) -> str:
    """A real per-chunk heading, or '' if none. Deliberately does NOT fall back
    to the page <title>."""
    if chunk.heading_path:
        parts = [p.strip() for p in chunk.heading_path.split(" > ") if p.strip()]
        if parts and MIN_TITLE_LEN <= len(parts[-1]) <= MAX_TITLE_LEN:
            return parts[-1]
    first_line = chunk.chunk_text.split("\n")[0].strip()
    if MIN_TITLE_LEN <= len(first_line) <= MAX_TITLE_LEN:
        return first_line
    return ""


def _dedupe_and_cap(candidates: List[StagedResourceCandidate]) -> List[StagedResourceCandidate]:
    """Collapse same-title candidates from one page (keep the highest confidence)
    and cap how many a single page can contribute."""
    best_by_title: dict = {}
    for c in candidates:
        key = _norm(c.title)
        cur = best_by_title.get(key)
        if cur is None or c.confidence_score > cur.confidence_score:
            best_by_title[key] = c
    ordered = sorted(best_by_title.values(), key=lambda x: x.confidence_score, reverse=True)
    return ordered[:MAX_CANDIDATES_PER_PAGE]


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
