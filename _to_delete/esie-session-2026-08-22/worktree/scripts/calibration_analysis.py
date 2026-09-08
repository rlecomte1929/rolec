#!/usr/bin/env python3
"""
[P1-04b / AIQ-636] Calibration analysis for AI roadmap-step confidence.

Reads ``public.specialist_review_calibration`` (the analytics view built by
P1-04a / AIQ-635) and computes, per confidence bucket (HIGH / MEDIUM / LOW),
the specialist approval rate. Emits ``audit/calibration_report_<date>.md`` with
the calibration curve and recommended threshold deltas.

Statistical-significance guard
------------------------------
A bucket with fewer than ``--min-sample`` (default 50) specialist reviews is
reported as **INSUFFICIENT** and produces **no** threshold recommendation — the
script refuses to emit misleading deltas on thin data. This is intentional: as
of this writing ``specialist_review_events`` is empty, so the report will say
"insufficient sample" until real review data accumulates, at which point the
same script produces the calibration curves automatically.

Usage
-----
    DATABASE_URL=postgresql://... python scripts/calibration_analysis.py
    DATABASE_URL=postgresql://... python scripts/calibration_analysis.py --json
    python scripts/calibration_analysis.py --min-sample 50 --dry-run

Exit codes
----------
    0 — analysis ran and the report was written (sufficient OR insufficient)
    2 — DB connection / query failure
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT_DIR = REPO_ROOT / "audit"

# Confidence buckets we calibrate. Order matters for report rendering.
BUCKETS = ("HIGH", "MEDIUM", "LOW")

# Outcome vocabulary from public.specialist_review_calibration.specialist_outcome
APPROVED_OUTCOME = "approved"
CORRECTED_OUTCOMES = ("edited", "rejected")

# Targets from the P1-04 validation criteria:
#  - HIGH-confidence steps should achieve >=95% specialist approval.
#  - LOW-confidence steps should trigger a correction in >=90% of cases
#    (i.e. LOW is meant to flag steps that genuinely needed expert input).
HIGH_APPROVAL_TARGET = 0.95
LOW_CORRECTION_TARGET = 0.90

# Columns the script reads from the view.
SELECT_SQL = """
SELECT confidence_at_time,
       specialist_outcome,
       was_edited,
       confidence_score_at_time,
       reason_code
FROM public.specialist_review_calibration
"""


# ---------------------------------------------------------------------------
# Pure logic (no I/O) — unit-tested in backend/tests/test_calibration_analysis.py
# ---------------------------------------------------------------------------
def normalize_bucket(raw: Any) -> str:
    """Map a raw confidence_at_time value to HIGH/MEDIUM/LOW, else UNKNOWN."""
    if raw is None:
        return "UNKNOWN"
    value = str(raw).strip().upper()
    return value if value in BUCKETS else "UNKNOWN"


def classify_outcome(row: Dict[str, Any]) -> str:
    """Classify a review row as 'approved', 'corrected', or 'unknown'."""
    outcome = (row.get("specialist_outcome") or "").strip().lower()
    if outcome == APPROVED_OUTCOME:
        return "approved"
    if outcome in CORRECTED_OUTCOMES:
        return "corrected"
    # Fall back to the was_edited boolean when the outcome label is missing.
    if row.get("was_edited") is True:
        return "corrected"
    return "unknown"


def _recommend(bucket: str, approval_rate: Optional[float],
               correction_rate: Optional[float]) -> str:
    """Threshold recommendation for a bucket with a sufficient sample."""
    if bucket == "HIGH":
        if approval_rate is None:
            return "No decided reviews in HIGH bucket; cannot assess."
        if approval_rate < HIGH_APPROVAL_TARGET:
            return (
                f"TIGHTEN HIGH threshold — approval {approval_rate:.1%} is below the "
                f"{HIGH_APPROVAL_TARGET:.0%} target. Raise the bar so fewer steps "
                f"qualify as HIGH."
            )
        return f"HIGH OK — approval {approval_rate:.1%} meets the {HIGH_APPROVAL_TARGET:.0%} target."
    if bucket == "LOW":
        if correction_rate is None:
            return "No decided reviews in LOW bucket; cannot assess."
        if correction_rate < LOW_CORRECTION_TARGET:
            return (
                f"LOOSEN LOW threshold — only {correction_rate:.1%} of LOW steps were "
                f"corrected (target ≥{LOW_CORRECTION_TARGET:.0%}). LOW may be firing on "
                f"steps that did not need expert input."
            )
        return f"LOW OK — correction rate {correction_rate:.1%} meets the {LOW_CORRECTION_TARGET:.0%} target."
    # MEDIUM is informational — no hard target.
    if approval_rate is None:
        return "MEDIUM — no decided reviews; informational only."
    return f"MEDIUM — approval {approval_rate:.1%} (informational; no hard target)."


def compute_calibration(rows: List[Dict[str, Any]], min_sample: int = 50) -> Dict[str, Any]:
    """Compute per-bucket calibration stats. Pure; no I/O.

    Returns a dict with per-bucket counts/rates, a recommendation per bucket
    (only when n >= min_sample), and a top-level ``had_sufficient_data`` flag.
    """
    tally: Dict[str, Dict[str, Any]] = {
        b: {"n": 0, "approved": 0, "corrected": 0, "unknown_outcome": 0, "scores": []}
        for b in (*BUCKETS, "UNKNOWN")
    }
    for row in rows:
        bucket = normalize_bucket(row.get("confidence_at_time"))
        slot = tally[bucket]
        slot["n"] += 1
        outcome = classify_outcome(row)
        if outcome == "approved":
            slot["approved"] += 1
        elif outcome == "corrected":
            slot["corrected"] += 1
        else:
            slot["unknown_outcome"] += 1
        score = row.get("confidence_score_at_time")
        if score is not None:
            try:
                slot["scores"].append(float(score))
            except (TypeError, ValueError):
                pass

    buckets_out: Dict[str, Any] = {}
    for bucket in BUCKETS:
        slot = tally[bucket]
        n = slot["n"]
        decided = slot["approved"] + slot["corrected"]
        approval_rate = (slot["approved"] / decided) if decided else None
        correction_rate = (slot["corrected"] / decided) if decided else None
        sufficient = n >= min_sample
        avg_score = (sum(slot["scores"]) / len(slot["scores"])) if slot["scores"] else None
        buckets_out[bucket] = {
            "n": n,
            "approved": slot["approved"],
            "corrected": slot["corrected"],
            "unknown_outcome": slot["unknown_outcome"],
            "decided": decided,
            "approval_rate": approval_rate,
            "correction_rate": correction_rate,
            "avg_score": avg_score,
            "sufficient": sufficient,
            "recommendation": (
                _recommend(bucket, approval_rate, correction_rate)
                if sufficient
                else f"INSUFFICIENT SAMPLE — {n} review(s) < {min_sample} required; no change recommended."
            ),
        }

    return {
        "min_sample": min_sample,
        "total_reviews": sum(tally[b]["n"] for b in (*BUCKETS, "UNKNOWN")),
        "unknown_bucket_reviews": tally["UNKNOWN"]["n"],
        "buckets": buckets_out,
        "had_sufficient_data": any(buckets_out[b]["sufficient"] for b in BUCKETS),
    }


def _fmt_rate(rate: Optional[float]) -> str:
    return f"{rate:.1%}" if rate is not None else "—"


def render_markdown(result: Dict[str, Any], report_date: str) -> str:
    """Render the calibration result as a Markdown report."""
    lines: List[str] = []
    lines.append(f"# Confidence Calibration Report — {report_date}")
    lines.append("")
    lines.append("_Generated by `scripts/calibration_analysis.py` (P1-04b / AIQ-636)._")
    lines.append("")
    lines.append(
        f"**Total specialist reviews analysed:** {result['total_reviews']}  ·  "
        f"**Minimum sample per bucket:** {result['min_sample']}"
    )
    lines.append("")
    if not result["had_sufficient_data"]:
        lines.append(
            "> ⚠️ **INSUFFICIENT DATA — no threshold changes recommended.** No confidence "
            f"bucket has reached the {result['min_sample']}-review minimum required for a "
            "statistically meaningful approval rate. Re-run once specialist reviews accumulate."
        )
        lines.append("")

    lines.append("## Calibration curve")
    lines.append("")
    lines.append("| Bucket | n | Approved | Corrected | Approval rate | Correction rate | Avg score | Sample |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for bucket in BUCKETS:
        b = result["buckets"][bucket]
        sample = "✅ ≥min" if b["sufficient"] else f"⚠️ {b['n']}<{result['min_sample']}"
        avg = f"{b['avg_score']:.3f}" if b["avg_score"] is not None else "—"
        lines.append(
            f"| {bucket} | {b['n']} | {b['approved']} | {b['corrected']} | "
            f"{_fmt_rate(b['approval_rate'])} | {_fmt_rate(b['correction_rate'])} | {avg} | {sample} |"
        )
    if result["unknown_bucket_reviews"]:
        lines.append("")
        lines.append(
            f"> Note: {result['unknown_bucket_reviews']} review(s) had an unrecognised "
            "`confidence_at_time` value and were excluded from bucket calibration."
        )
    lines.append("")

    lines.append("## Recommendations")
    lines.append("")
    for bucket in BUCKETS:
        lines.append(f"- **{bucket}** — {result['buckets'][bucket]['recommendation']}")
    lines.append("")

    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "1. Source: `public.specialist_review_calibration` (P1-04a), one row per specialist review.\n"
        "2. Each row is bucketed by `confidence_at_time` (HIGH / MEDIUM / LOW) and classified as\n"
        "   *approved* (`specialist_outcome = 'approved'`) or *corrected* (`edited` / `rejected`,\n"
        "   or `was_edited = true`).\n"
        f"3. Approval rate = approved / decided. A bucket needs ≥ {result['min_sample']} reviews before\n"
        "   any threshold change is recommended (statistical-significance guard).\n"
        f"4. Targets: HIGH approval ≥ {HIGH_APPROVAL_TARGET:.0%}; LOW correction ≥ {LOW_CORRECTION_TARGET:.0%}.\n"
        "5. Apply recommended deltas in the schema package via P1-04c, then re-run to confirm."
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
def fetch_rows(database_url: str) -> List[Dict[str, Any]]:
    """Fetch review rows from the calibration view. Raises on connection error."""
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError as exc:  # pragma: no cover - env-dependent
        raise RuntimeError(
            "psycopg2 not installed — `pip install psycopg2-binary` or run from the backend venv"
        ) from exc

    conn = psycopg2.connect(database_url, connect_timeout=10)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(SELECT_SQL)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate AI confidence thresholds from specialist reviews.")
    parser.add_argument("--min-sample", type=int, default=50,
                        help="Minimum reviews per bucket before a threshold change is recommended (default 50).")
    parser.add_argument("--output", type=str, default=None,
                        help="Report path (default audit/calibration_report_<date>.md).")
    parser.add_argument("--json", action="store_true", help="Also print the result as JSON to stdout.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write the report file.")
    args = parser.parse_args(argv)

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2
    try:
        rows = fetch_rows(database_url)
    except Exception as exc:  # noqa: BLE001 - surface any DB failure as exit 2
        print(f"could not read specialist_review_calibration: {exc}", file=sys.stderr)
        return 2

    result = compute_calibration(rows, min_sample=args.min_sample)
    report_date = date.today().isoformat()
    markdown = render_markdown(result, report_date)

    if args.dry_run:
        print(markdown)
    else:
        out_path = Path(args.output) if args.output else (DEFAULT_REPORT_DIR / f"calibration_report_{report_date}.md")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(markdown, encoding="utf-8")
        print(f"wrote {out_path}")

    if args.json:
        print(json.dumps(result, indent=2))

    if not result["had_sufficient_data"]:
        print(
            f"INSUFFICIENT DATA: no bucket reached the {args.min_sample}-review minimum "
            f"(total reviews={result['total_reviews']}). No thresholds changed.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
