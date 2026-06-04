"""
P1-08d · Rule-change notifications (AIQ-642).

When a rule_version that an active case relied on is superseded, the case owner
must be told — otherwise compliance breaks silently. This service detects
recently-superseded rule_versions, finds every open case whose
``rce.roadmap_audit_log`` cites the prior version, and writes one in-app
notification per recipient.

Schema note: the original task brief referenced ``rules.is_current=false``, but
the live ``rce.rule_versions`` schema (migration 20260528020000) expresses
currency via ``effective_to`` (a closed validity window) and ``superseded_by``
(a pointer to the replacing version). A version is treated as *superseded* when
either is set. This is the correct, schema-accurate signal.

MVP STATUS (2026-06-04): MANUAL-ONLY. This function is currently invoked only via
the admin endpoint POST /api/admin/rule-change-notifications/run. It is NOT yet on
a scheduler, so the P1-08d "within 24h" criterion is only met when an admin runs it.
TODO [P1-08d-followup]: before a real production launch, call this from a ≤24h
scheduled job (e.g. the same daily job that runs backend/relopass/jobs/rule_scraper.py)
so the 24h guarantee holds automatically.

Idempotency: a recipient is notified at most once per (case, prior rule_version)
— re-running the job does not re-notify.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ...database import db

logger = logging.getLogger(__name__)

NOTIFICATION_TYPE = "rule_updated"

# Cases past these statuses are closed — no point notifying.
_OPEN_CASE_STATUSES = ("ACTIVE", "DRAFT", "BLOCKED")


# Distinct (case, prior-version) pairs where an open case cites a rule_version
# that has since been superseded, and the supersession was recorded recently.
_AFFECTED_SQL = """
SELECT DISTINCT
    ral.case_id,
    rv.rule_version_id AS old_rule_version_id,
    rv.rule_id,
    rv.version_label,
    rv.superseded_by   AS new_rule_version_id
FROM rce.rule_versions rv
JOIN rce.roadmap_audit_log ral ON ral.rule_version_id = rv.rule_version_id
JOIN rce.cases c ON c.case_id = ral.case_id
WHERE (
        rv.superseded_by IS NOT NULL
        OR (rv.effective_to IS NOT NULL AND rv.effective_to <= CURRENT_DATE)
      )
  AND rv.updated_at >= :since
  AND c.status = ANY(:open_statuses)
"""


def _already_notified(case_id: str, old_rule_version_id: str) -> bool:
    """True if a rule_updated notification for this (case, prior version) exists."""
    with db.engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT 1 FROM public.notifications "
                "WHERE case_id = :cid AND type = :type "
                "AND metadata->>'old_rule_version_id' = :ov LIMIT 1"
            ),
            {"cid": case_id, "type": NOTIFICATION_TYPE, "ov": old_rule_version_id},
        ).first()
    return row is not None


def _recipients_for_case(case_id: str) -> List[str]:
    """Resolve the user ids to notify for a case (HR owner + employee)."""
    case = db.get_relocation_case(case_id)
    if not case:
        return []
    recipients = [case.get("hr_user_id"), case.get("employee_id")]
    # De-dupe + drop falsy, preserving order.
    seen: set = set()
    out: List[str] = []
    for uid in recipients:
        if uid and uid not in seen:
            seen.add(uid)
            out.append(str(uid))
    return out


def notify_superseded_rules(since: Optional[datetime] = None) -> Dict[str, int]:
    """Notify open cases whose cited rule_version was recently superseded.

    Args:
        since: only consider supersessions recorded at/after this time.
               Defaults to 24h ago (matches the "within 24h" validation criterion).

    Returns:
        Counts: ``affected_pairs`` scanned, ``notifications_created``,
        ``skipped_idempotent``, ``skipped_no_recipient``.
    """
    if since is None:
        since = datetime.utcnow() - timedelta(hours=24)

    with db.engine.connect() as conn:
        affected = (
            conn.execute(
                text(_AFFECTED_SQL),
                {"since": since, "open_statuses": list(_OPEN_CASE_STATUSES)},
            )
            .mappings()
            .all()
        )

    created = skipped_idem = skipped_norecip = 0
    for row in affected:
        case_id = str(row["case_id"])
        old_version = str(row["old_rule_version_id"])
        if _already_notified(case_id, old_version):
            skipped_idem += 1
            continue
        recipients = _recipients_for_case(case_id)
        if not recipients:
            skipped_norecip += 1
            continue
        metadata = {
            "rule_id": row["rule_id"],
            "old_rule_version_id": old_version,
            "new_rule_version_id": (
                str(row["new_rule_version_id"]) if row["new_rule_version_id"] else None
            ),
            "version_label": row["version_label"],
            "case_id": case_id,
        }
        title = "A rule on your case was updated"
        body = (
            f"Rule {row['rule_id']} cited in this case's roadmap has a new version. "
            "Review the case to confirm the guidance still applies."
        )
        for uid in recipients:
            try:
                db.create_notification_with_preferences(
                    user_id=uid,
                    type_=NOTIFICATION_TYPE,
                    title=title,
                    body=body,
                    case_id=case_id,
                    metadata=metadata,
                )
                created += 1
            except Exception as exc:  # noqa: BLE001 — one bad recipient must not abort the run
                logger.error(
                    "rule_change_notifier: notify failed case=%s user=%s: %s",
                    case_id,
                    uid,
                    exc,
                )

    return {
        "affected_pairs": len(affected),
        "notifications_created": created,
        "skipped_idempotent": skipped_idem,
        "skipped_no_recipient": skipped_norecip,
    }
