"""
data_sheet_write_service.py — the Document Data Sheet EDIT path (Phase 2).

Persists a user's edit of a `needs_input` (or correction of a prefilled) data-sheet field, then
returns the freshly-composed sheet. NOT a serving root — this is a mutation.

Two invariants, enforced here on the write side (the read side enforces them too):
  * **Reject consult-professional fields.** A field flagged `consult_professional` (template) or
    `professional_review_required` (fact dictionary) is a regulated determination — writing a
    value is refused (422). The firewall must hold at the write boundary, not just on display.
  * **Keep provenance coherent (AIQ-1755/1756).** A user edit sets `source='manual'`,
    `reviewed=true`, and flips `overridden=true` when it replaces a machine value, so a later
    prefill re-run never clobbers it. Mirrors `cases_write.bulk_update_form_fields`.

`source='manual'` is set explicitly — `bulk_update_form_fields` leaves it NULL, a known gap; the
data sheet needs the provenance to render "you entered this."

Scope (Phase 2): form-local write-back to `case_form_field_values`. Cross-FORM propagation via
the canonical intake store (`cases.intake_data`) is the deliberate fast-follow — the sanctioned
intake writer is a heavy wizard-patch, so a safe single-field intake writer lands on its own.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import text as _sql_text

from .. import schemas
from . import fact_dictionary
from .case_service import _pg_table, _sql_now, _sql_uuid_gen
from .data_sheet_service import build_data_sheet, _as_json
from ...database import db as main_db

logger = logging.getLogger(__name__)


def apply_field_edit(
    case_id: str,
    field_id: str,
    value: Optional[str],
    user: Dict[str, Any],
    audience: str = "employee",
    lang: str = "en",
    mode: str = "full",
) -> schemas.DataSheetDTO:
    """Persist an edit to one data-sheet field and return the recomposed sheet.

    ``case_id`` must already be the resolved canonical id (the router calls
    ``_assert_case_access`` first).
    """
    role = (user.get("role") or "employee").lower()
    filled_by = "hr" if role in ("hr", "admin", "specialist") else "employee"
    cfv = _pg_table("case_form_field_values")

    with main_db.engine.begin() as conn:
        form_row = conn.execute(
            _sql_text(
                f"""
                SELECT cf.id AS case_form_id, ft.fields
                FROM {_pg_table('case_forms')} cf
                JOIN {_pg_table('form_templates')} ft ON cf.form_template_id = ft.id
                WHERE cf.case_id = :cid AND ft.category = 'data_sheet'
                ORDER BY cf.updated_at DESC
                LIMIT 1
                """
            ),
            {"cid": case_id},
        ).mappings().first()
        if not form_row:
            raise HTTPException(status_code=404, detail="No data sheet for this case")

        cf_id = form_row["case_form_id"]
        fields = _as_json(form_row.get("fields"), [])
        field_def = next((f for f in fields if f.get("id") == field_id), None)
        if field_def is None:
            raise HTTPException(status_code=404, detail="Field not found on this data sheet")

        # Firewall: regulated determinations can never be filled here.
        entry = fact_dictionary.lookup(field_def.get("prefill_source"), field_id)
        is_consult = bool(field_def.get("consult_professional")) or (
            entry.professional_review_required if entry else False
        )
        if is_consult:
            raise HTTPException(
                status_code=422,
                detail="This field is a consult-a-professional determination and cannot be filled here.",
            )

        prev = conn.execute(
            _sql_text(f"SELECT filled_by FROM {cfv} WHERE case_form_id=:cf AND field_id=:fid"),
            {"cf": cf_id, "fid": field_id},
        ).first()
        was_machine = bool(prev) and prev[0] in ("ai", "system")

        conn.execute(
            _sql_text(
                f"INSERT INTO {cfv} "
                f"(id, case_form_id, field_id, value, filled_by, source, reviewed, overridden, updated_at) "
                f"VALUES ({_sql_uuid_gen()}, :cf, :fid, :val, :by, 'manual', TRUE, :ovr, {_sql_now()}) "
                f"ON CONFLICT (case_form_id, field_id) DO UPDATE "
                f"SET value=EXCLUDED.value, filled_by=:by, source='manual', reviewed=TRUE, "
                f"overridden=CASE WHEN {cfv}.filled_by IN ('ai','system') THEN TRUE "
                f"ELSE {cfv}.overridden END, updated_at={_sql_now()}"
            ),
            {"cf": cf_id, "fid": field_id, "val": value, "by": filled_by, "ovr": was_machine},
        )

        # Keep the stored completion column in step with what the sheet shows (the dossier
        # surfaces read case_forms.completion_pct). Non-consult fields only, matching the sheet.
        value_rows = conn.execute(
            _sql_text(f"SELECT field_id, value FROM {cfv} WHERE case_form_id=:cf"),
            {"cf": cf_id},
        ).mappings().all()
        stored = {str(r["field_id"]): r["value"] for r in value_rows}
        total = filled = 0
        for fd in fields:
            e = fact_dictionary.lookup(fd.get("prefill_source"), fd.get("id"))
            if bool(fd.get("consult_professional")) or (e.professional_review_required if e else False):
                continue
            total += 1
            if stored.get(fd.get("id")):
                filled += 1
        pct = round(100 * filled / total) if total else 100
        conn.execute(
            _sql_text(
                f"UPDATE {_pg_table('case_forms')} SET completion_pct=:pct, "
                f"status=CASE WHEN status='not_started' THEN 'in_progress' ELSE status END, "
                f"updated_at={_sql_now()} WHERE id=:cf"
            ),
            {"pct": pct, "cf": cf_id},
        )

    # Recompose from committed state so the client gets the fresh sheet in one round-trip.
    return build_data_sheet(case_id, audience=audience, lang=lang, mode=mode)
