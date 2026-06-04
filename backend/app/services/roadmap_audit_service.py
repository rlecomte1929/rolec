"""
P1-08 · Roadmap audit-trail service (AIQ-202 parent).

Read/write helpers over ``rce.roadmap_audit_log`` — the append-only audit trail
created by P1-08a (AIQ-639, migration 20260605500000). Three concerns live here:

  - append_roadmap_audit       (P1-08b / AIQ-640) — the writer. One immutable
                               row per roadmap-generation / specialist-correction
                               event, recording the exact rule_version that
                               produced the decision. Accepts a caller-owned
                               connection so the audit write is *transactional
                               with the roadmap write* (P1-08 Technical Constraint).
  - reconstruct_roadmap_as_of  (P1-08c / AIQ-641) — "show me the roadmap as it
                               existed on date X": for every rule cited on a case,
                               the rule_version that was in effect at that date.
  - export_case_audit          (P1-08e / AIQ-643) — schema-versioned JSON dump of
                               every audit row + the rule_version content recorded
                               at generation time, for legal proceedings.

DB access mirrors backend/app/routers/hr_case_audit.py (C1-16): raw SQL via the
legacy ``database.db`` engine, since this domain reads the ``rce.*`` ontology that
the modular ORM layer does not model.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ...database import db


# Mirrors the table CHECK constraint (rce.roadmap_audit_log.generated_by).
VALID_GENERATED_BY = ("AI", "SPECIALIST")

# Bump when the export JSON shape changes (P1-08e: "Schema-versioned").
AUDIT_EXPORT_SCHEMA_VERSION = "1.0"


_INSERT_AUDIT_SQL = """
INSERT INTO rce.roadmap_audit_log (
    case_id, step_id, rule_version_id, source_url, source_fetch_date,
    generated_by, generated_at, confidence_at_time, specialist_corrections
) VALUES (
    :case_id, :step_id, :rule_version_id, :source_url, :source_fetch_date,
    :generated_by, COALESCE(:generated_at, now()), :confidence_at_time,
    CAST(:specialist_corrections AS JSONB)
)
RETURNING roadmap_audit_log_id
"""


def append_roadmap_audit(
    *,
    case_id: str,
    rule_version_id: str,
    generated_by: str,
    step_id: Optional[str] = None,
    source_url: Optional[str] = None,
    source_fetch_date: Optional[date] = None,
    generated_at: Optional[datetime] = None,
    confidence_at_time: Optional[float] = None,
    specialist_corrections: Optional[Any] = None,
    conn: Optional[Any] = None,
) -> str:
    """Append one immutable audit row and return its id (P1-08b).

    The table is append-only (no UPDATE/DELETE) — this is the *only* write path.

    Transactionality: pass ``conn`` (an open SQLAlchemy connection inside the
    roadmap-write transaction) so the audit row commits or rolls back together
    with the roadmap. When ``conn`` is omitted the helper opens its own
    autocommitting transaction (``db.engine.begin()``).

    Args:
        case_id: rce.cases.case_id the decision belongs to.
        rule_version_id: the exact rce.rule_versions row that produced the step.
        generated_by: 'AI' or 'SPECIALIST'.
        step_id: the rce.steps row produced, if step-scoped (nullable).
        source_url / source_fetch_date: provenance of the cited rule.
        generated_at: decision timestamp (defaults to now() in SQL).
        confidence_at_time: model confidence at generation (0..1).
        specialist_corrections: JSON-serialisable record of any corrections.
    """
    if generated_by not in VALID_GENERATED_BY:
        raise ValueError(
            f"generated_by must be one of {VALID_GENERATED_BY}, got {generated_by!r}"
        )

    import json

    params = {
        "case_id": case_id,
        "step_id": step_id,
        "rule_version_id": rule_version_id,
        "source_url": source_url,
        "source_fetch_date": source_fetch_date,
        "generated_by": generated_by,
        "generated_at": generated_at,
        "confidence_at_time": confidence_at_time,
        "specialist_corrections": (
            json.dumps(specialist_corrections)
            if specialist_corrections is not None
            else None
        ),
    }

    if conn is not None:
        row = conn.execute(text(_INSERT_AUDIT_SQL), params).fetchone()
    else:
        with db.engine.begin() as own_conn:
            row = own_conn.execute(text(_INSERT_AUDIT_SQL), params).fetchone()
    return str(row[0])


# ---------------------------------------------------------------------------
# P1-08c — as_of reconstruction
# ---------------------------------------------------------------------------

# For every (step, rule) cited on the case, re-resolve the rule_version that was
# *in effect on the as_of date* via a LATERAL pick of the latest version whose
# [effective_from, effective_to) window contains the date. With no as_of we use
# CURRENT_DATE, so the default reconstruction returns the current rule text.
_RECONSTRUCT_SQL = """
WITH cited AS (
    SELECT DISTINCT
        ral.step_id,
        rv.rule_id,
        ral.rule_version_id        AS generated_rule_version_id,
        ral.generated_by,
        ral.generated_at,
        ral.source_url             AS audit_source_url,
        ral.confidence_at_time
    FROM rce.roadmap_audit_log ral
    JOIN rce.rule_versions rv ON rv.rule_version_id = ral.rule_version_id
    WHERE ral.case_id = :case_id
      AND (:as_of IS NULL OR ral.generated_at::date <= :as_of)
)
SELECT
    cited.step_id,
    cited.rule_id,
    cited.generated_rule_version_id,
    cited.generated_by,
    cited.generated_at,
    cited.audit_source_url,
    cited.confidence_at_time,
    eff.rule_version_id            AS effective_rule_version_id,
    eff.version_label,
    eff.effective_from,
    eff.effective_to,
    eff.predicate_dsl,
    eff.body,
    eff.source_url                 AS rule_source_url
FROM cited
LEFT JOIN LATERAL (
    SELECT rv2.*
    FROM rce.rule_versions rv2
    WHERE rv2.rule_id = cited.rule_id
      AND rv2.effective_from <= COALESCE(:as_of, CURRENT_DATE)
      AND (rv2.effective_to IS NULL OR rv2.effective_to > COALESCE(:as_of, CURRENT_DATE))
    ORDER BY rv2.effective_from DESC
    LIMIT 1
) eff ON TRUE
ORDER BY cited.generated_at, cited.step_id
"""


def _jsonify(value: Any) -> Any:
    """Make a DB cell JSON-safe (dates/datetimes → ISO strings)."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def reconstruct_roadmap_as_of(
    case_id: str, as_of: Optional[date] = None
) -> List[Dict[str, Any]]:
    """Return each cited roadmap step with the rule_version in effect on ``as_of``.

    P1-08c. ``as_of=None`` → current state (CURRENT_DATE). For a rule that
    changed on date D, reconstructing at D-1 yields the old version's body and
    at D+1 the new version's body.
    """
    with db.engine.connect() as conn:
        rows = (
            conn.execute(text(_RECONSTRUCT_SQL), {"case_id": case_id, "as_of": as_of})
            .mappings()
            .all()
        )
    return [{k: _jsonify(v) for k, v in dict(r).items()} for r in rows]


# ---------------------------------------------------------------------------
# P1-08e — legal export
# ---------------------------------------------------------------------------

# Every audit row for the case, joined to the rule_version content RECORDED AT
# GENERATION TIME (not re-resolved) — the exact state that produced each step.
_EXPORT_SQL = """
SELECT
    ral.roadmap_audit_log_id,
    ral.case_id,
    ral.step_id,
    ral.rule_version_id,
    ral.source_url,
    ral.source_fetch_date,
    ral.generated_by,
    ral.generated_at,
    ral.confidence_at_time,
    ral.specialist_corrections,
    ral.created_at,
    rv.rule_id,
    rv.version_label,
    rv.effective_from,
    rv.effective_to,
    rv.predicate_dsl,
    rv.body                AS rule_body,
    rv.source_url          AS rule_source_url,
    rv.captured_at         AS rule_captured_at
FROM rce.roadmap_audit_log ral
JOIN rce.rule_versions rv ON rv.rule_version_id = ral.rule_version_id
WHERE ral.case_id = :case_id
ORDER BY ral.generated_at, ral.roadmap_audit_log_id
"""


def export_case_audit(case_id: str) -> Dict[str, Any]:
    """Schema-versioned JSON export of the full audit trail for a case (P1-08e)."""
    with db.engine.connect() as conn:
        rows = (
            conn.execute(text(_EXPORT_SQL), {"case_id": case_id}).mappings().all()
        )
    entries = [{k: _jsonify(v) for k, v in dict(r).items()} for r in rows]
    return {
        "schema_version": AUDIT_EXPORT_SCHEMA_VERSION,
        "case_id": case_id,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "entry_count": len(entries),
        "audit_log": entries,
    }
