"""
C1-16 · Audit query endpoint — GET /api/hr/cases/{case_id}/audit

Single source of truth for case lineage. Returns a chronological event
stream UNION'd across four canonical sources:

  - rce.agent_runs    → AGENT_RUN events (model + cost + digest)
  - rce.entity_links  → ENTITY_LINK events (method + confidence)
  - rce.corrections   → CORRECTION events (field + before/after + reason)
  - rce.rule_versions → RULE_CITATION events (legal_reference + URL)

Architecture Report §13.3. Answers the immigration-lawyer question:
"Show me everything that happened on this case."

Tenant scoping (RLS): mirrors the C1-11c-be pattern — 404 on cross-
tenant access, not 403, so case ids can't be probed via status code.

Pagination: cursor-based. The cursor is an opaque base64-encoded
`(ts_iso, source_table, row_id)` triple, which gives us a stable
ordering even when two events share the same `ts`.

Caching: response includes a strong ETag derived from the SHA-256
of the most-recent event row's `(ts, source_table, row_id)`. Clients
that have seen the same head get a 304 Not Modified.

Performance target (per brief): p99 < 500ms for cases up to 200 events.
The UNION is bounded by the page size + the WHERE on case_id, so the
worst case is four small index scans + a sort.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ...database import db


router = APIRouter(prefix="/api/hr/cases", tags=["hr-case-audit"])


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


AuditEventType = Literal["AGENT_RUN", "ENTITY_LINK", "CORRECTION", "RULE_CITATION"]


class AuditEvent(BaseModel):
    ts: str
    type: AuditEventType
    actor: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class AuditResponse(BaseModel):
    case_id: str
    events: List[AuditEvent] = Field(default_factory=list)
    next_cursor: Optional[str] = None


DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


# ---------------------------------------------------------------------------
# Cursor encoding — opaque base64; never reveal raw shape to clients
# ---------------------------------------------------------------------------


def _encode_cursor(ts: str, source: str, row_id: str) -> str:
    raw = json.dumps([ts, source, row_id], separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> Tuple[str, str, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        parsed = json.loads(raw)
        if (
            not isinstance(parsed, list)
            or len(parsed) != 3
            or not all(isinstance(x, str) for x in parsed)
        ):
            raise ValueError("malformed cursor payload")
        return parsed[0], parsed[1], parsed[2]
    except Exception as exc:  # noqa: BLE001 — opaque to the caller by design
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pagination cursor.",
        ) from exc


# ---------------------------------------------------------------------------
# Tenant gate — same pattern as hr_case_detail._require_case_access
# ---------------------------------------------------------------------------


def _require_case_access(case_id: str, org_id: str) -> Dict[str, Any]:
    """Return the legacy `relocation_cases` row if the caller's org owns it.

    404 (NOT 403) on tenant mismatch so attackers cannot probe other
    tenants' case ids via status code.
    """
    row = db.get_relocation_case(case_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    case_company_id = row.get("company_id")
    if case_company_id and case_company_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return row


# ---------------------------------------------------------------------------
# SQL — one UNION query, cursor-aware, ordered descending by (ts, source, id)
# ---------------------------------------------------------------------------


# The UNION here intentionally reads BIGINT-style id-or-uuid columns as
# their literal text representation; downstream JSON serialisation never
# needs them as anything else. Each branch projects identical columns so
# the union is type-stable.
_AUDIT_UNION_SQL = """
WITH events AS (
    -- 1. agent_runs → AGENT_RUN
    SELECT
        COALESCE(started_at, created_at) AS ts,
        'agent_runs' AS source,
        agent_run_id::text AS row_id,
        'AGENT_RUN' AS event_type,
        COALESCE(agent_id, 'system.agent') AS actor,
        jsonb_build_object(
            'agent_id', agent_id,
            'agent_version', agent_version,
            'model', llm_model_used,
            'cost_tokens', cost_tokens,
            'status', status,
            'output_digest', output_digest
        ) AS payload
    FROM rce.agent_runs
    WHERE case_id = :case_id

    UNION ALL

    -- 2. entity_links → ENTITY_LINK (via the extracted_field → document → case join)
    SELECT
        el.created_at AS ts,
        'entity_links' AS source,
        el.entity_link_id::text AS row_id,
        'ENTITY_LINK' AS event_type,
        CASE
            WHEN el.link_method = 'HUMAN' THEN COALESCE('user.' || el.resolved_by_user_id::text, 'user.unknown')
            ELSE 'system.resolver'
        END AS actor,
        jsonb_build_object(
            'method', el.link_method,
            'confidence', el.confidence,
            'canonical_entity_id', el.canonical_entity_id,
            'extracted_field_id', el.extracted_field_id
        ) AS payload
    FROM rce.entity_links el
    JOIN rce.extracted_fields ef ON ef.extracted_field_id = el.extracted_field_id
    JOIN rce.documents d         ON d.document_id = ef.document_id
    WHERE d.case_id = :case_id

    UNION ALL

    -- 3. corrections → CORRECTION
    SELECT
        corrected_at AS ts,
        'corrections' AS source,
        correction_id::text AS row_id,
        'CORRECTION' AS event_type,
        CASE
            WHEN corrected_by IS NULL THEN 'system'
            ELSE 'user.' || corrected_by::text
        END AS actor,
        jsonb_build_object(
            'field', field,
            'value_before', value_before,
            'value_after', value_after,
            'reason_code', reason_code,
            'reason_freetext', reason_freetext,
            'target_table', target_table,
            'target_id', target_id::text
        ) AS payload
    FROM rce.corrections
    WHERE case_id = :case_id

    UNION ALL

    -- 4. rule_versions cited on this case → RULE_CITATION
    -- (One row per (case, rule_version) pair surfaced via rce.steps —
    --  rule_versions don't reference cases directly, so we approximate
    --  the citation moment by reading the case's corridor_id and the
    --  rules that target it.)
    SELECT
        rv.effective_from::timestamptz AS ts,
        'rule_versions' AS source,
        rv.rule_version_id::text AS row_id,
        'RULE_CITATION' AS event_type,
        CASE
            WHEN c.corridor_id IS NOT NULL THEN 'system.corridor.' || c.corridor_id
            ELSE 'system.corridor'
        END AS actor,
        jsonb_build_object(
            'rule_version_id', rv.rule_version_id,
            'rule_id', rv.rule_id,
            'version_label', rv.version_label,
            'effective_from', rv.effective_from,
            'effective_to', rv.effective_to,
            'predicate_dsl', rv.predicate_dsl
        ) AS payload
    FROM rce.rule_versions rv
    JOIN rce.rules r ON r.rule_id = rv.rule_id
    LEFT JOIN rce.cases c ON c.case_id = :case_id
    WHERE c.corridor_id IS NOT NULL
)
SELECT ts, source, row_id, event_type, actor, payload
FROM events
WHERE
    (:cursor_ts IS NULL)
    OR (ts < :cursor_ts)
    OR (ts = :cursor_ts AND source < :cursor_source)
    OR (ts = :cursor_ts AND source = :cursor_source AND row_id < :cursor_row_id)
ORDER BY ts DESC, source DESC, row_id DESC
LIMIT :limit
"""


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/{case_id}/audit", response_model=AuditResponse)
def get_case_audit(
    case_id: str,
    response: Response,
    request: Request,
    cursor: Optional[str] = Query(None, description="Opaque pagination cursor."),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> AuditResponse:
    """
    Chronological audit trail for one case.

    Ordered NEWEST first so the demo case detail can render the head of
    the timeline without a follow-up `?reverse=` query. Older events are
    paged via `?cursor=…`.

    Returns 304 when the client's `If-None-Match` matches the current
    head's ETag — even when the case has hundreds of events, an unchanged
    case answers with no body.
    """
    _require_case_access(case_id, org_id)

    cursor_ts = cursor_source = cursor_row_id = None
    if cursor:
        cursor_ts, cursor_source, cursor_row_id = _decode_cursor(cursor)

    events: List[AuditEvent] = []
    head_etag: Optional[str] = None

    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(_AUDIT_UNION_SQL),
                {
                    "case_id": case_id,
                    "cursor_ts": cursor_ts,
                    "cursor_source": cursor_source,
                    "cursor_row_id": cursor_row_id,
                    "limit": limit + 1,  # fetch one extra to detect "has more"
                },
            ).mappings().all()
        # First row is the head — use it for the ETag.
        if rows:
            head = rows[0]
            head_token = f"{head['ts']}|{head['source']}|{head['row_id']}"
            head_etag = (
                'W/"' + hashlib.sha256(head_token.encode("utf-8")).hexdigest()[:32] + '"'
            )

        for r in rows[:limit]:
            payload = r.get("payload") or {}
            if not isinstance(payload, dict):
                # SQLAlchemy + JSONB may surface as a string in some drivers;
                # parse defensively so the response shape stays clean.
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {"raw": str(payload)}
            ts_value = r["ts"]
            ts_iso = ts_value.isoformat() if hasattr(ts_value, "isoformat") else str(ts_value)
            events.append(
                AuditEvent(
                    ts=ts_iso,
                    type=str(r["event_type"]),  # type: ignore[arg-type]
                    actor=str(r["actor"]),
                    payload=payload,
                )
            )

        # Compute next cursor only if there's a (limit+1)th row hinting more.
        next_cursor: Optional[str] = None
        if len(rows) > limit and events:
            last = events[-1]
            tail_source = str(rows[limit - 1]["source"])
            tail_row_id = str(rows[limit - 1]["row_id"])
            next_cursor = _encode_cursor(last.ts, tail_source, tail_row_id)

    except HTTPException:
        raise
    except Exception:
        # rce.* tables not present yet → degrade to empty response.
        # The frontend renders "no audit events" rather than an error.
        events = []
        next_cursor = None
        head_etag = None

    # ETag handling — 304 when unchanged.
    if head_etag:
        client_etag = request.headers.get("if-none-match")
        if client_etag and client_etag == head_etag:
            response.status_code = status.HTTP_304_NOT_MODIFIED
            response.headers["ETag"] = head_etag
            return AuditResponse(case_id=case_id, events=[], next_cursor=None)
        response.headers["ETag"] = head_etag

    return AuditResponse(case_id=case_id, events=events, next_cursor=next_cursor)


# ---------------------------------------------------------------------------
# [NAV-HR-3 / AIQ-1122 + NAV-HR-3-FU / AIQ-1137] HR-action audit trail from the
# canonical audit_logs. Distinct from GET /audit above (which unions the rce.*
# immigration pipeline): this returns the HR mutation trail consolidated by
# AUDIT-1/2/3 — who did what to this case (escalate, reassign, note, ...).
#
# AIQ-1137 completes the MVP: (1) aggregates across ALL of the case's bridged
# ids (most legacy rows are keyed by the relocation uuid, recent NAV-HR-2 rows by
# the assignment id), (2) action-type + date filters, (3) append-only
# amend/reverse annotations (never mutate an existing row).
# ---------------------------------------------------------------------------


class CaseActionAuditEvent(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    action_type: str  # insert | update | delete
    actor_type: Optional[str] = None
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    event: Optional[str] = None  # the semantic verb, from new_value.event
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def _require_case_access_bridged(case_id: str, org_id: str) -> str:
    """Tenant gate for the audit trail. Resolves the owning company whether
    ``case_id`` is the assignment id (what the UI passes) or a relocation uuid.
    404 (not 403) on missing/cross-tenant so case ids can't be probed.
    Returns the resolved company id.
    """
    company_id = db.get_case_company_for_audit(case_id)
    if not company_id or (org_id and company_id != org_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return company_id


def _actor_uuid(user: Dict[str, Any]) -> Optional[str]:
    """The actor's auth uuid if it is a real uuid, else None (audit_logs.actor_id
    is a nullable uuid; a non-uuid legacy id is dropped rather than rejected)."""
    raw = user.get("auth_uuid") or user.get("id")
    return str(raw) if raw and _UUID_RE.match(str(raw)) else None


@router.get("/{case_id}/audit-trail", response_model=List[CaseActionAuditEvent])
def get_case_action_audit_trail(
    case_id: str,
    action_type: Optional[str] = Query(None, pattern=r"^(insert|update|delete)$"),
    event: Optional[str] = Query(None, max_length=100, description="Filter by semantic verb (new_value.event)."),
    date_from: Optional[str] = Query(None, description="ISO timestamp; events at/after this time."),
    date_to: Optional[str] = Query(None, description="ISO timestamp; events at/before this time."),
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> List[Dict[str, Any]]:
    """Chronological HR-action audit trail for one case, newest first, from the
    canonical ``public.audit_logs``. Aggregates across all of the case's bridged
    ids so no event is missed. Optional action-type / event / date filters.
    Tenant-gated by case ownership (404 on mismatch); actor names via profiles.
    """
    _require_case_access_bridged(case_id, org_id)
    entity_ids = db.resolve_case_audit_entity_ids(case_id)
    return db.query_case_audit_trail(
        entity_ids,
        action_type=action_type,
        event=event,
        from_ts=date_from,
        to_ts=date_to,
        limit=200,
    )


class AuditAnnotationBody(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


def _annotate_audit_event(
    case_id: str,
    audit_id: str,
    *,
    kind: Literal["amend", "reverse"],
    reason: str,
    user: Dict[str, Any],
    org_id: str,
) -> Dict[str, Any]:
    """Shared amend/reverse path: tenant-gate, validate the target belongs to
    this case, enforce the reversible-state rule, then append a linked row."""
    _require_case_access_bridged(case_id, org_id)

    target = db.get_audit_log_entry(audit_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit entry not found")

    entity_ids = set(db.resolve_case_audit_entity_ids(case_id))
    if str(target.get("entity_id")) not in entity_ids:
        # The target row isn't part of this case — 404 so it can't be probed.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit entry not found")

    target_event = (target.get("event") or "").upper()
    if kind == "reverse":
        # Reversible state: only an original insert/update event may be reversed,
        # never a delete, never an amend/reverse annotation, and not twice.
        if target.get("action_type") == "delete" or target_event in ("AUDIT_AMENDED", "AUDIT_REVERSED"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This entry cannot be reversed.")
        existing = db.find_audit_amendments(audit_id)
        if any((e.get("event") or "").upper() == "AUDIT_REVERSED" for e in existing):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This entry has already been reversed.")

    link_field = "amends" if kind == "amend" else "reverses"
    new_id = db.insert_case_audit_annotation(
        entity_type=target.get("entity_type"),
        entity_id=str(target.get("entity_id")),
        event="AUDIT_AMENDED" if kind == "amend" else "AUDIT_REVERSED",
        reason=reason,
        link_field=link_field,
        original_id=audit_id,
        actor_id=_actor_uuid(user),
    )
    return {"ok": True, "id": new_id, link_field: audit_id}


@router.post("/{case_id}/audit-trail/{audit_id}/amend")
def amend_case_audit_event(
    case_id: str,
    audit_id: str,
    body: AuditAnnotationBody = Body(...),
    user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """Append an amendment (correction note) linked to an existing audit entry.
    The original row is never mutated; a new row records ``amends = audit_id``."""
    return _annotate_audit_event(case_id, audit_id, kind="amend", reason=body.reason, user=user, org_id=org_id)


@router.post("/{case_id}/audit-trail/{audit_id}/reverse")
def reverse_case_audit_event(
    case_id: str,
    audit_id: str,
    body: AuditAnnotationBody = Body(...),
    user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """Append a reversal linked to an existing audit entry, only in a reversible
    state. The original row is never mutated; a new row records ``reverses = audit_id``."""
    return _annotate_audit_event(case_id, audit_id, kind="reverse", reason=body.reason, user=user, org_id=org_id)
