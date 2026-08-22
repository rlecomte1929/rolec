"""AIQ-378b (AIQ-817) — Nightly case-health scan: alert-dispatch layer.

Runs the read-only case-delay signal (AIQ-378a, ``scan_active_cases``) and, for
each behind-schedule case, raises a single **deduped** ops-notification (one open
notification per case, retriggered while it stays behind) and fans a best-effort
Slack/email alert. This is the side-effecting counterpart to the pure signal
layer — the "surface each behind case as a proactive HR alert" step.

Inert by construction: ``scan_active_cases()`` returns ``[]`` until the pilot
populates ``immigration_milestones``, so this raises nothing live. Best-effort:
a notification or alert failure for one case is logged and never aborts the scan.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from .case_delay_monitor import scan_active_cases
from .case_suggested_action import build_suggested_action

logger = logging.getLogger(__name__)

NOTIFICATION_TYPE = "case_behind_schedule"

# Signal severity ('warning' | 'critical') -> ops-notification severity. Both
# are valid ops_notification_service severities; default to 'warning'.
_SEVERITY_MAP = {"warning": "warning", "critical": "critical"}


def _dedupe_key(case_id: str) -> str:
    """One open notification per case (mirrors ``_build_dedupe_key``'s ``|`` format)."""
    return f"{NOTIFICATION_TYPE}|case:{case_id}"


def run_case_health_scan() -> Dict[str, Any]:
    """Scan active cases for delays and raise one deduped HR alert per behind case.

    Returns a summary ``{flagged, notifications, alerts, errors}``. Idempotent via
    the per-case dedupe key: re-running while a case stays behind retriggers its
    single open notification instead of creating duplicates.
    """
    flagged = scan_active_cases()

    # Lazy imports: an unconfigured Supabase / alert client must not break import
    # of this module (mirrors case_staleness_alert.py).
    from .case_suggested_action import build_suggested_action
    from .monitoring_alerts import dispatch_monitoring_alert
    from .ops_notification_service import create_or_update_notification

    notifications = 0
    alerts = 0
    errors = 0

    for sig in flagged:
        case_id = str(sig.get("case_id") or "")
        if not case_id:
            continue
        severity = _SEVERITY_MAP.get(sig.get("severity"), "warning")
        # AIQ-378c: per-stage suggested action + draft reminder, attached to the
        # payload (consumed by the HR surface, AIQ-378d) and the alert message.
        suggested = build_suggested_action(sig)
        title = f"Case {case_id} behind schedule"
        message = (
            f"Stage '{sig.get('stage')}' is {sig.get('days_behind')} day(s) past its "
            f"expected date ({sig.get('expected_date')}). {suggested['suggested_action']}"
        )
        payload = {**sig, **suggested}
        try:
            create_or_update_notification(
                NOTIFICATION_TYPE,
                severity,
                title,
                message,
                _dedupe_key(case_id),
                payload=payload,
            )
            notifications += 1
        except Exception:  # noqa: BLE001 — one bad case must not abort the scan
            logger.exception("case_health_scan: notification failed for case=%s", case_id)
            errors += 1
            continue

        # Best-effort fan-out; dispatch_monitoring_alert never raises, but guard anyway.
        try:
            dispatch_monitoring_alert(
                NOTIFICATION_TYPE, title, message, severity=severity, context=sig
            )
            alerts += 1
        except Exception:  # noqa: BLE001 — a failed alert never undoes the notification
            logger.exception("case_health_scan: alert dispatch failed for case=%s", case_id)

    return {
        "flagged": len(flagged),
        "notifications": notifications,
        "alerts": alerts,
        "errors": errors,
    }


def _company_case_ids(company_id: str) -> set:
    """Set of this company's case ids (as text). Safe-fails to an empty set."""
    from sqlalchemy import text

    from ...database import db

    try:
        with db.engine.connect() as conn:
            rows = (
                conn.execute(
                    text("SELECT id::text AS id FROM public.relocation_cases WHERE company_id::text = :c"),
                    {"c": str(company_id)},
                )
                .mappings()
                .all()
            )
        return {r["id"] for r in rows}
    except Exception:  # noqa: BLE001 — degrade rather than raise
        logger.exception("case_health_scan: company case-id query failed")
        return set()


def list_behind_cases_for_company(company_id: str) -> list:
    """The behind-schedule cases for ``company_id`` — the tenant-scoped feed for
    the HR "Needs your attention" panel. Read-only, tenant-safe, safe-fails to ``[]``.

    [AIQ-2041] Computed **live** from the delay signal, not read back from the
    notifications the nightly scan raises.

    It used to read ``ops_notifications``, which made the HR surface depend on the
    cron having run — and that cron is gated behind the ``CASE_HEALTH_CRON_ENABLED``
    repo variable, which `docs/findings/AIQ-2012-cron-gates-never-set.md` records as
    **never set**. So the panel showed "nothing behind schedule" no matter what the
    data said, and fixing the two SQL predicates in ``case_delay_monitor`` would not
    have changed that on its own.

    Reading live also makes the panel *current* rather than showing last night's
    snapshot, which is what an action list on a dashboard should be. The nightly
    scan keeps its job — raising deduped notifications and firing Slack/email
    alerts; that is a different concern from what this screen renders.
    """
    if not company_id:
        return []
    case_ids = _company_case_ids(company_id)
    if not case_ids:
        return []

    from .case_delay_monitor import scan_active_cases

    try:
        signals = scan_active_cases()
    except Exception:  # noqa: BLE001 — degrade rather than raise
        logger.exception("case_health_scan: live delay scan failed")
        return []

    out = []
    for payload in signals:
        cid = str(payload.get("case_id") or "")
        if not cid or cid not in case_ids:
            continue  # tenant scope: only this company's cases
        payload = {**payload, **build_suggested_action(payload)}
        out.append(
            {
                "case_id": cid,
                "stage": payload.get("stage"),
                # [AIQ-2041] The milestone's own curated title and owner. `stage` is a
                # milestone_type key and many are opaque ('pre_departure_ai_01'), so
                # showing it alone tells an HR user nothing; the title is what the
                # step actually is. Exposed as `milestone_title` because `title` on a
                # notification already means the notification's own headline.
                "milestone_title": payload.get("title"),
                "owner": payload.get("owner"),
                "days_behind": payload.get("days_behind"),
                "expected_date": payload.get("expected_date"),
                "severity": payload.get("severity"),
                "suggested_action": payload.get("suggested_action"),
                "draft_reminder": payload.get("draft_reminder"),
            }
        )
    out.sort(key=lambda c: -(c.get("days_behind") or 0))
    return out
