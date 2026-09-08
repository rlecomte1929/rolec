"""P2-08e (AIQ-706) — admin alert when >20% of active cases have stale steps.

When source refresh falls behind, a growing share of active cases end up citing
forms whose official source has not been re-verified inside its freshness window.
This service aggregates that share across active cases and, when it crosses the
configured threshold, raises a single admin ops-notification so the team knows
the crawler/refresh pipeline has fallen behind.

A case is counted as *stale* when its oldest cited form-card source exceeds the
``tier1_critical`` threshold — the exact same ``is_stale`` rule and tier the
Dossier form-card badge uses (``StalenessBadge`` / ``frontend/src/utils/staleness.ts``),
so the backend alert and the UI badge agree. The redirect recorded on the parent
P2-08 applies here too: roadmap steps carry no source metadata, so the staleness
signal is read from the Dossier form-card source layer (``source_pages.last_fetched_at``,
wired by P1-05d), not from ``roadmap_steps``.

Alert channel: this repo has no Slack integration, so the admin alert is an
``ops_notifications`` row (the existing admin alert feed), created via
``create_or_update_notification`` and deduped to a single open notification —
mirroring ``evaluate_stale_signal_notification`` / ``evaluate_crawl_failure_notification``.

MVP STATUS (2026-06-04): MANUAL-ONLY. ``evaluate_case_staleness_alert`` is invoked
only via the admin endpoint POST /api/admin/freshness/staleness-alert/run. It is
NOT yet on a scheduler. This matches the same MVP decision taken for the P1-08d
rule-change notifier. TODO [P2-08e-followup]: before production, call this from a
daily scheduled job (e.g. alongside the source-freshness crawl) so the alert fires
hands-off rather than only when an admin presses the button.
"""
from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Union

from sqlalchemy import text

from ...database import db
from .staleness import Tier, is_stale

logger = logging.getLogger(__name__)

# A case counts as stale at the same threshold the Dossier form-card badge uses.
ALERT_TIER: Tier = "tier1_critical"

# Fraction of active cases that must be stale before the alert fires.
DEFAULT_ALERT_THRESHOLD_PCT = 0.20
ENV_THRESHOLD = "STALE_CASE_ALERT_THRESHOLD_PCT"

# Stable dedupe key: one open admin notification at a time, retriggered on
# subsequent runs (subject to the ops cooldown) while the breach persists.
NOTIFICATION_TYPE = "stale_cases_over_threshold"

# Only cases with this status count toward the denominator. Legacy rows with a
# NULL status are not active cases and are excluded.
_ACTIVE_STATUS = "active"


def load_threshold_pct(env: Optional[Mapping[str, str]] = None) -> float:
    """Read the alert threshold fraction from env, clamped to [0, 1].

    Accepts either a fraction (``0.2``) or a percentage (``20``) — any value
    greater than 1 is treated as a percentage and divided by 100. Falls back to
    ``DEFAULT_ALERT_THRESHOLD_PCT`` on a missing or unparseable value.
    """
    source = os.environ if env is None else env
    raw = source.get(ENV_THRESHOLD)
    if raw is None or str(raw).strip() == "":
        return DEFAULT_ALERT_THRESHOLD_PCT
    try:
        val = float(raw)
    except (TypeError, ValueError):
        logger.warning(
            "case_staleness_alert: %s=%r is not a number; using default %.2f",
            ENV_THRESHOLD, raw, DEFAULT_ALERT_THRESHOLD_PCT,
        )
        return DEFAULT_ALERT_THRESHOLD_PCT
    if val > 1:
        val = val / 100.0
    if val < 0:
        return 0.0
    if val > 1:
        return 1.0
    return val


@dataclass(frozen=True)
class StalenessAlertSummary:
    total_active: int
    cases_with_sources: int
    stale_cases: int
    stale_pct: float
    threshold_pct: float
    breached: bool


def summarize_case_staleness(
    *,
    total_active: int,
    case_oldest_sources: Mapping[str, Optional[Union[datetime, str]]],
    now: Optional[datetime] = None,
    tier: Tier = ALERT_TIER,
    threshold_pct: Optional[float] = None,
) -> StalenessAlertSummary:
    """Pure aggregation core — no DB, ``now`` injectable for tests.

    Args:
        total_active: count of active cases (the denominator).
        case_oldest_sources: map of case_id → the *oldest* last-verified
            timestamp among that case's cited form-card sources. A case absent
            from this map (or mapped to ``None``) has no datable source and is
            never stale (fail-open on missing data, matching the badge).
        now: reference time (defaults to UTC now).
        tier: staleness tier whose threshold defines "stale".
        threshold_pct: breach fraction (defaults to env / 0.20).

    Breach is strict (``stale_pct > threshold_pct``) to match the ">20%" spec,
    and never fires when there are no active cases.
    """
    ref = now or datetime.now(timezone.utc)
    pct_threshold = load_threshold_pct() if threshold_pct is None else threshold_pct

    cases_with_sources = 0
    stale_cases = 0
    for oldest in case_oldest_sources.values():
        if oldest is None:
            continue
        cases_with_sources += 1
        if is_stale(oldest, tier, now=ref):
            stale_cases += 1

    stale_pct = (stale_cases / total_active) if total_active > 0 else 0.0
    breached = total_active > 0 and stale_pct > pct_threshold

    return StalenessAlertSummary(
        total_active=total_active,
        cases_with_sources=cases_with_sources,
        stale_cases=stale_cases,
        stale_pct=round(stale_pct, 4),
        threshold_pct=pct_threshold,
        breached=breached,
    )


# Oldest re-verified source timestamp per active case that has at least one
# form whose official source URL matches a crawled source_page.
_OLDEST_SOURCE_SQL = """
SELECT cf.case_id AS case_id,
       MIN(sp.last_fetched_at) AS oldest_source
FROM public.relocation_cases rc
JOIN public.case_forms cf ON cf.case_id = rc.id
JOIN public.form_templates ft ON ft.id = cf.form_template_id
JOIN public.source_pages sp ON sp.url = ft.source_url
WHERE rc.status = :active_status
  AND sp.last_fetched_at IS NOT NULL
GROUP BY cf.case_id
"""

_ACTIVE_COUNT_SQL = """
SELECT count(*) AS n
FROM public.relocation_cases
WHERE status = :active_status
"""


def _fetch_active_case_sources() -> tuple[int, Dict[str, Optional[datetime]]]:
    """Return (total active cases, {case_id: oldest matched source timestamp}).

    Safe-fails to ``(0, {})`` so a query error degrades to "no alert" rather
    than a 500 on the admin endpoint.
    """
    try:
        with db.engine.connect() as conn:
            total = conn.execute(
                text(_ACTIVE_COUNT_SQL), {"active_status": _ACTIVE_STATUS}
            ).scalar() or 0
            rows = (
                conn.execute(
                    text(_OLDEST_SOURCE_SQL), {"active_status": _ACTIVE_STATUS}
                )
                .mappings()
                .all()
            )
        oldest_by_case = {str(r["case_id"]): r["oldest_source"] for r in rows}
        return int(total), oldest_by_case
    except Exception:  # noqa: BLE001 — degrade rather than 500
        logger.exception("case_staleness_alert: fetch failed; treating as no data")
        return 0, {}


def evaluate_case_staleness_alert(now: Optional[datetime] = None) -> Dict[str, Any]:
    """Aggregate active-case staleness and raise an admin alert if it breaches.

    Returns the summary plus ``alert_fired`` and ``notification_id``. Idempotent
    via the ops-notification dedupe key: re-running while the breach persists
    retriggers the single open notification instead of creating duplicates.
    """
    total, oldest_by_case = _fetch_active_case_sources()
    summary = summarize_case_staleness(
        total_active=total, case_oldest_sources=oldest_by_case, now=now
    )

    result: Dict[str, Any] = dict(asdict(summary))
    result["alert_fired"] = False
    result["notification_id"] = None

    if not summary.breached:
        return result

    pct_label = f"{summary.stale_pct * 100:.0f}%"
    threshold_label = f"{summary.threshold_pct * 100:.0f}%"
    # Lazy import to avoid a hard import-time dependency on the Supabase client.
    from .ops_notification_service import _build_dedupe_key, create_or_update_notification

    try:
        notif = create_or_update_notification(
            NOTIFICATION_TYPE,
            "high",
            f"{pct_label} of active cases have stale sources",
            (
                f"{summary.stale_cases} of {summary.total_active} active cases cite a "
                f"source not re-verified within its freshness window "
                f"({pct_label} > {threshold_label} threshold). Source refresh has "
                f"fallen behind — review the freshness dashboard."
            ),
            _build_dedupe_key(NOTIFICATION_TYPE),
            payload={
                "total_active": summary.total_active,
                "stale_cases": summary.stale_cases,
                "stale_pct": summary.stale_pct,
                "threshold_pct": summary.threshold_pct,
            },
        )
        result["alert_fired"] = True
        result["notification_id"] = (notif or {}).get("id")
    except Exception:  # noqa: BLE001 — alerting failure must not 500 the endpoint
        logger.exception("case_staleness_alert: failed to create ops notification")

    return result
