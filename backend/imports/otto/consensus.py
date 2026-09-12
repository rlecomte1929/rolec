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
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from backend.imports.otto.parsers import OFFICIAL, UNOFFICIAL, classify_source

Fact = Dict[str, Any]

#: Entity-resolution, step 1 — canonical topic keys. Independent research passes name the same
#: topic differently ("right_of_residence" / "eu_right_of_residence" / "…_worker"). Voting on the
#: raw key collapses consensus to noise, so map known aliases to a canonical form. Explicit and
#: deterministic on purpose (no silent structural merges); extend it as corridors are added.
CANONICAL_TOPICS: Dict[str, str] = {
    "right_of_residence": "eu_right_of_residence",
    "right_of_residence_eu": "eu_right_of_residence",
    "eu_right_of_residence_worker": "eu_right_of_residence",
    "eea_right_of_residence": "eu_right_of_residence",
    "eu_residence_permit_optional": "eu_right_of_residence",
    "driving_licence": "eu_driving_licence",
    "eea_driving_licence": "eu_driving_licence",
    "numero_securite_sociale": "social_security_number",
    "numero_de_securite_sociale": "social_security_number",
    "securite_sociale": "social_security_number",
    "opening_bank_account": "bank_account",
    "bank_account_opening": "bank_account",
    "family_benefits_caf": "caf_family_benefits",
    "tax_residence": "income_tax_residence",
    "puma": "puma_health_cover",
    "school_enrollment": "school_enrolment",
    "s1": "s1_portable_document",
}

#: Content-word filter for fact-text similarity (EN + a little FR). Kept small and stable.
_STOPWORDS: Set[str] = set(
    "a an the of to in on for and or is are be as it this that by with from at into you your "
    "must may can will shall not no if then within their they them there here which who whom "
    "de la le les des du un une et ou en dans pour par sur au aux que qui ne pas est sont doit "
    "vous votre son sa ses leur leurs".split()
)


def _canon_topic(topic: Any) -> str:
    t = str(topic or "").strip().lower()
    return CANONICAL_TOPICS.get(t, t)


def _content_tokens(text: Any) -> Set[str]:
    """Accent-stripped, stopword-filtered content tokens of a fact_text — the clustering signal."""
    norm = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return {w for w in re.findall(r"[a-z0-9]+", norm) if len(w) > 2 and w not in _STOPWORDS}


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


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


def _finalize(rep: Fact, pass_count: int, canon_topic: str, *, needs_lawyer: bool) -> Fact:
    out = copy.deepcopy(rep)
    applies = dict(out.get("applies_to") or {})
    applies["pass_count"] = pass_count
    out["applies_to"] = applies
    out["entity_topic_key"] = canon_topic  # canonical, so re-runs converge on one key
    out["needs_lawyer_review"] = needs_lawyer
    return out


def _gap(rep: Fact, pass_count: int, canon_topic: str, reason: str) -> Dict[str, Any]:
    return {
        "destination_country": str(rep.get("destination_country", "")).strip().upper(),
        "entity_topic_key": canon_topic,
        "fact_key": rep.get("fact_key", ""),
        "source_url": rep.get("source_url", ""),
        "pass_count": pass_count,
        "reason": reason,
    }


def _cluster_topic(items: List[Tuple[int, Fact]], sim_threshold: float) -> List[Dict[str, Any]]:
    """Greedily cluster one topic's facts by fact-text similarity (entity resolution, step 2).

    Independent passes drift the fact_key for the same fact, so exact-key voting misses the
    agreement. The fact_text, however, stays near-identical for the same fact and diverges for
    genuinely different facts — so cluster on content-token Jaccard. Deterministic: items are
    pre-sorted, and a fact joins the first cluster it is similar enough to.
    """
    ordered = sorted(items, key=lambda pf: (str(pf[1].get("fact_key", "")),
                                            str(pf[1].get("source_url", "")), pf[0]))
    clusters: List[Dict[str, Any]] = []
    for pass_index, fact in ordered:
        tokens = _content_tokens(fact.get("fact_text"))
        for c in clusters:
            if _jaccard(tokens, c["tokens"]) >= sim_threshold:
                c["passes"].add(pass_index)
                c["instances"].append(fact)
                break
        else:
            clusters.append({"tokens": tokens, "passes": {pass_index}, "instances": [fact]})
    return clusters


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return 0.0 if na == 0.0 or nb == 0.0 else dot / (na * nb)


def _merge_clusters_by_embedding(
    clusters: List[Dict[str, Any]],
    embed_fn: Callable[[List[str]], List[List[float]]],
    threshold: float,
) -> List[Dict[str, Any]]:
    """Agglomeratively merge deterministic clusters whose representative facts are semantically
    equal (embedding cosine >= threshold).

    This runs ON TOP OF the deterministic (topic + token-Jaccard) clustering and only ever
    *combines* clusters — never splits one — so consensus yield is always >= the deterministic
    path. That guarantee matters: a global embedding clustering can *fragment* a fact the
    topic-grouping had correctly grouped (observed live: it cut NO→FR from 3 consensus to 1). This
    design instead recovers the same fact when passes drift the topic key AND phrase it beyond
    token overlap, without ever losing a deterministic grouping. ``embed_fn`` is injected — the
    module imports no LLM SDK. The threshold is conservative: a false merge of two distinct
    compliance facts is worse than an under-count.
    """
    if len(clusters) < 2:
        return clusters
    reps = [_representative(c["instances"]) for c in clusters]
    vectors = embed_fn([str(r.get("fact_text", "") or "") for r in reps])

    parent = list(range(len(clusters)))

    def find(i: int) -> int:
        root = i
        while parent[root] != root:
            root = parent[root]
        while parent[i] != root:
            parent[i], i = root, parent[i]
        return root

    for i in range(len(clusters)):
        for j in range(i + 1, len(clusters)):
            if _cosine(vectors[i], vectors[j]) >= threshold:
                parent[find(i)] = find(j)

    merged: Dict[int, Dict[str, Any]] = {}
    for i, c in enumerate(clusters):
        root = find(i)
        m = merged.setdefault(root, {"passes": set(), "instances": []})
        m["passes"] |= c["passes"]
        m["instances"].extend(c["instances"])
    return list(merged.values())


def _apply_bands(
    clusters: List[Dict[str, Any]], n: int, middle_floor: int
) -> Tuple[List[Fact], List[Fact], List[Dict[str, Any]]]:
    """Route each resolved cluster into consensus / needs_review / gaps by pass_count + sourcing."""
    consensus: List[Fact] = []
    needs_review: List[Fact] = []
    gaps: List[Dict[str, Any]] = []
    for cluster in clusters:
        count = len(cluster["passes"])
        rep = _representative(cluster["instances"])
        canon_topic = _canon_topic(rep.get("entity_topic_key"))
        tier = _tier(rep)
        has_quote = _has_verbatim_quote(rep)
        if tier == UNOFFICIAL:
            gaps.append(_gap(rep, count, canon_topic,
                             "source is unofficial (blog / vendor / law-firm) — rejected"))
        elif count >= n and tier == OFFICIAL and has_quote:
            consensus.append(_finalize(rep, count, canon_topic, needs_lawyer=False))
        elif count >= middle_floor:
            needs_review.append(_finalize(rep, count, canon_topic, needs_lawyer=True))
        elif tier == OFFICIAL and has_quote:
            # Low-band rescue: a single strong statutory citation is worth a lawyer's look.
            needs_review.append(_finalize(rep, count, canon_topic, needs_lawyer=True))
        else:
            gaps.append(_gap(rep, count, canon_topic,
                             f"low consensus ({count}/{n}) and not statutory + verbatim"))
    return consensus, needs_review, gaps


def merge_passes(
    passes: List[List[Fact]],
    *,
    n_passes: int | None = None,
    low_band_ratio: float = 0.6,
    sim_threshold: float = 0.55,
    embed_fn: Optional[Callable[[List[str]], List[List[float]]]] = None,
    embed_threshold: float = 0.86,
) -> ConsensusResult:
    """Vote N independent research passes into consensus / needs_review / gaps.

    Facts are resolved before voting because independent passes drift both the topic key and the
    fact key. Two resolution modes:

    - default (deterministic, LLM-free): group by (destination_country, CANONICAL topic), then
      cluster within a topic by fact-text token Jaccard.
    - ``embed_fn`` given (opt-in, higher yield): group by destination_country only, then cluster
      by fact-text embedding cosine — merges the same fact across drifted topic keys and differing
      phrasing. ``embed_fn(list[str]) -> list[list[float]]`` is injected; this module imports no
      LLM SDK, so the isolation guard is unaffected.

    A cluster's ``pass_count`` is the number of *distinct* passes in it. Bands (``n`` = passes):
      - ``pass_count == n`` AND official source AND verbatim quote  → **consensus**
      - ``pass_count >= ceil(low_band_ratio*n)`` (incl. full-count that missed the clean bar) → **needs_review**
      - below that, official + verbatim → **needs_review**; otherwise → **gap**
      - any unofficial source, at any pass_count → **gap** (hard rule)
    """
    n = n_passes if n_passes is not None else len(passes)
    if n <= 0:
        return ConsensusResult([], [], [], {"n_passes": 0})

    middle_floor = math.ceil(low_band_ratio * n)  # >= this and < n is the "middle" band

    by_dest: Dict[str, List[Tuple[int, Fact]]] = {}
    for pass_index, one_pass in enumerate(passes):
        for fact in one_pass:
            dc = str(fact.get("destination_country", "")).strip().upper()
            by_dest.setdefault(dc, []).append((pass_index, fact))

    clusters: List[Dict[str, Any]] = []
    for dc in sorted(by_dest):
        # Deterministic base: group by canonical topic, cluster each by token Jaccard.
        by_topic: Dict[str, List[Tuple[int, Fact]]] = {}
        for pass_index, fact in by_dest[dc]:
            by_topic.setdefault(_canon_topic(fact.get("entity_topic_key")), []).append((pass_index, fact))
        dest_clusters: List[Dict[str, Any]] = []
        for tk in sorted(by_topic):
            dest_clusters.extend(_cluster_topic(by_topic[tk], sim_threshold))
        # Opt-in: merge base clusters that are the same fact across drifted topics/phrasing.
        # Merge-only, so yield is always >= the deterministic base.
        if embed_fn is not None:
            dest_clusters = _merge_clusters_by_embedding(dest_clusters, embed_fn, embed_threshold)
        clusters.extend(dest_clusters)

    consensus, needs_review, gaps = _apply_bands(clusters, n, middle_floor)

    histogram = Counter()
    for bucket in (consensus, needs_review):
        for f in bucket:
            histogram[f["applies_to"]["pass_count"]] += 1
    report = {
        "n_passes": n,
        "mode": "embedding" if embed_fn is not None else "deterministic",
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
