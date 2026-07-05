"""AIQ-1414 Phase 2b — persistent Mobility Coordinator session-state store.

Durable per-relocation "memory" row (``ai_coordinator_sessions``) for the Option-B
coordinator: a bounded rolling summary + the last few verbatim turns + an event cursor,
one row per HR-surface case. Mirrors the ``interview_sessions`` persistence pattern
(get-or-create, ``SELECT … FOR UPDATE`` on write, service-role connection with in-app
company scoping). No LLM here — the coordinator turn (Phase 2b-ii) composes this store
with ``coordinator_context_builder`` and the Anthropic call.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

log = logging.getLogger(__name__)

MODEL_DEFAULT = "claude-sonnet-4-6"
# Keep the last N turns verbatim; older turns fold into ``rolling_summary`` (Phase 2b-ii).
MAX_RECENT_TURNS = 6

_COLUMNS = (
    "id, case_id, employee_id, company_id, rolling_summary, recent_turns, "
    "last_event_cursor, model, status, started_at, last_active_at, updated_at"
)


def _get_db():
    from ...database import db as main_db

    return main_db


# ── pure state helpers (unit-testable) ────────────────────────────────────────


def append_turn(session: Dict[str, Any], user_msg: str, assistant_msg: str) -> Dict[str, Any]:
    """Append one conversational turn to ``recent_turns`` (in place, returned)."""
    turns: List[Dict[str, Any]] = list(session.get("recent_turns") or [])
    turns.append({"user": user_msg, "assistant": assistant_msg})
    session["recent_turns"] = turns
    return session


def needs_fold(session: Dict[str, Any], *, max_turns: int = MAX_RECENT_TURNS) -> bool:
    """Whether verbatim turns exceed the window and should fold into the summary."""
    return len(session.get("recent_turns") or []) > max_turns


def _row_to_dict(row: Any) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    d = dict(row)
    rt = d.get("recent_turns")
    if isinstance(rt, str):  # SQLite returns TEXT for jsonb; PG returns a list
        try:
            d["recent_turns"] = json.loads(rt)
        except Exception:  # noqa: BLE001
            d["recent_turns"] = []
    elif rt is None:
        d["recent_turns"] = []
    return d


# ── DB I/O ────────────────────────────────────────────────────────────────────


def _select(conn: Any, case_id: str) -> Any:
    return (
        conn.execute(
            text(f"SELECT {_COLUMNS} FROM ai_coordinator_sessions WHERE case_id = :c"),
            {"c": str(case_id)},
        )
        .mappings()
        .first()
    )


def get_or_create(
    case_id: str, employee_id: Optional[str], company_id: str, *, db: Any = None
) -> Optional[Dict[str, Any]]:
    """Return the existing coordinator session for ``case_id``, creating it if absent.

    Uses a single transaction; the INSERT is ``ON CONFLICT (case_id) DO NOTHING`` so
    concurrent creation is safe (the follow-up SELECT returns the winner's row).
    """
    mdb = db or _get_db()
    with mdb.engine.begin() as conn:
        existing = _select(conn, case_id)
        if existing is not None:
            return _row_to_dict(existing)
        conn.execute(
            text(
                "INSERT INTO ai_coordinator_sessions (case_id, employee_id, company_id, model) "
                "VALUES (:c, :e, :co, :m) ON CONFLICT (case_id) DO NOTHING"
            ),
            {"c": str(case_id), "e": employee_id, "co": str(company_id), "m": MODEL_DEFAULT},
        )
        return _row_to_dict(_select(conn, case_id))


def load_for_update(conn: Any, case_id: str) -> Optional[Dict[str, Any]]:
    """Row-locked load for a read-modify-write cycle (``SELECT … FOR UPDATE``)."""
    row = (
        conn.execute(
            text(f"SELECT {_COLUMNS} FROM ai_coordinator_sessions WHERE case_id = :c FOR UPDATE"),
            {"c": str(case_id)},
        )
        .mappings()
        .first()
    )
    return _row_to_dict(row)


def save(conn: Any, session: Dict[str, Any]) -> None:
    """Persist the mutable session fields. ``recent_turns`` is bound as a JSON string and
    cast with ``CAST(:rt AS jsonb)`` — never ``:rt::jsonb`` (an unbound ``::jsonb`` cast is
    a Postgres-only 500 that SQLite silently masks)."""
    conn.execute(
        text(
            "UPDATE ai_coordinator_sessions SET "
            "rolling_summary = :rs, recent_turns = CAST(:rt AS jsonb), "
            "last_event_cursor = :lec, model = :m, status = :st, "
            "last_active_at = NOW(), updated_at = NOW() "
            "WHERE id = :id"
        ),
        {
            "rs": session.get("rolling_summary", ""),
            "rt": json.dumps(session.get("recent_turns") or []),
            "lec": session.get("last_event_cursor"),
            "m": session.get("model", MODEL_DEFAULT),
            "st": session.get("status", "active"),
            "id": session["id"],
        },
    )


def close_session(conn: Any, case_id: str) -> None:
    """Freeze the session (terminal relocation / archived) — stops future folds."""
    conn.execute(
        text(
            "UPDATE ai_coordinator_sessions SET status = 'closed', updated_at = NOW() "
            "WHERE case_id = :c"
        ),
        {"c": str(case_id)},
    )
