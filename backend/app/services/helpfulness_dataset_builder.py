"""Helpfulness → eval golden-set candidate builder (WS-E).

Turns end-user helpfulness votes (``policy_answer_helpfulness``) into eval
golden-set CANDIDATES: anonymised, deduplicated, net-sentiment records that a
human curates into the real golden set. This mirrors
``preference_dataset_builder`` (which turns ``ai_human_feedback`` into DPO pairs)
in shape and honest-signal discipline:

* Votes are grouped by ``query_hash`` — the only anonymised "same underlying
  question" key (``policy_assistant_traces`` is deliberately PII-free, storing a
  16-hex SHA-256 of the question, never the raw prompt). A downstream curation job
  rehydrates the prompt text by ``query_hash`` from its own store.
* We never fabricate candidates: a group below ``min_votes`` is dropped, and every
  emitted candidate carries ``needs_review = True`` (these are CANDIDATES, not
  graded gold).

Pure functions operate on in-memory rows so they are testable without a DB; a thin
DB read path (``build_candidates_from_db``) joins the votes to their trace for the
``query_hash`` + ``company_id``.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ..db import SessionLocal

log = logging.getLogger(__name__)

LABEL_POSITIVE = "candidate_positive"
LABEL_NEGATIVE = "candidate_negative"
LABEL_CONTESTED = "contested"


@dataclass(frozen=True)
class GoldenCandidate:
    """One eval golden-set candidate derived from end-user votes on a question."""

    prompt: str  # anonymised query_hash; rehydrate text downstream
    label: str  # candidate_positive | candidate_negative | contested
    helpful_votes: int
    unhelpful_votes: int
    net_score: int
    company_id: Optional[str]
    trace_session_ids: List[str] = field(default_factory=list)
    needs_review: bool = True
    source: str = "end_user_helpfulness"

    def to_jsonl_obj(self) -> Dict[str, Any]:
        d = asdict(self)
        prompt = d.pop("prompt")
        label = d.pop("label")
        needs_review = d.pop("needs_review")
        return {
            "prompt": prompt,
            "label": label,
            "needs_review": needs_review,
            "metadata": d,
        }


def _classify(helpful: int, unhelpful: int) -> str:
    net = helpful - unhelpful
    if net > 0:
        return LABEL_POSITIVE
    if net < 0:
        return LABEL_NEGATIVE
    return LABEL_CONTESTED


def build_candidates(
    rows: List[Dict[str, Any]], *, min_votes: int = 1
) -> List[GoldenCandidate]:
    """Build golden-set candidates from helpfulness rows.

    Each row needs ``query_hash``, ``helpful`` (bool), ``trace_session_id`` and
    (optionally) ``company_id``. Rows are grouped by ``query_hash``; groups with
    fewer than ``min_votes`` total votes are dropped (never fabricated). Output is
    deterministically ordered by ``query_hash`` for stable diffs.
    """
    groups: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        qh = r.get("query_hash")
        if not qh:
            continue  # cannot anchor a candidate without the anonymised key
        g = groups.setdefault(
            qh,
            {"helpful": 0, "unhelpful": 0, "company_id": None, "traces": []},
        )
        if r.get("helpful"):
            g["helpful"] += 1
        else:
            g["unhelpful"] += 1
        if g["company_id"] is None and r.get("company_id"):
            g["company_id"] = r.get("company_id")
        tsid = r.get("trace_session_id")
        if tsid:
            g["traces"].append(str(tsid))

    candidates: List[GoldenCandidate] = []
    for qh in sorted(groups):
        g = groups[qh]
        total = g["helpful"] + g["unhelpful"]
        if total < min_votes:
            continue
        candidates.append(
            GoldenCandidate(
                prompt=qh,
                label=_classify(g["helpful"], g["unhelpful"]),
                helpful_votes=g["helpful"],
                unhelpful_votes=g["unhelpful"],
                net_score=g["helpful"] - g["unhelpful"],
                company_id=g["company_id"],
                trace_session_ids=sorted(set(g["traces"])),
            )
        )

    if not candidates:
        log.info("build_candidates: no candidates (rows=%d)", len(rows))
    return candidates


def to_jsonl(candidates: List[GoldenCandidate]) -> str:
    """Serialise candidates to JSONL (one candidate per line, stable key order)."""
    return "\n".join(
        json.dumps(c.to_jsonl_obj(), sort_keys=True) for c in candidates
    )


# ── DB read path ──────────────────────────────────────────────────────────────


def _fetch_votes(s: Any) -> List[Dict[str, Any]]:
    """All helpfulness votes joined to their trace's anonymised query_hash."""
    rows = (
        s.execute(
            text(
                "SELECT h.trace_session_id, h.company_id, h.helpful, t.query_hash "
                "FROM policy_answer_helpfulness h "
                "JOIN policy_assistant_traces t ON t.id = h.trace_session_id"
            )
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def build_candidates_from_db(
    *, min_votes: int = 1, session: Any = None
) -> List[GoldenCandidate]:
    """Read helpfulness votes from the DB and build candidates."""
    own = session is None
    s = session or SessionLocal()
    try:
        rows = _fetch_votes(s)
    finally:
        if own:
            s.close()
    return build_candidates(rows, min_votes=min_votes)
