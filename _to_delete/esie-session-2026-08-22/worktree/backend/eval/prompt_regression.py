"""WS-E — prompt-regression gate (deterministic, offline, hermetic).

Why this exists
---------------
The policy-assistant answer is shaped by a *versioned* system prompt
(``backend/app/services/policy_assistant_rag_engine.py::SYSTEM_PROMPT_VERSION``)
plus any committed prompt templates under ``backend/app/services/**/prompts/``.
When that prompt surface changes there is no cheap, network-free signal that the
change didn't quietly regress answer quality. This gate is that signal: it runs
the already-committed offline eval gates and FAILS if any of them regress.

It does NOT introduce new metrics or fixtures — it composes the three existing
offline, no-network suites so the prompt author gets one verdict:

  1. WS-A offline gate aggregator — :func:`backend.eval.grader.run_all_offline_gates`
     (refusal-correctness + PII-leak fences on the policy assistant).
  2. WS-C HR-policy context-precision — the deterministic lexical retriever in
     :mod:`backend.scripts.eval_hr_policy_context_precision` over the committed
     ``tests/fixtures/rag_eval/hr_policy`` golden set.
  3. WS-C RAG triad (context-relevance · groundedness · answer-relevance) via the
     **mock** judge in :mod:`backend.eval.run_rag_triad` (no LLM, no network).

All three reuse their own thresholds and fixtures — this module never restates
them, so they stay the single source of truth.

Determinism: every sub-gate is pure-python over committed fixtures with no
network, so the verdict is reproducible in CI without a DB or secrets.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from . import grader, run_rag_triad
from ..scripts import eval_hr_policy_context_precision as hr_ctx

# Mirror the script's own default so the gate and the CLI agree.
CONTEXT_PRECISION_THRESHOLD = 0.5
CONTEXT_PRECISION_K = 5

_REPO_ROOT = Path(__file__).resolve().parents[2]
# The versioned prompt surface this gate guards. Changing any of these is the
# trigger to (re-)run this gate; the file set is surfaced in the report as a
# fingerprint so a reviewer can see *which* prompt version the verdict covers.
_PROMPT_VERSION_FILE = (
    _REPO_ROOT / "backend" / "app" / "services" / "policy_assistant_rag_engine.py"
)
_PROMPT_TEMPLATE_GLOB = "backend/app/services/**/prompts/*.txt"
_VERSION_RE = re.compile(r"""SYSTEM_PROMPT_VERSION\s*=\s*["']([^"']+)["']""")


@dataclass
class SubGate:
    """One composed offline gate's normalised result."""

    name: str
    passed: bool
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


def prompt_fingerprint() -> Dict[str, Any]:
    """Provenance for the report: the prompt version + a hash of prompt files.

    Read straight off disk (regex, not import) so this stays cheap and never
    pulls the heavy rag-engine import chain. Informational only — it does not
    affect the pass/fail verdict.
    """
    version = "unknown"
    try:
        text = _PROMPT_VERSION_FILE.read_text(encoding="utf-8")
        m = _VERSION_RE.search(text)
        if m:
            version = m.group(1)
    except OSError:
        pass

    h = hashlib.sha256()
    files: List[str] = []
    if _PROMPT_VERSION_FILE.exists():
        h.update(_PROMPT_VERSION_FILE.read_bytes())
        files.append(str(_PROMPT_VERSION_FILE.relative_to(_REPO_ROOT)))
    for tmpl in sorted(_REPO_ROOT.glob(_PROMPT_TEMPLATE_GLOB)):
        h.update(tmpl.read_bytes())
        files.append(str(tmpl.relative_to(_REPO_ROOT)))

    return {
        "system_prompt_version": version,
        "files": files,
        "sha256": h.hexdigest(),
    }


# ── Composed sub-gates ────────────────────────────────────────────────────────


def _offline_gates() -> SubGate:
    """WS-A refusal + PII offline gates (single combined verdict)."""
    report = grader.run_all_offline_gates()
    return SubGate(
        name="offline_gates",
        passed=bool(report["all_passed"]),
        detail={
            "n_gates": report["n_gates"],
            "n_failed": report["n_failed"],
            "gates": [
                {"name": g["name"], "passed": g["passed"]} for g in report["gates"]
            ],
        },
    )


def _hr_policy_context_precision(threshold: float) -> SubGate:
    """WS-C HR-policy context-precision over the committed golden set."""
    queries = hr_ctx.load_queries(hr_ctx._DEFAULT_QUERIES)
    chunks = hr_ctx._load_chunks(hr_ctx._DEFAULT_CHUNKS)
    retriever = hr_ctx.LexicalPolicyRetriever(chunks)
    results = hr_ctx.evaluate(queries, retriever, k=CONTEXT_PRECISION_K)
    report = hr_ctx.aggregate_report(
        results,
        metric_name="precision_at_k",
        threshold=threshold,
        extra={"k": CONTEXT_PRECISION_K},
    )
    return SubGate(
        name="hr_policy_context_precision",
        passed=bool(report["passes_threshold"]),
        detail={
            "aggregate": report["aggregate"],
            "threshold": report["threshold"],
            "queries_evaluated": report["queries_evaluated"],
        },
    )


def _rag_triad() -> SubGate:
    """WS-C RAG triad with the offline mock judge (never the LLM judge)."""
    report = run_rag_triad.run_eval(run_rag_triad.DEFAULT_FIXTURES, judge_name="mock")
    return SubGate(
        name="rag_triad",
        passed=bool(report["gate_pass"]),
        detail={
            "judge": report["judge"],
            "n_cases": report["n_cases"],
            "aggregates": report["aggregates"],
            "thresholds": report["thresholds"],
            "per_metric_pass": report["per_metric_pass"],
        },
    )


def run_prompt_regression(
    *, context_precision_threshold: float = CONTEXT_PRECISION_THRESHOLD
) -> Dict[str, Any]:
    """Run every composed offline gate and return one combined verdict.

    ``context_precision_threshold`` is injectable purely so the test-suite can
    prove the gate *catches* a regression (an impossibly-high threshold forces a
    fail) — production callers should leave it at the default.
    """
    gates = [
        _offline_gates(),
        _hr_policy_context_precision(context_precision_threshold),
        _rag_triad(),
    ]
    return {
        "all_passed": all(g.passed for g in gates),
        "n_gates": len(gates),
        "n_failed": sum(1 for g in gates if not g.passed),
        "prompt_fingerprint": prompt_fingerprint(),
        "gates": [g.to_dict() for g in gates],
    }
