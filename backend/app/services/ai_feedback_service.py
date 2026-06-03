"""
AI human-feedback writer (Parker Step E).

Records a single human review verdict (approved / rejected / edited) into
``ai_human_feedback``, attributed to the prompt-registry version + canary arm
(Step D) that served the original request. Attribution is derived by joining to
the request's trace (``policy_assistant_traces``) on POST, so the caller (the
Notion review skill) only has to send the trace id and the verdict.

The write is idempotent on ``(trace_session_id, reviewer_user_id)`` via an upsert,
so re-submitting a review updates the verdict instead of duplicating it.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import JSON, bindparam, text

from ..db import SessionLocal

log = logging.getLogger(__name__)

VALID_VERDICTS = ("approved", "rejected", "edited")


class UnknownTraceError(Exception):
    """Raised when the referenced trace_session_id has no trace row."""


def _lookup_trace_attribution(s: Any, trace_session_id: str) -> Optional[Dict[str, Any]]:
    """Return the prompt attribution for a trace, or None if the trace is unknown."""
    row = (
        s.execute(
            text(
                "SELECT id, prompt_version_id, canary_arm "
                "FROM policy_assistant_traces WHERE id = :tid"
            ),
            {"tid": trace_session_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def record_feedback(
    *,
    trace_session_id: str,
    reviewer_user_id: str,
    verdict: str,
    edited_output_json: Optional[Dict[str, Any]] = None,
    comment: Optional[str] = None,
    session: Any = None,
) -> Dict[str, Any]:
    """Upsert a human review verdict; attribute it to the trace's prompt version/arm.

    Idempotent on ``(trace_session_id, reviewer_user_id)``. Raises
    :class:`ValueError` on a bad verdict and :class:`UnknownTraceError` when the
    trace does not exist.
    """
    if verdict not in VALID_VERDICTS:
        raise ValueError(f"invalid verdict: {verdict}")

    own = session is None
    s = session or SessionLocal()
    try:
        trace = _lookup_trace_attribution(s, trace_session_id)
        if trace is None:
            raise UnknownTraceError(trace_session_id)

        prompt_version_id = trace.get("prompt_version_id")
        canary_arm = trace.get("canary_arm")
        row_id = str(uuid.uuid4())

        stmt = text(
            "INSERT INTO ai_human_feedback "
            "(id, trace_session_id, reviewer_user_id, verdict, edited_output_json, "
            " comment, prompt_version_id, canary_arm) "
            "VALUES (:id, :tsid, :rid, :verdict, :edited, :comment, :pvid, :arm) "
            "ON CONFLICT (trace_session_id, reviewer_user_id) DO UPDATE SET "
            "  verdict = excluded.verdict, "
            "  edited_output_json = excluded.edited_output_json, "
            "  comment = excluded.comment"
        ).bindparams(bindparam("edited", type_=JSON(none_as_null=True)))

        s.execute(
            stmt,
            {
                "id": row_id,
                "tsid": trace_session_id,
                "rid": reviewer_user_id,
                "verdict": verdict,
                "edited": edited_output_json,
                "comment": comment,
                "pvid": prompt_version_id,
                "arm": canary_arm,
            },
        )
        s.commit()

        saved = (
            s.execute(
                text(
                    "SELECT id, trace_session_id, reviewer_user_id, verdict, "
                    "prompt_version_id, canary_arm "
                    "FROM ai_human_feedback "
                    "WHERE trace_session_id = :tsid AND reviewer_user_id = :rid"
                ),
                {"tsid": trace_session_id, "rid": reviewer_user_id},
            )
            .mappings()
            .first()
        )
        return {k: (str(v) if v is not None else None) for k, v in dict(saved).items()}
    except Exception:
        s.rollback()
        raise
    finally:
        if own:
            s.close()
