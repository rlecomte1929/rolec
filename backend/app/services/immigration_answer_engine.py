"""
N4 / AIQ-843 — grounded, citation-enforced immigration answer generator.

Takes the staleness-aware retrieval payload (immigration_retriever.
retrieve_with_staleness → {chunks, all_stale_warning, oldest_fetched_at}),
builds a source-cited prompt, calls claude-sonnet-4-6 via the existing
LlmClient abstraction, and returns a structured answer. Mirrors
policy_assistant_rag_engine's guardrail + trace pattern.

Hard guarantees:
  - 0 chunks  -> immediate refusal_insufficient_context, NO LLM call, cost 0.
  - all-stale -> staleness caveat prepended to the system prompt.
  - every answer carries a trace_id (ai_trace_logger).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .ai_trace_logger import TraceSession
from .immigration_retriever import IMMIGRATION_CORPUS_COMPANY_ID
from .policy_assistant_llm_client import (
    LlmClient,
    LlmRequest,
    estimate_cost_usd,
    get_default_client,
)

log = logging.getLogger(__name__)

_FEATURE_KEY = "immigration_answer"
_MODEL = "claude-sonnet-4-6"

# Verbatim per the N4 spec — do not paraphrase.
SYSTEM_PROMPT = """You are an immigration guidance assistant for ReloPass.
You answer questions about work permit and visa requirements ONLY from the provided source documents.
RULES (non-negotiable):

Answer ONLY from the chunks provided in the context. Do not use training knowledge.
Cite every factual claim as [source: <source_url>].
NEVER provide legal advice. NEVER speculate beyond the provided documents.
ALWAYS recommend verifying requirements directly with the relevant immigration authority.
If the context is insufficient to answer, respond EXACTLY: "I cannot confirm the requirements for this corridor from current official sources. Please verify directly with the relevant immigration authority."
If the sources are flagged as potentially outdated, begin your response with: "⚠️ Note: The available sources may be outdated. Please verify the following with the official authority before acting."

Immigration domain scope: you are restricted to visa, work permit, and residency requirements only.
NEVER comment on political, social, or non-immigration topics."""

INSUFFICIENT_CONTEXT_REFUSAL = (
    "I cannot confirm the requirements for this corridor from current official sources. "
    "Please verify directly with the relevant immigration authority."
)
_STALE_CAVEAT_HINT = (
    "\n\nThe provided sources are flagged as potentially outdated — begin your response "
    "with the outdated-sources note specified in the rules."
)
_SOURCE_RE = re.compile(r"\[source:\s*([^\]]+)\]")


def _build_user_message(chunks: List[Dict[str, Any]], query: str, corridor: str) -> str:
    lines = [f"CORRIDOR: {corridor}", "", "SOURCES:"]
    for c in chunks:
        url = c.get("source_url") or c.get("source_ref") or "unknown"
        body = (c.get("chunk_text") or "").replace("\n", " ").strip()
        lines.append(f"[source: {url}] {body}")
    lines += ["", f"QUESTION: {query}"]
    return "\n".join(lines)


def _extract_cited_sources(answer_text: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pull [source: <url>] refs from the answer, dedupe, enrich from the chunks."""
    by_url: Dict[str, Dict[str, Any]] = {}
    for c in chunks:
        url = c.get("source_url") or c.get("source_ref")
        if url and url not in by_url:
            by_url[url] = c
    out: List[Dict[str, Any]] = []
    seen = set()
    for m in _SOURCE_RE.finditer(answer_text or ""):
        url = m.group(1).strip()
        if url in seen:
            continue
        seen.add(url)
        chunk = by_url.get(url, {})
        out.append({
            "source_url": url,
            "trust_tier": chunk.get("trust_tier"),
            "fetched_at": chunk.get("fetched_at"),
        })
    return out


def generate_immigration_answer(
    chunks_payload: Dict[str, Any],
    query: str,
    corridor: str,
    *,
    client: Optional[LlmClient] = None,
) -> Dict[str, Any]:
    """
    Generate a grounded answer from a retrieve_with_staleness() payload.
    Returns: answer_text, answer_kind ('answer' | 'refusal_insufficient_context'
    | 'refusal_stale_sources'), cited_sources, model, corridor, cost_usd,
    generated_at, trace_id.
    """
    chunks = chunks_payload.get("chunks") or []
    all_stale = bool(chunks_payload.get("all_stale_warning"))
    now_iso = datetime.now(timezone.utc).isoformat()

    tracer = TraceSession(
        session_id=None, query=query, company_id=IMMIGRATION_CORPUS_COMPANY_ID, feature_key=_FEATURE_KEY,
    )

    # Hard guard: no context -> refuse without an LLM call.
    if not chunks:
        tracer.mark_fallback("insufficient_context")
        tracer.flush()
        return {
            "answer_text": INSUFFICIENT_CONTEXT_REFUSAL,
            "answer_kind": "refusal_insufficient_context",
            "cited_sources": [],
            "model": None,
            "corridor": corridor,
            "cost_usd": 0.0,
            "generated_at": now_iso,
            "trace_id": tracer.trace_id,
        }

    client = client or get_default_client()
    system = SYSTEM_PROMPT + (_STALE_CAVEAT_HINT if all_stale else "")
    user_message = _build_user_message(chunks, query, corridor)

    resp = client.complete(LlmRequest(system=system, user_message=user_message, model=_MODEL, max_tokens=800))
    answer_text = (resp.get("text") or "").strip()
    usage = resp.get("usage") or {}
    model = resp.get("model") or _MODEL
    cost = estimate_cost_usd(usage, model)
    tracer.record_llm_call(model, int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0)), 0)

    is_refusal = answer_text.startswith("I cannot confirm the requirements for this corridor")
    if is_refusal:
        answer_kind = "refusal_stale_sources" if all_stale else "refusal_insufficient_context"
    else:
        answer_kind = "answer"  # stale answers still answer, with the caveat the model prepends

    cited_sources = _extract_cited_sources(answer_text, chunks)
    tracer.flush()
    return {
        "answer_text": answer_text,
        "answer_kind": answer_kind,
        "cited_sources": cited_sources,
        "model": model,
        "corridor": corridor,
        "cost_usd": cost,
        "generated_at": now_iso,
        "trace_id": tracer.trace_id,
    }
