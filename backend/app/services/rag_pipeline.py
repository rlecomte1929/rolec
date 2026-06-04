"""
RAG roadmap pipeline (P1-01d) — the single auditable wiring of the immigration
roadmap pipeline:

    UserProfile + PathClassification
        → immigration_retriever (P1-01a)   corridor/pathway-scoped chunks
        → roadmap_generator     (P1-01b)   schema-strict CaseRoadmap / RULE_NOT_FOUND
        → factual_verifier      (P1-01c)   per-step support check
        → assembled CaseRoadmap with verification verdicts

The whole run is wrapped in a TraceSession so retrieval scores, every LLM call
(model + token counts + latency), and the verification outcome land in the AI
audit trail (parent P1-01 constraint: "all LLM calls logged for audit trail").

RULE_NOT_FOUND short-circuits: when the retriever returns no chunks the
generator refuses without an LLM call and verification is skipped — an uncovered
corridor is a routing signal, not a roadmap.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from . import factual_verifier, immigration_retriever, roadmap_generator
from .ai_trace_logger import TraceSession
from .immigration_retriever import (
    IMMIGRATION_CORPUS_COMPANY_ID,
    PathClassification,
    UserProfile,
    corridor_key,
)
from .policy_assistant_llm_client import LlmClient, get_default_client
from .roadmap_generator import RESULT_OK

log = logging.getLogger(__name__)

_FEATURE_KEY = "rag_roadmap"


def generate_roadmap(
    *,
    profile: UserProfile,
    classification: PathClassification,
    top_k: int = 10,
    client: Optional[LlmClient] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the full retriever → generator → verifier pipeline and return the
    assembled CaseRoadmap. Never raises on a pipeline-internal failure — it
    degrades to RULE_NOT_FOUND so the caller always has something to route on."""
    corridor = classification.corridor or corridor_key(
        profile.origin_country, profile.destination_country
    )
    client = client or get_default_client()
    tracer = TraceSession(
        session_id=None,
        query=corridor,
        company_id=IMMIGRATION_CORPUS_COMPANY_ID,
        feature_key=_FEATURE_KEY,
    )
    started = time.time()
    try:
        # 1. Retrieve corridor/pathway-scoped chunks.
        t0 = time.time()
        chunks = immigration_retriever.retrieve_for_profile(
            profile=profile, classification=classification, top_k=top_k
        )
        tracer.record_retrieval(
            [float(c.get("score") or 0.0) for c in chunks],
            int((time.time() - t0) * 1000),
        )

        # 2. Generate (short-circuits to RULE_NOT_FOUND on empty context).
        t0 = time.time()
        gen = roadmap_generator.generate(
            profile=profile, classification=classification, chunks=chunks,
            client=client, model=model,
        )
        if gen.called_llm:
            tracer.record_llm_call(
                model=gen.model,
                input_tokens=int(gen.usage.get("input_tokens") or 0),
                output_tokens=int(gen.usage.get("output_tokens") or 0),
                latency_ms=int((time.time() - t0) * 1000),
            )
        roadmap = gen.roadmap

        # 3. Verify every generated step against the retrieved chunks. Skipped
        # for a refusal (no steps to verify).
        steps: List[Dict[str, Any]] = roadmap.get("steps") or []
        if roadmap.get("result") == RESULT_OK and steps:
            t0 = time.time()
            verification = factual_verifier.verify_roadmap(
                steps=steps, chunks=chunks, client=client, model=model
            )
            tracer.record_step(
                "verification",
                latency_ms=int((time.time() - t0) * 1000),
                steps=len(steps),
                approved=verification.approved,
                unsupported=len(verification.unsupported),
            )
            verdicts = verification.verdicts
            approved = verification.approved
        else:
            verdicts = []
            approved = False
            if roadmap.get("result") != RESULT_OK:
                tracer.mark_fallback(roadmap.get("refusal_reason") or "rule_not_found")

        return _assemble(roadmap, verdicts, approved, len(chunks),
                         int((time.time() - started) * 1000))
    finally:
        tracer.flush()


def _assemble(
    roadmap: Dict[str, Any],
    verdicts: List[factual_verifier.StepVerdict],
    approved: bool,
    chunk_count: int,
    latency_ms: int,
) -> Dict[str, Any]:
    """Merge each step with its verification verdict and stamp pipeline-level
    metadata onto the CaseRoadmap."""
    by_order = {v.order: v for v in verdicts}
    enriched_steps = []
    for step in roadmap.get("steps") or []:
        v = by_order.get(step.get("order"))
        enriched_steps.append({
            **step,
            "verification": {
                "supported": v.supported if v else False,
                "citation_ok": v.citation_ok if v else False,
                "evidence_chunk_ids": v.evidence_chunk_ids if v else [],
            },
        })
    return {
        "result": roadmap.get("result"),
        "corridor": roadmap.get("corridor"),
        "pathway_type": roadmap.get("pathway_type"),
        "refusal_reason": roadmap.get("refusal_reason"),
        "summary": roadmap.get("summary"),
        "approved": approved,
        "steps": enriched_steps,
        "retrieved_chunk_count": chunk_count,
        "latency_ms": latency_ms,
    }
