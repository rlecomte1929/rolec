"""Error analysis over the offline eval gates.

The eval-foundations literature (Hamel & Shankar, Eugene Yan) puts *error
analysis* before any new metric work: review the failures, group them, and let
the shape of the failures tell you what to build next. The repo had per-runner
pass/fail gates but no tool that aggregates *why* things fail across modules.

This module turns the combined report from
:func:`backend.eval.grader.run_all_offline_gates` into:

  * a per-gate status table (module, headline metric, pass/fail),
  * a confusion matrix per gate (expected class x actual class counts), which is
    the "first-failure transition" view in its simplest form, and
  * a flat list of failing cases grouped by failure type + category.

It is deterministic and offline. ``render_markdown`` produces a committable
``audit/eval/error_analysis_<date>.md``; ``build_error_analysis`` returns the
same content as JSON for programmatic use / tests.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List, Tuple


def _confusion(cases: List[Dict[str, object]]) -> Dict[str, Dict[str, int]]:
    """Counts of (expected -> actual) over a gate's per-case rows.

    Returns a nested dict ``{expected: {actual: count}}``. Empty when the gate
    exposes no per-case detail.
    """
    matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for c in cases:
        expected = str(c.get("expected", "?"))
        actual = str(c.get("actual", "?"))
        matrix[expected][actual] += 1
    # Freeze nested defaultdicts into plain dicts for clean JSON.
    return {k: dict(v) for k, v in matrix.items()}


def _failures_by_category(cases: List[Dict[str, object]]) -> Dict[str, int]:
    """Count of failing cases per category (the 'where does it hurt' view)."""
    counter: Counter = Counter()
    for c in cases:
        if not c.get("passed", True):
            counter[str(c.get("category", "unknown"))] += 1
    return dict(counter)


def build_error_analysis(combined: Dict[str, object]) -> Dict[str, object]:
    """Build a structured error-analysis report from a combined gate report."""
    gates_out: List[Dict[str, object]] = []
    total_failing_cases = 0

    for gate in combined.get("gates", []):  # type: ignore[union-attr]
        cases: List[Dict[str, object]] = list(gate.get("cases", []))  # type: ignore[arg-type]
        failing_ids: List[str] = []
        for ftype, ids in (gate.get("failing") or {}).items():  # type: ignore[union-attr]
            failing_ids.extend(ids)
        total_failing_cases += len(failing_ids)

        gates_out.append(
            {
                "name": gate.get("name"),
                "module": gate.get("module"),
                "passed": gate.get("passed"),
                "headline": gate.get("headline", {}),
                "failing_by_type": {
                    k: list(v) for k, v in (gate.get("failing") or {}).items()
                },
                "failures_by_category": _failures_by_category(cases),
                "confusion": _confusion(cases),
                "n_cases": len(cases),
            }
        )

    by_module: Dict[str, Dict[str, int]] = defaultdict(lambda: {"passed": 0, "failed": 0})
    for g in gates_out:
        bucket = by_module[str(g["module"])]
        bucket["passed" if g["passed"] else "failed"] += 1

    return {
        "all_passed": combined.get("all_passed"),
        "n_gates": combined.get("n_gates"),
        "n_failed": combined.get("n_failed"),
        "total_failing_cases": total_failing_cases,
        "by_module": {k: dict(v) for k, v in by_module.items()},
        "gates": gates_out,
    }


def _confusion_lines(confusion: Dict[str, Dict[str, int]]) -> List[str]:
    if not confusion:
        return ["  _(no per-case detail)_"]
    actual_labels: List[str] = sorted(
        {a for row in confusion.values() for a in row}
    )
    header = "  | expected \\ actual | " + " | ".join(actual_labels) + " |"
    sep = "  |" + "---|" * (len(actual_labels) + 1)
    lines = [header, sep]
    for expected in sorted(confusion):
        row = confusion[expected]
        cells = " | ".join(str(row.get(a, 0)) for a in actual_labels)
        lines.append(f"  | {expected} | {cells} |")
    return lines


def render_markdown(analysis: Dict[str, object], generated_at: str) -> str:
    """Render the error-analysis report as committable markdown."""
    status = "✅ all gates green" if analysis.get("all_passed") else "❌ failures present"
    lines: List[str] = [
        "# AI eval — error analysis",
        "",
        f"_Generated: {generated_at}_  ·  **{status}**",
        "",
        f"Gates: {analysis.get('n_gates')}  ·  "
        f"failed: {analysis.get('n_failed')}  ·  "
        f"failing cases: {analysis.get('total_failing_cases')}",
        "",
        "## By module",
        "",
        "| module | passed | failed |",
        "|---|---|---|",
    ]
    for module, counts in sorted((analysis.get("by_module") or {}).items()):
        lines.append(f"| {module} | {counts.get('passed', 0)} | {counts.get('failed', 0)} |")

    lines += ["", "## Gates", ""]
    for g in analysis.get("gates", []):  # type: ignore[union-attr]
        verdict = "PASS" if g["passed"] else "FAIL"
        lines.append(f"### `{g['name']}` ({g['module']}) — {verdict}")
        lines.append("")
        if g.get("headline"):
            hl = ", ".join(f"{k}={v}" for k, v in g["headline"].items())
            lines.append(f"- headline: {hl}")
        # Failing cases by type
        any_fail = False
        for ftype, ids in (g.get("failing_by_type") or {}).items():
            if ids:
                any_fail = True
                lines.append(f"- {ftype}: {', '.join(map(str, ids))}")
        if not any_fail:
            lines.append("- no failing cases")
        if g.get("failures_by_category"):
            cats = ", ".join(
                f"{c}={n}" for c, n in sorted(g["failures_by_category"].items())
            )
            lines.append(f"- failures by category: {cats}")
        lines.append("- confusion (expected \\ actual):")
        lines.extend(_confusion_lines(g.get("confusion", {})))
        lines.append("")

    return "\n".join(lines)
