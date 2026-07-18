"""AIQ-1602 Seg 4: HR-submitted preferred-supplier moderation queue.

HR proposes a supplier (minimal fields) → a `pending` row here → a platform
admin approves it into the shared public.suppliers registry (via
supplier_registry.create_supplier) or rejects it. HR never writes the registry
directly. Per-company scoped by the caller (backend uses the service-role key;
RLS on the table is defense-in-depth).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ..db import SessionLocal
from .supplier_registry import create_supplier

log = logging.getLogger(__name__)

_COLS = (
    "id, company_id, submitted_by_user_id, name, service_category, "
    "coverage_scope_type, country_code, city_name, contact_email, status, "
    "reviewed_by, reviewed_at, review_notes, created_supplier_id, "
    "created_at, updated_at"
)


class SubmissionNotFound(Exception):
    """No submission with the given id."""


class SubmissionNotPending(Exception):
    """Submission has already been approved/rejected."""


def _row_to_dict(row: Any) -> Dict[str, Any]:
    d = dict(row)
    for k, v in list(d.items()):
        if v is not None and not isinstance(v, (str, int, float, bool)):
            d[k] = str(v)
    return d


def create(
    *,
    company_id: str,
    submitted_by: Optional[str],
    name: str,
    service_category: str,
    coverage_scope_type: str = "country",
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    contact_email: Optional[str] = None,
) -> Dict[str, Any]:
    name = (name or "").strip()
    service_category = (service_category or "").strip()
    if not name or not service_category:
        raise ValueError("name and service_category are required")
    row_id = str(uuid.uuid4())
    with SessionLocal() as s:
        s.execute(
            text(
                "INSERT INTO hr_supplier_submissions "
                "(id, company_id, submitted_by_user_id, name, service_category, "
                " coverage_scope_type, country_code, city_name, contact_email, status) "
                "VALUES (:id, :co, :by, :name, :cat, :scope, :cc, :city, :email, 'pending')"
            ),
            {
                "id": row_id, "co": company_id, "by": submitted_by, "name": name,
                "cat": service_category, "scope": coverage_scope_type or "country",
                "cc": country_code, "city": city_name, "email": contact_email,
            },
        )
        s.commit()
        row = s.execute(
            text(f"SELECT {_COLS} FROM hr_supplier_submissions WHERE id = :id"),
            {"id": row_id},
        ).mappings().first()
    return _row_to_dict(row)


def list_for_company(company_id: str) -> List[Dict[str, Any]]:
    with SessionLocal() as s:
        rows = s.execute(
            text(
                f"SELECT {_COLS} FROM hr_supplier_submissions "
                "WHERE company_id = :co ORDER BY created_at DESC LIMIT 200"
            ),
            {"co": company_id},
        ).mappings().all()
    return [_row_to_dict(r) for r in rows]


def list_all(status: Optional[str] = None) -> List[Dict[str, Any]]:
    query = f"SELECT {_COLS} FROM hr_supplier_submissions"
    params: Dict[str, Any] = {}
    if status:
        query += " WHERE status = :st"
        params["st"] = status
    query += " ORDER BY created_at DESC LIMIT 500"
    with SessionLocal() as s:
        rows = s.execute(text(query), params).mappings().all()
    return [_row_to_dict(r) for r in rows]


def approve(*, submission_id: str, reviewed_by: Optional[str]) -> Dict[str, Any]:
    """Approve a pending submission into public.suppliers. Raises
    SubmissionNotFound / SubmissionNotPending; create_supplier raises
    DuplicateSupplierError on a name clash (submission stays pending)."""
    with SessionLocal() as s:
        row = s.execute(
            text(f"SELECT {_COLS} FROM hr_supplier_submissions WHERE id = :id"),
            {"id": submission_id},
        ).mappings().first()
        if not row:
            raise SubmissionNotFound(submission_id)
        if row["status"] != "pending":
            raise SubmissionNotPending(f"submission is already {row['status']}")

        capability = {
            "service_category": row["service_category"],
            "coverage_scope_type": row["coverage_scope_type"] or "country",
            "country_code": row["country_code"],
            "city_name": row["city_name"],
        }
        # create_supplier commits internally. If it raises (e.g. duplicate name),
        # the submission is left untouched (still pending) for the admin to retry.
        supplier = create_supplier(
            s,
            {
                "name": row["name"],
                "contact_email": row["contact_email"],
                "status": "active",
                "source": "customer_upload",
                "source_reference": f"hr_submission:{submission_id}",
                "capabilities": [capability],
            },
        )
        supplier_id = str(supplier.get("id"))
        now = datetime.utcnow().isoformat()
        s.execute(
            text(
                "UPDATE hr_supplier_submissions SET status = 'approved', "
                "reviewed_by = :by, reviewed_at = :now, created_supplier_id = :sid, "
                "updated_at = :now WHERE id = :id"
            ),
            {"by": reviewed_by, "now": now, "sid": supplier_id, "id": submission_id},
        )
        s.commit()
        out = s.execute(
            text(f"SELECT {_COLS} FROM hr_supplier_submissions WHERE id = :id"),
            {"id": submission_id},
        ).mappings().first()
    return _row_to_dict(out)


def reject(*, submission_id: str, reviewed_by: Optional[str], notes: str) -> Dict[str, Any]:
    notes = (notes or "").strip()
    if not notes:
        raise ValueError("rejection notes are required")
    with SessionLocal() as s:
        row = s.execute(
            text("SELECT status FROM hr_supplier_submissions WHERE id = :id"),
            {"id": submission_id},
        ).mappings().first()
        if not row:
            raise SubmissionNotFound(submission_id)
        if row["status"] != "pending":
            raise SubmissionNotPending(f"submission is already {row['status']}")
        now = datetime.utcnow().isoformat()
        s.execute(
            text(
                "UPDATE hr_supplier_submissions SET status = 'rejected', "
                "reviewed_by = :by, reviewed_at = :now, review_notes = :notes, "
                "updated_at = :now WHERE id = :id"
            ),
            {"by": reviewed_by, "now": now, "notes": notes, "id": submission_id},
        )
        s.commit()
        out = s.execute(
            text(f"SELECT {_COLS} FROM hr_supplier_submissions WHERE id = :id"),
            {"id": submission_id},
        ).mappings().first()
    return _row_to_dict(out)
