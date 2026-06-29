"""
Shared writer for rag-eval dashboard report files.

Emits ``<metric_key>_<YYYYMMDD>.json`` with a top-level numeric ``aggregate`` and
``generated_at`` — the exact shape ``rag_eval_reports.load_live_reports`` reads to
plot a metric over time. Used by run_structuring_eval and run_roadmap_outcome_eval
so their results show on the same dashboard as outcome_accuracy.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def write_dashboard_report(
    out_dir: Path,
    metric_key: str,
    aggregate: float,
    payload: Dict[str, Any],
    today: Optional[date] = None,
) -> Path:
    """Write a dated dashboard report. Filename prefix MUST equal a
    rag_eval_reports.METRIC_SPECS key for the dashboard to pick it up."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = (today or datetime.now(timezone.utc).date()).strftime("%Y%m%d")
    report = {
        **payload,
        "aggregate": round(float(aggregate), 4),
        "generated_at": (today or datetime.now(timezone.utc).date()).isoformat(),
    }
    dest = out_dir / f"{metric_key}_{stamp}.json"
    dest.write_text(json.dumps(report, indent=2))
    return dest
