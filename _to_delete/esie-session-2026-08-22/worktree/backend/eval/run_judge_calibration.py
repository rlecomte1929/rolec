"""
WS-C — Grounding-judge calibration.

Measures how well the grounding judge (the one that powers
backend.app.services.immigration_answer_verifier.verify_grounding, also used by
the live HR Policy answer path) agrees with a human-labeled gold set of
{answer, chunks, gold_verdict} cases. Reports:

  * agreement   — fraction of cases where judge verdict == gold verdict
  * cohen_kappa — chance-corrected agreement across the 3-class verdict space
                  (grounded / partially_grounded / ungrounded)

Two judges
----------
* ``mock`` (default) — deterministic, no-network. Scores groundedness as the
  coverage of answer tokens by chunk tokens and bands it into a verdict. This is
  what the unit tests use — offline, hermetic, free.
* ``verifier`` — the REAL judge: calls ``verify_grounding`` (one cheap LLM pass).
  Off by default; needs an LLM client / ANTHROPIC_API_KEY. Never used by tests.

Gate
----
This is a *calibration* report, not a hard gate: a kappa below the warn
threshold (default 0.6, overridable via fixture ``kappa_warn_below``) prints a
WARNING but the process still exits 0 — drift in the judge should be visible
without blocking unrelated CI.

Usage
-----
    python -m backend.eval.run_judge_calibration
    python -m backend.eval.run_judge_calibration --json
    python -m backend.eval.run_judge_calibration --judge verifier   # real LLM
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from itertools import product
from typing import Any, Dict, List, Optional

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_REPO_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DEFAULT_FIXTURES = os.path.join(
    _BACKEND_DIR, "tests", "fixtures", "rag_eval", "judge_calibration_cases.json"
)
VERDICTS = ("grounded", "partially_grounded", "ungrounded")
DEFAULT_KAPPA_WARN = 0.6

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "is", "are", "for", "of", "to", "and", "or", "in", "on",
    "per", "by", "with", "at", "be", "as", "it", "from", "into", "you", "your",
}


def _tokens(text: str) -> set:
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOP}


def _chunks_text(chunks: List[Dict[str, Any]]) -> str:
    return " ".join((c.get("text") or "") for c in chunks)


# ---------------------------------------------------------------------------
# Judges (verdict only)
# ---------------------------------------------------------------------------


def mock_judge(case: Dict[str, Any]) -> str:
    """Deterministic grounding verdict from answer-token coverage by the chunks.

    coverage = |answer_tokens ∩ chunk_tokens| / |answer_tokens|
      >= 0.7  -> grounded            (answer is a subset/paraphrase of sources)
      0.4-0.7 -> partially_grounded  (answer mixes supported + new claims)
      <  0.4  -> ungrounded          (answer largely unsupported)
    """
    a_tokens = _tokens(case.get("answer") or "")
    c_tokens = _tokens(_chunks_text(case.get("chunks") or []))
    if not a_tokens:
        return "ungrounded"
    coverage = len(a_tokens & c_tokens) / len(a_tokens)
    if coverage >= 0.7:
        return "grounded"
    if coverage >= 0.4:
        return "partially_grounded"
    return "ungrounded"


def verifier_judge(case: Dict[str, Any]) -> str:
    """Real judge: delegate to immigration_answer_verifier.verify_grounding.

    Only used with ``--judge verifier``; never called by tests. Fails OPEN inside
    verify_grounding — a skipped verification is reported here as the model
    declining to ground, mapped to 'ungrounded' for the agreement maths.
    """
    from backend.app.services.immigration_answer_verifier import verify_grounding

    result = verify_grounding(case.get("answer") or "", case.get("chunks") or [])
    verdict = result.get("verdict")
    return verdict if verdict in VERDICTS else "ungrounded"


_JUDGES = {"mock": mock_judge, "verifier": verifier_judge}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def cohen_kappa(gold: List[str], pred: List[str], labels=VERDICTS) -> float:
    """Cohen's kappa for two raters over a fixed label set. Returns 0.0 when
    chance agreement is perfect (undefined kappa) to keep the report finite."""
    n = len(gold)
    if n == 0:
        return 0.0
    idx = {lab: i for i, lab in enumerate(labels)}
    conf = [[0 for _ in labels] for _ in labels]
    for g, p in zip(gold, pred):
        conf[idx[g]][idx[p]] += 1

    po = sum(conf[i][i] for i in range(len(labels))) / n
    row = [sum(conf[i][j] for j in range(len(labels))) for i in range(len(labels))]
    col = [sum(conf[i][j] for i in range(len(labels))) for j in range(len(labels))]
    pe = sum((row[i] / n) * (col[i] / n) for i in range(len(labels)))
    if pe >= 1.0:
        return 0.0
    return round((po - pe) / (1 - pe), 4)


@dataclass
class CaseResult:
    case_id: str
    gold: str
    pred: str

    @property
    def agree(self) -> bool:
        return self.gold == self.pred


def _load_fixtures(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def run_eval(fixtures_path: str, judge_name: str = "mock") -> dict:
    fixtures = _load_fixtures(fixtures_path)
    judge = _JUDGES[judge_name]
    warn_below = float(fixtures.get("kappa_warn_below", DEFAULT_KAPPA_WARN))

    results = [
        CaseResult(case_id=c["id"], gold=c["gold"], pred=judge(c))
        for c in fixtures["cases"]
    ]
    gold = [r.gold for r in results]
    pred = [r.pred for r in results]

    n = len(results)
    agreement = round(sum(1 for r in results if r.agree) / n, 4) if n else 0.0
    kappa = cohen_kappa(gold, pred)

    # 3x3 confusion (gold rows × pred cols) for the human report.
    confusion = {
        g: {p: sum(1 for r in results if r.gold == g and r.pred == p) for p in VERDICTS}
        for g in VERDICTS
    }

    return {
        "fixtures_path": fixtures_path,
        "judge": judge_name,
        "n_cases": n,
        "agreement": agreement,
        "cohen_kappa": kappa,
        "kappa_warn_below": warn_below,
        "kappa_warning": kappa < warn_below,
        "confusion": confusion,
        "disagreements": [
            {"case_id": r.case_id, "gold": r.gold, "pred": r.pred}
            for r in results
            if not r.agree
        ],
    }


def _print_human(report: dict) -> None:
    lines = [
        "",
        "=== WS-C Grounding-Judge Calibration ({} judge) ===".format(report["judge"]),
        f"Fixtures:   {report['fixtures_path']}",
        f"Cases:      {report['n_cases']}",
        f"Agreement:  {report['agreement']:.4f} ({report['agreement'] * 100:.1f}%)",
        f"Cohen kappa: {report['cohen_kappa']:.4f} (warn below {report['kappa_warn_below']:.2f})",
        "Confusion (gold ↓ / pred →):",
        "                     " + "  ".join(f"{p[:5]:>7}" for p in VERDICTS),
    ]
    for g in VERDICTS:
        row = report["confusion"][g]
        lines.append(f"  {g:<18} " + "  ".join(f"{row[p]:>7}" for p in VERDICTS))
    if report["disagreements"]:
        lines.append("Disagreements:")
        for d in report["disagreements"]:
            lines.append(f"  - {d['case_id']}: gold={d['gold']} pred={d['pred']}")
    if report["kappa_warning"]:
        lines.append(
            f"WARNING: Cohen kappa {report['cohen_kappa']:.4f} is below "
            f"{report['kappa_warn_below']:.2f} — judge calibration has drifted; review the judge."
        )
    lines.append("")
    print("\n".join(lines))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="WS-C grounding-judge calibration.")
    parser.add_argument(
        "--fixtures",
        default=DEFAULT_FIXTURES,
        help="Path to the calibration fixtures JSON.",
    )
    parser.add_argument(
        "--judge",
        choices=sorted(_JUDGES),
        default="mock",
        help="Judge: 'mock' (offline deterministic, default) or 'verifier' (real LLM).",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of the human summary.")
    parser.add_argument(
        "--emit-dashboard",
        action="store_true",
        help="Write a dated judge_calibration_kappa dashboard report into --out-dir "
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
        from pathlib import Path

        from backend.eval.dashboard_report import write_dashboard_report

        dest = write_dashboard_report(
            Path(args.out_dir), "judge_calibration_kappa", report["cohen_kappa"], report
        )
        print(f"wrote {dest}", file=sys.stderr)

    if args.json:
        print(json.dumps(report, indent=2))
        if report["kappa_warning"]:
            # Still surface the warning on stderr even in JSON mode.
            print(
                f"WARNING: Cohen kappa {report['cohen_kappa']:.4f} < "
                f"{report['kappa_warn_below']:.2f}",
                file=sys.stderr,
            )
    else:
        _print_human(report)

    # Calibration is advisory — always exit 0 (warning only).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
