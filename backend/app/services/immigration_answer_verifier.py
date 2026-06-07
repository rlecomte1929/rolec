"""
N5 / AIQ-844 — self-critique grounding verifier for the immigration answer engine.

A second, cheaper LLM pass (claude-haiku-4-5) that fact-checks the N4 generator's
answer claim-by-claim against the retrieved source chunks. Mirrors the idea of
policy_assistant_rag_engine._validate_answer — but that only checks citation-ID
*existence* (string validation); this checks semantic *grounding* (entailment).

Fail-open contract (Technical Constraint): if the verifier LLM errors, times out,
or returns an unparseable verdict, NEVER block the answer — return
verification_skipped=True and let the original answer through. This function never
raises.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from .policy_assistant_llm_client import (
    FALLBACK_MODEL,
    LlmClient,
    LlmRequest,
    get_default_client,
)

log = logging.getLogger(__name__)

# A cheap/fast model — this is structured classification, not generation.
VERIFIER_MODEL = FALLBACK_MODEL  # claude-haiku-4-5-20251001

VALID_VERDICTS = ("grounded", "partially_grounded", "ungrounded")

# Verbatim per the N5 spec — do not paraphrase.
VERIFIER_SYSTEM_PROMPT = (
    "You are a fact-checker. Given the ANSWER and the SOURCE CHUNKS below, for each "
    "factual claim in the answer, verify it is directly supported by at least one chunk. "
    'Return JSON: {verdict: "grounded"|"partially_grounded"|"ungrounded", '
    "unsupported_claims: [str], grounding_score: float 0-1}"
)

# Grab the outermost {...} block so prose / markdown fences around the JSON don't trip us.
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _build_verifier_message(answer_text: str, chunks: List[Dict[str, Any]]) -> str:
    lines = ["ANSWER:", answer_text.strip(), "", "SOURCE CHUNKS:"]
    for c in chunks:
        url = c.get("source_url") or c.get("source_ref") or "unknown"
        body = (c.get("chunk_text") or "").replace("\n", " ").strip()
        lines.append(f"[{url}] {body}")
    return "\n".join(lines)


def _parse_verdict(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Extract {verdict, unsupported_claims, grounding_score} from the LLM text.
    Returns None if there's no JSON, it doesn't parse, or the verdict is invalid."""
    m = _JSON_RE.search(text or "")
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    verdict = str(data.get("verdict", "")).strip().lower()
    if verdict not in VALID_VERDICTS:
        return None
    try:
        score = float(data.get("grounding_score"))
    except (TypeError, ValueError):
        score = None
    claims = data.get("unsupported_claims") or []
    if not isinstance(claims, list):
        claims = [str(claims)]
    return {
        "verdict": verdict,
        "grounding_score": score,
        "unsupported_claims": [str(x) for x in claims],
    }


def _skipped_result(latency_ms: int = 0) -> Dict[str, Any]:
    """Fail-open verdict: the answer is returned untouched, flagged unverified."""
    return {
        "verdict": None,
        "grounding_score": None,
        "unsupported_claims": [],
        "verification_skipped": True,
        "model": VERIFIER_MODEL,
        "latency_ms": latency_ms,
    }


def verify_grounding(
    answer_text: str,
    chunks: List[Dict[str, Any]],
    *,
    client: Optional[LlmClient] = None,
) -> Dict[str, Any]:
    """
    Fact-check ``answer_text`` against ``chunks`` with one cheap LLM pass.

    Returns: {verdict, grounding_score, unsupported_claims, verification_skipped,
    model, latency_ms}. Fails OPEN (verification_skipped=True, verdict=None) on any
    verifier error/timeout or unparseable output — never raises, never blocks.
    """
    started = time.time()
    # Nothing meaningful to verify against -> skip the call, fail open.
    if not (answer_text or "").strip() or not chunks:
        return _skipped_result()

    client = client or get_default_client()
    try:
        resp = client.complete(
            LlmRequest(
                system=VERIFIER_SYSTEM_PROMPT,
                user_message=_build_verifier_message(answer_text, chunks),
                model=VERIFIER_MODEL,
                max_tokens=400,
            )
        )
    except Exception:
        # LLM error / timeout — fail open per the Technical Constraint.
        log.warning("immigration grounding verifier call failed; failing open", exc_info=True)
        return _skipped_result(int((time.time() - started) * 1000))

    latency_ms = int((time.time() - started) * 1000)
    parsed = _parse_verdict(resp.get("text"))
    if parsed is None:
        log.warning("immigration grounding verifier returned unparseable verdict; failing open")
        return _skipped_result(latency_ms)

    return {
        **parsed,
        "verification_skipped": False,
        "model": resp.get("model") or VERIFIER_MODEL,
        "latency_ms": latency_ms,
    }
