"""P1 — Groundedness gate-impact canary (pure, in-memory).

Read-only analysis that quantifies, from ALREADY-PERSISTED policy-assistant
traces, what fraction of real answers the groundedness gate WOULD refuse if
``POLICY_RAG_GROUNDEDNESS_GATE`` were flipped on. No LLM, no replay — it only
re-applies the gate predicate to verdict/score columns the verifier already
wrote on every answer.

The predicate mirrored here is the exact one in
``backend/app/services/policy_assistant_rag_engine.py`` (~lines 339-348):

    would-refuse = answer_kind == 'answer'
                   AND not verification_skipped
                   AND (grounding_verdict == 'ungrounded'
                        OR (grounding_score is not None
                            AND grounding_score < min_score))

Functions are pure (operate on lists of plain dicts) so they are unit-testable
without a DB. The SQL-side equivalent lives in
``backend/db/misc.py::get_gate_impact_rollup``.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional


def default_min_score() -> float:
    """The gate's default minimum grounding score.

    Sourced (lazily, to keep this module DB/LLM-free on import) from
    ``policy_assistant_rag_engine.DEFAULT_GROUNDEDNESS_MIN_SCORE``; falls back to
    the documented literal 0.5 if that module can't be imported.
    """
    try:  # pragma: no cover - import path varies by environment
        from backend.app.services.policy_assistant_rag_engine import (
            DEFAULT_GROUNDEDNESS_MIN_SCORE,
        )

        return float(DEFAULT_GROUNDEDNESS_MIN_SCORE)
    except Exception:  # pragma: no cover - defensive fallback
        return 0.5


def _coerce_score(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def would_refuse(row: Dict[str, Any], min_score: float) -> bool:
    """Re-apply the exact gate predicate to one persisted trace row.

    A row "would be refused" only when it is a real answer that was actually
    verified (verification_skipped fails OPEN) and the verdict is ``ungrounded``
    OR the score is present and strictly below ``min_score``. A score exactly at
    ``min_score`` is NOT refused (matches the engine's ``< min`` comparison).
    """
    if (row.get("answer_kind") or "") != "answer":
        return False
    if bool(row.get("verification_skipped")):
        return False
    verdict = row.get("grounding_verdict")
    if verdict == "ungrounded":
        return True
    score = _coerce_score(row.get("grounding_score"))
    return score is not None and score < min_score


def estimate_gate_impact(
    rows: List[Dict[str, Any]],
    min_score: Optional[float] = None,
    *,
    by_company: bool = False,
) -> Dict[str, Any]:
    """Count would-be-refused answers across persisted trace rows.

    The gate only ever fires on real answers, so the denominator is the number
    of ``answer_kind == 'answer'`` rows (refusals are never gated).

    Returns:
        n_answers          — answers in scope (the gate denominator)
        n_would_refuse     — answers the gate would have replaced with a refusal
        would_refuse_rate  — n_would_refuse / n_answers (0.0 when no answers)
        min_score          — threshold used
        by_verdict         — {grounding_verdict: count} over would-be-refused rows
        by_company         — {company_id: {n_answers, n_would_refuse}} (only when
                             ``by_company=True``)
    """
    ms = default_min_score() if min_score is None else float(min_score)

    n_answers = 0
    n_would_refuse = 0
    by_verdict: Dict[str, int] = defaultdict(int)
    per_company: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"n_answers": 0, "n_would_refuse": 0}
    )

    for row in rows:
        is_answer = (row.get("answer_kind") or "") == "answer"
        if not is_answer:
            continue
        n_answers += 1
        company = str(row.get("company_id")) if row.get("company_id") is not None else "UNKNOWN"
        per_company[company]["n_answers"] += 1
        if would_refuse(row, ms):
            n_would_refuse += 1
            per_company[company]["n_would_refuse"] += 1
            by_verdict[row.get("grounding_verdict") or "null"] += 1

    out: Dict[str, Any] = {
        "n_answers": n_answers,
        "n_would_refuse": n_would_refuse,
        "would_refuse_rate": round(n_would_refuse / n_answers, 4) if n_answers else 0.0,
        "min_score": ms,
        "by_verdict": dict(by_verdict),
    }
    if by_company:
        out["by_company"] = {k: dict(v) for k, v in sorted(per_company.items())}
    return out


def false_refusal_signal(
    rows_with_helpful: List[Dict[str, Any]],
    min_score: Optional[float] = None,
) -> Dict[str, Any]:
    """Estimate FALSE refusals using the end-user helpfulness weak-label.

    ``rows_with_helpful`` are trace rows each carrying an optional ``helpful``
    field (True / False / None) from a LEFT JOIN to ``policy_answer_helpfulness``.
    A would-be-refused answer that a real user marked ``helpful=True`` is a
    candidate FALSE refusal — the gate would have suppressed an answer the user
    found useful.

    Returns counts over the would-be-refused set plus the false-refusal rate
    (n helpful / n would-refuse).
    """
    ms = default_min_score() if min_score is None else float(min_score)

    refused = [r for r in rows_with_helpful if would_refuse(r, ms)]
    n_refuse = len(refused)
    n_helpful = sum(1 for r in refused if r.get("helpful") is True)
    n_unhelpful = sum(1 for r in refused if r.get("helpful") is False)
    n_no_vote = sum(1 for r in refused if r.get("helpful") is None)

    return {
        "min_score": ms,
        "n_would_refuse": n_refuse,
        "n_would_refuse_helpful": n_helpful,
        "n_would_refuse_unhelpful": n_unhelpful,
        "n_would_refuse_no_vote": n_no_vote,
        "false_refusal_rate": round(n_helpful / n_refuse, 4) if n_refuse else 0.0,
    }


def sweep(
    rows: List[Dict[str, Any]],
    thresholds: Optional[List[float]] = None,
    *,
    by_company: bool = False,
) -> List[Dict[str, Any]]:
    """Run ``estimate_gate_impact`` at each threshold (default 0.3 / 0.5 / 0.7)."""
    grid = thresholds if thresholds is not None else [0.3, 0.5, 0.7]
    return [estimate_gate_impact(rows, t, by_company=by_company) for t in grid]
