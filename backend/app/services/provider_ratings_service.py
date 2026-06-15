"""
CATALOG-3 / AIQ-1067 — Employee provider ratings -> live recommendation signal.

An employee rates a provider (1-5) for a case. We persist the rating
idempotently (one per employee+supplier+case) and recompute the supplier's
aggregate into `supplier_scoring_metadata.average_rating`/`review_count` — the
exact value the recommendation engine scores via
`supplier_registry.search_by_service_destination`. So ratings feed
recommendations with no extra wiring on the recs side.

Raw SQL (portable across Postgres + the SQLite test harness): ids are generated
in Python and upserts use `ON CONFLICT ... DO UPDATE` (supported by both).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text

from ..db import SessionLocal


def recompute_supplier_aggregate(session, supplier_id: str) -> Dict[str, Any]:
    """Recompute avg + count from provider_ratings and upsert into
    supplier_scoring_metadata. Returns the new aggregate. Caller manages the
    transaction/commit."""
    row = session.execute(
        text(
            "SELECT AVG(score) AS avg_score, COUNT(*) AS cnt "
            "FROM provider_ratings WHERE supplier_id = :sid"
        ),
        {"sid": supplier_id},
    ).first()
    avg_score = float(row.avg_score) if row and row.avg_score is not None else None
    count = int(row.cnt) if row and row.cnt is not None else 0

    session.execute(
        text(
            "INSERT INTO supplier_scoring_metadata (supplier_id, average_rating, review_count) "
            "VALUES (:sid, :avg, :cnt) "
            "ON CONFLICT (supplier_id) DO UPDATE SET "
            "average_rating = excluded.average_rating, "
            "review_count = excluded.review_count"
        ),
        {"sid": supplier_id, "avg": avg_score, "cnt": count},
    )
    return {"average_rating": avg_score, "review_count": count}


def record_rating(
    *,
    employee_id: str,
    company_id: str,
    supplier_id: str,
    case_id: str,
    score: int,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    """Idempotently record an employee's rating for a provider on a case, then
    recompute the supplier aggregate. Re-rating the same (employee, supplier,
    case) updates the existing row rather than inserting a duplicate."""
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        session.execute(
            text(
                "INSERT INTO provider_ratings "
                "(id, employee_id, company_id, supplier_id, case_id, score, comment, created_at, updated_at) "
                "VALUES (:id, :emp, :company, :sid, :case, :score, :comment, :created, :updated) "
                "ON CONFLICT (employee_id, supplier_id, case_id) DO UPDATE SET "
                "score = excluded.score, comment = excluded.comment, updated_at = excluded.updated_at"
            ),
            {
                "id": str(uuid.uuid4()),
                "emp": employee_id,
                "company": company_id,
                "sid": supplier_id,
                "case": case_id,
                "score": score,
                "comment": comment,
                "created": now,
                "updated": now,
            },
        )
        aggregate = recompute_supplier_aggregate(session, supplier_id)
        session.commit()
    return aggregate
