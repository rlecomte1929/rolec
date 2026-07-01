"""T5 — Setup & Help Assistant eval.

Measures three properties of the engine output across a golden set:

  grounding        — every returned route is in all_routes() AND every cited
                     topic is in topic_ids(); zero hallucinated references.
                     Hard CI gate: must be 1.0.

  refusal_correct  — out-of-scope questions are deflected with no actionable
                     next_step.route and a "contact support" answer.
                     Hard CI gate: must be 1.0.

  next_step_accuracy — the returned route matches the golden expected route.
                       Report-only in v1 (the mock is a stand-in; real LLM
                       accuracy needs ``--live``).

The KEY invariant: grounding is ALWAYS 1.0 on the engine output, even when the
mock returns hallucinated routes/topics, because the engine's guardrail filters
them before they reach the caller.  The hallucinated-route unit test in
tests/eval/test_setup_help_eval.py proves this guardrail is active.

Usage
-----
    cd <repo-root>
    python -m backend.eval.run_setup_help_eval --mock
    python -m backend.eval.run_setup_help_eval --mock --json
    python -m backend.eval.run_setup_help_eval --mock --ci   # exits 1 on gate fail
    python -m backend.eval.run_setup_help_eval --mock --fixtures /path/to/cases.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Allow invocation as ``python -m backend.eval.run_setup_help_eval`` from repo root.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_REPO_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.app.services.setup_help.knowledge_base import all_routes, topic_ids
from backend.app.services.setup_help.setup_help_engine import answer_setup_question
from backend.app.services.policy_assistant_llm_client import LlmRequest

DEFAULT_FIXTURES = os.path.join(
    _BACKEND_DIR, "tests", "fixtures", "setup_help", "cases.jsonl"
)

# ── Mock client ───────────────────────────────────────────────────────────────

# Phrase-to-(route, topic) map.  Each phrase is a substring that appears in
# exactly one class of question in the golden set, enabling deterministic,
# unambiguous keyword matching without touching real LLM calls.
_ROUTE_MAP: Dict[str, tuple] = {
    # (phrase_lower, (route_or_None, topic_id_or_None))
    "weather forecast":         (None, None),          # oos trigger
    "performance review":       (None, None),          # oos trigger
    "immigration law":          (None, None),          # oos trigger
    "company profile":          ("/hr/company-profile", "company-profile"),
    "company address":          ("/hr/company-profile", "company-profile"),
    "policy exceptions":        ("/hr/policy-dashboard", "policy-dashboard-exceptions"),
    "out-of-policy":            ("/hr/policy-dashboard", "policy-dashboard-exceptions"),
    "policy dashboard":         ("/hr/policy-dashboard", "policy-dashboard-exceptions"),
    "approve an out-of-policy": ("/hr/policy-dashboard", "policy-dashboard-exceptions"),
    "publish a relocation policy": ("/hr/settings/policy", "policy-draft-publish"),
    "publish it":               ("/hr/settings/policy", "policy-draft-publish"),
    "policy document":          ("/hr/settings/policy", "policy-draft-publish"),
    "roadmap":                  ("/hr/command-center", "roadmap-and-tasks"),
    "employee do after":        (None, "employee-next-steps"),
    "employee to access":       ("/hr/command-center", "invite-employee"),
    "claimed the case":         ("/hr/command-center", "invite-employee"),
    "assign an employee to a case": ("/hr/command-center", "invite-employee"),
    "first relocation case":    ("/hr/command-center", "create-first-case"),
    "risk level":               ("/hr/command-center", "hr-command-center"),
    "kpis are tracked":         ("/hr/command-center", "hr-command-center"),
    "hr portfolio":             ("/hr/command-center", "hr-command-center"),
    "hr command center":        ("/hr/command-center", "hr-command-center"),
}

_OOS_PHRASES = {"weather forecast", "performance review", "immigration law"}

_REFUSAL_TEXT = (
    "I can only help with ReloPass setup topics. "
    "For anything else, please contact ReloPass support."
)


def _extract_question(user_message: str) -> str:
    """Return only the question portion of the user_message block."""
    marker = "## HR Question\n"
    idx = user_message.find(marker)
    return user_message[idx + len(marker):] if idx >= 0 else user_message


class SetupHelpMockClient:
    """Deterministic offline mock for the setup & help eval.

    Scans the question for known phrase signatures (longest match wins) and
    returns a valid structured response.  All returned routes and topic ids
    are real KB values, so grounding is 1.0 on the mock path before the
    engine's own guardrail even runs.  Out-of-scope phrases return the
    canonical refusal text with next_step=null.
    """

    name = "mock"

    def complete(self, req: LlmRequest) -> Dict[str, Any]:
        q = _extract_question(req.user_message).lower()

        # Longest-match across all phrases so specific multi-word phrases
        # beat shorter single-word ones.
        best_phrase: Optional[str] = None
        best_len = -1
        for phrase in _ROUTE_MAP:
            if phrase in q and len(phrase) > best_len:
                best_phrase = phrase
                best_len = len(phrase)

        if best_phrase is None:
            # No known phrase → generic in-scope fallback.
            return self._make(
                "Please refer to the ReloPass Setup Guide for help with your workspace.",
                None, [],
            )

        route, topic = _ROUTE_MAP[best_phrase]

        if best_phrase in _OOS_PHRASES:
            return self._make(_REFUSAL_TEXT, None, [])

        next_step = {"label": f"Open {topic}", "route": route} if route else None
        cited = [topic] if topic else []
        return self._make(
            f"Follow the Setup Guide steps for {topic}.",
            next_step, cited,
        )

    @staticmethod
    def _make(
        answer: str,
        next_step: Optional[Dict[str, str]],
        cited_topics: List[str],
    ) -> Dict[str, Any]:
        return {
            "text": "",
            "tool_use": {
                "answer": answer,
                "next_step": next_step,
                "cited_topics": cited_topics,
            },
            "model": "mock",
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }


# ── Loader ────────────────────────────────────────────────────────────────────


def load_cases(path: str) -> List[Dict[str, Any]]:
    """Return all case dicts (skips _meta lines) from a JSONL fixture file."""
    cases: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if not obj.get("_meta"):
                cases.append(obj)
    return cases


# ── Scoring ───────────────────────────────────────────────────────────────────


@dataclass
class CaseResult:
    id: str
    grounding_ok: bool
    next_step_ok: bool
    refusal_ok: bool        # True when not a refusal case (N/A)
    is_oos: bool            # True when should_refuse
    returned_route: Optional[str]
    expected_route: Optional[str]
    cited_topics: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)


def _score_one(case: Dict[str, Any], result: Dict[str, Any]) -> CaseResult:
    real_routes = all_routes()
    real_topics = topic_ids()

    ns = result.get("next_step") or {}
    returned_route: Optional[str] = ns.get("route") if isinstance(ns, dict) else None
    cited: List[str] = result.get("cited_topics") or []
    answer: str = result.get("answer") or ""

    expect = case["expect"]
    expected_route: Optional[str] = expect.get("next_step_route")
    should_refuse: bool = bool(expect.get("should_refuse", False))

    failures: List[str] = []

    # Grounding: engine output must contain only real routes and topics.
    no_bad_route = returned_route is None or returned_route in real_routes
    no_bad_topics = all(t in real_topics for t in cited)
    grounding_ok = no_bad_route and no_bad_topics
    if not no_bad_route:
        failures.append(f"hallucinated_route:{returned_route}")
    for t in cited:
        if t not in real_topics:
            failures.append(f"hallucinated_topic:{t}")

    # Next-step accuracy (report-only).
    next_step_ok = returned_route == expected_route
    if not next_step_ok:
        failures.append(
            f"wrong_route:got={returned_route!r} expected={expected_route!r}"
        )

    # Refusal correctness.
    if should_refuse:
        al = answer.lower()
        has_deflection = any(w in al for w in ("only help", "contact", "support"))
        refusal_ok = returned_route is None and has_deflection
        if not refusal_ok:
            failures.append(
                f"refusal_miss:route={returned_route!r} deflection={has_deflection}"
            )
    else:
        refusal_ok = True

    return CaseResult(
        id=case["id"],
        grounding_ok=grounding_ok,
        next_step_ok=next_step_ok,
        refusal_ok=refusal_ok,
        is_oos=should_refuse,
        returned_route=returned_route,
        expected_route=expected_route,
        cited_topics=cited,
        failures=failures,
    )


def run_eval(cases: List[Dict[str, Any]], client: Any) -> Dict[str, Any]:
    """Score all cases.  Returns a metrics dict with grounding, refusal_correct,
    next_step_accuracy and per-case details.

    Args:
        cases:  List of case dicts (already stripped of _meta lines).
        client: An LlmClient (real or mock) injected for offline/live runs.
    """
    results: List[CaseResult] = []
    for case in cases:
        if case.get("_meta"):
            continue
        try:
            result = answer_setup_question(
                question=case["question"],
                setup_status=case["setup_state"],
                client=client,
            )
        except Exception as exc:
            # Treat engine crashes as grounding failures.
            result = {
                "answer": f"ERROR: {exc}",
                "next_step": None,
                "cited_topics": [],
                "model": "error",
                "usage": {},
                "error": True,
            }
        results.append(_score_one(case, result))

    n = len(results)
    oos = [r for r in results if r.is_oos]
    n_oos = len(oos)

    grounding = sum(r.grounding_ok for r in results) / n if n else 0.0
    next_step_accuracy = sum(r.next_step_ok for r in results) / n if n else 0.0
    refusal_correct = sum(r.refusal_ok for r in oos) / n_oos if n_oos else 1.0

    return {
        "n_cases": n,
        "n_out_of_scope": n_oos,
        "grounding": round(grounding, 4),
        "next_step_accuracy": round(next_step_accuracy, 4),
        "refusal_correct": round(refusal_correct, 4),
        "ci_gate_pass": grounding == 1.0 and refusal_correct == 1.0,
        "details": [
            {
                "id": r.id,
                "grounding_ok": r.grounding_ok,
                "next_step_ok": r.next_step_ok,
                "refusal_ok": r.refusal_ok,
                "returned_route": r.returned_route,
                "expected_route": r.expected_route,
                "failures": r.failures,
            }
            for r in results
        ],
    }


# ── CLI ───────────────────────────────────────────────────────────────────────


def _print_human(report: Dict[str, Any], fixtures_path: str) -> None:
    ok = "✓"
    fail = "✗"

    def _badge(v: float, gate: bool = False) -> str:
        symbol = ok if v == 1.0 else fail
        gated = " [GATE]" if gate else ""
        return f"{v:.4f} {symbol}{gated}"

    lines = [
        "",
        "=== T5 Setup & Help Assistant Eval ===",
        f"Fixtures:          {fixtures_path}",
        f"Cases:             {report['n_cases']}  (out-of-scope: {report['n_out_of_scope']})",
        f"grounding:         {_badge(report['grounding'], gate=True)}",
        f"refusal_correct:   {_badge(report['refusal_correct'], gate=True)}",
        f"next_step_accuracy:{report['next_step_accuracy']:.4f} (report-only)",
    ]

    bad = [d for d in report["details"] if d["failures"]]
    if bad:
        lines.append(f"Failures ({len(bad)}):")
        for d in bad:
            lines.append(f"  - {d['id']}: {'; '.join(d['failures'])}")

    if report["ci_gate_pass"]:
        lines.append(f"CI gate: PASS {ok}")
    else:
        lines.append(f"CI gate: FAIL {fail}  (grounding=1.0 AND refusal_correct=1.0 required)")

    lines.append("")
    print("\n".join(lines))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="T5 Setup & Help Assistant grounding + refusal eval."
    )
    parser.add_argument(
        "--fixtures",
        default=DEFAULT_FIXTURES,
        help="Path to the JSONL golden set (default: tests/fixtures/setup_help/cases.jsonl).",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use the deterministic offline mock client (required for CI).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="emit_json",
        help="Emit JSON report instead of human summary.",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Exit 1 if grounding < 1.0 OR refusal_correct < 1.0.",
    )
    args = parser.parse_args(argv)

    if not args.mock:
        print(
            "ERROR: --mock is required for offline/CI runs. "
            "Pass --mock to use the deterministic mock client.",
            file=sys.stderr,
        )
        return 2

    client = SetupHelpMockClient()
    cases = load_cases(args.fixtures)
    report = run_eval(cases, client)
    report["fixtures_path"] = args.fixtures
    report["client"] = client.name

    if args.emit_json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report, args.fixtures)

    if args.ci and not report["ci_gate_pass"]:
        if not args.emit_json:
            pass  # already printed the failure above
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
