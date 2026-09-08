"""
Factual verifier (P1-01c) — third stage of the immigration roadmap RAG pipeline.

The generator (P1-01b) turns retrieved immigration-rule chunks into a
CaseRoadmap of steps, each claiming a `source_url` / `source_chunk_id`. This
module re-checks every generated step against the *actual* retrieved chunks
with a second Claude pass, so a fabricated or unsupported step never reaches a
caseworker. It is deliberately adversarial: it trusts only the retrieved
context, never the generator's say-so.

For each step it returns a `StepVerdict`:
  - citation_ok        : the step's source_chunk_id is a real retrieved chunk
                         (and the urls match when both are present). Purely
                         deterministic — no LLM needed.
  - evidence_chunk_ids : retrieved chunk ids the verifier found to actually
                         support the step's claim, filtered to real ids only —
                         so the verifier can never invent support from a chunk
                         that was not retrieved.
  - supported          : the LLM judged the step grounded AND at least one real
                         supporting chunk remains after filtering.

`verify_roadmap` aggregates the per-step verdicts into a `RoadmapVerification`;
`approved` is True only when every step is supported. The orchestrator (P1-01d)
rejects the whole roadmap when `approved` is False — a single fabricated
citation discards the roadmap, per the generator's contract.

Reuses the policy_assistant LLM seam (`LlmRequest` + injectable client), so
tests drive a deterministic MockClient with no network / API key. The
orchestrator (P1-01d) owns the full LLM-I/O audit trail; this module logs each
verdict via `log.info` for traceability.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .policy_assistant_llm_client import (
    DEFAULT_MODEL,
    LlmClient,
    LlmRequest,
    get_default_client,
)

log = logging.getLogger(__name__)

# The verifier reads a single step + the retrieved chunks and replies with a
# small JSON verdict. It needs little headroom; keep it tight for latency.
_VERIFY_MAX_TOKENS = 400

SYSTEM_PROMPT = """You are the FACTUAL VERIFIER of the ReloPass immigration roadmap pipeline.

A generator has produced one immigration STEP and claims it is grounded in a set
of RETRIEVED CHUNKS. Your job is to independently check that claim against the
chunks — and ONLY the chunks. You are adversarial: assume the step may be
hallucinated until a chunk proves otherwise.

Rules:
1. A chunk SUPPORTS the step only if its text actually states or directly
   implies what the step instructs. Topical overlap is not support.
2. You may cite ANY retrieved chunk as evidence, not only the one the step
   claimed — but every evidence id you return MUST be the id of a chunk present
   in RETRIEVED CHUNKS. Never invent a chunk id.
3. If no retrieved chunk supports the step, return supported=false and an empty
   evidence_chunk_ids list. A step with no genuine grounding is a failure, even
   if it sounds plausible.
4. Do not use any outside knowledge of immigration law. The chunks are the only
   admissible evidence.

Reply with ONE JSON object and nothing else:
{
  "supported": <true|false>,
  "evidence_chunk_ids": [<chunk ids from RETRIEVED CHUNKS that support the step>],
  "reason": "<one sentence: why supported, or why not>"
}
"""


@dataclass(frozen=True)
class StepVerdict:
    """Per-step verification result. `order`/`title` map the verdict back to
    the generated step for the orchestrator and audit log."""

    order: Optional[int]
    title: str
    supported: bool
    citation_ok: bool
    evidence_chunk_ids: List[str]
    reason: str


@dataclass(frozen=True)
class RoadmapVerification:
    """Aggregate verdict over a whole roadmap's steps."""

    verdicts: List[StepVerdict]

    @property
    def approved(self) -> bool:
        """True only when every step is supported. Vacuously true for an empty
        roadmap (e.g. a RULE_NOT_FOUND refusal, which carries no steps)."""
        return all(v.supported for v in self.verdicts)

    @property
    def unsupported(self) -> List[StepVerdict]:
        return [v for v in self.verdicts if not v.supported]


# Tolerant extractor: pull the first {...} object out of the model's reply,
# whether or not it wrapped it in prose or a code fence.
_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def verify_roadmap(
    *,
    steps: List[Dict[str, Any]],
    chunks: List[Dict[str, Any]],
    client: Optional[LlmClient] = None,
    model: Optional[str] = None,
) -> RoadmapVerification:
    """Verify every step against the retrieved chunks and aggregate the
    verdicts. One LLM call per step (matches "for each generated step")."""
    client = client or get_default_client()
    verdicts = [
        verify_step(step=s, chunks=chunks, client=client, model=model)
        for s in steps
    ]
    return RoadmapVerification(verdicts=verdicts)


def verify_step(
    *,
    step: Dict[str, Any],
    chunks: List[Dict[str, Any]],
    client: Optional[LlmClient] = None,
    model: Optional[str] = None,
) -> StepVerdict:
    """Verify a single generated step against the retrieved chunks."""
    client = client or get_default_client()
    model = model or DEFAULT_MODEL

    index = _chunk_index(chunks)
    title = str(step.get("title") or "")
    order = step.get("order")
    claimed_id = str(step.get("source_chunk_id") or "")
    claimed_url = str(step.get("source_url") or "")

    # 1. Deterministic citation check — the cited chunk must be a real
    # retrieved chunk, and (when both carry a url) the urls must match. This
    # alone catches a fabricated or sourceless citation, no LLM required.
    cited = index.get(claimed_id)
    citation_ok = cited is not None
    if citation_ok and claimed_url:
        chunk_url = str((cited or {}).get("source_url") or (cited or {}).get("source_ref") or "")
        citation_ok = (chunk_url == claimed_url) if chunk_url else True

    # 2. No retrieved evidence at all → nothing can ground the step. Short
    # circuit without spending an LLM call.
    if not index:
        verdict = StepVerdict(
            order=order, title=title, supported=False, citation_ok=False,
            evidence_chunk_ids=[], reason="No retrieved chunks to verify against.",
        )
        log.info("factual_verifier step=%r supported=False (no chunks)", title)
        return verdict

    # 3. Second Claude pass — does any retrieved chunk actually support it?
    req = LlmRequest(
        system=SYSTEM_PROMPT,
        user_message=_build_user_message(step, chunks),
        model=model,
        temperature=0.0,
        max_tokens=_VERIFY_MAX_TOKENS,
    )
    resp = client.complete(req)
    parsed = _parse_verdict_json(resp.get("text") or "")
    if parsed is None:
        log.warning(
            "factual_verifier: unparseable verdict for step=%r; treating as unsupported",
            title,
        )
        return StepVerdict(
            order=order, title=title, supported=False, citation_ok=citation_ok,
            evidence_chunk_ids=[], reason="Verifier returned an unparseable response.",
        )

    # Filter the model's evidence to *real* retrieved chunk ids, de-duplicated.
    # The verifier can never claim support from a chunk that was not retrieved.
    evidence: List[str] = []
    seen = set()
    raw_evidence = parsed.get("evidence_chunk_ids")
    if isinstance(raw_evidence, list):
        for cid in raw_evidence:
            s = str(cid)
            if s in index and s not in seen:
                seen.add(s)
                evidence.append(s)

    llm_supported = bool(parsed.get("supported"))
    supported = llm_supported and len(evidence) > 0
    reason = str(parsed.get("reason") or "").strip() or (
        "Grounded in retrieved chunk(s)."
        if supported
        else "No retrieved chunk supports this step."
    )

    log.info(
        "factual_verifier step=%r supported=%s citation_ok=%s evidence=%s",
        title, supported, citation_ok, evidence,
    )
    return StepVerdict(
        order=order, title=title, supported=supported, citation_ok=citation_ok,
        evidence_chunk_ids=evidence, reason=reason,
    )


# --- Internals -------------------------------------------------------------

def _chunk_index(chunks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Map retrieved chunk id (as str) -> chunk dict."""
    return {str(c.get("id")): c for c in chunks if c.get("id") is not None}


def _format_chunks_for_prompt(chunks: List[Dict[str, Any]]) -> str:
    if not chunks:
        return "(no retrieved chunks)"
    blocks = []
    for c in chunks:
        cid = str(c.get("id"))
        url = c.get("source_url") or c.get("source_ref") or ""
        text = (c.get("chunk_text") or "").strip()
        blocks.append(f"[chunk:{cid}] (source_url: {url})\n{text}")
    return "\n\n".join(blocks)


def _build_user_message(step: Dict[str, Any], chunks: List[Dict[str, Any]]) -> str:
    return (
        "STEP TO VERIFY:\n"
        f"  title: {step.get('title') or ''}\n"
        f"  description: {step.get('description') or ''}\n"
        f"  claimed source_chunk_id: {step.get('source_chunk_id') or ''}\n"
        f"  claimed source_url: {step.get('source_url') or ''}\n\n"
        "RETRIEVED CHUNKS (the only admissible evidence):\n"
        f"{_format_chunks_for_prompt(chunks)}"
    )


def _parse_verdict_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    m = _JSON_OBJ_RE.search(text)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None
