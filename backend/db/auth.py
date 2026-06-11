"""[AUDIT-C1.4] Auth-domain DB methods, extracted from backend/database.py.

Session tokens, claim-invite lookups, and admin-session helpers. These were
methods on the monolithic ``Database`` class; they live here as a mixin
(:class:`AuthMixin`) that ``Database`` inherits, so every caller
(``db.get_user_by_token(...)`` etc.) keeps working unchanged via normal MRO.
Login behaviour is byte-for-byte identical — this is a pure relocation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from ..db_config import DATABASE_URL as _raw_url

log = logging.getLogger(__name__)

_is_sqlite = _raw_url.startswith("sqlite")


class AuthMixin:
    """Auth-domain methods mixed into :class:`backend.database.Database`."""

    def delete_session_by_token(self, token: str) -> bool:
        """Remove session on logout. Returns True if a row was deleted."""
        with self.engine.begin() as conn:
            result = conn.execute(text("DELETE FROM sessions WHERE token = :token"), {"token": token})
            return result.rowcount > 0

    def create_session(self, token: str, user_id: str) -> bool:
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO sessions (token, user_id, created_at) VALUES (:token, :user_id, :created_at)"
            ), {"token": token, "user_id": user_id, "created_at": datetime.utcnow().isoformat()})
        return True

    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT user_id FROM sessions WHERE token = :token"), {"token": token}).fetchone()
        if not row:
            return None
        return self.get_user_by_id(row._mapping["user_id"])

    def get_user_context_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Single-query replacement for the 4-call chain:
            get_user_by_token -> get_user_by_id -> get_admin_session -> get_profile_record
        Returns None if the session token is unknown.
        """
        sql = text("""
            SELECT
                u.id,
                u.email,
                u.role,
                u.username,
                p.full_name,
                p.company_id::text AS company_id,
                (LOWER(u.role) = 'admin') AS is_admin
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            LEFT JOIN profiles p ON p.id::text = u.id
            WHERE s.token = :token
            LIMIT 1
        """)
        with self.engine.connect() as conn:
            row = conn.execute(sql, {"token": token}).fetchone()
        if not row:
            return None
        m = row._mapping
        return {
            "id":          m["id"],
            "email":       m["email"],
            "role":        m["role"],
            "username":    m.get("username"),
            "full_name":   m.get("full_name"),
            "company_id":  m.get("company_id"),
            "is_admin":    bool(m.get("is_admin")),
        }

    def get_claim_invite_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Look up a single assignment_claim_invites row by its unique token.
        Returns the row as a dict, or None if not found or on DB error.
        """
        token = (token or "").strip()
        if not token:
            return None
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT * FROM assignment_claim_invites WHERE token = :tok LIMIT 1"
                    ),
                    {"tok": token},
                ).fetchone()
            if row is None:
                return None
            m = row._mapping if hasattr(row, "_mapping") else dict(row)
            return dict(m)
        except (OperationalError, ProgrammingError):
            return None

    def link_employee_contact_to_auth_user(
        self,
        employee_contact_id: str,
        user_id: str,
        request_id: Optional[str] = None,
    ) -> None:
        """Idempotent: set linked_auth_user_id when unset or already same user."""
        if not (employee_contact_id or "").strip() or not (user_id or "").strip():
            return
        ec = self.get_employee_contact_by_id(employee_contact_id.strip(), request_id=request_id)
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            self._exec(
                conn,
                "UPDATE employee_contacts SET linked_auth_user_id = :uid, updated_at = :ua "
                "WHERE id = :ecid AND (linked_auth_user_id IS NULL OR linked_auth_user_id = :uid)",
                {"uid": user_id.strip(), "ua": now, "ecid": employee_contact_id.strip()},
                op_name="link_employee_contact_to_auth_user",
                request_id=request_id,
            )
        if ec:
            cc = (str(ec.get("company_id") or "")).strip()
            if cc:
                self.assign_employee_profile_to_company_directory(
                    user_id.strip(), cc, request_id=request_id
                )

    def list_pending_claim_assignments_for_auth_user(
        self,
        auth_user_id: str,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Assignments tied to employee_contacts linked to this user, awaiting explicit claim."""
        uid = (auth_user_id or "").strip()
        if not uid:
            return []
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT a.* FROM case_assignments a "
                "INNER JOIN employee_contacts ec ON ec.id = a.employee_contact_id "
                "WHERE TRIM(COALESCE(ec.linked_auth_user_id, '')) = :uid "
                "AND a.employee_user_id IS NULL "
                "AND LOWER(TRIM(COALESCE(a.employee_link_mode, ''))) = 'pending_claim' "
                "ORDER BY a.created_at DESC",
                {"uid": uid},
                op_name="list_pending_claim_assignments_for_auth_user",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def dismiss_pending_claim_assignment_for_auth_user(
        self,
        assignment_id: str,
        auth_user_id: str,
        request_id: Optional[str] = None,
    ) -> bool:
        """Mark pending_claim assignment as dismissed for this user (no account link). Returns True if updated."""
        aid = (assignment_id or "").strip()
        uid = (auth_user_id or "").strip()
        if not aid or not uid:
            return False
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            res = self._exec(
                conn,
                "UPDATE case_assignments SET employee_link_mode = 'dismissed', updated_at = :ua "
                "WHERE id = :aid AND employee_user_id IS NULL "
                "AND LOWER(TRIM(COALESCE(employee_link_mode, ''))) = 'pending_claim' "
                "AND employee_contact_id IN ("
                "  SELECT id FROM employee_contacts WHERE TRIM(COALESCE(linked_auth_user_id, '')) = :uid"
                ")",
                {"aid": aid, "uid": uid, "ua": now},
                op_name="dismiss_pending_claim_assignment_for_auth_user",
                request_id=request_id,
            )
            try:
                rc = res.rowcount
            except Exception:
                rc = 0
        return bool(rc and rc > 0)

    def get_pending_claim_invite_token_for_assignment(self, assignment_id: str) -> Optional[str]:
        if not (assignment_id or "").strip():
            return None
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT token FROM assignment_claim_invites "
                        "WHERE assignment_id = :aid AND status = 'pending' LIMIT 1"
                    ),
                    {"aid": assignment_id.strip()},
                ).fetchone()
            if not row:
                return None
            m = row._mapping if hasattr(row, "_mapping") else dict(row)
            return str(m["token"]) if m.get("token") else None
        except (OperationalError, ProgrammingError):
            return None

    def set_admin_session(self, token: str, actor_user_id: str, target_user_id: str, mode: str) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT OR REPLACE INTO admin_sessions (token, actor_user_id, target_user_id, mode, created_at) "
                "VALUES (:token, :actor, :target, :mode, :created_at)"
            ), {"token": token, "actor": actor_user_id, "target": target_user_id, "mode": mode, "created_at": now})

    def clear_admin_session(self, token: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM admin_sessions WHERE token = :token"), {"token": token})

    def get_admin_session(self, token: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM admin_sessions WHERE token = :token"), {"token": token}).fetchone()
        return self._row_to_dict(row)
