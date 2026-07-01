"""
Answer/extraction faithfulness metrics (deepen-evals slice 1).

Aggregates immigration Q&A replay records (feature_key='immigration_answer') into
faithfulness signals, reading the pipeline's own stored verify_grounding verdicts —
deterministic, no LLM re-run. Primary metric (`aggregate`) = grounding_rate. Note
the pipeline turns an `ungrounded` verdict into a `refusal_ungrounded` (the answer
is discarded), so among answer_kind=='answer' the verdict is grounded /
partially_grounded / None(skipped); caught hallucinations show up as refusals.
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, List

_ANSWER_FEATURE = "immigration_answer"


def _load(rec: Dict[str, Any]) -> Dict[str, Any]:
    raw = rec.get("output_masked") or rec.get("output") or "{}"
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def grade_answer_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate answer-faithfulness metrics. Report shape matches the dashboard
    contract (top-level numeric `aggregate` = grounding_rate). Safe on empty input."""
    n_total = n_answered = n_grounded = n_cited = n_unsupported = 0
    n_refusal = n_ungrounded_caught = 0
    by_corridor_answered: Dict[str, int] = defaultdict(int)
    by_corridor_grounded: Dict[str, int] = defaultdict(int)

    for rec in records:
        if rec.get("feature_key") != _ANSWER_FEATURE:
            continue
        out = _load(rec)
        kind = out.get("answer_kind")
        corridor = rec.get("corridor") or "UNKNOWN"
        n_total += 1

        if kind == "answer":
            n_answered += 1
            by_corridor_answered[corridor] += 1
            if out.get("grounding_verdict") == "grounded":
                n_grounded += 1
                by_corridor_grounded[corridor] += 1
            if out.get("cited_sources"):
                n_cited += 1
            if out.get("unsupported_claims"):
                n_unsupported += 1
        else:
            n_refusal += 1
            if kind == "refusal_ungrounded":
                n_ungrounded_caught += 1

    grounding_rate = (n_grounded / n_answered) if n_answered else 0.0
    by_corridor = {
        c: round(by_corridor_grounded[c] / n, 4)
        for c, n in sorted(by_corridor_answered.items()) if n
    }

    return {
        "aggregate": round(grounding_rate, 4),
        "by_corridor": by_corridor,
        "extra": {
            "metric": "answer_grounding",
            "n_total": n_total,
            "n_answered": n_answered,
            "n_grounded": n_grounded,
            "citation_validity": round(n_cited / n_answered, 4) if n_answered else 0.0,
            "unsupported_claim_rate": round(n_unsupported / n_answered, 4) if n_answered else 0.0,
            "refusal_rate": round(n_refusal / n_total, 4) if n_total else 0.0,
            "ungrounded_caught": n_ungrounded_caught,
        },
    }
