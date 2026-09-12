from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests

from ...crawler.parsers import immigration_page_parser
from ...database import db
from .requirement_fact_extractor import RequirementFact, extract_requirement_facts
from .requirements_extractor import (
    _required_fields_from_text,
    _slugify,
    extract_requirements_from_doc,
)

log = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
# [AIQ-1821] Matches requirement_fact_extractor._MAX_CONTENT_CHARS so the excerpt we
# persist is exactly what the extractor can consume — a smaller cap here would silently
# withhold content the LLM had room for. This truncates *parsed* text, not raw HTML.
MAX_EXCERPT_CHARS = 24_000
# Same floor as backend.imports.immigration.fetcher.MIN_TEXT_CHARS. A JS shell or
# login chrome is not a document; storing it as fetched evidence is the NULL-deref.
MIN_TEXT_CHARS = 600
_LOGIN_PATH_MARKERS = ("/login", "/signin", "/sign-in", "/log-in", "/sso")

OFFICIAL_DOMAINS: Dict[str, list[str]] = {
    "US": ["uscis.gov", "travel.state.gov", "cbp.gov", "ssa.gov", "irs.gov"],
    "SG": ["mom.gov.sg", "ica.gov.sg", "iras.gov.sg", "gov.sg"],
    # [AIQ-1821] FR->NO corridor. Norway's authorities split by topic: udi.no
    # (immigration), skatteetaten.no (D-number, skattekort, folkeregister),
    # politiet.no (EEA registration), nav.no (social security).
    "NO": ["udi.no", "skatteetaten.no", "politiet.no", "nav.no"],
    "FR": ["service-public.fr", "cleiss.fr", "urssaf.fr", "ameli.fr", "impots.gouv.fr"],
}


def _is_allowed_domain(url: str, destination_country: str) -> bool:
    host = urlparse(url).netloc.lower()
    allowed = OFFICIAL_DOMAINS.get(destination_country.upper(), [])
    return any(host.endswith(domain) for domain in allowed)


def _is_login_page(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path == marker or path.startswith(marker + "/") for marker in _LOGIN_PATH_MARKERS)


def _fetch_html(url: str, destination_country: str) -> Tuple[str, str]:
    headers = {"User-Agent": "ReloPassBot/1.0 (official-source-ingest)"}
    resp = requests.get(url, headers=headers, timeout=15, stream=True, allow_redirects=True)
    resp.raise_for_status()
    final_url = resp.url
    if not _is_allowed_domain(final_url, destination_country):
        raise ValueError("Redirected to a non-official domain")
    content_type = (resp.headers.get("Content-Type") or "").lower()
    if "text/html" not in content_type:
        raise ValueError("Non-HTML content type")
    data = bytearray()
    for chunk in resp.iter_content(chunk_size=8192):
        if chunk:
            data.extend(chunk)
            if len(data) > MAX_RESPONSE_BYTES:
                raise ValueError("Response too large")
    return final_url, data.decode(resp.encoding or "utf-8", errors="replace")


def _extract_text(html: str) -> Tuple[str, str]:
    """Parse a government page into (title, excerpt).

    [AIQ-1821] Delegates to the crawler's immigration-page parser rather than
    stripping tags here. That parser drops script/style/nav/footer/aside/form/
    noscript, narrows to <main>/<article>/<body>, and — the reason it matters —
    keeps headings, list items and tables as markdown. On government pages the
    requirement semantics live in exactly those structures, and flattening them
    to a single run of text is what made the previous extractor unreliable.
    """
    parsed = immigration_page_parser.parse(html)
    text = (parsed.get("text") or "").strip()
    title = (parsed.get("title") or "").strip()
    return title, text[:MAX_EXCERPT_CHARS]


# ── [AIQ-1821] LLM fact extraction ───────────────────────────────────────────
# The rule-based `extract_requirements_from_doc` splits sentences and keyword-matches,
# which yields low-precision facts. The P4-01 extractor is a real LLM extractor with
# `mask_pii` in front of it; this maps its output onto the legacy fact shape that
# `list_approved_requirement_facts` -> `compute_requirements_sufficiency` already reads.

# RequirementFact.requirement_type is (document|fee|timeline|eligibility|other);
# requirement_facts.fact_type CHECK is a different, wider set — 'timeline' has no
# counterpart there and maps to 'deadline'.
_LLM_FACT_TYPE_MAP = {
    "document": "document",
    "fee": "fee",
    "timeline": "deadline",
    "eligibility": "eligibility",
    "other": "other",
}


def _confidence_band(score: float) -> str:
    """Numeric confidence_score (0,1] -> the legacy CHECK's low|medium|high."""
    if score < 0.5:
        return "low"
    if score < 0.8:
        return "medium"
    return "high"


def _map_llm_fact(fact: RequirementFact) -> Dict[str, Any]:
    """One RequirementFact -> one `requirement_facts` row dict."""
    text = (fact.text or "").strip()
    key_seed = " ".join(text.split()[:6])
    return {
        "id": str(uuid.uuid4()),
        "fact_type": _LLM_FACT_TYPE_MAP.get(fact.requirement_type, "other"),
        "fact_key": _slugify(key_seed) + "-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:6],
        "fact_text": text,
        "applies_to": {},
        "required_fields": _required_fields_from_text(text),
        "evidence_quote": (fact.source_quote or "").strip()[:250] or None,
        "confidence": _confidence_band(fact.confidence_score),
    }


def _llm_facts_for_doc(source_url: str, content: str, corridor: str = "") -> list[Dict[str, Any]]:
    """Run the P4-01 LLM extractor over already-parsed text. Never raises.

    `content` is passed explicitly so the extractor does NOT re-fetch the page — we
    already have the parsed text, and re-fetching would feed it raw HTML again.
    `mask_pii` runs inside `extract_requirement_facts` before the model call.
    """
    if not content.strip():
        return []
    try:
        facts = asyncio.run(
            extract_requirement_facts(source_url, corridor=corridor, content=content)
        )
    except Exception as exc:  # LLM/network failure must not fail the ingest
        log.warning("official_ingest: LLM extraction failed url=%s err=%s", source_url, exc)
        return []
    return [_map_llm_fact(f) for f in facts]


def ingest_url_to_knowledge_doc(
    url: str,
    destination_country: str,
    domain_area: str,
) -> Dict[str, Optional[str]]:
    if not _is_allowed_domain(url, destination_country):
        raise ValueError("URL not in official allowlist")

    fetched_at = datetime.utcnow().isoformat() + "Z"
    final_url = url
    title = ""
    excerpt = ""
    fetch_status = "not_fetched"
    fetch_error = None
    content_hash = None
    try:
        final_url, html = _fetch_html(url, destination_country)
        if _is_login_page(final_url):
            raise ValueError("Login-page redirect")
        title, excerpt = _extract_text(html)
        if not excerpt:
            raise ValueError("Empty content after extraction")
        if len(excerpt) < MIN_TEXT_CHARS:
            raise ValueError(
                f"only {len(excerpt)} chars extracted (min {MIN_TEXT_CHARS})"
            )
        content_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        fetch_status = "fetched"
    except Exception as exc:
        fetch_status = "fetch_failed"
        fetch_error = str(exc)
        source_host = urlparse(final_url).netloc
        log.warning(
            "official_ingest: fetch failed source_host=%s failure_reason=%s url=%s",
            source_host,
            fetch_error,
            final_url,
        )
        # Failed fetch is NULL: do not persist empty text_content as evidence.
        # knowledge_docs.text_content is NOT NULL — skipping the upsert avoids a
        # placeholder row. Existing real excerpts are left untouched.
        return {
            "doc_id": None,
            "rule_id": None,
            "fetch_status": fetch_status,
            "facts_created": 0,
            "error": fetch_error,
        }

    pack = db.ensure_knowledge_pack(destination_country, domain_area)
    doc = db.upsert_knowledge_doc_by_url(
        pack_id=pack["id"],
        source_url=final_url,
        title=title or final_url,
        publisher=urlparse(final_url).netloc,
        text_content=excerpt,
        fetched_at=fetched_at,
        fetch_status=fetch_status,
        content_excerpt=excerpt,
        content_sha256=content_hash,
        last_verified_at=fetched_at,
    )

    rule_id = None
    facts_created = 0
    if fetch_status == "fetched":
        rule_id = db.create_baseline_rule_for_doc(
            pack_id=pack["id"],
            doc_id=doc["id"],
            doc_title=doc.get("title") or title or final_url,
            domain_area=domain_area,
        )
        extracted = extract_requirements_from_doc(
            {
                "id": doc["id"],
                "title": doc.get("title") or title or final_url,
                "source_url": final_url,
                "content_excerpt": doc.get("content_excerpt") or doc.get("text_content") or "",
            },
            destination_country,
            domain_area,
        )
        if extracted.get("entity"):
            entity = db.upsert_requirement_entity(
                destination_country=destination_country,
                domain_area=domain_area,
                topic_key=extracted["entity"]["topic_key"],
                title=extracted["entity"]["title"],
                status="pending",
            )
            # [AIQ-1821] Prefer the LLM extractor; keep the rule-based facts as the
            # fallback so a model/network failure still ingests something.
            facts = _llm_facts_for_doc(
                final_url,
                doc.get("content_excerpt") or doc.get("text_content") or "",
                corridor=destination_country,
            )
            extraction_method = "llm"
            if not facts:
                facts = extracted.get("facts") or []
                extraction_method = "rule_based"
            facts_created = len(facts)
            log.info(
                "official_ingest: %d facts via %s url=%s",
                facts_created, extraction_method, final_url,
            )
            now = datetime.utcnow().isoformat()
            db.insert_requirement_facts([
                {
                    "id": fact["id"],
                    "entity_id": entity["id"],
                    "fact_type": fact["fact_type"],
                    "fact_key": fact["fact_key"],
                    "fact_text": fact["fact_text"],
                    "applies_to": json.dumps(fact.get("applies_to") or {}),
                    "required_fields": json.dumps(fact.get("required_fields") or []),
                    "source_doc_id": doc["id"],
                    "source_url": final_url,
                    "evidence_quote": fact.get("evidence_quote"),
                    "confidence": fact.get("confidence", "medium"),
                    "status": "pending",
                    "created_at": now,
                }
                for fact in facts
            ])

    return {
        "doc_id": doc["id"],
        "rule_id": rule_id,
        "fetch_status": fetch_status,
        "facts_created": facts_created,
        "error": fetch_error,
    }
