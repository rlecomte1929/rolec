"""
N8 / AIQ-848 — central, tunable knobs for the source-reliability feedback loop.

Single source of truth so the score computation (source_reliability_service) and
the ranking application (immigration_retriever) read the same values, and a future
admin panel (N8-FU) can read/write them without touching either module's logic.

Env-backed for now; N8-FU moves these DB-backed + surfaces them in the admin UI.

⚠️ Ships DORMANT: RELIABILITY_WEIGHT defaults to 0.0, so the feedback-loop score has
NO effect on ranking until it is deliberately turned up. This lets the producer side
(N8-FU) start logging feedback without silently shifting prod ranking — you ramp the
weight 0 → 1 while watching results.
"""
from __future__ import annotations

import os

# ── Ranking application (immigration_retriever) ──────────────────────────────
# How much the reliability score influences ranking. Applied as a blended factor:
#   factor = (1 - weight) + weight * reliability_score
#   adjusted_score = raw * tier_boost * freshness * factor
#   weight = 0.0 -> factor is always 1.0  -> reliability has NO effect (safe default)
#   weight = 1.0 -> factor == reliability_score (full effect)
RELIABILITY_WEIGHT: float = float(os.getenv("IMMIGRATION_RELIABILITY_WEIGHT", "0.0"))

# Neutral score for a chunk with no feedback yet (also the DB column default).
NEUTRAL_RELIABILITY: float = float(os.getenv("IMMIGRATION_RELIABILITY_NEUTRAL", "0.5"))

# ── Score computation (source_reliability_service) ───────────────────────────
# Wilson z (1.96 = 95% lower bound) and the citation count below which the Wilson
# lower bound is used instead of the raw rejection rate.
# (N8-FU: a min-citations floor here is where the "clean-but-lightly-cited scores
#  below neutral" tuning will live — left at spec defaults until there's real data.)
WILSON_Z: float = float(os.getenv("IMMIGRATION_RELIABILITY_WILSON_Z", "1.96"))
LOW_SAMPLE_THRESHOLD: int = int(os.getenv("IMMIGRATION_RELIABILITY_LOW_SAMPLE", "10"))


def reliability_factor(reliability_score) -> float:
    """
    Blend a chunk's reliability_score into a ranking multiplier per RELIABILITY_WEIGHT.
    Reads the module-level weight at call time (so it stays tunable / monkeypatchable).
    weight=0 -> 1.0 (dormant); weight=1 -> the clamped reliability_score.
    """
    rel = NEUTRAL_RELIABILITY if reliability_score is None else float(reliability_score)
    rel = max(0.0, min(1.0, rel))
    w = max(0.0, min(1.0, RELIABILITY_WEIGHT))
    return (1.0 - w) + w * rel
