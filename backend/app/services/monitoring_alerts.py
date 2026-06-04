"""
[P3-02c] Source-monitoring alert delivery.

Fans monitoring events out to admin channels:
  - Slack via an incoming webhook (``SLACK_WEBHOOK_URL``)
  - Email via Resend (reuses dossier_notifications._send_email, sent to
    ``OPS_ALERT_EMAIL``)

Triggers: a material (significant) change to a monitored source, or repeated
crawl failures (3rd consecutive). Both channels are best-effort — a delivery
failure is logged and never raised, so monitoring jobs stay green. With no
channel configured, alerts fall back to INFO logging (dev/test).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import requests

log = logging.getLogger(__name__)

_SEVERITY_EMOJI = {
    "info": ":information_source:",
    "warning": ":warning:",
    "high": ":rotating_light:",
    "critical": ":rotating_light:",
}


def _slack_webhook_url() -> str:
    return os.getenv("SLACK_WEBHOOK_URL", "").strip()


def _format_slack_text(text: str, severity: str) -> str:
    emoji = _SEVERITY_EMOJI.get(severity, ":warning:")
    return f"{emoji} {text}"


def send_slack_alert(text: str, *, severity: str = "warning") -> bool:
    """Post a message to the configured Slack incoming webhook.

    Returns True on a 2xx response. No-ops (returns False) and logs when no
    webhook is configured or the post fails.
    """
    url = _slack_webhook_url()
    if not url:
        log.info("SLACK ALERT (no SLACK_WEBHOOK_URL): %s", text)
        return False
    try:
        resp = requests.post(
            url,
            json={"text": _format_slack_text(text, severity)},
            timeout=10,
        )
        ok = 200 <= resp.status_code < 300
        if not ok:
            log.warning("Slack alert non-2xx (%s): %s", resp.status_code, text)
        return ok
    except Exception as e:  # never raise into the caller
        log.warning("Slack alert failed: %s", e)
        return False


def send_email_alert(subject: str, title: str, body: str) -> bool:
    """Email an alert to OPS_ALERT_EMAIL via the existing Resend sender.

    No-ops (returns False) when OPS_ALERT_EMAIL is not configured.
    """
    to = os.getenv("OPS_ALERT_EMAIL", "").strip()
    if not to:
        return False
    try:
        from .dossier_notifications import _send_email
        _send_email(to, subject, title, body)
        return True
    except Exception as e:  # never raise into the caller
        log.warning("Ops email alert failed: %s", e)
        return False


def dispatch_monitoring_alert(
    event_type: str,
    title: str,
    message: str,
    *,
    severity: str = "warning",
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Fan a monitoring alert out to Slack + email. Best-effort, never raises."""
    text = f"*{title}*\n{message}"
    slack_ok = send_slack_alert(text, severity=severity)
    email_ok = send_email_alert(f"[ReloPass Ops] {title}", title, message)
    log.info(
        "monitoring alert dispatched type=%s severity=%s slack=%s email=%s",
        event_type, severity, slack_ok, email_ok,
    )
    return {"event_type": event_type, "slack": slack_ok, "email": email_ok}


def alert_material_change(
    source_name: str,
    significant_count: int,
    *,
    country_code: Optional[str] = None,
    crawl_run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Alert that a monitored source changed materially."""
    where = f" ({country_code})" if country_code else ""
    title = f"Material change detected: {source_name}{where}"
    message = (
        f"{significant_count} significant change(s) detected while monitoring "
        f"{source_name}. Review the staged changes in the source-monitor dashboard."
    )
    return dispatch_monitoring_alert(
        "material_change", title, message,
        severity="warning",
        context={"source_name": source_name, "significant_count": significant_count,
                 "country_code": country_code, "crawl_run_id": crawl_run_id},
    )


def alert_crawl_failure(
    source_name: str,
    failure_count: int,
    *,
    schedule_id: Optional[str] = None,
    job_run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Alert that a monitored source has failed repeatedly (3rd consecutive)."""
    title = f"Source monitoring failure: {source_name}"
    message = (
        f"{source_name} has failed {failure_count} consecutive times. "
        f"Manual attention required — the source may be down or blocking the crawler."
    )
    return dispatch_monitoring_alert(
        "crawl_failure", title, message,
        severity="critical",
        context={"source_name": source_name, "failure_count": failure_count,
                 "schedule_id": schedule_id, "job_run_id": job_run_id},
    )


def send_test_alert() -> Dict[str, Any]:
    """Fire a test alert through every channel (used by the test cron endpoint)."""
    return dispatch_monitoring_alert(
        "test",
        "Test alert",
        "This is a ReloPass source-monitoring test alert. If you see this, the "
        "Slack/email wiring works.",
        severity="info",
    )
