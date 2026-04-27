"""
Policy Assistant RAG (Sprint B): rolling 4-turn session memory.

Per the design doc, multi-turn matters but full session history is
overkill — 4 turns covers "what about my partner?" / "and the kids?"
follow-up flows without ballooning context cost.

Storage: in-process dict with a 30-minute idle TTL. Adequate for first
pilot at one backend instance. When we need multi-instance support
(Sprint N+1), swap to Redis with the same public API.

Threading: Python GIL makes the simple dict access safe for our usage
(single read + single write per request). No locking needed.

Public API (small, stable):
  - record_turn(session_id, user_message, assistant_answer)
  - get_recent_turns(session_id) -> List[(user_msg, assistant_msg)]
  - clear_session(session_id)
"""
from __future__ import annotations

import threading
import time
from typing import Dict, List, Tuple

# --- Constants -------------------------------------------------------------

MAX_TURNS = 4              # rolling window size (locked per design doc)
IDLE_TTL_SECONDS = 30 * 60 # 30 minutes since last touch → evict


# --- Storage ---------------------------------------------------------------

# session_id -> {"turns": [(user, assistant), ...], "touched_at": epoch_seconds}
_SESSIONS: Dict[str, Dict] = {}
_LOCK = threading.Lock()


def _now() -> float:
    return time.time()


def _evict_stale(now: float) -> None:
    """Drop sessions idle longer than IDLE_TTL_SECONDS. Cheap pass; runs
    on every record/get so memory doesn't grow unbounded."""
    expired = [
        sid for sid, s in _SESSIONS.items()
        if (now - s.get("touched_at", 0)) > IDLE_TTL_SECONDS
    ]
    for sid in expired:
        _SESSIONS.pop(sid, None)


# --- Public API ------------------------------------------------------------

def record_turn(
    session_id: str,
    user_message: str,
    assistant_answer: str,
) -> None:
    """Append one (user, assistant) pair to the session, trimmed to
    MAX_TURNS. No-op if session_id is empty (caller hasn't started a
    session yet)."""
    if not session_id:
        return
    with _LOCK:
        now = _now()
        _evict_stale(now)
        s = _SESSIONS.setdefault(
            session_id, {"turns": [], "touched_at": now}
        )
        s["turns"].append((user_message, assistant_answer))
        if len(s["turns"]) > MAX_TURNS:
            s["turns"] = s["turns"][-MAX_TURNS:]
        s["touched_at"] = now


def get_recent_turns(session_id: str) -> List[Tuple[str, str]]:
    """Return the rolling window of (user, assistant) pairs in
    chronological order. Empty list if session unknown / expired."""
    if not session_id:
        return []
    with _LOCK:
        now = _now()
        _evict_stale(now)
        s = _SESSIONS.get(session_id)
        if not s:
            return []
        s["touched_at"] = now  # touching it on read keeps active sessions alive
        return list(s["turns"])


def clear_session(session_id: str) -> None:
    """Drop a session explicitly (e.g. user clicked 'Reset conversation')."""
    if not session_id:
        return
    with _LOCK:
        _SESSIONS.pop(session_id, None)


# --- Test helpers (intentionally minimal) ----------------------------------

def _reset_all_for_tests() -> None:
    """Test-only: wipe all sessions. Don't call from production code."""
    with _LOCK:
        _SESSIONS.clear()


def _session_count_for_tests() -> int:
    with _LOCK:
        return len(_SESSIONS)
