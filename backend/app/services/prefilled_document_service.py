"""
[AIQ-1758] Register a reviewed prefilled data-sheet as a durable case artifact.
============================================================================
On employee/HR confirmation, this:
  1. snapshots the CaseForm's reviewed field values into a fill report,
  2. stores a JSON artifact of the snapshot in the `case-documents` bucket
     (fail-soft — dev/test has no Storage),
  3. inserts a `case_form_documents` row (doc_kind='prefilled', fill_report),
  4. writes an audit_logs entry using the prefill convention
     (entity_type='case_form', new_value.event='prefill'),
  5. advances the CaseForm status per the existing state machine.

Reuses the ad-hoc registration pattern (`case_forms_adhoc.py`) and the prefill
audit convention (`prefill_engine._insert_prefill_audit`). Written with pure
SQLAlchemy `text()` + the `_t()` dialect helper (like `prefill_engine`) so it is
unit-testable on SQLite.

PII discipline (CLAUDE.md): the fill-report COLUMN holds only status/source/
confidence per field (never the raw value); the full snapshot WITH values lives
in the RLS-scoped, signed-URL storage artifact. Raw values are never logged.
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ...database import db
from .audit_log_service import ACTION_INSERT, ACTOR_SYSTEM, insert_audit_log

logger = logging.getLogger(__name__)

_BUCKET = "case-documents"

# Statuses from which registering the reviewed sheet advances to 'ready'.
# Never downgrade a form already submitted/approved/rejected.
_ADVANCEABLE = ("not_started", "auto_filled", "in_progress", "pending_doc")

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


# ---------------------------------------------------------------------------
# Dialect helpers (mirror prefill_engine._t / _now)
# ---------------------------------------------------------------------------

def _dialect() -> str:
    try:
        return db.engine.dialect.name
    except Exception:
        return "postgresql"


def _t(name: str) -> str:
    return f"public.{name}" if _dialect() == "postgresql" else name


def _now() -> str:
    return "now()" if _dialect() == "postgresql" else "CURRENT_TIMESTAMP"


def _jsonb_param(name: str) -> str:
    """Bind expression for a JSON column: ::jsonb cast on Postgres, plain on SQLite."""
    return f":{name}::jsonb" if _dialect() == "postgresql" else f":{name}"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def register_prefilled_document(
    case_id: str,
    form_id: str,
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Register the reviewed prefilled data-sheet for one CaseForm.

    Returns {document_id, storage_path, status, field_count}.
    Raises ValueError if the CaseForm does not exist for this case.
    """
    form = _load_form(form_id, case_id)
    if not form:
        raise ValueError("case_form not found")

    fields = _parse_json(form.get("fields"))
    values = _load_field_values(form_id)

    # Two views of the reviewed sheet:
    #  - report_meta: status/source/confidence per field → the fill_report COLUMN
    #    (no raw values, keeps PII out of a second DB location).
    #  - snapshot: the full sheet WITH values → the storage artifact.
    report_meta, snapshot_fields = _build_fill_report(fields, values)

    ts = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    snapshot = {
        "case_form_id": form_id,
        "case_id": case_id,
        "generated_at": _dt.datetime.utcnow().isoformat() + "Z",
        "fields": snapshot_fields,
    }
    payload = json.dumps(snapshot, ensure_ascii=False).encode("utf-8")
    storage_path = f"{case_id}/prefilled/{form_id}/{ts}.json"
    _upload_snapshot(storage_path, payload)  # fail-soft

    document_id = str(uuid.uuid4())
    code = form.get("code") or "form"
    file_name = f"{code}-datasheet-{ts}.json"

    _insert_document(
        document_id=document_id,
        case_form_id=form_id,
        case_id=case_id,
        file_name=file_name,
        storage_path=storage_path,
        size_bytes=len(payload),
        uploaded_by=_actor_uuid(actor_id),
        fill_report=report_meta,
    )
    _write_audit(form_id, document_id, len(report_meta))
    new_status = _advance_status(form_id)

    logger.info(
        "register_prefilled_document: registered doc=%s cf=%s fields=%d status=%s",
        document_id, form_id, len(report_meta), new_status,
    )
    return {
        "document_id": document_id,
        "storage_path": storage_path,
        "status": new_status,
        "field_count": len(report_meta),
    }


# ---------------------------------------------------------------------------
# Fill report
# ---------------------------------------------------------------------------

def _build_fill_report(
    fields: List[Dict[str, Any]],
    values: Dict[str, Dict[str, Any]],
) -> tuple:
    """Return (report_meta, snapshot_fields).

    status ∈ {'consult', 'filled', 'blank_missing_data'}:
      - consult_professional fields are never pre-filled → 'consult', no value.
      - a field with a non-empty value → 'filled'.
      - everything else → 'blank_missing_data' (never invented).
    """
    report_meta: List[Dict[str, Any]] = []
    snapshot_fields: List[Dict[str, Any]] = []
    for f in fields:
        fid = f.get("id") or f.get("field_id")
        if not fid:
            continue
        label = f.get("label")
        if f.get("consult_professional"):
            status, value, source, conf = "consult", None, None, None
        else:
            vrow = values.get(fid) or {}
            value = vrow.get("value")
            source = vrow.get("source")
            conf = vrow.get("ai_confidence")
            status = "filled" if (value is not None and str(value).strip() != "") else "blank_missing_data"
        report_meta.append({
            "field_id": fid, "label": label, "status": status,
            "source": source, "confidence": conf,
        })
        snapshot_fields.append({
            "field_id": fid, "label": label, "value": value, "status": status,
            "source": source, "confidence": conf,
        })
    return report_meta, snapshot_fields


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _load_form(form_id: str, case_id: str) -> Optional[Dict[str, Any]]:
    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT cf.id, cf.status, ft.code, ft.fields "
                    f"FROM {_t('case_forms')} cf "
                    f"LEFT JOIN {_t('form_templates')} ft ON ft.id = cf.form_template_id "
                    f"WHERE cf.id = :fid AND cf.case_id = :cid"
                ),
                {"fid": form_id, "cid": case_id},
            ).mappings().first()
        return dict(row) if row else None
    except Exception:
        logger.exception("register: failed to load case_form %s", form_id)
        return None


def _load_field_values(form_id: str) -> Dict[str, Dict[str, Any]]:
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT field_id, value, source, ai_confidence "
                    f"FROM {_t('case_form_field_values')} WHERE case_form_id = :fid"
                ),
                {"fid": form_id},
            ).mappings().all()
        return {r["field_id"]: dict(r) for r in rows}
    except Exception:
        logger.exception("register: failed to load field values cf=%s", form_id)
        return {}


# ---------------------------------------------------------------------------
# Storage (fail-soft)
# ---------------------------------------------------------------------------

def _upload_snapshot(storage_path: str, payload: bytes) -> bool:
    """Upload the snapshot JSON to Storage. Returns False when Storage is
    unavailable (dev/test) — the DB row is still created so the artifact is
    tracked and can be re-materialised."""
    try:
        from .supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()
        sb.storage.from_(_BUCKET).upload(
            storage_path,
            payload,
            {"content-type": "application/json", "upsert": "true"},
        )
        return True
    except Exception:
        logger.warning("register: snapshot storage upload skipped (unavailable)")
        return False


# ---------------------------------------------------------------------------
# DB writes
# ---------------------------------------------------------------------------

def _insert_document(
    document_id: str,
    case_form_id: str,
    case_id: str,
    file_name: str,
    storage_path: str,
    size_bytes: int,
    uploaded_by: Optional[str],
    fill_report: List[Dict[str, Any]],
) -> None:
    with db.engine.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO {_t('case_form_documents')} "
                f"  (id, case_form_id, case_id, file_name, storage_path, content_type, "
                f"   size_bytes, uploaded_by, doc_kind, fill_report) "
                f"VALUES (:id, :cfid, :cid, :fname, :path, 'application/json', "
                f"        :size, :by, 'prefilled', {_jsonb_param('report')})"
            ),
            {
                "id": document_id,
                "cfid": case_form_id,
                "cid": case_id,
                "fname": file_name,
                "path": storage_path,
                "size": size_bytes,
                "by": uploaded_by,
                "report": json.dumps(fill_report, ensure_ascii=False),
            },
        )


def _write_audit(case_form_id: str, document_id: str, field_count: int) -> None:
    """Prefill-convention audit event (fail-soft — never blocks registration)."""
    try:
        with db.engine.begin() as conn:
            insert_audit_log(
                conn,
                entity_type="case_form",
                entity_id=case_form_id,
                action_type=ACTION_INSERT,
                actor_type=ACTOR_SYSTEM,
                new_value={
                    "event": "prefill",
                    "kind": "register",
                    "document_id": document_id,
                    "field_count": field_count,
                },
            )
    except Exception:
        logger.exception("register: audit write failed cf=%s", case_form_id)


def _advance_status(case_form_id: str) -> str:
    """Advance to 'ready' from an advanceable state; never downgrade a form that
    is already submitted/approved/rejected. Returns the resulting status."""
    try:
        placeholders = ", ".join(f"'{s}'" for s in _ADVANCEABLE)
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    f"UPDATE {_t('case_forms')} "
                    f"SET status = 'ready', updated_at = {_now()} "
                    f"WHERE id = :id AND status IN ({placeholders})"
                ),
                {"id": case_form_id},
            )
            row = conn.execute(
                text(f"SELECT status FROM {_t('case_forms')} WHERE id = :id"),
                {"id": case_form_id},
            ).first()
        return str(row[0]) if row else "ready"
    except Exception:
        logger.exception("register: status advance failed cf=%s", case_form_id)
        return "unknown"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _actor_uuid(actor_id: Optional[str]) -> Optional[str]:
    """uploaded_by is uuid-typed; return actor_id only when uuid-shaped, else None
    (nullable) — a non-uuid legacy id would otherwise fail the cast."""
    s = str(actor_id) if actor_id else ""
    return s if _UUID_RE.match(s) else None


def _parse_json(value: Any) -> Any:
    if value is None:
        return []
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    return []
