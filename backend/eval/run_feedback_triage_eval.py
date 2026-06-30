"""Feedback-triage classifier accuracy eval — L2 of D-BugRoutine.

Measures deterministic-keyword vs LLM classifier accuracy over a labeled gold
set, producing the metric that justifies (or not) flipping the LLM-triage flag.

Metrics reported
----------------
severity_accuracy   exact match  (low/medium/high/critical)
area_accuracy       exact match  (ui/api/isolation/feature/other)
severity_within_1   |ordinal_gold − ordinal_pred| ≤ 1  (low=0 … critical=3)
area_confusion      per-gold-area confusion counts
mismatched_*_ids    list of failing case ids

CI gate (--ci)
--------------
Gates ONLY the deterministic baseline on ``area_accuracy ≥ CI_AREA_ACCURACY_GATE``.
The LLM number is report-only: the real LLM path needs OPENAI_API_KEY and is
never gated in CI.  Use ``--mock`` to run the LLM classifier offline with a
documented stand-in client (scores poorly by design — it always returns
medium/other regardless of content).

Usage
-----
    python -m backend.eval.run_feedback_triage_eval --classifier deterministic --json
    python -m backend.eval.run_feedback_triage_eval --classifier llm --mock --json
    python -m backend.eval.run_feedback_triage_eval --ci
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Callable, Dict, List, Optional, Tuple

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_REPO_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DEFAULT_FIXTURES = os.path.join(
    _BACKEND_DIR, "tests", "fixtures", "feedback_triage", "cases.jsonl"
)

# CI gate: area_accuracy for the deterministic classifier on the committed gold
# set (measured 2026-06-30: 20/24 = 0.8333).  Hardcoded so any regression is
# caught without re-running the baseline.
CI_AREA_ACCURACY_GATE: float = 0.83

_SEVERITY_ORDINAL: Dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


def _mock_llm_client(**kwargs) -> dict:
    """Stand-in LLM client for offline / CI use.

    Always returns {"severity": "medium", "area": "other"} regardless of
    content.  This is intentionally wrong on most cases — its purpose is to let
    the eval run without a network call or API key so the comparison column is
    populated in CI.  The real LLM numbers require OPENAI_API_KEY.
    """
    return {"severity": "medium", "area": "other"}


def _load_cases(fixtures_path: str) -> List[dict]:
    """Load non-meta lines from a .jsonl fixture file."""
    cases = []
    with open(fixtures_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("_meta"):
                continue
            cases.append(obj)
    return cases


def run_eval(fixtures_path: str, classifier: Callable[[str, Optional[str]], dict]) -> dict:
    """Score a classifier over the gold set.

    Args:
        fixtures_path: Path to the .jsonl gold set.
        classifier:    Callable(text, category) → {"severity": str, "area": str}.

    Returns:
        dict with keys: total, severity_accuracy, area_accuracy,
        severity_within_1, area_confusion, mismatched_severity_ids,
        mismatched_area_ids.
    """
    cases = _load_cases(fixtures_path)
    total = len(cases)
    if total == 0:
        return {
            "total": 0,
            "severity_accuracy": 0.0,
            "area_accuracy": 0.0,
            "severity_within_1": 0.0,
            "area_confusion": {},
            "mismatched_severity_ids": [],
            "mismatched_area_ids": [],
        }

    sev_correct = 0
    area_correct = 0
    sev_within_1 = 0
    area_confusion: Dict[str, Dict[str, int]] = {}
    mismatched_sev: List[str] = []
    mismatched_area: List[str] = []

    for case in cases:
        case_id = case["id"]
        text = case["text"]
        category = case.get("category")
        gold_sev = case["gold_severity"]
        gold_area = case["gold_area"]

        pred = classifier(text, category)
        pred_sev = pred["severity"]
        pred_area = pred["area"]

        # Severity exact match
        if pred_sev == gold_sev:
            sev_correct += 1
        else:
            mismatched_sev.append(case_id)

        # Severity within-1 (ordinal)
        gold_ord = _SEVERITY_ORDINAL.get(gold_sev, 0)
        pred_ord = _SEVERITY_ORDINAL.get(pred_sev, 0)
        if abs(gold_ord - pred_ord) <= 1:
            sev_within_1 += 1

        # Area exact match
        if pred_area == gold_area:
            area_correct += 1
        else:
            mismatched_area.append(case_id)

        # Area confusion matrix
        area_confusion.setdefault(gold_area, {})
        area_confusion[gold_area][pred_area] = (
            area_confusion[gold_area].get(pred_area, 0) + 1
        )

    return {
        "total": total,
        "severity_accuracy": sev_correct / total,
        "area_accuracy": area_correct / total,
        "severity_within_1": sev_within_1 / total,
        "area_confusion": area_confusion,
        "mismatched_severity_ids": mismatched_sev,
        "mismatched_area_ids": mismatched_area,
    }


def _build_classifier(
    name: str, mock: bool
) -> Tuple[Callable[[str, Optional[str]], dict], str]:
    """Return (classifier_fn, label) for the given CLI args."""
    if name == "deterministic":
        from backend.app.services.feedback_triage import classify
        return classify, "deterministic"

    if name == "llm":
        from backend.app.services.feedback_triage import classify_llm

        if mock:
            client = _mock_llm_client
            label = "llm[mock — stand-in; always returns medium/other]"
        else:
            client = None  # uses real complete_sync; needs OPENAI_API_KEY
            label = "llm[live]"

        def _llm_wrapper(text: str, category: Optional[str]) -> dict:
            return classify_llm(text, category, client=client)

        return _llm_wrapper, label

    raise ValueError(f"Unknown classifier: {name!r}")


def _print_human(report: dict, label: str, ci_gate: Optional[float]) -> None:
    lines = [
        "",
        "=== Feedback-Triage Classifier Accuracy Eval (L2 / D-BugRoutine) ===",
        f"Classifier:        {label}",
        f"Fixtures:          {report['fixtures_path']}",
        f"Total cases:       {report['total']}",
        f"Severity accuracy: {report['severity_accuracy']:.4f}  "
        f"({int(report['severity_accuracy'] * report['total'])}/{report['total']})",
        f"Area accuracy:     {report['area_accuracy']:.4f}  "
        f"({int(report['area_accuracy'] * report['total'])}/{report['total']})",
        f"Severity within-1: {report['severity_within_1']:.4f}",
    ]
    if report["mismatched_area_ids"]:
        lines.append(f"Mismatched area ids: {', '.join(report['mismatched_area_ids'])}")
    if report["mismatched_severity_ids"]:
        lines.append(f"Mismatched severity ids: {', '.join(report['mismatched_severity_ids'])}")
    if ci_gate is not None:
        gate_pass = report["area_accuracy"] >= ci_gate
        verdict = "PASS" if gate_pass else "FAIL"
        lines.append(
            f"GATE [{verdict}]: area_accuracy {report['area_accuracy']:.4f} "
            f">= {ci_gate} (deterministic baseline)"
        )
    lines.append("")
    print("\n".join(lines))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Feedback-triage classifier accuracy eval (L2 / D-BugRoutine)."
    )
    parser.add_argument(
        "--fixtures",
        default=DEFAULT_FIXTURES,
        help="Path to the gold-set .jsonl (default: tests/fixtures/feedback_triage/cases.jsonl).",
    )
    parser.add_argument(
        "--classifier",
        choices=["deterministic", "llm"],
        default="deterministic",
        help="Which classifier to evaluate.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help=(
            "For --classifier llm: inject an offline stand-in client that always "
            "returns medium/other instead of calling the real LLM.  Runs without "
            "OPENAI_API_KEY; scores poorly by design — it is a CI stand-in only."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_out",
        help="Emit machine-readable JSON instead of the human summary.",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help=(
            "Gate mode: run the deterministic classifier and exit 1 if "
            f"area_accuracy < {CI_AREA_ACCURACY_GATE} (the committed baseline)."
        ),
    )
    args = parser.parse_args(argv)

    classifier_name = "deterministic" if args.ci else args.classifier
    classifier_fn, label = _build_classifier(classifier_name, mock=args.mock)

    report = run_eval(args.fixtures, classifier_fn)
    report["fixtures_path"] = args.fixtures
    report["classifier"] = label

    ci_gate = CI_AREA_ACCURACY_GATE if (args.ci or args.classifier == "deterministic") else None

    if args.json_out:
        serializable = {k: v for k, v in report.items()}
        if ci_gate is not None:
            serializable["ci_gate"] = ci_gate
            serializable["gate_pass"] = report["area_accuracy"] >= ci_gate
        print(json.dumps(serializable, indent=2))
    else:
        _print_human(report, label, ci_gate)

    if args.ci:
        return 0 if report["area_accuracy"] >= CI_AREA_ACCURACY_GATE else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
