"""
[P1-6] Employee tier assignment API.

Tier is the key personalisation primitive used by AI assistant retrieval,
the policy summary page, and benefit comparison — every employee belongs to
exactly one active tier per company, persisted in `public.employee_tiers`
(see migration 20260522120000).

Endpoints
─────────
GET  /api/employees/{employee_id}              → profile + current tier
POST /api/employees/{employee_id}/tier         → single assignment
POST /api/employees/import                     → bulk CSV import

CSV format
──────────
The first row must be the header: `name,email,tier_name`. Empty cells in
the header are ignored, extra columns are silently dropped.

Idempotency
───────────
The CSV importer is idempotent over (company_id, email). Re-importing the
same email — same or different tier — archives the previous active row by
setting `end_date = now()` and inserts a fresh active row in the same
transaction. The DB's `employee_tiers_current_unique` partial index
guarantees at most one active row per employee.

Validation rules
────────────────
- tier_name must exist in the same company's policy_tiers (case-insensitive
  match — HR routinely capitalises inconsistently in their HRIS exports).
- email is required; rows with a blank email are reported as errors.
- Unknown emails (no profiles row) are reported as errors. We do NOT
  auto-create profiles here — that's the responsibility of the HRIS sync
  or the auth signup flow.

Audit log
─────────
Every successful assignment writes a row to `public.audit_log`
(action_type='employee_tier.assigned'). The schema is the legacy text-based
one (created 2026-02-21) so we serialise metadata to JSON text.

Tests live in `backend/tests/test_employee_tiers.py`.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import get_current_user
from ...database import db


router = APIRouter(prefix="/api/employees", tags=["employee-tiers"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dialect helper — same pattern as case_form_pdf.py
# ---------------------------------------------------------------------------

def _t(name: str) -> str:
    try:
        dialect_name = db.engine.dialect.name
    except Exception:
        dialect_name = "postgresql"
    return f"public.{name}" if dialect_name == "postgresql" else name


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Auth: HR / admin guard. Returns the profile dict (id + company_id + role).
# ---------------------------------------------------------------------------

def _require_hr_or_admin(user: Dict[str, Any]) -> Dict[str, Any]:
    """Return the caller's profile when they're HR or admin, else 403."""
    role = (user.get("role") or "").lower()
    if role not in ("hr", "admin"):
        raise HTTPException(status_code=403, detail="HR or admin role required")
    company_id = user.get("company_id")
    if not company_id and role != "admin":
        # Admins may operate across companies; HR must be scoped to one.
        raise HTTPException(status_code=403, detail="HR user must have a company_id")
    return {
        "id": user.get("id") or user.get("sub"),
        "company_id": company_id,
        "role": role,
    }


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CurrentTier(BaseModel):
    policy_tier_id: str
    tier_name: str
    assigned_at: str
    assigned_by: Optional[str] = None


class EmployeeWithTier(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    company_id: Optional[str] = None
    role: Optional[str] = None
    tier: Optional[CurrentTier] = None


class AssignTierPayload(BaseModel):
    tier_name: str = Field(..., min_length=1)


class TierRowError(BaseModel):
    row: int  # 1-indexed including header (so first data row is row=2)
    email: Optional[str] = None
    message: str


class TierRowSuccess(BaseModel):
    row: int
    email: str
    tier_name: str
    employee_id: str


class TierImportResponse(BaseModel):
    successes: List[TierRowSuccess]
    errors: List[TierRowError]
    total_rows: int


# ---------------------------------------------------------------------------
# Internal helpers — DB I/O
# ---------------------------------------------------------------------------

def _fetch_profile_by_email(conn: Any, company_id: str, email: str) -> Optional[Dict[str, Any]]:
    """Return profile row for (company_id, email) or None."""
    row = conn.execute(
        text(
            f"SELECT id, email, full_name, company_id, role "
            f"FROM {_t('profiles')} "
            f"WHERE company_id = :cid AND lower(email) = lower(:email) "
            f"LIMIT 1"
        ),
        {"cid": company_id, "email": email},
    ).mappings().first()
    return dict(row) if row else None


def _fetch_profile_by_id(conn: Any, employee_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            f"SELECT id, email, full_name, company_id, role "
            f"FROM {_t('profiles')} WHERE id = :id"
        ),
        {"id": employee_id},
    ).mappings().first()
    return dict(row) if row else None


def _fetch_policy_tier(conn: Any, company_id: str, tier_name: str) -> Optional[Dict[str, Any]]:
    """Case-insensitive tier lookup scoped to a company."""
    row = conn.execute(
        text(
            f"SELECT id, name FROM {_t('policy_tiers')} "
            f"WHERE company_id = :cid AND lower(name) = lower(:name) "
            f"AND is_active = true "
            f"LIMIT 1"
        ),
        {"cid": company_id, "name": tier_name},
    ).mappings().first()
    return dict(row) if row else None


def _fetch_current_tier(conn: Any, employee_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            f"SELECT policy_tier_id, tier_name, assigned_at, assigned_by "
            f"FROM {_t('employee_tiers')} "
            f"WHERE employee_id = :eid AND end_date IS NULL "
            f"LIMIT 1"
        ),
        {"eid": employee_id},
    ).mappings().first()
    return dict(row) if row else None


def _archive_active_tier(conn: Any, employee_id: str) -> None:
    """Set end_date=now() on the current active row, if any."""
    conn.execute(
        text(
            f"UPDATE {_t('employee_tiers')} "
            f"SET end_date = :now "
            f"WHERE employee_id = :eid AND end_date IS NULL"
        ),
        {"eid": employee_id, "now": _now_iso()},
    )


def _insert_tier_row(
    conn: Any,
    *,
    employee_id: str,
    company_id: str,
    policy_tier_id: str,
    tier_name: str,
    assigned_by: Optional[str],
) -> str:
    """Insert a new active tier row and return its id."""
    new_id = str(uuid.uuid4())
    conn.execute(
        text(
            f"INSERT INTO {_t('employee_tiers')} "
            f"  (id, employee_id, company_id, policy_tier_id, tier_name, "
            f"   assigned_by, assigned_at) "
            f"VALUES (:id, :eid, :cid, :ptid, :tname, :by, :now)"
        ),
        {
            "id": new_id,
            "eid": employee_id,
            "cid": company_id,
            "ptid": policy_tier_id,
            "tname": tier_name,
            "by": assigned_by,
            "now": _now_iso(),
        },
    )
    return new_id


def _write_audit_log(
    conn: Any,
    *,
    actor_id: str,
    employee_id: str,
    company_id: str,
    tier_name: str,
    policy_tier_id: str,
) -> None:
    """
    Append to public.audit_log. The legacy schema is text-only with a
    metadata_json TEXT column, so we serialise the payload to JSON.

    Audit failures must never break the assignment — they're logged but
    swallowed.
    """
    try:
        conn.execute(
            text(
                f"INSERT INTO {_t('audit_log')} "
                f"  (id, actor_user_id, action_type, target_type, target_id, "
                f"   metadata_json, created_at) "
                f"VALUES (:id, :actor, 'employee_tier.assigned', 'profile', "
                f"        :target, :meta, :now)"
            ),
            {
                "id": str(uuid.uuid4()),
                "actor": actor_id,
                "target": employee_id,
                "meta": json.dumps({
                    "company_id": company_id,
                    "policy_tier_id": policy_tier_id,
                    "tier_name": tier_name,
                }),
                "now": _now_iso(),
            },
        )
    except Exception:
        logger.warning(
            "employee_tiers: audit_log write failed employee_id=%s", employee_id,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Assignment core — used by both the single-employee and bulk endpoints
# ---------------------------------------------------------------------------

def _assign_tier(
    conn: Any,
    *,
    employee_id: str,
    company_id: str,
    tier_name: str,
    assigned_by: str,
) -> str:
    """
    Validate the tier, archive the existing active row (if any), insert
    the new active row, and write to audit_log. Returns the new row id.

    Raises HTTPException(422) if the tier_name is unknown.
    Raises HTTPException(409) if the employee belongs to a different
    company than `company_id` — this is a HR safety guard, not just a
    data check.
    """
    policy_tier = _fetch_policy_tier(conn, company_id, tier_name)
    if not policy_tier:
        raise HTTPException(
            status_code=422,
            detail=(
                f"tier_name '{tier_name}' is not defined for this company. "
                "Create it in the policy builder first."
            ),
        )

    # Belt-and-suspenders: confirm the employee is in this company.
    emp = _fetch_profile_by_id(conn, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    if str(emp.get("company_id") or "") != str(company_id):
        raise HTTPException(
            status_code=409,
            detail="Employee belongs to a different company",
        )

    _archive_active_tier(conn, employee_id)
    new_id = _insert_tier_row(
        conn,
        employee_id=employee_id,
        company_id=company_id,
        policy_tier_id=str(policy_tier["id"]),
        tier_name=str(policy_tier["name"]),  # canonical casing from DB
        assigned_by=assigned_by,
    )
    _write_audit_log(
        conn,
        actor_id=assigned_by,
        employee_id=employee_id,
        company_id=company_id,
        tier_name=str(policy_tier["name"]),
        policy_tier_id=str(policy_tier["id"]),
    )
    return new_id


# ---------------------------------------------------------------------------
# Endpoint: GET /api/employees/{employee_id}
# ---------------------------------------------------------------------------

@router.get("/{employee_id}", response_model=EmployeeWithTier)
def get_employee_with_tier(
    employee_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> EmployeeWithTier:
    """Return the employee's profile + their current active tier (if any)."""
    actor = _require_hr_or_admin(user)
    try:
        with db.engine.connect() as conn:
            profile = _fetch_profile_by_id(conn, employee_id)
            if not profile:
                raise HTTPException(status_code=404, detail="Employee not found")
            # HR scoped to their company; admins can read across.
            if actor["role"] != "admin" and str(profile.get("company_id") or "") != str(actor["company_id"]):
                raise HTTPException(status_code=403, detail="Cross-company access denied")

            current = _fetch_current_tier(conn, employee_id)
    except HTTPException:
        raise
    except Exception:
        logger.exception("get_employee_with_tier: failed employee_id=%s", employee_id)
        raise HTTPException(status_code=500, detail="Failed to load employee")

    tier_dto: Optional[CurrentTier] = None
    if current:
        tier_dto = CurrentTier(
            policy_tier_id=str(current["policy_tier_id"]),
            tier_name=str(current["tier_name"]),
            assigned_at=str(current["assigned_at"]),
            assigned_by=str(current["assigned_by"]) if current.get("assigned_by") else None,
        )

    return EmployeeWithTier(
        id=str(profile["id"]),
        email=str(profile["email"]),
        full_name=profile.get("full_name"),
        company_id=str(profile.get("company_id")) if profile.get("company_id") else None,
        role=profile.get("role"),
        tier=tier_dto,
    )


# ---------------------------------------------------------------------------
# Endpoint: POST /api/employees/{employee_id}/tier
# ---------------------------------------------------------------------------

@router.post("/{employee_id}/tier", response_model=EmployeeWithTier)
def assign_single_tier(
    employee_id: str,
    payload: AssignTierPayload,
    user: Dict[str, Any] = Depends(get_current_user),
) -> EmployeeWithTier:
    """Assign or update an employee's tier (single-row write)."""
    actor = _require_hr_or_admin(user)
    if not actor["company_id"]:
        # Admin without a company_id needs the employee's company_id to
        # validate the tier — we'll grab it from the profile.
        pass

    try:
        with db.engine.begin() as conn:
            emp = _fetch_profile_by_id(conn, employee_id)
            if not emp:
                raise HTTPException(status_code=404, detail="Employee not found")
            company_id = actor["company_id"] or emp.get("company_id")
            if not company_id:
                raise HTTPException(
                    status_code=409,
                    detail="Employee has no company_id; cannot validate tier",
                )
            _assign_tier(
                conn,
                employee_id=employee_id,
                company_id=str(company_id),
                tier_name=payload.tier_name,
                assigned_by=actor["id"],
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "assign_single_tier: failed employee_id=%s", employee_id
        )
        raise HTTPException(status_code=500, detail="Failed to assign tier")

    # Reload for the response — guarantees we return what was committed.
    return get_employee_with_tier(employee_id, user)


# ---------------------------------------------------------------------------
# Endpoint: POST /api/employees/import
# ---------------------------------------------------------------------------

@router.post("/import", response_model=TierImportResponse)
async def import_employee_tiers_csv(
    file: UploadFile = File(..., description="CSV with header: name,email,tier_name"),
    user: Dict[str, Any] = Depends(get_current_user),
) -> TierImportResponse:
    """
    Bulk-assign tiers from a CSV upload. Returns per-row success/error
    breakdown. Each row is processed in its own SAVEPOINT so a single bad
    row does not abort the whole batch.
    """
    actor = _require_hr_or_admin(user)
    if not actor["company_id"]:
        raise HTTPException(
            status_code=400,
            detail="Bulk import requires the caller to be scoped to a company",
        )
    company_id = str(actor["company_id"])

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    try:
        text_content = raw.decode("utf-8-sig")  # tolerate BOM from Excel
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="CSV must be UTF-8")

    reader = csv.DictReader(io.StringIO(text_content))
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV is missing a header row")

    # Header normalisation — accept any column casing but require the three keys.
    normalised = {name.strip().lower(): name for name in reader.fieldnames if name}
    required = {"email", "tier_name"}
    missing = required - set(normalised.keys())
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"CSV header missing required column(s): {sorted(missing)}",
        )
    email_col = normalised["email"]
    tier_col = normalised["tier_name"]

    successes: List[TierRowSuccess] = []
    errors: List[TierRowError] = []
    total_rows = 0

    # Each row in its own transaction so failures don't poison the batch.
    for idx, raw_row in enumerate(reader, start=2):  # start=2 → row 2 is first data row
        total_rows += 1
        email = (raw_row.get(email_col) or "").strip()
        tier_name = (raw_row.get(tier_col) or "").strip()

        if not email:
            errors.append(TierRowError(row=idx, message="email is required"))
            continue
        if not tier_name:
            errors.append(TierRowError(row=idx, email=email, message="tier_name is required"))
            continue

        try:
            with db.engine.begin() as conn:
                profile = _fetch_profile_by_email(conn, company_id, email)
                if not profile:
                    errors.append(TierRowError(
                        row=idx, email=email,
                        message="No profile found for this email in your company",
                    ))
                    continue

                try:
                    _assign_tier(
                        conn,
                        employee_id=str(profile["id"]),
                        company_id=company_id,
                        tier_name=tier_name,
                        assigned_by=actor["id"],
                    )
                except HTTPException as he:
                    errors.append(TierRowError(
                        row=idx, email=email,
                        message=str(he.detail),
                    ))
                    continue

                successes.append(TierRowSuccess(
                    row=idx, email=email, tier_name=tier_name,
                    employee_id=str(profile["id"]),
                ))
        except Exception as exc:
            logger.exception(
                "employee_tiers.import: row %d email=%s failed", idx, email
            )
            errors.append(TierRowError(
                row=idx, email=email,
                message=f"Unexpected error: {type(exc).__name__}",
            ))

    return TierImportResponse(
        successes=successes,
        errors=errors,
        total_rows=total_rows,
    )
