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
