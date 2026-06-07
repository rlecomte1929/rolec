"""
Catalog scraper — Phase 2b.

When a new (category, destination_city) pair is seen with zero rows
in the master catalog, this module populates up to 10 plausible vendor
entries so HR has something to curate. The vendors land in
`service_catalog_items` with `source='scraper'`.

Implementation: LLM synthesis (OpenAI) with a structured JSON schema.
HTML scraping was considered and rejected for the demo — sites change
shape weekly and a fragile scraper would block more than help. The
LLM produces directionally-correct vendors based on its training data;
HR is the authority gate that catches inaccuracies before employees
see anything (Phase 2c filter).

Operational guards:
- OFF by default. Set `CATALOG_SCRAPER_ENABLED=1` to turn on.
- Requires `OPENAI_API_KEY` to be set; otherwise returns 0 without
  raising (so case creation never fails just because we couldn't scrape).
- Idempotent via service_catalog.upsert_item's (category, external_id)
  unique key — re-running the scrape on the same (category, city)
  upserts in place rather than duplicating.
- Cap of 10 items per (category, city) honored at the prompt level AND
  at the slice level (truncate if the model returns more).
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from . import service_catalog
from .llm_client import complete_text_sync

log = logging.getLogger(__name__)

MAX_ITEMS_PER_DESTINATION = 10
DEFAULT_MODEL = os.getenv("CATALOG_SCRAPER_MODEL", "gpt-4o-mini")
DEFAULT_TIMEOUT_S = float(os.getenv("CATALOG_SCRAPER_TIMEOUT_SECONDS", "45"))


def _enabled() -> bool:
    """Hard gate so the scraper never fires unintentionally in tests / CI."""
    flag = (os.getenv("CATALOG_SCRAPER_ENABLED") or "").strip().lower()
    return flag in ("1", "true", "yes")


def _slug(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return s[:64] or "x"


def _build_prompt(category: str, destination_city: str, country: Optional[str]) -> str:
    """
    Strict-JSON prompt. Tell the model what shape to return so we can
    parse without prose stripping.
    """
    return (
        "You produce a curated baseline list of real, plausible service-provider "
        "vendors that an HR mobility lead at a 500-person company would consider "
        "for a relocating employee. The list will be reviewed by HR before any "
        "employee sees it.\n\n"
        f"CATEGORY: {category}\n"
        f"DESTINATION CITY: {destination_city}\n"
        f"COUNTRY: {country or '(unknown)'}\n\n"
        f"Return up to {MAX_ITEMS_PER_DESTINATION} vendors. Output strictly a "
        "JSON object of shape:\n"
        "{\n"
        "  \"vendors\": [\n"
        "    {\n"
        "      \"name\": \"<official vendor name>\",\n"
        "      \"summary\": \"<one-sentence description, ≤140 chars>\",\n"
        "      \"website\": \"<https URL or null>\",\n"
        "      \"strengths\": [\"<short tag>\", ...],\n"
        "      \"notes\": \"<optional extra info or null>\"\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Constraints:\n"
        "- Only vendors that genuinely operate in or serve the destination city.\n"
        "- Skip parent brands when a more specific local subsidiary is well known.\n"
        "- Do NOT include placeholders, lorem-ipsum, or fictional-sounding names.\n"
        "- If you cannot confidently produce N vendors, return fewer.\n"
        "- Return ONLY the JSON object. No prose, no markdown fences."
    )


def _call_llm(prompt: str) -> str:
    """Run the chat completion via the shared wrapper. Caller validates JSON.

    AIQ-401: routes through llm_client.complete_text_sync for timeout + 429/5xx
    retry + structured logging. Same model, json_object contract, temperature,
    and the 45s timeout / 2 retries the direct client used.
    """
    return complete_text_sync(
        system=(
            "You are a careful research assistant for a corporate "
            "relocation platform. You output strictly valid JSON."
        ),
        user=prompt,
        model=DEFAULT_MODEL,
        temperature=0.2,
        json_object=True,
        timeout=DEFAULT_TIMEOUT_S,
        max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "2")),
    ).strip()


def _parse_vendors(raw: str) -> List[Dict[str, Any]]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("catalog_scraper_invalid_json snippet=%s", raw[:200])
        return []
    vendors = payload.get("vendors") if isinstance(payload, dict) else None
    if not isinstance(vendors, list):
        return []
    out: List[Dict[str, Any]] = []
    for v in vendors[:MAX_ITEMS_PER_DESTINATION]:
        if not isinstance(v, dict):
            continue
        name = (v.get("name") or "").strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "summary": (v.get("summary") or "").strip(),
                "website": (v.get("website") or None) or None,
                "strengths": [str(s) for s in (v.get("strengths") or []) if str(s).strip()],
                "notes": (v.get("notes") or None),
            }
        )
    return out


def populate_destination_catalog(
    *,
    category: str,
    destination_city: str,
    country: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Scrape (synthesize) up to MAX_ITEMS_PER_DESTINATION vendors and write
    them to the master catalog. Returns the list of upserted master rows.

    The LLM call goes through llm_client.complete_text_sync (AIQ-401); tests
    patch ``catalog_scraper.complete_text_sync``. Returns an empty list
    (without raising) when:
      - the scraper is disabled,
      - no OPENAI_API_KEY is set,
      - the LLM returns non-JSON or zero usable vendors.
    """
    if not _enabled():
        log.info(
            "catalog_scraper_skipped_disabled category=%s destination_city=%s",
            category,
            destination_city,
        )
        return []
    # L1 cost short-circuit (Phase 2b-secured): if the master already has any
    # rows for this (category, city), skip the LLM call entirely. This is the
    # biggest single cost saver — even repeated triggers from a malicious
    # caller never re-burn tokens once the slot is populated. Re-scraping a
    # populated destination requires deactivating the existing rows first
    # (admin path, Phase 2h).
    if service_catalog.count_by_category_city(category, destination_city) > 0:
        log.info(
            "catalog_scraper_skipped_already_populated category=%s destination_city=%s",
            category,
            destination_city,
        )
        return []
    if not os.getenv("OPENAI_API_KEY"):
        log.warning(
            "catalog_scraper_no_api_key category=%s destination_city=%s",
            category,
            destination_city,
        )
        return []

    prompt = _build_prompt(category, destination_city, country)
    try:
        raw = _call_llm(prompt)
    except Exception as ex:  # pragma: no cover — network path
        log.warning(
            "catalog_scraper_llm_failed category=%s destination_city=%s error=%s",
            category,
            destination_city,
            ex,
        )
        return []

    vendors = _parse_vendors(raw)
    if not vendors:
        log.info(
            "catalog_scraper_returned_empty category=%s destination_city=%s",
            category,
            destination_city,
        )
        return []

    inserted: List[Dict[str, Any]] = []
    for v in vendors:
        external_id = f"scrape-{_slug(category)}-{_slug(destination_city)}-{_slug(v['name'])}"
        attributes = {
            "summary": v["summary"],
            "website": v["website"],
            "strengths": v["strengths"],
            "notes": v["notes"],
            "_provenance": "llm_synthesis",
        }
        try:
            row = service_catalog.upsert_item(
                category=category,
                name=v["name"],
                attributes=attributes,
                source="scraper",
                city=destination_city,
                country=country,
                external_id=external_id,
            )
            inserted.append(row)
        except Exception:  # pragma: no cover — unexpected DB issue
            log.exception(
                "catalog_scraper_upsert_failed category=%s name=%s",
                category,
                v["name"],
            )
    log.info(
        "catalog_scraper_done category=%s destination_city=%s inserted=%d",
        category,
        destination_city,
        len(inserted),
    )
    return inserted
