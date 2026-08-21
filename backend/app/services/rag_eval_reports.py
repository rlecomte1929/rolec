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
    # Phase 2 eval surfaced on the dashboard (emitted by run_structuring_eval):
    # structuring_accuracy = per-profile requirement matching accuracy.
    MetricSpec("structuring_accuracy", "Structuring accuracy", 0.95),
    # RETIRED: the aggregate 'roadmap_completeness' (corridor completeness %) spec.
    # An aggregate average hides rare-slice failures (Ng MLOps C1 W2-3), and the
    # rare missed non-obvious requirement is exactly the failure the product
    # exists to kill. Replaced by the sliced metric below; old
    # roadmap_completeness_*.json reports are no longer read.
    #
    # nonobvious_recall = non-obvious requirement recall per
    # (corridor x employee_type) slice vs the lawyer-verified HLP baseline
    # (backend/eval/hlp_nonobvious_baseline.json), emitted by
    # run_nonobvious_recall_eval. The plotted aggregate is the WORST slice's
    # recall (a minimum, never a mean), and the report carries per-slice detail
    # sorted worst-first. Threshold 1.0: a single missed non-obvious requirement
    # in any one slice must alert.
    MetricSpec("nonobvious_recall", "Non-obvious recall (worst corridor \u00d7 employee-type slice)", 1.0),
    # overserved_requirements = the PRECISION half of the non-obvious metric: what a roadmap
    # told an audience that it must never tell them. Recall is structurally blind to it —
    # telling a free mover to obtain a 'D' visa costs zero recall — and every defect the
    # 2026-08-21 ES->IE audit found was an over-serving defect.
    #
    # Emitted as 1.0 (clean) / 0.0 (any violation) rather than a raw count, because
    # `load_live_reports` hardcodes `passes_threshold = aggregate >= threshold` and a
    # count-down metric reads backwards there. The count and the named violations ride in
    # the payload. The key must NOT begin "nonobvious_recall": `_metric_key_for_filename`
    # matches by startswith, so such a name would be plotted on the recall chart.
    MetricSpec("overserved_requirements", "Corridor over-serving (violations, 0 = clean)", 1.0),
    # Mission Control demand-triage accuracy (emitted by run_triage_eval): fraction
    # of demands classified to the right kind (bug/idea/quality/task).
    MetricSpec("triage_accuracy", "Demand triage accuracy", 0.85),
    # Assistant policy-bridge routing accuracy (emitted by run_routing_eval):
    # fraction of questions sent to the correct engine (immigration vs policy)
    # or honestly deferred to the clarifier.
    MetricSpec("routing_accuracy", "Assistant routing accuracy", 0.90),
    # Answer-path faithfulness (run_answer_grade): grounding_rate of the immigration
    # Q&A answers (the "remove noise, ensure accuracy" surface).
    MetricSpec("answer_grounding", "Answer grounding", 0.90),
    # Confidence calibration (run_calibration_eval): 1 − ECE; is HIGH actually right?
    MetricSpec("calibration_score", "Confidence calibration", 0.90),
    # WS-C: HR-policy retriever context precision (offline lexical eval —
    # backend/scripts/eval_hr_policy_context_precision.py). Reports land as
    # audit/rag_eval/hr_policy_context_precision_*.json; the first committed
    # report flips this metric from mock to live.
    MetricSpec("hr_policy_context_precision", "HR policy context precision", 0.50),
    # [AIQ-1821] Requirement-fact extraction recall over the snapshot-backed golden set
    # (backend/scripts/eval_requirement_extraction.py --emit-dashboard, run report-only on
    # the weekly eval-llm-reports workflow). 0.60 matches the runner's measured default so
    # the dashboard alert line agrees with the gate; it was derived from three baseline runs
    # (recall 0.909-1.000), not chosen aspirationally. Recall rather than precision: substring
    # matching depresses precision whenever the model finds true facts beyond the curated
    # expectations, so precision would penalise a better extractor.
    MetricSpec("requirement_extraction_recall", "Requirement extraction recall", 0.60),
    # P3: real-LLM eval producers surfaced via the eval-llm-reports workflow.
    # RAG triad (run_rag_triad --judge claude) — thresholds match the runner's
    # DEFAULT_THRESHOLDS so the dashboard alert line agrees with the gate.
    MetricSpec("context_relevance", "RAG triad: context relevance", 0.30),
    MetricSpec("groundedness", "RAG triad: groundedness", 0.30),
    MetricSpec("answer_relevance", "RAG triad: answer relevance", 0.30),
    # Grounding-judge calibration (run_judge_calibration --judge verifier) —
    # Cohen's kappa vs the human gold set; warn band matches the runner (0.60).
    MetricSpec("judge_calibration_kappa", "Judge calibration (Cohen kappa)", 0.60),
    # Supplier-ranking pairwise judge agreement (run_ranking_judge --live).
    MetricSpec("ranking_agreement", "Ranking judge agreement", 0.70),
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
        point: Dict[str, Any] = {
            "date": report_date.isoformat(),
            "aggregate": round(float(aggregate), 4),
            "passes_threshold": float(aggregate) >= threshold,
        }
        # Sliced metrics (nonobvious_recall) carry per-slice detail worst-first
        # plus the worst slice's identity; pass it through so the dashboard can
        # show WHICH (corridor x employee_type) slice is failing, not a mean.
        if isinstance(report.get("slices"), list):
            point["slices"] = report["slices"]
            point["worst_slice"] = report.get("worst_slice")
        grouped.setdefault(metric_key, []).append(point)

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
    # Worst-slice non-obvious recall. Ends below the 1.0 threshold on purpose:
    # the mock demonstrates the exact story this metric exists for \u2014 one missed
    # non-obvious requirement in one slice (see _MOCK_NONOBVIOUS_SLICES) pulls
    # the worst slice, and only that slice, below target.
    "nonobvious_recall": [0.75, 0.75, 0.8571, 0.8571, 0.8571, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.8571],
    "overserved_requirements": [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0],
    "triage_accuracy": [0.86, 0.88, 0.89, 0.90, 0.92, 0.93, 0.95, 0.96, 0.97, 1.0, 1.0, 1.0, 1.0],
    "routing_accuracy": [0.92, 0.94, 0.94, 0.95, 0.97, 0.97, 0.97, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    "answer_grounding": [0.90, 0.91, 0.92, 0.92, 0.93, 0.93, 0.94, 0.94, 0.95, 0.95, 0.96, 0.96, 0.96],
    "calibration_score": [0.91, 0.92, 0.92, 0.93, 0.93, 0.94, 0.94, 0.94, 0.95, 0.95, 0.95, 0.96, 0.96],
    "hr_policy_context_precision": [0.52, 0.54, 0.55, 0.57, 0.58, 0.60, 0.60, 0.61, 0.62, 0.61, 0.60, 0.60, 0.60],
    # P3 real-LLM eval metrics (mock fallback until the eval-llm-reports workflow
    # lands real reports). Lexical-judge floors sit near the 0.30 triad gate.
    "context_relevance": [0.41, 0.43, 0.42, 0.45, 0.47, 0.46, 0.48, 0.49, 0.50, 0.49, 0.48, 0.47, 0.46],
    "groundedness": [0.55, 0.57, 0.58, 0.60, 0.61, 0.62, 0.63, 0.62, 0.63, 0.64, 0.63, 0.62, 0.61],
    "answer_relevance": [0.38, 0.40, 0.41, 0.42, 0.44, 0.45, 0.46, 0.45, 0.46, 0.47, 0.46, 0.45, 0.44],
    "judge_calibration_kappa": [0.62, 0.64, 0.65, 0.67, 0.68, 0.70, 0.71, 0.70, 0.72, 0.73, 0.72, 0.71, 0.70],
    "ranking_agreement": [0.74, 0.75, 0.76, 0.78, 0.79, 0.80, 0.81, 0.80, 0.81, 0.82, 0.81, 0.80, 0.80],
    # [AIQ-1821] Mock series anchored on the real measured baseline (0.909-1.000 across three
    # runs over the v2 snapshot set), so the placeholder does not imply better quality than
    # the eval has actually demonstrated.
    "requirement_extraction_recall": [0.82, 0.84, 0.85, 0.86, 0.88, 0.89, 0.90, 0.91, 0.91, 0.92, 0.91, 0.91, 0.91],
}
_MOCK_WEEKS = 13

# Deterministic per-slice detail for the mock nonobvious_recall metric: the six
# active (corridor x employee_type) slices, sorted WORST-FIRST. One slice \u2014 the
# priority ES\u2192IE non-EU passport holder (Madrid\u2192Dublin) \u2014 misses exactly one
# non-obvious requirement, so its recall (6/7) is the worst-slice aggregate
# while every other slice stays at 1.0.
_MOCK_NONOBVIOUS_SLICES: List[Dict[str, Any]] = [
    {"corridor": "ES_IE", "employee_type": "non_eu_passport_holder",
     "label": "Spain \u2192 Ireland \u00b7 non-EU passport holder (priority \u2014 Madrid\u2192Dublin case)",
     "recall": 0.8571, "served": 6, "total": 7,
     "missing": ["d_visa_before_travel"], "n_roadmaps": 3, "hlp_status": "pending_lawyer_signoff"},
    {"corridor": "ES_IE", "employee_type": "eu_national",
     "label": "Spain \u2192 Ireland \u00b7 EU national",
     "recall": 1.0, "served": 3, "total": 3, "missing": [], "n_roadmaps": 2,
     "hlp_status": "pending_lawyer_signoff"},
    {"corridor": "FR_NO", "employee_type": "eu_national",
     "label": "France \u2192 Norway \u00b7 EU national",
     "recall": 1.0, "served": 3, "total": 3, "missing": [], "n_roadmaps": 4,
     "hlp_status": "pending_lawyer_signoff"},
    {"corridor": "FR_NO", "employee_type": "non_eu_eea_national",
     "label": "France \u2192 Norway \u00b7 non-EU EEA national",
     "recall": 1.0, "served": 3, "total": 3, "missing": [], "n_roadmaps": 1,
     "hlp_status": "pending_lawyer_signoff"},
    {"corridor": "FR_NO", "employee_type": "non_eea_national",
     "label": "France \u2192 Norway \u00b7 non-EEA national",
     "recall": 1.0, "served": 3, "total": 3, "missing": [], "n_roadmaps": 1,
     "hlp_status": "pending_lawyer_signoff"},
    {"corridor": "NO_FR", "employee_type": "norwegian_national",
     "label": "Norway \u2192 France \u00b7 Norwegian national (repatriation, SLB case)",
     "recall": 1.0, "served": 8, "total": 8, "missing": [], "n_roadmaps": 1,
     "hlp_status": "pending_lawyer_signoff"},
]
_MOCK_NONOBVIOUS_WORST: Dict[str, Any] = {
    "corridor": "ES_IE", "employee_type": "non_eu_passport_holder",
    "recall": 0.8571, "missing": ["d_visa_before_travel"],
}


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
        metric: Dict[str, Any] = {
            "metric": spec.key,
            "label": spec.label,
            "threshold": spec.threshold,
            "points": points,
            "latest": latest,
            "alert": evaluate_alert(points, spec.threshold),
        }
        # Surface per-slice detail (worst-first) for sliced metrics so the UI
        # names the failing (corridor x employee_type) slice instead of hiding
        # it behind an average.
        if points and isinstance(points[-1].get("slices"), list):
            metric["slices"] = points[-1]["slices"]
            metric["worst_slice"] = points[-1].get("worst_slice")
        elif source == "mock" and spec.key == "nonobvious_recall":
            metric["slices"] = _MOCK_NONOBVIOUS_SLICES
            metric["worst_slice"] = _MOCK_NONOBVIOUS_WORST
        metrics.append(metric)

    return {"source": source, "metrics": metrics}
