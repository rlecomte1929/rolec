"""
AI Trace Logger — structured per-request trace collection for the Policy Assistant pipeline.

Every call to answer_policy_question() wraps a TraceSession context manager.
Each pipeline step is recorded with its latency and relevant payload.

Storage layers (all best-effort — never fails the main request):
  Primary:  policy_assistant_traces table (SQLite dev / Postgres prod)
  Optional: LangSmith project (set LANGSMITH_API_KEY + LANGSMITH_PROJECT)
  Always:   structured JSON log line via Python logging (searchable in prod)

PII policy:
  Raw query text is NEVER stored in traces.
  query_hash = first 16 hex chars of SHA-256(query) — deduplication only.
  session_id is an opaque UUID — no user identifiers.
  company_id is stored (needed to scope dashboard views by tenant).

Unit economics (Parker Step G):
  Each trace carries a feature_key (required) + customer_id attribution and, on flush,
  an estimated CO2e value + USD cost + token totals summed across its llm_call steps.
  These feed the mv_ai_unit_economics rollup (cost/carbon per customer per feature).

Usage (in policy_assistant_rag_engine.py):
    tracer = TraceSession(session_id=session_id, query=question, company_id=company_id,
                          feature_key="policy_assistant")
    # ... run step ...
    tracer.record_retrieval(top_scores=[0.87, 0.82, ...], latency_ms=210)
    tracer.record_llm_call(model="claude-sonnet-4-6", input_tokens=2100,
                           output_tokens=340, latency_ms=1800)
    tracer.record_step("validation", latency_ms=12, passed=True)
    tracer.flush()
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Step data model                                                              #
# --------------------------------------------------------------------------- #


@dataclass
class TraceStep:
    """One timed step inside a PolicyAssistant trace."""

    step: str
    latency_ms: int = 0
    payload: Dict[str, Any] = field(default_factory=dict)
    # Internal: wall-clock start for the start_step() helper pattern.
    _started_at: float = field(default_factory=time.time, repr=False, compare=False)

    def finish(self, **payload: Any) -> None:
        """Stop the timer and attach arbitrary key/value payload."""
        self.latency_ms = int((time.time() - self._started_at) * 1000)
        self.payload.update(payload)

    def to_dict(self) -> Dict[str, Any]:
        return {"step": self.step, "latency_ms": self.latency_ms, **self.payload}


# --------------------------------------------------------------------------- #
# Trace session                                                                #
# --------------------------------------------------------------------------- #


class TraceSession:
    """
    Collect trace data for one answer_policy_question() invocation.

    Designed to be created at the top of the function, populated during
    execution, and flushed at the end (or in a finally block).
    """

    def __init__(
        self,
        session_id: Optional[str],
        query: str,
        company_id: str,
        # Combined Parker D + G params. feature_key (Step G) is required, so it must
        # stay ahead of every defaulted param (Python forbids a non-default arg after a
        # default). customer_id (G) and prompt_version_id/canary_arm (D) are optional.
        feature_key: str,
        customer_id: Optional[str] = None,
        prompt_version_id: Optional[str] = None,
        canary_arm: Optional[str] = None,
    ) -> None:
        self.trace_id: str = str(uuid.uuid4())
        self.session_id: Optional[str] = session_id
        # Hash the query so the raw user text never appears in traces.
        self.query_hash: str = hashlib.sha256(query.encode("utf-8", errors="replace")).hexdigest()[:16]
        self.company_id: str = company_id
        self._steps: List[TraceStep] = []
        self._started_at: float = time.time()
        self.fallback_triggered: bool = False
        # Unit-economics attribution (Parker Step G) — feature_key is the master cost/
        # carbon dimension and is required (no bare TraceSession()). customer_id defaults
        # to company_id when the caller doesn't distinguish the two.
        self.feature_key: str = feature_key
        self.customer_id: Optional[str] = customer_id if customer_id is not None else company_id
        # Prompt attribution (Parker Step D) — which registry version/arm served
        # this request. Both None when the registry is absent (literal fallback).
        self.prompt_version_id: Optional[str] = prompt_version_id
        self.canary_arm: Optional[str] = canary_arm
        # W3/AIQ-837: chunk ids cited in the final answer. Persisted on the trace
        # so feedback (ai_human_feedback.trace_session_id -> traces.id) can be
        # joined back to the chunks that produced the answer.
        self.cited_chunk_ids: List[str] = []

    def set_prompt_attribution(
        self, prompt_version_id: Optional[str], canary_arm: Optional[str]
    ) -> None:
        """Record which prompt version/arm served this request (Parker Step D)."""
        self.prompt_version_id = prompt_version_id
        self.canary_arm = canary_arm

    def record_citations(self, chunk_ids: Optional[List[str]]) -> None:
        """Record the chunk ids cited in the final answer (W3/AIQ-837)."""
        self.cited_chunk_ids = [str(c) for c in (chunk_ids or [])]

    # ── Recording helpers ── #

    def start_step(self, name: str) -> TraceStep:
        """
        Create a step and start its timer. Caller must call step.finish()
        when the step completes.

            step = tracer.start_step("classifier")
            ...do work...
            step.finish(decision="hr_policy", latency_ms=45)
        """
        step = TraceStep(step=name)
        self._steps.append(step)
        return step

    def record_retrieval(self, top_scores: List[float], latency_ms: int) -> None:
        """Record retrieval result (top-5 similarity scores, no text)."""
        step = TraceStep(step="retrieval", latency_ms=latency_ms)
        step.payload = {"top_5_scores": [round(s, 4) for s in top_scores[:5]]}
        self._steps.append(step)

    def record_llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
    ) -> None:
        """Record an LLM call (model, token counts, latency — no text)."""
        step = TraceStep(step="llm_call", latency_ms=latency_ms)
        step.payload = {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        self._steps.append(step)

    def record_step(self, name: str, latency_ms: int, **payload: Any) -> None:
        """Generic step recorder for classifier, guardrails, validation, etc."""
        step = TraceStep(step=name, latency_ms=latency_ms)
        step.payload = {k: v for k, v in payload.items()}
        self._steps.append(step)

    def mark_fallback(self, reason: str = "") -> None:
        """Flag that the pipeline fell back to the canonical refusal."""
        self.fallback_triggered = True
        if reason:
            self.record_step("fallback", latency_ms=0, reason=reason)

    # ── Flush ── #

    def flush(self) -> None:
        """
        Finalize the trace and push to all configured sinks.
        Call this in a finally block so it always runs, even on exception.
        This method never raises.
        """
        try:
            total_ms = int((time.time() - self._started_at) * 1000)
            econ = self._compute_unit_economics()
            payload: Dict[str, Any] = {
                "trace_id": self.trace_id,
                "session_id": self.session_id,
                "query_hash": self.query_hash,
                "steps": [s.to_dict() for s in self._steps],
                "total_latency_ms": total_ms,
                "fallback_triggered": self.fallback_triggered,
                "feature_key": self.feature_key,
                "customer_id": self.customer_id,
                "prompt_version_id": self.prompt_version_id,
                "canary_arm": self.canary_arm,
                "cited_chunk_ids": self.cited_chunk_ids,
                **self._hoist_provenance(),
                **econ,
            }
            # 1. Structured JSON log — always on, zero extra deps.
            log.info("ai_trace %s", json.dumps(payload, separators=(",", ":")))
            # 2. DB write — best-effort, never fails the caller.
            _write_to_db(payload, self.company_id)
            # 3. LangSmith — opt-in via env var.
            _forward_to_langsmith(payload)
        except Exception:
            log.debug("ai_trace flush failed", exc_info=True)

    # W2-5 provenance keys promoted from step payloads onto the trace row so an
    # HR rollup can query them without JSON-walking steps_json. Both answer
    # pipelines record these into steps (policy: answer_provenance +
    # grounding_verification; immigration: grounding_verification), so a single
    # hoist here covers both surfaces.
    _PROVENANCE_KEYS = (
        "answer_kind",
        "grounding_verdict",
        "verification_skipped",
        "grounding_score",
    )

    def _hoist_provenance(self) -> Dict[str, Any]:
        """Pull provenance signals out of the recorded steps into top-level keys.

        Last writer wins if two steps carry the same key. Any key never recorded
        stays absent → the column is left NULL. Best-effort: never raises.
        """
        hoisted: Dict[str, Any] = {}
        try:
            for step in self._steps:
                for k in self._PROVENANCE_KEYS:
                    if k in step.payload and step.payload[k] is not None:
                        hoisted[k] = step.payload[k]
        except Exception:
            log.debug("ai_trace provenance hoist failed", exc_info=True)
        return hoisted

    def _compute_unit_economics(self) -> Dict[str, Any]:
        """Sum tokens, USD cost and estimated CO2e across this trace's llm_call steps.

        Carbon comes from ai_carbon_estimator (always available — falls back to in-code
        defaults); cost comes from the router's costs.yaml (0.0 for models absent there).
        Best-effort: any failure yields zeros so flush never breaks.
        """
        tokens_in = tokens_out = 0
        cost_usd = 0.0
        co2e_grams = 0.0
        try:
            from .ai_carbon_estimator import estimate_co2e_grams

            for step in self._steps:
                if step.step != "llm_call":
                    continue
                model = step.payload.get("model")
                t_in = int(step.payload.get("input_tokens", 0) or 0)
                t_out = int(step.payload.get("output_tokens", 0) or 0)
                tokens_in += t_in
                tokens_out += t_out
                if not model:
                    continue
                co2e_grams += estimate_co2e_grams(model, t_in, t_out)
                cost_usd += _safe_usd_cost(model, t_in, t_out)
        except Exception:
            log.debug("ai_trace unit-economics calc failed", exc_info=True)
        return {
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd_estimated": round(cost_usd, 6),
            "co2e_grams_estimated": round(co2e_grams, 6),
        }


# --------------------------------------------------------------------------- #
# DB write                                                                     #
# --------------------------------------------------------------------------- #


def _safe_usd_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """USD cost via the router's costs.yaml; 0.0 for models with no pricing entry."""
    try:
        from ...relopass.llm.router import usd_cost

        return float(usd_cost(model, tokens_in, tokens_out))
    except Exception:
        log.debug("ai_trace usd_cost lookup failed for %s", model, exc_info=True)
        return 0.0


def _write_to_db(payload: Dict[str, Any], company_id: str) -> None:
    """Write trace row to policy_assistant_traces. No-op if table absent."""
    try:
        from ...database import db  # avoid circular at module level

        if hasattr(db, "insert_policy_assistant_trace"):
            db.insert_policy_assistant_trace(
                trace_id=payload["trace_id"],
                session_id=payload.get("session_id"),
                query_hash=payload["query_hash"],
                company_id=company_id,
                steps_json=json.dumps(payload["steps"], separators=(",", ":")),
                total_latency_ms=payload["total_latency_ms"],
                fallback_triggered=bool(payload["fallback_triggered"]),
                feature_key=payload.get("feature_key"),
                customer_id=payload.get("customer_id"),
                tokens_in=payload.get("tokens_in"),
                tokens_out=payload.get("tokens_out"),
                cost_usd_estimated=payload.get("cost_usd_estimated"),
                co2e_grams_estimated=payload.get("co2e_grams_estimated"),
                prompt_version_id=payload.get("prompt_version_id"),
                canary_arm=payload.get("canary_arm"),
                cited_chunk_ids=payload.get("cited_chunk_ids"),
                answer_kind=payload.get("answer_kind"),
                grounding_verdict=payload.get("grounding_verdict"),
                verification_skipped=payload.get("verification_skipped"),
                grounding_score=payload.get("grounding_score"),
            )
    except Exception:
        log.debug("ai_trace db write failed", exc_info=True)


# --------------------------------------------------------------------------- #
# LangSmith forward                                                            #
# --------------------------------------------------------------------------- #


def _forward_to_langsmith(payload: Dict[str, Any]) -> None:
    """
    Push the trace to LangSmith when LANGSMITH_API_KEY is set.

    Uses the langsmith Python SDK directly (no LangChain required).
    Silently skips if the SDK is not installed or the key is absent.
    """
    api_key = os.getenv("LANGSMITH_API_KEY", "").strip()
    project = os.getenv("LANGSMITH_PROJECT", "relopass-policy-assistant").strip()
    if not api_key:
        return

    try:
        from langsmith import Client  # type: ignore
        from datetime import datetime, timezone

        client = Client(api_key=api_key)
        now = datetime.now(timezone.utc)

        # LangSmith run IDs must be valid UUIDs.
        parent_run_id = uuid.UUID(payload["trace_id"])

        # Parent run — represents the full assistant session.
        client.create_run(
            id=parent_run_id,
            name="policy_assistant_session",
            run_type="chain",
            project_name=project,
            inputs={"query_hash": payload["query_hash"]},
            outputs={
                "fallback_triggered": payload["fallback_triggered"],
                "total_latency_ms": payload["total_latency_ms"],
            },
            start_time=now,
            end_time=now,
            extra={
                "metadata": {
                    "session_id": payload.get("session_id"),
                }
            },
        )

        # Child runs — one per pipeline step.
        for step in payload.get("steps", []):
            child_id = uuid.uuid4()
            client.create_run(
                id=child_id,
                name=step["step"],
                run_type="tool",
                project_name=project,
                parent_run_id=parent_run_id,
                inputs={},
                outputs={k: v for k, v in step.items() if k != "step"},
                start_time=now,
                end_time=now,
            )

    except ImportError:
        log.debug("langsmith package not installed; skipping LangSmith forwarding")
    except Exception:
        log.debug("langsmith forward failed", exc_info=True)
