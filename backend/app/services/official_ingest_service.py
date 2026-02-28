from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ...database import db
from .requirements_extractor import extract_requirements_from_doc

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_EXCERPT_CHARS = 5000

OFFICIAL_DOMAINS: Dict[str, list[str]] = {
    "US": ["uscis.gov", "travel.state.gov", "cbp.gov", "ssa.gov", "irs.gov"],
    "SG": ["mom.gov.sg", "ica.gov.sg", "iras.gov.sg", "gov.sg"],
}


def _is_allowed_domain(url: str, destination_country: str) -> bool:
    host = urlparse(url).netloc.lower()
    allowed = OFFICIAL_DOMAINS.get(destination_country.upper(), [])
    return any(host.endswith(domain) for domain in allowed)


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
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    title = (soup.title.string if soup.title else "") or ""
    main = soup.find("main") or soup.body
    text = main.get_text(separator=" ", strip=True) if main else ""
    text = " ".join(text.split())
    excerpt = text[:MAX_EXCERPT_CHARS] if text else ""
    return title.strip(), excerpt.strip()


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
        title, excerpt = _extract_text(html)
        if not excerpt:
            raise ValueError("Empty content after extraction")
        content_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        fetch_status = "fetched"
    except Exception as exc:
        fetch_status = "fetch_failed"
        fetch_error = str(exc)

    pack = db.ensure_knowledge_pack(destination_country, domain_area)
    doc = db.upsert_knowledge_doc_by_url(
        pack_id=pack["id"],
        source_url=final_url,
        title=title or final_url,
        publisher=urlparse(final_url).netloc,
        text_content=excerpt or "",
        fetched_at=fetched_at,
        fetch_status=fetch_status,
        content_excerpt=excerpt or None,
        content_sha256=content_hash,
        last_verified_at=fetched_at if fetch_status == "fetched" else None,
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
            facts = extracted.get("facts") or []
            facts_created = len(facts)
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
