"""Active-case finder for source-change notifications (P2-02c / AIQ-691).

Part of the source-change monitoring pipeline (parent P2-02). When a source
rule changes materially (classified by `source_change_classifier`, P2-02b), we
must notify the users it affects. This module answers the bridging question:

    "given the rule_version that changed, which active cases cite it?"

The provenance audit trail is `rce.rule_citations` (AIQ-751): one row per
(case output, rule_version) pair, indexed by `rule_version_id` precisely for
this fan-out. We join to `rce.cases` to restrict the result to *active* cases —
a rule change should never raise a banner on a completed or cancelled case.

Pure read path: no writes, no side effects. The core function takes any
connection/session executor (so it is trivially testable with a fake), and a
thin wrapper opens the canonical app engine and degrades to an empty list if the
`rce.*` schema is not present yet (its writer, the corridor evaluator, is a
separate task that may not have landed).
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional, Sequence

from sqlalchemy import text

log = logging.getLogger(__name__)

# Statuses considered "active" for notification purposes. rce.cases.status is
# one of DRAFT/ACTIVE/BLOCKED/COMPLETED/CANCELLED. We notify cases that are
# in-flight (ACTIVE) or stalled awaiting action (BLOCKED) — a rule change is
# exactly the kind of event that can matter to a blocked case. DRAFT (not yet
# started), COMPLETED and CANCELLED (finished) are excluded. Overridable via the
# `statuses` argument if a caller wants a narrower or wider set.
ACTIVE_CASE_STATUSES: Sequence[str] = ("ACTIVE", "BLOCKED")

_FIND_CASES_SQL = text(
    """
    SELECT DISTINCT c.case_id::text AS case_id
    FROM rce.rule_citations rc
    JOIN rce.cases c ON c.case_id = rc.case_id
    WHERE rc.rule_version_id = :rule_version_id
      AND c.status = ANY(:statuses)
    """
)


def find_cases_citing_rule_version(
    conn: Any,
    rule_version_id: str,
    statuses: Sequence[str] = ACTIVE_CASE_STATUSES,
) -> List[str]:
    """Return the sorted, de-duplicated active case_ids citing ``rule_version_id``.

    ``conn`` is any executor exposing ``.execute(sql, params).mappings().all()``
    (a SQLAlchemy Connection or Session). Dedup/sort are applied in Python as
    well as SQL so the result is stable regardless of driver row ordering.
    """
    rows = conn.execute(
        _FIND_CASES_SQL,
        {"rule_version_id": rule_version_id, "statuses": list(statuses)},
    ).mappings().all()
    return sorted({str(r["case_id"]) for r in rows})


def _default_engine() -> Any:
    # Imported lazily so importing this module never triggers engine creation
    # (and so tests can inject a fake engine without a live DATABASE_URL).
    from ..db import engine

    return engine


def find_active_cases_for_rule_version(
    rule_version_id: str,
    statuses: Sequence[str] = ACTIVE_CASE_STATUSES,
    engine: Optional[Any] = None,
) -> List[str]:
    """Convenience wrapper that opens the canonical app engine and runs the query.

    Degrades to ``[]`` (rather than raising) if the ``rce.*`` schema is not
    present yet — its writer is a separate task, so the table may be absent or
    empty in some environments.
    """
    eng = engine or _default_engine()
    try:
        with eng.connect() as conn:
            return find_cases_citing_rule_version(conn, rule_version_id, statuses)
    except Exception as exc:  # rce.* tables not present / transient DB error
        log.warning("active_case_finder: query failed, returning empty set: %s", exc)
        return []
