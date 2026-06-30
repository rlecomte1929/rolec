"""
RAG-quality dashboard service — P3-01e.

Reads the JSON eval reports emitted by the P3-01 evaluator suite
(``backend/scripts/eval_rag_context_precision.py`` and
``eval_factual_consistency.py`` via ``rag_eval_harness.aggregate_report``) and
assembles a per-metric time-series plus threshold-alert evaluation for the admin
RAG-quality dashboard.

Data source (read-only, no DB): committed report files under ``audit/rag_eval/``.
Reports are grouped by **filename prefix** (``context_precision_*.json`` etc.),
not by the report's internal ``metric`` field — the context-precision report
records ``metric = "precision_at_k"`` while its filename prefix is the canonical
metric family the dashboard plots.

Until real reports land (P3-01b-FU3 and P3-01d are data/infra-blocked at the time
of writing), ``build_dashboard`` falls back to a deterministic, clearly-flagged
mock series (``source = "mock"``) so the dashboard renders and the alert logic is
demonstrable. The moment one real report per metric exists on disk, the same
endpoint serves live data (``source = "live"``) with no code change.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Repo-root/audit/rag_eval — three parents up from this file is backend/, then repo root.
_DEFAULT_REPORTS_DIR = Path(__file__).resolve().parents[3] / "audit" / "rag_eval"

# Canonical metric families plotted by the dashboard. The key is the report
# filename prefix; threshold/label/unit drive the alert lines and axis.
@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    threshold: float


METRIC_SPECS: List[MetricSpec] = [
    MetricSpec("context_precision", "Context precision", 0.85),
    MetricSpec("factual_consistency", "Factual consistency", 0.95),
    MetricSpec("outcome_accuracy", "Outcome accuracy", 0.90),
    # Phase 2 evals surfaced on the dashboard (emitted by run_structuring_eval /
    # run_roadmap_outcome_eval). structuring_accuracy = per-profile requirement
    # matching accuracy; roadmap_completeness = recall of required roadmap steps.
    MetricSpec("structuring_accuracy", "Structuring accuracy", 0.95),
    MetricSpec("roadmap_completeness", "Roadmap completeness", 0.90),
    # WS-C: HR-policy retriever context precision (offline lexical eval —
    # backend/scripts/eval_hr_policy_context_precision.py). Reports land as
    # audit/rag_eval/hr_policy_context_precision_*.json; the first committed
    # report flips this metric from mock to live.
    MetricSpec("hr_policy_context_precision", "HR policy context precision", 0.50),
]

_SPEC_BY_KEY: Dict[str, MetricSpec] = {s.key: s for s in METRIC_SPECS}

# Matches a YYYY-MM-DD or YYYYMMDD date anywhere in a report filename.
_DATE_RE = re.compile(r"(\d{4})-?(\d{2})-?(\d{2})")


def _parse_report_date(report: Dict[str, Any], filename: str) -> Optional[date]:
    """Resolve a report's date: explicit ``generated_at`` wins, else parse the filename."""
    raw = report.get("generated_at")
    if isinstance(raw, str):
        m = _DATE_RE.search(raw)
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _DATE_RE.search(filename)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _metric_key_for_filename(filename: str) -> Optional[str]:
    """Map a report filename to its canonical metric family by prefix."""
    for spec in METRIC_SPECS:
        if filename.startswith(spec.key):
            return spec.key
    return None


def load_live_reports(reports_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Read ``<metric>_*.json`` reports from ``reports_dir``, grouped by metric key.

    Each point is ``{date, aggregate, passes_threshold}``, sorted ascending by date.
    Malformed or undated reports are skipped with a warning rather than failing the
    whole dashboard. Returns ``{}`` when the directory is absent or holds no reports.
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    if not reports_dir.is_dir():
        return grouped

    for path in sorted(reports_dir.glob("*.json")):
        metric_key = _metric_key_for_filename(path.name)
        if metric_key is None:
            continue
        try:
            report = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("rag_eval: skipping unreadable report %s (%s)", path.name, exc)
            continue
        report_date = _parse_report_date(report, path.name)
        aggregate = report.get("aggregate")
        if report_date is None or not isinstance(aggregate, (int, float)):
            logger.warning("rag_eval: skipping report %s (missing date or aggregate)", path.name)
            continue
        threshold = _SPEC_BY_KEY[metric_key].threshold
        grouped.setdefault(metric_key, []).append(
            {
                "date": report_date.isoformat(),
                "aggregate": round(float(aggregate), 4),
                "passes_threshold": float(aggregate) >= threshold,
            }
        )

    for points in grouped.values():
        points.sort(key=lambda p: p["date"])
    return grouped


# Deterministic mock series — one value per week. Engineered so the dashboard
# demonstrates all three alert states: context_precision ends BELOW threshold
# (below_threshold), factual_consistency stays healthy (no alert), and
# outcome_accuracy shows a monotonic 3-point decline while still above threshold
# (declining). No randomness so the output is stable and unit-testable.
_MOCK_VALUES: Dict[str, List[float]] = {
    "context_precision": [0.79, 0.81, 0.80, 0.83, 0.86, 0.88, 0.87, 0.89, 0.90, 0.88, 0.87, 0.85, 0.83],
    "factual_consistency": [0.95, 0.96, 0.96, 0.97, 0.97, 0.96, 0.98, 0.97, 0.98, 0.98, 0.97, 0.98, 0.97],
    "outcome_accuracy": [0.88, 0.89, 0.91, 0.92, 0.93, 0.94, 0.95, 0.94, 0.95, 0.96, 0.95, 0.94, 0.93],
    "structuring_accuracy": [0.96, 0.97, 0.97, 0.98, 0.98, 0.99, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    "roadmap_completeness": [0.82, 0.84, 0.85, 0.87, 0.88, 0.90, 0.91, 0.92, 0.93, 0.93, 0.94, 0.94, 0.95],
    "hr_policy_context_precision": [0.52, 0.54, 0.55, 0.57, 0.58, 0.60, 0.60, 0.61, 0.62, 0.61, 0.60, 0.60, 0.60],
}
_MOCK_WEEKS = 13


def generate_mock_reports(end_date: date) -> Dict[str, List[Dict[str, Any]]]:
    """Build a deterministic ~3-month weekly series per metric, ending at ``end_date``."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for spec in METRIC_SPECS:
        values = _MOCK_VALUES[spec.key]
        points = []
        for i, value in enumerate(values):
            d = end_date - timedelta(weeks=(_MOCK_WEEKS - 1 - i))
            points.append(
                {
                    "date": d.isoformat(),
                    "aggregate": value,
                    "passes_threshold": value >= spec.threshold,
                }
            )
        grouped[spec.key] = points
    return grouped


def evaluate_alert(points: List[Dict[str, Any]], threshold: float) -> Dict[str, Any]:
    """Decide whether a metric is alerting.

    Fires when the latest point is below threshold (``below_threshold``), or when
    the last three points strictly decrease (``declining``) even if still above
    threshold — an early-warning signal. ``below_threshold`` takes precedence.
    """
    if not points:
        return {"firing": False, "reason": "no_data"}

    latest = points[-1]["aggregate"]
    if latest < threshold:
        return {"firing": True, "reason": "below_threshold"}

    if len(points) >= 3:
        a, b, c = points[-3]["aggregate"], points[-2]["aggregate"], points[-1]["aggregate"]
        if a > b > c:
            return {"firing": True, "reason": "declining"}

    return {"firing": False, "reason": "healthy"}


def build_dashboard(
    reports_dir: Optional[Path] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Assemble the dashboard payload: per-metric series + alert, live if reports
    exist on disk, otherwise a flagged deterministic mock series."""
    reports_dir = reports_dir or _DEFAULT_REPORTS_DIR
    live = load_live_reports(reports_dir)
    if live:
        source = "live"
        grouped = live
    else:
        source = "mock"
        grouped = generate_mock_reports(today or date.today())

    metrics: List[Dict[str, Any]] = []
    for spec in METRIC_SPECS:
        points = grouped.get(spec.key, [])
        latest = points[-1]["aggregate"] if points else None
        metrics.append(
            {
                "metric": spec.key,
                "label": spec.label,
                "threshold": spec.threshold,
                "points": points,
                "latest": latest,
                "alert": evaluate_alert(points, spec.threshold),
            }
        )

    return {"source": source, "metrics": metrics}
