"""AIQ-1414 Phase 1–2a — read-only Mobility Coordinator context builder.

Assembles a **bounded, PII-masked snapshot** of a single relocation's current state
for the (future) persistent Mobility Coordinator agent. This is the read-only half of
the Option-B "the memory is Postgres" design: instead of maintaining conversational
history in an accruing server session, the coordinator re-reads authoritative Postgres
state each turn via this builder.

Scope (see docs/ai/AIQ-1414_mobility_coordinator_design.md):
- READ-ONLY. No LLM call, no writes, no schema. Nothing in production calls this yet.
- Gated behind ``RELOPASS_AI_COORDINATOR_ENABLED`` (``resolve_flag``, default **OFF**).
- Reuses ``case_context_service.fetch_case_context`` for the state snapshot and
  ``pii_masker.mask_pii`` for GDPR Art. 28/44 compliance before any data could later
  cross the LLM trust boundary.

Anchor (design §12, resolved): the coordinator anchors on the **HR-surface case id**
(``relocation_cases``/``wizard_cases`` family, also on ``case_assignments.case_id`` /
``canonical_case_id``). Because ``CaseContextService`` anchors on ``mobility_cases.id``
and the event spine keys on the HR-surface id, ``build_coordinator_context_for_case``
reconciles the two using the existing resolver chain:

    HR case_id → db.get_assignment_by_case_id → assignment["id"]
              → db.get_mobility_case_id_for_assignment (assignment_mobility_links, 1:1)
              → fetch_case_context(conn, mobility_case_id)     [current state]
    HR case_id → db.list_case_events + case_notes              [event spine]

Reads run as the service role (``db.engine`` bypasses RLS), so notes are scoped by
company at the app layer here; the Phase-2b endpoint enforces caller auth/company scope.
Phase-2b adds the rolling summary (``rolling_summary`` is an empty slot until then).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .case_context_service import fetch_case_context
from .feature_flags import resolve_flag
from .pii_masker import mask_pii

log = logging.getLogger(__name__)

FLAG_KEY = "RELOPASS_AI_COORDINATOR_ENABLED"

# Bounds — keep the context O(constant) so per-interaction token cost stays predictable
# regardless of how large/old a relocation's record grows (the Option-B cost property).
_MAX_PEOPLE = 12
_MAX_DOCUMENTS = 25
_MAX_REQUIREMENTS = 40
_MAX_EVENTS = 30
_MAX_NOTES = 15


def coordinator_enabled(*, db: Optional[object] = None) -> bool:
    """Whether the AI coordinator feature is enabled (DB flag → env → default OFF)."""
    return resolve_flag(FLAG_KEY, env_default=False, db=db)


def build_coordinator_context_for_case(
    case_id: Optional[str], *, db: Optional[object] = None
) -> Optional[Dict[str, Any]]:
    """HR-surface entrypoint — the canonical way to build coordinator context.

    Resolves ``case_id`` (HR-surface) through the assignment → mobility-case chain, then
    assembles current state (``CaseContextService``) + the event spine (``case_events`` +
    ``case_notes``) into one bounded, PII-masked blob.

    Returns ``None`` only when the feature flag is OFF (so the feature is inert in prod).
    When the case/assignment can't be resolved it returns a shaped blob with
    ``_meta.case_found = False`` and a ``_meta.reason`` — distinguishable from flag-off.
    """
    if not coordinator_enabled(db=db):
        return None

    mdb = _get_db()
    assignment = _resolve_assignment(mdb, case_id)
    if not assignment:
        return _shaped_not_found(case_id, "assignment_not_found")

    assignment_id = _s(assignment.get("id"))
    company_id = _s(assignment.get("company_id"))
    mobility_case_id = (
        mdb.get_mobility_case_id_for_assignment(assignment_id) if assignment_id else None
    )

    snapshot: Dict[str, Any] = _empty_snapshot()
    notes: List[Dict[str, Any]] = []
    try:
        with mdb.engine.connect() as conn:
            if mobility_case_id:
                snapshot = fetch_case_context(conn, mobility_case_id)
            notes = _fetch_notes(conn, case_id, company_id)
    except Exception as exc:  # noqa: BLE001 — best-effort; never fail context assembly
        log.warning("coordinator context: state/notes read failed for case %s: %s", case_id, exc)

    try:
        events = _get_db().list_case_events(case_id) or []
    except Exception as exc:  # noqa: BLE001
        log.warning("coordinator context: list_case_events failed for case %s: %s", case_id, exc)
        events = []

    ctx = shape_and_mask(snapshot, events=events, notes=notes)
    ctx["_meta"].update(
        {
            "hr_case_id": _s(case_id),
            "assignment_id": assignment_id,
            "mobility_case_id": _s(mobility_case_id),
            "mobility_linked": bool(mobility_case_id),
        }
    )
    return ctx


def build_coordinator_context(
    conn: Any, mobility_case_id: Optional[str], *, db: Optional[object] = None
) -> Optional[Dict[str, Any]]:
    """Low-level builder: shape the state snapshot for an already-resolved
    ``mobility_cases.id`` (no event spine). Prefer ``build_coordinator_context_for_case``
    for the HR-surface flow. Returns ``None`` when the flag is OFF.
    """
    if not coordinator_enabled(db=db):
        return None
    snapshot = fetch_case_context(conn, mobility_case_id)
    return shape_and_mask(snapshot)


def shape_and_mask(
    snapshot: Dict[str, Any],
    *,
    events: Optional[List[Dict[str, Any]]] = None,
    notes: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Pure transform: raw CaseContextService snapshot (+ optional event spine) → the
    bounded, PII-masked coordinator context blob. No I/O — unit-testable in isolation.
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

    spine_provided = events is not None or notes is not None
    recent_events = _shape_events(events, notes)

    return {
        "case": case,
        "people": people,
        "documents": documents,
        "requirements": requirements,
        "recent_events": recent_events,
        # rolling_summary is populated in Phase 2b (LLM fold) — empty slot until then.
        "rolling_summary": "",
        "_meta": {
            "case_found": case_found,
            "source": "case_context_service",
            "pii_masked": True,
            "event_spine": "wired" if spine_provided else "none",
            "counts": {
                "people": len(people),
                "documents": len(documents),
                "requirements": len(requirements),
                "recent_events": len(recent_events),
            },
        },
    }


# ── event spine ──────────────────────────────────────────────────────────────


def _shape_events(
    events: Optional[List[Dict[str, Any]]], notes: Optional[List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """Merge case_events + case_notes into one masked, bounded, newest-first activity
    list. Free-text (``description``/``body``/``author_name``) and ``payload`` jsonb are
    masked; structured fields (``event_type``, timestamps) are kept.
    """
    items: List[Dict[str, Any]] = []
    for e in (events or [])[:_MAX_EVENTS]:
        items.append(
            {
                "kind": "event",
                "at": _iso(e.get("created_at")),
                "type": _s(e.get("event_type")),
                "actor": _s(e.get("actor_principal_id")) or _s(e.get("actor_user_id")),
                "description": mask_pii(_s(e.get("description")) or ""),
                "payload": _mask_value(e.get("payload")),
            }
        )
    for n in (notes or [])[:_MAX_NOTES]:
        items.append(
            {
                "kind": "note",
                "at": _iso(n.get("created_at")),
                "author": mask_pii(_s(n.get("author_name")) or ""),
                "body": mask_pii(_s(n.get("body")) or ""),
            }
        )
    items.sort(key=lambda x: x.get("at") or "", reverse=True)
    return items[:_MAX_EVENTS]


def _fetch_notes(
    conn: Any, case_id: Optional[str], company_id: Optional[str], *, limit: int = _MAX_NOTES
) -> List[Dict[str, Any]]:
    """Company-scoped, best-effort read of recent case_notes for an HR-surface case."""
    from sqlalchemy import text

    try:
        rows = (
            conn.execute(
                text(
                    "SELECT author_name, body, created_at FROM case_notes "
                    "WHERE case_id = :cid "
                    "AND (:org IS NULL OR company_id = :org OR company_id IS NULL) "
                    "ORDER BY created_at DESC, id DESC LIMIT :lim"
                ),
                {"cid": _s(case_id), "org": company_id, "lim": int(limit)},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]
    except Exception as exc:  # noqa: BLE001 — notes are best-effort; never fail context build
        log.warning("coordinator context: case_notes read failed for %s: %s", case_id, exc)
        return []


# ── helpers ──────────────────────────────────────────────────────────────────


def _get_db():
    """Lazy accessor for the shared DB singleton (indirection for testability)."""
    from ...database import db as main_db

    return main_db


def _resolve_assignment(mdb: Any, case_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """HR case_id → case_assignments row, mirroring routers' ``_resolve_assignment``."""
    if case_id is None:
        return None
    return mdb.get_assignment_by_case_id(case_id) or mdb.get_assignment_by_id(case_id)


def _empty_snapshot() -> Dict[str, Any]:
    return {
        "meta": {"ok": True, "case_found": False, "error": None},
        "case": None,
        "people": [],
        "documents": [],
        "evaluations": [],
    }


def _shaped_not_found(case_id: Optional[str], reason: str) -> Dict[str, Any]:
    ctx = shape_and_mask(_empty_snapshot(), events=[], notes=[])
    ctx["_meta"].update({"hr_case_id": _s(case_id), "mobility_linked": False, "reason": reason})
    return ctx


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
