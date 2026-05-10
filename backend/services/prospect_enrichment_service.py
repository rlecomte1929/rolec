"""
HR prospect enrichment agent.

Given a seed row in `prospect_candidates` (company name + domain + optional
notes), fetches a small bundle of pages from the company's site, optionally
runs one mobility-oriented web search, and asks an LLM to synthesise a
structured ICP profile:

  {
    "company_profile":  {size_band, sector, hq_country, offices[], summary},
    "mobility_signals": [{type, evidence, source}, ...],
    "icp_score":        0..100,
    "icp_rationale":    short text,
    "suggested_contact_title": str,
    "suggested_hook":   str,
  }

The qualification band is then applied deterministically from
`prospect_icp_config.band_thresholds` so tuning the boundaries never
requires a model re-run.

Same operational shape as `OpenAIPolicyCanonicalExtractor`: same env
vars, same `llm_flags` disabled gate, same JSON-object response format.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ..app.db import SessionLocal
from ..app.models import ProspectCandidate
from ..core.llm_flags import LLMDisabled, policy_llm_disabled, policy_llm_temperature
from .prospect_icp_config import band_for_score, config_as_prompt_block
from .prospect_web_fetcher import fetch_prospect_snapshot
from .prospect_web_search import run_prospect_web_search

log = logging.getLogger(__name__)

DEFAULT_MODEL_ENV = "OPENAI_PROSPECT_ENRICHMENT_MODEL"
FALLBACK_MODEL = "gpt-4.1-mini"


PROSPECT_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "company_profile": {
            "type": "object",
            "properties": {
                "size_band": {"type": "string"},
                "sector": {"type": "string"},
                "hq_country": {"type": "string"},
                "offices": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"},
            },
        },
        "mobility_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "evidence": {"type": "string"},
                    "source": {"type": "string"},
                },
            },
        },
        "icp_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "icp_rationale": {"type": "string"},
        "suggested_contact_title": {"type": "string"},
        "suggested_hook": {"type": "string"},
    },
    "required": ["icp_score"],
}


@dataclass
class EnrichmentRequest:
    prospect_id: str
    enable_web_search: bool = False


def _build_client() -> Any:
    if policy_llm_disabled():
        return LLMDisabled(reason="RELOPASS_POLICY_LLM_DISABLED=1")
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("openai package is required for prospect enrichment") from exc
    timeout_s = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))
    max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        timeout=timeout_s,
        max_retries=max_retries,
    )


def _model_name() -> str:
    return os.getenv(DEFAULT_MODEL_ENV, FALLBACK_MODEL)


def _build_user_prompt(
    *,
    company_name: str,
    domain: str,
    linkedin: str,
    raw_input_notes: str,
    website_text: str,
    search_text: str,
) -> str:
    return (
        f"COMPANY NAME: {company_name}\n"
        f"DOMAIN: {domain or '(none)'}\n"
        f"LINKEDIN: {linkedin or '(none)'}\n"
        f"ADMIN NOTES: {raw_input_notes or '(none)'}\n\n"
        f"=== WEBSITE EVIDENCE ===\n{website_text}\n\n"
        f"=== WEB SEARCH EVIDENCE ===\n{search_text}\n"
    )


def _system_prompt() -> str:
    icp_block = config_as_prompt_block()
    schema = json.dumps(PROSPECT_JSON_SCHEMA)
    return (
        "You are an ICP qualification analyst for ReloPass, a relocation "
        "operations platform. Given evidence gathered about one company, "
        "produce a strict JSON object matching the schema below. Base every "
        "field on the evidence provided — do not invent signals. If a field "
        "is unknown, omit it or use an empty string / empty array. If a "
        "disqualifier applies, cap icp_score below 30 and state why in "
        "icp_rationale.\n\n"
        f"{icp_block}\n\n"
        f"OUTPUT JSON SCHEMA: {schema}"
    )


def _call_llm(
    client: Any,
    *,
    system_prompt: str,
    user_prompt: str,
    model: str,
) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        temperature=policy_llm_temperature(),
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content if response.choices else "{}"
    try:
        return json.loads(content or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"LLM returned non-JSON content: {exc}") from exc


def _coerce_score(raw: Any) -> Optional[int]:
    try:
        score = int(raw)
    except (TypeError, ValueError):
        return None
    return max(0, min(100, score))


def _apply_enrichment_to_row(
    row: ProspectCandidate,
    *,
    enriched: Dict[str, Any],
    web_search_used: bool,
) -> None:
    score = _coerce_score(enriched.get("icp_score"))
    row.icp_score = score
    row.qualification_band = band_for_score(score)
    row.suggested_contact_title = (enriched.get("suggested_contact_title") or None) or None
    row.suggested_hook = enriched.get("suggested_hook") or None
    row.enriched_json = json.dumps(enriched, ensure_ascii=False)
    row.web_search_used = web_search_used
    row.status = "enriched"
    row.enrichment_error = None
    row.enriched_at = datetime.utcnow()


def _record_failure(row: ProspectCandidate, reason: str) -> None:
    row.status = "enrichment_failed"
    row.enrichment_error = reason[:2000]
    row.enriched_at = datetime.utcnow()


def enrich_prospect(request: EnrichmentRequest) -> None:
    """Enrich one prospect row end-to-end and persist the result.

    Runs inside its own `SessionLocal()` so it's safe to dispatch from
    `BackgroundTasks` without passing the request's DB session across
    the task boundary.
    """
    with SessionLocal() as db:  # type: Session
        row = db.get(ProspectCandidate, request.prospect_id)
        if row is None:
            log.warning("enrich_prospect: row not found id=%s", request.prospect_id)
            return
        try:
            _enrich_row(db, row, enable_web_search=request.enable_web_search)
        except Exception as exc:  # noqa: BLE001 — background boundary
            log.exception("prospect enrichment failed id=%s", row.id)
            _record_failure(row, f"{type(exc).__name__}: {exc}")
            db.commit()


def _enrich_row(
    db: Session,
    row: ProspectCandidate,
    *,
    enable_web_search: bool,
) -> None:
    raw_input = _safe_json(row.raw_input_json)
    notes = str(raw_input.get("notes") or "")
    domain = row.company_domain or str(raw_input.get("domain") or "")
    linkedin = row.company_linkedin_url or str(raw_input.get("linkedin") or "")

    snapshot = fetch_prospect_snapshot(domain) if domain else None
    website_text = snapshot.to_prompt_text() if snapshot else "(no domain provided)"

    search_text = "(web search disabled for this batch)"
    web_search_used = False
    if enable_web_search:
        outcome = run_prospect_web_search(row.company_name)
        search_text = outcome.to_prompt_text()
        web_search_used = True

    client = _build_client()
    if isinstance(client, LLMDisabled):
        _record_failure(row, f"LLM disabled: {client.reason}")
        if snapshot and snapshot.fetch_errors:
            row.enrichment_error = (
                (row.enrichment_error or "")
                + " | fetch_errors: "
                + "; ".join(snapshot.fetch_errors)
            )
        db.commit()
        return

    system_prompt = _system_prompt()
    user_prompt = _build_user_prompt(
        company_name=row.company_name,
        domain=domain,
        linkedin=linkedin,
        raw_input_notes=notes,
        website_text=website_text,
        search_text=search_text,
    )
    payload = _call_llm(
        client,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=_model_name(),
    )

    if snapshot and snapshot.fetch_errors:
        payload.setdefault("_meta", {})["fetch_errors"] = snapshot.fetch_errors
    payload.setdefault("_meta", {})["web_search_used"] = web_search_used
    _apply_enrichment_to_row(row, enriched=payload, web_search_used=web_search_used)
    db.commit()


def _safe_json(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
