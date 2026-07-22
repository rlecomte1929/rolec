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
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

# [AUDIT-C1 fix] These helpers were referenced by the extracted CasesMixin
# methods but never imported into this module, so the relevant code paths
# raised NameError at runtime (same class as the `_is_sqlite` extraction bug).
# Source-of-truth imports mirror the pre-extraction backend/database.py.
from ..identity_normalize import normalize_invite_key
from ..readiness_service import (
    extract_destination_from_case_profile,
    extract_destination_from_profile,
    normalize_destination_key,
    resolve_readiness_route_key,
)
from ..sla_rules import compute_sla_status
from ..intake_route_fields import wizard_basics_to_route

log = logging.getLogger(__name__)

# CasesMixin methods branch on `_is_sqlite` for SQLite-vs-Postgres SQL. The C1
# mixin extraction left these references pointing at a module global that only
# existed in backend/database.py, so every such method raised
# NameError("name '_is_sqlite' is not defined") at runtime (e.g. the intake
# autosave 500). Derive it here from the same single source database.py uses
# (db_config.DATABASE_URL) — db_config imports nothing from backend/db, so this
# is circular-import-safe, unlike `from ..database import _is_sqlite`.
from ..db_config import DATABASE_URL as _raw_url

_is_sqlite = _raw_url.startswith("sqlite")


def _coerce_answers_field(value: Any) -> Dict[str, Any]:
    """Normalise the case_service_answers.answers column to a dict.

    Postgres returns the jsonb column already parsed as a dict (psycopg2); the old
    json.loads() raised on it and the except silently blanked it to {} — so saved
    service answers never reached the recommendation criteria (personalization was
    ignored in prod, invisible to SQLite tests where the column reads back as text).
    Accept a dict (Postgres jsonb) OR a JSON string (SQLite/text); anything else → {}.
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}
# JSONB cast suffix, mirroring backend/database.py (empty on SQLite). Referenced
# by extracted CasesMixin methods that build jsonb SQL.
_jb = "" if _is_sqlite else "::jsonb"


def _jbind(name: str) -> str:
    """Bind a JSON param with the correct per-backend cast.

    The historical ``f":{name}{_jb}"`` form produced ``:param::jsonb`` on
    Postgres, but SQLAlchemy's text() bind regex has a negative lookahead for
    ``:`` and so refuses to bind ``:param`` when it is immediately followed by
    ``::``. The placeholder was passed to Postgres literally and raised
    ``syntax error at or near ":"`` (a 500). ``CAST(:param AS jsonb)`` binds
    correctly; SQLite (TEXT columns) just takes the bare ``:param``.
    """
    return f":{name}" if _is_sqlite else f"CAST(:{name} AS jsonb)"

# public.cases.purpose CHECK allows only these four values. The wizard emits
# free-er strings; map them onto the allowed set so the canonical-case bridge
# never trips cases_purpose_check. Unknown/blank → 'work' (the column default).
_CASE_PURPOSE_MAP = {
    "work": "work",
    "employment": "work",
    "employment_transfer": "work",
    "job": "work",
    "relocation": "work",
    "intra_company_transfer": "intra_company_transfer",
    "intra_company": "intra_company_transfer",
    "ict": "intra_company_transfer",
    "transfer": "intra_company_transfer",
    "family_join": "family_join",
    "family": "family_join",
    "family_reunification": "family_join",
    "remote_work": "remote_work",
    "remote": "remote_work",
}


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

    def get_assignment_route_cities(self, assignment_id: str) -> tuple:
        """[AIQ-1336] Origin/destination CITY for an assignment from wizard_cases — the
        intake source of truth, reached via the SAME case_assignments→wizard_cases join
        the command-center uses. Returns (origin_city, dest_city), each None when unknown.

        relocation_cases frequently lacks the city (it lives in the wizard draft), so the
        HR case detail prefers this over the relocation_cases-based route hints. Defensive:
        any error / no match yields (None, None) so the caller falls back to country-only."""
        if not assignment_id or not str(assignment_id).strip():
            return (None, None)
        wc_join = self._command_center_join_wizard_cases()
        sql = f"""
            SELECT wc.origin_city AS oc, wc.dest_city AS dc
            FROM case_assignments ca
            LEFT JOIN wizard_cases wc ON {wc_join}
            WHERE ca.id = :aid
            LIMIT 1
        """
        try:
            with self.engine.connect() as conn:
                row = conn.execute(text(sql), {"aid": str(assignment_id).strip()}).fetchone()
            if not row:
                return (None, None)
            m = row._mapping
            oc = (m.get("oc") or "").strip() or None
            dc = (m.get("dc") or "").strip() or None
            return (oc, dc)
        except Exception:
            return (None, None)

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

    def update_assignment_intake_progress(
        self,
        assignment_id: str,
        employee_user_id: str,
        step: int,
        total_steps: int,
        request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Bump the intake wizard step counter for an assignment, scoped by
        employee ownership. Returns the new {intake_step, intake_total_steps,
        intake_updated_at} on success, or None if no row matched (caller maps
        that to a 404).

        Bounds are enforced by the case_assignments_intake_progress_bounds
        check constraint added in migration 20260529130000.
        """
        aid = (assignment_id or "").strip()
        uid = (employee_user_id or "").strip()
        if not aid or not uid:
            return None
        # Clamp at the python edge too so a constraint violation can't fire on
        # bad client input — this is a hot path called on every "Continue" click.
        step_i = max(0, int(step))
        total_i = max(1, int(total_steps))
        if step_i > total_i:
            step_i = total_i
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            row = self._exec(
                conn,
                "UPDATE case_assignments "
                "SET intake_step = :step, intake_total_steps = :total, "
                "    intake_updated_at = :now, updated_at = :now "
                "WHERE id = :id AND employee_user_id = :uid "
                "RETURNING intake_step, intake_total_steps, intake_updated_at",
                {"step": step_i, "total": total_i, "now": now, "id": aid, "uid": uid},
                op_name="update_assignment_intake_progress",
                request_id=request_id,
            ).fetchone()
        if not row:
            return None
        m = row._mapping if hasattr(row, "_mapping") else dict(row)
        return {
            "intake_step": m["intake_step"],
            "intake_total_steps": m["intake_total_steps"],
            "intake_updated_at": (
                m["intake_updated_at"].isoformat()
                if hasattr(m["intake_updated_at"], "isoformat") and m["intake_updated_at"] is not None
                else m["intake_updated_at"]
            ),
        }

    def get_assignment_intake(
        self,
        assignment_id: str,
        employee_user_id: str,
        request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Read step counter + form draft for one assignment. Scoped by
        employee ownership; returns None if the assignment isn't
        owned by this user. The draft is decoded to a dict
        regardless of backend — Postgres delivers jsonb pre-parsed,
        SQLite stores TEXT we json.loads here so the API contract
        stays stable across both.
        """
        aid = (assignment_id or "").strip()
        uid = (employee_user_id or "").strip()
        if not aid or not uid:
            return None
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT intake_step, intake_total_steps, intake_updated_at, intake_draft "
                "FROM case_assignments WHERE id = :id AND employee_user_id = :uid",
                {"id": aid, "uid": uid},
                op_name="get_assignment_intake",
                request_id=request_id,
            ).fetchone()
        if not row:
            return None
        m = row._mapping if hasattr(row, "_mapping") else dict(row)
        raw = m["intake_draft"]
        if isinstance(raw, str):
            try:
                draft: Optional[Dict[str, Any]] = json.loads(raw) if raw else None
            except (ValueError, TypeError):
                draft = None
        else:
            # psycopg returns jsonb already-parsed
            draft = raw
        return {
            "intake_step": m["intake_step"],
            "intake_total_steps": m["intake_total_steps"],
            "intake_updated_at": (
                m["intake_updated_at"].isoformat()
                if hasattr(m["intake_updated_at"], "isoformat") and m["intake_updated_at"] is not None
                else m["intake_updated_at"]
            ),
            "intake_draft": draft,
        }

    def update_assignment_intake_draft(
        self,
        assignment_id: str,
        employee_user_id: str,
        draft: Dict[str, Any],
        request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Upsert the wizard form draft for one assignment. Scoped by
        employee ownership. Postgres CASTs the JSON text to jsonb
        so the column type stays correct end-to-end; SQLite stores
        the same TEXT verbatim. Returns None when the assignment
        isn't owned by this user (caller maps to 404).
        """
        aid = (assignment_id or "").strip()
        uid = (employee_user_id or "").strip()
        if not aid or not uid:
            return None
        now = datetime.utcnow().isoformat()
        payload = json.dumps(draft) if draft is not None else None
        if _is_sqlite:
            sql = (
                "UPDATE case_assignments "
                "SET intake_draft = :draft, intake_updated_at = :now, updated_at = :now "
                "WHERE id = :id AND employee_user_id = :uid "
                "RETURNING intake_updated_at"
            )
        else:
            sql = (
                "UPDATE case_assignments "
                "SET intake_draft = CAST(:draft AS jsonb), "
                # intake_updated_at / updated_at are timestamptz in prod; the
                # bound :now is ISO text, and Postgres has no implicit text→
                # timestamptz cast for a parameter (it 500s the autosave). Cast
                # explicitly. SQLite (TEXT columns) keeps the un-cast branch above.
                "    intake_updated_at = CAST(:now AS timestamptz), "
                "    updated_at = CAST(:now AS timestamptz) "
                "WHERE id = :id AND employee_user_id = :uid "
                "RETURNING intake_updated_at"
            )
        with self.engine.begin() as conn:
            row = self._exec(
                conn,
                sql,
                {"draft": payload, "now": now, "id": aid, "uid": uid},
                op_name="update_assignment_intake_draft",
                request_id=request_id,
            ).fetchone()
        if not row:
            return None
        m = row._mapping if hasattr(row, "_mapping") else dict(row)
        return {
            "intake_updated_at": (
                m["intake_updated_at"].isoformat()
                if hasattr(m["intake_updated_at"], "isoformat") and m["intake_updated_at"] is not None
                else m["intake_updated_at"]
            ),
            "intake_draft": draft,
        }

    def set_assignment_submitted(self, assignment_id: str, request_id: Optional[str] = None) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            # AIQ-1243 (C-01b): mark intake complete in the SAME write that flips the
            # status. The client's updateIntakeProgress is fire-and-forget and the
            # best-effort server advance keys on employee_user_id (so an id-resolution
            # mismatch can miss the row), which left submitted cases reading
            # "4/5 steps · Continue". Setting intake_step = intake_total_steps here is
            # unconditional (WHERE id only) and satisfies the intake_step<=total CHECK.
            self._exec(
                conn,
                "UPDATE case_assignments "
                "SET status = :status, intake_step = intake_total_steps, "
                "    submitted_at = :now, updated_at = :now "
                "WHERE id = :id",
                {"status": "submitted", "now": now, "id": assignment_id},
                op_name="set_assignment_submitted",
                request_id=request_id,
            )

    def set_assignment_decision(
        self,
        assignment_id: str,
        decision: str,
        notes: Optional[str],
        request_id: Optional[str] = None,
    ) -> None:
        with self.engine.begin() as conn:
            self._exec(
                conn,
                "UPDATE case_assignments "
                "SET status = :decision, decision = :decision, hr_notes = :notes, updated_at = :ua "
                "WHERE id = :id",
                {"decision": decision, "notes": notes, "ua": datetime.utcnow().isoformat(), "id": assignment_id},
                op_name="set_assignment_decision",
                request_id=request_id,
            )

    def insert_case_event(
        self,
        case_id: str,
        assignment_id: Optional[str],
        actor_principal_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Append an immutable event to the case_events spine."""
        event_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        pl = json.dumps(payload or {})
        with self.engine.begin() as conn:
            if _is_sqlite:
                self._exec(
                    conn,
                    "INSERT INTO case_events (id, case_id, canonical_case_id, assignment_id, actor_principal_id, event_type, payload, created_at) "
                    "VALUES (:id, :cid, :canonical, :aid, :actor, :et, :pl, :ca)",
                    {
                        "id": event_id,
                        "cid": case_id,
                        "canonical": case_id,
                        "aid": assignment_id,
                        "actor": actor_principal_id,
                        "et": event_type,
                        "pl": pl,
                        "ca": now,
                    },
                    op_name="insert_case_event",
                    request_id=request_id,
                )
            else:
                self._exec(
                    conn,
                    "INSERT INTO case_events (id, case_id, canonical_case_id, assignment_id, actor_principal_id, event_type, payload, created_at) "
                    "VALUES (:id, :cid, :canonical, :aid, :actor, :et, :pl, :ca)",
                    {
                        "id": event_id,
                        "cid": case_id,
                        "canonical": case_id,
                        "aid": assignment_id,
                        "actor": actor_principal_id,
                        "et": event_type,
                        "pl": pl,
                        "ca": now,
                    },
                    op_name="insert_case_event",
                    request_id=request_id,
                )

    def list_case_events(self, case_id: str, request_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List case_events for a case, newest first. Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT id, case_id, assignment_id, actor_principal_id, actor_user_id, event_type, payload, description, created_at "
                "FROM case_events WHERE (canonical_case_id = :cid OR case_id = :cid) ORDER BY created_at DESC LIMIT 200",
                {"cid": cid},
                op_name="list_case_events",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def ensure_case_participant(
        self,
        case_id: str,
        person_id: str,
        role: str,
        invited_at: Optional[str] = None,
        joined_at: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Insert or update case_participants. Idempotent on (case_id, person_id, role)."""
        part_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        inv = invited_at or now
        jnd = joined_at
        params = {
            "id": part_id,
            "cid": case_id,
            "canonical": case_id,
            "pid": person_id,
            "role": role,
            "inv": inv,
            "jnd": jnd,
            "ca": now,
        }
        with self.engine.begin() as conn:
            if _is_sqlite:
                self._exec(
                    conn,
                    "INSERT INTO case_participants (id, case_id, canonical_case_id, person_id, role, invited_at, joined_at, created_at) "
                    "VALUES (:id, :cid, :canonical, :pid, :role, :inv, :jnd, :ca) "
                    "ON CONFLICT (case_id, person_id, role) DO UPDATE SET "
                    "invited_at = COALESCE(excluded.invited_at, case_participants.invited_at), "
                    "joined_at = COALESCE(excluded.joined_at, case_participants.joined_at), "
                    "canonical_case_id = COALESCE(excluded.canonical_case_id, case_participants.canonical_case_id)",
                    params,
                    op_name="ensure_case_participant",
                    request_id=request_id,
                )
            else:
                self._exec(
                    conn,
                    "INSERT INTO case_participants (id, case_id, canonical_case_id, person_id, role, invited_at, joined_at, created_at) "
                    "VALUES (:id, :cid, :canonical, :pid, :role, :inv, :jnd, :ca) "
                    "ON CONFLICT (case_id, person_id, role) DO UPDATE SET "
                    "invited_at = COALESCE(EXCLUDED.invited_at, case_participants.invited_at), "
                    "joined_at = COALESCE(EXCLUDED.joined_at, case_participants.joined_at), "
                    "canonical_case_id = COALESCE(EXCLUDED.canonical_case_id, case_participants.canonical_case_id)",
                    params,
                    op_name="ensure_case_participant",
                    request_id=request_id,
                )

    def list_case_participants(
        self, case_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List case_participants for a case. Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT id, case_id, person_id, role, invited_at, joined_at, created_at "
                "FROM case_participants WHERE (canonical_case_id = :cid OR case_id = :cid) ORDER BY created_at ASC",
                {"cid": cid},
                op_name="list_case_participants",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def insert_case_evidence(
        self,
        case_id: str,
        assignment_id: Optional[str],
        participant_id: Optional[str],
        requirement_id: Optional[str],
        evidence_type: str,
        file_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: str = "submitted",
        request_id: Optional[str] = None,
    ) -> str:
        """Insert a case_evidence row. Returns the new evidence id."""
        evidence_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        pl = json.dumps(metadata or {})
        with self.engine.begin() as conn:
            self._exec(
                conn,
                "INSERT INTO case_evidence "
                "(id, case_id, canonical_case_id, assignment_id, participant_id, requirement_id, evidence_type, "
                "file_url, metadata, status, submitted_at, created_at) "
                "VALUES (:id, :cid, :canonical, :aid, :pid, :rid, :et, :url, :meta, :status, :sub, :ca)",
                {
                    "id": evidence_id,
                    "cid": case_id,
                    "canonical": case_id,
                    "aid": assignment_id,
                    "pid": participant_id,
                    "rid": requirement_id,
                    "et": evidence_type,
                    "url": file_url,
                    "meta": pl,
                    "status": status,
                    "sub": now,
                    "ca": now,
                },
                op_name="insert_case_evidence",
                request_id=request_id,
            )
        return evidence_id

    def list_case_evidence(
        self, case_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List case_evidence for a case, newest first. Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT id, case_id, assignment_id, participant_id, requirement_id, evidence_type, "
                "file_url, metadata, status, submitted_at, created_at "
                "FROM case_evidence WHERE (canonical_case_id = :cid OR case_id = :cid) ORDER BY created_at DESC",
                {"cid": cid},
                op_name="list_case_evidence",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def list_assignment_evidence(
        self, assignment_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List case_evidence for an assignment, newest first."""
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT id, case_id, assignment_id, participant_id, requirement_id, evidence_type, "
                "file_url, metadata, status, submitted_at, created_at "
                "FROM case_evidence WHERE assignment_id = :aid ORDER BY created_at DESC",
                {"aid": assignment_id},
                op_name="list_assignment_evidence",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def _ensure_case_milestones_tracker_sqlite(self, conn: Any) -> None:
        """Migrate legacy SQLite case_milestones to blocked status + owner/criticality/notes."""
        row = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='case_milestones'")
        ).fetchone()
        if not row or not row[0]:
            return
        ddl = row[0] or ""
        if "blocked" in ddl and "owner" in ddl:
            return
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        try:
            conn.execute(text("""
                CREATE TABLE case_milestones__new (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    canonical_case_id TEXT,
                    milestone_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    target_date TEXT,
                    actual_date TEXT,
                    status TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','in_progress','done','skipped','overdue','blocked')),
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    owner TEXT NOT NULL DEFAULT 'joint',
                    criticality TEXT NOT NULL DEFAULT 'normal',
                    notes TEXT,
                    source TEXT,
                    service_key TEXT
                )
            """))
            conn.execute(text("""
                INSERT INTO case_milestones__new (
                  id, case_id, canonical_case_id, milestone_type, title, description,
                  target_date, actual_date, status, sort_order, created_at, updated_at,
                  owner, criticality, notes
                )
                SELECT
                  id, case_id, canonical_case_id, milestone_type, title, description,
                  target_date, actual_date, status, sort_order, created_at, updated_at,
                  'joint', 'normal', NULL
                FROM case_milestones
            """))
            conn.execute(text("DROP TABLE case_milestones"))
            conn.execute(text("ALTER TABLE case_milestones__new RENAME TO case_milestones"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_milestones_case ON case_milestones(case_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_milestones_canonical ON case_milestones(canonical_case_id)"))
        finally:
            conn.execute(text("PRAGMA foreign_keys=ON"))

    # ------------------------------------------------------------------
    # Case milestones (timeline workflow)
    # ------------------------------------------------------------------
    def list_case_milestones(
        self, case_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List case_milestones for a case, ordered by sort_order then created_at."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                """SELECT id, case_id, canonical_case_id, milestone_type, title, description,
                   target_date, actual_date, status, sort_order, created_at, updated_at,
                   owner, criticality, notes, source, service_key
                   FROM case_milestones
                   WHERE (canonical_case_id = :cid OR case_id = :cid)
                   ORDER BY sort_order ASC, created_at ASC""",
                {"cid": cid},
                op_name="list_case_milestones",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def upsert_case_milestone(
        self,
        case_id: str,
        milestone_type: str,
        title: str,
        *,
        description: Optional[str] = None,
        target_date: Optional[str] = None,
        actual_date: Optional[str] = None,
        status: str = "pending",
        sort_order: int = 0,
        owner: str = "joint",
        criticality: str = "normal",
        notes: Optional[str] = None,
        source: Optional[str] = None,
        service_key: Optional[str] = None,
        milestone_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create or update a milestone. If milestone_id given, update; else create."""
        cid = self.coalesce_case_lookup_id(case_id)
        now = datetime.utcnow().isoformat()
        if milestone_id:
            with self.engine.begin() as conn:
                self._exec(
                    conn,
                    """UPDATE case_milestones SET
                       title = :title, description = :desc, target_date = :td, actual_date = :ad,
                       status = :status, sort_order = :so, owner = :owner, criticality = :crit,
                       notes = :notes, source = :source, service_key = :svc_key, updated_at = :now
                       WHERE id = :id AND (canonical_case_id = :cid OR case_id = :cid)""",
                    {
                        "id": milestone_id,
                        "cid": cid,
                        "title": title,
                        "desc": description,
                        "td": target_date,
                        "ad": actual_date,
                        "status": status,
                        "so": sort_order,
                        "owner": owner,
                        "crit": criticality,
                        "notes": notes,
                        "source": source,
                        "svc_key": service_key,
                        "now": now,
                    },
                    op_name="update_case_milestone",
                    request_id=request_id,
                )
            with self.engine.connect() as conn:
                row = self._exec(
                    conn,
                    "SELECT * FROM case_milestones WHERE id = :id",
                    {"id": milestone_id},
                    op_name="get_milestone",
                    request_id=request_id,
                ).fetchone()
            return self._row_to_dict(row) or {}
        mid = str(uuid.uuid4())
        with self.engine.begin() as conn:
            self._exec(
                conn,
                """INSERT INTO case_milestones
                   (id, case_id, canonical_case_id, milestone_type, title, description, target_date, actual_date, status, sort_order, created_at, updated_at, owner, criticality, notes, source, service_key)
                   VALUES (:id, :cid, :canonical, :mt, :title, :desc, :td, :ad, :status, :so, :now, :now, :owner, :crit, :notes, :source, :svc_key)""",
                {
                    "id": mid,
                    "cid": case_id,
                    "canonical": cid,
                    "mt": milestone_type,
                    "title": title,
                    "desc": description,
                    "td": target_date,
                    "ad": actual_date,
                    "status": status,
                    "so": sort_order,
                    "now": now,
                    "owner": owner,
                    "crit": criticality,
                    "notes": notes,
                    "source": source,
                    "svc_key": service_key,
                },
                op_name="insert_case_milestone",
                request_id=request_id,
            )
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT * FROM case_milestones WHERE id = :id",
                {"id": mid},
                op_name="get_milestone",
                request_id=request_id,
            ).fetchone()
        return self._row_to_dict(row) or {}

    def delete_case_milestones(
        self, case_id: str, *, exclude_source: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> int:
        """Delete milestones for a case. Used before re-persisting a regenerated
        roadmap so the plan view reflects the new set rather than a mix. Matches
        the same predicate list_case_milestones reads by. `exclude_source`
        (e.g. 'service') preserves rows with that source so externally-managed
        milestones survive a regeneration."""
        cid = self.coalesce_case_lookup_id(case_id)
        sql = "DELETE FROM case_milestones WHERE (canonical_case_id = :cid OR case_id = :cid)"
        params: Dict[str, Any] = {"cid": cid}
        if exclude_source is not None:
            sql += " AND (source IS NULL OR source <> :excl)"
            params["excl"] = exclude_source
        with self.engine.begin() as conn:
            result = self._exec(
                conn, sql, params,
                op_name="delete_case_milestones",
                request_id=request_id,
            )
        return getattr(result, "rowcount", 0) or 0

    def delete_service_milestones_not_in(
        self, case_id: str, keep_service_keys: Sequence[str],
        *, request_id: Optional[str] = None,
    ) -> int:
        """Delete source='service' milestones whose service_key is NOT in
        keep_service_keys (i.e. the service was deselected). Never touches
        AI/deterministic/manual rows."""
        cid = self.coalesce_case_lookup_id(case_id)
        keys = list(keep_service_keys)
        with self.engine.begin() as conn:
            if keys:
                placeholders = ", ".join(f":k{i}" for i in range(len(keys)))
                params: Dict[str, Any] = {"cid": cid, **{f"k{i}": k for i, k in enumerate(keys)}}
                sql = (
                    "DELETE FROM case_milestones "
                    "WHERE (canonical_case_id = :cid OR case_id = :cid) "
                    "AND source = 'service' "
                    f"AND service_key NOT IN ({placeholders})"
                )
            else:
                params = {"cid": cid}
                sql = (
                    "DELETE FROM case_milestones "
                    "WHERE (canonical_case_id = :cid OR case_id = :cid) "
                    "AND source = 'service'"
                )
            result = self._exec(
                conn, sql, params,
                op_name="delete_service_milestones_not_in",
                request_id=request_id,
            )
        return getattr(result, "rowcount", 0) or 0

    def delete_service_milestones_not_in_types(
        self, case_id: str, keep_types: Sequence[str],
        *, request_id: Optional[str] = None,
    ) -> int:
        """Delete source='service' milestones whose milestone_type is NOT in
        keep_types. Used so a changed step set (e.g. destination change) cleans up
        stale rows. Never touches AI/deterministic/manual rows."""
        cid = self.coalesce_case_lookup_id(case_id)
        types = list(keep_types)
        with self.engine.begin() as conn:
            if types:
                ph = ", ".join(f":t{i}" for i in range(len(types)))
                params: Dict[str, Any] = {"cid": cid, **{f"t{i}": t for i, t in enumerate(types)}}
                sql = (
                    "DELETE FROM case_milestones "
                    "WHERE (canonical_case_id = :cid OR case_id = :cid) "
                    "AND source = 'service' "
                    f"AND milestone_type NOT IN ({ph})"
                )
            else:
                params = {"cid": cid}
                sql = (
                    "DELETE FROM case_milestones "
                    "WHERE (canonical_case_id = :cid OR case_id = :cid) AND source = 'service'"
                )
            result = self._exec(
                conn, sql, params,
                op_name="delete_service_milestones_not_in_types",
                request_id=request_id,
            )
        return getattr(result, "rowcount", 0) or 0

    # ------------------------------------------------------------------
    # Roadmap validation gate (employee "validate & start tasks" checkpoint)
    # ------------------------------------------------------------------
    def _ensure_case_roadmap_validations_table(self, conn: Any) -> None:
        """Idempotently ensure the table exists (prod gets it via migration;
        this keeps SQLite test DBs and fresh dev DBs working)."""
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS case_roadmap_validations ("
            "  canonical_case_id TEXT PRIMARY KEY,"
            "  validated_at TEXT NOT NULL,"
            "  validated_by_user_id TEXT,"
            "  created_at TEXT NOT NULL"
            ")"
        ))

    def upsert_roadmap_validation(
        self, case_id: str, validated_by_user_id: Optional[str],
        *, request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record (or refresh) the roadmap-validation checkpoint for a case.
        Keyed by canonical case id (same as case_milestones). Idempotent."""
        cid = self.coalesce_case_lookup_id(case_id)
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            self._ensure_case_roadmap_validations_table(conn)
            existing = self._exec(
                conn,
                "SELECT canonical_case_id FROM case_roadmap_validations WHERE canonical_case_id = :cid",
                {"cid": cid}, op_name="get_roadmap_validation_for_upsert", request_id=request_id,
            ).fetchone()
            if existing:
                self._exec(
                    conn,
                    "UPDATE case_roadmap_validations SET validated_at = :now, "
                    "validated_by_user_id = :uid WHERE canonical_case_id = :cid",
                    {"now": now, "uid": validated_by_user_id, "cid": cid},
                    op_name="update_roadmap_validation", request_id=request_id,
                )
            else:
                self._exec(
                    conn,
                    "INSERT INTO case_roadmap_validations "
                    "(canonical_case_id, validated_at, validated_by_user_id, created_at) "
                    "VALUES (:cid, :now, :uid, :now)",
                    {"cid": cid, "now": now, "uid": validated_by_user_id},
                    op_name="insert_roadmap_validation", request_id=request_id,
                )
        return {"canonical_case_id": cid, "validated_at": now,
                "validated_by_user_id": validated_by_user_id}

    def get_roadmap_validation(
        self, case_id: str, *, request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the validation row for a case, or None."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.begin() as conn:
            self._ensure_case_roadmap_validations_table(conn)
            row = self._exec(
                conn,
                "SELECT canonical_case_id, validated_at, validated_by_user_id, created_at "
                "FROM case_roadmap_validations WHERE canonical_case_id = :cid",
                {"cid": cid}, op_name="get_roadmap_validation", request_id=request_id,
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row) if hasattr(self, "_row_to_dict") else dict(row._mapping)

    def get_roadmap_release(
        self, case_id: str, *, request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """HR's review decision for a case's roadmap, or None if nobody has decided.

        None means RELEASED to the caller — see `_resolve_roadmap_release`. The 47 cases
        that had a roadmap before this gate existed have no row here, and must not lose
        their plans.
        """
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.begin() as conn:
            row = self._exec(
                conn,
                "SELECT case_id, released_to_user, regeneration_requested, reviewer_id, notes "
                "FROM roadmap_review_status WHERE case_id = :cid",
                {"cid": cid}, op_name="get_roadmap_release", request_id=request_id,
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row) if hasattr(self, "_row_to_dict") else dict(row._mapping)

    def link_milestone_entity(
        self,
        milestone_id: str,
        linked_entity_type: str,
        linked_entity_id: str,
        request_id: Optional[str] = None,
    ) -> None:
        """Add a link from milestone to an entity (evidence, event, rfq, service, etc.)."""
        link_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            self._exec(
                conn,
                "INSERT INTO milestone_links (id, milestone_id, linked_entity_type, linked_entity_id, created_at) "
                "VALUES (:id, :mid, :et, :eid, :now)",
                {
                    "id": link_id,
                    "mid": milestone_id,
                    "et": linked_entity_type,
                    "eid": linked_entity_id,
                    "now": now,
                },
                op_name="link_milestone_entity",
                request_id=request_id,
            )

    def list_milestone_links(
        self, milestone_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List links for a milestone."""
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT id, milestone_id, linked_entity_type, linked_entity_id, created_at FROM milestone_links WHERE milestone_id = :mid",
                {"mid": milestone_id},
                op_name="list_milestone_links",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    # ------------------------------------------------------------------
    # Exception requests (P2/P3 — HR sign-off flags)
    # ------------------------------------------------------------------

    def get_assignment_by_id(
        self,
        assignment_id: str,
        request_id: Optional[str] = None,
        *,
        include_archived: bool = False,
    ) -> Optional[Dict[str, Any]]:
        where = "WHERE id = :id" if include_archived else "WHERE id = :id AND archived_at IS NULL"
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                f"SELECT * FROM case_assignments {where}",
                {"id": assignment_id},
                op_name="get_assignment_by_id",
                request_id=request_id,
            ).fetchone()
        return self._row_to_dict(row)

    def get_assignment_by_case_id(self, case_id: str, request_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Prefer canonical_case_id when resolving, fall back to case_id for legacy."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT * FROM case_assignments WHERE (canonical_case_id = :cid OR case_id = :cid)",
                {"cid": cid},
                op_name="get_assignment_by_case_id",
                request_id=request_id,
            ).fetchone()
        return self._row_to_dict(row)

    def resolve_case_status(
        self,
        case_key: str,
        employee_user_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Optional[str]:
        """Canonical case status — the SINGLE source shared by the case LIST
        (GET /api/employee/cases) and the case DETAIL (GET /api/cases/{id}) so
        they can never disagree. Picks the requesting employee's most-recently
        created assignment for the case (matching the list's ORDER BY created_at
        DESC), or the most-recent assignment overall when employee_user_id is None
        (HR/admin callers), and normalizes it. Returns None when the case has no
        assignment (callers then fall back to wizard_cases.status).
        """
        from ..app.services.case_status import normalize_status  # lazy: avoid import cycle
        ck = (case_key or "").strip()
        if not ck:
            return None
        emp = (employee_user_id or "").strip() or None
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT status FROM case_assignments "
                "WHERE (canonical_case_id = :ck OR case_id = :ck OR id = :ck) "
                "  AND (:emp IS NULL OR employee_user_id = :emp) "
                "ORDER BY created_at DESC LIMIT 1",
                {"ck": ck, "emp": emp},
                op_name="resolve_case_status",
                request_id=request_id,
            ).fetchone()
        if not row:
            return None
        m = row._mapping if hasattr(row, "_mapping") else row
        return normalize_status(m["status"])

    def get_mobility_case_id_for_assignment(
        self, assignment_id: str, request_id: Optional[str] = None
    ) -> Optional[str]:
        """Forward lookup: case_assignments.id -> mobility_cases.id via assignment_mobility_links."""
        aid = (assignment_id or "").strip()
        if not aid:
            return None
        try:
            with self.engine.connect() as conn:
                row = self._exec(
                    conn,
                    "SELECT mobility_case_id FROM assignment_mobility_links WHERE assignment_id = :aid LIMIT 1",
                    {"aid": aid},
                    op_name="get_mobility_case_id_for_assignment",
                    request_id=request_id,
                ).mappings().first()
            if not row:
                return None
            mid = row.get("mobility_case_id")
            return str(mid).strip() if mid is not None else None
        except Exception as e:
            log.debug("get_mobility_case_id_for_assignment failed: %s", e)
            return None

    def get_assignment_id_for_mobility_case(
        self, mobility_case_id: str, request_id: Optional[str] = None
    ) -> Optional[str]:
        """Reverse lookup: mobility_cases.id -> case_assignments.id via assignment_mobility_links."""
        mid = (mobility_case_id or "").strip()
        if not mid:
            return None
        try:
            with self.engine.connect() as conn:
                row = self._exec(
                    conn,
                    "SELECT assignment_id FROM assignment_mobility_links WHERE mobility_case_id = :mid LIMIT 1",
                    {"mid": mid},
                    op_name="get_assignment_id_for_mobility_case",
                    request_id=request_id,
                ).mappings().first()
            if not row:
                return None
            aid = row.get("assignment_id")
            return str(aid).strip() if aid is not None else None
        except Exception as e:
            log.debug("get_assignment_id_for_mobility_case failed: %s", e)
            return None

    def mobility_case_row_exists(self, mobility_case_id: str, request_id: Optional[str] = None) -> bool:
        """True if a mobility_cases row exists (used for admin read access without assignment bridge)."""
        mid = (mobility_case_id or "").strip()
        if not mid:
            return False
        try:
            with self.engine.connect() as conn:
                row = self._exec(
                    conn,
                    "SELECT 1 FROM mobility_cases WHERE id = :id LIMIT 1",
                    {"id": mid},
                    op_name="mobility_case_row_exists",
                    request_id=request_id,
                ).fetchone()
            return row is not None
        except Exception as e:
            log.debug("mobility_case_row_exists failed: %s", e)
            return False

    def list_case_services(self, assignment_id: str, request_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT * FROM case_services WHERE assignment_id = :aid ORDER BY category, service_key",
                {"aid": assignment_id},
                op_name="list_case_services",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def upsert_case_services(
        self,
        assignment_id: str,
        case_id: str,
        services: List[Dict[str, Any]],
        request_id: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            for item in services:
                payload = {
                    "id": item.get("id") or str(uuid.uuid4()),
                    "case_id": case_id,
                    "canonical_case_id": case_id,
                    "assignment_id": assignment_id,
                    "service_key": item.get("service_key"),
                    "category": item.get("category"),
                    "selected": bool(item.get("selected", True)),
                    "estimated_cost": item.get("estimated_cost"),
                    "currency": item.get("currency") or "EUR",
                    "created_at": now,
                    "updated_at": now,
                }
                if _is_sqlite:
                    # SQLite local dev: no unique constraint on (case_id, service_key)
                    update = self._exec(
                        conn,
                        """
                        UPDATE case_services
                        SET assignment_id = :assignment_id,
                            category = :category,
                            selected = :selected,
                            estimated_cost = :estimated_cost,
                            currency = :currency,
                            updated_at = :updated_at
                        WHERE case_id = :case_id AND service_key = :service_key
                        """,
                        payload,
                        op_name="update_case_services",
                        request_id=request_id,
                    )
                    if update.rowcount == 0:
                        self._exec(
                            conn,
                            """
                            INSERT INTO case_services (
                                id, case_id, canonical_case_id, assignment_id, service_key, category,
                                selected, estimated_cost, currency, created_at, updated_at
                            )
                            VALUES (
                                :id, :case_id, :canonical_case_id, :assignment_id, :service_key, :category,
                                :selected, :estimated_cost, :currency, :created_at, :updated_at
                            )
                            """,
                            payload,
                            op_name="insert_case_services",
                            request_id=request_id,
                        )
                else:
                    self._exec(
                        conn,
                        """
                        INSERT INTO case_services (
                            id, case_id, canonical_case_id, assignment_id, service_key, category,
                            selected, estimated_cost, currency, created_at, updated_at
                        )
                        VALUES (
                            :id, :case_id, :canonical_case_id, :assignment_id, :service_key, :category,
                            :selected, :estimated_cost, :currency, :created_at, :updated_at
                        )
                        ON CONFLICT(case_id, service_key)
                        DO UPDATE SET
                            canonical_case_id = COALESCE(excluded.canonical_case_id, case_services.canonical_case_id),
                            assignment_id = excluded.assignment_id,
                            category = excluded.category,
                            selected = excluded.selected,
                            estimated_cost = excluded.estimated_cost,
                            currency = excluded.currency,
                            updated_at = excluded.updated_at
                        """,
                        payload,
                        op_name="upsert_case_services",
                        request_id=request_id,
                    )

    def list_case_service_answers(
        self,
        case_id: str,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT * FROM case_service_answers WHERE (canonical_case_id = :cid OR case_id = :cid) ORDER BY service_key",
                {"cid": cid},
                op_name="list_case_service_answers",
                request_id=request_id,
            ).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["answers"] = _coerce_answers_field(item.get("answers"))
        return items

    def upsert_case_service_answers(
        self,
        case_id: str,
        service_key: str,
        answers: Dict[str, Any],
        request_id: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        sql = """
            INSERT INTO case_service_answers (id, case_id, canonical_case_id, service_key, answers, updated_at)
            VALUES (:id, :case_id, :canonical_case_id, :service_key, :answers, :updated_at)
            ON CONFLICT(case_id, service_key) DO UPDATE SET
                canonical_case_id = COALESCE(excluded.canonical_case_id, case_service_answers.canonical_case_id),
                answers = excluded.answers,
                updated_at = excluded.updated_at
        """
        params = {
            "id": str(uuid.uuid4()),
            "case_id": case_id,
            "canonical_case_id": case_id,
            "service_key": service_key,
            "answers": json.dumps(answers),
            "updated_at": now,
        }
        with self.engine.begin() as conn:
            self._exec(conn, sql, params, op_name="upsert_case_service_answers", request_id=request_id)

    def list_linked_assignments_for_employee(
        self,
        employee_user_id: str,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not (employee_user_id or "").strip():
            return []
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT * FROM case_assignments WHERE employee_user_id = :emp "
                "ORDER BY created_at DESC",
                {"emp": employee_user_id.strip()},
                op_name="list_linked_assignments_for_employee",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def get_assignment_for_employee(
        self,
        employee_user_id: str,
        request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        linked = self.list_linked_assignments_for_employee(employee_user_id, request_id=request_id)
        return linked[0] if linked else None

    def list_employee_linked_assignment_overview(
        self,
        employee_user_id: str,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lightweight linked rows for the employee overview: assignment + case + company + destination hints.
        Scoped strictly by case_assignments.employee_user_id.
        """
        uid = (employee_user_id or "").strip()
        if not uid:
            return []
        from ..database import _relocation_cases_join_on  # lazy: avoid import cycle
        join_on = _relocation_cases_join_on("a", style="standard")
        sql = f"""
            SELECT
                a.id AS assignment_id,
                COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id) AS case_id,
                a.status AS assignment_status,
                a.created_at AS assignment_created_at,
                a.updated_at AS assignment_updated_at,
                a.intake_step AS intake_step,
                a.intake_total_steps AS intake_total_steps,
                a.intake_updated_at AS intake_updated_at,
                rc.host_country AS host_country,
                rc.home_country AS home_country,
                rc.host_city AS host_city,
                rc.home_city AS home_city,
                rc.stage AS relocation_stage,
                rc.status AS relocation_case_status,
                COALESCE(rc.company_id, hu.company_id) AS company_id,
                c.name AS company_name
            FROM case_assignments a
            LEFT JOIN relocation_cases rc ON {join_on}
            LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
            LEFT JOIN companies c ON CAST(c.id AS TEXT) = COALESCE(rc.company_id, hu.company_id)
            WHERE a.employee_user_id = :uid
            ORDER BY a.created_at DESC
        """
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                sql,
                {"uid": uid},
                op_name="list_employee_linked_assignment_overview",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def list_employee_pending_assignment_overview(
        self,
        auth_user_id: str,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Pending_claim assignments for contacts already linked to this auth user.
        Drops rows where relocation case company disagrees with employee_contact company (anti-leak).
        """
        uid = (auth_user_id or "").strip()
        if not uid:
            return []
        from ..database import _relocation_cases_join_on  # lazy: avoid import cycle
        join_on = _relocation_cases_join_on("a", style="standard")
        sql = f"""
            SELECT
                a.id AS assignment_id,
                COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id) AS case_id,
                a.created_at AS assignment_created_at,
                a.employee_link_mode AS employee_link_mode,
                ec.company_id AS contact_company_id,
                rc.host_country AS host_country,
                rc.home_country AS home_country,
                COALESCE(rc.company_id, ec.company_id) AS company_id,
                c.name AS company_name
            FROM case_assignments a
            INNER JOIN employee_contacts ec ON ec.id = a.employee_contact_id
            LEFT JOIN relocation_cases rc ON {join_on}
            LEFT JOIN companies c ON CAST(c.id AS TEXT) = COALESCE(rc.company_id, ec.company_id)
            WHERE TRIM(COALESCE(ec.linked_auth_user_id, '')) = :uid
            AND a.employee_user_id IS NULL
            AND LOWER(TRIM(COALESCE(a.employee_link_mode, ''))) = 'pending_claim'
            AND (
                rc.id IS NULL
                OR TRIM(COALESCE(ec.company_id, '')) = ''
                OR TRIM(COALESCE(rc.company_id, '')) = ''
                OR CAST(rc.company_id AS TEXT) = CAST(ec.company_id AS TEXT)
            )
            ORDER BY a.created_at DESC
        """
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                sql,
                {"uid": uid},
                op_name="list_employee_pending_assignment_overview",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def get_unassigned_assignment_by_identifier(
        self,
        identifier: str,
        request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        ident = normalize_invite_key(identifier)
        if not ident:
            return None
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT a.* FROM case_assignments a "
                "LEFT JOIN employee_contacts ec ON ec.id = a.employee_contact_id "
                "WHERE a.employee_user_id IS NULL AND ( "
                "LOWER(TRIM(COALESCE(a.employee_identifier, ''))) = :ident "
                "OR ec.invite_key = :ident "
                ") "
                "ORDER BY a.created_at DESC LIMIT 1",
                {"ident": ident},
                op_name="get_unassigned_assignment_by_identifier",
                request_id=request_id,
            ).fetchone()
        return self._row_to_dict(row)

    def list_assignments_for_hr(self, hr_user_id: str, request_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        FALLBACK path: list assignments owned by an HR user who is NOT yet linked
        to any company (i.e. has no row in hr_users). Callers normally resolve a
        company_id first and call list_assignments_for_company; this function is
        only reached when that resolution returned None.

        The NOT EXISTS guard is a safety floor: if the HR user IS associated with
        any company (via hr_users), this returns empty instead of leaking across
        company boundaries. That forces the caller to go through the company-
        scoped path, where multi-tenant filtering is correct.
        """
        with self.engine.begin() as conn:
            # S4-fix: guard this fallback path with the same timeouts used by the
            # company-scoped path, so a slow NOT EXISTS subquery cannot hang forever.
            if not _is_sqlite:
                conn.execute(text("SET LOCAL statement_timeout = '7500ms'"))
                conn.execute(text("SET LOCAL lock_timeout = '5000ms'"))
            rows = self._exec(
                conn,
                "SELECT * FROM case_assignments "
                "WHERE hr_user_id = :hr "
                "AND archived_at IS NULL "
                "AND NOT EXISTS (SELECT 1 FROM hr_users WHERE profile_id = :hr) "
                "ORDER BY created_at DESC",
                {"hr": hr_user_id},
                op_name="list_assignments_for_hr",
                request_id=request_id,
            ).fetchall()
        if not rows:
            # Not necessarily an error — just worth a trace when the guard bites.
            log.info(
                "list_assignments_for_hr: 0 rows for hr_user_id=%s (guard rejects if user has any hr_users row)",
                hr_user_id[:8] if hr_user_id else "",
            )
        return self._rows_to_list(rows)

    def list_all_assignments(self) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT * FROM case_assignments ORDER BY created_at DESC")).fetchall()
        return self._rows_to_list(rows)

    def list_admin_assignments(
        self,
        company_id: Optional[str] = None,
        employee_user_id: Optional[str] = None,
        employee_search: Optional[str] = None,
        status: Optional[str] = None,
        destination_country: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List assignments for admin with filters. Joins case_assignments, relocation_cases, profiles, companies."""
        clauses = []
        params: Dict[str, Any] = {}
        if company_id:
            clauses.append("(rc.company_id = :company_id OR (rc.company_id IS NULL AND EXISTS (SELECT 1 FROM hr_users hu2 WHERE hu2.profile_id = a.hr_user_id AND hu2.company_id = :company_id)))")
            params["company_id"] = company_id
        if employee_user_id:
            clauses.append("a.employee_user_id = :employee_user_id")
            params["employee_user_id"] = employee_user_id
        if status:
            clauses.append("a.status = :status")
            params["status"] = status
        else:
            clauses.append("(COALESCE(TRIM(LOWER(a.status)), '') NOT IN ('archived', 'closed'))")
        if destination_country:
            clauses.append("LOWER(TRIM(COALESCE(rc.host_country, ''))) = LOWER(TRIM(:dest_country))")
            params["dest_country"] = destination_country
        if employee_search:
            esc = (employee_search or "").strip()
            pattern = f"%{esc}%"
            if _is_sqlite:
                clauses.append(
                    "(LOWER(COALESCE(a.employee_identifier, '')) LIKE LOWER(:emp_search) OR "
                    "LOWER(COALESCE(emp_p.full_name, '')) LIKE LOWER(:emp_search) OR "
                    "LOWER(COALESCE(a.employee_first_name, '')) LIKE LOWER(:emp_search) OR "
                    "LOWER(COALESCE(a.employee_last_name, '')) LIKE LOWER(:emp_search))"
                )
            else:
                clauses.append(
                    "(a.employee_identifier ILIKE :emp_search OR emp_p.full_name ILIKE :emp_search OR "
                    "a.employee_first_name ILIKE :emp_search OR a.employee_last_name ILIKE :emp_search)"
                )
            params["emp_search"] = pattern

        where_sql = "AND " + " AND ".join(clauses) if clauses else ""

        if _is_sqlite:
            join_on_cases = "rc.id = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"
        else:
            # Postgres: relocation_cases.id is uuid, case_assignments.case_id / canonical_case_id are text UUIDs.
            # Cast uuid to text for a safe, index-friendly join.
            join_on_cases = "rc.id::text = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"

        sql = f"""
            SELECT
                a.id, a.case_id, a.canonical_case_id, a.hr_user_id, a.employee_user_id, a.employee_identifier,
                a.status, a.employee_first_name, a.employee_last_name, a.expected_start_date, a.submitted_at,
                a.created_at, a.updated_at,
                rc.id AS case_pk, rc.company_id AS case_company_id, rc.host_country, rc.home_country,
                rc.status AS case_status, rc.stage,
                c.name AS company_name,
                emp_p.full_name AS employee_full_name, emp_p.company_id AS employee_profile_company_id,
                hr_p.full_name AS hr_full_name, hr_p.company_id AS hr_profile_company_id,
                hu.company_id AS hr_company_id,
                COALESCE(emp.company_id, emp_p.company_id::text) AS employee_company_id,
                ep.profile_json,
                rap.id AS resolved_policy_id,
                (SELECT COUNT(*) FROM company_policies cp WHERE cp.company_id = COALESCE(rc.company_id, hu.company_id) AND cp.extraction_status = 'extracted') AS company_policy_count,
                -- Count matrix-published policies too so the admin Policy
                -- column shows "Available" for companies that publish via
                -- the Compensation & Allowance matrix (policy_config_versions)
                -- and haven't uploaded a document-normalized policy. Without
                -- this, every matrix-only company reads as "None" even when
                -- employees already resolve against a published matrix.
                (SELECT COUNT(*) FROM policy_config_versions pcv
                    JOIN policy_configs pcfg ON pcfg.id = pcv.policy_config_id
                    WHERE pcfg.company_id = COALESCE(rc.company_id, hu.company_id)
                      AND pcv.status = 'published') AS matrix_policy_count
            FROM case_assignments a
            LEFT JOIN relocation_cases rc ON {join_on_cases}
            LEFT JOIN companies c ON CAST(c.id AS TEXT) = COALESCE(rc.company_id, (SELECT hu2.company_id FROM hr_users hu2 WHERE hu2.profile_id = a.hr_user_id LIMIT 1))
            LEFT JOIN profiles emp_p ON CAST(emp_p.id AS TEXT) = a.employee_user_id
            LEFT JOIN profiles hr_p ON CAST(hr_p.id AS TEXT) = a.hr_user_id
            LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
            LEFT JOIN employees emp ON emp.profile_id = a.employee_user_id
            LEFT JOIN wizard_employee_profiles ep ON ep.assignment_id = a.id
            LEFT JOIN resolved_assignment_policies rap ON rap.assignment_id = a.id
            WHERE 1=1 {where_sql}
            ORDER BY a.updated_at DESC, a.created_at DESC
        """

        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()

        result = []
        for row in rows:
            m = row._mapping
            r = dict(m)
            profile_json = r.get("profile_json")
            profile = self._json_load(profile_json) if profile_json else {}
            mp = profile.get("movePlan") or {}
            pa = profile.get("primaryApplicant") or {}
            assign = pa.get("assignment") or {}
            r["assignment_type"] = assign.get("type") or assign.get("assignmentType")
            r["move_date"] = mp.get("targetArrivalDate") or r.get("expected_start_date")
            dep = profile.get("dependents") or []
            has_spouse = bool(profile.get("spouse", {}).get("fullName"))
            r["family_status"] = "family" if (has_spouse or dep) else "single"
            r["destination_from_profile"] = mp.get("destination") if isinstance(mp.get("destination"), str) else None
            r["policy_resolved"] = bool(r.get("resolved_policy_id"))
            # Both canonical (document-normalized) and matrix-published
            # policies count as "company has a policy" for admin visibility.
            canon_count = r.get("company_policy_count") or 0
            matrix_count = r.get("matrix_policy_count") or 0
            r["company_has_policy"] = (canon_count + matrix_count) > 0
            r["company_has_matrix_policy"] = matrix_count > 0
            # Normalized fields for admin list
            r["assignment_id"] = r.get("id")
            r["company_id"] = r.get("case_company_id") or r.get("hr_company_id")
            r["destination_country"] = r.get("host_country") or r.get("destination_from_profile")
            r["orphan_employee"] = not (
                (r.get("employee_user_id") and str(r.get("employee_user_id")).strip())
                or (r.get("employee_identifier") and str(r.get("employee_identifier")).strip())
            )
            result.append(r)
        return result

    def get_admin_assignment_detail(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        """Full assignment context for admin detail: assignment, case, employee, HR, services, policy."""
        with self.engine.connect() as conn:
            join_on_cases = "rc.id = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)" if _is_sqlite else "rc.id::text = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"
            row = conn.execute(
                text(f"""
                    SELECT a.*, rc.id AS case_pk, rc.company_id AS case_company_id, rc.hr_user_id AS case_hr_user_id,
                        rc.host_country, rc.home_country, rc.status AS case_status, rc.stage, rc.profile_json AS case_profile_json,
                        c.name AS company_name,
                        emp_p.id AS emp_profile_id, emp_p.full_name AS employee_full_name, emp_p.email AS employee_email, emp_p.company_id AS employee_profile_company_id,
                        hr_p.id AS hr_profile_id, hr_p.full_name AS hr_full_name, hr_p.email AS hr_email, hr_p.company_id AS hr_profile_company_id,
                        hu.company_id AS hr_company_id, emp.company_id AS employee_company_id
                    FROM case_assignments a
                    LEFT JOIN relocation_cases rc ON {join_on_cases}
                    LEFT JOIN companies c ON CAST(c.id AS TEXT) = COALESCE(rc.company_id, (SELECT hu2.company_id FROM hr_users hu2 WHERE hu2.profile_id = a.hr_user_id LIMIT 1))
                    LEFT JOIN profiles emp_p ON CAST(emp_p.id AS TEXT) = a.employee_user_id
                    LEFT JOIN profiles hr_p ON CAST(hr_p.id AS TEXT) = a.hr_user_id
                    LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
                    LEFT JOIN employees emp ON emp.profile_id = a.employee_user_id
                    WHERE a.id = :aid
                """),
                {"aid": assignment_id},
            ).fetchone()
        if not row:
            return None
        out = dict(row._mapping)
        ep = self.get_employee_profile(assignment_id)
        out["employee_profile"] = ep
        out["case_services"] = self.list_case_services(assignment_id)
        out["resolved_policy"] = self.get_resolved_assignment_policy(assignment_id)
        comp_id = out.get("case_company_id") or out.get("hr_company_id")
        policies = self.list_company_policies(comp_id) if comp_id else []
        out["company_policies"] = [p for p in policies if (p.get("extraction_status") or "") == "extracted"]
        out["company_has_published_policy"] = len(out["company_policies"]) > 0
        return out

    def list_dossier_case_questions(self, case_id: str) -> List[Dict[str, Any]]:
        """Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM dossier_case_questions WHERE (canonical_case_id = :cid OR case_id = :cid) ORDER BY created_at ASC"
            ), {"cid": cid}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["options"] = self._json_load(item.get("options"))
            item["sources"] = self._json_load(item.get("sources"))
        return items

    def add_dossier_case_question(
        self,
        case_id: str,
        question_text: str,
        answer_type: str,
        options: Optional[Any],
        is_mandatory: bool,
        sources: Optional[Any],
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        row = {
            "id": str(uuid.uuid4()),
            "case_id": case_id,
            "question_text": question_text,
            "answer_type": answer_type,
            "options": json.dumps(options) if options is not None else None,
            "is_mandatory": 1 if is_mandatory else 0,
            "sources": json.dumps(sources) if sources is not None else None,
            "created_at": now,
        }
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO dossier_case_questions "
                "(id, case_id, question_text, answer_type, options, is_mandatory, sources, created_at) "
                "VALUES (:id, :case_id, :question_text, :answer_type, :options, :is_mandatory, :sources, :created_at)"
            ), row)
        return row

    def list_dossier_case_answers(self, case_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM dossier_case_answers WHERE (canonical_case_id = :cid OR case_id = :cid) AND user_id = :uid"
            ), {"cid": cid, "uid": user_id}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["answer"] = self._json_load(item.get("answer_json"))
        return items

    def upsert_dossier_case_answers(self, case_id: str, user_id: str, answers: List[Dict[str, Any]]) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            for ans in answers:
                payload = {
                    "id": ans.get("id") or str(uuid.uuid4()),
                    "cid": case_id,
                    "uid": user_id,
                    "qid": ans["case_question_id"],
                    "answer": json.dumps(ans["answer"]),
                    "answered_at": now,
                }
                conn.execute(text(
                    "INSERT INTO dossier_case_answers (id, case_id, user_id, case_question_id, answer_json, answered_at) "
                    "VALUES (:id, :cid, :uid, :qid, :answer, :answered_at) "
                    "ON CONFLICT(case_id, user_id, case_question_id) DO UPDATE SET "
                    "answer_json = excluded.answer_json, answered_at = excluded.answered_at"
                ), payload)

    def upsert_relocation_case(
        self,
        case_id: str,
        company_id: Optional[str],
        employee_id: Optional[str],
        status: Optional[str],
        stage: Optional[str],
        host_country: Optional[str],
        home_country: Optional[str],
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE relocation_cases SET company_id = :cid, employee_id = :eid, status = :status, "
                "stage = :stage, host_country = :host, home_country = :home, updated_at = :now "
                "WHERE id = :id"
            ), {
                "id": case_id,
                "cid": company_id,
                "eid": employee_id,
                "status": status,
                "stage": stage,
                "host": host_country,
                "home": home_country,
                "now": now,
            })

    def set_relocation_case_status(self, case_id: str, status: str) -> int:
        """Status-only transition for a relocation case (e.g. reactivate). Unlike
        upsert_relocation_case — which UPDATEs every column and null-overwrites
        company_id/employee_id/stage/countries when called with just a status — this
        touches ONLY status + updated_at. Returns the number of rows updated (0 when no
        case matches the id), so callers can report honestly instead of faking success."""
        now = datetime.utcnow().isoformat()
        # relocation_cases.id is UUID in prod; cast to text so a string id compares (matches
        # get_case_by_id). SQLite ids are text already.
        where = "id = :id" if _is_sqlite else "id::text = :id"
        with self.engine.begin() as conn:
            res = conn.execute(
                text(f"UPDATE relocation_cases SET status = :status, updated_at = :now WHERE {where}"),
                {"id": case_id, "status": status, "now": now},
            )
            return res.rowcount or 0

    def create_support_case(
        self,
        support_case_id: str,
        company_id: str,
        created_by_profile_id: str,
        category: str,
        severity: str,
        status: str,
        summary: Optional[str],
        employee_id: Optional[str] = None,
        hr_profile_id: Optional[str] = None,
        last_error_code: Optional[str] = None,
        last_error_context: Optional[Dict[str, Any]] = None,
        priority: Optional[str] = None,
        assignee_id: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        prio = (priority or "medium").lower() if priority else "medium"
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO support_cases "
                "(id, company_id, created_by_profile_id, employee_id, hr_profile_id, category, severity, status, summary, last_error_code, last_error_context_json, created_at, updated_at, priority, assignee_id) "
                "VALUES (:id, :cid, :cbp, :eid, :hid, :cat, :sev, :status, :summary, :err, :ctx, :created_at, :updated_at, :priority, :assignee_id) "
                "ON CONFLICT(id) DO UPDATE SET company_id = excluded.company_id, status = excluded.status, summary = excluded.summary, "
                "last_error_code = excluded.last_error_code, last_error_context_json = excluded.last_error_context_json, updated_at = excluded.updated_at, priority = excluded.priority, assignee_id = excluded.assignee_id"
            ), {
                "id": support_case_id,
                "cid": company_id,
                "cbp": created_by_profile_id,
                "eid": employee_id,
                "hid": hr_profile_id,
                "cat": category,
                "sev": severity,
                "status": status,
                "summary": summary,
                "err": last_error_code,
                "ctx": json.dumps(last_error_context or {}),
                "created_at": now,
                "updated_at": now,
                "priority": prio,
                "assignee_id": assignee_id,
            })

    def list_relocation_cases(self, company_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        clauses = []
        if company_id:
            clauses.append("company_id = :cid")
            params["cid"] = company_id
        if status:
            clauses.append("status = :status")
            params["status"] = status
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                f"SELECT * FROM relocation_cases {where} ORDER BY updated_at DESC"
            ), params).fetchall()
        return self._rows_to_list(rows)

    def get_relocation_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM relocation_cases WHERE id = :id"),
                {"id": case_id},
            ).fetchone()
        return self._row_to_dict(row)

    def list_support_cases(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        company_id: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        clauses = []
        if status:
            clauses.append("status = :status")
            params["status"] = status
        if severity:
            clauses.append("severity = :severity")
            params["severity"] = severity
        if company_id:
            clauses.append("company_id = :cid")
            params["cid"] = company_id
        if priority:
            clauses.append("priority = :priority")
            params["priority"] = priority
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                f"SELECT * FROM support_cases {where} ORDER BY updated_at DESC"
            ), params).fetchall()
        return self._rows_to_list(rows)

    def update_support_case(
        self,
        support_case_id: str,
        *,
        priority: Optional[str] = None,
        status: Optional[str] = None,
        assignee_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update ticket fields: priority (low|medium|high|urgent), status (open|investigating|blocked|resolved), assignee_id, category."""
        updates = []
        params: Dict[str, Any] = {"id": support_case_id, "now": datetime.utcnow().isoformat()}
        if priority is not None:
            updates.append("priority = :priority")
            params["priority"] = priority
        if status is not None:
            updates.append("status = :status")
            params["status"] = status
        if assignee_id is not None:
            updates.append("assignee_id = :assignee_id")
            params["assignee_id"] = assignee_id
        if category is not None:
            updates.append("category = :category")
            params["category"] = category
        if not updates:
            return self.get_support_case(support_case_id)
        updates.append("updated_at = :now")
        with self.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE support_cases SET {', '.join(updates)} WHERE id = :id"),
                params,
            )
        return self.get_support_case(support_case_id)

    def get_support_case(self, support_case_id: str) -> Optional[Dict[str, Any]]:
        """Get a single support case by id."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM support_cases WHERE id = :id"),
                {"id": support_case_id},
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_command_center_cases(
        self,
        company_id: Optional[str] = None,
        hr_user_id: Optional[str] = None,
        page: int = 1,
        limit: int = 25,
        risk_filter: Optional[str] = None,
        sla_thresholds_for: Optional[
            Callable[[Optional[str], Optional[str]], Optional[Tuple[int, int]]]
        ] = None,
    ) -> List[Dict[str, Any]]:
        """Paginated cases with task %% and risk. Prefer company_id; fallback hr_user_id; None = admin.

        I-3 Stage 4: ``sla_thresholds_for(origin, dest) -> (window_days, pct) | None``
        is an optional app-layer callback letting each row use a corridor-specific
        timeline-SLA override; None (or absent) keeps the sla_rules defaults — the
        DB layer never imports app/.
        """
        try:
            rc_join = self._command_center_join_relocation_cases()
            wc_join = self._command_center_join_wizard_cases()
            dest_sql = self._command_center_dest_country_sql()
            with self.engine.connect() as conn:
                params: Dict[str, Any] = {"limit": limit, "offset": (page - 1) * limit}
                # Shared additional projections: origin country, owner full name,
                # employee role/band, household composition + visa-surrogate. All
                # LEFT joins so missing rows just yield NULLs. Household fields
                # land on wizard_cases via 20260502110000_s4_family_details;
                # move_type / contract_type via 20260502100000_s3_contract_move_type.
                extra_select = (
                    "wc.origin_country as wizard_origin_country, "
                    "wc.dest_country as wizard_dest_country, "
                    "wc.target_move_date as wizard_target_move_date, "
                    "wc.purpose as wizard_purpose, "
                    "wc.move_type as wizard_move_type, "
                    "wc.contract_type as wizard_contract_type, "
                    "wc.has_spouse as wizard_has_spouse, "
                    "wc.child_count as wizard_child_count, "
                    "wc.partner_requires_visa as wizard_partner_requires_visa, "
                    "hp.full_name as hr_owner_name, "
                    "hp.email as hr_owner_email, "
                    "emp.band as employee_band, "
                    "emp.assignment_type as employee_assignment_type"
                )
                extra_joins = (
                    "LEFT JOIN profiles hp ON CAST(hp.id AS TEXT) = ca.hr_user_id "
                    "LEFT JOIN employees emp ON emp.profile_id = ca.employee_user_id"
                )
                if company_id:
                    where = "WHERE " + self._command_center_company_where()
                    params["cid"] = company_id
                    sql = f"""
                        SELECT ca.id, ca.case_id, ca.employee_identifier, ca.status,
                               COALESCE(ca.risk_status, 'green') as risk_status,
                               ca.budget_limit, ca.budget_estimated, ca.expected_start_date,
                               ca.updated_at,
                               {dest_sql} as dest_country,
                               {extra_select}
                        FROM case_assignments ca
                        LEFT JOIN relocation_cases rc ON {rc_join}
                        LEFT JOIN wizard_cases wc ON {wc_join}
                        LEFT JOIN hr_users hu ON hu.profile_id = ca.hr_user_id
                        {extra_joins}
                        {where}
                    """
                elif hr_user_id:
                    # Fallback only for HR users without a company association.
                    # NOT EXISTS guard: if the user has any hr_users row, this
                    # returns empty rather than leaking across companies.
                    where = (
                        "WHERE ca.hr_user_id = :hr "
                        "AND ca.archived_at IS NULL "
                        "AND NOT EXISTS (SELECT 1 FROM hr_users WHERE profile_id = :hr)"
                    )
                    params["hr"] = hr_user_id
                    sql = f"""
                        SELECT ca.id, ca.case_id, ca.employee_identifier, ca.status,
                               COALESCE(ca.risk_status, 'green') as risk_status,
                               ca.budget_limit, ca.budget_estimated, ca.expected_start_date,
                               ca.updated_at,
                               {dest_sql} as dest_country,
                               {extra_select}
                        FROM case_assignments ca
                        LEFT JOIN relocation_cases rc ON {rc_join}
                        LEFT JOIN wizard_cases wc ON {wc_join}
                        {extra_joins}
                        {where}
                    """
                else:
                    sql = f"""
                        SELECT ca.id, ca.case_id, ca.employee_identifier, ca.status,
                               COALESCE(ca.risk_status, 'green') as risk_status,
                               ca.budget_limit, ca.budget_estimated, ca.expected_start_date,
                               ca.updated_at,
                               {dest_sql} as dest_country,
                               {extra_select}
                        FROM case_assignments ca
                        LEFT JOIN relocation_cases rc ON {rc_join}
                        LEFT JOIN wizard_cases wc ON {wc_join}
                        {extra_joins}
                        WHERE 1=1
                    """
                # The e2e/verify suites provision synthetic personas (…@testco.com)
                # against PROD on every run, so they reappear within minutes of any
                # purge. The admin Companies list already excludes them at read
                # time; the HR command center did not, so they polluted the case
                # list and every portfolio count derived from it. Same filter, same
                # seam as risk_filter — every branch above ends in a WHERE clause.
                from .test_data_filter import exclude_test_people

                sql = sql.rstrip() + " AND " + exclude_test_people("ca.employee_identifier")
                if risk_filter:
                    sql = sql.rstrip() + " AND COALESCE(ca.risk_status, 'green') = :risk"
                    params["risk"] = risk_filter
                sql += " ORDER BY ca.updated_at DESC LIMIT :limit OFFSET :offset"
                rows = conn.execute(text(sql), params).fetchall()

            a_ids = [r._mapping["id"] for r in rows]
            task_stats: Dict[str, Dict[str, Any]] = {}
            if a_ids:
                try:
                    with self.engine.connect() as conn:
                        placeholders = ", ".join(f":a{i}" for i in range(len(a_ids)))
                        tr = conn.execute(
                            text(
                                f"SELECT assignment_id, status, due_date FROM relocation_tasks "
                                f"WHERE assignment_id IN ({placeholders})"
                            ),
                            {f"a{i}": aid for i, aid in enumerate(a_ids)},
                        ).fetchall()
                        for r in tr:
                            m = r._mapping
                            aid = m["assignment_id"]
                            if aid not in task_stats:
                                task_stats[aid] = {"total": 0, "done": 0, "next_overdue": None}
                            task_stats[aid]["total"] += 1
                            if m.get("status") == "done":
                                task_stats[aid]["done"] += 1
                            elif m.get("status") == "overdue" and m.get("due_date"):
                                cur = task_stats[aid]["next_overdue"]
                                task_stats[aid]["next_overdue"] = min(cur, m["due_date"]) if cur else m["due_date"]
                except Exception:
                    pass

            # [P4-1] Dossier health: aggregate case_forms per case_id
            dossier_stats: Dict[str, Dict[str, Any]] = {}
            case_ids = [r._mapping.get("case_id") for r in rows if r._mapping.get("case_id")]
            if case_ids:
                try:
                    with self.engine.connect() as conn:
                        placeholders = ", ".join(f":c{i}" for i in range(len(case_ids)))
                        dr = conn.execute(
                            text(
                                f"SELECT cf.case_id, COUNT(cf.id) AS total_forms, "
                                f"ROUND(AVG(cf.completion_pct)) AS avg_completion, "
                                f"SUM(CASE WHEN cf.status IN ('ready','submitted','approved') THEN 1 ELSE 0 END) AS ready_count, "
                                f"SUM(CASE WHEN cf.status IN ('in_progress','auto_filled') THEN 1 ELSE 0 END) AS action_count, "
                                f"SUM(CASE WHEN cf.blocker_form_id IS NOT NULL "
                                f"    AND cf.status NOT IN ('submitted','approved','rejected') THEN 1 ELSE 0 END) AS blocked_count "
                                f"FROM public.case_forms cf "
                                f"WHERE cf.case_id IN ({placeholders}) "
                                f"GROUP BY cf.case_id"
                            ),
                            {f"c{i}": cid for i, cid in enumerate(case_ids)},
                        ).fetchall()
                        for r in dr:
                            m = r._mapping
                            dossier_stats[str(m["case_id"])] = {
                                "total_forms": int(m.get("total_forms") or 0),
                                "avg_completion": int(m.get("avg_completion") or 0),
                                "ready_count": int(m.get("ready_count") or 0),
                                "action_count": int(m.get("action_count") or 0),
                                "blocked_count": int(m.get("blocked_count") or 0),
                            }
                except Exception:
                    pass

            result = []
            for row in rows:
                m = row._mapping
                a_id = m["id"]
                stats = task_stats.get(a_id, {"total": 0, "done": 0, "next_overdue": None})
                dh = dossier_stats.get(str(m.get("case_id") or ""), {})
                pct = round(100 * stats["done"] / stats["total"]) if stats["total"] else 0
                wiz_o = m.get("wizard_origin_country")
                wiz_d = m.get("wizard_dest_country")
                display_status = self._command_center_display_status(m.get("status"), wiz_o, wiz_d)
                # W2-2: timeline SLA from the target move date + task progress.
                # I-3 Stage 4: corridor-specific at-risk thresholds when the
                # injected resolver supplies them (else sla_rules defaults).
                _sla_window = _sla_pct = None
                if sla_thresholds_for is not None:
                    _ovr = sla_thresholds_for(wiz_o, wiz_d)
                    if _ovr:
                        _sla_window, _sla_pct = _ovr
                sla_status, days_until_move = compute_sla_status(
                    m.get("wizard_target_move_date"), pct, display_status,
                    at_risk_window_days=_sla_window, at_risk_pct=_sla_pct,
                )
                next_d = stats["next_overdue"]
                if not next_d and m.get("expected_start_date"):
                    next_d = m.get("expected_start_date")
                if not next_d and m.get("wizard_target_move_date"):
                    next_d = m.get("wizard_target_move_date")
                dest = m.get("dest_country")
                if dest is not None and isinstance(dest, str) and not dest.strip():
                    dest = None
                origin = m.get("wizard_origin_country")
                if origin is not None and isinstance(origin, str) and not origin.strip():
                    origin = None
                owner_name = m.get("hr_owner_name") or None
                if isinstance(owner_name, str) and not owner_name.strip():
                    owner_name = None
                if not owner_name:
                    # Fallback to email local-part so the column never reads "Unassigned"
                    # for HR users whose profile.full_name hasn't been backfilled.
                    email = m.get("hr_owner_email") or ""
                    if isinstance(email, str) and "@" in email:
                        owner_name = email.split("@", 1)[0]
                employee_role = m.get("employee_band") or m.get("employee_assignment_type") or None
                if isinstance(employee_role, str) and not employee_role.strip():
                    employee_role = None

                # Visa label — sourced from the employee's intake wizard (AIQ-1135).
                # `purpose` is the wizard's relocation-purpose field and the most
                # visa-relevant signal, so it's preferred; move_type / contract_type
                # (also wizard) and the employees-table assignment_type are fallbacks.
                # None of these is a real visa-program enum (the prototype mock showed
                # "Skilled Worker", "EU Blue Card", "L-1A", etc.) — they're the closest
                # first-class fields the wizard captures today.
                visa_label = (
                    m.get("wizard_purpose")
                    or m.get("wizard_move_type")
                    or m.get("wizard_contract_type")
                    or m.get("employee_assignment_type")
                    or None
                )
                if isinstance(visa_label, str) and not visa_label.strip():
                    visa_label = None

                # Household composition from wizard family fields.
                #   None  → not asked yet
                #   "Solo"        → no spouse, no kids
                #   "Partner"     → spouse only
                #   "N kids"      → no spouse, kids only
                #   "Partner + N kids" → both
                has_spouse = bool(m.get("wizard_has_spouse"))
                try:
                    child_count = int(m.get("wizard_child_count") or 0)
                except (TypeError, ValueError):
                    child_count = 0
                household_label: Optional[str]
                if not has_spouse and child_count == 0:
                    household_label = None  # Treat zeros as "unanswered" to avoid claiming "Solo" prematurely
                elif has_spouse and child_count == 0:
                    household_label = "Partner"
                elif not has_spouse and child_count > 0:
                    household_label = f"{child_count} kid{'s' if child_count != 1 else ''}"
                else:
                    household_label = f"Partner + {child_count} kid{'s' if child_count != 1 else ''}"

                result.append({
                    "id": a_id,
                    "caseId": m.get("case_id") or None,
                    "employeeIdentifier": m.get("employee_identifier") or "",
                    "employeeRole": employee_role,
                    "originCountry": origin,
                    "destCountry": dest,
                    "status": display_status,
                    "riskStatus": m.get("risk_status") or "green",
                    "tasksDonePercent": pct,
                    "budgetLimit": m.get("budget_limit"),
                    "budgetEstimated": m.get("budget_estimated"),
                    "nextDeadline": str(next_d) if next_d else None,
                    "targetMoveDate": str(m.get("wizard_target_move_date")) if m.get("wizard_target_move_date") else None,
                    "ownerName": owner_name,
                    "updatedAt": str(m.get("updated_at")) if m.get("updated_at") else None,
                    # New: visa surrogate + household composition (both may be None).
                    "visaLabel": visa_label,
                    "household": household_label,
                    "hasSpouse": has_spouse,
                    "childCount": child_count,
                    # W2-2: timeline SLA (on_track | at_risk | overdue | None) + signed days to move.
                    "slaStatus": sla_status,
                    "daysUntilMove": days_until_move,
                    # [P4-1] dossier health
                    **{
                        "dossierTotalForms": dh.get("total_forms", 0),
                        "dossierAvgCompletion": dh.get("avg_completion", 0),
                        "dossierReadyCount": dh.get("ready_count", 0),
                        "dossierActionCount": dh.get("action_count", 0),
                        "dossierBlockedCount": dh.get("blocked_count", 0),
                    }
                })
            return result
        except Exception as e:
            log.warning("list_command_center_cases: %s", e)
            return []

    def get_command_center_case_detail(
        self,
        assignment_id: str,
        company_id: Optional[str] = None,
        hr_user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Full case detail: tasks, budget, events."""
        try:
            rc_join = self._command_center_join_relocation_cases()
            wc_join = self._command_center_join_wizard_cases()
            dest_sql = self._command_center_dest_country_sql()
            with self.engine.connect() as conn:
                params: Dict[str, Any] = {"aid": assignment_id}
                if company_id:
                    where = "ca.id = :aid AND " + self._command_center_company_where()
                    params["cid"] = company_id
                    sql = f"""
                        SELECT ca.*, {dest_sql} as intake_dest_country,
                               wc.origin_country as wizard_origin_country,
                               wc.dest_country as wizard_dest_country,
                               wc.dest_city as wizard_dest_city,
                               wc.target_move_date as wizard_target_move_date
                        FROM case_assignments ca
                        LEFT JOIN relocation_cases rc ON {rc_join}
                        LEFT JOIN wizard_cases wc ON {wc_join}
                        LEFT JOIN hr_users hu ON hu.profile_id = ca.hr_user_id
                        WHERE {where}
                    """
                elif hr_user_id:
                    # Fallback only for HR users without a company association.
                    # NOT EXISTS guard: if the user has any hr_users row, this
                    # returns nothing rather than leaking an assignment from
                    # another company (see list_assignments_for_hr).
                    where = (
                        "ca.id = :aid AND ca.hr_user_id = :hr "
                        "AND ca.archived_at IS NULL "
                        "AND NOT EXISTS (SELECT 1 FROM hr_users WHERE profile_id = :hr)"
                    )
                    params["hr"] = hr_user_id
                    sql = f"""
                        SELECT ca.*, {dest_sql} as intake_dest_country,
                               wc.origin_country as wizard_origin_country,
                               wc.dest_country as wizard_dest_country,
                               wc.dest_city as wizard_dest_city,
                               wc.target_move_date as wizard_target_move_date
                        FROM case_assignments ca
                        LEFT JOIN relocation_cases rc ON {rc_join}
                        LEFT JOIN wizard_cases wc ON {wc_join}
                        WHERE {where}
                    """
                else:
                    sql = f"""
                        SELECT ca.*, {dest_sql} as intake_dest_country,
                               wc.origin_country as wizard_origin_country,
                               wc.dest_country as wizard_dest_country,
                               wc.dest_city as wizard_dest_city,
                               wc.target_move_date as wizard_target_move_date
                        FROM case_assignments ca
                        LEFT JOIN relocation_cases rc ON {rc_join}
                        LEFT JOIN wizard_cases wc ON {wc_join}
                        WHERE ca.id = :aid
                    """
                row = conn.execute(text(sql), params).fetchone()
                if not row:
                    return None
                m = row._mapping
                tasks = []
                try:
                    tr = conn.execute(text(
                        "SELECT * FROM relocation_tasks WHERE assignment_id = :aid ORDER BY due_date"
                    ), {"aid": assignment_id}).fetchall()
                    tasks = self._rows_to_list(tr)
                except Exception:
                    pass
                events = []
                try:
                    er = conn.execute(text(
                        "SELECT * FROM case_events WHERE assignment_id = :aid ORDER BY created_at DESC LIMIT 50"
                    ), {"aid": assignment_id}).fetchall()
                    events = self._rows_to_list(er)
                except Exception:
                    pass
                tasks_done = sum(1 for t in tasks if t.get("status") == "done")
                tasks_overdue = sum(1 for t in tasks if t.get("status") == "overdue")
                phases: Dict[str, List[Dict]] = {}
                for t in tasks:
                    ph = t.get("phase") or "General"
                    if ph not in phases:
                        phases[ph] = []
                    phases[ph].append({"title": t.get("title"), "status": t.get("status"), "due_date": t.get("due_date")})
                dest_val = m.get("intake_dest_country")
                if dest_val is not None and isinstance(dest_val, str) and not dest_val.strip():
                    dest_val = None
                # [AIQ-1336] city-level destination from the intake source of truth.
                dest_city_val = m.get("wizard_dest_city")
                if isinstance(dest_city_val, str) and not dest_city_val.strip():
                    dest_city_val = None
                display_status = self._command_center_display_status(
                    m.get("status"),
                    m.get("wizard_origin_country"),
                    m.get("wizard_dest_country"),
                )
                exp_start = m.get("expected_start_date") or m.get("wizard_target_move_date")
                return {
                    "id": assignment_id,
                    "caseId": m.get("case_id") or None,
                    "employeeIdentifier": m.get("employee_identifier") or "",
                    "destCountry": dest_val,
                    "destCity": dest_city_val,
                    "status": display_status,
                    "riskStatus": m.get("risk_status") or "green",
                    "budgetLimit": m.get("budget_limit"),
                    "budgetEstimated": m.get("budget_estimated"),
                    "expectedStartDate": str(exp_start) if exp_start else None,
                    "tasksTotal": len(tasks),
                    "tasksDone": tasks_done,
                    "tasksOverdue": tasks_overdue,
                    "phases": [{"phase": k, "tasks": v} for k, v in phases.items()],
                    "events": [{"event_type": e.get("event_type"), "description": e.get("description"), "created_at": e.get("created_at")} for e in events],
                }
        except Exception as e:
            log.warning("get_command_center_case_detail: %s", e)
            return None

    def delete_assignment(self, assignment_id: str, *, actor_id: Optional[str] = None) -> bool:
        """
        Soft-delete an assignment and its parent relocation case.

        Sets archived_at on both rows; revokes the ephemeral invites (those are
        never customer data). Writes audit_logs rows for both entities so the
        deletion is investigable.

        Returns True on success, False if the assignment did not exist or was
        already archived (idempotent).
        """
        from .app.services.audit_log_service import (
            insert_audit_log,
            ACTION_DELETE,
            ACTOR_HUMAN,
            ACTOR_SYSTEM,
        )
        from ._time import utcnow_iso_naive
        now = utcnow_iso_naive()
        with self.engine.begin() as conn:
            row = conn.execute(text(
                "SELECT * FROM case_assignments WHERE id = :id AND archived_at IS NULL"
            ), {"id": assignment_id}).fetchone()
            if not row:
                return False
            assignment_snapshot = self._row_to_dict(row) or {}
            case_id = assignment_snapshot.get("case_id")
            case_snapshot: Dict[str, Any] = {}
            if case_id:
                case_row = conn.execute(text(
                    "SELECT * FROM relocation_cases WHERE id = :cid AND archived_at IS NULL"
                ), {"cid": case_id}).fetchone()
                case_snapshot = self._row_to_dict(case_row) or {}

            # Invites are ephemeral credentials for onboarding; hard-delete is safe.
            try:
                conn.execute(
                    text("DELETE FROM assignment_claim_invites WHERE assignment_id = :aid"),
                    {"aid": assignment_id},
                )
            except (OperationalError, ProgrammingError):
                pass
            try:
                conn.execute(
                    text("DELETE FROM assignment_invites WHERE case_id = :cid"),
                    {"cid": case_id},
                )
            except (OperationalError, ProgrammingError):
                pass

            # Soft-delete assignment + parent case.
            conn.execute(
                text("UPDATE case_assignments SET archived_at = :now, updated_at = :now WHERE id = :id"),
                {"now": now, "id": assignment_id},
            )
            if case_id:
                conn.execute(
                    text("UPDATE relocation_cases SET archived_at = :now, updated_at = :now WHERE id = :cid"),
                    {"now": now, "cid": case_id},
                )

            # Audit trail — one row per entity.
            actor_type = ACTOR_HUMAN if actor_id else ACTOR_SYSTEM
            try:
                insert_audit_log(
                    conn,
                    entity_type="case_assignment",
                    entity_id=assignment_id,
                    action_type=ACTION_DELETE,
                    old_value=assignment_snapshot,
                    new_value={"archived_at": now},
                    actor_type=actor_type,
                    actor_id=actor_id,
                )
                if case_id and case_snapshot:
                    insert_audit_log(
                        conn,
                        entity_type="relocation_case",
                        entity_id=case_id,
                        action_type=ACTION_DELETE,
                        old_value=case_snapshot,
                        new_value={"archived_at": now},
                        actor_type=actor_type,
                        actor_id=actor_id,
                    )
            except Exception as audit_exc:
                # Audit is best-effort — never block the delete on audit failure,
                # but log loudly so we can find silent drops.
                log.warning(
                    "delete_assignment audit insert failed (aid=%s cid=%s): %s",
                    assignment_id[:8], (case_id or "")[:8], audit_exc,
                )
        return True

    # ==================================================================
    # Assignment invites (legacy `assignment_invites` + canonical `assignment_claim_invites`)
    # ==================================================================
    # New HR/Admin flows must use `ensure_pending_assignment_invites` only (writes both tables in sync).
    # Do not add standalone `create_assignment_invite` call sites for product features.

    def get_resolved_assignment_policy(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM resolved_assignment_policies WHERE assignment_id = :aid"),
                {"aid": assignment_id},
            ).fetchone()
        d = self._row_to_dict(row)
        if d:
            self._parse_json_col(d, "resolution_context_json")
        return d

    def upsert_resolved_assignment_policy(
        self,
        assignment_id: str,
        case_id: Optional[str],
        company_id: str,
        policy_id: str,
        policy_version_id: str,
        canonical_case_id: Optional[str],
        resolution_status: str,
        resolution_context: Dict[str, Any],
        benefits: List[Dict[str, Any]],
        exclusions: List[Dict[str, Any]],
    ) -> str:
        now = datetime.utcnow().isoformat()
        with self.engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id FROM resolved_assignment_policies WHERE assignment_id = :aid"),
                {"aid": assignment_id},
            ).fetchone()
        rid = str(uuid.uuid4()) if not existing else existing._mapping["id"]
        with self.engine.begin() as conn:
            if existing:
                conn.execute(text(f"""
                    UPDATE resolved_assignment_policies SET
                    case_id = :cid, company_id = :coid, policy_id = :pid, policy_version_id = :vid,
                    canonical_case_id = :ccid, resolution_status = :status, resolved_at = :now,
                    resolution_context_json = {_jbind('ctx')}, updated_at = :now
                    WHERE assignment_id = :aid
                """), {
                    "aid": assignment_id, "cid": case_id, "coid": company_id, "pid": policy_id,
                    "vid": policy_version_id, "ccid": canonical_case_id, "status": resolution_status,
                    "now": now, "ctx": json.dumps(resolution_context),
                })
                conn.execute(text("DELETE FROM resolved_assignment_policy_benefits WHERE resolved_policy_id = :rid"), {"rid": rid})
                conn.execute(text("DELETE FROM resolved_assignment_policy_exclusions WHERE resolved_policy_id = :rid"), {"rid": rid})
            else:
                conn.execute(text(f"""
                    INSERT INTO resolved_assignment_policies
                    (id, assignment_id, case_id, company_id, policy_id, policy_version_id, canonical_case_id,
                     resolution_status, resolved_at, resolution_context_json, created_at, updated_at)
                    VALUES (:id, :aid, :cid, :coid, :pid, :vid, :ccid, :status, :now, {_jbind('ctx')}, :now, :now)
                """), {
                    "id": rid, "aid": assignment_id, "cid": case_id, "coid": company_id, "pid": policy_id,
                    "vid": policy_version_id, "ccid": canonical_case_id, "status": resolution_status,
                    "now": now, "ctx": json.dumps(resolution_context),
                })
            for b in benefits:
                bid = str(uuid.uuid4())
                inc = b.get("included", True)
                apr = b.get("approval_required", False)
                if not isinstance(inc, bool):
                    inc = bool(inc)
                if not isinstance(apr, bool):
                    apr = bool(apr)
                conn.execute(text(f"""
                    INSERT INTO resolved_assignment_policy_benefits
                    (id, resolved_policy_id, benefit_key, included, min_value, standard_value, max_value,
                     currency, amount_unit, frequency, approval_required, evidence_required_json,
                     exclusions_json, condition_summary, source_rule_ids_json, created_at, updated_at)
                    VALUES (:id, :rid, :bk, :inc, :minv, :stdv, :maxv, :cur, :au, :freq, :apr,
                            {_jbind('evj')}, {_jbind('exj')}, :cs, {_jbind('srj')}, :now, :now)
                """), {
                    "id": bid, "rid": rid, "bk": b["benefit_key"], "inc": inc,
                    "minv": b.get("min_value"), "stdv": b.get("standard_value"), "maxv": b.get("max_value"),
                    "cur": b.get("currency"), "au": b.get("amount_unit"), "freq": b.get("frequency"),
                    "apr": apr,
                    "evj": json.dumps(b.get("evidence_required_json") or []),
                    "exj": json.dumps(b.get("exclusions_json") or []),
                    "cs": b.get("condition_summary"), "srj": json.dumps(b.get("source_rule_ids_json") or []),
                    "now": now,
                })
            for e in exclusions:
                eid = str(uuid.uuid4())
                conn.execute(text(f"""
                    INSERT INTO resolved_assignment_policy_exclusions
                    (id, resolved_policy_id, benefit_key, domain, description, source_rule_ids_json)
                    VALUES (:id, :rid, :bk, :dom, :desc, {_jbind('srj')})
                """), {
                    "id": eid, "rid": rid, "bk": e.get("benefit_key"), "dom": e["domain"],
                    "desc": e.get("description"), "srj": json.dumps(e.get("source_rule_ids_json") or []),
                })
        return rid

    # ==================================================================
    # Case Readiness Core v1
    # ==================================================================

    def resolve_readiness_destination_for_assignment(self, assignment_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Returns (destination_raw, destination_key) for the assignment.

        Priority:
          1. Employee profile (intake form) — most recent first-party answer
          2. Canonical `relocation_cases.host_country` column — set by the
             intake/admin flow and updated on reassignment
          3. Case `profile_json.movePlan.destination` — historical blob,
             may be stale (e.g. assignment was reassigned but the blob was
             never re-saved)

        The blob is the LAST fallback, not the first, because we have seen
        cases where it disagrees with the canonical column (e.g. monica's
        case had host_country="Japan" but profile_json said "Singapore",
        causing the readiness summary to mislabel a Japan assignment with
        a Singapore template).
        """
        prof = self.get_employee_profile(assignment_id)
        raw = extract_destination_from_profile(prof)
        # Fall back when the profile destination is MISSING *or* doesn't normalise to a
        # country key — e.g. a city-only value like "Amsterdam" with no country (AIQ-1321).
        # The old `if not raw` only caught the empty case, so a truthy-but-unnormalisable
        # value short-circuited to no_destination instead of using the canonical host_country.
        if not normalize_destination_key(raw):
            asn = self.get_assignment_by_id(assignment_id)
            if asn:
                cid = (asn.get("case_id") or "").strip()
                case = self.get_case_by_id(cid) if cid else None
                if case:
                    host = str(case.get("host_country") or "").strip() or None
                    if normalize_destination_key(host):
                        raw = host
                    else:
                        # Last-resort fallback to the historical blob.
                        blob = extract_destination_from_case_profile(case.get("profile_json"))
                        if normalize_destination_key(blob):
                            raw = blob
        key = normalize_destination_key(raw)
        return raw, key

    def ensure_case_readiness_binding(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        """Create case_readiness row pointing at resolved template; no template duplication."""
        asn = self.get_assignment_by_id(assignment_id)
        if not asn:
            return None
        prof = self.get_employee_profile(assignment_id)
        _, dest_key = self.resolve_readiness_destination_for_assignment(assignment_id)
        route_key = resolve_readiness_route_key(asn, prof)
        if not dest_key:
            return None
        tmpl = self.get_readiness_template(dest_key, route_key)
        if not tmpl:
            return None
        tid = tmpl["id"]
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            row = conn.execute(
                text("SELECT * FROM case_readiness WHERE assignment_id = :aid"),
                {"aid": assignment_id},
            ).fetchone()
            if row:
                d = dict(row._mapping)
                if d.get("template_id") != tid:
                    conn.execute(
                        text(
                            "UPDATE case_readiness SET template_id = :tid, destination_key = :dk, "
                            "route_key = :rk, updated_at = :ua WHERE assignment_id = :aid"
                        ),
                        {"tid": tid, "dk": dest_key, "rk": route_key, "ua": now, "aid": assignment_id},
                    )
                row2 = conn.execute(
                    text("SELECT * FROM case_readiness WHERE assignment_id = :aid"), {"aid": assignment_id}
                ).fetchone()
                return self._row_to_dict(row2) if row2 else None
            conn.execute(
                text(
                    "INSERT INTO case_readiness (assignment_id, template_id, destination_key, route_key, updated_at) "
                    "VALUES (:aid, :tid, :dk, :rk, :ua)"
                ),
                {"aid": assignment_id, "tid": tid, "dk": dest_key, "rk": route_key, "ua": now},
            )
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM case_readiness WHERE assignment_id = :aid"), {"aid": assignment_id}).fetchone()
        return self._row_to_dict(row) if row else None

    def upsert_readiness_milestone_state(
        self, assignment_id: str, template_milestone_id: str, completed: bool, notes: Optional[str] = None
    ) -> None:
        now = datetime.utcnow().isoformat()
        completed_at = now if completed else None
        with self.engine.begin() as conn:
            if _is_sqlite:
                conn.execute(
                    text(
                        """
                        INSERT INTO case_readiness_milestone_state
                        (assignment_id, template_milestone_id, completed_at, notes, updated_at)
                        VALUES (:aid, :mid, :cat, :notes, :ua)
                        ON CONFLICT(assignment_id, template_milestone_id) DO UPDATE SET
                            completed_at = excluded.completed_at,
                            notes = COALESCE(excluded.notes, case_readiness_milestone_state.notes),
                            updated_at = excluded.updated_at
                        """
                    ),
                    {"aid": assignment_id, "mid": template_milestone_id, "cat": completed_at, "notes": notes, "ua": now},
                )
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO case_readiness_milestone_state
                        (assignment_id, template_milestone_id, completed_at, notes, updated_at)
                        VALUES (:aid, :mid, :cat, :notes, :ua)
                        ON CONFLICT(assignment_id, template_milestone_id) DO UPDATE SET
                            completed_at = EXCLUDED.completed_at,
                            notes = COALESCE(EXCLUDED.notes, case_readiness_milestone_state.notes),
                            updated_at = EXCLUDED.updated_at
                        """
                    ),
                    {"aid": assignment_id, "mid": template_milestone_id, "cat": completed_at, "notes": notes, "ua": now},
                )

    # ------------------------------------------------------------------
    # Compensation & Allowance — policy_configs / policy_config_versions / policy_config_benefits
    # ------------------------------------------------------------------

    def purge_inactive_cases(self, active_statuses: List[str]) -> Dict[str, int]:
        """Remove inactive case/assignment data and related records."""
        status_list = [s for s in active_statuses if s]
        if not status_list:
            return {"assignments_deleted": 0, "relocation_cases_deleted": 0}

        placeholders = ", ".join([f":s{i}" for i in range(len(status_list))])
        params = {f"s{i}": status_list[i] for i in range(len(status_list))}

        with self.engine.begin() as conn:
            # Collect assignments to delete
            rows = conn.execute(text(
                f"SELECT id FROM case_assignments WHERE status NOT IN ({placeholders})"
            ), params).fetchall()
            assignment_ids = [r._mapping["id"] for r in rows]

            if assignment_ids:
                id_placeholders = ", ".join([f":a{i}" for i in range(len(assignment_ids))])
                id_params = {f"a{i}": assignment_ids[i] for i in range(len(assignment_ids))}

                conn.execute(text(
                    f"DELETE FROM wizard_employee_profiles WHERE assignment_id IN ({id_placeholders})"
                ), id_params)
                conn.execute(text(
                    f"DELETE FROM employee_answers WHERE assignment_id IN ({id_placeholders})"
                ), id_params)
                conn.execute(text(
                    f"DELETE FROM compliance_reports WHERE assignment_id IN ({id_placeholders})"
                ), id_params)
                conn.execute(text(
                    f"DELETE FROM compliance_runs WHERE assignment_id IN ({id_placeholders})"
                ), id_params)
                conn.execute(text(
                    f"DELETE FROM policy_exceptions WHERE assignment_id IN ({id_placeholders})"
                ), id_params)
                conn.execute(text(
                    f"DELETE FROM compliance_actions WHERE assignment_id IN ({id_placeholders})"
                ), id_params)

                conn.execute(text(
                    f"DELETE FROM assignment_invites WHERE case_id IN (SELECT case_id FROM case_assignments WHERE id IN ({id_placeholders}))"
                ), id_params)

                conn.execute(text(
                    f"DELETE FROM case_assignments WHERE id IN ({id_placeholders})"
                ), id_params)

            # Purge relocation_cases not active
            rows_cases = conn.execute(text(
                f"SELECT id FROM relocation_cases WHERE status NOT IN ({placeholders})"
            ), params).fetchall()
            case_ids = [r._mapping["id"] for r in rows_cases]
            if case_ids:
                case_placeholders = ", ".join([f":c{i}" for i in range(len(case_ids))])
                case_params = {f"c{i}": case_ids[i] for i in range(len(case_ids))}
                conn.execute(text(
                    f"DELETE FROM relocation_cases WHERE id IN ({case_placeholders})"
                ), case_params)

        return {
            "assignments_deleted": len(assignment_ids),
            "relocation_cases_deleted": len(case_ids),
        }

    # ==================================================================
    # HR Policies (full policy spec)
    # ==================================================================

    def list_policy_assignment_applicability(self, policy_version_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM policy_assignment_type_applicability WHERE policy_version_id = :vid"),
                {"vid": policy_version_id},
            ).fetchall()
        return self._rows_to_list(rows)

    def insert_policy_assignment_applicability(self, app: Dict[str, Any], *, connection: Any = None) -> str:
        aid = app.get("id") or str(uuid.uuid4())
        bind = {
            "id": aid,
            "vid": app["policy_version_id"],
            "brid": app["benefit_rule_id"],
            "at": app["assignment_type"],
        }

        def _ins(conn: Any) -> None:
            conn.execute(
                text("""
                    INSERT INTO policy_assignment_type_applicability
                    (id, policy_version_id, benefit_rule_id, assignment_type)
                    VALUES (:id, :vid, :brid, :at)
                """),
                bind,
            )

        if connection is not None:
            _ins(connection)
        else:
            with self.engine.begin() as conn:
                _ins(conn)
        return aid

    def update_relocation_case_host_country(self, case_id: str, host_country: str) -> None:
        """Set destination (host_country) on a relocation case (e.g. after admin create)."""
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE relocation_cases SET host_country = :host, updated_at = :ua WHERE id::text = :cid"),
                {"host": host_country, "ua": datetime.utcnow().isoformat(), "cid": case_id},
            )

    def set_relocation_case_route(
        self,
        relocation_case_id: str,
        *,
        home_country: str,
        home_city: str,
        host_country: str,
        host_city: str,
    ) -> None:
        """TD-FIX-7 (AIQ-1510): pin a case to a fixed route (test-drive corridor lock).

        Unlike touch_relocation_case_route_from_wizard (which denormalizes what the
        wizard supplied), this OVERWRITES the route unconditionally — it is the
        server-side enforcement of an assigned corridor, so a value the client sent
        must never win.

        Writes both column families on purpose:
          • home_/host_country + home_/host_city — what the employee intake prefill
            reads (list_employee_linked_assignment_overview), i.e. what makes the
            "🔒 HR pre-filled" lock fire.
          • origin_/dest_country_code + origin_/dest_city — what the HR case overview
            reads; `corridor` is a generated column derived from the two codes.
        """
        rid = (relocation_case_id or "").strip()
        if not rid:
            return
        params: Dict[str, Any] = {
            "cid": rid,
            "ua": datetime.utcnow().isoformat(),
            "home_country": home_country,
            "host_country": host_country,
            "origin_country_code": home_country,
            "dest_country_code": host_country,
            "home_city": home_city,
            "host_city": host_city,
            "origin_city": home_city,
            "dest_city": host_city,
        }
        cols = [c for c in params if c not in ("cid", "ua")]
        sql = (
            "UPDATE relocation_cases SET updated_at = :ua, "
            + ", ".join(f"{c} = :{c}" for c in cols)
            + " WHERE id::text = :cid"
        )
        with self.engine.begin() as conn:
            conn.execute(text(sql), params)

    def touch_relocation_case_route_from_wizard(
        self,
        relocation_case_id: str,
        *,
        home_country: Optional[str] = None,
        host_country: Optional[str] = None,
        origin_city: Optional[str] = None,
        dest_city: Optional[str] = None,
        target_start_date: Optional[str] = None,
    ) -> None:
        """Denormalize wizard origin/destination onto relocation_cases for HR lists and filters.

        AIQ-1311 PR2: also writes origin_country_code/dest_country_code/origin_city/
        dest_city/target_start_date — the columns hr_case_detail.get_case_overview
        reads (corridor is a generated column derived from the codes). The legacy
        home_country/host_country are still written (case-list surfaces read those).
        """
        rid = (relocation_case_id or "").strip()
        if not rid:
            return
        # origin/dest *_country_code mirror home/host — the overview reads the former.
        col_vals = {
            "home_country": home_country,
            "host_country": host_country,
            "origin_country_code": home_country,
            "dest_country_code": host_country,
            "origin_city": origin_city,
            "dest_city": dest_city,
        }
        if not any(col_vals.values()) and not target_start_date:
            return
        if not self.get_case_by_id(rid):
            return
        now = datetime.utcnow().isoformat()
        parts = ["updated_at = :ua"]
        params: Dict[str, Any] = {"cid": rid, "ua": now}
        for col, val in col_vals.items():
            if val:
                parts.append(f"{col} = :{col}")
                params[col] = val
        if target_start_date:
            # DATE column: bind plain on SQLite, CAST on Postgres (mirrors the
            # _is_sqlite branch the other date/jsonb writes here use).
            parts.append(
                "target_start_date = :tsd" if _is_sqlite else "target_start_date = CAST(:tsd AS date)"
            )
            params["tsd"] = target_start_date
        sql = f"UPDATE relocation_cases SET {', '.join(parts)} WHERE id::text = :cid"
        with self.engine.begin() as conn:
            conn.execute(text(sql), params)

    def sync_relocation_case_route_from_wizard_draft(self, relocation_case_id: str, draft: Dict[str, Any]) -> None:
        """
        Denormalize relocationBasics onto relocation_cases (same fields as PATCH /api/cases).
        Used on employee submit so HR lists + the case overview stay current without an
        extra wizard save. AIQ-1311 PR2: now also carries city + target move date.
        """
        basics = (draft or {}).get("relocationBasics") or {}
        route = wizard_basics_to_route(basics)
        if any(route.values()):
            self.touch_relocation_case_route_from_wizard(
                relocation_case_id,
                home_country=route["origin_country"],
                host_country=route["dest_country"],
                origin_city=route["origin_city"],
                dest_city=route["dest_city"],
                target_start_date=route["target_start_date"],
            )

    def _sync_case_dependents_from_draft(self, canonical_case_id: str, draft: Dict[str, Any]) -> None:
        """Sync the wizard family (spouse + children) into ``case_dependents``.

        The trigger engine reads ``case_dependents`` to set has_spouse /
        has_children, which gate the family-reunion forms (NO UTL-2011F/B, GB
        DEP-*, DE FAM-*). The household intake writes only the wizard draft, so
        without this sync ``case_dependents`` is never populated and NO family
        form is ever generated. Insert-if-absent keyed on
        (case_id, relationship, full_name) so re-saves never duplicate or churn
        ids (``case_forms.dependent_id`` stays stable). No-op when the canonical
        ``public.cases`` row doesn't exist yet (FK) or there is no family.
        """
        cid = (canonical_case_id or "").strip()
        if not cid:
            return
        fam = (draft or {}).get("familyMembers") or (draft or {}).get("family") or {}
        if not isinstance(fam, dict):
            return
        members: List[Any] = []  # (relationship, full_name, nationality, dob)
        sp = fam.get("spouse")
        if isinstance(sp, dict):
            members.append((
                "spouse",
                (str(sp.get("fullName") or sp.get("full_name") or "").strip() or "Spouse"),
                sp.get("nationality"),
                sp.get("dateOfBirth") or sp.get("date_of_birth"),
            ))
        kids = fam.get("children")
        if isinstance(kids, list):
            for i, c in enumerate(kids):
                if not isinstance(c, dict):
                    continue
                members.append((
                    "child",
                    (str(c.get("fullName") or c.get("full_name") or "").strip() or f"Child {i + 1}"),
                    c.get("nationality"),
                    c.get("dateOfBirth") or c.get("date_of_birth"),
                ))
        if not members:
            return
        cases_tbl = "cases" if _is_sqlite else "public.cases"
        dep_tbl = "case_dependents" if _is_sqlite else "public.case_dependents"
        try:
            with self.engine.begin() as conn:
                exists = conn.execute(
                    text(f"SELECT 1 FROM {cases_tbl} WHERE CAST(id AS TEXT) = :c LIMIT 1"), {"c": cid}
                ).first()
                if not exists:
                    return  # canonical case not materialized yet — sync on a later patch
                for rel, name, nat, dob in members:
                    already = conn.execute(
                        text(
                            f"SELECT 1 FROM {dep_tbl} WHERE CAST(case_id AS TEXT) = :c "
                            "AND relationship = :rel AND full_name = :name LIMIT 1"
                        ),
                        {"c": cid, "rel": rel, "name": name},
                    ).first()
                    if already:
                        continue
                    dep_id = str(uuid.uuid4())
                    dob_val = (str(dob).strip() or None) if dob else None
                    if _is_sqlite:
                        conn.execute(
                            text(
                                f"INSERT INTO {dep_tbl} (id, case_id, relationship, full_name, nationality, date_of_birth, created_at) "
                                "VALUES (:id, :c, :rel, :name, :nat, :dob, :now)"
                            ),
                            {"id": dep_id, "c": cid, "rel": rel, "name": name, "nat": nat,
                             "dob": dob_val, "now": datetime.utcnow().isoformat()},
                        )
                    else:
                        conn.execute(
                            text(
                                f"INSERT INTO {dep_tbl} (id, case_id, relationship, full_name, nationality, date_of_birth, created_at) "
                                "VALUES (CAST(:id AS uuid), CAST(:c AS uuid), :rel, :name, :nat, CAST(NULLIF(:dob,'') AS date), now())"
                            ),
                            {"id": dep_id, "c": cid, "rel": rel, "name": name, "nat": nat, "dob": (dob_val or "")},
                        )
        except Exception:
            log.exception("case-dependents sync: failed case=%s", cid)

    def _ensure_canonical_case_from_wizard(
        self, case_id: str, derived: Dict[str, Any], assignment: Dict[str, Any]
    ) -> None:
        """Upsert the canonical ``public.cases`` row the Case Engine reads.

        The intake wizard writes ``wizard_cases``; the trigger engine + case-access
        guard read ``public.cases``. Without this bridge, no wizard-created case
        ever appears to the trigger, so no CaseForms (and hence no roadmap/dossier)
        are generated. We populate the canonical row from the wizard draft + the
        ``case_assignments`` link. ``public.cases.employee_id`` is an FK to
        ``profiles``; we resolve it via ``_resolve_employee_profile_id`` —
        ``employee_user_id`` when it is itself a profile (uuid-native employees),
        else the employee's email, else ``employee_contact_id``. (The contact id
        is an FK to ``employee_contacts``, not ``profiles``, so it is almost never
        a valid ``employee_id`` — using it directly broke every real case.)

        Fail-safe: every NOT NULL column must resolve, else we skip — never insert
        a partial/invalid row. Caller (apply_wizard_patch_side_effects) is itself
        wrapped in try/except by the PATCH handler, so a failure can't break intake.
        """
        dest = (derived.get("dest_country") or "").strip()
        employee_uuid = self._resolve_employee_profile_id(assignment)
        if not dest or not employee_uuid:
            return  # trigger needs a destination; public.cases needs a profile employee_id
        canonical = str(assignment.get("canonical_case_id") or case_id).strip()
        company_id = self._resolve_canonical_case_company(canonical, assignment, employee_uuid)
        if not company_id:
            return
        origin = (derived.get("origin_country") or "").strip()
        # public.cases.purpose has a CHECK constraint
        # (work | intra_company_transfer | family_join | remote_work). The wizard
        # emits free-er values (and the old default 'relocation' is invalid), which
        # tripped cases_purpose_check and made this whole bridge silently fail for
        # ~every case — leaving public.cases nearly empty. Map onto the allowed set;
        # default to 'work' (the column default).
        _raw_purpose = (derived.get("purpose") or "").strip().lower()
        purpose = _CASE_PURPOSE_MAP.get(_raw_purpose, "work")
        dest_city = (derived.get("dest_city") or "").strip() or None
        move = (derived.get("target_move_date") or "") or ""
        # AIQ-1349: carry assignment type + expected duration onto the canonical
        # case so the (STA/LTA-aware) policy resolver + roadmap generation can
        # branch on them. Both columns are nullable; no CHECK constraint.
        assignment_type = (derived.get("assignment_type") or "").strip().upper() or None
        _dur = derived.get("expected_duration_months")
        try:
            duration_months = int(_dur) if _dur is not None and str(_dur).strip() != "" else None
        except (TypeError, ValueError):
            duration_months = None
        # AIQ-1603: single-select commute preference (nullable, no CHECK — validated at the DTO).
        commute_pref = (derived.get("commute_preference") or "").strip() or None
        params = {
            "id": case_id, "company": company_id, "emp": employee_uuid,
            "origin": origin, "dest": dest, "dest_city": dest_city,
            "purpose": purpose, "move": move,
            "assignment_type": assignment_type, "duration_months": duration_months,
            "commute_pref": commute_pref,
        }
        # public.cases enforces CHECK constraints — status in (draft, active,
        # on_hold, completed, cancelled), stage in (discovery, dossier, roadmap,
        # in_progress, closing, closed) — and FK employee_id -> profiles. We seed
        # status='active', stage='discovery'; employee_contact_id must already be
        # a profiles row (real employees have one). The whole upsert is
        # try/except-wrapped, so a constraint miss skips rather than breaking intake.
        if self.engine.dialect.name == "postgresql":
            sql = (
                "INSERT INTO cases "
                "(id, company_id, employee_id, origin_country_code, dest_country_code, dest_city, purpose, status, stage, target_move_date, assignment_type, expected_duration_months, commute_preference, created_at, updated_at) "
                "VALUES (CAST(:id AS uuid), CAST(:company AS uuid), CAST(:emp AS uuid), :origin, :dest, :dest_city, :purpose, 'active', 'discovery', CAST(NULLIF(:move,'') AS date), :assignment_type, :duration_months, :commute_pref, now(), now()) "
                "ON CONFLICT (id) DO UPDATE SET "
                "dest_country_code = EXCLUDED.dest_country_code, origin_country_code = EXCLUDED.origin_country_code, "
                "dest_city = EXCLUDED.dest_city, purpose = EXCLUDED.purpose, employee_id = EXCLUDED.employee_id, "
                "assignment_type = COALESCE(EXCLUDED.assignment_type, cases.assignment_type), "
                "expected_duration_months = COALESCE(EXCLUDED.expected_duration_months, cases.expected_duration_months), "
                "commute_preference = COALESCE(EXCLUDED.commute_preference, cases.commute_preference), "
                "updated_at = now()"
            )
        else:
            sql = (
                "INSERT INTO cases "
                "(id, company_id, employee_id, origin_country_code, dest_country_code, dest_city, purpose, status, stage, target_move_date, assignment_type, expected_duration_months, commute_preference) "
                "VALUES (:id, :company, :emp, :origin, :dest, :dest_city, :purpose, 'active', 'discovery', NULLIF(:move,''), :assignment_type, :duration_months, :commute_pref) "
                "ON CONFLICT (id) DO UPDATE SET dest_country_code=excluded.dest_country_code, "
                "origin_country_code=excluded.origin_country_code, dest_city=excluded.dest_city, "
                "purpose=excluded.purpose, employee_id=excluded.employee_id, "
                "assignment_type=COALESCE(excluded.assignment_type, cases.assignment_type), "
                "expected_duration_months=COALESCE(excluded.expected_duration_months, cases.expected_duration_months), "
                "commute_preference=COALESCE(excluded.commute_preference, cases.commute_preference)"
            )
        try:
            with self.engine.begin() as conn:
                conn.execute(text(sql), params)
        except Exception:
            log.exception("canonical-case bridge: upsert failed case=%s", case_id)

    def next_open_milestone_deadlines_for_cases(
        self, relocation_case_ids: List[str], request_id: Optional[str] = None
    ) -> Dict[str, str]:
        """Map normalized case id -> human-readable next open milestone date (earliest target_date)."""
        if not relocation_case_ids:
            return {}
        # Note: coalesce_case_lookup_id ran a wizard_cases SELECT per id but
        # always returned the input string unchanged. .strip() is equivalent
        # and avoids N synchronous round-trips on the HR dashboard hot path.
        normalized: List[str] = []
        seen: Set[str] = set()
        for raw in relocation_case_ids:
            nid = (raw or "").strip()
            if nid and nid not in seen:
                seen.add(nid)
                normalized.append(nid)
        if not normalized:
            return {}
        n = len(normalized)
        c_ph = ", ".join(f":c{i}" for i in range(n))
        d_ph = ", ".join(f":d{i}" for i in range(n))
        params: Dict[str, Any] = {f"c{i}": normalized[i] for i in range(n)}
        params.update({f"d{i}": normalized[i] for i in range(n)})
        sql = (
            f"SELECT case_id, canonical_case_id, target_date, status FROM case_milestones "
            f"WHERE case_id IN ({c_ph}) OR canonical_case_id IN ({d_ph})"
        )
        terminal = frozenset({"completed", "done", "cancelled", "canceled"})
        best: Dict[str, Optional[str]] = {k: None for k in normalized}
        try:
            with self.engine.connect() as conn:
                rows = self._exec(
                    conn, sql, params, op_name="milestones_bulk_for_deadlines", request_id=request_id
                ).fetchall()
        except Exception:
            return {}
        for row in rows:
            m = row._mapping if hasattr(row, "_mapping") else dict(row)
            td = m.get("target_date")
            if not td or not str(td).strip():
                continue
            st = (m.get("status") or "").strip().lower()
            if st in terminal:
                continue
            c1 = (m.get("canonical_case_id") or "").strip()
            c0 = (m.get("case_id") or "").strip()
            key = (c1 or c0)
            if key not in best:
                continue
            ts = str(td).strip()
            cur = best.get(key)
            if cur is None or ts < cur:
                best[key] = ts
        out: Dict[str, str] = {}
        for nid, raw_date in best.items():
            if not raw_date:
                continue
            disp = raw_date
            try:
                dpart = raw_date[:10]
                parsed = datetime.strptime(dpart, "%Y-%m-%d").date()
                disp = f"{parsed.strftime('%b')} {parsed.day}, {parsed.year}"
            except Exception:
                pass
            out[nid] = disp
        return out

    def create_assignment(
        self,
        assignment_id: str,
        case_id: str,
        hr_user_id: str,
        employee_user_id: Optional[str],
        employee_identifier: str,
        status: str,
        request_id: Optional[str] = None,
        employee_first_name: Optional[str] = None,
        employee_last_name: Optional[str] = None,
        employee_contact_id: Optional[str] = None,
        employee_link_mode: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        efn = (employee_first_name or "").strip() or None
        eln = (employee_last_name or "").strip() or None
        # B3-fix: skip pre-validation SELECT on employee_contact_id.
        # The ID was just returned by resolve_or_create_employee_contact which already
        # verified its existence.  The extra SELECT opened a second pool connection that
        # was the first DB op to hit a stale/locked Supabase connection, causing the
        # 20-second hang.  Callers are responsible for passing a valid ID.
        ecid_check = (employee_contact_id or "").strip() if employee_contact_id else None
        elm = (employee_link_mode or "").strip() or None
        # B3-fix-v4: ensure DB init is complete BEFORE opening the transaction.
        # If _initialized=False here (startup race), we block before holding any
        # connection — no zombie is created.  If _initialized=True (normal case),
        # this is a single boolean read and is effectively free.
        self.ensure_initialized()
        with self.engine.begin() as conn:
            # B3-fix-v3: SET LOCAL applies for the duration of this explicit transaction.
            # PgBouncer transaction mode assigns the SAME backend server for BEGIN…COMMIT,
            # so SET LOCAL is guaranteed to be honoured (unlike SET outside a transaction
            # which PgBouncer may route to a different backend on the next round-trip).
            if not _is_sqlite:
                try:
                    conn.execute(text("SET LOCAL statement_timeout = '7500ms'"))
                    conn.execute(text("SET LOCAL lock_timeout = '5000ms'"))
                except Exception:
                    pass  # never block the insert for a non-critical SET
            self._exec(
                conn,
                "INSERT INTO case_assignments "
                "(id, case_id, canonical_case_id, hr_user_id, employee_user_id, employee_identifier, status, "
                "employee_first_name, employee_last_name, employee_contact_id, employee_link_mode, created_at, updated_at) "
                "VALUES (:id, :cid, :canonical, :hr, :emp, :ident, :status, :efn, :eln, :ecid, :elm, :ca, :ua)",
                {
                    "id": assignment_id,
                    "cid": case_id,
                    "canonical": case_id,
                    "hr": hr_user_id,
                    "emp": employee_user_id,
                    "ident": employee_identifier,
                    "status": status,
                    "efn": efn,
                    "eln": eln,
                    "ecid": employee_contact_id,
                    "elm": elm,
                    "ca": now,
                    "ua": now,
                },
                op_name="create_assignment",
                request_id=request_id,
            )

    def update_assignment_status(self, assignment_id: str, status: str, request_id: Optional[str] = None) -> None:
        with self.engine.begin() as conn:
            self._exec(
                conn,
                "UPDATE case_assignments SET status = :status, updated_at = :ua WHERE id = :id",
                {"status": status, "ua": datetime.utcnow().isoformat(), "id": assignment_id},
                op_name="update_assignment_status",
                request_id=request_id,
            )

    def update_assignment_identifier(self, assignment_id: str, employee_identifier: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE case_assignments SET employee_identifier = :ident, updated_at = :ua WHERE id = :id"
            ), {"ident": employee_identifier, "ua": datetime.utcnow().isoformat(), "id": assignment_id})

    def attach_employee_to_assignment(
        self,
        assignment_id: str,
        employee_user_id: str,
        request_id: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        post_ecid: Optional[str] = None
        post_hr_uid: Optional[str] = None
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT employee_contact_id, hr_user_id FROM case_assignments WHERE id = :id"
                ),
                {"id": assignment_id},
            ).fetchone()
            self._exec(
                conn,
                "UPDATE case_assignments SET employee_user_id = :emp, employee_link_mode = NULL, "
                "updated_at = :ua WHERE id = :id",
                {"emp": employee_user_id, "ua": now, "id": assignment_id},
                op_name="attach_employee_to_assignment",
                request_id=request_id,
            )
            ecid = None
            if row:
                m = row._mapping if hasattr(row, "_mapping") else dict(row)
                ecid = m.get("employee_contact_id")
                hu = m.get("hr_user_id")
                if hu and str(hu).strip():
                    post_hr_uid = str(hu).strip()
            if ecid and str(ecid).strip():
                post_ecid = str(ecid).strip()
                conn.execute(
                    text(
                        "UPDATE employee_contacts SET linked_auth_user_id = :uid, updated_at = :ua "
                        "WHERE id = :ecid AND (linked_auth_user_id IS NULL OR linked_auth_user_id = :uid)"
                    ),
                    {"uid": employee_user_id, "ua": now, "ecid": post_ecid},
                )

        company_for_dir: Optional[str] = None
        if post_ecid:
            ec_row = self.get_employee_contact_by_id(post_ecid, request_id=request_id)
            if ec_row and ec_row.get("company_id"):
                company_for_dir = str(ec_row["company_id"]).strip()
        if not company_for_dir and post_hr_uid:
            company_for_dir = self.get_hr_company_id(post_hr_uid)
        if company_for_dir:
            self.assign_employee_profile_to_company_directory(
                employee_user_id.strip(), company_for_dir, request_id=request_id
            )

    def list_unassigned_assignments_for_employee_contact(
        self, employee_contact_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if not (employee_contact_id or "").strip():
            return []
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT * FROM case_assignments "
                "WHERE employee_contact_id = :ecid AND employee_user_id IS NULL "
                "AND (employee_link_mode IS NULL OR TRIM(COALESCE(employee_link_mode, '')) = '' "
                "OR LOWER(TRIM(employee_link_mode)) NOT IN ('pending_claim', 'dismissed'))",
                {"ecid": employee_contact_id.strip()},
                op_name="list_unassigned_assignments_for_employee_contact",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def list_pending_claim_assignments_for_employee_contact(
        self, employee_contact_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """pending_claim assignments for a contact (employee_user_id NULL, mode='pending_claim').
        Used only by the verified-email auto-link path — the normal reconcile query
        (`list_unassigned_assignments_for_employee_contact`) deliberately excludes these."""
        if not (employee_contact_id or "").strip():
            return []
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT * FROM case_assignments "
                "WHERE employee_contact_id = :ecid AND employee_user_id IS NULL "
                "AND LOWER(TRIM(COALESCE(employee_link_mode, ''))) = 'pending_claim'",
                {"ecid": employee_contact_id.strip()},
                op_name="list_pending_claim_assignments_for_employee_contact",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def list_unassigned_assignments_legacy_for_identifiers(
        self, identifiers: List[str], request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Assignments with no employee_contact_id (legacy) and no employee_user_id,
        matching normalized employee_identifier.
        """
        idents = sorted(
            {normalize_invite_key(x) for x in identifiers if x and normalize_invite_key(x)}
        )
        if not idents:
            return []
        seen: Set[str] = set()
        out: List[Dict[str, Any]] = []
        with self.engine.connect() as conn:
            for ident in idents:
                rows = self._exec(
                    conn,
                    "SELECT * FROM case_assignments WHERE employee_user_id IS NULL "
                    "AND (employee_contact_id IS NULL OR TRIM(COALESCE(employee_contact_id, '')) = '') "
                    "AND LOWER(TRIM(COALESCE(employee_identifier, ''))) = :ident "
                    "AND (employee_link_mode IS NULL OR TRIM(COALESCE(employee_link_mode, '')) = '' "
                    "OR LOWER(TRIM(employee_link_mode)) NOT IN ('pending_claim', 'dismissed'))",
                    {"ident": ident},
                    op_name="list_unassigned_assignments_legacy_for_identifiers",
                    request_id=request_id,
                ).fetchall()
                for row in rows:
                    d = self._row_to_dict(row)
                    aid = d.get("id") if d else None
                    if aid and aid not in seen:
                        seen.add(aid)
                        out.append(d)
        return out

    def list_rfqs_for_case(
        self, case_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List RFQs for a case with items and recipients."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                """SELECT * FROM rfqs
                   WHERE case_id = :cid OR canonical_case_id = :cid
                   ORDER BY created_at DESC""",
                {"cid": cid},
                op_name="list_rfqs_for_case",
                request_id=request_id,
            ).fetchall()
            rfqs = self._rows_to_list(rows)
            for rfq in rfqs:
                rfq["items"] = self._list_rfq_items(conn, rfq["id"])
                rfq["recipients"] = self._list_rfq_recipients(conn, rfq["id"])
        return rfqs

    def list_rfqs_for_assignment(
        self, assignment_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List RFQs for an assignment via its case_id."""
        assignment = self.get_assignment_by_id(assignment_id, request_id=request_id)
        if not assignment:
            return []
        case_id = assignment.get("case_id")
        if not case_id:
            return []
        return self.list_rfqs_for_case(case_id, request_id=request_id)

    def _command_center_join_relocation_cases(self) -> str:
        """Join relocation_cases using legacy case_id and/or canonical_case_id (COALESCE alone can miss rows)."""
        if _is_sqlite:
            return (
                "("
                "(NULLIF(TRIM(ca.case_id), '') IS NOT NULL AND rc.id = NULLIF(TRIM(ca.case_id), ''))"
                " OR "
                "(NULLIF(TRIM(ca.canonical_case_id), '') IS NOT NULL AND rc.id = NULLIF(TRIM(ca.canonical_case_id), ''))"
                ")"
            )
        return (
            "("
            "(NULLIF(TRIM(ca.case_id::text), '') IS NOT NULL AND rc.id::text = NULLIF(TRIM(ca.case_id::text), ''))"
            " OR "
            "(NULLIF(TRIM(ca.canonical_case_id::text), '') IS NOT NULL AND rc.id::text = NULLIF(TRIM(ca.canonical_case_id::text), ''))"
            ")"
        )

    def _command_center_join_wizard_cases(self) -> str:
        """Join wizard_cases (intake source of truth) using the same id as relocation_cases / assignment pointers."""
        if _is_sqlite:
            return "wc.id = COALESCE(NULLIF(TRIM(ca.canonical_case_id), ''), NULLIF(TRIM(ca.case_id), ''))"
        return "wc.id::text = COALESCE(NULLIF(TRIM(ca.canonical_case_id::text), ''), NULLIF(TRIM(ca.case_id::text), ''))"

    def _ensure_postgres_case_milestones_schema(self, conn) -> None:
        """Postgres timeline tables (text ids, aligned with app inserts). See supabase/migrations/20260325000000_*."""
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.case_milestones (
                  id text PRIMARY KEY,
                  case_id text NOT NULL,
                  canonical_case_id text,
                  milestone_type text NOT NULL,
                  title text NOT NULL,
                  description text,
                  target_date date,
                  actual_date date,
                  status text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','in_progress','done','skipped','overdue','blocked')),
                  sort_order int NOT NULL DEFAULT 0,
                  created_at timestamptz NOT NULL DEFAULT now(),
                  updated_at timestamptz NOT NULL DEFAULT now(),
                  owner text NOT NULL DEFAULT 'joint',
                  criticality text NOT NULL DEFAULT 'normal',
                  notes text,
                  source text,
                  service_key text
                )
                """
            )
        )
        # Idempotent ALTERs so pre-existing test/dev DBs gain the provenance columns.
        for _col in ("source", "service_key"):
            conn.execute(
                text(f"ALTER TABLE public.case_milestones ADD COLUMN IF NOT EXISTS {_col} text")
            )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_case_milestones_case_id "
                "ON public.case_milestones(case_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_case_milestones_canonical "
                "ON public.case_milestones(canonical_case_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_case_milestones_sort "
                "ON public.case_milestones(case_id, sort_order)"
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.milestone_links (
                  id text PRIMARY KEY,
                  milestone_id text NOT NULL REFERENCES public.case_milestones(id) ON DELETE CASCADE,
                  linked_entity_type text NOT NULL,
                  linked_entity_id text NOT NULL,
                  created_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_milestone_links_milestone "
                "ON public.milestone_links(milestone_id)"
            )
        )
        try:
            conn.execute(text("ALTER TABLE public.case_milestones ENABLE ROW LEVEL SECURITY"))
            conn.execute(text("DROP POLICY IF EXISTS case_milestones_all ON public.case_milestones"))
            conn.execute(
                text(
                    "CREATE POLICY case_milestones_all ON public.case_milestones "
                    "FOR ALL TO service_role USING (true) WITH CHECK (true)"
                )
            )
        except (OperationalError, ProgrammingError) as ex:
            log.warning("case_milestones RLS/policy skipped: %s", ex)
        try:
            conn.execute(text("ALTER TABLE public.milestone_links ENABLE ROW LEVEL SECURITY"))
            conn.execute(text("DROP POLICY IF EXISTS milestone_links_all ON public.milestone_links"))
            conn.execute(
                text(
                    "CREATE POLICY milestone_links_all ON public.milestone_links "
                    "FOR ALL TO service_role USING (true) WITH CHECK (true)"
                )
            )
        except (OperationalError, ProgrammingError) as ex:
            log.warning("milestone_links RLS/policy skipped: %s", ex)

    # ------------------------------------------------------------------
    # Schema creation
    # ------------------------------------------------------------------

    def _maybe_ensure_postgres_case_assignments_employee_link_mode(self) -> None:
        """
        case_assignments.employee_link_mode is required for create_assignment INSERT and pending-claim flows.
        Supabase migration: 20260413120000_case_assignments_employee_link_mode.sql

        When DISABLE_RUNTIME_DDL skips full init_db DDL, this narrow idempotent patch still runs so
        production does not 500 on HR assign (UndefinedColumn).
        """
        if _is_sqlite:
            return
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE case_assignments ADD COLUMN IF NOT EXISTS employee_link_mode TEXT"
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE INDEX IF NOT EXISTS idx_case_assignments_employee_link_mode
                        ON case_assignments (employee_link_mode)
                        WHERE employee_user_id IS NULL AND employee_link_mode IS NOT NULL
                        """
                    )
                )
            log.info(
                "Ensured case_assignments.employee_link_mode exists (idempotent). "
                "Prefer applying supabase/migrations/20260413120000_case_assignments_employee_link_mode.sql in CI."
            )
        except Exception as ex:
            log.warning("case_assignments.employee_link_mode ensure failed (run Supabase migration): %s", ex)

    def list_messages_by_assignment(self, assignment_id: str) -> List[Dict[str, Any]]:
        from ..database import _eq_text  # lazy: avoid import cycle
        """List all messages for an assignment (admin or HR/employee context)."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(f"""
                SELECT m.*, COALESCE(u.name, u.email, u.username) as sender_display_name
                FROM messages m
                LEFT JOIN users u ON {_eq_text("u.id", "COALESCE(m.sender_user_id, m.hr_user_id)")}
                WHERE {_eq_text("m.assignment_id", ":aid")}
                ORDER BY m.created_at ASC
            """),
                {"aid": assignment_id},
            ).fetchall()
        items = self._rows_to_list(rows)
        # AIQ-1325b: defensively scrub a leading '[verify]' marker from per-message
        # subjects at read time (display-only) so it never surfaces as a thread title.
        from .test_data_filter import strip_verify_prefix
        for it in items:
            if it.get("subject"):
                it["subject"] = strip_verify_prefix(it["subject"])
        return items

    def insert_message(
        self,
        *,
        assignment_id: str,
        body: str,
        sender_user_id: str,
        recipient_user_id: Optional[str] = None,
        hr_user_id: Optional[str] = None,
        employee_identifier: Optional[str] = None,
        status: str = "sent",
        request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Insert one HR<->employee message on an assignment thread via the legacy
        assignment-based columns the inbox read path uses
        (list_messages_by_assignment / list_messages_for_{hr,employee}). The
        thread-model columns (thread_id/sender_id/sender_name/sender_initials) are
        left NULL — see migration 20260727000000. Tenant scoping is the caller's
        responsibility (the handler verifies assignment access first). The id is
        generated here so the insert is identical on Postgres and SQLite. Returns
        the created row, or None when assignment_id / body / sender are blank."""
        import uuid as _uuid

        aid = (assignment_id or "").strip()
        text_body = (body or "").strip()
        suid = (sender_user_id or "").strip()
        if not aid or not text_body or not suid:
            return None
        mid = str(_uuid.uuid4())
        now = datetime.utcnow().isoformat()
        params = {
            "id": mid,
            "aid": aid,
            "body": text_body,
            "suid": suid,
            "ruid": (recipient_user_id or None),
            "hruid": (hr_user_id or None),
            "emp": (employee_identifier or None),
            "status": status,
            "now": now,
        }
        cols = (
            "id, assignment_id, body, sender_user_id, recipient_user_id, "
            "hr_user_id, employee_identifier, status, created_at, sent_at"
        )
        if _is_sqlite:
            sql = (
                f"INSERT INTO messages ({cols}) "
                "VALUES (:id, :aid, :body, :suid, :ruid, :hruid, :emp, :status, :now, :now)"
            )
        else:
            sql = (
                f"INSERT INTO messages ({cols}) "
                "VALUES (:id, :aid, :body, :suid, :ruid, :hruid, :emp, :status, "
                "CAST(:now AS timestamptz), CAST(:now AS timestamptz))"
            )
        with self.engine.begin() as conn:
            self._exec(conn, sql, params, op_name="insert_message", request_id=request_id)
        return {
            "id": mid,
            "assignment_id": aid,
            "body": text_body,
            "sender_user_id": suid,
            "recipient_user_id": recipient_user_id,
            "hr_user_id": hr_user_id,
            "status": status,
            "created_at": now,
        }

    def get_admin_assignments_index(
        self,
        company_id: Optional[str] = None,
        employee_user_id: Optional[str] = None,
        employee_search: Optional[str] = None,
        status: Optional[str] = None,
        destination_country: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        from ..database import _relocation_cases_join_on  # lazy: avoid import cycle
        """
        List assignments for admin (same as list_admin_assignments) plus summary with
        count, orphans_without_company, orphans_without_person.
        """
        items = self.list_admin_assignments(
            company_id=company_id,
            employee_user_id=employee_user_id,
            employee_search=employee_search,
            status=status,
            destination_country=destination_country,
        )
        with self.engine.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) AS n FROM case_assignments"), {}).fetchone()
            total_count = int(total._mapping["n"]) if total else 0
            no_company_sql = text(f"""
                SELECT COUNT(*) AS n FROM case_assignments a
                LEFT JOIN relocation_cases rc ON {_relocation_cases_join_on("a", "canonical_coalesce")}
                LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
                WHERE COALESCE(rc.company_id, hu.company_id) IS NULL
            """)
            no_emp_sql = text("""
                SELECT COUNT(*) AS n FROM case_assignments
                WHERE employee_user_id IS NULL OR TRIM(COALESCE(employee_user_id,'')) = ''
            """)
            try:
                no_co = conn.execute(no_company_sql, {}).fetchone()
                no_emp = conn.execute(no_emp_sql, {}).fetchone()
                orphans_no_company = int(no_co._mapping["n"]) if no_co else 0
                orphans_no_person = int(no_emp._mapping["n"]) if no_emp else 0
            except Exception as e:
                log.warning("admin_assignments_index: orphan counts failed: %s", e)
                orphans_no_company = orphans_no_person = 0
        summary = {
            "count": total_count,
            "orphans_without_company": orphans_no_company,
            "orphans_without_person": orphans_no_person,
        }
        return items, summary

    def list_employee_tasks(
        self,
        employee_id: str,
        case_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return all tasks for an employee, ordered by due_date ASC NULLS LAST then created_at.
        If case_id is provided, scoped to that case; otherwise returns all tasks for the employee.
        """
        try:
            with self.engine.connect() as conn:
                params: Dict[str, Any] = {"eid": employee_id}
                if case_id:
                    where = "WHERE employee_id = :eid AND case_id = :cid"
                    params["cid"] = case_id
                else:
                    where = "WHERE employee_id = :eid"
                # fix: the column is `task_type`, not `type` — the old SELECT
                # raised `column "type" does not exist`, which the except below
                # swallowed into an empty list (employee task list always blank).
                sql = f"""
                    SELECT id, case_id, employee_id, org_id, task_type, title, description,
                           due_date, status, required_file_upload, submission_data,
                           file_url, submitted_at, reviewed_by, reviewed_at, review_note,
                           created_at, updated_at
                    FROM employee_tasks
                    {where}
                    ORDER BY due_date ASC NULLS LAST, created_at ASC
                """
                rows = conn.execute(text(sql), params).fetchall()
                result = []
                for row in rows:
                    d = dict(row._mapping)
                    # Dates to ISO strings
                    for k in ("due_date", "submitted_at", "reviewed_at", "created_at", "updated_at"):
                        if d.get(k) is not None:
                            d[k] = str(d[k])
                    result.append(d)
                return result
        except Exception as e:
            log.warning("list_employee_tasks employee_id=%s: %s", employee_id, e)
            return []

    def get_employee_task(
        self,
        task_id: str,
        employee_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a single task, verifying it belongs to the given employee.
        Returns None if not found or not owned by employee.
        """
        try:
            with self.engine.connect() as conn:
                sql = """
                    SELECT id, case_id, employee_id, org_id, task_type, title, description,
                           due_date, status, required_file_upload, submission_data,
                           file_url, submitted_at, reviewed_at, reviewed_by, review_note,
                           created_at, updated_at
                    FROM employee_tasks
                    WHERE id = :tid AND employee_id = :eid
                    LIMIT 1
                """
                row = conn.execute(text(sql), {"tid": task_id, "eid": employee_id}).fetchone()
                if row is None:
                    return None
                d = dict(row._mapping)
                for k in ("due_date", "submitted_at", "reviewed_at", "created_at", "updated_at"):
                    if d.get(k) is not None:
                        d[k] = str(d[k])
                return d
        except Exception as e:
            log.warning("get_employee_task task_id=%s: %s", task_id, e)
            return None

    def submit_employee_task(
        self,
        task_id: str,
        employee_id: str,
        submission_data: Optional[Dict[str, Any]] = None,
        file_url: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Mark a task as submitted (status='submitted') and persist submission payload.
        Returns updated task or None if task not found / not owned by employee.
        Only updates tasks in status 'pending' or 'revision_requested'.
        """
        try:
            with self.engine.begin() as conn:
                # Verify ownership + eligible status
                check = conn.execute(
                    text("""
                        SELECT id, status FROM employee_tasks
                        WHERE id = :tid AND employee_id = :eid
                        LIMIT 1
                    """),
                    {"tid": task_id, "eid": employee_id},
                ).fetchone()
                if check is None:
                    return None
                current_status = check._mapping["status"]
                if current_status not in ("pending", "revision_requested"):
                    # Already submitted/approved — return current state
                    return self.get_employee_task(task_id, employee_id)

                sub_data_json = json.dumps(submission_data) if submission_data else None
                now = datetime.utcnow().isoformat()

                conn.execute(
                    text("""
                        UPDATE employee_tasks
                        SET status       = 'submitted',
                            submission_data = COALESCE(:sub_data::jsonb, submission_data),
                            file_url     = COALESCE(:file_url, file_url),
                            submitted_at = :now,
                            updated_at   = :now
                        WHERE id = :tid AND employee_id = :eid
                    """),
                    {
                        "sub_data": sub_data_json,
                        "file_url": file_url,
                        "now": now,
                        "tid": task_id,
                        "eid": employee_id,
                    },
                )
            return self.get_employee_task(task_id, employee_id)
        except Exception as e:
            log.error("submit_employee_task task_id=%s: %s", task_id, e, exc_info=True)
            return None

    def review_employee_task(
        self,
        task_id: str,
        case_id: str,
        hr_user_id: str,
        action: str,        # 'approved' | 'revision_requested'
        review_note: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        HR approves or requests revision on a submitted employee task.

        Only acts on tasks in status 'submitted'. Returns updated task or None.
        `action` must be 'approved' or 'revision_requested'.
        """
        if action not in ("approved", "revision_requested"):
            return None
        try:
            with self.engine.begin() as conn:
                check = conn.execute(
                    text("""
                        SELECT id, status FROM employee_tasks
                        WHERE id = :tid AND case_id = :cid
                        LIMIT 1
                    """),
                    {"tid": task_id, "cid": case_id},
                ).fetchone()
                if check is None:
                    return None
                current_status = check._mapping["status"]
                if current_status != "submitted":
                    # Already reviewed — return current state without change
                    pass
                else:
                    now = datetime.utcnow().isoformat()
                    conn.execute(
                        text("""
                            UPDATE employee_tasks
                            SET status       = :action,
                                reviewed_by  = :hr,
                                reviewed_at  = :now,
                                review_note  = :note,
                                updated_at   = :now
                            WHERE id = :tid AND case_id = :cid
                        """),
                        {
                            "action": action,
                            "hr": hr_user_id,
                            "now": now,
                            "note": review_note,
                            "tid": task_id,
                            "cid": case_id,
                        },
                    )
            # Return fresh read
            with self.engine.connect() as conn:
                row = conn.execute(
                    text("""
                        SELECT * FROM employee_tasks
                        WHERE id = :tid AND case_id = :cid LIMIT 1
                    """),
                    {"tid": task_id, "cid": case_id},
                ).fetchone()
                if row is None:
                    return None
                d = dict(row._mapping)
                for k in ("due_date", "submitted_at", "reviewed_at", "created_at", "updated_at"):
                    if d.get(k) is not None:
                        d[k] = str(d[k])
                return d
        except Exception as e:
            log.error("review_employee_task task_id=%s: %s", task_id, e, exc_info=True)
            return None

    def create_employee_task_for_case(
        self,
        case_id: str,
        employee_id: str,
        org_id: str,
        task_type: str,
        title: str,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
        required_file_upload: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        HR creates a new task on an existing case (mid-case assignment).
        Returns the created task row or None on error.
        """
        try:
            new_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            with self.engine.begin() as conn:
                # AIQ-1591: column is `task_type` (renamed from `type` in migration
                # 20260513280000). The old INSERT into `type` raised `column "type" does not
                # exist`, swallowed by the except → returned None → the endpoint 500'd for
                # every task type. get_employee_task / list_employee_tasks_for_case_hr had the
                # same stale name; all now use task_type (matching the EmployeeTask contract).
                conn.execute(
                    text("""
                        INSERT INTO employee_tasks
                            (id, case_id, employee_id, org_id, task_type, title, description,
                             due_date, status, required_file_upload, created_at, updated_at)
                        VALUES
                            (:id, :cid, :eid, :oid, :task_type, :title, :desc,
                             :due, 'pending', :req_file, :now, :now)
                    """),
                    {
                        "id": new_id,
                        "cid": case_id,
                        "eid": employee_id,
                        "oid": org_id,
                        "task_type": task_type,
                        "title": title,
                        "desc": description,
                        "due": due_date,
                        "req_file": required_file_upload,
                        "now": now,
                    },
                )
            with self.engine.connect() as conn:
                row = conn.execute(
                    text("SELECT * FROM employee_tasks WHERE id = :id LIMIT 1"),
                    {"id": new_id},
                ).fetchone()
                if row is None:
                    return None
                d = dict(row._mapping)
                for k in ("due_date", "submitted_at", "reviewed_at", "created_at", "updated_at"):
                    if d.get(k) is not None:
                        d[k] = str(d[k])
                return d
        except Exception as e:
            log.error("create_employee_task_for_case case_id=%s: %s", case_id, e, exc_info=True)
            return None

    def list_employee_tasks_for_case_hr(
        self,
        case_id: str,
    ) -> List[Dict[str, Any]]:
        """
        HR view: all tasks for a case, used by AIQ-34-C.
        Returns all tasks ordered by status (pending first) then due_date.
        """
        try:
            with self.engine.connect() as conn:
                sql = """
                    SELECT id, case_id, employee_id, org_id, task_type, title, description,
                           due_date, status, required_file_upload, submission_data,
                           file_url, submitted_at, reviewed_by, reviewed_at, review_note,
                           created_at, updated_at
                    FROM employee_tasks
                    WHERE case_id = :cid
                    ORDER BY
                        CASE status
                            WHEN 'pending'             THEN 1
                            WHEN 'revision_requested'  THEN 2
                            WHEN 'submitted'           THEN 3
                            WHEN 'approved'            THEN 4
                            ELSE 5
                        END,
                        due_date ASC NULLS LAST
                """
                rows = conn.execute(text(sql), {"cid": case_id}).fetchall()
                result = []
                for row in rows:
                    d = dict(row._mapping)
                    for k in ("due_date", "submitted_at", "reviewed_at", "created_at", "updated_at"):
                        if d.get(k) is not None:
                            d[k] = str(d[k])
                    result.append(d)
                return result
        except Exception as e:
            log.warning("list_employee_tasks_for_case_hr case_id=%s: %s", case_id, e)
            return []
