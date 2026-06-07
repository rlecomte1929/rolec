"""
N7 / AIQ-846 — pre-generation contradiction detection for the immigration
retrieval pipeline.

The immigration answer engine concatenates all retrieved chunks and lets the
LLM blend them — even when two sources state conflicting facts (e.g. a 4-week
vs a 12-week processing time). This module runs a fast pairwise conflict check
*before* generation, resolves conflicts by source authority then freshness, and
escalates when two equally-authoritative official sources disagree.

Resolution preference (per the N7 spec):
  1. Higher trust_tier wins (LOWER number = higher trust).
  2. If trust_tier is equal, the more recent fetched_at wins.
  3. If both are equal AND both are trust_tier == 1 (official), suppress
     neither — escalate so the generator presents both with a verify-directly note.

Cost/latency guards:
  - Only the top-k chunks (by adjusted_score) are compared (k=5 default).
  - Only pairs where BOTH chunks have adjusted_score >= 0.4 are checked.
  - A small, fast model is used (claude-haiku-4-5-20251001).

Fail-open: any LLM error (timeout, parse failure on the call itself) leaves the
pipeline untouched — all chunks pass through and contradiction_check_skipped=True.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .policy_assistant_llm_client import LlmClient, LlmRequest, get_default_client

log = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_TOP_K = 5
_MIN_SCORE = 0.4
_OFFICIAL_TIER = 1

CONFLICTING_OFFICIAL_SOURCES_NOTE = (
    "CONFLICTING OFFICIAL SOURCES: two official sources disagree on the same "
    "requirement. Present both perspectives and advise the user to verify directly "
    "with the relevant immigration authority."
)

_PAIR_SYSTEM = (
    "You compare two passages about immigration requirements and decide whether they "
    "state conflicting facts about the SAME requirement (e.g. different processing "
    "times, fees, or document rules for the same permit). Differences in topic or "
    "scope are NOT conflicts. Respond ONLY with JSON: "
    '{"conflict": true|false, "topic": str, "chunk_a_claim": str, "chunk_b_claim": str}.'
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_fetched_at(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _trust_tier(chunk: Dict[str, Any]) -> int:
    try:
        return int(chunk.get("trust_tier"))
    except (TypeError, ValueError):
        # Unknown trust → treat as least authoritative so a known tier wins.
        return 999


def _build_pair_message(a: Dict[str, Any], b: Dict[str, Any]) -> str:
    ta = (a.get("chunk_text") or "").replace("\n", " ").strip()
    tb = (b.get("chunk_text") or "").replace("\n", " ").strip()
    return f"PASSAGE A:\n{ta}\n\nPASSAGE B:\n{tb}"


def _classify_pair(client: LlmClient, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Return True iff the two passages conflict. Raises on LLM transport error."""
    resp = client.complete(
        LlmRequest(system=_PAIR_SYSTEM, user_message=_build_pair_message(a, b), model=_MODEL, max_tokens=256)
    )
    text = (resp.get("text") or "").strip()
    m = _JSON_RE.search(text)
    if not m:
        # Unparseable model output for this pair → treat as no conflict (don't suppress
        # on ambiguity). Transport errors are handled a level up (fail-open).
        log.warning("contradiction detector: unparseable pair verdict: %r", text[:200])
        return False
    try:
        return bool(json.loads(m.group(0)).get("conflict"))
    except (ValueError, TypeError):
        return False


def _resolve(a: Dict[str, Any], b: Dict[str, Any]) -> str:
    """
    Decide the winner of a conflicting pair.
    Returns 'a' (suppress b), 'b' (suppress a), or 'escalate' (keep both).
    """
    ta, tb = _trust_tier(a), _trust_tier(b)
    if ta != tb:
        return "a" if ta < tb else "b"
    # Equal trust tier → prefer the fresher source.
    fa, fb = _parse_fetched_at(a.get("fetched_at")), _parse_fetched_at(b.get("fetched_at"))
    if fa and fb and fa != fb:
        return "a" if fa > fb else "b"
    # Equal trust AND equal/again unknown freshness.
    if ta == _OFFICIAL_TIER:
        return "escalate"
    # Non-official, fully tied: can't rank — keep both rather than drop silently.
    return "escalate"


def detect_and_resolve_conflicts(
    chunks: List[Dict[str, Any]],
    *,
    client: Optional[LlmClient] = None,
    top_k: int = _TOP_K,
    min_score: float = _MIN_SCORE,
) -> Dict[str, Any]:
    """
    Detect factual conflicts between retrieved chunks and resolve them.

    Returns:
      {
        "kept_chunks": [...],          # non-suppressed chunks for the generator
        "suppressed_chunks": [...],    # each annotated conflict_suppressed=True
        "conflicts_detected": int,
        "conflicts_resolved": int,     # conflicts resolved by suppressing a loser
        "escalations": [ {topic, source_urls: [...]} ],
        "contradiction_check_skipped": bool,
      }
    """
    base = {
        "kept_chunks": list(chunks),
        "suppressed_chunks": [],
        "conflicts_detected": 0,
        "conflicts_resolved": 0,
        "escalations": [],
        "contradiction_check_skipped": False,
    }
    if not chunks or len(chunks) < 2:
        return base

    client = client or get_default_client()

    # Compare only the top-k most relevant chunks (O(n^2) guard).
    ranked = sorted(chunks, key=lambda c: float(c.get("adjusted_score") or 0), reverse=True)
    candidates = ranked[: max(0, top_k)]

    suppressed_ids: set = set()
    conflicts_detected = 0
    conflicts_resolved = 0
    escalations: List[Dict[str, Any]] = []

    def _cid(c: Dict[str, Any]) -> str:
        return str(c.get("chunk_id") or c.get("source_url") or id(c))

    try:
        for i in range(len(candidates)):
            a = candidates[i]
            if _cid(a) in suppressed_ids:
                continue
            if float(a.get("adjusted_score") or 0) < min_score:
                continue
            for j in range(i + 1, len(candidates)):
                b = candidates[j]
                if _cid(b) in suppressed_ids:
                    continue
                if float(b.get("adjusted_score") or 0) < min_score:
                    continue
                if (a.get("source_url") or a.get("source_ref")) == (b.get("source_url") or b.get("source_ref")):
                    continue  # same source can't conflict with itself
                if not _classify_pair(client, a, b):
                    continue
                conflicts_detected += 1
                decision = _resolve(a, b)
                if decision == "a":
                    suppressed_ids.add(_cid(b))
                    conflicts_resolved += 1
                elif decision == "b":
                    suppressed_ids.add(_cid(a))
                    conflicts_resolved += 1
                    break  # a is gone; stop pairing it
                else:  # escalate — keep both
                    escalations.append(
                        {
                            "topic": "conflicting_official_sources",
                            "source_urls": sorted(
                                {str(a.get("source_url") or ""), str(b.get("source_url") or "")}
                            ),
                        }
                    )
    except Exception as e:  # noqa: BLE001 — fail-open is the contract
        log.warning("contradiction detector failed-open (%s); passing all chunks through", e)
        return {**base, "contradiction_check_skipped": True}

    kept: List[Dict[str, Any]] = []
    suppressed: List[Dict[str, Any]] = []
    for c in chunks:
        if _cid(c) in suppressed_ids:
            suppressed.append({**c, "conflict_suppressed": True})
        else:
            kept.append(c)

    return {
        "kept_chunks": kept,
        "suppressed_chunks": suppressed,
        "conflicts_detected": conflicts_detected,
        "conflicts_resolved": conflicts_resolved,
        "escalations": escalations,
        "contradiction_check_skipped": False,
    }
