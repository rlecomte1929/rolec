"""[AUDIT-C1.2] Cases-domain DB methods, extracted from backend/database.py.

These were methods on the monolithic ``Database`` class. They live here as a
mixin (:class:`CasesMixin`) that ``Database`` inherits, so every existing caller
(``db.create_case(...)`` etc.) keeps working unchanged via normal MRO. The
methods reference instance state (``self.engine``, ``self._row_to_dict``) and
sibling methods (``self.resolve_canonical_case_id``) which resolve on the
composed ``Database`` instance — not on this class in isolation.

Extraction is incremental (AUDIT-C1.2, batch 1 of N): this module currently holds
the core case-lookup cluster. Remaining ``cases``-domain methods follow this same
pattern. Methods that use module-level helpers from database.py (e.g.
``_coerce_json_dict``, ``_relocation_cases_join_on``) will import those from
``backend.database`` (or a shared module) when moved — none in this batch need
them, which keeps this module free of any import cycle back to database.py.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import text

log = logging.getLogger(__name__)


class CasesMixin:
    """Cases-domain methods mixed into :class:`backend.database.Database`."""

    def create_case(
        self, case_id: str, hr_user_id: str, profile: Dict[str, Any], company_id: Optional[str] = None
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            if company_id is not None:
                conn.execute(text(
                    "INSERT INTO relocation_cases (id, hr_user_id, profile_json, company_id, created_at, updated_at) "
                    "VALUES (:id, :hr, :pj, :cid, :ca, :ua)"
                ), {"id": case_id, "hr": hr_user_id, "pj": json.dumps(profile), "cid": company_id, "ca": now, "ua": now})
            else:
                conn.execute(text(
                    "INSERT INTO relocation_cases (id, hr_user_id, profile_json, created_at, updated_at) "
                    "VALUES (:id, :hr, :pj, :ca, :ua)"
                ), {"id": case_id, "hr": hr_user_id, "pj": json.dumps(profile), "ca": now, "ua": now})

    def get_case_by_id(self, case_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            # relocation_cases.id is UUID; cast to text so string comparison works
            row = conn.execute(text("SELECT * FROM relocation_cases WHERE id::text = :id"), {"id": case_id}).fetchone()
        return self._row_to_dict(row)

    def redact_case_identity_data(
        self,
        case_id: str,
        *,
        actor_id: Optional[str] = None,
    ) -> bool:
        """
        GDPR erasure: replace identity PII in relocation_cases.profile_json with
        redaction markers. Preserves the row (keeps foreign-key targets intact)
        but clears passport, nationality, DOB, names, addresses, and family
        details. Writes an audit_logs row with action_type='erase'.

        Returns True if a row was redacted, False if no such case exists.
        """
        from ..app.services.audit_log_service import insert_audit_log, ACTOR_HUMAN, ACTOR_SYSTEM
        from .._time import utcnow_iso_naive
        now = utcnow_iso_naive()
        with self.engine.begin() as conn:
            row = conn.execute(
                text("SELECT * FROM relocation_cases WHERE id = :id"),
                {"id": case_id},
            ).fetchone()
            if not row:
                return False
            snapshot = self._row_to_dict(row) or {}
            # Top-level PII keys we scrub. Anything not listed is preserved
            # (origin/destination country, assignment type, etc. are not PII).
            PII_KEYS = {
                "employeeProfile", "familyMembers", "identity", "passport",
                "passports", "nationality", "nationalities", "dateOfBirth",
                "dob", "homeAddress", "destinationAddress", "phone", "email",
                "emergencyContact",
            }
            try:
                raw = snapshot.get("profile_json")
                profile = json.loads(raw) if isinstance(raw, str) else (raw or {})
            except Exception:
                profile = {}
            redacted = dict(profile) if isinstance(profile, dict) else {}
            for key in list(redacted.keys()):
                if key in PII_KEYS:
                    redacted[key] = "[redacted]"
            redacted["_erased"] = {"at": now, "actor": actor_id or "system"}
            conn.execute(
                text(
                    "UPDATE relocation_cases SET profile_json = :pj, updated_at = :ua "
                    "WHERE id = :id"
                ),
                {"pj": json.dumps(redacted), "ua": now, "id": case_id},
            )
            try:
                insert_audit_log(
                    conn,
                    entity_type="relocation_case",
                    entity_id=case_id,
                    action_type="erase",
                    old_value={"profile_keys": list((profile or {}).keys())},
                    new_value={"erased_at": now},
                    actor_type=ACTOR_HUMAN if actor_id else ACTOR_SYSTEM,
                    actor_id=actor_id,
                )
            except Exception as audit_exc:
                log.warning(
                    "redact_case_identity_data audit insert failed (cid=%s): %s",
                    case_id[:8], audit_exc,
                )
        return True

    def resolve_canonical_case_id(self, case_id: str) -> Optional[str]:
        """If case_id matches wizard_cases.id, return it (canonical). Else return None."""
        if not case_id or not case_id.strip():
            return None
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    text("SELECT id FROM wizard_cases WHERE id = :cid LIMIT 1"),
                    {"cid": case_id.strip()},
                ).fetchone()
            return str(row["id"]) if row else None
        except Exception:
            return None

    def coalesce_case_lookup_id(self, case_id: str) -> str:
        """Prefer canonical when resolvable (exists in wizard_cases), else return original."""
        canonical = self.resolve_canonical_case_id(case_id)
        return canonical if canonical is not None else (case_id or "")
