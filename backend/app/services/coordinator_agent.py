"""AIQ-1414 Phase 2b-ii — single-turn Mobility Coordinator.

Composes the read-only context builder (Phase 2a) and the durable session store
(Phase 2b-i) into one coordinator turn: assemble current case state + the rolling
summary + recent turns, mask, call Claude (prompt-cached, via the shared masking client),
record cost telemetry, then persist the turn (folding older turns into the summary when
the window overflows).

Gated behind ``RELOPASS_AI_COORDINATOR_ENABLED`` (default OFF) — ``respond`` returns
``None`` when disabled, so the whole path is inert in production until the human gate.
Reasoning model = ``claude-sonnet-4-6``; summary folds use ``claude-haiku-4-5``.
Phase 3b adds a cost circuit-breaker, a per-relocation rate limit (router), and
``tool_use`` structured actions — the coordinator can flag a risk or leave a note, which
are persisted to the ``case_events`` spine (best-effort; a failed action never breaks the
answer).
"""

from __future__ import annotations

import json
import logging
import os
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
_FOLD_MODEL = "claude-haiku-4-5"  # alias (not date-suffixed) so router.usd_cost / costs.yaml resolves
_MAX_TOKENS = 700
_KEEP_AFTER_FOLD = 2
_CONTEXT_CHAR_CAP = 8000

# Cost circuit-breaker (Phase 3b): once this ONE relocation's coordinator spend for the
# current month reaches the cap, routine turns are durably downgraded to Haiku (the cheaper
# model is written to the session row, so it sticks). Fail-open — the meter never blocks a
# turn. Env-tunable; <= 0 disables the breaker.
_MONTHLY_CAP_ENV = "RELOPASS_COORDINATOR_MONTHLY_USD_CAP"
_DEFAULT_MONTHLY_CAP_USD = 2.0


def _monthly_cap_usd() -> float:
    try:
        return float(os.getenv(_MONTHLY_CAP_ENV, str(_DEFAULT_MONTHLY_CAP_USD)))
    except (TypeError, ValueError):
        return _DEFAULT_MONTHLY_CAP_USD


def _breaker_model(case_id: str, current_model: str) -> str:
    """Return the model to use this turn, downgrading to Haiku once the per-relocation
    monthly cap is reached. Already-downgraded sessions stay on Haiku. Fail-open."""
    if current_model == _FOLD_MODEL:
        return current_model
    cap = _monthly_cap_usd()
    if cap <= 0:
        return current_model
    try:
        from .ai_unit_economics import relocation_feature_spend_usd

        spend = relocation_feature_spend_usd(str(case_id), feature_key=FEATURE_KEY)
    except Exception as exc:  # noqa: BLE001 — meter must never block a turn
        log.debug("coordinator breaker read failed for %s: %s", case_id, exc)
        return current_model
    if spend >= cap:
        log.info(
            "coordinator: monthly cap $%.2f reached for %s (spend $%.4f) → downgrade to %s",
            cap, case_id, spend, _FOLD_MODEL,
        )
        return _FOLD_MODEL
    return current_model


# ── Phase 3b: tool_use structured actions ─────────────────────────────────────
# One dispatcher tool (the client returns a tool_use block's `.input` but NOT the tool
# name, so the ``action`` enum carries the discriminator). Both actions append to the
# case_events spine, which the case timeline + the coordinator's own context already read.
_ACTION_EVENT_TYPES = {
    "flag_risk": "coordinator.risk_flagged",
    "add_note": "coordinator.note_added",
}

_TOOLS = [
    {
        "name": "record_coordinator_action",
        "description": (
            "Record a structured action on THIS relocation case. Call this ONLY when the "
            "user explicitly asks you to flag a risk or leave a note for HR — otherwise just "
            "answer normally without calling any tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["flag_risk", "add_note"],
                    "description": "flag_risk: record a risk for HR to review. add_note: leave a short note on the case.",
                },
                "detail": {
                    "type": "string",
                    "description": "The risk description or note body — one or two concise sentences.",
                },
                "severity": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Only for flag_risk: how urgent the risk is.",
                },
            },
            "required": ["action", "detail"],
        },
    }
]
_TOOL_CHOICE = {"type": "auto"}


def _assignment_id_of(ctx: Dict[str, Any]) -> Optional[str]:
    meta = ctx.get("_meta") or {}
    return meta.get("assignment_id") or (ctx.get("case") or {}).get("assignment_id")


def _dispatch_action(
    case_id: str,
    ctx: Dict[str, Any],
    employee_id: Optional[str],
    action: Dict[str, Any],
    *,
    db: Any = None,
) -> Optional[str]:
    """Persist a structured coordinator action to the ``case_events`` spine and return a
    short confirmation to append to the answer. Best-effort — never raises (a failed action
    must not break the turn). The detail is masked before it is persisted."""
    try:
        kind = str((action or {}).get("action") or "").strip()
        event_type = _ACTION_EVENT_TYPES.get(kind)
        detail = mask_pii(str((action or {}).get("detail") or "").strip())
        if not event_type or not detail:
            return None
        payload: Dict[str, Any] = {"detail": detail, "source": "ai_coordinator"}
        severity = (action or {}).get("severity")
        if kind == "flag_risk" and severity:
            payload["severity"] = str(severity)
        mdb = db or store._get_db()
        mdb.insert_case_event(
            case_id=str(case_id),
            assignment_id=_assignment_id_of(ctx),
            actor_principal_id=employee_id or "ai_coordinator",
            event_type=event_type,
            payload=payload,
        )
        if kind == "flag_risk":
            return f"⚠️ I’ve flagged a risk on this case for HR: {detail}"
        return f"\U0001f4dd I’ve added a note to this case: {detail}"
    except Exception as exc:  # noqa: BLE001 — actions are best-effort
        log.warning("coordinator: action dispatch failed for %s: %s", case_id, exc)
        return None

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

    # Cost circuit-breaker: pick the effective model (Haiku once this relocation is over cap)
    # and persist it on the session so the downgrade sticks for subsequent turns.
    effective_model = _breaker_model(str(case_id), session.get("model") or _REASONING_MODEL)

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
            model=effective_model,
            max_tokens=_MAX_TOKENS,
            tools=_TOOLS,
            tool_choice=_TOOL_CHOICE,
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
    action = result.get("tool_use")
    if action:
        confirmation = _dispatch_action(str(case_id), ctx, employee_id, action, db=db)
        if confirmation:
            answer = (answer + ("\n\n" if answer else "") + confirmation).strip()

    _persist_turn(case_id, session, masked_user, answer, ctx, model=effective_model, db=db)

    # AIQ-1694·4b — record this coordinator turn to the human-oversight audit trail
    # (best-effort). Unlike the recs engine's structured vendor output, a coordinator
    # answer is free text that may echo case PII, so we mask the answer before storing
    # it; the helper masks input_context on its own.
    if company_id and answer:
        try:
            from .ai_decision_logger import record_ai_recommendation, stable_recommendation_id
            _model = result.get("model", effective_model)
            record_ai_recommendation(
                feature="ai_coordinator",
                recommendation_id=stable_recommendation_id(company_id, "ai_coordinator", str(case_id), answer),
                input_context={"case_id": str(case_id), "user_message": masked_user},
                ai_output={"answer": mask_pii(answer), "model": _model},
                company_id=company_id,
                actor_id=employee_id,
                model_name=_model,
                skip_if_exists=True,
            )
        except Exception:  # noqa: BLE001 — audit is best-effort, never breaks the turn
            pass

    return {"answer": answer, "case_id": str(case_id), "model": result.get("model", effective_model)}


def _persist_turn(
    case_id: str,
    session: Dict[str, Any],
    masked_user: str,
    answer: str,
    ctx: Dict[str, Any],
    *,
    model: Optional[str] = None,
    db: Any = None,
) -> None:
    """Append the (masked) turn and, when the verbatim window overflows, fold older turns
    into the rolling summary. Best-effort — never fails the response. ``model`` (when the
    circuit-breaker downgraded this turn) is persisted so the downgrade sticks."""
    mdb = db or store._get_db()
    try:
        with mdb.engine.begin() as conn:
            s = store.load_for_update(conn, str(case_id)) or session
            if model:
                s["model"] = model
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
    company_id = session.get("company_id")
    case_id = session.get("case_id")
    tracer = TraceSession(
        session_id=str(case_id) if case_id is not None else None,
        query="coordinator_summary_fold",
        company_id=company_id,
        feature_key=FEATURE_KEY,
        customer_id=company_id,
    )
    t0 = time.monotonic()
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
    except Exception as exc:  # noqa: BLE001
        log.warning("coordinator: summary fold failed: %s", exc)
        return prior
    latency_ms = int((time.monotonic() - t0) * 1000)
    usage = out.get("usage") or {}
    try:  # attribute the fold's cost to the same feature_key (was previously untraced)
        tracer.record_llm_call(
            model=out.get("model", _FOLD_MODEL),
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            latency_ms=latency_ms,
        )
        tracer.flush()
    except Exception as exc:  # noqa: BLE001
        log.warning("coordinator: fold telemetry failed: %s", exc)
    return (out.get("text") or prior).strip()


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
