"""P2-01b — confidence-based gating for the live AI EEA roadmap.

Gates the AI roadmap (rag_pipeline / roadmap_generator output) before it reaches
a user: a step shows directly only when it is HIGH confidence and not flagged for
expert review. MEDIUM / LOW / UNKNOWN (absent or unrecognised) confidence — and
any step the generator marked `requires_expert_review` — are withheld until a
specialist releases the case via the specialist_review flow
(`RoadmapReviewStatus.released_to_user`). Fail-closed: unknown confidence is
treated as not-releasable.

The deterministic `derive_roadmap` output is NOT an AI roadmap (it carries no
`result` key) and is never gated — see `is_ai_roadmap`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..db import SessionLocal
from ..models import RoadmapReviewStatus

# Mirror roadmap_generator's result sentinels (kept local to avoid importing the
# LLM generator module into the read path).
_RESULT_OK = "OK"
_RESULT_RULE_NOT_FOUND = "RULE_NOT_FOUND"
_AI_RESULTS = (_RESULT_OK, _RESULT_RULE_NOT_FOUND)

_HIGH = "high"


def is_ai_roadmap(roadmap: Any) -> bool:
    """True for the RAG-pipeline/generator roadmap shape (carries a `result` of
    OK or RULE_NOT_FOUND). The deterministic derive_roadmap output returns False,
    so it is never gated."""
    return isinstance(roadmap, dict) and roadmap.get("result") in _AI_RESULTS


def _auto_releasable(step: Dict[str, Any]) -> bool:
    """A step shows to the user without specialist review only when it is HIGH
    confidence and not explicitly flagged for expert review."""
    confidence = str(step.get("confidence") or "").strip().lower()
    return confidence == _HIGH and not step.get("requires_expert_review")


def gate_ai_roadmap(roadmap: Dict[str, Any], *, released_to_user: bool) -> Dict[str, Any]:
    """Return a gated copy of an AI roadmap. When the case is released_to_user,
    every step is visible; otherwise only auto-releasable (HIGH) steps are, and
    the rest move to `withheld_steps`."""
    steps: List[Dict[str, Any]] = roadmap.get("steps") or []
    if released_to_user:
        visible, withheld = list(steps), []
    else:
        visible = [s for s in steps if _auto_releasable(s)]
        withheld = [s for s in steps if not _auto_releasable(s)]

    gated = dict(roadmap)
    gated["steps"] = visible
    gated["withheld_steps"] = withheld
    gated["requires_specialist_review"] = (not released_to_user) and len(withheld) > 0
    gated["released_to_user"] = released_to_user
    return gated


def released_to_user_for(case_id: str, *, db: Optional[object] = None) -> bool:
    """Read the specialist release decision for a case. Pass `db` to reuse an
    open Session; otherwise a short-lived one is opened."""
    if db is not None:
        return _released(db, case_id)
    with SessionLocal() as session:
        return _released(session, case_id)


def _released(db, case_id: str) -> bool:
    status = db.get(RoadmapReviewStatus, case_id)
    return bool(status and status.released_to_user)


def gate_roadmap_for_case(
    case_id: str, roadmap: Dict[str, Any], *, db: Optional[object] = None
) -> Dict[str, Any]:
    """Convenience: gate an AI roadmap using the case's current release status."""
    return gate_ai_roadmap(roadmap, released_to_user=released_to_user_for(case_id, db=db))
