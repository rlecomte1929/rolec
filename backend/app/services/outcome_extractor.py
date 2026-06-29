"""AIQ-685 / P1-07b — outcome_extractor service.

Reads a (closed) case and produces a PII-stripped ``CaseOutcomeData``, then
idempotently persists it to ``public.case_outcomes`` (one row per case).

Design notes (see plan AIQ-685):
- The target table is anonymized BY CONSTRUCTION (no name/email/DOB/user_id).
  "PII stripping" here is therefore mostly *not copying* PII: we map only
  categorical/quantitative fields, and run ``mask_pii()`` belt-and-braces over
  the two free-text columns (``pathway_type``, ``rejection_reason_code``). The
  DB PII-guard trigger is the third line of defence.
- This is deterministic field-mapping, not an LLM call, so the CLAUDE.md
  "mask before the prompt" rule does not apply — but masking still runs.
- Writes go through the ordinary app SessionLocal (DATABASE_URL / owner pool).
  ``case_outcomes`` is service-role-only, so it must NOT be written via the F3
  least-privilege request pool.
- Consent (config-flag gated until P1-07c lands): ``has_outcome_consent`` reads
  ``users.outcome_consent_at`` when that column exists; otherwise it honours the
  ``OUTCOME_EXTRACTION_ENABLED`` env flag; otherwise it fails closed (no write).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import crud, models
from .pii_masker import mask_pii

log = logging.getLogger(__name__)

_TERMINAL_OUTCOMES = {"APPROVED", "REJECTED", "WITHDRAWN", "PENDING"}

# Map a wizard/assignment status to the case_outcomes.outcome enum.
_STATUS_TO_OUTCOME = {
    "approved": "APPROVED",
    "rejected": "REJECTED",
    "withdrawn": "WITHDRAWN",
    "cancelled": "WITHDRAWN",
    "canceled": "WITHDRAWN",
    "closed": "WITHDRAWN",  # closed without an explicit decision
}

# Minimal ISO-3166 normalisation for the live corridors. The column is nullable
# and constrained to ^[A-Z]{2}$, so anything we can't confidently resolve → None.
_ISO3_TO_ISO2 = {
    "FRA": "FR", "NOR": "NO", "DEU": "DE", "IND": "IN", "USA": "US",
    "GBR": "GB", "NLD": "NL", "ESP": "ES", "ITA": "IT", "CHE": "CH",
}
_NAME_TO_ISO2 = {
    "FRANCE": "FR", "NORWAY": "NO", "GERMANY": "DE", "INDIA": "IN",
    "UNITED STATES": "US", "USA": "US", "UNITED KINGDOM": "GB", "UK": "GB",
    "NETHERLANDS": "NL", "SPAIN": "ES", "ITALY": "IT", "SWITZERLAND": "CH",
}


@dataclass
class CaseOutcomeData:
    """Pure compute result — no DB. Every string field is non-PII by design."""

    case_ref_hash: str
    outcome: str
    pathway_type: Optional[str] = None
    origin_country_code: Optional[str] = None
    dest_country_code: Optional[str] = None
    processing_time_days_actual: Optional[int] = None
    rejection_reason_code: Optional[str] = None
    specialist_corrections_count: int = 0
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None


def hash_case_ref(case_id: str) -> str:
    """SHA-256 hex of the real case id — the only (anonymized) link back."""
    return hashlib.sha256(str(case_id).encode("utf-8")).hexdigest()


def _norm_country(value: Any) -> Optional[str]:
    if not value:
        return None
    raw = str(value).strip()
    if len(raw) == 2 and raw.isalpha():
        return raw.upper()
    upper = raw.upper()
    if upper in _ISO3_TO_ISO2:
        return _ISO3_TO_ISO2[upper]
    return _NAME_TO_ISO2.get(upper)


def _map_outcome(status: Optional[str]) -> str:
    return _STATUS_TO_OUTCOME.get((status or "").strip().lower(), "PENDING")


def _parse_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        raw = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None
    return None


def _mask_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    masked = mask_pii(str(value)).strip()
    return masked or None


def _count_specialist_corrections(db: Session, case_id: str) -> int:
    """Best-effort count of specialist correction events for the case.

    Defensive: the table/columns may be absent (SQLite tests) or named
    differently — any failure yields 0 rather than breaking extraction.
    """
    try:
        val = db.execute(
            text("SELECT count(*) FROM specialist_review_events WHERE case_id = :cid"),
            {"cid": case_id},
        ).scalar()
        return int(val or 0)
    except Exception:  # noqa: BLE001 — corrections count is non-critical
        return 0


def extract_outcome_from_case(db: Session, case_id: str) -> CaseOutcomeData:
    """Read a case and compute its anonymized, PII-stripped outcome record.

    Pure: reads + maps + masks. Does NOT write. Raises ValueError if the case
    does not exist.
    """
    case = crud.get_case(db, case_id)
    if case is None:
        raise ValueError(f"case not found: {case_id}")

    flags: Dict[str, Any] = {}
    draft: Dict[str, Any] = {}
    try:
        flags = json.loads(case.flags_json or "{}") or {}
    except (TypeError, ValueError):
        flags = {}
    try:
        draft = json.loads(case.draft_json or "{}") or {}
    except (TypeError, ValueError):
        draft = {}

    outcome = _map_outcome(case.status)

    submitted_at = _parse_dt(flags.get("submitted_at"))
    decided_at = _parse_dt(flags.get("decided_at"))
    # Honour the decided_at >= submitted_at CHECK: drop a value rather than violate it.
    if submitted_at and decided_at and decided_at < submitted_at:
        decided_at = None

    processing_days: Optional[int] = None
    if submitted_at and decided_at:
        delta = (decided_at - submitted_at).days
        processing_days = delta if delta >= 0 else None

    # rejection_reason_code is only meaningful (and only allowed) when REJECTED.
    rejection_reason_code: Optional[str] = None
    if outcome == "REJECTED":
        rejection_reason_code = _mask_or_none(flags.get("rejection_reason_code")) or "UNSPECIFIED"

    pathway_type = _mask_or_none(
        flags.get("pathway_type") or case.purpose or draft.get("purpose")
    )

    return CaseOutcomeData(
        case_ref_hash=hash_case_ref(case_id),
        outcome=outcome,
        pathway_type=pathway_type,
        origin_country_code=_norm_country(case.origin_country or draft.get("originCountry")),
        dest_country_code=_norm_country(case.dest_country or draft.get("destCountry")),
        processing_time_days_actual=processing_days,
        rejection_reason_code=rejection_reason_code,
        specialist_corrections_count=_count_specialist_corrections(db, case_id),
        submitted_at=submitted_at,
        decided_at=decided_at,
    )


def has_outcome_consent(db: Session, case_id: str) -> bool:
    """Consent gate, fail-closed.

    Order of precedence:
      1. If ``users.outcome_consent_at`` exists (P1-07c shipped), the case's
         employee must have a non-null value.
      2. Else if ``OUTCOME_EXTRACTION_ENABLED`` is truthy, allow (internal/test
         data only — pre-launch).
      3. Else deny.
    """
    try:
        val = db.execute(
            text(
                "SELECT outcome_consent_at FROM users u "
                "JOIN wizard_cases c ON c.id = :cid "
                "WHERE u.id = c.owner_user_id"
            ),
            {"cid": case_id},
        ).scalar()
        # Column exists → consent is authoritative.
        return val is not None
    except Exception:  # noqa: BLE001 — column/flow not built yet (P1-07c)
        pass
    return _flag_enabled("OUTCOME_EXTRACTION_ENABLED")


def _flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


def persist_outcome(
    db: Session,
    data: CaseOutcomeData,
    *,
    consent_granted: Optional[bool] = None,
) -> bool:
    """Idempotently upsert one row per case (keyed on case_ref_hash).

    Returns True if a row was written/updated, False if skipped for lack of
    consent. The gate is: ``consent_granted`` when supplied, else the
    ``OUTCOME_EXTRACTION_ENABLED`` env flag (fail-closed). Per-case consent
    (``users.outcome_consent_at``) is resolved upstream in
    ``extract_and_persist`` where the real case_id is known — ``data`` only
    carries the hash, so it cannot be resolved here.

    Portable manual upsert (mirrors crud.upsert_country_profile) so it runs on
    both Postgres (prod) and SQLite (tests); the case_ref_hash UNIQUE constraint
    is the backstop against races.
    """
    allowed = consent_granted if consent_granted is not None else _flag_enabled("OUTCOME_EXTRACTION_ENABLED")
    if not allowed:
        return False

    existing = (
        db.query(models.CaseOutcome)
        .filter(models.CaseOutcome.case_ref_hash == data.case_ref_hash)
        .first()
    )
    payload = dict(
        pathway_type=data.pathway_type,
        origin_country_code=data.origin_country_code,
        dest_country_code=data.dest_country_code,
        outcome=data.outcome,
        processing_time_days_actual=data.processing_time_days_actual,
        rejection_reason_code=data.rejection_reason_code,
        specialist_corrections_count=data.specialist_corrections_count,
        submitted_at=data.submitted_at,
        decided_at=data.decided_at,
    )
    if existing is not None:
        for key, value in payload.items():
            setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        db.commit()
        return True

    row = models.CaseOutcome(id=str(uuid.uuid4()), case_ref_hash=data.case_ref_hash, **payload)
    db.add(row)
    db.commit()
    return True


def extract_and_persist(
    db: Session,
    case_id: str,
    *,
    consent_granted: Optional[bool] = None,
) -> Optional[CaseOutcomeData]:
    """Compute → consent-gate → persist. Returns the data if written, else None.

    When ``consent_granted`` is not supplied, the gate is resolved here from the
    real ``case_id`` (so ``users.outcome_consent_at`` / the env flag can apply).
    """
    data = extract_outcome_from_case(db, case_id)
    if consent_granted is None:
        consent_granted = has_outcome_consent(db, case_id)
    if not consent_granted:
        log.info("outcome_extractor: skipped (no consent) for case %s", str(case_id)[:8])
        return None
    persist_outcome(db, data, consent_granted=True)
    return data
