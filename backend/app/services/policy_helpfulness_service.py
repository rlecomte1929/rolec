"""End-user helpfulness writer (WS-E).

Records a single end-user thumbs up/down ("was this answer helpful?") on a policy
answer into ``policy_answer_helpfulness``. The company tenant is derived by joining
to the answer's trace (``policy_assistant_traces``) on POST — mirroring how
``ai_feedback_service.record_feedback`` derives prompt attribution — so the caller
only sends the trace id, the boolean, and an optional comment.

The write is idempotent on ``(trace_session_id, user_id)`` via an upsert, so a user
flipping their vote updates the row instead of duplicating it.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.exc import DataError

from ..db import SessionLocal

log = logging.getLogger(__name__)


class UnknownTraceError(Exception):
    """Raised when the referenced trace_session_id has no trace row."""


def _lookup_trace_company(s: Any, trace_session_id: str) -> Optional[Dict[str, Any]]:
    """Return the trace's company (tenant), or None if the trace is unknown.

    ``policy_assistant_traces.id`` is uuid in Postgres, so a malformed (non-uuid)
    ``trace_session_id`` makes ``WHERE id = :tid`` raise a cast error (a 500) rather
    than matching no rows. Catch that and treat the trace as unknown → the caller
    raises UnknownTraceError → the endpoint returns 404, not 500. (SQLite's text id
    never casts, so this is a no-op there and existing text-id tests are unaffected.)
    """
    try:
        row = (
            s.execute(
                text(
                    "SELECT id, company_id FROM policy_assistant_traces WHERE id = :tid"
                ),
                {"tid": trace_session_id},
            )
            .mappings()
            .first()
        )
    except DataError:
        s.rollback()  # the bad-uuid cast aborts the tx; clear it before we bail
        return None
    return dict(row) if row else None


def record_helpfulness(
    *,
    trace_session_id: str,
    user_id: str,
    helpful: bool,
    comment: Optional[str] = None,
    session: Any = None,
) -> Dict[str, Any]:
    """Upsert an end-user helpfulness vote; derive the tenant from the trace.

    Idempotent on ``(trace_session_id, user_id)``. Raises
    :class:`UnknownTraceError` when the trace does not exist.
    """
    own = session is None
    s = session or SessionLocal()
    try:
        trace = _lookup_trace_company(s, trace_session_id)
        if trace is None:
            raise UnknownTraceError(trace_session_id)

        company_id = trace.get("company_id")
        row_id = str(uuid.uuid4())

        s.execute(
            text(
                "INSERT INTO policy_answer_helpfulness "
                "(id, trace_session_id, company_id, user_id, helpful, comment) "
                "VALUES (:id, :tsid, :cid, :uid, :helpful, :comment) "
                "ON CONFLICT (trace_session_id, user_id) DO UPDATE SET "
                "  helpful = excluded.helpful, "
                "  comment = excluded.comment"
            ),
            {
                "id": row_id,
                "tsid": trace_session_id,
                "cid": company_id,
                "uid": user_id,
                "helpful": helpful,
                "comment": comment,
            },
        )
        s.commit()

        saved = (
            s.execute(
                text(
                    "SELECT id, trace_session_id, company_id, user_id, helpful, comment "
                    "FROM policy_answer_helpfulness "
                    "WHERE trace_session_id = :tsid AND user_id = :uid"
                ),
                {"tsid": trace_session_id, "uid": user_id},
            )
            .mappings()
            .first()
        )
        row = dict(saved)
        # `helpful` may come back as 1/0 (SQLite) or bool (Postgres) — normalise.
        return {
            "id": str(row["id"]),
            "trace_session_id": str(row["trace_session_id"]),
            "company_id": str(row["company_id"]) if row["company_id"] is not None else None,
            "user_id": str(row["user_id"]),
            "helpful": bool(row["helpful"]),
            "comment": row["comment"],
        }
    except Exception:
        s.rollback()
        raise
    finally:
        if own:
            s.close()
