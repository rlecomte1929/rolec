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

Usage (in policy_assistant_rag_engine.py):
    tracer = TraceSession(session_id=session_id, query=question, company_id=company_id)
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
    ) -> None:
        self.trace_id: str = str(uuid.uuid4())
        self.session_id: Optional[str] = session_id
        # Hash the query so the raw user text never appears in traces.
        self.query_hash: str = hashlib.sha256(query.encode("utf-8", errors="replace")).hexdigest()[:16]
        self.company_id: str = company_id
        self._steps: List[TraceStep] = []
        self._started_at: float = time.time()
        self.fallback_triggered: bool = False

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
            payload: Dict[str, Any] = {
                "trace_id": self.trace_id,
                "session_id": self.session_id,
                "query_hash": self.query_hash,
                "steps": [s.to_dict() for s in self._steps],
                "total_latency_ms": total_ms,
                "fallback_triggered": self.fallback_triggered,
            }
            # 1. Structured JSON log — always on, zero extra deps.
            log.info("ai_trace %s", json.dumps(payload, separators=(",", ":")))
            # 2. DB write — best-effort, never fails the caller.
            _write_to_db(payload, self.company_id)
            # 3. LangSmith — opt-in via env var.
            _forward_to_langsmith(payload)
        except Exception:
            log.debug("ai_trace flush failed", exc_info=True)


# --------------------------------------------------------------------------- #
# DB write                                                                     #
# --------------------------------------------------------------------------- #


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
