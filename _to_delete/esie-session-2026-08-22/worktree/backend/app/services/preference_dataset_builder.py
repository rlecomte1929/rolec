"""
Preference dataset builder (Parker Step E).

Turns human review verdicts (``ai_human_feedback``) into:

* **DPO-style preference pairs** — ``{prompt, chosen, rejected}`` JSONL, suitable
  for DPO/KTO fine-tuning or for re-ranking prompt-registry canaries.
* **Per-version win rates** — approvals / total verdicts with a Wilson 95% CI.

Honest-signal constraints (grounded in the actual schema Step D shipped):

* ``policy_assistant_traces`` is deliberately **PII-free** — it stores only a
  ``query_hash`` (16-hex SHA-256 of the question), never the raw prompt or the
  model output. So pairs are keyed on ``query_hash`` (the only anonymized "same
  underlying question" signal available), and the ``chosen`` / ``rejected`` text
  is populated from the reviewer-supplied ``edited_output_json`` where present;
  otherwise it carries a stable version reference (``version:<id>:arm:<arm>``) that
  a downstream job rehydrates to raw text by ``query_hash`` from its own store.
* ``edited`` is treated as "the original output was rejected, the edited output was
  approved" (per the audit design note) — a single ``edited`` row yields one
  self-contained pair (chosen = edited text, rejected = original reference).
* ``approved`` / ``rejected`` rows on the *same* ``query_hash`` but *different*
  arms form a cross-arm pair (the only honest A/B signal from organic traffic).
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ..db import SessionLocal

log = logging.getLogger(__name__)

_Z_95 = 1.959963984540054  # z for a 95% two-sided normal interval


# ── Data shapes ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DPOPair:
    """One preference pair in the canonical ``{prompt, chosen, rejected}`` shape."""

    prompt: str  # the anonymized input key (query_hash); rehydrate text downstream
    chosen: str
    rejected: str
    task_key: str
    chosen_version_id: Optional[str]
    rejected_version_id: Optional[str]
    source: str  # 'edited' | 'cross_arm'

    def to_jsonl_obj(self) -> Dict[str, Any]:
        d = asdict(self)
        prompt = d.pop("prompt")
        chosen = d.pop("chosen")
        rejected = d.pop("rejected")
        return {"prompt": prompt, "chosen": chosen, "rejected": rejected, "metadata": d}


@dataclass(frozen=True)
class WinRate:
    version_id: str
    approvals: int
    total: int
    win_rate: float
    ci_low: float
    ci_high: float


# ── Pure helpers ──────────────────────────────────────────────────────────────


def wilson_interval(approvals: int, total: int, z: float = _Z_95) -> Dict[str, float]:
    """Wilson score interval for a binomial proportion (95% by default).

    Used instead of naive ±√(p(1-p)/n) because Romain reads these numbers in
    product meetings and the naive interval is badly wrong for small n. Returns
    ``{rate, low, high}`` all clamped to ``[0, 1]``; ``total == 0`` → all zeros.
    """
    if total <= 0:
        return {"rate": 0.0, "low": 0.0, "high": 0.0}
    p = approvals / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (p + z2 / (2 * total)) / denom
    half = (z * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total))) / denom
    return {
        "rate": p,
        "low": max(0.0, center - half),
        "high": min(1.0, center + half),
    }


def _version_ref(version_id: Optional[str], arm: Optional[str]) -> str:
    return f"version:{version_id or 'unknown'}:arm:{arm or 'unknown'}"


def _edited_text(edited_output_json: Any) -> Optional[str]:
    """Normalise the jsonb/text edited output into a string for the chosen side."""
    if edited_output_json is None:
        return None
    if isinstance(edited_output_json, str):
        return edited_output_json
    try:
        return json.dumps(edited_output_json, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return str(edited_output_json)


# ── Read path ─────────────────────────────────────────────────────────────────


def _fetch_feedback(s: Any, task_key: str) -> List[Dict[str, Any]]:
    """All attributed feedback for a task_key, joined to its trace's query_hash."""
    rows = (
        s.execute(
            text(
                "SELECT f.id, f.trace_session_id, f.verdict, f.edited_output_json, "
                "       f.prompt_version_id, f.canary_arm, t.query_hash, pv.task_key "
                "FROM ai_human_feedback f "
                "JOIN policy_assistant_traces t ON t.id = f.trace_session_id "
                "JOIN prompt_versions pv ON pv.id = f.prompt_version_id "
                "WHERE pv.task_key = :tk"
            ),
            {"tk": task_key},
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def build_dpo_pairs(
    task_key: str, min_pairs: int = 50, *, session: Any = None
) -> List[DPOPair]:
    """Build ``{prompt, chosen, rejected}`` preference pairs for ``task_key``.

    ``min_pairs`` is a soft target: if fewer honest pairs exist we log a warning
    and return what we have (never fabricate pairs). Empty feedback → ``[]``.
    """
    own = session is None
    s = session or SessionLocal()
    try:
        rows = _fetch_feedback(s, task_key)
    finally:
        if own:
            s.close()

    pairs: List[DPOPair] = []

    # (a) edited verdicts → self-contained edit-preference pairs.
    for r in rows:
        if r["verdict"] != "edited":
            continue
        chosen = _edited_text(r["edited_output_json"])
        if not chosen:
            continue  # nothing to learn from without the edited text
        pairs.append(
            DPOPair(
                prompt=r["query_hash"],
                chosen=chosen,
                rejected=_version_ref(r["prompt_version_id"], r["canary_arm"]),
                task_key=task_key,
                chosen_version_id=r["prompt_version_id"],
                rejected_version_id=r["prompt_version_id"],
                source="edited",
            )
        )

    # (b) cross-arm: same query_hash, one approved + one rejected, different arm.
    by_hash: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        if r["verdict"] in ("approved", "rejected"):
            by_hash.setdefault(r["query_hash"], []).append(r)

    for query_hash, group in by_hash.items():
        approved = [r for r in group if r["verdict"] == "approved"]
        rejected = [r for r in group if r["verdict"] == "rejected"]
        for win in approved:
            for lose in rejected:
                if win["canary_arm"] == lose["canary_arm"]:
                    continue  # same arm — no A/B signal
                pairs.append(
                    DPOPair(
                        prompt=query_hash,
                        chosen=_version_ref(win["prompt_version_id"], win["canary_arm"]),
                        rejected=_version_ref(lose["prompt_version_id"], lose["canary_arm"]),
                        task_key=task_key,
                        chosen_version_id=win["prompt_version_id"],
                        rejected_version_id=lose["prompt_version_id"],
                        source="cross_arm",
                    )
                )

    if len(pairs) < min_pairs:
        log.warning(
            "build_dpo_pairs(%s): only %d pairs (< min_pairs=%d)",
            task_key,
            len(pairs),
            min_pairs,
        )
    return pairs


def compute_win_rates(task_key: str, *, session: Any = None) -> Dict[str, WinRate]:
    """Per-version win rate (approvals / total verdicts) with a Wilson 95% CI.

    ``edited`` and ``rejected`` both count as non-wins (an ``edited`` verdict means
    the original output was not accepted as-is). Keyed by ``prompt_version_id``.
    """
    own = session is None
    s = session or SessionLocal()
    try:
        rows = (
            s.execute(
                text(
                    "SELECT f.prompt_version_id AS vid, f.verdict AS verdict, "
                    "       COUNT(*) AS n "
                    "FROM ai_human_feedback f "
                    "JOIN prompt_versions pv ON pv.id = f.prompt_version_id "
                    "WHERE pv.task_key = :tk "
                    "GROUP BY f.prompt_version_id, f.verdict"
                ),
                {"tk": task_key},
            )
            .mappings()
            .all()
        )
    finally:
        if own:
            s.close()

    agg: Dict[str, Dict[str, int]] = {}
    for r in rows:
        vid = str(r["vid"])
        bucket = agg.setdefault(vid, {"approvals": 0, "total": 0})
        bucket["total"] += int(r["n"])
        if r["verdict"] == "approved":
            bucket["approvals"] += int(r["n"])

    out: Dict[str, WinRate] = {}
    for vid, c in agg.items():
        ci = wilson_interval(c["approvals"], c["total"])
        out[vid] = WinRate(
            version_id=vid,
            approvals=c["approvals"],
            total=c["total"],
            win_rate=ci["rate"],
            ci_low=ci["low"],
            ci_high=ci["high"],
        )
    return out
