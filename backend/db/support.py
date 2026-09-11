"""[AUDIT-C1.6a] Support-domain DB methods, extracted from backend/database.py.

These were methods on the monolithic ``Database`` class; they live here as a
mixin (:class:`SupportMixin`) that ``Database`` inherits, so every caller keeps
working unchanged via normal MRO. Pure relocation; ``..database`` module
helpers are imported lazily in-method to avoid an import cycle.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import logging
import uuid

from sqlalchemy import text

from ..db_config import DATABASE_URL as _raw_url

log = logging.getLogger(__name__)

_is_sqlite = _raw_url.startswith("sqlite")

# [AIQ-1610] Notification types that default to email-ON when the recipient has no explicit
# notification_preferences row. An explicit preference still wins (opt-out is respected). This
# makes the policy-exception lifecycle actually enqueue an outbox row by default, so the consumer
# delivers it: REQUESTED → the assigned HR (over-cap alert); DECIDED → the employee (the outcome
# of the request they filed).
_EMAIL_DEFAULT_ON = {"POLICY_EXCEPTION_REQUESTED", "POLICY_EXCEPTION_DECIDED"}


class SupportMixin:
    """Support-domain methods mixed into :class:`backend.database.Database`."""

    def list_exception_requests(
        self,
        case_id: str,
        assignment_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return all exception_request rows for a case, ordered blockers first
        then by created_at DESC.

        If assignment_id is also supplied, returns only rows matching that
        assignment (useful for assignment-scoped timeline endpoints).
        """
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            if assignment_id:
                rows = self._exec(
                    conn,
                    """SELECT id, case_id, assignment_id, exception_type, reason, severity,
                       status, recommended_action, resolved_at, resolved_by,
                       resolution_notes, created_at, updated_at
                       FROM exception_requests
                       WHERE case_id = :cid AND assignment_id = :aid
                       ORDER BY
                         CASE severity WHEN 'blocker' THEN 0 ELSE 1 END ASC,
                         created_at DESC""",
                    {"cid": cid, "aid": assignment_id},
                    op_name="list_exception_requests",
                    request_id=request_id,
                ).fetchall()
            else:
                rows = self._exec(
                    conn,
                    """SELECT id, case_id, assignment_id, exception_type, reason, severity,
                       status, recommended_action, resolved_at, resolved_by,
                       resolution_notes, created_at, updated_at
                       FROM exception_requests
                       WHERE case_id = :cid
                       ORDER BY
                         CASE severity WHEN 'blocker' THEN 0 ELSE 1 END ASC,
                         created_at DESC""",
                    {"cid": cid},
                    op_name="list_exception_requests",
                    request_id=request_id,
                ).fetchall()
        return self._rows_to_list(rows)

    def upsert_exception_request(
        self,
        case_id: str,
        exception_type: str,
        reason: str,
        severity: str,
        *,
        assignment_id: Optional[str] = None,
        recommended_action: Optional[str] = None,
        status: str = "pending",
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Insert a new exception_request row, or update the reason/severity/
        recommended_action on an existing one if (case_id, exception_type)
        already exists with status='pending'.

        Rows that have been resolved (approved/denied/withdrawn) are left
        untouched — a new pending row is inserted alongside them instead.
        """
        cid = self.coalesce_case_lookup_id(case_id)
        now = datetime.utcnow().isoformat()

        # Try to UPDATE an existing pending row first (idempotent re-run).
        with self.engine.begin() as conn:
            result = self._exec(
                conn,
                """UPDATE exception_requests
                   SET reason = :reason, severity = :sev,
                       recommended_action = :ra, updated_at = :now
                   WHERE case_id = :cid
                     AND exception_type = :et
                     AND status = 'pending'""",
                {
                    "cid": cid,
                    "et": exception_type,
                    "reason": reason,
                    "sev": severity,
                    "ra": recommended_action,
                    "now": now,
                },
                op_name="update_exception_request",
                request_id=request_id,
            )
            updated = getattr(result, "rowcount", 0)

        if updated and updated > 0:
            # Fetch the row we just updated.
            with self.engine.connect() as conn:
                row = self._exec(
                    conn,
                    """SELECT * FROM exception_requests
                       WHERE case_id = :cid AND exception_type = :et
                         AND status = 'pending'
                       ORDER BY updated_at DESC LIMIT 1""",
                    {"cid": cid, "et": exception_type},
                    op_name="get_exception_request",
                    request_id=request_id,
                ).fetchone()
            return self._row_to_dict(row) or {}

        # No existing pending row — insert a new one.
        eid = str(uuid.uuid4())
        with self.engine.begin() as conn:
            self._exec(
                conn,
                """INSERT INTO exception_requests
                   (id, case_id, assignment_id, exception_type, reason, severity,
                    status, recommended_action, created_at, updated_at)
                   VALUES (:id, :cid, :aid, :et, :reason, :sev,
                           :status, :ra, :now, :now)""",
                {
                    "id": eid,
                    "cid": cid,
                    "aid": assignment_id,
                    "et": exception_type,
                    "reason": reason,
                    "sev": severity,
                    "status": status,
                    "ra": recommended_action,
                    "now": now,
                },
                op_name="insert_exception_request",
                request_id=request_id,
            )
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT * FROM exception_requests WHERE id = :id",
                {"id": eid},
                op_name="get_exception_request",
                request_id=request_id,
            ).fetchone()
        return self._row_to_dict(row) or {}

    def update_exception_request(
        self,
        case_id: str,
        exception_id: str,
        status: str,
        *,
        resolved_by: Optional[str] = None,
        resolution_notes: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update the status (and optional resolution fields) of an existing
        exception_request row.

        Rules:
          • Verifies the row belongs to case_id before updating (prevents
            cross-case tampering via the API).
          • Sets resolved_at = UTC now when moving to approved / denied /
            escalated / withdrawn.
          • Returns the updated row as a dict, or None if the row was not
            found or does not belong to the given case.

        Valid target statuses: approved | denied | escalated | withdrawn.
        (The 'pending' status is managed by upsert_exception_request only.)
        """
        cid = self.coalesce_case_lookup_id(case_id)
        now = datetime.utcnow().isoformat()
        resolved_statuses = {"approved", "denied", "escalated", "withdrawn"}
        resolved_at = now if status in resolved_statuses else None

        with self.engine.begin() as conn:
            result = self._exec(
                conn,
                """UPDATE exception_requests
                   SET status           = :status,
                       resolved_by      = :resolved_by,
                       resolution_notes = :resolution_notes,
                       resolved_at      = :resolved_at,
                       updated_at       = :now
                   WHERE id = :eid
                     AND case_id = :cid""",
                {
                    "status": status,
                    "resolved_by": resolved_by,
                    "resolution_notes": resolution_notes,
                    "resolved_at": resolved_at,
                    "now": now,
                    "eid": exception_id,
                    "cid": cid,
                },
                op_name="update_exception_request_status",
                request_id=request_id,
            )
            updated = getattr(result, "rowcount", 0)

        if not updated:
            return None  # row not found or wrong case_id

        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT * FROM exception_requests WHERE id = :eid",
                {"eid": exception_id},
                op_name="get_exception_request",
                request_id=request_id,
            ).fetchone()
        return self._row_to_dict(row) or None

    def _get_notification_preference(
        self, user_id: str, type_: str
    ) -> Optional[Dict[str, Any]]:
        """6C: Get preference for user/type. Returns None if no row or table missing (use defaults)."""
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT in_app, email, muted_until FROM notification_preferences "
                        "WHERE user_id::text = :uid AND type = :type"
                    ),
                    {"uid": str(user_id), "type": type_},
                ).fetchone()
            if row:
                return {"in_app": row._mapping.get("in_app"), "email": row._mapping.get("email"), "muted_until": row._mapping.get("muted_until")}
        except Exception as e:
            log.debug("notification_preferences not available: %s", e)
        return None

    def _insert_notification_outbox(
        self,
        notification_id: str,
        user_id: str,
        to_email: str,
        type_: str,
        payload: Dict[str, Any],
    ) -> None:
        """6C: Insert outbox row for email delivery. No-op if table missing."""
        try:
            outbox_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            payload_json = json.dumps(payload)
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO notification_outbox "
                        "(id, notification_id, user_id, to_email, type, payload, status) "
                        "VALUES (:id, :nid, :uid, :email, :type, CAST(:payload AS jsonb), 'pending')"
                    ),
                    {
                        "id": outbox_id, "nid": notification_id, "uid": user_id,
                        "email": to_email, "type": type_, "payload": payload_json,
                    },
                )
        except Exception as e:
            log.warning("Failed to insert notification outbox: %s", e)

    def create_notification_with_preferences(
        self,
        user_id: str,
        type_: str,
        title: str,
        body: Optional[str] = None,
        assignment_id: Optional[str] = None,
        case_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """6C: Create notification respecting preferences and muted_until. Returns notification id or None."""
        pref = self._get_notification_preference(user_id, type_)
        in_app = True
        # [AIQ-1610] Default email on for opt-in-by-default types (e.g. policy-exception → HR);
        # a stored preference below still overrides this.
        email = type_ in _EMAIL_DEFAULT_ON
        muted_until = None
        if pref:
            in_app = pref.get("in_app") if pref.get("in_app") is not None else True
            email = pref.get("email") or False
            muted_until = pref.get("muted_until")
        if muted_until:
            try:
                if isinstance(muted_until, str):
                    muted_dt = datetime.fromisoformat(muted_until.replace("Z", "+00:00"))
                else:
                    muted_dt = muted_until
                if muted_dt and muted_dt > datetime.utcnow():
                    return None
            except Exception:
                pass
        if not in_app and not email:
            return None
        notification_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        meta_json = json.dumps(metadata or {})
        with self.engine.begin() as conn:
                conn.execute(
                text(
                    "INSERT INTO notifications (id, created_at, user_id, assignment_id, case_id, type, title, body, metadata) "
                    "VALUES (:id, :ca, :uid, :aid, :cid, :type, :title, :body, :meta)"
                ),
                {
                    "id": notification_id, "ca": now, "uid": user_id, "aid": assignment_id,
                    "cid": case_id, "type": type_, "title": title, "body": body, "meta": meta_json,
                },
            )
        if email:
            user = self.get_user_by_id(user_id)
            to_email = (user or {}).get("email") or ""
            if to_email:
                self._insert_notification_outbox(
                    notification_id=notification_id,
                    user_id=user_id,
                    to_email=to_email,
                    type_=type_,
                    payload={
                        "title": title,
                        "body": body or "",
                        "assignment_id": assignment_id,
                        "case_id": case_id,
                        **(metadata or {}),
                    },
                )
        return notification_id

    def insert_notification(
        self,
        notification_id: str,
        user_id: str,
        type_: str,
        title: str,
        body: Optional[str] = None,
        assignment_id: Optional[str] = None,
        case_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        meta_json = json.dumps(metadata or {})
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO notifications (id, created_at, user_id, assignment_id, case_id, type, title, body, metadata) "
                "VALUES (:id, :ca, :uid, :aid, :cid, :type, :title, :body, :meta)"
            ), {
                "id": notification_id, "ca": now, "uid": user_id, "aid": assignment_id,
                "cid": case_id, "type": type_, "title": title, "body": body, "meta": meta_json,
            })

    def list_notifications(
        self,
        user_id: str,
        limit: int = 25,
        only_unread: bool = False,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            # Compare as text: notifications.user_id is uuid in prod, but HR
            # ReloPass ids are legacy strings (seed-hr-testingapril). Equality
            # without ::text 500s the bell: invalid input syntax for type uuid.
            q = (
                "SELECT id, created_at, assignment_id, case_id, type, title, body, metadata, read_at "
                "FROM notifications WHERE user_id::text = :uid"
            )
            if only_unread:
                q += " AND read_at IS NULL"
            q += " ORDER BY created_at DESC LIMIT :lim"
            rows = self._exec(
                conn,
                q,
                {"uid": user_id, "lim": min(limit, 100)},
                op_name="list_notifications",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def count_unread_notifications(self, user_id: str, request_id: Optional[str] = None) -> int:
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT COUNT(*) FROM notifications WHERE user_id::text = :uid AND read_at IS NULL",
                {"uid": user_id},
                op_name="count_unread_notifications",
                request_id=request_id,
            ).fetchone()
        return row[0] if row else 0

    def mark_notification_read(self, notification_id: str, user_id: str) -> bool:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            result = conn.execute(text(
                "UPDATE notifications SET read_at = :ra WHERE id = :id AND user_id::text = :uid"
            ), {"ra": now, "id": notification_id, "uid": user_id})
        return result.rowcount > 0

    def add_support_note(self, support_case_id: str, author_user_id: str, note: str) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO support_case_notes (id, support_case_id, author_user_id, note, created_at) "
                "VALUES (:id, :sid, :uid, :note, :created_at)"
            ), {"id": str(uuid.uuid4()), "sid": support_case_id, "uid": author_user_id, "note": note, "created_at": now})

    def list_support_notes(self, support_case_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM support_case_notes WHERE support_case_id = :sid ORDER BY created_at DESC"
            ), {"sid": support_case_id}).fetchall()
        return self._rows_to_list(rows)

    def create_message(
        self,
        message_id: str,
        assignment_id: Optional[str],
        hr_user_id: Optional[str],
        employee_identifier: Optional[str],
        subject: str,
        body: str,
        status: str = "draft",
        sender_user_id: Optional[str] = None,
        recipient_user_id: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        sender = sender_user_id or hr_user_id
        recipient = recipient_user_id
        if not recipient and assignment_id and hr_user_id:
            # HR sent: recipient is employee
            assignment = self.get_assignment_by_id(assignment_id)
            if assignment and assignment.get("employee_user_id"):
                recipient = assignment["employee_user_id"]
            elif assignment and employee_identifier:
                user = self.get_user_by_identifier(employee_identifier)
                if user:
                    recipient = user["id"]
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO messages (id, assignment_id, hr_user_id, employee_identifier, subject, body, status, created_at, delivered_at, sender_user_id, recipient_user_id) "
                "VALUES (:id, :aid, :hr, :emp, :sub, :body, :status, :created_at, :delivered_at, :sender, :recipient)"
            ), {
                "id": message_id,
                "aid": assignment_id,
                "hr": hr_user_id,
                "emp": employee_identifier,
                "sub": subject,
                "body": body,
                "status": status,
                "created_at": now,
                "delivered_at": now,
                "sender": sender,
                "recipient": recipient,
            })

    def upsert_message_conversation_pref(
        self, user_id: str, assignment_id: str, archived: bool
    ) -> None:
        """Soft-archive or restore a conversation in the HR user's list (per user_id + assignment_id)."""
        from ..database import _eq_text  # lazy: avoid import cycle
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            if archived:
                if _is_sqlite:
                    conn.execute(
                        text(
                            "INSERT INTO message_conversation_prefs (user_id, assignment_id, archived_at) "
                            "VALUES (:u, :a, :now) ON CONFLICT (user_id, assignment_id) "
                            "DO UPDATE SET archived_at = excluded.archived_at"
                        ),
                        {"u": user_id, "a": assignment_id, "now": now},
                    )
                else:
                    conn.execute(
                        text(
                            "INSERT INTO message_conversation_prefs (user_id, assignment_id, archived_at) "
                            "VALUES (:u, :a, :now) ON CONFLICT (user_id, assignment_id) "
                            "DO UPDATE SET archived_at = EXCLUDED.archived_at"
                        ),
                        {"u": user_id, "a": assignment_id, "now": now},
                    )
            else:
                conn.execute(
                    text(
                        f"DELETE FROM message_conversation_prefs "
                        f"WHERE {_eq_text('user_id', ':u')} AND {_eq_text('assignment_id', ':a')}"
                    ),
                    {"u": user_id, "a": assignment_id},
                )

    def get_message_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Single message row by id (cross-type-safe id match on Postgres)."""
        from ..database import _eq_text  # lazy: avoid import cycle
        with self.engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT * FROM messages WHERE {_eq_text('id', ':mid')}"),
                {"mid": message_id},
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def delete_message_by_id(self, message_id: str) -> bool:
        """Hard-delete one message row. Caller must enforce authorization."""
        from ..database import _eq_text  # lazy: avoid import cycle
        with self.engine.begin() as conn:
            result = conn.execute(
                text(f"DELETE FROM messages WHERE {_eq_text('id', ':mid')}"),
                {"mid": message_id},
            )
        rc = getattr(result, "rowcount", None)
        return bool(rc and rc > 0)

    def list_messages_for_employee(self, employee_user_id: str, request_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """All HR↔employee platform messages across every linked assignment."""
        linked = self.list_linked_assignments_for_employee(employee_user_id, request_id=request_id)
        if not linked:
            return []
        aids = [str(a["id"]).strip() for a in linked if a.get("id")]
        aids = [x for x in aids if x]
        if not aids:
            return []
        n = len(aids)
        placeholders = ", ".join(f":a{i}" for i in range(n))
        params: Dict[str, Any] = {f"a{i}": aids[i] for i in range(n)}
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                f"SELECT * FROM messages WHERE assignment_id IN ({placeholders}) ORDER BY created_at ASC",
                params,
                op_name="list_messages_for_employee",
                request_id=request_id,
            ).fetchall()
        return self._rows_to_list(rows)

    def dismiss_message_notification(self, message_id: str, recipient_user_id: str) -> bool:
        """Set dismissed_at for one message. Returns True if updated."""
        from ..database import _eq_text  # lazy: avoid import cycle
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE messages SET dismissed_at = :now "
                    f"WHERE {_eq_text('id', ':mid')} "
                    f"AND {_eq_text('recipient_user_id', ':uid')} AND dismissed_at IS NULL"
                ),
                {"now": now, "mid": message_id, "uid": recipient_user_id},
            )
        return (result.rowcount if hasattr(result, "rowcount") else 0) > 0

    def get_unread_message_count(self, recipient_user_id: str) -> int:
        """Count messages where recipient hasn't read and hasn't dismissed."""
        from ..database import _eq_text  # lazy: avoid import cycle
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT COUNT(*) as n FROM messages "
                    f"WHERE {_eq_text('recipient_user_id', ':uid')} "
                    "AND read_at IS NULL AND dismissed_at IS NULL"
                ),
                {"uid": recipient_user_id},
            ).fetchone()
        return row[0] if row else 0

    def list_unread_message_notifications(
        self, recipient_user_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List unread, non-dismissed messages for the recipient with sender name and snippet."""
        from ..database import _eq_text  # lazy: avoid import cycle
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(f"""
                SELECT m.id as message_id, m.assignment_id as conversation_id,
                       m.body, m.created_at,
                       COALESCE(u.name, u.email, u.username, 'HR') as sender_name
                FROM messages m
                LEFT JOIN users u ON {_eq_text("u.id", "COALESCE(m.sender_user_id, m.hr_user_id)")}
                WHERE {_eq_text("m.recipient_user_id", ":uid")}
                  AND m.read_at IS NULL AND m.dismissed_at IS NULL
                ORDER BY m.created_at DESC
                LIMIT :lim
            """),
                {"uid": recipient_user_id, "lim": limit},
            ).fetchall()
        out = []
        for r in rows:
            row = dict(r._mapping)
            body = (row.get("body") or "")[:80]
            if len((row.get("body") or "")) > 80:
                body = body.rstrip() + "…"
            out.append({
                "message_id": row.get("message_id"),
                "conversation_id": row.get("conversation_id") or row.get("assignment_id"),
                "sender_name": row.get("sender_name") or "HR",
                "snippet": body,
                "created_at": row.get("created_at"),
            })
        return out
