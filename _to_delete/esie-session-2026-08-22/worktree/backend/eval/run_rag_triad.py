"""
WS-C — RAG triad eval (context-relevance · groundedness · answer-relevance).

The "RAG triad" scores three failure surfaces of a retrieval-augmented answer:

  1. context_relevance — are the retrieved chunks relevant to the query?
  2. groundedness      — is the answer supported by the retrieved chunks?
  3. answer_relevance  — does the answer actually address the query?

Two judges
----------
* ``mock`` (default) — a deterministic, no-network lexical judge. Token-overlap
  scoring, so the same fixtures always produce the same numbers. This is what the
  unit tests and the CI gate use — fully offline, hermetic, free (matching the
  convention of run_refusal_eval.py).
* ``claude`` — a real LLM judge backed by
  ``backend.app.services.llm_client.claude_complete`` (structured JSON via tool
  use). Off by default; only used when ``--judge claude`` is passed AND
  ANTHROPIC_API_KEY is set. Never invoked by the tests.

Gate
----
Each metric has its own threshold (overridable in the fixture ``gate`` block).
The process exits non-zero if any metric's aggregate falls below its threshold,
so the suite is directly usable from CI.

Usage
-----
    python -m backend.eval.run_rag_triad
    python -m backend.eval.run_rag_triad --json
    python -m backend.eval.run_rag_triad --fixtures /path/to/triad_cases.json
    python -m backend.eval.run_rag_triad --judge claude   # real LLM, needs key

Add cases to ``tests/fixtures/rag_eval/triad_cases.json``, not this runner.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make ``backend.app...`` importable whether invoked as ``python -m eval.run_rag_triad``
# from inside backend/, or ``python -m backend.eval.run_rag_triad`` from the repo root.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_REPO_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DEFAULT_FIXTURES = os.path.join(
    _BACKEND_DIR, "tests", "fixtures", "rag_eval", "triad_cases.json"
)
METRICS = ("context_relevance", "groundedness", "answer_relevance")
DEFAULT_THRESHOLDS = {m: 0.30 for m in METRICS}

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "is", "are", "for", "of", "to", "and", "or", "in", "on",
    "what", "how", "does", "do", "this", "that", "per", "by", "with", "at",
    "be", "as", "it", "from", "into", "you", "your",
}
# Strip the [chunk:<id>] citation markers before scoring an answer's text — they
# are structure, not content, and would otherwise inflate overlap.
_CITATION_RE = re.compile(r"\[chunk:[^\]]+\]")


def _tokens(text: str) -> set:
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOP}


def _overlap(a: str, b: str) -> float:
    """Jaccard token overlap in [0, 1]. 0 when either side is empty."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _chunks_text(chunks: List[Dict[str, Any]]) -> str:
    return " ".join((c.get("text") or "") for c in chunks)


# ---------------------------------------------------------------------------
# Judges
# ---------------------------------------------------------------------------


def mock_judge(case: Dict[str, Any]) -> Dict[str, float]:
    """Deterministic offline triad scorer (no network).

    context_relevance: mean query↔chunk overlap across retrieved chunks.
    groundedness:      answer↔chunks overlap (is the answer in the sources?).
    answer_relevance:  answer↔query overlap (does the answer address the query?).
    """
    query = case.get("query") or ""
    chunks = case.get("retrieved_chunks") or []
    answer = _CITATION_RE.sub("", case.get("answer") or "")

    if chunks:
        ctx = sum(_overlap(query, c.get("text") or "") for c in chunks) / len(chunks)
    else:
        ctx = 0.0
    grounded = _overlap(answer, _chunks_text(chunks))
    ans_rel = _overlap(answer, query)

    return {
        "context_relevance": round(ctx, 4),
        "groundedness": round(grounded, 4),
        "answer_relevance": round(ans_rel, 4),
    }


_CLAUDE_SCHEMA = {
    "type": "object",
    "properties": {
        "context_relevance": {"type": "number", "minimum": 0, "maximum": 1},
        "groundedness": {"type": "number", "minimum": 0, "maximum": 1},
        "answer_relevance": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": list(METRICS),
    "additionalProperties": False,
}

_CLAUDE_SYSTEM = (
    "You are a strict RAG evaluator. Score three axes from 0 to 1: "
    "context_relevance (are the CHUNKS relevant to the QUERY), "
    "groundedness (is every claim in the ANSWER supported by the CHUNKS), "
    "answer_relevance (does the ANSWER address the QUERY). Return JSON only."
)


def claude_judge(case: Dict[str, Any]) -> Dict[str, float]:
    """Real LLM judge via llm_client.claude_complete (structured tool output).

    Only used with ``--judge claude``; never called by the tests. Requires
    ANTHROPIC_API_KEY (claude_complete raises otherwise).
    """
    import asyncio

    from backend.app.services.llm_client import claude_complete

    user = (
        f"QUERY:\n{case.get('query') or ''}\n\n"
        f"CHUNKS:\n{_chunks_text(case.get('retrieved_chunks') or [])}\n\n"
        f"ANSWER:\n{_CITATION_RE.sub('', case.get('answer') or '')}"
    )
    result = asyncio.run(
        claude_complete(system=_CLAUDE_SYSTEM, user=user, schema=_CLAUDE_SCHEMA)
    )
    out: Dict[str, float] = {}
    for m in METRICS:
        try:
            out[m] = round(max(0.0, min(1.0, float(result.get(m)))), 4)
        except (TypeError, ValueError):
            out[m] = 0.0
    return out


_JUDGES = {"mock": mock_judge, "claude": claude_judge}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


@dataclass
class CaseResult:
    case_id: str
    scores: Dict[str, float]


def _load_fixtures(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def run_eval(fixtures_path: str, judge_name: str = "mock") -> dict:
    fixtures = _load_fixtures(fixtures_path)
    judge = _JUDGES[judge_name]
    thresholds = {**DEFAULT_THRESHOLDS, **(fixtures.get("gate") or {})}

    results: List[CaseResult] = [
        CaseResult(case_id=c["id"], scores=judge(c)) for c in fixtures["cases"]
    ]

    def _mean(metric: str) -> float:
        vals = [r.scores.get(metric, 0.0) for r in results]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    aggregates = {m: _mean(m) for m in METRICS}
    per_metric_pass = {m: aggregates[m] >= float(thresholds[m]) for m in METRICS}
    gate_pass = all(per_metric_pass.values())

    return {
        "fixtures_path": fixtures_path,
        "judge": judge_name,
        "n_cases": len(results),
        "thresholds": {m: float(thresholds[m]) for m in METRICS},
        "aggregates": aggregates,
        "per_metric_pass": per_metric_pass,
        "gate_pass": gate_pass,
        "results": results,
    }


def _print_human(report: dict) -> None:
    lines = [
        "",
        "=== WS-C RAG Triad Eval ({} judge) ===".format(report["judge"]),
        f"Fixtures:  {report['fixtures_path']}",
        f"Cases:     {report['n_cases']}",
        "Metric                aggregate  threshold  pass",
    ]
    for m in METRICS:
        lines.append(
            f"  {m:<18} {report['aggregates'][m]:>9.4f} "
            f"{report['thresholds'][m]:>10.2f}  "
            f"{'OK' if report['per_metric_pass'][m] else 'FAIL'}"
        )
    verdict = "PASS" if report["gate_pass"] else "FAIL"
    lines.append(f"GATE: {verdict}")
    lines.append("")
    print("\n".join(lines))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="WS-C RAG triad eval.")
    parser.add_argument(
        "--fixtures",
        default=DEFAULT_FIXTURES,
        help="Path to the triad fixtures JSON (default: tests/fixtures/rag_eval/triad_cases.json).",
    )
    parser.add_argument(
        "--judge",
        choices=sorted(_JUDGES),
        default="mock",
        help="Scoring judge: 'mock' (offline deterministic, default) or 'claude' (real LLM).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON report instead of the human summary.",
    )
    parser.add_argument(
        "--emit-dashboard",
        action="store_true",
        help="Write one dated dashboard report per triad metric into --out-dir "
        "(off by default so tests/CI never write files).",
    )
    parser.add_argument(
        "--out-dir",
        default=os.path.join(_REPO_ROOT, "audit", "rag_eval"),
        help="Directory for --emit-dashboard report files.",
    )
    args = parser.parse_args(argv)

    report = run_eval(args.fixtures, judge_name=args.judge)

    if args.emit_dashboard:
        from backend.eval.dashboard_report import write_dashboard_report

        payload = {
            "judge": report["judge"],
            "n_cases": report["n_cases"],
            "fixtures_path": report["fixtures_path"],
            "thresholds": report["thresholds"],
            "aggregates": report["aggregates"],
            "per_metric_pass": report["per_metric_pass"],
        }
        out_dir = Path(args.out_dir)
        for m in METRICS:
            dest = write_dashboard_report(out_dir, m, report["aggregates"][m], payload)
            print(f"wrote {dest}", file=sys.stderr)

    if args.json:
        serializable = {k: v for k, v in report.items() if k != "results"}
        serializable["results"] = [
            {"case_id": r.case_id, "scores": r.scores} for r in report["results"]
        ]
        print(json.dumps(serializable, indent=2))
    else:
        _print_human(report)

    return 0 if report["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
