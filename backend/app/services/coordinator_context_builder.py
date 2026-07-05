"""AIQ-1414 Phase 1 — read-only Mobility Coordinator context builder.

Assembles a **bounded, PII-masked snapshot** of a single relocation's current state
for the (future) persistent Mobility Coordinator agent. This is the read-only half of
the Option-B "the memory is Postgres" design: instead of maintaining conversational
history in an accruing server session, the coordinator re-reads authoritative Postgres
state each turn via this builder.

Scope of Phase 1 (deliberately narrow — see docs/ai/AIQ-1414_mobility_coordinator_design.md):
- READ-ONLY. No LLM call, no writes, no schema. Nothing in production calls this yet.
- Gated behind ``RELOPASS_AI_COORDINATOR_ENABLED`` (``resolve_flag``, default **OFF**).
- Reuses ``case_context_service.fetch_case_context`` (deterministic, "no AI") for the
  state snapshot and ``pii_masker.mask_pii`` for GDPR Art. 28/44 compliance before any
  data could later cross the LLM trust boundary.

Deferred to Phase 2 (pending the design doc's §12 open question): the **event spine**
(``case_events`` / ``case_notes``) and the rolling summary. Those tables key on the
HR-surface case id, whereas ``CaseContextService`` anchors on ``mobility_cases.id`` —
wiring them before the case-id anchor is reconciled would query the wrong id space and
return silently-empty results. ``recent_events`` / ``rolling_summary`` are therefore
present as empty, clearly-marked slots rather than guessed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .case_context_service import fetch_case_context
from .feature_flags import resolve_flag
from .pii_masker import mask_pii

FLAG_KEY = "RELOPASS_AI_COORDINATOR_ENABLED"

# Bounds — keep the context O(constant) so per-interaction token cost stays predictable
# regardless of how large/old a relocation's record grows (the Option-B cost property).
_MAX_PEOPLE = 12
_MAX_DOCUMENTS = 25
_MAX_REQUIREMENTS = 40


def coordinator_enabled(*, db: Optional[object] = None) -> bool:
    """Whether the AI coordinator feature is enabled (DB flag → env → default OFF)."""
    return resolve_flag(FLAG_KEY, env_default=False, db=db)


def build_coordinator_context(
    conn: Any, case_id: Optional[str], *, db: Optional[object] = None
) -> Optional[Dict[str, Any]]:
    """Build the masked, bounded coordinator context for ``case_id``.

    Returns ``None`` when the feature flag is OFF (the caller does nothing) — so this is
    inert in production until the flag is enabled behind the human gate. ``conn`` is a
    SQLAlchemy Connection passed through to ``fetch_case_context``.
    """
    if not coordinator_enabled(db=db):
        return None
    snapshot = fetch_case_context(conn, case_id)
    return shape_and_mask(snapshot)


def shape_and_mask(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Pure transform: a raw CaseContextService snapshot → the bounded, PII-masked
    coordinator context blob. No I/O — unit-testable in isolation.
    """
    meta = snapshot.get("meta") or {}
    case_found = bool(meta.get("case_found"))
    raw_case = snapshot.get("case") or {}

    case: Optional[Dict[str, Any]] = None
    if case_found and raw_case:
        case = {
            # Opaque internal ids / structured codes / dates are non-personal — kept as-is.
            "case_id": _s(raw_case.get("id")),
            "company_id": _s(raw_case.get("company_id")),
            "case_type": _s(raw_case.get("case_type")),
            "origin_country": _s(raw_case.get("origin_country")),
            "destination_country": _s(raw_case.get("destination_country")),
            "created_at": _iso(raw_case.get("created_at")),
            "updated_at": _iso(raw_case.get("updated_at")),
            # metadata jsonb may carry free-text / PII → deep-masked.
            "details": _mask_value(raw_case.get("metadata")),
        }

    people: List[Dict[str, Any]] = [
        {
            "role": _s(p.get("role")),
            # Person names/emails live inside the metadata jsonb → deep-masked.
            "details": _mask_value(p.get("metadata")),
        }
        for p in (snapshot.get("people") or [])[:_MAX_PEOPLE]
    ]

    documents: List[Dict[str, Any]] = [
        {
            "status": _s(d.get("document_status")),
            "key": mask_pii(_s(d.get("document_key")) or ""),
            "details": _mask_value(d.get("metadata")),
        }
        for d in (snapshot.get("documents") or [])[:_MAX_DOCUMENTS]
    ]

    requirements: List[Dict[str, Any]] = [
        {
            "code": _s(e.get("requirement_code")),
            "status": _s(e.get("evaluation_status")),
            "reason": mask_pii(_s(e.get("reason_text")) or ""),
        }
        for e in (snapshot.get("evaluations") or [])[:_MAX_REQUIREMENTS]
    ]

    return {
        "case": case,
        "people": people,
        "documents": documents,
        "requirements": requirements,
        # Phase 2 slots — intentionally empty in Phase 1 (see module docstring / design §12).
        "rolling_summary": "",
        "recent_events": [],
        "_meta": {
            "case_found": case_found,
            "source": "case_context_service",
            "pii_masked": True,
            "event_spine": "deferred_phase2",
            "counts": {
                "people": len(people),
                "documents": len(documents),
                "requirements": len(requirements),
            },
        },
    }


# ── helpers ──────────────────────────────────────────────────────────────────


def _s(v: Any) -> Optional[str]:
    return None if v is None else str(v)


def _iso(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def _mask_value(v: Any) -> Any:
    """Recursively mask every string leaf in a (possibly nested) jsonb value.

    Masks values only, never keys. Numbers/bools/None pass through. A metadata blob
    that arrives as a raw JSON string is masked as a whole string (safe direction).
    """
    if v is None:
        return None
    if isinstance(v, str):
        return mask_pii(v)
    if isinstance(v, dict):
        return {k: _mask_value(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_mask_value(x) for x in v]
    return v
