# WS-D — pairwise LLM-as-judge for supplier ranking.
# For each golden (category, corridor) case the engine produces a ranked list;
# we ask a judge, for each ordered pair (A above B), "is A a better fit than B?"
# and report how often the judge agrees with the engine's order.
#
# Two judges:
#   * mock (default)  — deterministic, no network; used in CI/tests.
#   * --live          — real Claude via llm_client.claude_complete; supplier
#                       attributes + non-personal criteria are masked (mask_pii)
#                       before the prompt per the data-minimisation rule.
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "ranking"
    / "golden_rankings.json"
)


def _engine_ranked_items(category: str, criteria: Dict[str, Any], k: int) -> List[Dict[str, Any]]:
    """Engine-ranked top-k items, each enriched with its full dataset attributes."""
    from backend.app.recommendations.engine import recommend_debug
    from backend.app.recommendations.registry import get_plugin

    plugin = get_plugin(category)
    by_id = {str(it.get("item_id")): it for it in (plugin.load_dataset() if plugin else [])}
    dbg = recommend_debug(category, criteria, top_n=100)
    items: List[Dict[str, Any]] = []
    for row in dbg["ranked"][:k]:
        attrs = by_id.get(str(row["item_id"]), {})
        items.append({"item_id": row["item_id"], "name": row.get("name"), **attrs})
    return items


def mock_judge_pair(case_ctx: Dict[str, Any], a: Dict[str, Any], b: Dict[str, Any]) -> str:
    """Deterministic offline judge: a single-attribute heuristic, independent of
    the engine's full blend so agreement is a real (non-trivial) signal.

    Prefers higher rating, then sooner availability, then lexicographic item_id.
    Returns "A" or "B".
    """
    def key(s: Dict[str, Any]) -> Tuple[float, float, str]:
        return (
            -float(s.get("rating") or 0.0),
            float(s.get("next_available_days") or 999),
            str(s.get("item_id") or ""),
        )

    return "A" if key(a) <= key(b) else "B"


_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "better": {"type": "string", "enum": ["A", "B"]},
        "reason": {"type": "string"},
    },
    "required": ["better"],
}

_JUDGE_SYSTEM = (
    "You are an impartial relocation-services analyst. Given a relocating "
    "employee's non-personal preferences and two candidate suppliers, decide "
    "which supplier is the better fit. Answer strictly with A or B."
)


async def llm_judge_pair(case_ctx: Dict[str, Any], a: Dict[str, Any], b: Dict[str, Any]) -> str:
    """Real Claude judge. Masks the rendered prompt before sending."""
    from backend.app.services.llm_client import claude_complete
    from backend.app.services.pii_masker import mask_pii

    user = mask_pii(
        json.dumps(
            {
                "category": case_ctx.get("category"),
                "corridor": case_ctx.get("corridor"),
                "preferences": case_ctx.get("criteria"),
                "supplier_A": a,
                "supplier_B": b,
            },
            ensure_ascii=False,
        )
    )
    result = await claude_complete(system=_JUDGE_SYSTEM, user=user, schema=_JUDGE_SCHEMA)
    return "A" if str(result.get("better", "A")).upper().startswith("A") else "B"


def _agreement_for_case(
    items: List[Dict[str, Any]],
    case_ctx: Dict[str, Any],
    judge_pair,
) -> Dict[str, Any]:
    """Fraction of engine-ordered pairs the judge agrees with.

    For each i<j (engine ranks items[i] above items[j]) the judge sees the higher
    one as A; agreement counts how often it still picks A.
    """
    agree = 0
    total = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            total += 1
            verdict = judge_pair(case_ctx, items[i], items[j])
            if verdict == "A":
                agree += 1
    return {
        "pairs": total,
        "agreements": agree,
        "agreement_rate": round(agree / total, 4) if total else 1.0,
    }


def run_judge(fixtures: Dict[str, Any], live: bool = False) -> Dict[str, Any]:
    k = int(fixtures.get("_meta", {}).get("k", 5))
    per_case: List[Dict[str, Any]] = []

    for case in fixtures.get("cases", []):
        case_ctx = {
            "category": case["category"],
            "corridor": case.get("corridor", ""),
            "criteria": case["criteria"],
        }
        items = _engine_ranked_items(case["category"], case["criteria"], k)

        if live:
            def judge_pair(ctx, a, b):
                return asyncio.run(llm_judge_pair(ctx, a, b))
        else:
            judge_pair = mock_judge_pair

        result = _agreement_for_case(items, case_ctx, judge_pair)
        per_case.append({**case_ctx, "k": k, **result})

    rates = [c["agreement_rate"] for c in per_case]
    return {
        "judge": "live" if live else "mock",
        "k": k,
        "n_cases": len(per_case),
        "mean_agreement": round(sum(rates) / len(rates), 4) if rates else 1.0,
        "per_case": per_case,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Pairwise LLM-judge for supplier ranking.")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--json", action="store_true", help="Emit the full JSON report.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use the real Claude judge (requires ANTHROPIC_API_KEY). Default: mock.",
    )
    args = parser.parse_args()

    os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
    with args.fixtures.open(encoding="utf-8") as f:
        fixtures = json.load(f)
    report = run_judge(fixtures, live=args.live)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"ranking judge ({report['judge']}): cases={report['n_cases']} "
            f"mean_agreement={report['mean_agreement']:.4f}"
        )


if __name__ == "__main__":
    main()
