"""[AUDIT-C1.6a] Companies-domain DB methods, extracted from backend/database.py.

These were methods on the monolithic ``Database`` class; they live here as a
mixin (:class:`CompaniesMixin`) that ``Database`` inherits, so every caller keeps
working unchanged via normal MRO. Pure relocation; ``..database`` module
helpers are imported lazily in-method to avoid an import cycle.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
import json
import logging
import os
import re
import time
import uuid

from sqlalchemy import text

from ..db_config import DATABASE_URL as _raw_url

log = logging.getLogger(__name__)

_is_sqlite = _raw_url.startswith("sqlite")


class CompaniesMixin:
    """Companies-domain methods mixed into :class:`backend.database.Database`."""

    def list_assignments_for_company(
        self, company_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List assignments belonging to a company (via case or HR ownership). Used for HR company-scoped view."""
        rows, _ = self._list_assignments_for_company_core(
            company_id, limit=None, offset=0, search=None, status=None, destination=None, request_id=request_id
        )
        return rows

    def list_assignments_for_company_paginated(
        self,
        company_id: str,
        *,
        limit: int = 25,
        offset: int = 0,
        search: Optional[str] = None,
        status: Optional[str] = None,
        destination: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List assignments for company with server-side filter and pagination. Returns (rows, total_count)."""
        return self._list_assignments_for_company_core(
            company_id, limit=limit, offset=offset, search=search, status=status, destination=destination, request_id=request_id
        )

    def _list_assignments_for_company_core(
        self,
        company_id: str,
        *,
        limit: Optional[int] = None,
        offset: int = 0,
        search: Optional[str] = None,
        status: Optional[str] = None,
        destination: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Core query for company assignments with optional filters and pagination."""
        # B3-fix-v4: ensure init before opening the transaction (same pattern as create_assignment).
        self.ensure_initialized()
        if _is_sqlite:
            join_on_cases = "rc.id = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"
        else:
            join_on_cases = "rc.id::text = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"

        base_where = (
            "(rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid))"
            " AND a.archived_at IS NULL"
        )
        params: Dict[str, Any] = {"cid": company_id}
        extras: List[str] = []

        if search and (s := search.strip()):
            pattern = f"%{s}%"
            params["search"] = pattern
            extras.append(
                "(LOWER(COALESCE(a.employee_identifier,'')) LIKE LOWER(:search) OR "
                "LOWER(COALESCE(a.employee_first_name,'')) LIKE LOWER(:search) OR "
                "LOWER(COALESCE(a.employee_last_name,'')) LIKE LOWER(:search))"
            )
        if status and status.strip() and status.lower() != "all":
            params["status"] = status.strip()
            extras.append("a.status = :status")
        if destination and (d := destination.strip()):
            dest_pattern = f"%{d}%"
            params["dest"] = dest_pattern
            extras.append(
                "(LOWER(COALESCE(rc.host_country,'')) LIKE LOWER(:dest) OR LOWER(COALESCE(rc.home_country,'')) LIKE LOWER(:dest))"
            )

        where_clause = base_where + (" AND " + " AND ".join(extras) if extras else "")
        limit_clause = f" LIMIT {int(limit)}" if limit is not None else ""
        offset_clause = f" OFFSET {int(offset)}" if offset else ""

        count_sql = f"""
            SELECT COUNT(*) AS n FROM case_assignments a
            LEFT JOIN relocation_cases rc ON {join_on_cases}
            LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
            WHERE {where_clause}
        """
        data_sql = f"""
            SELECT a.* FROM case_assignments a
            LEFT JOIN relocation_cases rc ON {join_on_cases}
            LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
            WHERE {where_clause}
            ORDER BY a.created_at DESC
            {limit_clause}{offset_clause}
        """
        # B3-fix-v3: use engine.begin() so SET LOCAL applies to both queries
        # (PgBouncer transaction mode routes entire BEGIN…COMMIT to same backend).
        with self.engine.begin() as conn:
            if not _is_sqlite:
                try:
                    conn.execute(text("SET LOCAL statement_timeout = '7500ms'"))
                    conn.execute(text("SET LOCAL lock_timeout = '5000ms'"))
                except Exception:
                    pass
            total_row = self._exec(
                conn, count_sql, params, op_name="list_assignments_for_company_count", request_id=request_id
            ).fetchone()
            total = int(total_row._mapping["n"]) if total_row else 0
            rows = self._exec(
                conn, data_sql, params, op_name="list_assignments_for_company", request_id=request_id
            ).fetchall()
        return self._rows_to_list(rows), total

    def list_assignments_for_company_with_details(
        self, company_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Assignments for company with employee_name, destination, status for admin company detail."""
        if _is_sqlite:
            join_on_cases = "rc.id = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"
        else:
            join_on_cases = "rc.id::text = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"

        sql = f"""
            SELECT a.id, a.status,
                   COALESCE(TRIM(emp_p.full_name),
                            NULLIF(TRIM(COALESCE(a.employee_first_name, '') || ' ' || COALESCE(a.employee_last_name, '')), ''),
                            a.employee_identifier, a.employee_user_id, '—') AS employee_name,
                   COALESCE(rc.host_country, rc.home_country, '—') AS destination
            FROM case_assignments a
            LEFT JOIN relocation_cases rc ON {join_on_cases}
            LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
            LEFT JOIN profiles emp_p ON CAST(emp_p.id AS TEXT) = a.employee_user_id
            WHERE (rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid))
            ORDER BY a.created_at DESC
        """
        with self.engine.connect() as conn:
            rows = self._exec(
                conn, sql, {"cid": company_id}, op_name="list_assignments_for_company_with_details", request_id=request_id
            ).fetchall()
        return self._rows_to_list(rows)

    def get_company_detail_orphan_diagnostics(self, company_id: str) -> Dict[str, Any]:
        """Counts of legacy records missing company_id linkage. For admin company detail."""
        from ..database import _relocation_cases_join_on  # lazy: avoid import cycle
        with self.engine.connect() as conn:
            # Assignments where case has null company_id but HR belongs to this company
            row = conn.execute(
                text(f"""
                    SELECT COUNT(*) AS n FROM case_assignments a
                    LEFT JOIN relocation_cases rc ON {_relocation_cases_join_on("a")}
                    LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
                    WHERE hu.company_id = :cid AND (rc.company_id IS NULL OR TRIM(COALESCE(rc.company_id, '')) = '')
                """),
                {"cid": company_id},
            ).fetchone()
            assignments_case_missing_company_id = row._mapping["n"] if row else 0
            # HR users with no profile (would show as missing name/email)
            row2 = conn.execute(
                text(
                    "SELECT COUNT(*) AS n FROM hr_users hu "
                    "LEFT JOIN profiles p ON CAST(p.id AS TEXT) = hu.profile_id WHERE hu.company_id = :cid AND p.id IS NULL"
                ),
                {"cid": company_id},
            ).fetchone()
            hr_users_missing_profile = row2._mapping["n"] if row2 else 0
            row3 = conn.execute(
                text(
                    "SELECT COUNT(*) AS n FROM employees e "
                    "LEFT JOIN profiles p ON CAST(p.id AS TEXT) = e.profile_id WHERE e.company_id = :cid AND p.id IS NULL"
                ),
                {"cid": company_id},
            ).fetchone()
            employees_missing_profile = row3._mapping["n"] if row3 else 0
        return {
            "assignments_case_missing_company_id": assignments_case_missing_company_id,
            "hr_users_missing_profile": hr_users_missing_profile,
            "employees_missing_profile": employees_missing_profile,
        }

    def assignment_belongs_to_company(self, assignment_id: str, company_id: str) -> bool:
        """Check if assignment belongs to the given company (via case or HR)."""
        from ..database import _relocation_cases_join_on  # lazy: avoid import cycle
        sql = f"""
            SELECT 1 FROM case_assignments a
            LEFT JOIN relocation_cases rc ON {_relocation_cases_join_on("a")}
            LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
            WHERE a.id = :aid AND (rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid))
            LIMIT 1
        """
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), {"aid": assignment_id, "cid": company_id}).fetchone()
        return row is not None

    def admin_reassign_employee_company(self, employee_user_id: str, company_id: str) -> None:
        """Reassign employee profile to a company (profiles.company_id)."""
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE profiles SET company_id = :cid WHERE id = :id"), {"cid": company_id, "id": employee_user_id})
            conn.execute(text("UPDATE employees SET company_id = :cid WHERE profile_id = :pid"), {"cid": company_id, "pid": employee_user_id})

    def admin_fix_assignment_company_linkage(self, assignment_id: str, company_id: str) -> None:
        """Set relocation_case.company_id to match; ensures assignment-company consistency."""
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT case_id FROM case_assignments WHERE id = :aid"), {"aid": assignment_id}).fetchone()
        if not row or not row[0]:
            return
        case_id = row[0]
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE relocation_cases SET company_id = :cid, updated_at = :ua WHERE id = :case_id"),
                {"cid": company_id, "ua": datetime.utcnow().isoformat(), "case_id": case_id},
            )

    def _resolve_canonical_case_company(
        self,
        canonical_case_id: str,
        assignment: Dict[str, Any],
        employee_uuid: Optional[str] = None,
    ) -> Optional[str]:
        """Resolve the ``company_id`` (FK to ``companies``) for the canonical case.

        ``relocation_cases.company_id`` is the primary source (HR-create writes it),
        but resolving from it alone makes the bridge a single point of failure: a
        case whose ``relocation_cases`` row is missing or lacks a company (e.g.
        created through a different path) never materializes a canonical case and so
        never renders a roadmap/dossier. Fall back to the assignment's HR user
        (``hr_users``) and then the employee profile — the same multi-path tenant
        resolution used elsewhere. Returns None only when no source has a company.
        """
        cand = (canonical_case_id or "").strip()
        # 1. relocation_cases (denormalized by HR-create).
        if cand:
            try:
                with self.engine.connect() as conn:
                    r = conn.execute(
                        text("SELECT company_id FROM relocation_cases WHERE CAST(id AS TEXT) = :id"),
                        {"id": cand},
                    ).mappings().first()
                if r and r.get("company_id"):
                    return str(r["company_id"]).strip()
            except Exception:
                log.exception("canonical-case bridge: relocation_cases company lookup failed case=%s", cand)
        # 2. The assignment's HR user -> hr_users.
        hr_uid = str((assignment or {}).get("hr_user_id") or "").strip()
        if hr_uid:
            try:
                cid = self.get_hr_company_id(hr_uid)
                if cid:
                    return str(cid).strip()
            except Exception:
                log.exception("canonical-case bridge: hr_users company lookup failed hr=%s", hr_uid)
        # 3. The employee's own profile.
        if employee_uuid:
            try:
                prof = self.get_profile_record(employee_uuid)
                if prof and prof.get("company_id"):
                    return str(prof["company_id"]).strip()
            except Exception:
                log.exception("canonical-case bridge: profile company lookup failed emp=%s", employee_uuid)
        return None

    def admin_link_policy_company(self, policy_id: str, company_id: str) -> None:
        """Reassign a company_policy to a company (for reconciliation)."""
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE company_policies SET company_id = :cid WHERE id = :id"),
                {"cid": company_id, "id": policy_id},
            )

    def backfill_link_latest_policy_to_test_company(self, company_name: str = "Test company") -> Dict[str, Any]:
        """
        Link the most recently created company_policy (by created_at) to the company named company_name.
        Use to surface the policy worked on in the HR workflow under Test company in Admin Policies.
        """
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM companies WHERE LOWER(TRIM(name)) = LOWER(TRIM(:name)) LIMIT 1"),
                {"name": company_name},
            ).fetchone()
        if not row:
            return {"ok": False, "error": f"Company '{company_name}' not found", "policy_id": None}
        test_company_id = row._mapping["id"]
        with self.engine.connect() as conn:
            policy_row = conn.execute(
                text(
                    "SELECT id FROM company_policies ORDER BY created_at DESC LIMIT 1"
                ),
                {},
            ).fetchone()
        if not policy_row:
            return {"ok": True, "company_id": test_company_id, "company_name": company_name, "policy_id": None, "linked": False}
        policy_id = policy_row._mapping["id"]
        self.admin_link_policy_company(policy_id, test_company_id)
        log.info(
            "backfill_link_latest_policy_to_test_company: company=%s company_id=%s policy_id=%s",
            company_name,
            test_company_id,
            policy_id,
        )
        return {"ok": True, "company_id": test_company_id, "company_name": company_name, "policy_id": policy_id, "linked": True}

    def backfill_assignments_to_test_company(self, company_name: str = "Test company") -> Dict[str, Any]:
        """
        Set relocation_cases.company_id to the given company for all cases that have no company.
        This makes assignments show under that company in the admin list (company filter).
        Does not duplicate records; only updates existing relocation_cases rows.
        """
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM companies WHERE LOWER(TRIM(name)) = LOWER(TRIM(:name)) LIMIT 1"),
                {"name": company_name},
            ).fetchone()
        if not row:
            return {"ok": False, "error": f"Company '{company_name}' not found", "cases_updated": 0}
        test_company_id = row._mapping["id"]
        with self.engine.begin() as conn:
            if _is_sqlite:
                result = conn.execute(
                    text(
                        "UPDATE relocation_cases SET company_id = :cid "
                        "WHERE company_id IS NULL OR TRIM(COALESCE(company_id, '')) = ''"
                    ),
                    {"cid": test_company_id},
                )
            else:
                result = conn.execute(
                    text(
                        "UPDATE relocation_cases SET company_id = :cid "
                        "WHERE company_id IS NULL OR TRIM(COALESCE(company_id, '')) = ''"
                    ),
                    {"cid": test_company_id},
                )
        updated = result.rowcount if hasattr(result, "rowcount") else 0
        log.info(
            "backfill_assignments_to_test_company: company=%s company_id=%s cases_updated=%s",
            company_name,
            test_company_id,
            updated,
        )
        return {
            "ok": True,
            "company_id": test_company_id,
            "company_name": company_name,
            "cases_updated": updated,
        }

    def list_companies(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        # AIQ-913: hide synthetic e2e/verify seed companies from the admin list
        # (prod is continuously re-seeded, so a one-time purge can't hold).
        from .test_data_filter import exclude_test_companies
        excl = exclude_test_companies("name")
        q = (query or "").strip().lower()
        with self.engine.connect() as conn:
            if q:
                rows = conn.execute(text(
                    f"SELECT * FROM companies WHERE LOWER(name) LIKE :q AND {excl} ORDER BY created_at DESC"
                ), {"q": f"%{q}%"}).fetchall()
            else:
                rows = conn.execute(text(
                    f"SELECT * FROM companies WHERE {excl} ORDER BY created_at DESC"
                )).fetchall()
        return self._rows_to_list(rows)

    def get_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM companies WHERE id = :id"), {"id": company_id}).fetchone()
        return self._row_to_dict(row)

    def get_company_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find company by exact name match (case-sensitive)."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM companies WHERE TRIM(name) = :name LIMIT 1"),
                {"name": (name or "").strip()},
            ).fetchone()
        return self._row_to_dict(row)

    def find_or_create_company_by_name(
        self, name: str, company_size: Optional[str] = None
    ) -> Optional[str]:
        """Return the company_id for ``name``, creating the company if none exists.

        Match is case-insensitive on the trimmed name so self-serve HR signups
        reuse an existing workspace instead of spawning duplicates (the "17 Test
        company" problem). Returns None when ``name`` is blank.

        ``company_size`` (AIQ-829) is the HR signup's headcount band; it is stored
        as ``size_band`` only when a NEW company is created — an existing workspace
        keeps its current value rather than being overwritten by a later signup.
        """
        cleaned = (name or "").strip()
        if not cleaned:
            return None
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM companies WHERE LOWER(TRIM(name)) = LOWER(:name) LIMIT 1"),
                {"name": cleaned},
            ).fetchone()
        if row is not None:
            return self._row_to_dict(row)["id"]
        company_id = str(uuid.uuid4())
        self.create_company(
            company_id=company_id, name=cleaned, status="active", plan_tier="starter",
            size_band=company_size,
        )
        return company_id

    def run_admin_reconciliation_backfill_test_company(
        self, test_company_name: str = "Test company"
    ) -> Dict[str, Any]:
        """
        One-time non-destructive backfill: link orphan profiles, hr_users, and relocation_cases
        to Test company. Uses fixed company_id 110854ad-3c85-4291-a484-0b43effb680e when that
        company exists; otherwise falls back to lookup by exact name and creates if missing.
        Does not overwrite existing non-null linkage.
        Returns summary counts.
        """
        name = (test_company_name or "").strip()
        if not name:
            return {"ok": False, "error": "test_company_name is required", "summary": {}}
        test_id = self.TEST_COMPANY_FIXED_ID
        with self.engine.connect() as conn:
            by_id = conn.execute(
                text("SELECT id, name FROM companies WHERE id = :id LIMIT 1"),
                {"id": test_id},
            ).fetchone()
            if by_id:
                log.info("admin_reconciliation: using existing Test company id=%s name=%s", test_id, by_id._mapping.get("name"))
            else:
                # Create Test company with fixed ID so all backfill targets this UUID
                self.create_company(
                    company_id=test_id,
                    name=name,
                    country=None,
                    status="active",
                    plan_tier="low",
                )
                log.info("admin_reconciliation: created Test company id=%s name=%s", test_id, name)
        summary: Dict[str, Any] = {
            "test_company_id": test_id,
            "profiles_linked": 0,
            "hr_users_linked": 0,
            "relocation_cases_linked": 0,
        }
        with self.engine.begin() as conn:
            # Profiles: set company_id where null or empty (profiles table may not have updated_at in SQLite)
            r = conn.execute(
                text(
                    "UPDATE profiles SET company_id = :tid "
                    "WHERE (company_id IS NULL OR TRIM(COALESCE(company_id, '')) = '')"
                ),
                {"tid": test_id},
            )
            summary["profiles_linked"] = r.rowcount
            # hr_users
            r = conn.execute(
                text(
                    "UPDATE hr_users SET company_id = :tid "
                    "WHERE (company_id IS NULL OR TRIM(COALESCE(company_id, '')) = '')"
                ),
                {"tid": test_id},
            )
            summary["hr_users_linked"] = r.rowcount
            # relocation_cases
            r = conn.execute(
                text(
                    "UPDATE relocation_cases SET company_id = :tid, updated_at = COALESCE(updated_at, :now) "
                    "WHERE (company_id IS NULL OR TRIM(COALESCE(company_id, '')) = '')"
                ),
                {"tid": test_id, "now": datetime.utcnow().isoformat()},
            )
            summary["relocation_cases_linked"] = r.rowcount
        log.info(
            "admin_reconciliation backfill test_company: profiles_linked=%s hr_users_linked=%s cases_linked=%s",
            summary["profiles_linked"],
            summary["hr_users_linked"],
            summary["relocation_cases_linked"],
        )
        return {"ok": True, "summary": summary}

    def rebuild_test_company_graph(self) -> Dict[str, Any]:
        """
        Rebuild canonical Test company graph in the current DB.
        - Uses TEST_COMPANY_FIXED_ID as the canonical company id.
        - Reassigns non-admin profiles, hr_users, employees, and relocation_cases to this company
          when they are demo/test data.
        - Ensures HR and employee seats exist for HR/EMPLOYEE profiles.
        - Repairs relocation_cases.employee_id and hr_user_id when possible.
        Idempotent: running multiple times converges to the same graph.
        """
        test_id = self.TEST_COMPANY_FIXED_ID
        now = datetime.utcnow().isoformat()
        created: Dict[str, Any] = {
            "profiles_linked": 0,
            "hr_users_linked": 0,
            "employees_linked": 0,
            "relocation_cases_linked": 0,
            "case_assignments_repaired": 0,
            "policies_linked": 0,
        }

        # Ensure Test company exists
        self.create_company(
            company_id=test_id,
            name="Test company",
            country=None,
            status="active",
            plan_tier="low",
        )

        # Link non-admin profiles that look like demo/test into Test company
        with self.engine.begin() as conn:
            r = conn.execute(
                text(
                    """
                    UPDATE profiles
                    SET company_id = :cid
                    WHERE COALESCE(role,'') <> 'ADMIN'
                      AND (company_id IS NULL OR TRIM(company_id) = '' OR company_id = 'demo-company-001')
                    """
                ),
                {"cid": test_id},
            )
            created["profiles_linked"] = r.rowcount

        # Repoint hr_users and employees rows with demo company to Test company
        with self.engine.begin() as conn:
            r = conn.execute(
                text("UPDATE hr_users SET company_id = :cid WHERE company_id = 'demo-company-001'"),
                {"cid": test_id},
            )
            created["hr_users_linked"] += r.rowcount
            r = conn.execute(
                text("UPDATE employees SET company_id = :cid WHERE company_id = 'demo-company-001'"),
                {"cid": test_id},
            )
            created["employees_linked"] += r.rowcount

        # Ensure HR seats exist for HR profiles
        with self.engine.begin() as conn:
            hr_profiles = conn.execute(
                text("SELECT id FROM profiles WHERE role = 'HR' AND company_id = :cid"),
                {"cid": test_id},
            ).fetchall()
            existing_hr = conn.execute(
                text("SELECT DISTINCT profile_id FROM hr_users"),
                {},
            ).fetchall()
            existing_hr_ids = {r._mapping["profile_id"] for r in existing_hr}
            for r in hr_profiles:
                pid = r._mapping["id"]
                if pid in existing_hr_ids:
                    continue
                hr_id = f"hr-{pid}"
                conn.execute(
                    text(
                        "INSERT INTO hr_users (id, company_id, profile_id, permissions_json, created_at) "
                        "VALUES (:id, :cid, :pid, :perms, :ca)"
                    ),
                    {
                        "id": hr_id,
                        "cid": test_id,
                        "pid": pid,
                        "perms": '{"can_manage_policy": true}',
                        "ca": now,
                    },
                )
                created["hr_users_linked"] += 1

        # Ensure employee seats exist for employee/employee_user profiles
        with self.engine.begin() as conn:
            emp_profiles = conn.execute(
                text(
                    "SELECT id FROM profiles "
                    "WHERE role IN ('EMPLOYEE','EMPLOYEE_USER') AND company_id = :cid"
                ),
                {"cid": test_id},
            ).fetchall()
            existing_emp = conn.execute(
                text("SELECT DISTINCT profile_id FROM employees"),
                {},
            ).fetchall()
            existing_emp_ids = {r._mapping["profile_id"] for r in existing_emp}
            for r in emp_profiles:
                pid = r._mapping["id"]
                if pid in existing_emp_ids:
                    continue
                emp_id = f"emp-{pid}"
                conn.execute(
                    text(
                        "INSERT INTO employees (id, company_id, profile_id, band, assignment_type, relocation_case_id, status, created_at) "
                        "VALUES (:id, :cid, :pid, NULL, NULL, NULL, 'active', :ca)"
                    ),
                    {"id": emp_id, "cid": test_id, "pid": pid, "ca": now},
                )
                created["employees_linked"] += 1

        # Repoint relocation_cases for demo company or null company_id
        with self.engine.begin() as conn:
            r = conn.execute(
                text(
                    """
                    UPDATE relocation_cases
                    SET company_id = :cid, updated_at = :now
                    WHERE company_id = 'demo-company-001'
                       OR company_id IS NULL OR TRIM(COALESCE(company_id,'')) = ''
                    """
                ),
                {"cid": test_id, "now": now},
            )
            created["relocation_cases_linked"] = r.rowcount

        # Attempt to fix relocation_cases.employee_id from employees table when missing
        with self.engine.begin() as conn:
            # Cases with null employee_id but matching employees.relocation_case_id
            rows = conn.execute(
                text(
                    """
                    SELECT rc.id AS case_id, e.id AS employee_id
                    FROM relocation_cases rc
                    JOIN employees e ON e.relocation_case_id = rc.id
                    WHERE (rc.employee_id IS NULL OR TRIM(COALESCE(rc.employee_id,'')) = '')
                    """
                ),
                {},
            ).fetchall()
            for row in rows:
                conn.execute(
                    text("UPDATE relocation_cases SET employee_id = :eid, updated_at = :now WHERE id = :cid"),
                    {"eid": row._mapping["employee_id"], "cid": row._mapping["case_id"], "now": now},
                )

        # Assignments: nothing to change for canonical counts here; linkage via company_id already fixed via cases/hr_users
        # Leave created['case_assignments_repaired'] for future detailed repair logic if needed.

        return created

    def create_company(
        self,
        company_id: str,
        name: str,
        country: Optional[str] = None,
        size_band: Optional[str] = None,
        address: Optional[str] = None,
        phone: Optional[str] = None,
        hr_contact: Optional[str] = None,
        legal_name: Optional[str] = None,
        website: Optional[str] = None,
        hq_city: Optional[str] = None,
        industry: Optional[str] = None,
        logo_url: Optional[str] = None,
        brand_color: Optional[str] = None,
        default_destination_country: Optional[str] = None,
        support_email: Optional[str] = None,
        default_working_location: Optional[str] = None,
        status: Optional[str] = None,
        plan_tier: Optional[str] = None,
        hr_seat_limit: Optional[int] = None,
        employee_seat_limit: Optional[int] = None,
        is_test: Optional[bool] = None,
    ) -> None:
        from ..database import _table_columns  # lazy: avoid import cycle
        # PRODSEED-3/AIQ-1130: stamp synthetic tenants with a durable is_test flag.
        # Explicit value wins (e.g. verify scripts pass True); otherwise auto-detect
        # from the seeder name pattern so e2e-created companies are flagged at write
        # time. Real/demo tenants resolve to False.
        from .test_data_filter import looks_like_test_company
        is_test_val = bool(is_test) if is_test is not None else looks_like_test_company(name)
        now = datetime.utcnow().isoformat()
        status_val = (status or "active").lower() if status else "active"
        plan_val = (plan_tier or "starter").lower() if plan_tier else "starter"
        if plan_val not in ("starter", "growth", "enterprise"):
            plan_val = "starter"
        # Generate a URL-safe slug from the company name + short random suffix to satisfy
        # the NOT NULL UNIQUE constraint on companies.slug.
        _slug_base = re.sub(r"[^a-z0-9]+", "-", (name or "company").lower()).strip("-") or "company"
        _slug_suffix = uuid.uuid4().hex[:6]
        slug_val = f"{_slug_base}-{_slug_suffix}"
        params = {
            "id": company_id,
            "name": name,
            "slug": slug_val,
            "country": country,
            "size_band": size_band,
            "address": address,
            "phone": phone,
            "hr_contact": hr_contact,
            "created_at": now,
            "legal_name": legal_name,
            "website": website,
            "hq_city": hq_city,
            "industry": industry,
            "logo_url": logo_url,
            "brand_color": brand_color,
            "updated_at": now,
            "default_destination_country": default_destination_country,
            "support_email": support_email,
            "default_working_location": default_working_location,
            "status": status_val,
            "plan_tier": plan_val,
            "hr_seat_limit": hr_seat_limit,
            "employee_seat_limit": employee_seat_limit,
            "is_test": is_test_val,
        }

        with self.engine.begin() as conn:
            # Production Postgres may not yet have the newer columns (status, plan_tier, hr_seat_limit, employee_seat_limit).
            # Build the INSERT/UPSERT dynamically based on actual columns to avoid UndefinedColumn errors.
            company_cols = _table_columns(conn, "companies")

            base_cols = [
                "id",
                "name",
                "slug",
                "country",
                "size_band",
                "address",
                "phone",
                "hr_contact",
                "created_at",
                "legal_name",
                "website",
                "hq_city",
                "industry",
                "logo_url",
                "brand_color",
                "updated_at",
                "default_destination_country",
                "support_email",
                "default_working_location",
            ]
            optional_cols = [
                "status",
                "plan_tier",
                "hr_seat_limit",
                "employee_seat_limit",
                # PRODSEED-3: only inserted when the column exists (deploy-safe before
                # the migration applies). Deliberately omitted from the ON CONFLICT
                # update set so a re-upsert never un-flags an existing row.
                "is_test",
            ]

            insert_cols = [c for c in base_cols if c in company_cols] + [
                c for c in optional_cols if c in company_cols
            ]
            values_clause = ", ".join(f":{c}" for c in insert_cols)
            columns_clause = ", ".join(insert_cols)

            # Build ON CONFLICT update set — only for columns that are in insert_cols
            # (i.e., columns that actually exist in the table AND were included in VALUES).
            # Referencing excluded.<col> for a column not in the INSERT raises
            # "column excluded.<col> does not exist" in Postgres.
            _insert_set = set(insert_cols)

            def _upd(col: str, expr: str) -> Optional[str]:
                """Return the update expression only if col was actually inserted."""
                return expr if col in _insert_set else None

            _all_update_candidates = [
                _upd("name",       "name = excluded.name"),
                # slug is immutable once set — preserve existing value
                _upd("slug",       "slug = COALESCE(companies.slug, excluded.slug)"),
                _upd("country",    "country = excluded.country"),
                _upd("size_band",  "size_band = excluded.size_band"),
                _upd("address",    "address = excluded.address"),
                _upd("phone",      "phone = excluded.phone"),
                _upd("hr_contact", "hr_contact = excluded.hr_contact"),
                _upd("legal_name", "legal_name = COALESCE(excluded.legal_name, companies.legal_name)"),
                _upd("website",    "website = COALESCE(excluded.website, companies.website)"),
                _upd("hq_city",    "hq_city = COALESCE(excluded.hq_city, companies.hq_city)"),
                _upd("industry",   "industry = COALESCE(excluded.industry, companies.industry)"),
                _upd("logo_url",   "logo_url = COALESCE(excluded.logo_url, companies.logo_url)"),
                _upd("brand_color","brand_color = COALESCE(excluded.brand_color, companies.brand_color)"),
                _upd("updated_at", "updated_at = excluded.updated_at"),
                _upd("default_destination_country",
                     "default_destination_country = COALESCE(excluded.default_destination_country, companies.default_destination_country)"),
                _upd("support_email",
                     "support_email = COALESCE(excluded.support_email, companies.support_email)"),
                _upd("default_working_location",
                     "default_working_location = COALESCE(excluded.default_working_location, companies.default_working_location)"),
                _upd("status",
                     "status = COALESCE(excluded.status, companies.status)"),
                _upd("plan_tier",
                     "plan_tier = COALESCE(excluded.plan_tier, companies.plan_tier)"),
                _upd("hr_seat_limit",
                     "hr_seat_limit = COALESCE(excluded.hr_seat_limit, companies.hr_seat_limit)"),
                _upd("employee_seat_limit",
                     "employee_seat_limit = COALESCE(excluded.employee_seat_limit, companies.employee_seat_limit)"),
            ]
            update_sets = [s for s in _all_update_candidates if s is not None]

            sql = f"""
                INSERT INTO companies ({columns_clause})
                VALUES ({values_clause})
                ON CONFLICT(id) DO UPDATE SET
                {", ".join(update_sets)}
            """
            conn.execute(text(sql), params)

    def update_company(
        self,
        company_id: str,
        name: Optional[str] = None,
        country: Optional[str] = None,
        size_band: Optional[str] = None,
        address: Optional[str] = None,
        phone: Optional[str] = None,
        hr_contact: Optional[str] = None,
        legal_name: Optional[str] = None,
        website: Optional[str] = None,
        hq_city: Optional[str] = None,
        industry: Optional[str] = None,
        logo_url: Optional[str] = None,
        brand_color: Optional[str] = None,
        default_destination_country: Optional[str] = None,
        support_email: Optional[str] = None,
        default_working_location: Optional[str] = None,
        status: Optional[str] = None,
        plan_tier: Optional[str] = None,
        hr_seat_limit: Optional[int] = None,
        employee_seat_limit: Optional[int] = None,
    ) -> bool:
        """Update company by id. Only provided (non-None) fields are updated. Returns True if row was updated."""
        from ..database import _table_has_column  # lazy: avoid import cycle
        updates = []
        params: Dict[str, Any] = {"id": company_id}
        if name is not None:
            updates.append("name = :name")
            params["name"] = name
        if country is not None:
            updates.append("country = :country")
            params["country"] = country
        if size_band is not None:
            updates.append("size_band = :size_band")
            params["size_band"] = size_band
        if address is not None:
            updates.append("address = :address")
            params["address"] = address
        if phone is not None:
            updates.append("phone = :phone")
            params["phone"] = phone
        if hr_contact is not None:
            updates.append("hr_contact = :hr_contact")
            params["hr_contact"] = hr_contact
        if legal_name is not None:
            updates.append("legal_name = :legal_name")
            params["legal_name"] = legal_name
        if website is not None:
            updates.append("website = :website")
            params["website"] = website
        if hq_city is not None:
            updates.append("hq_city = :hq_city")
            params["hq_city"] = hq_city
        if industry is not None:
            updates.append("industry = :industry")
            params["industry"] = industry
        if logo_url is not None:
            updates.append("logo_url = :logo_url")
            params["logo_url"] = logo_url
        if brand_color is not None:
            updates.append("brand_color = :brand_color")
            params["brand_color"] = brand_color
        if default_destination_country is not None:
            updates.append("default_destination_country = :default_destination_country")
            params["default_destination_country"] = default_destination_country
        if support_email is not None:
            updates.append("support_email = :support_email")
            params["support_email"] = support_email
        if default_working_location is not None:
            updates.append("default_working_location = :default_working_location")
            params["default_working_location"] = default_working_location
        if status is not None:
            # Some runtimes (like current production) have no companies.status column.
            # We only include this update when the column exists.
            try:
                with self.engine.connect() as conn:
                    has_status = _table_has_column(conn, "companies", "status")
                if has_status:
                    updates.append("status = :status")
                    params["status"] = (status or "active").lower()
            except Exception:
                # If schema lookup fails, skip status update to avoid breaking writes.
                pass
        if plan_tier is not None:
            pt = (plan_tier or "low").lower()
            if pt in ("low", "medium", "premium"):
                updates.append("plan_tier = :plan_tier")
                params["plan_tier"] = pt
        if hr_seat_limit is not None:
            updates.append("hr_seat_limit = :hr_seat_limit")
            params["hr_seat_limit"] = hr_seat_limit
        if employee_seat_limit is not None:
            updates.append("employee_seat_limit = :employee_seat_limit")
            params["employee_seat_limit"] = employee_seat_limit
        if not updates:
            return False
        updates.append("updated_at = :updated_at")
        params["updated_at"] = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            result = conn.execute(
                text(f"UPDATE companies SET {', '.join(updates)} WHERE id = :id"),
                params,
            )
        return result.rowcount > 0

    def deactivate_company(self, company_id: str) -> bool:
        """
        Delete/deactivate a company.
        - If companies.status column exists, mark it inactive.
        - Otherwise, hard delete the row.
        """
        from ..database import _table_has_column  # lazy: avoid import cycle
        try:
            with self.engine.connect() as conn:
                has_status = _table_has_column(conn, "companies", "status")
            if has_status:
                return self.update_company(company_id, status="inactive")
        except Exception:
            pass
        # Fallback: hard delete.
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM companies WHERE id = :id"), {"id": company_id})
        return True

    def archive_company(self, company_id: str) -> bool:
        """Set companies.status to 'archived'. Soft-delete used by the admin
        UI to hide a company from active lists without destroying its data."""
        return self.update_company(company_id, status="archived")

    def delete_company_hard(self, company_id: str) -> bool:
        """Hard-delete a company row. Will orphan rows in tables that hold a
        company_id column without an explicit FK constraint (employees,
        hr_users, profiles, relocation_cases, support_cases). Use only when
        you actually want the row gone."""
        with self.engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM companies WHERE id = :id"),
                {"id": company_id},
            )
            return (result.rowcount or 0) > 0

    def update_company_logo(self, company_id: str, logo_url: Optional[str]) -> None:
        with self.engine.begin() as conn:
            if _is_sqlite:
                conn.execute(text("UPDATE companies SET logo_url = :url WHERE id = :id"), {"url": logo_url, "id": company_id})
            else:
                conn.execute(text("UPDATE companies SET logo_url = :url, updated_at = now() WHERE id = :id"), {"url": logo_url, "id": company_id})

    def ensure_directory_from_assignments_for_company(self, company_id: str) -> None:
        """
        Backfill HR → Employees for users already attached to assignments (employee_user_id set)
        but missing profiles.company_id — e.g. claimed before directory sync existed.
        """
        cid = (company_id or "").strip()
        if not cid:
            return
        if _is_sqlite:
            join_on_cases = "rc.id = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"
        else:
            join_on_cases = "rc.id::text = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"
        sql = f"""
            SELECT DISTINCT a.employee_user_id AS euid
            FROM case_assignments a
            LEFT JOIN relocation_cases rc ON {join_on_cases}
            LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
            WHERE (rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid))
              AND NULLIF(TRIM(CAST(a.employee_user_id AS TEXT)), '') IS NOT NULL
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"cid": cid}).fetchall()
        seen: Set[str] = set()
        for row in rows:
            m = row._mapping if hasattr(row, "_mapping") else dict(row)
            euid = m.get("euid")
            if not euid:
                continue
            pid = str(euid).strip()
            if not pid or pid in seen:
                continue
            seen.add(pid)
            self.assign_employee_profile_to_company_directory(pid, cid)

    def ensure_employees_for_company(self, company_id: str) -> None:
        """
        Ensure employees rows exist for all profiles with role EMPLOYEE/EMPLOYEE_USER and
        company_id=company_id (backfill so they appear in assignment creation dropdown).
        """
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id FROM profiles WHERE role IN ('EMPLOYEE', 'EMPLOYEE_USER') AND company_id = :cid"
                ),
                {"cid": company_id},
            ).fetchall()
        for row in rows:
            pid = row._mapping["id"] if hasattr(row, "_mapping") else row[0]
            self.ensure_employee_for_profile(pid, company_id)

    def get_employee_for_company(
        self, employee_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get employee with profile if they belong to the given company. Returns None if not found or wrong company."""
        sql = """
            SELECT e.id, e.company_id, e.profile_id, e.band, e.assignment_type, e.relocation_case_id, e.status, e.created_at,
                   p.full_name, p.email, p.role
            FROM employees e
            LEFT JOIN profiles p ON CAST(p.id AS TEXT) = e.profile_id
            WHERE e.id = :eid AND e.company_id = :cid
        """
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), {"eid": employee_id, "cid": company_id}).fetchone()
        return self._row_to_dict(row) if row else None

    def delete_employee_for_company(self, employee_id: str, company_id: str) -> bool:
        """Remove an employee from the company roster. Returns False if not found/wrong company."""
        with self.engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM employees WHERE id = :eid AND company_id = :cid"),
                {"eid": employee_id, "cid": company_id},
            )
        return result.rowcount > 0 if hasattr(result, "rowcount") else True

    def list_hr_policies_by_company(self, company_id: str) -> List[Dict[str, Any]]:
        return self.list_hr_policies(company_entity=company_id)

    def create_company_policy(
        self,
        policy_id: str,
        company_id: str,
        title: str,
        version: Optional[str],
        effective_date: Optional[str],
        file_url: str,
        file_type: str,
        created_by: Optional[str],
        template_source: str = "company_uploaded",
        template_name: Optional[str] = None,
        is_default_template: bool = False,
        request_id: Optional[str] = None,
        *,
        connection: Any = None,
    ) -> None:
        """
        Insert a row into company_policies. Columns are built from actual schema so production
        Postgres without template_source/template_name/is_default_template still works.
        """
        from ..database import _get_company_policies_columns, _policy_bool_bind  # lazy: avoid import cycle
        now = datetime.utcnow().isoformat()
        _col_to_param = {
            "id": "id",
            "company_id": "cid",
            "title": "title",
            "version": "ver",
            "effective_date": "ed",
            "file_url": "url",
            "file_type": "ft",
            "extraction_status": "status",
            "created_by": "cb",
            "created_at": "ca",
            "template_source": "tsrc",
            "template_name": "tname",
            "is_default_template": "isdef",
        }
        _param_values = {
            "id": policy_id,
            "cid": company_id,
            "title": title,
            "ver": version,
            "ed": effective_date,
            "url": file_url,
            "ft": file_type,
            "status": "pending",
            "cb": created_by,
            "ca": now,
            "tsrc": template_source,
            "tname": template_name,
            # Postgres: company_policies.is_default_template is boolean (strict). SQLite uses INTEGER 0/1.
            "isdef": _policy_bool_bind(is_default_template),
        }
        existing: set = set()
        last_insert_params: Optional[Dict[str, Any]] = None

        def _exec(conn: Any) -> None:
            nonlocal existing, last_insert_params
            existing = _get_company_policies_columns(conn)
            core = [
                "id", "company_id", "title", "version", "effective_date",
                "file_url", "file_type", "extraction_status", "created_by", "created_at",
            ]
            optional = ["template_source", "template_name", "is_default_template"]
            insert_cols = [c for c in core + optional if c in existing]
            if not insert_cols:
                raise RuntimeError("company_policies has no columns we can insert")
            # Postgres rejects integer binds into boolean columns; some drivers still send 0/1.
            # Use a SQL CASE so the column expression is boolean-typed regardless of driver.
            placeholders: List[str] = []
            params: Dict[str, Any] = {}
            for c in insert_cols:
                key = _col_to_param[c]
                if c == "is_default_template" and not _is_sqlite:
                    placeholders.append("(CASE WHEN :cp_isdef_i = 0 THEN false ELSE true END)")
                    params["cp_isdef_i"] = 1 if is_default_template else 0
                else:
                    placeholders.append(f":{key}")
                    params[key] = _param_values[key]
            last_insert_params = dict(params)
            sql = (
                "INSERT INTO company_policies ("
                + ", ".join(insert_cols)
                + ") VALUES ("
                + ", ".join(placeholders)
                + ")"
            )
            conn.execute(text(sql), params)

        try:
            if connection is not None:
                _exec(connection)
            else:
                with self.engine.begin() as conn:
                    _exec(conn)
        except Exception as exc:
            _lip = last_insert_params or {}
            _isdef = _lip.get("cp_isdef_i") if "cp_isdef_i" in _lip else _param_values.get("isdef")
            log.error(
                "request_id=%s create_company_policy failed company_id=%s policy_id=%s title=%s "
                "company_policies_columns=%s exc_type=%s exc_msg=%s "
                "bind_isdef_type=%s bind_isdef_repr=%s engine_is_sqlite=%s",
                request_id or "?",
                company_id,
                policy_id,
                (title or "")[:80],
                sorted(existing),
                type(exc).__name__,
                str(exc)[:500],
                type(_isdef).__name__,
                repr(_isdef),
                _is_sqlite,
                exc_info=True,
            )
            # region agent log
            try:
                if os.environ.get("RELOPASS_DEBUG_NDJ", "").strip() in ("1", "476bd2"):
                    _lp = "/Users/Rom/Documents/GitHub/rolec/.cursor/debug-476bd2.log"
                    with open(_lp, "a", encoding="utf-8") as _f:
                        _f.write(
                            json.dumps(
                                {
                                    "sessionId": "476bd2",
                                    "hypothesisId": "H-create_company_policy-fail",
                                    "location": "database.create_company_policy",
                                    "message": (str(exc) or type(exc).__name__)[:300],
                                    "data": {
                                        "bind_isdef_type": type(_isdef).__name__,
                                        "bind_isdef_repr": repr(_isdef),
                                        "engine_is_sqlite": _is_sqlite,
                                        "columns": sorted(existing),
                                        "request_id": request_id,
                                        "insert_param_keys": sorted((last_insert_params or {}).keys()),
                                    },
                                    "timestamp": int(time.time() * 1000),
                                }
                            )
                            + "\n"
                        )
            except Exception:
                pass
            # endregion
            raise

    def list_company_policies(self, company_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT * FROM company_policies WHERE company_id = :cid "
                    "ORDER BY created_at DESC"
                ),
                {"cid": company_id},
            ).fetchall()
        return self._rows_to_list(rows)

    def get_admin_policies_by_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        """
        Admin: full policy list for one company with version counts, published version, source doc count.
        Returns None if company not found.
        """
        company = self.get_company(company_id)
        if not company:
            return None
        policies_raw = self.list_company_policies(company_id)
        docs = self.list_policy_documents(company_id)
        source_document_count = len(docs)
        latest_source_document_title: Optional[str] = None
        if docs:
            fn = str(docs[0].get("filename") or "").strip()
            latest_source_document_title = fn or None
        policies: List[Dict[str, Any]] = []
        for cp in policies_raw:
            pid = cp.get("id")
            if not pid:
                continue
            versions = self.list_policy_versions(pid)
            published = self.get_published_policy_version(pid)
            latest = versions[0] if versions else None
            policies.append({
                "policy_id": pid,
                "title": cp.get("title"),
                "extraction_status": cp.get("extraction_status"),
                "version_count": len(versions),
                "published_version_id": published.get("id") if published else None,
                "published_at": published.get("updated_at") if published else None,
                "latest_version_status": latest.get("status") if latest else None,
                "latest_version_number": latest.get("version_number") if latest else None,
                "template_source": cp.get("template_source") or "company_uploaded",
                "template_name": cp.get("template_name"),
                "is_default_template": bool(cp.get("is_default_template")),
            })
        return {
            "company_id": company_id,
            "company_name": company.get("name"),
            "source_document_count": source_document_count,
            "latest_source_document_title": latest_source_document_title,
            "policies": policies,
        }

    def apply_default_template_to_company(
        self,
        company_id: str,
        template_id: str,
        overwrite_existing: bool = False,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a company policy from a default template and one policy_version + benefit_rules.
        Does not overwrite existing company policies unless overwrite_existing=True (then we still only add, never delete).
        Returns the new policy_id and version_id.
        """
        from ..database import _policy_ag_sql, _policy_bool_bind  # lazy: avoid import cycle
        template = self.get_default_policy_template(template_id)
        if not template:
            return {"ok": False, "error": "Template not found", "policy_id": None}
        snapshot = template.get("snapshot_json") or {}
        if isinstance(snapshot, str):
            try:
                snapshot = json.loads(snapshot)
            except Exception:
                snapshot = {}
        template_name = template.get("template_name") or "Platform default"
        version_label = template.get("version") or "1.0"
        effective_date = (snapshot.get("effectiveDate") or "")[:10] if isinstance(snapshot.get("effectiveDate"), str) else None
        if not overwrite_existing:
            existing = self.list_company_policies(company_id)
            if existing:
                has_custom = any((p.get("template_source") or "company_uploaded") == "company_uploaded" for p in existing)
                if has_custom:
                    return {"ok": False, "error": "Company already has a custom uploaded policy; use overwrite_existing to add template anyway", "policy_id": None}
        policy_id = str(uuid.uuid4())
        file_url = ""
        file_type = "application/json"
        self.create_company_policy(
            policy_id=policy_id,
            company_id=company_id,
            title=template_name,
            version=version_label,
            effective_date=effective_date,
            file_url=file_url,
            file_type=file_type,
            created_by=created_by,
            template_source="default_platform_template",
            template_name=template_name,
            is_default_template=False,
        )
        self.update_company_policy_status(policy_id, "extracted", datetime.utcnow().isoformat())
        version_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        ag_sql = _policy_ag_sql()
        with self.engine.begin() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO policy_versions
                    (id, policy_id, source_policy_document_id, version_number, status,
                     auto_generated, review_status, confidence, created_by, created_at, updated_at)
                    VALUES (:id, :pid, NULL, 1, 'draft', {ag_sql}, 'accepted', NULL, :cb, :now, :now)
                """),
                {"id": version_id, "pid": policy_id, "ag": _policy_bool_bind(True), "cb": created_by, "now": now},
            )
        benefit_rules = snapshot.get("benefit_rules") or []
        for br in benefit_rules:
            if not isinstance(br, dict):
                continue
            rule_id = str(uuid.uuid4())
            ag_sql = _policy_ag_sql()
            with self.engine.begin() as conn:
                conn.execute(
                    text(f"""
                        INSERT INTO policy_benefit_rules
                        (id, policy_version_id, benefit_key, benefit_category, calc_type, amount_value, amount_unit, currency,
                         description, metadata_json, auto_generated, review_status, created_at, updated_at)
                        VALUES (:id, :vid, :bk, :cat, :ct, :av, :au, :cur, :desc, '{{}}', {ag_sql}, 'accepted', :now, :now)
                    """),
                    {
                        "id": rule_id,
                        "vid": version_id,
                        "ag": _policy_bool_bind(True),
                        "bk": br.get("benefit_key") or "",
                        "cat": br.get("benefit_category") or "",
                        "ct": br.get("calc_type"),
                        "av": br.get("amount_value"),
                        "au": br.get("amount_unit"),
                        "cur": br.get("currency"),
                        "desc": br.get("description"),
                        "now": now,
                    },
                )
        return {"ok": True, "policy_id": policy_id, "version_id": version_id}

    def get_admin_company_index(
        self, query: Optional[str] = None, include_test: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List all companies for admin from the canonical companies table only.
        Orphan company_ids (referenced elsewhere but not in companies) are logged, not shown.

        PRODSEED-3/AIQ-1130: synthetic e2e/verify tenants (is_test=true) are hidden by
        default; pass include_test=True to show them. The filter is guarded on the
        column's presence so it degrades safely if the migration hasn't applied yet.
        """
        from ..database import _table_columns  # lazy: avoid import cycle
        q = (query or "").strip().lower()
        with self.engine.connect() as conn:
            base_sql = "SELECT * FROM companies WHERE 1=1"
            params: Dict[str, Any] = {}
            if not include_test and "is_test" in _table_columns(conn, "companies"):
                base_sql += " AND COALESCE(is_test, false) = false"
            if q:
                base_sql += " AND (LOWER(name) LIKE :q OR LOWER(COALESCE(legal_name,'')) LIKE :q)"
                params["q"] = f"%{q}%"
            base_sql += " ORDER BY name ASC"
            rows = conn.execute(text(base_sql), params).fetchall()
            result = []
            for r in rows:
                d = dict(r._mapping)
                d["missing_from_companies_table"] = 0
                result.append(d)
            # [AIQ-864] str() so this text-keyed set matches the TEXT company_id
            # columns below (companies.id is uuid); otherwise the orphan NOT IN
            # check compares text vs uuid and mis-flags every id as an orphan.
            seen = {str(r["id"]) for r in result}
            # Collect orphan company_ids for logging only; do not add them to the visible list.
            orphan_ids: set = set()
            for table, col in [("hr_users", "company_id"), ("profiles", "company_id"),
                              ("company_policies", "company_id"), ("relocation_cases", "company_id")]:
                try:
                    orphan_sql = text(
                        f"SELECT DISTINCT {col} AS id FROM {table} WHERE {col} IS NOT NULL AND TRIM({col}) <> ''"
                    )
                    if seen:
                        placeholders = ",".join([f":s{i}" for i in range(len(seen))])
                        orphan_sql = text(
                            f"SELECT DISTINCT {col} AS id FROM {table} WHERE {col} IS NOT NULL AND TRIM({col}) <> '' "
                            f"AND {col} NOT IN ({placeholders})"
                        )
                        orphan_params = {f"s{i}": s for i, s in enumerate(seen)}
                    else:
                        orphan_params = {}
                    orows = conn.execute(orphan_sql, orphan_params).fetchall()
                    for o in orows:
                        cid = (o._mapping.get("id") or "").strip()
                        if cid and cid not in seen:
                            orphan_ids.add(cid)
                except Exception as e:
                    log.warning("admin_company_index: orphan lookup %s.%s failed: %s", table, col, e)
            if orphan_ids:
                log.warning("admin_company_index: orphan company_ids (not in registry): %s", sorted(orphan_ids))

            # Enrich each row with grouped counts instead of correlated subqueries per company.
            if result:
                # [AIQ-864] companies.id is a Postgres uuid; hr_users/employees/
                # case_assignments .company_id are TEXT. Passing uuid objects as the
                # IN-params compares `text = uuid` (no implicit cast) → the aggregate
                # subqueries error/return nothing → the except below zeroes every tile.
                # Cast ids to str so it's a text=text match (no-op for SQLite's text ids).
                ids = [str(r["id"]) for r in result]
                id_placeholders = ",".join([f":id{i}" for i in range(len(ids))])
                params_agg = {f"id{i}": ids[i] for i in range(len(ids))}
                if _is_sqlite:
                    join_on_cases = "rc.id = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"
                else:
                    # Postgres: relocation_cases.id is uuid, case_assignments.case_id / canonical_case_id are text UUIDs.
                    join_on_cases = "rc.id::text = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)"
                try:
                    hr_count_rows = conn.execute(
                        text(
                            f"""
                            SELECT company_id AS id, COUNT(*) AS hr_users_count
                            FROM hr_users
                            WHERE company_id IN ({id_placeholders})
                            GROUP BY company_id
                            """
                        ),
                        params_agg,
                    ).fetchall()
                    employee_count_rows = conn.execute(
                        text(
                            f"""
                            SELECT company_id AS id, COUNT(*) AS employee_count
                            FROM employees
                            WHERE company_id IN ({id_placeholders})
                            GROUP BY company_id
                            """
                        ),
                        params_agg,
                    ).fetchall()
                    assignment_count_rows = conn.execute(
                        text(
                            f"""
                            SELECT
                                COALESCE(rc.company_id, hu.company_id) AS id,
                                COUNT(*) AS assignments_count
                            FROM case_assignments a
                            LEFT JOIN relocation_cases rc ON {join_on_cases}
                            LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
                            WHERE COALESCE(rc.company_id, hu.company_id) IN ({id_placeholders})
                            GROUP BY COALESCE(rc.company_id, hu.company_id)
                            """
                        ),
                        params_agg,
                    ).fetchall()
                    contact_rows = conn.execute(
                        text(
                            f"""
                            SELECT hu.company_id AS id, COALESCE(p.full_name, p.email) AS contact_name, hu.created_at
                            FROM hr_users hu
                            JOIN profiles p ON CAST(p.id AS TEXT) = hu.profile_id
                            WHERE hu.company_id IN ({id_placeholders})
                            ORDER BY hu.company_id ASC, hu.created_at ASC
                            """
                        ),
                        params_agg,
                    ).fetchall()
                    # [AIQ-864] Normalize all keys to str. companies.id is a uuid
                    # (returned as a uuid.UUID object) while hr_users/employees/
                    # case_assignments .company_id are text, so the aggregate dicts
                    # were str-keyed and `.get(uuid)` always missed → every rollup
                    # tile showed 0 in prod (SQLite tests are all-text → false green).
                    hr_counts = {str(row._mapping["id"]): int(row._mapping["hr_users_count"] or 0) for row in hr_count_rows}
                    employee_counts = {str(row._mapping["id"]): int(row._mapping["employee_count"] or 0) for row in employee_count_rows}
                    assignment_counts = {str(row._mapping["id"]): int(row._mapping["assignments_count"] or 0) for row in assignment_count_rows}
                    first_contacts: Dict[str, Optional[str]] = {}
                    for row in contact_rows:
                        company_id = str(row._mapping["id"])
                        if company_id not in first_contacts:
                            first_contacts[company_id] = row._mapping.get("contact_name")
                    for r in result:
                        rid = str(r["id"])
                        r["hr_users_count"] = hr_counts.get(rid, 0)
                        r["employee_count"] = employee_counts.get(rid, 0)
                        r["assignments_count"] = assignment_counts.get(rid, 0)
                        explicit_contact = (r.get("hr_contact") or "").strip() if isinstance(r.get("hr_contact"), str) else None
                        r["primary_contact_name"] = explicit_contact or first_contacts.get(rid)
                except Exception as e:
                    log.warning("admin_company_index: enrich counts failed: %s", e)
                    for r in result:
                        r["hr_users_count"] = 0
                        r["employee_count"] = 0
                        r["assignments_count"] = 0
                        r["primary_contact_name"] = None
        return result

    def list_company_preferred_suppliers(
        self, company_id: str, service_category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            sql = "SELECT * FROM company_preferred_suppliers WHERE company_id = :cid AND status = 'active'"
            params: Dict[str, Any] = {"cid": company_id}
            if service_category:
                sql += " AND (service_category = :svc OR service_category IS NULL)"
                params["svc"] = service_category
            sql += " ORDER BY priority_rank ASC, created_at ASC"
            rows = conn.execute(text(sql), params).fetchall()
        return self._rows_to_list(rows)

    def add_company_preferred_supplier(
        self,
        company_id: str,
        supplier_id: str,
        service_category: Optional[str] = None,
        priority_rank: int = 0,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        rid = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO company_preferred_suppliers
                    (id, company_id, supplier_id, service_category, priority_rank, status, notes, created_at, updated_at)
                    VALUES (:id, :cid, :sid, :svc, :rank, 'active', :notes, :now, :now)
                """),
                {
                    "id": rid,
                    "cid": company_id,
                    "sid": supplier_id,
                    "svc": service_category,
                    "rank": priority_rank,
                    "notes": notes or "",
                    "now": now,
                },
            )
        return {"id": rid, "company_id": company_id, "supplier_id": supplier_id}

    def remove_company_preferred_supplier(
        self, company_id: str, supplier_id: str, service_category: Optional[str] = None
    ) -> int:
        with self.engine.begin() as conn:
            if service_category:
                r = conn.execute(
                    text("DELETE FROM company_preferred_suppliers WHERE company_id = :cid AND supplier_id = :sid AND service_category = :svc"),
                    {"cid": company_id, "sid": supplier_id, "svc": service_category},
                )
            else:
                r = conn.execute(
                    text("DELETE FROM company_preferred_suppliers WHERE company_id = :cid AND supplier_id = :sid AND service_category IS NULL"),
                    {"cid": company_id, "sid": supplier_id},
                )
                return r.rowcount

    def get_active_canonical_policy_document_for_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        from ..database import _coerce_json_dict, _coerce_json_list  # lazy: avoid import cycle
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT * FROM canonical_policy_documents
                    WHERE company_id = :company_id
                      AND extraction_status IN ('extracted', 'chunked', 'validated_with_errors', 'pending')
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT 1
                    """
                ),
                {"company_id": company_id},
            ).fetchone()
        doc = self._row_to_dict(row)
        if not doc:
            return None
        doc["assignment_types_json"] = _coerce_json_list(doc.get("assignment_types_json"))
        doc["metadata_json"] = _coerce_json_dict(doc.get("metadata_json"))
        return doc

    def list_policy_knowledge_snapshots_for_company(self, company_id: str) -> List[Dict[str, Any]]:
        if not self.policy_assistant_tables_available():
            return []
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT * FROM policy_knowledge_snapshots WHERE company_id = :cid "
                    "ORDER BY created_at DESC"
                ),
                {"cid": company_id},
            ).fetchall()
        return self._rows_to_list(rows)

    def get_company_id_for_assignment_id(self, assignment_id: str) -> Optional[str]:
        """Resolve the company_id linked to a case_assignments row.

        Primary source is the joined ``relocation_cases.company_id``; falls back to
        the assignment's HR user (``hr_users``) so an assignment whose
        ``relocation_cases`` row is missing/lacks a company still resolves a tenant
        (mirrors the canonical-case bridge — employee benefits/exceptions depend on
        this and otherwise 400/403 for such cases)."""
        from ..database import _relocation_cases_join_on  # lazy: avoid import cycle
        aid = (assignment_id or "").strip()
        if not aid:
            return None
        join_on = _relocation_cases_join_on("a", style="standard")
        row = None
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    text(
                        f"""
                        SELECT rc.company_id AS company_id, a.hr_user_id AS hr_user_id
                        FROM case_assignments a
                        LEFT JOIN relocation_cases rc ON {join_on}
                        WHERE a.id = :aid
                        LIMIT 1
                        """
                    ),
                    {"aid": aid},
                ).mappings().first()
        except Exception:
            return None
        if not row:
            return None
        cid = row.get("company_id")
        if cid and str(cid).strip():
            return str(cid).strip()
        hr_uid = str(row.get("hr_user_id") or "").strip()
        if hr_uid:
            try:
                hc = self.get_hr_company_id(hr_uid)
                if hc:
                    return str(hc).strip()
            except Exception:
                log.exception("get_company_id_for_assignment_id: hr_users fallback failed hr=%s", hr_uid)
        return None
