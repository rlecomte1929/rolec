"""RPX-05 consensus merge + eval — the deterministic core of the corridor-facts research pipeline.

Why this exists
---------------
Reliable corridor knowledge at scale cannot come from a single LLM pass (one pass is
confidently wrong often enough to be dangerous for a compliance product) and it must not be
hand-coded (that does not scale to new countries/cities/services and cannot be kept fresh).
The answer is an *ensemble*: run N independent research passes, then keep a fact only in
proportion to how many passes independently found it, gated by whether it is cited to a
statutory source with a verbatim quote.

This module is that merge. It is **deterministic and LLM-free**: N passes of candidate facts
go in (each pass produced by a separate research worker and delivered as a file), a voted,
citation-gated set of candidate rows comes out — in the same FactRow shape
``scripts/import_otto_facts.py`` already loads as ``review_status='pending'``. It lives in the
authoring layer and never serves; keeping the merge in code (not in a model's head) is the
whole point — "the merge is a checklist, then JSONL".

Technique provenance
--------------------
- Multi-pass / self-consistency and offline evaluation suites: Berryman & Ziegler,
  *Prompt Engineering for LLMs* (O'Reilly, 2025), ch. 9 & 10.
- Evaluation-driven development + guardrails: Chip Huyen, *AI Engineering* (O'Reilly, 2024).

The consensus bands (5/5 → consensus; 3-4/5 → needs_lawyer_review; 1-2/5 → drop unless
statutory + verbatim) are the RPX-05 card's rules, made executable.
"""
from __future__ import annotations

import copy
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from backend.imports.otto.parsers import OFFICIAL, UNOFFICIAL, classify_source

Fact = Dict[str, Any]
Key = Tuple[str, str, str]


@dataclass
class ConsensusResult:
    #: Clean, servable-after-review candidates: full pass agreement, official source, verbatim quote.
    consensus: List[Fact]
    #: Included but flagged: middle-band agreement, or semi-official, or low-band statutory rescue.
    needs_review: List[Fact]
    #: Rejected — the re-sourcing worklist, never fabricated into a fact.
    gaps: List[Dict[str, Any]]
    #: Per-run metrics (pass-count histogram, band counts).
    report: Dict[str, Any] = field(default_factory=dict)


def _key(fact: Fact) -> Key:
    return (
        str(fact.get("destination_country", "")).strip().upper(),
        str(fact.get("entity_topic_key", "")).strip(),
        str(fact.get("fact_key", "")).strip(),
    )


def _has_verbatim_quote(fact: Fact) -> bool:
    return bool(str(fact.get("evidence_quote", "") or "").strip())


def _tier(fact: Fact) -> str:
    return classify_source(str(fact.get("source_url", "") or ""))


def _representative(instances: List[Fact]) -> Fact:
    """The best instance of a fact across passes: official first, then quoted, then longest quote.

    Deterministic so a re-run over the same passes yields byte-identical output.
    """
    def rank(f: Fact) -> Tuple[int, int, int]:
        return (
            1 if _tier(f) == OFFICIAL else 0,
            1 if _has_verbatim_quote(f) else 0,
            len(str(f.get("evidence_quote", "") or "")),
        )

    return sorted(instances, key=rank, reverse=True)[0]


def _finalize(rep: Fact, pass_count: int, *, needs_lawyer: bool) -> Fact:
    out = copy.deepcopy(rep)
    applies = dict(out.get("applies_to") or {})
    applies["pass_count"] = pass_count
    out["applies_to"] = applies
    out["needs_lawyer_review"] = needs_lawyer
    return out


def _gap(rep: Fact, pass_count: int, reason: str) -> Dict[str, Any]:
    return {
        "destination_country": str(rep.get("destination_country", "")).strip().upper(),
        "entity_topic_key": rep.get("entity_topic_key", ""),
        "fact_key": rep.get("fact_key", ""),
        "source_url": rep.get("source_url", ""),
        "pass_count": pass_count,
        "reason": reason,
    }


def merge_passes(
    passes: List[List[Fact]],
    *,
    n_passes: int | None = None,
    low_band_ratio: float = 0.6,
) -> ConsensusResult:
    """Vote N independent research passes into consensus / needs_review / gaps.

    A fact's ``pass_count`` is the number of *distinct* passes that produced its
    (destination_country | entity_topic_key | fact_key) key.

    Bands (``n`` = number of passes):
      - ``pass_count == n`` AND official source AND verbatim quote  → **consensus**
      - ``pass_count >= ceil(low_band_ratio*n)`` (incl. full-count that missed the clean bar,
        e.g. semi-official or no quote)                             → **needs_review** (lawyer)
      - below that (low band): kept only if official + verbatim      → **needs_review** (lawyer)
        otherwise                                                    → **gap**
      - any unofficial source, at any pass_count                     → **gap** (hard rule)
    """
    n = n_passes if n_passes is not None else len(passes)
    if n <= 0:
        return ConsensusResult([], [], [], {"n_passes": 0})

    middle_floor = math.ceil(low_band_ratio * n)  # >= this and < n is the "middle" band

    groups: Dict[Key, Dict[str, Any]] = {}
    for pass_index, one_pass in enumerate(passes):
        for fact in one_pass:
            g = groups.setdefault(_key(fact), {"passes": set(), "instances": []})
            g["passes"].add(pass_index)
            g["instances"].append(fact)

    consensus: List[Fact] = []
    needs_review: List[Fact] = []
    gaps: List[Dict[str, Any]] = []

    for key in sorted(groups):
        g = groups[key]
        count = len(g["passes"])
        rep = _representative(g["instances"])
        tier = _tier(rep)
        has_quote = _has_verbatim_quote(rep)

        if tier == UNOFFICIAL:
            gaps.append(_gap(rep, count, "source is unofficial (blog / vendor / law-firm) — rejected"))
        elif count >= n and tier == OFFICIAL and has_quote:
            consensus.append(_finalize(rep, count, needs_lawyer=False))
        elif count >= middle_floor:
            reason = []
            if tier != OFFICIAL:
                reason.append("semi-official publisher")
            if not has_quote:
                reason.append("no verbatim quote")
            needs_review.append(_finalize(rep, count, needs_lawyer=True))
        elif tier == OFFICIAL and has_quote:
            # Low-band rescue: a single strong statutory citation is worth a lawyer's look.
            needs_review.append(_finalize(rep, count, needs_lawyer=True))
        else:
            gaps.append(_gap(rep, count, f"low consensus ({count}/{n}) and not statutory + verbatim"))

    histogram = Counter()
    for bucket in (consensus, needs_review):
        for f in bucket:
            histogram[f["applies_to"]["pass_count"]] += 1
    report = {
        "n_passes": n,
        "n_consensus": len(consensus),
        "n_needs_review": len(needs_review),
        "n_gaps": len(gaps),
        "pass_count_histogram": {str(k): v for k, v in sorted(histogram.items(), reverse=True)},
    }
    return ConsensusResult(consensus, needs_review, gaps, report)


def evaluate_consensus(result: ConsensusResult, *, min_gap_ratio_warn: float = 0.5) -> Dict[str, Any]:
    """Offline eval of a merge result (Huyen: the eval defines "good"; it is the guardrail).

    Verifies the merge's own invariant — every consensus row is official + verbatim-cited —
    so a regression in ``merge_passes`` fails here rather than shipping a wrong fact. Also
    reports quality metrics for the run.
    """
    cons = result.consensus
    n = len(cons)

    def cited(f: Fact) -> bool:
        return bool(str(f.get("source_url", "") or "").strip()) and _has_verbatim_quote(f)

    citation_coverage = 1.0 if n == 0 else sum(1 for f in cons if cited(f)) / n
    statutory_ratio = 1.0 if n == 0 else sum(1 for f in cons if _tier(f) == OFFICIAL) / n
    total = n + len(result.needs_review) + len(result.gaps)
    gap_ratio = 0.0 if total == 0 else len(result.gaps) / total

    invariant_ok = citation_coverage == 1.0 and statutory_ratio == 1.0
    warnings = []
    if gap_ratio >= min_gap_ratio_warn:
        warnings.append(f"high gap ratio ({gap_ratio:.0%}) — corridor may be under-sourced")

    return {
        "verdict": "PASS" if invariant_ok else "FAIL",
        "n_consensus": n,
        "n_needs_review": len(result.needs_review),
        "n_gaps": len(result.gaps),
        "citation_coverage": citation_coverage,
        "statutory_ratio": statutory_ratio,
        "gap_ratio": gap_ratio,
        "pass_count_histogram": result.report.get("pass_count_histogram", {}),
        "warnings": warnings,
    }
