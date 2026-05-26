#!/usr/bin/env python3
"""
Evaluate the LLM + regex policy extractors against a labelled fixture set.

AIQ-285-followup #1 (eval harness). Runs both extractors over every fixture
in backend/tests/fixtures/policy_eval_set/ and prints a per-fixture and
overall precision / recall / F1 table, keyed on benefit_key presence.

V1 scope reduction (vs the original audit ask):
  - Fixtures are PLAIN TEXT (.txt + .gold.json), not real .docx/.pdf.
    The eval feeds each fixture's content directly to the extractors'
    line-level entry points, bypassing the docx/pdf parsing layer.
  - Adding real .docx fixtures is a follow-up (would require a script to
    generate or anonymise real customer policies). The eval framework
    itself is the same.

Usage::

    # Regex-only baseline (no API key needed):
    python backend/scripts/eval_llm_policy_extraction.py

    # With LLM extraction (requires ANTHROPIC_API_KEY in env):
    ANTHROPIC_API_KEY=sk-... python backend/scripts/eval_llm_policy_extraction.py

    # JSON output (for piping into dashboards):
    python backend/scripts/eval_llm_policy_extraction.py --json

Exit codes:
  0 — eval ran, results printed
  1 — fixtures dir missing or all fixtures invalid

This script is read-only against the codebase and the network — it only
calls the Anthropic API when ANTHROPIC_API_KEY is set. Output is printable.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Importing the extractors. The orchestrator lives in policy_extractor;
# the LLM-only entry point lives in llm_policy_extractor.
from backend.app.services.policy_extractor import (  # noqa: E402
    _build_regex_extraction,
)
from backend.app.services.llm_policy_extractor import (  # noqa: E402
    extract_policy_with_llm,
)

FIXTURE_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "policy_eval_set"


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class FixtureScore:
    name: str
    extractor: str  # 'regex' or 'llm'
    gold: List[str]
    predicted: List[str]
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0

    @property
    def precision(self) -> float:
        denom = self.true_positive + self.false_positive
        return self.true_positive / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positive + self.false_negative
        return self.true_positive / denom if denom > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return (2 * p * r / (p + r)) if (p + r) > 0 else 0.0


@dataclass
class OverallScore:
    extractor: str
    fixtures: List[FixtureScore] = field(default_factory=list)

    @property
    def precision(self) -> float:
        tp = sum(f.true_positive for f in self.fixtures)
        fp = sum(f.false_positive for f in self.fixtures)
        denom = tp + fp
        return tp / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        tp = sum(f.true_positive for f in self.fixtures)
        fn = sum(f.false_negative for f in self.fixtures)
        denom = tp + fn
        return tp / denom if denom > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return (2 * p * r / (p + r)) if (p + r) > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Fixture loading
# ─────────────────────────────────────────────────────────────────────────────


def load_fixtures(fixture_dir: Path) -> List[Tuple[str, List[str], Dict[str, Any]]]:
    """Return a list of (name, lines, gold_dict) tuples sorted by filename."""
    out: List[Tuple[str, List[str], Dict[str, Any]]] = []
    if not fixture_dir.is_dir():
        return out
    for txt_path in sorted(fixture_dir.glob("*.txt")):
        name = txt_path.stem
        gold_path = fixture_dir / f"{name}.gold.json"
        if not gold_path.is_file():
            print(f"  skip {name} — no matching .gold.json", file=sys.stderr)
            continue
        text = txt_path.read_text(encoding="utf-8")
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        out.append((name, lines, gold))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────────────────


def _benefit_keys(extraction_result: Optional[Dict[str, Any]]) -> List[str]:
    """Return the set of benefit_key values from an extractor result, or []."""
    if not extraction_result:
        return []
    raw = extraction_result.get("benefits") or []
    if not isinstance(raw, list):
        return []
    keys: List[str] = []
    for row in raw:
        if isinstance(row, dict):
            k = row.get("benefit_key")
            if isinstance(k, str):
                keys.append(k)
    return keys


def score_one(name: str, extractor: str, predicted: List[str], gold: List[str]) -> FixtureScore:
    pset, gset = set(predicted), set(gold)
    tp = len(pset & gset)
    fp = len(pset - gset)
    fn = len(gset - pset)
    return FixtureScore(
        name=name,
        extractor=extractor,
        gold=sorted(gset),
        predicted=sorted(pset),
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────────


def print_table(scores: List[FixtureScore], extractor: str) -> None:
    print(f"\n{extractor.upper()} EXTRACTOR — per fixture")
    print(f"{'Fixture':<28} {'Gold':>5} {'Pred':>5} {'TP':>4} {'FP':>4} {'FN':>4} "
          f"{'P':>6} {'R':>6} {'F1':>6}")
    print("-" * 78)
    for s in scores:
        print(
            f"{s.name:<28} {len(s.gold):>5} {len(s.predicted):>5} "
            f"{s.true_positive:>4} {s.false_positive:>4} {s.false_negative:>4} "
            f"{s.precision:>6.2f} {s.recall:>6.2f} {s.f1:>6.2f}"
        )
    overall = OverallScore(extractor=extractor, fixtures=scores)
    print("-" * 78)
    print(f"{'OVERALL':<28} {sum(len(s.gold) for s in scores):>5} "
          f"{sum(len(s.predicted) for s in scores):>5} "
          f"{sum(s.true_positive for s in scores):>4} "
          f"{sum(s.false_positive for s in scores):>4} "
          f"{sum(s.false_negative for s in scores):>4} "
          f"{overall.precision:>6.2f} {overall.recall:>6.2f} {overall.f1:>6.2f}")


def to_json(regex_scores: List[FixtureScore], llm_scores: List[FixtureScore]) -> Dict[str, Any]:
    def block(scores: List[FixtureScore], extractor: str) -> Dict[str, Any]:
        overall = OverallScore(extractor=extractor, fixtures=scores)
        return {
            "extractor": extractor,
            "overall": {
                "precision": overall.precision,
                "recall": overall.recall,
                "f1": overall.f1,
                "true_positive": sum(s.true_positive for s in scores),
                "false_positive": sum(s.false_positive for s in scores),
                "false_negative": sum(s.false_negative for s in scores),
            },
            "fixtures": [
                {
                    "name": s.name,
                    "gold": s.gold,
                    "predicted": s.predicted,
                    "precision": s.precision,
                    "recall": s.recall,
                    "f1": s.f1,
                    "true_positive": s.true_positive,
                    "false_positive": s.false_positive,
                    "false_negative": s.false_negative,
                }
                for s in scores
            ],
        }

    out: Dict[str, Any] = {"regex": block(regex_scores, "regex")}
    if llm_scores:
        out["llm"] = block(llm_scores, "llm")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON output."
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Don't call the LLM extractor even if ANTHROPIC_API_KEY is set.",
    )
    args = parser.parse_args(argv)

    fixtures = load_fixtures(FIXTURE_DIR)
    if not fixtures:
        print(f"ERROR: no fixtures found in {FIXTURE_DIR}", file=sys.stderr)
        return 1

    regex_scores: List[FixtureScore] = []
    llm_scores: List[FixtureScore] = []

    llm_enabled = bool(os.environ.get("ANTHROPIC_API_KEY")) and not args.skip_llm

    for name, lines, gold in fixtures:
        gold_keys = list(gold.get("benefits") or [])

        # Regex path
        regex_result = _build_regex_extraction(lines)
        regex_predicted = _benefit_keys(regex_result)
        regex_scores.append(score_one(name, "regex", regex_predicted, gold_keys))

        # LLM path (optional)
        if llm_enabled:
            llm_result = extract_policy_with_llm(lines)
            llm_predicted = _benefit_keys(llm_result)
            llm_scores.append(score_one(name, "llm", llm_predicted, gold_keys))

    if args.json:
        print(json.dumps(to_json(regex_scores, llm_scores), indent=2))
    else:
        print_table(regex_scores, "regex")
        if llm_enabled and llm_scores:
            print_table(llm_scores, "llm")
        elif not llm_enabled:
            print("\nLLM EXTRACTOR — skipped (ANTHROPIC_API_KEY not set or --skip-llm).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
