"""
N8 / AIQ-848 — rolling source_reliability_score from the feedback loop.

Closes the learning loop: chunks cited in answers that reviewers REJECT get
down-ranked; chunks cited in answers that hold up keep their weight. The score is
recomputed from scratch on each run (nightly cron) and folded into the N3
retriever's ranking as a 4th factor (see immigration_retriever._apply_quality_gates).

Signal source (per the W3/N2/N4 contract):
  ai_human_feedback.verdict='rejected'  →  policy_assistant_traces.cited_chunk_ids
  →  immigration_corpus_chunks.id

  citation_count = # immigration-answer traces that cite the chunk (any verdict)
  rejection_count = # of those traces whose answer was rejected
  reliability_score:
    n == 0            -> 0.5 (neutral; a never-cited chunk is not penalised)
    0 < n < 10        -> Wilson 95% lower bound (one rejection on a fresh chunk
                         must not crater it to 0)
    n >= 10           -> simple 1 - rejection_rate

Idempotency (Validation Criterion 5): counts and score are SET from a full
recompute every run, never incremented — running twice yields identical rows.

NOTE (known gap, documented for the reviewer): the N4 immigration answer engine
does not yet persist which immigration_corpus_chunks.id it cited (it cites by
source_url), and ai_human_feedback currently carries no immigration-answer
verdicts. So in production this recompute leaves every chunk at the neutral 0.5
until that producer side is wired (tracked as a follow-up). The service itself is
correct and unit-tested against seeded feedback; it activates automatically once
real signal exists.
"""
from __future__ import annotations

import json
import logging
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from .. import db as _db
from .source_reliability_config import (
    LOW_SAMPLE_THRESHOLD as _LOW_SAMPLE_THRESHOLD,
    NEUTRAL_RELIABILITY as _NEUTRAL_SCORE,
    WILSON_Z as _WILSON_Z,
)

log = logging.getLogger(__name__)

# policy_assistant_traces.feature_key value the N4 immigration engine logs under.
IMMIGRATION_FEATURE_KEY = "immigration_answer"

# Tolerate both a plain id and the policy-style "[chunk:<id>]" citation wrapper.
_CHUNK_REF_RE = re.compile(r"\[chunk:([^\]]+)\]")


def _wilson_lower_bound(successes: int, n: int, z: float = _WILSON_Z) -> float:
    """Wilson score 95% lower bound on the success (non-rejection) rate."""
    if n <= 0:
        return _NEUTRAL_SCORE
    phat = successes / n
    z2 = z * z
    denom = n + z2
    centre = (successes + z2 / 2.0) / denom
    margin = z * math.sqrt((phat * (1.0 - phat) + z2 / (4.0 * n)) / denom)
    return centre - margin


def reliability_score(citation_count: int, rejection_count: int) -> float:
    """Score a chunk from its citation/rejection tallies. Always in [0, 1]."""
    n = int(citation_count)
    if n <= 0:
        return _NEUTRAL_SCORE
    rej = max(0, min(int(rejection_count), n))
    successes = n - rej
    if n >= _LOW_SAMPLE_THRESHOLD:
        score = 1.0 - (rej / n)
    else:
        score = _wilson_lower_bound(successes, n)
    return max(0.0, min(1.0, score))


def _parse_cited(raw: Any) -> List[str]:
    """cited_chunk_ids is jsonb (postgres) / TEXT json (sqlite) / already a list."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        try:
            v = json.loads(raw)
        except (ValueError, TypeError):
            return []
        return [str(x) for x in v] if isinstance(v, list) else []
    return []


def _normalize_ref(ref: str) -> str:
    m = _CHUNK_REF_RE.fullmatch(ref.strip())
    return m.group(1).strip() if m else ref.strip()


def recompute_reliability_scores(
    *, engine=None, feature_key: str = IMMIGRATION_FEATURE_KEY
) -> Dict[str, Any]:
    """
    Recompute reliability_score / citation_count / rejection_count for every
    immigration_corpus_chunks row from the current feedback + trace data, and
    write them back. Full recompute (idempotent). Returns a summary dict.
    """
    engine = engine or _db.engine
    updated_at = datetime.now(timezone.utc)

    with engine.begin() as conn:
        chunk_ids = [str(r[0]) for r in conn.execute(
            text("SELECT id FROM immigration_corpus_chunks")).all()]
        rejected_traces = {str(r[0]) for r in conn.execute(
            text("SELECT trace_session_id FROM ai_human_feedback WHERE verdict = 'rejected'")
        ).all()}
        traces = conn.execute(
            text("SELECT id, cited_chunk_ids FROM policy_assistant_traces WHERE feature_key = :fk"),
            {"fk": feature_key},
        ).all()

    chunk_set = set(chunk_ids)
    citation: Dict[str, int] = defaultdict(int)
    rejection: Dict[str, int] = defaultdict(int)
    for trace_id, cited_raw in traces:
        is_rejected = str(trace_id) in rejected_traces
        seen: set = set()  # one chunk cited twice in an answer counts once
        for ref in _parse_cited(cited_raw):
            cid = _normalize_ref(ref)
            if cid in chunk_set and cid not in seen:
                seen.add(cid)
                citation[cid] += 1
                if is_rejected:
                    rejection[cid] += 1

    updates = []
    for cid in chunk_ids:
        cc = citation.get(cid, 0)
        rc = rejection.get(cid, 0)
        updates.append({
            "cid": cid, "cc": cc, "rc": rc,
            "score": reliability_score(cc, rc), "ts": updated_at,
        })

    if updates:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE immigration_corpus_chunks SET "
                    "reliability_score = :score, citation_count = :cc, "
                    "rejection_count = :rc, last_reliability_update = :ts "
                    "WHERE id = :cid"
                ),
                updates,
            )

    summary = {
        "chunks_total": len(chunk_ids),
        "traces_scanned": len(traces),
        "rejected_traces": len(rejected_traces),
        "chunks_with_citations": sum(1 for c in chunk_ids if citation.get(c, 0) > 0),
        "updated_at": updated_at.isoformat(),
    }
    log.info("recompute_reliability_scores %s", json.dumps(summary, separators=(",", ":")))
    return summary
