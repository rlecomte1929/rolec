"""[AUDIT-C1.4] Auth-domain DB methods, extracted from backend/database.py.

Session tokens, claim-invite lookups, and admin-session helpers. These were
methods on the monolithic ``Database`` class; they live here as a mixin
(:class:`AuthMixin`) that ``Database`` inherits, so every caller
(``db.get_user_by_token(...)`` etc.) keeps working unchanged via normal MRO.
Login behaviour is byte-for-byte identical — this is a pure relocation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from ..db_config import DATABASE_URL as _raw_url

log = logging.getLogger(__name__)

_is_sqlite = _raw_url.startswith("sqlite")

# SEC-FE-1 (AIQ-1168): bound the ReloPass session-token lifetime. Tokens live in
# localStorage (JS-readable, Option A pre-launch), so an absolute TTL caps the
# window a stolen token is usable. Expiry is derived from the existing created_at
# column (created_at + TTL) — no schema change, and checked in Python so the
# validation query stays a single cross-DB SELECT. A 401 from an expired token
# routes the user back to login (the existing client.ts interceptor); a seamless
# sliding/refresh-token mechanism is a documented follow-up.
SESSION_TTL_DAYS = 14


def _parse_role_rows(raw: Any) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return []
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        if not role:
            continue
        out.append({"role": role, "is_primary": bool(item.get("is_primary"))})
    return out


def _session_is_expired(created_at: Optional[str]) -> bool:
    """True if a session is older than SESSION_TTL_DAYS. A missing/garbage
    created_at is treated as EXPIRED (fail-closed) — every session row has one."""
    if not created_at:
        return True
    try:
        created = datetime.fromisoformat(
            str(created_at).replace("Z", "+00:00")
        ).replace(tzinfo=None)
    except (ValueError, TypeError):
        return True
    return created + timedelta(days=SESSION_TTL_DAYS) <= datetime.utcnow()


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
            row = conn.execute(
                text("SELECT user_id, created_at FROM sessions WHERE token = :token"),
                {"token": token},
            ).fetchone()
        if not row:
            return None
        # SEC-FE-1: reject sessions past their TTL (treat an expired token as
        # unknown, so the caller 401s and the user re-authenticates).
        if _session_is_expired(row._mapping.get("created_at")):
            return None
        return self.get_user_by_id(row._mapping["user_id"])

    def get_user_context_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """One round-trip: session + user row + user_roles (WS2 Task 2.7).

        Replaces ``get_user_by_token`` (which itself calls ``get_user_by_id``)
        plus ``get_user_roles``. Returns the users-row dict (same keys as
        ``get_user_by_id``) plus ``role_rows`` in the shape ``get_user_roles``
        returns. ``get_admin_session`` stays a separate call.

        Also keeps the keys ``backend.main.get_current_user`` already reads
        from this method (``full_name``, ``company_id``, ``is_admin``).
        """
        if _is_sqlite:
            roles_sql = (
                "(SELECT json_group_array(json_object("
                "'role', ur.role, 'is_primary', ur.is_primary)) "
                "FROM user_roles ur WHERE ur.user_id = u.id)"
            )
            company_sql = "CAST(p.company_id AS TEXT)"
            profile_join = "LEFT JOIN profiles p ON CAST(p.id AS TEXT) = CAST(u.id AS TEXT)"
        else:
            roles_sql = (
                "(SELECT json_agg(json_build_object("
                "'role', ur.role, 'is_primary', ur.is_primary)) "
                "FROM user_roles ur WHERE ur.user_id = u.id)"
            )
            company_sql = "p.company_id::text"
            profile_join = "LEFT JOIN profiles p ON p.id::text = u.id"

        sql_with_roles = (
            "SELECT u.*, s.created_at AS session_created_at, "
            f"p.full_name AS profile_full_name, {company_sql} AS company_id, "
            f"{roles_sql} AS role_rows "
            "FROM sessions s "
            "JOIN users u ON u.id = s.user_id "
            f"{profile_join} "
            "WHERE s.token = :token LIMIT 1"
        )
        sql_no_roles = (
            "SELECT u.*, s.created_at AS session_created_at, "
            f"p.full_name AS profile_full_name, {company_sql} AS company_id "
            "FROM sessions s "
            "JOIN users u ON u.id = s.user_id "
            f"{profile_join} "
            "WHERE s.token = :token LIMIT 1"
        )

        row = None
        try:
            with self.engine.connect() as conn:
                row = conn.execute(text(sql_with_roles), {"token": token}).fetchone()
        except (OperationalError, ProgrammingError):
            with self.engine.connect() as conn:
                row = conn.execute(text(sql_no_roles), {"token": token}).fetchone()
        if not row:
            return None
        payload = self._row_to_dict(row)
        if not payload:
            return None
        session_created_at = payload.pop("session_created_at", None)
        if _session_is_expired(session_created_at):
            return None
        profile_full_name = payload.pop("profile_full_name", None)
        role_rows = _parse_role_rows(payload.pop("role_rows", None))
        # users.created_at can be shadowed by the session alias on some drivers;
        # the users-row shape is otherwise SELECT u.*.
        payload["full_name"] = profile_full_name if profile_full_name is not None else payload.get("name")
        payload["is_admin"] = (str(payload.get("role") or "")).lower() == "admin"
        payload["role_rows"] = role_rows
        return payload

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

    def is_auth_email_confirmed(self, email: Optional[str]) -> bool:
        """True iff a Supabase auth user with this email exists AND has confirmed it
        (email_confirmed_at set). Gate for verified-email auto-link. Fails CLOSED
        (returns False) on any error — including SQLite tests with no auth schema — so
        an unverifiable email never auto-links (the employee falls back to manual accept)."""
        e = (email or "").strip()
        if not e:
            return False
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT 1 FROM auth.users "
                        "WHERE LOWER(email) = LOWER(:e) AND email_confirmed_at IS NOT NULL LIMIT 1"
                    ),
                    {"e": e},
                ).fetchone()
            return bool(row)
        except Exception:
            return False

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
        # [AIQ-1362] One identity, many roles: this account is now the employee on an
        # assignment, so it also holds an EMPLOYEE role. Add it idempotently rather than
        # rejecting on the unique-email wall (e.g. an existing HR user being relocated
        # gains EMPLOYEE without a duplicate account). is_primary stays false so the
        # user's existing primary role is untouched. Wrapped so a missing junction
        # (pre-migration / SQLite without the table) never breaks the contact link.
        try:
            with self.engine.begin() as conn:
                self._exec(
                    conn,
                    "INSERT INTO user_roles (user_id, role, is_primary) "
                    "VALUES (:uid, 'EMPLOYEE', :fp) "
                    "ON CONFLICT (user_id, role) DO NOTHING",
                    {"uid": user_id.strip(), "fp": False},
                    op_name="link_user_employee_role_upsert",
                    request_id=request_id,
                )
        except Exception as exc:
            log.warning(
                "link_employee_contact_to_auth_user: EMPLOYEE user_roles upsert failed user_id=%s err=%s",
                user_id.strip()[:8],
                exc,
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
        # AIQ-2091: portable upsert keyed on admin_sessions_pkey (token). The prior
        # `INSERT OR REPLACE` is SQLite-only and 500s on Postgres (42601 syntax error),
        # so `POST /api/admin/impersonate/start` failed in prod. `ON CONFLICT ... DO
        # UPDATE` works on both dialects (SQLite >= 3.24, Postgres).
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO admin_sessions (token, actor_user_id, target_user_id, mode, created_at) "
                "VALUES (:token, :actor, :target, :mode, :created_at) "
                "ON CONFLICT (token) DO UPDATE SET "
                "actor_user_id = excluded.actor_user_id, "
                "target_user_id = excluded.target_user_id, "
                "mode = excluded.mode, "
                "created_at = excluded.created_at"
            ), {"token": token, "actor": actor_user_id, "target": target_user_id, "mode": mode, "created_at": now})

    def clear_admin_session(self, token: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM admin_sessions WHERE token = :token"), {"token": token})

    def get_admin_session(self, token: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM admin_sessions WHERE token = :token"), {"token": token}).fetchone()
        return self._row_to_dict(row)
