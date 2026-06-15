"""
Run the 46-question golden eval against the live HR policy assistant
and record results as a Langfuse dataset run.

Usage (from repo root, with venv_new active):
    python -m experiments.run_golden_eval [--run-name my-run]

What it does:
  1. Fetches all items from the ``policy-assistant-golden-v2`` Langfuse dataset.
  2. For each item, calls hr_policy_assistant_query_response_dict with the question.
  3. Scores the answer using the same rubric as the offline eval harness.
  4. Records each call as a Langfuse trace (via @observe decorator — SDK v4 compatible).
  5. Adds a "pass" score (1.0 / 0.0) to each trace.
  6. Prints a per-section scorecard identical to run_comprehensive_eval.py.

Environment variables (read from .env or shell):
  LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
  DATABASE_URL (Supabase pooler), OPENAI_API_KEY

Requires: langfuse>=4, python-dotenv, psycopg2-binary, sqlalchemy, openai
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Bootstrap ─────────────────────────────────────────────────────────────────
_root = Path(__file__).resolve().parent.parent
_env = _root / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_env, override=False)

sys.path.insert(0, str(_root))

# ── Imports ───────────────────────────────────────────────────────────────────
try:
    from langfuse import Langfuse
    from langfuse.decorators import langfuse_context, observe
    _HAS_LANGFUSE = True
except ImportError:
    _HAS_LANGFUSE = False
    print("WARNING: langfuse not installed — Langfuse tracing disabled.")

from backend.observability import configure_observability
configure_observability()

from backend.app.services.hr_policy_assistant_service import (
    hr_policy_assistant_query_response_dict,
)
from experiments.create_langfuse_golden_dataset import (
    DATASET_NAME,
    _score_item,
)

# ── Constants ─────────────────────────────────────────────────────────────────
POLICY_ID = "d70615b6-11b3-4595-989e-a3ef20cf2fe2"

MOCK_HR = {
    "id": "eval-hr-00000000",
    "role": "HR",
    "company_id": "0d3e8d04-b463-4516-a26d-bf0e8f68dbdb",
    "email": "eval@relopass.com",
}

_SECTIONS: List[str] = (
    ["A-baseline"] * 18   # Q01–Q18
    + ["B-db-cleanup"] * 10  # Q19–Q28
    + ["C-aspects"] * 6   # Q29–Q34
    + ["D-refusal"] * 6   # Q35–Q40
    + ["E-hr-meta"] * 4   # Q41–Q44
    + ["out-of-scope"] * 2  # Q45–Q46
)


def _section_for(idx: int) -> str:
    return _SECTIONS[idx] if idx < len(_SECTIONS) else "unknown"


# ── Per-item runner (wrapped with @observe for Langfuse v4 tracing) ───────────

def _make_runner(run_name: str, q_num: str, section: str, expected_output: dict):
    """
    Returns a zero-arg callable that runs one question and returns (answer, verdict).
    Wraps it in @observe so Langfuse v4 records a trace per question.
    """
    if _HAS_LANGFUSE:
        @observe(name=f"golden-eval-{q_num}")
        def _run(q: str) -> tuple:
            langfuse_context.update_current_trace(
                name=f"golden-eval-{q_num}",
                tags=[run_name, "golden-eval", section],
                metadata={"q_num": q_num, "section": section, "run_name": run_name},
                input={"question": q},
            )
            result = hr_policy_assistant_query_response_dict(
                message=q,
                user=MOCK_HR,
                policy_id=POLICY_ID,
            )
            answer = result.get("answer", {})
            verdict = _score_item(answer, expected_output)
            langfuse_context.update_current_trace(output=answer)
            langfuse_context.score_current_trace(
                name="pass",
                value=1.0 if verdict == "PASS" else 0.0,
                comment=verdict,
            )
            return answer, verdict
    else:
        def _run(q: str) -> tuple:  # type: ignore[misc]
            result = hr_policy_assistant_query_response_dict(
                message=q,
                user=MOCK_HR,
                policy_id=POLICY_ID,
            )
            answer = result.get("answer", {})
            verdict = _score_item(answer, expected_output)
            return answer, verdict

    return _run


# ── Runner ────────────────────────────────────────────────────────────────────

def run(run_name: Optional[str] = None) -> None:
    if run_name is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
        run_name = f"golden-eval-{ts}"

    lf = Langfuse(
        public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
        host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    ) if _HAS_LANGFUSE else None

    print(f"\n{'='*72}")
    print(f"  ReloPass Policy Assistant — Langfuse Golden Eval")
    print(f"  Dataset : {DATASET_NAME}")
    print(f"  Run     : {run_name}")
    print(f"{'='*72}\n")

    # ── Fetch + deduplicate items ──────────────────────────────────────────────
    if lf:
        dataset = lf.get_dataset(name=DATASET_NAME)
        raw_items = list(dataset.items)
        seen: set = set()
        items = []
        for it in raw_items:
            q_text = (it.input or {}).get("question", "")
            if q_text and q_text not in seen:
                seen.add(q_text)
                items.append(it)
        items = items[:46]
        print(f"  Fetched {len(raw_items)} items, de-duplicated to {len(items)} unique questions\n")
    else:
        # No Langfuse — run against local GOLDEN_ITEMS directly
        from experiments.create_langfuse_golden_dataset import GOLDEN_ITEMS
        items = GOLDEN_ITEMS  # type: ignore[assignment]
        print(f"  Running {len(items)} questions (offline — no Langfuse)\n")

    sections: Dict[str, List[tuple]] = {}
    passes = 0
    errors = 0
    total = len(items)

    for i, item in enumerate(items):
        if lf:
            q = item.input.get("question", "")
            expected_output = item.expected_output or {}
        else:
            # item is a dict from GOLDEN_ITEMS
            q = item["question"]  # type: ignore[index]
            expected_output = item["expected_output"]  # type: ignore[index]

        section = _section_for(i)
        q_num = f"Q{i+1:02d}"

        answer: Dict[str, Any] = {}
        verdict = "ERROR"
        error_msg = ""

        runner = _make_runner(run_name, q_num, section, expected_output)
        try:
            answer, verdict = runner(q)
        except Exception as exc:
            error_msg = str(exc)[:200]
            verdict = "ERROR"

        if verdict == "PASS":
            passes += 1
        elif verdict == "ERROR":
            errors += 1

        sections.setdefault(section, []).append(
            (verdict, q_num, q, answer, error_msg)
        )

        icon = "✓" if verdict == "PASS" else ("⚠" if verdict == "ERROR" else "✗")
        atype = answer.get("answer_type", "?") if answer else "?"
        topic = answer.get("canonical_topic") or "-"
        preview = (answer.get("answer_text") or "")[:80].replace("\n", " ")
        print(f"  [{icon}] {q_num}  {verdict:<5}  {atype} | topic={topic}")
        if preview:
            print(f"        A: {preview}")
        if error_msg:
            print(f"        ERROR: {error_msg}")

    # ── Flush Langfuse ─────────────────────────────────────────────────────────
    if lf:
        lf.flush()

    # ── Scorecard ──────────────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print(f"  SCORE: {passes}/{total} PASS  |  {total-passes-errors} FAIL  |  {errors} ERROR")
    print(f"{'='*72}\n")

    for section, rows in sections.items():
        sec_pass = sum(1 for v, *_ in rows if v == "PASS")
        pct = sec_pass / len(rows) * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        ok = "✓" if sec_pass == len(rows) else "✗"
        print(f"  {section:<20} {bar} {pct:.0f}%  {ok}  ({sec_pass}/{len(rows)})")

    print()
    if lf:
        print(f"  Traces recorded in Langfuse under run '{run_name}'")
        print(f"  → {os.environ.get('LANGFUSE_HOST', 'https://cloud.langfuse.com')}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run 46-question golden eval and record traces in Langfuse."
    )
    parser.add_argument(
        "--run-name",
        default=None,
        help="Langfuse run label (default: golden-eval-YYYYMMDD-HHMM)",
    )
    args = parser.parse_args()
    run(run_name=args.run_name)


if __name__ == "__main__":
    main()
