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
from typing import Any, Dict, List, Optional

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
                "    intake_updated_at = :now, updated_at = :now "
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
            self._exec(
                conn,
                "UPDATE case_assignments "
                "SET status = :status, submitted_at = :now, updated_at = :now "
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
                    notes TEXT
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
                   owner, criticality, notes
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
                       notes = :notes, updated_at = :now
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
                   (id, case_id, canonical_case_id, milestone_type, title, description, target_date, actual_date, status, sort_order, created_at, updated_at, owner, criticality, notes)
                   VALUES (:id, :cid, :canonical, :mt, :title, :desc, :td, :ad, :status, :so, :now, :now, :owner, :crit, :notes)""",
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
                    "selected": 1 if item.get("selected", True) else 0,
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
            try:
                item["answers"] = json.loads(item.get("answers") or "{}")
            except Exception:
                item["answers"] = {}
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
