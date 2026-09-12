"""Append-only history for public.requirement_items.

Not a serving engine. Catalog writes (admin review, crud upsert) call record_change
so a poisoned or mistaken overwrite has a previous_value to roll back to.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.orm import Session

from backend.app import models

log = logging.getLogger(__name__)

CHANGE_ADDED = "requirement_added"
CHANGE_REVISED = "requirement_revised"
CHANGE_DEPRECATED = "requirement_deprecated"
CHANGE_SOURCE = "source_updated"
CHANGE_SEVERITY = "severity_changed"

_CRITICAL_SEVERITIES = frozenset({"critical", "blocker", "CRITICAL", "BLOCKER"})

TRACKED_FIELDS: tuple[str, ...] = (
    "description",
    "severity",
    "owner",
    "citations_json",
    "non_obvious",
    "timing",
    "review_status",
)


def snapshot_item(item: models.RequirementItem) -> Dict[str, Any]:
    return {name: getattr(item, name, None) for name in TRACKED_FIELDS}


def classify_change(previous: Dict[str, Any], new: Dict[str, Any]) -> str:
    if previous.get("severity") != new.get("severity"):
        return CHANGE_SEVERITY
    if previous.get("citations_json") != new.get("citations_json"):
        return CHANGE_SOURCE
    if previous.get("review_status") == "approved" and new.get("review_status") == "rejected":
        return CHANGE_DEPRECATED
    return CHANGE_REVISED


def _json_text(value: Optional[Dict[str, Any]]) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, default=str)


def record_change(
    db: Session,
    *,
    requirement_id: str,
    country_code: Optional[str],
    change_type: str,
    previous_value: Optional[Dict[str, Any]],
    new_value: Optional[Dict[str, Any]],
    changed_by: Optional[str] = None,
    change_justification: Optional[str] = None,
    commit: bool = False,
) -> models.RequirementItemChangelog:
    row = models.RequirementItemChangelog(
        change_id=str(uuid.uuid4()),
        requirement_id=requirement_id,
        country_code=(country_code or "").upper() or None,
        change_type=change_type,
        previous_value=_json_text(previous_value),
        new_value=_json_text(new_value),
        changed_by=changed_by,
        changed_at=datetime.now(timezone.utc),
        change_justification=change_justification,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)

    prev_sev = (previous_value or {}).get("severity")
    new_sev = (new_value or {}).get("severity")
    if prev_sev != new_sev and (
        str(prev_sev) in _CRITICAL_SEVERITIES or str(new_sev) in _CRITICAL_SEVERITIES
    ):
        log.warning(
            "critical-severity requirement change requirement_id=%s from=%s to=%s by=%s",
            requirement_id,
            prev_sev,
            new_sev,
            changed_by,
        )
    return row


def record_field_diff(
    db: Session,
    item: models.RequirementItem,
    previous: Dict[str, Any],
    *,
    changed_by: Optional[str],
    extra_new: Optional[Dict[str, Any]] = None,
) -> Optional[models.RequirementItemChangelog]:
    current = snapshot_item(item)
    if extra_new:
        current.update(extra_new)
    changed = {k: current[k] for k in TRACKED_FIELDS if previous.get(k) != current[k]}
    if not changed:
        return None
    prev_subset = {k: previous.get(k) for k in changed}
    return record_change(
        db,
        requirement_id=item.id,
        country_code=item.country_code,
        change_type=classify_change(previous, current),
        previous_value=prev_subset,
        new_value=changed,
        changed_by=changed_by,
    )


def list_for_requirement(db: Session, requirement_id: str) -> Iterable[models.RequirementItemChangelog]:
    return (
        db.query(models.RequirementItemChangelog)
        .filter(models.RequirementItemChangelog.requirement_id == requirement_id)
        .order_by(models.RequirementItemChangelog.changed_at.desc())
        .all()
    )
