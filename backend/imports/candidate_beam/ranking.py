"""Corridor Candidate Beam — deterministic dedupe and ranking.

AUTHORING LAYER. Nothing here is served to a customer. This module turns the raw
per-pass output of N independent LLM passes into one ranked review queue, and it does so
with pure functions and no model call of its own — the LLM's job ended when the passes
returned.

Deterministic by design, and not an implementation detail: a review queue that reordered
itself between runs would make a reviewer's place in it meaningless, and the port is
pinned to a golden fixture (`backend/tests/fixtures/candidate_beam_fr_no_eea.json`) that
only reproduces if the algorithm matches exactly. No embeddings, no similarity model —
token Jaccard over a fixed stop-word list, greedy in arrival order.

Two rules that look like bugs and are not:

* **Nothing is dropped for being rare.** A candidate produced by 1 of 5 passes is kept and
  flagged for review priority. Low agreement is a triage signal; deleting it would hide
  precisely the non-obvious items the beam exists to surface.
* **Near-duplicate paraphrases occasionally survive as two rows.** That is accepted for a
  review queue — a human collapses them in a second. Loosening the threshold to "fix" it
  merges genuinely distinct requirements, which a human cannot recover from because the
  loser never appears.
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

# Sources the models emit when they mean "I have none". Treated as null rather than
# stored, because a source that looks like a source but is not is worse than an absent
# one: it survives review by looking already-done.
JUNK_SOURCES = {
    "n/a", "na", "none", "null", "nil", "unknown", "unspecified", "-", "—",
    "example.com", "www.example.com", "http://example.com", "https://example.com",
    "official website", "official site", "government website", "various",
    "see above", "tbd", "todo",
}

STOP_WORDS = {
    "the", "a", "an", "of", "to", "in", "for", "and", "or", "with", "on", "at", "from",
    "into", "before", "after", "your", "you", "must", "is", "are", "be", "been", "do",
    "does", "not", "no", "all", "any", "this", "that", "it", "its", "their", "they",
    "when", "if", "than", "via", "per", "within", "by", "as", "new", "get", "out", "up",
}

JOIN_THRESHOLD = 0.45
# Full-text agreement is a weaker signal than title agreement per token, so it is scaled
# up to compete on the same scale rather than given its own lower threshold.
FULL_SET_WEIGHT = 1.1

MAX_ITEMS_PER_PASS = 40
MAX_SOURCES_JOINED = 3

BAND_NEAR_CERTAIN = "near-certain"
BAND_STRONG = "strong"
BAND_MODERATE = "moderate"
BAND_LOW = "low"


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


def normalise_source(raw: Optional[str]) -> Optional[str]:
    """A claimed source, or None. Never invented, never URL-ified, never 'cleaned'.

    Stored verbatim apart from whitespace: the string is the model's CLAIM, and a human
    verifies it later. Rewriting `udi.no` into `https://udi.no/` would quietly assert a
    URL the model never gave.
    """
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    return None if value.lower() in JUNK_SOURCES else value


def _tokens(text: str) -> Set[str]:
    """Lowercase content tokens, accents preserved.

    Accented letters are kept deliberately — this corridor vocabulary is French and
    Norwegian ("séjour", "folkeregisteret"), and stripping accents to ASCII would collapse
    distinct terms and change cluster membership.
    """
    lowered = (text or "").lower()
    kept = []
    for ch in lowered:
        if ch.isalnum() or ch.isspace():
            kept.append(ch)
        elif unicodedata.category(ch).startswith("L"):
            kept.append(ch)
        else:
            kept.append(" ")
    words = re.split(r"\s+", "".join(kept))
    return {w for w in words if len(w) > 2 and w not in STOP_WORDS}


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


# ---------------------------------------------------------------------------
# Items and clusters
# ---------------------------------------------------------------------------


@dataclass
class Variant:
    """One raw item from one pass, as the model produced it."""

    pass_number: int
    framing: Optional[str]
    title: str
    official_guidance: str
    actual_reality: str
    action_required: str
    source: Optional[str]
    category: Optional[str]

    @property
    def body_length(self) -> int:
        return len(self.official_guidance or "") + len(self.actual_reality or "") + len(
            self.action_required or ""
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "pass": self.pass_number,
            "framing": self.framing,
            "title": self.title,
            "official_guidance": self.official_guidance,
            "actual_reality": self.actual_reality,
            "action_required": self.action_required,
            "source": self.source,
            "category": self.category,
        }


@dataclass
class Cluster:
    title_tokens: Set[str]
    full_tokens: Set[str]
    variants: List[Variant] = field(default_factory=list)

    def absorb(self, variant: Variant, title_tokens: Set[str], full_tokens: Set[str]) -> None:
        # The cluster's token sets GROW on join, so a later paraphrase that matches any
        # earlier member matches the cluster. Without this the first member alone would
        # define the cluster forever and near-synonyms would split.
        self.title_tokens |= title_tokens
        self.full_tokens |= full_tokens
        self.variants.append(variant)

    @property
    def pass_frequency(self) -> int:
        return len({v.pass_number for v in self.variants})


def parse_variant(raw: Dict[str, Any], pass_number: int, framing: Optional[str] = None) -> Optional[Variant]:
    """Build a Variant, or None when the item is unusable.

    An item with no title cannot be reviewed and an item with no action cannot be acted
    on; both are dropped rather than carried as noise. Everything else is kept, including
    items with no source — those are the research worklist.
    """
    title = str(raw.get("title") or "").strip()
    action = str(raw.get("action_required") or "").strip()
    if not title or not action:
        return None
    return Variant(
        pass_number=pass_number,
        framing=framing or raw.get("framing"),
        title=title,
        official_guidance=str(raw.get("official_guidance") or "").strip(),
        actual_reality=str(raw.get("actual_reality") or "").strip(),
        action_required=action,
        source=normalise_source(raw.get("source")),
        category=(raw.get("category") or None),
    )


def parse_pass(items: Sequence[Dict[str, Any]], pass_number: int, framing: Optional[str] = None) -> List[Variant]:
    """Usable variants from one pass's parsed output, capped."""
    out: List[Variant] = []
    for raw in list(items)[:MAX_ITEMS_PER_PASS]:
        variant = parse_variant(raw, pass_number, framing)
        if variant is not None:
            out.append(variant)
    return out


# ---------------------------------------------------------------------------
# Clustering and ranking
# ---------------------------------------------------------------------------


def cluster_variants(variants: Iterable[Variant]) -> List[Cluster]:
    """Greedy single-link clustering in arrival order.

    Arrival order is load-bearing: the same variants fed in a different order can produce
    a different clustering, because a cluster's tokens grow as it absorbs members. Callers
    must therefore feed passes in a stable order (pass 1 first, original order within a
    pass), which is what makes the golden fixture reproducible.
    """
    clusters: List[Cluster] = []
    for variant in variants:
        title_tokens = _tokens(variant.title)
        full_tokens = _tokens(
            " ".join([variant.title, variant.official_guidance, variant.action_required])
        )

        best: Optional[Cluster] = None
        best_score = 0.0
        for cluster in clusters:
            score = max(
                _jaccard(title_tokens, cluster.title_tokens),
                FULL_SET_WEIGHT * _jaccard(full_tokens, cluster.full_tokens),
            )
            if score > best_score:
                best, best_score = cluster, score

        if best is not None and best_score >= JOIN_THRESHOLD:
            best.absorb(variant, title_tokens, full_tokens)
        else:
            clusters.append(Cluster(title_tokens=title_tokens, full_tokens=full_tokens, variants=[variant]))
    return clusters


def confidence_band(frequency: int, passes_total: int) -> str:
    if passes_total > 0 and frequency >= passes_total:
        return BAND_NEAR_CERTAIN
    if frequency >= math.ceil(0.6 * passes_total):
        return BAND_STRONG
    if frequency >= 2:
        return BAND_MODERATE
    return BAND_LOW


def _representative(cluster: Cluster) -> Variant:
    """The variant whose text represents the cluster.

    A sourced variant wins outright — a citation is the scarcest thing in the set, and
    showing the reviewer the sourced phrasing puts the checkable claim in front of them.
    Otherwise the longest body wins as a proxy for the most complete articulation.
    """
    sourced = [v for v in cluster.variants if v.source]
    pool = sourced or cluster.variants
    return max(pool, key=lambda v: (v.body_length, v.title))


def _joined_sources(cluster: Cluster) -> Optional[str]:
    seen: List[str] = []
    for variant in cluster.variants:
        if variant.source and variant.source not in seen:
            seen.append(variant.source)
    return "; ".join(seen[:MAX_SOURCES_JOINED]) if seen else None


def rank_clusters(clusters: Sequence[Cluster], passes_total: int) -> List[Dict[str, Any]]:
    """Ranked candidate rows, 1-based.

    Order: agreement first, then sourced before unsourced, then title A-Z. The tie-breaks
    are not cosmetic — they put the checkable items above the unresearched ones at equal
    agreement, which is the order a reviewer wants to work in.
    """
    rows: List[Dict[str, Any]] = []
    for cluster in clusters:
        rep = _representative(cluster)
        frequency = cluster.pass_frequency
        source = _joined_sources(cluster)
        source_missing = source is None
        rows.append(
            {
                "title": rep.title,
                "official_guidance": rep.official_guidance,
                "actual_reality": rep.actual_reality,
                "action_required": rep.action_required,
                "category": rep.category,
                "source": source,
                "source_missing": source_missing,
                "pass_frequency": frequency,
                "passes_total": passes_total,
                "confidence_band": confidence_band(frequency, passes_total),
                # Rare OR unresearched. Both are reasons a human should look first, and
                # collapsing them into one flag is deliberate: the review queue sorts by
                # "needs attention", not by which kind of attention.
                "flagged": frequency <= 1 or source_missing,
                "variants": [v.as_dict() for v in cluster.variants],
            }
        )

    rows.sort(key=lambda r: (-r["pass_frequency"], r["source_missing"], r["title"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def build_candidates(passes: Sequence[Sequence[Dict[str, Any]]], framings: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    """Raw per-pass outputs -> ranked candidate rows.

    `passes[i]` is pass i+1's parsed items. Empty or failed passes are passed through as
    empty lists so that `passes_total` still reflects what was attempted — a run that
    completed 4 of 5 passes must not silently report 4/4 agreement as unanimous.
    """
    variants: List[Variant] = []
    for index, items in enumerate(passes):
        framing = framings[index] if framings and index < len(framings) else None
        variants.extend(parse_pass(items or [], index + 1, framing))
    return rank_clusters(cluster_variants(variants), passes_total=len(passes))
