"""AIQ-1414 Phase 2b-ii — single-turn Mobility Coordinator.

Composes the read-only context builder (Phase 2a) and the durable session store
(Phase 2b-i) into one coordinator turn: assemble current case state + the rolling
summary + recent turns, mask, call Claude (prompt-cached, via the shared masking client),
record cost telemetry, then persist the turn (folding older turns into the summary when
the window overflows).

Gated behind ``RELOPASS_AI_COORDINATOR_ENABLED`` (default OFF) — ``respond`` returns
``None`` when disabled, so the whole path is inert in production until the human gate.
Reasoning model = ``claude-sonnet-4-6``; summary folds use ``claude-haiku-4-5``.
Structured tool actions (flag a milestone, draft a message) are a Phase-3 follow-up.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from . import coordinator_session_store as store
from .ai_trace_logger import TraceSession
from .coordinator_context_builder import build_coordinator_context_for_case, coordinator_enabled
from .pii_masker import mask_pii
from .policy_assistant_llm_client import LlmRequest, get_default_client

log = logging.getLogger(__name__)

FEATURE_KEY = "ai_coordinator"
_REASONING_MODEL = store.MODEL_DEFAULT  # claude-sonnet-4-6
_FOLD_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 700
_KEEP_AFTER_FOLD = 2
_CONTEXT_CHAR_CAP = 8000

_SYSTEM = (
    "You are ReloPass's Mobility Coordinator — a calm, precise relocation concierge for one "
    "employee's move. You are given the current, authoritative case state (already anonymised), "
    "a running summary of the relocation so far, and recent activity. Answer the user's question "
    "or give the single next best step, grounded ONLY in the provided context. Be concise and "
    "warm. If the context does not contain the answer, say what is missing and who to ask — never "
    "invent visa rules, dates, or costs. The data is anonymised: do not ask for or repeat personal "
    "identifiers."
)


def respond(
    case_id: str, user_message: str, *, employee_id: Optional[str] = None, db: Any = None
) -> Optional[Dict[str, Any]]:
    """Run one coordinator turn. Returns ``{"answer","case_id","model"}`` or ``None`` when
    the feature flag is OFF (caller does nothing)."""
    if not coordinator_enabled(db=db):
        return None

    ctx = build_coordinator_context_for_case(case_id, db=db)
    if ctx is None:  # flag flipped mid-call
        return None

    company_id = _company_of(ctx)
    session = store.get_or_create(str(case_id), employee_id, company_id or "unknown", db=db)

    masked_user = mask_pii(user_message or "")
    user_content = _render(ctx, session, masked_user)

    tracer = TraceSession(
        session_id=str(case_id),
        query=masked_user,
        company_id=company_id,
        feature_key=FEATURE_KEY,
        customer_id=company_id,
    )
    t0 = time.monotonic()
    result = get_default_client().complete(
        LlmRequest(
            system=_SYSTEM,
            user_message=user_content,
            model=session.get("model") or _REASONING_MODEL,
            max_tokens=_MAX_TOKENS,
        )
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    usage = result.get("usage") or {}
    try:
        tracer.record_llm_call(
            model=result.get("model", _REASONING_MODEL),
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            latency_ms=latency_ms,
        )
        tracer.flush()
    except Exception as exc:  # noqa: BLE001 — telemetry is best-effort
        log.warning("coordinator: telemetry failed for %s: %s", case_id, exc)

    answer = (result.get("text") or "").strip()
    _persist_turn(case_id, session, masked_user, answer, ctx, db=db)
    return {"answer": answer, "case_id": str(case_id), "model": result.get("model", _REASONING_MODEL)}


def _persist_turn(
    case_id: str,
    session: Dict[str, Any],
    masked_user: str,
    answer: str,
    ctx: Dict[str, Any],
    *,
    db: Any = None,
) -> None:
    """Append the (masked) turn and, when the verbatim window overflows, fold older turns
    into the rolling summary. Best-effort — never fails the response."""
    mdb = db or store._get_db()
    try:
        with mdb.engine.begin() as conn:
            s = store.load_for_update(conn, str(case_id)) or session
            store.append_turn(s, masked_user, answer)
            if store.needs_fold(s):
                s["rolling_summary"] = _fold_summary(s)
                s["recent_turns"] = list(s.get("recent_turns") or [])[-_KEEP_AFTER_FOLD:]
                cursor = _latest_event_at(ctx)
                if cursor:
                    s["last_event_cursor"] = cursor
            store.save(conn, s)
    except Exception as exc:  # noqa: BLE001
        log.warning("coordinator: persist turn failed for %s: %s", case_id, exc)


def _fold_summary(session: Dict[str, Any]) -> str:
    """Fold prior summary + recent turns into a bounded summary via a cheap Haiku call."""
    prior = session.get("rolling_summary") or ""
    turns = session.get("recent_turns") or []
    body = "\n".join(
        f"User: {t.get('user', '')}\nCoordinator: {t.get('assistant', '')}" for t in turns
    )
    try:
        out = get_default_client().complete(
            LlmRequest(
                system=(
                    "You maintain a running summary of one relocation. Given the prior summary and "
                    "the recent turns, produce an updated summary of the relocation's status and open "
                    "threads in under 150 words. The data is anonymised — keep it that way."
                ),
                user_message=f"PRIOR SUMMARY:\n{prior}\n\nRECENT TURNS:\n{body}",
                model=_FOLD_MODEL,
                max_tokens=300,
            )
        )
        return (out.get("text") or prior).strip()
    except Exception as exc:  # noqa: BLE001
        log.warning("coordinator: summary fold failed: %s", exc)
        return prior


def _render(ctx: Dict[str, Any], session: Dict[str, Any], masked_user: str) -> str:
    """Compose the user-turn payload. Context is already masked by the builder; the new
    message is masked here; the client re-masks (idempotent)."""
    state = {k: ctx.get(k) for k in ("case", "people", "documents", "requirements", "recent_events")}
    parts = ["CASE STATE (anonymised JSON):", json.dumps(state, default=str)[:_CONTEXT_CHAR_CAP]]

    summary = (session.get("rolling_summary") or "").strip()
    if summary:
        parts += ["", "SUMMARY SO FAR:", summary]

    recent = session.get("recent_turns") or []
    if recent:
        parts += ["", "RECENT TURNS:"]
        for t in recent[-4:]:
            parts += [f"User: {t.get('user', '')}", f"Coordinator: {t.get('assistant', '')}"]

    parts += ["", "NEW MESSAGE:", masked_user]
    return "\n".join(parts)


def _company_of(ctx: Dict[str, Any]) -> Optional[str]:
    case = ctx.get("case") or {}
    return case.get("company_id") or (ctx.get("_meta") or {}).get("company_id")


def _latest_event_at(ctx: Dict[str, Any]) -> Optional[str]:
    for ev in ctx.get("recent_events") or []:
        at = ev.get("at")
        if at:
            return at
    return None
