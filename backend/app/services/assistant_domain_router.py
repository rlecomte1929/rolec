"""
Assistant domain router — the single source of truth for the relocation
assistant's policy bridge (Slice 5 backend). Decides whether a free-text question
is about IMMIGRATION (visas/permits/documents → the immigration RAG) or COMPANY
POLICY (benefits/allowances/coverage → the policy RAG), or is genuinely AMBIGUOUS
(→ the UI asks the user).

Deterministic weighted-keyword scoring (mirrors the style of
`policy_assistant_classifier.score_policy_assistant_topics`). Intentionally biased
so coverage-INTENT phrases ("does my company pay for…", "is X covered") outweigh a
bare immigration noun — "does my company pay for the visa?" is a policy question.
A misroute is bounded: each engine still grounds/refuses, so the worst case is the
wrong engine declining, not a wrong answer.

This is the canonical classifier; the frontend should call /api/assistant/route
rather than duplicate the lexicon. Kept identical to the shipped TS version so the
routing eval (backend/eval/run_routing_eval.py) measures real behaviour.
"""
from typing import Dict, List, Tuple

Signal = Tuple[str, int]

IMMIGRATION_SIGNALS: List[Signal] = [
    ("visa", 2), ("permit", 2), ("passport", 2), ("apostille", 2), ("biometric", 2),
    ("anabin", 2), ("blue card", 2), ("residence", 2), ("register", 2), ("registration", 2),
    ("embassy", 2), ("consulate", 2), ("immigration", 2), ("processing time", 2),
    ("document", 1), ("appointment", 1),
]

POLICY_SIGNALS: List[Signal] = [
    ("my company", 3), ("my employer", 3), ("pay for", 3), ("covered", 3), ("cover", 3),
    ("reimburse", 3), ("allowance", 3), ("benefit", 3), ("entitled", 3), ("relocation package", 3),
    ("employer", 2), ("budget", 2), ("housing", 2), ("accommodation", 2), ("flight", 2),
    ("home leave", 2), ("school", 2), ("cola", 2), ("shipping", 2), ("spouse support", 2),
    ("tax equalization", 2), ("tax equalisation", 2),
]


def _score(haystack: str, signals: List[Signal]) -> int:
    return sum(weight for phrase, weight in signals if phrase in haystack)


def classify_domain(question: str) -> Dict[str, object]:
    """Return {domain, immigration_score, policy_score}."""
    q = (question or "").lower()
    immigration = _score(q, IMMIGRATION_SIGNALS)
    policy = _score(q, POLICY_SIGNALS)

    if immigration == 0 and policy == 0:
        domain = "ambiguous"
    elif immigration == policy:
        domain = "ambiguous"
    else:
        domain = "immigration" if immigration > policy else "policy"

    return {"domain": domain, "immigration_score": immigration, "policy_score": policy}
