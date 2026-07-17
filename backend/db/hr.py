"""[AUDIT-C1.5] HR command-center DB methods, extracted from backend/database.py.

The HR dashboard surface: command-center KPIs/SQL helpers, HR readiness
summaries, backlog, feedback, conversation summaries, and HR company lookup.
These were methods on the monolithic ``Database`` class; they live here as a
mixin (:class:`HrMixin`) that ``Database`` inherits, so every caller keeps
working unchanged via normal MRO. Module-level ``..database`` helpers
(``_eq_text``, ``_relocation_cases_join_on``) are imported lazily in-method
(matching cases.py/policies.py) to avoid an import cycle.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from ..readiness_service import DEFAULT_ROUTE_KEY, resolve_readiness_route_key

from ..db_config import DATABASE_URL as _raw_url

log = logging.getLogger(__name__)

_is_sqlite = _raw_url.startswith("sqlite")


class HrMixin:
    """HR command-center-domain methods mixed into :class:`backend.database.Database`."""

    def insert_hr_feedback(
        self,
        feedback_id: str,
        assignment_id: str,
        hr_user_id: str,
        employee_user_id: Optional[str],
        message: str,
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO hr_feedback (id, assignment_id, hr_user_id, employee_user_id, message, created_at) "
                "VALUES (:id, :aid, :hr, :emp, :msg, :ca)"
            ), {"id": feedback_id, "aid": assignment_id, "hr": hr_user_id, "emp": employee_user_id, "msg": message, "ca": now})
        return {"id": feedback_id, "assignment_id": assignment_id, "message": message, "created_at": now}

    def list_hr_feedback(self, assignment_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT id, assignment_id, hr_user_id, employee_user_id, message, created_at "
                "FROM hr_feedback WHERE assignment_id = :aid ORDER BY created_at DESC"
            ), {"aid": assignment_id}).fetchall()
        return self._rows_to_list(rows)

    def _command_center_dest_country_sql(self) -> str:
        """Prefer denormalized relocation_cases; fall back to wizard_cases from PATCH /api/cases."""
        return (
            "COALESCE(NULLIF(TRIM(rc.host_country), ''), NULLIF(TRIM(wc.dest_country), ''))"
        )

    def _command_center_base_join(self) -> str:
        """Join clause for case_assignments -> relocation_cases (alias rc)."""
        return self._command_center_join_relocation_cases()

    @staticmethod
    def _command_center_display_status(
        raw_status: Optional[str],
        wizard_origin: Optional[str],
        wizard_dest: Optional[str],
    ) -> str:
        """
        If intake wizard has saved route basics but assignment row is still created/assigned,
        show awaiting_intake so HR Command Center matches employee progress.
        """
        s = (raw_status or "").strip().lower()
        if s not in ("assigned", "created"):
            return (raw_status or "").strip() or ""
        if (wizard_origin or "").strip() or (wizard_dest or "").strip():
            return "awaiting_intake"
        return (raw_status or "").strip() or ""

    def _command_center_company_where(self) -> str:
        """WHERE clause for company-scoped, non-archived assignments (needs rc, hu joins)."""
        return (
            "(rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid))"
            " AND ca.archived_at IS NULL"
        )

    def get_command_center_kpis(
        self,
        company_id: Optional[str] = None,
        hr_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Aggregate KPIs. Prefer company_id for company scope; fallback hr_user_id; None = admin (all)."""
        empty = {
            "activeCases": 0, "atRiskCount": 0, "attentionNeededCount": 0,
            "overdueTasksCount": 0, "avgVisaDurationDays": None, "budgetOverrunsCount": 0,
            "actionRequiredCount": 0, "departingSoonCount": 0, "completedCount": 0,
        }
        try:
            join_on = self._command_center_base_join()
            with self.engine.connect() as conn:
                if company_id:
                    sql = f"""
                        SELECT ca.* FROM case_assignments ca
                        LEFT JOIN relocation_cases rc ON {join_on}
                        LEFT JOIN hr_users hu ON hu.profile_id = ca.hr_user_id
                        WHERE {self._command_center_company_where()}
                    """
                    rows = conn.execute(text(sql), {"cid": company_id}).fetchall()
                elif hr_user_id:
                    # Fallback only for HR users without a company association.
                    # NOT EXISTS guard prevents cross-company leakage if the
                    # user *does* have an hr_users row (see list_assignments_for_hr).
                    rows = conn.execute(
                        text(
                            "SELECT * FROM case_assignments "
                            "WHERE hr_user_id = :hr "
                            "AND archived_at IS NULL "
                            "AND NOT EXISTS (SELECT 1 FROM hr_users WHERE profile_id = :hr) "
                            "ORDER BY created_at DESC"
                        ),
                        {"hr": hr_user_id},
                    ).fetchall()
                else:
                    # Admin fallback: include archived for investigation visibility.
                    rows = conn.execute(text("SELECT * FROM case_assignments ORDER BY created_at DESC")).fetchall()
                assignments = self._rows_to_list(rows)
        except Exception:
            return empty

        at_risk = sum(1 for a in assignments if (a.get("risk_status") or "green") == "red")
        attention = sum(1 for a in assignments if (a.get("risk_status") or "green") == "yellow")
        budget_overruns = sum(
            1 for a in assignments
            if a.get("budget_limit") is not None and a.get("budget_estimated") is not None
            and float(a.get("budget_estimated") or 0) > float(a.get("budget_limit") or 0)
        )
        action_required = sum(1 for a in assignments if a.get("status") == "submitted")
        completed = 0
        now = datetime.utcnow()

        def _parse_date(value: Optional[str]) -> Optional[datetime]:
            if not value:
                return None
            try:
                return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except Exception:
                return None

        def _days_until(target: datetime) -> int:
            diff = target - now
            return int(math.ceil(diff.total_seconds() / (60 * 60 * 24)))

        for a in assignments:
            status = a.get("status")
            created_at = _parse_date(a.get("created_at"))
            if status == "approved" and (created_at is None or created_at.year == now.year):
                completed += 1

        departing_soon = 0
        for a in assignments:
            expected = _parse_date(str(a.get("expected_start_date") or ""))
            if expected:
                d = _days_until(expected)
                if 0 <= d <= 30:
                    departing_soon += 1

        a_ids = [a["id"] for a in assignments]
        overdue = 0
        if a_ids:
            try:
                with self.engine.connect() as conn:
                    placeholders = ", ".join(f":a{i}" for i in range(len(a_ids)))
                    r = conn.execute(
                        text(
                            f"SELECT COUNT(*) FROM relocation_tasks "
                            f"WHERE assignment_id IN ({placeholders}) AND status = 'overdue'"
                        ),
                        {f"a{i}": aid for i, aid in enumerate(a_ids)},
                    ).fetchone()
                    overdue = r[0] or 0
            except Exception:
                pass

        return {
            "activeCases": len([a for a in assignments if a.get("status") not in ("closed", "rejected")]),
            "atRiskCount": at_risk,
            "attentionNeededCount": attention,
            "overdueTasksCount": overdue,
            "avgVisaDurationDays": None,
            "budgetOverrunsCount": budget_overruns,
            "actionRequiredCount": action_required,
            "departingSoonCount": departing_soon,
            "completedCount": completed,
        }

    def get_hr_company_id(self, profile_id: str) -> Optional[str]:
        """
        Resolve company_id for HR user.
        Uses hr_users.company_id when set; if the row exists but company_id is NULL/empty,
        falls back to profiles.company_id (Admin assign-company updates profile; hr_users can lag).
        """
        profile = self.get_profile_record(profile_id)
        pcid = (str(profile["company_id"]).strip() if profile and profile.get("company_id") else "") or None
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT company_id FROM hr_users WHERE profile_id = :pid LIMIT 1"),
                {"pid": profile_id},
            ).fetchone()
        if row:
            v = row._mapping.get("company_id")
            hcid = str(v).strip() if v is not None and str(v).strip() else None
            if hcid:
                return hcid
            return pcid
        return pcid

    def list_messages_for_hr(self, hr_user_id: str) -> List[Dict[str, Any]]:
        from ..database import _eq_text  # lazy: avoid import cycle
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT * FROM messages WHERE {_eq_text('hr_user_id', ':hr')} "
                    "ORDER BY created_at DESC"
                ),
                {"hr": hr_user_id},
            ).fetchall()
        return self._rows_to_list(rows)

    def list_hr_conversation_summaries(
        self,
        hr_user_id: str,
        hr_company_id: Optional[str],
        is_admin: bool,
        search_q: Optional[str] = None,
        archive_filter: str = "active",
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        One row per assignment_id: preview, counts, archive pref, company-safe HR visibility.
        archive_filter: 'active' | 'archived' | 'all'
        """
        from ..database import _eq_text, _relocation_cases_join_on  # lazy: avoid import cycle
        lim = max(1, min(int(limit or 50), 200))
        off = max(0, int(offset or 0))

        if is_admin:
            access_sql = "1 = 1"
            access_params: Dict[str, Any] = {}
        elif hr_company_id:
            access_sql = f"""(
                {_eq_text("a.hr_user_id", ":hr_uid")} OR
                {_eq_text("rc.company_id", ":hr_cid")} OR
                (rc.company_id IS NULL AND {_eq_text("hu.company_id", ":hr_cid")})
            )"""
            access_params = {"hr_uid": hr_user_id, "hr_cid": hr_company_id}
        else:
            access_sql = _eq_text("a.hr_user_id", ":hr_uid")
            access_params = {"hr_uid": hr_user_id}

        if archive_filter == "archived":
            archive_sql = "p.archived_at IS NOT NULL"
        elif archive_filter == "all":
            archive_sql = "1 = 1"
        else:
            archive_sql = "(p.archived_at IS NULL)"

        search_sql = "1 = 1"
        search_params: Dict[str, Any] = {}
        if search_q and search_q.strip():
            term = f"%{search_q.strip().lower()}%"
            search_sql = """(
                LOWER(COALESCE(emp_p.full_name, '')) LIKE :sq OR
                LOWER(COALESCE(emp_p.email, '')) LIKE :sq OR
                LOWER(COALESCE(a.employee_identifier, '')) LIKE :sq OR
                LOWER(COALESCE(a.employee_first_name, '')) LIKE :sq OR
                LOWER(COALESCE(a.employee_last_name, '')) LIKE :sq OR
                LOWER(COALESCE(a.case_id, '')) LIKE :sq OR
                LOWER(COALESCE(a.canonical_case_id, '')) LIKE :sq
            )"""
            search_params["sq"] = term

        unread_sql = "1 = 1"
        if unread_only:
            unread_sql = (
                "(SELECT COUNT(*) FROM messages uq WHERE "
                + _eq_text("uq.assignment_id", "m.assignment_id")
                + " AND "
                + _eq_text("uq.recipient_user_id", ":hr_uid_unread")
                + " "
                "AND uq.read_at IS NULL AND uq.dismissed_at IS NULL) > 0"
            )

        order_clause = (
            "ORDER BY last_message_at DESC NULLS LAST"
            if not _is_sqlite
            else "ORDER BY last_message_at DESC"
        )

        params: Dict[str, Any] = {
            **access_params,
            **search_params,
            "hr_uid": hr_user_id,
            "hr_uid_unread": hr_user_id,
            "lim": lim,
            "off": off,
        }

        sql_full = f"""
            SELECT
                m.assignment_id,
                MAX(m.created_at) AS last_message_at,
                COUNT(*) AS message_count,
                (SELECT body FROM messages m2 WHERE {_eq_text("m2.assignment_id", "m.assignment_id")}
                 ORDER BY m2.created_at DESC LIMIT 1) AS last_body,
                (SELECT subject FROM messages m2s WHERE {_eq_text("m2s.assignment_id", "m.assignment_id")}
                 ORDER BY m2s.created_at DESC LIMIT 1) AS last_subject,
                (SELECT COUNT(*) FROM messages m3 WHERE {_eq_text("m3.assignment_id", "m.assignment_id")}
                 AND {_eq_text("m3.recipient_user_id", ":hr_uid_unread")}
                 AND m3.read_at IS NULL AND m3.dismissed_at IS NULL) AS unread_count,
                MAX(p.archived_at) AS archived_at,
                MAX(a.employee_user_id) AS employee_user_id,
                MAX(a.hr_user_id) AS assignment_hr_user_id,
                MAX(a.employee_identifier) AS employee_identifier,
                MAX(a.employee_first_name) AS employee_first_name,
                MAX(a.employee_last_name) AS employee_last_name,
                MAX(a.status) AS assignment_status,
                MAX(emp_p.full_name) AS employee_full_name,
                MAX(emp_p.email) AS employee_email,
                MAX(COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)) AS case_id
            FROM messages m
            INNER JOIN case_assignments a ON {_eq_text("a.id", "m.assignment_id")}
            LEFT JOIN relocation_cases rc ON {_relocation_cases_join_on("a")}
            LEFT JOIN hr_users hu ON {_eq_text("hu.profile_id", "a.hr_user_id")}
            LEFT JOIN profiles emp_p ON {_eq_text("emp_p.id", "a.employee_user_id")}
            LEFT JOIN message_conversation_prefs p ON {_eq_text("p.user_id", ":hr_uid")} AND {_eq_text("p.assignment_id", "m.assignment_id")}
            WHERE m.assignment_id IS NOT NULL
              AND ({access_sql})
              AND ({archive_sql})
              AND ({search_sql})
              AND ({unread_sql})
            GROUP BY m.assignment_id
            {order_clause}
            LIMIT :lim OFFSET :off
        """

        # Postgres without runtime DDL often lacks: message_conversation_prefs, messages.read_at/*,
        # case_assignments.canonical_case_id / employee_* name columns. Degraded query keeps messages working.
        search_compat_sql = "1 = 1"
        search_compat_params: Dict[str, Any] = {}
        if search_q and search_q.strip():
            term = f"%{search_q.strip().lower()}%"
            search_compat_sql = """(
                LOWER(COALESCE(a.employee_identifier, '')) LIKE :sqc OR
                LOWER(COALESCE(a.case_id, '')) LIKE :sqc
            )"""
            search_compat_params["sqc"] = term
        compat_params = {**access_params, **search_compat_params, "hr_uid": hr_user_id, "lim": lim, "off": off}
        null_arch = "NULL" if _is_sqlite else "CAST(NULL AS TEXT)"
        sql_compat = f"""
            SELECT
                m.assignment_id,
                MAX(m.created_at) AS last_message_at,
                COUNT(*) AS message_count,
                (SELECT body FROM messages m2 WHERE {_eq_text("m2.assignment_id", "m.assignment_id")}
                 ORDER BY m2.created_at DESC LIMIT 1) AS last_body,
                (SELECT subject FROM messages m2s WHERE {_eq_text("m2s.assignment_id", "m.assignment_id")}
                 ORDER BY m2s.created_at DESC LIMIT 1) AS last_subject,
                0 AS unread_count,
                {null_arch} AS archived_at,
                MAX(a.employee_user_id) AS employee_user_id,
                MAX(a.hr_user_id) AS assignment_hr_user_id,
                MAX(a.employee_identifier) AS employee_identifier,
                {null_arch} AS employee_first_name,
                {null_arch} AS employee_last_name,
                MAX(a.status) AS assignment_status,
                MAX(emp_p.full_name) AS employee_full_name,
                MAX(emp_p.email) AS employee_email,
                MAX(a.case_id) AS case_id
            FROM messages m
            INNER JOIN case_assignments a ON {_eq_text("a.id", "m.assignment_id")}
            LEFT JOIN relocation_cases rc ON {_relocation_cases_join_on("a", "simple")}
            LEFT JOIN hr_users hu ON {_eq_text("hu.profile_id", "a.hr_user_id")}
            LEFT JOIN profiles emp_p ON {_eq_text("emp_p.id", "a.employee_user_id")}
            WHERE m.assignment_id IS NOT NULL
              AND ({access_sql})
              AND ({search_compat_sql})
            GROUP BY m.assignment_id
            {order_clause}
            LIMIT :lim OFFSET :off
        """

        rows: List[Any] = []
        try:
            with self.engine.connect() as conn:
                rows = list(conn.execute(text(sql_full), params).fetchall())
        except (ProgrammingError, OperationalError) as e:
            log.warning(
                "list_hr_conversation_summaries: full query failed (%s), using compat query",
                e,
            )
            try:
                with self.engine.connect() as conn:
                    rows = list(conn.execute(text(sql_compat), compat_params).fetchall())
            except (ProgrammingError, OperationalError):
                raise

        out: List[Dict[str, Any]] = []
        for row in rows:
            r = dict(row._mapping)
            aid = r.get("assignment_id")
            if not aid:
                continue
            # AIQ-1325b: scrub a leading '[verify]' marker (verify/e2e seed) from
            # the inbox preview at read time — display-only, stored row untouched.
            from .test_data_filter import strip_verify_prefix
            raw_body = strip_verify_prefix(r.get("last_body") or "") or ""
            raw_sub = strip_verify_prefix(r.get("last_subject") or "") or ""
            preview_src = raw_body.strip() or raw_sub.strip() or ""
            last_body = preview_src[:100]
            if len(preview_src) > 100:
                last_body = last_body.rstrip() + "…"

            fn = (r.get("employee_first_name") or "").strip()
            ln = (r.get("employee_last_name") or "").strip()
            composed = (fn + " " + ln).strip()
            emp_name = (
                r.get("employee_full_name")
                or composed
                or r.get("employee_identifier")
                or "Employee"
            )
            unread = int(r.get("unread_count") or 0)
            out.append({
                "assignment_id": aid,
                "case_id": r.get("case_id"),
                "employee_user_id": r.get("employee_user_id"),
                "employee_name": emp_name,
                "employee_email": r.get("employee_email"),
                "employee_identifier": r.get("employee_identifier"),
                "last_message_preview": last_body,
                "last_message_at": r.get("last_message_at"),
                "message_count": int(r.get("message_count") or 0),
                "unread_count": unread,
                "has_unread": unread > 0,
                "archived_at": r.get("archived_at"),
                "assignment_status": r.get("assignment_status"),
            })
        return out

    def get_hr_readiness_summary(self, assignment_id: str) -> Dict[str, Any]:
        """Compact payload for first paint; no full checklist rows."""
        from .. import provenance_catalog  # backend.provenance_catalog (NOT backend.db)

        raw_dest, dest_key = self.resolve_readiness_destination_for_assignment(assignment_id)
        prof = self.get_employee_profile(assignment_id)
        asn = self.get_assignment_by_id(assignment_id)
        route_key = resolve_readiness_route_key(asn or {}, prof) if asn else DEFAULT_ROUTE_KEY
        if not dest_key:
            return {
                "resolved": False,
                "reason": "no_destination",
                "destination_raw": raw_dest,
                "destination_key": None,
                "route_key": route_key,
                **provenance_catalog.degraded_readiness_payload(
                    "no_destination", raw_dest, None, route_key
                ),
            }
        if not self._readiness_store_available():
            return {
                "resolved": False,
                "reason": "readiness_store_unavailable",
                "destination_raw": raw_dest,
                "destination_key": dest_key,
                "route_key": route_key,
                **provenance_catalog.degraded_readiness_payload(
                    "readiness_store_unavailable", raw_dest, dest_key, route_key
                ),
            }
        tmpl = self.get_readiness_template(dest_key, route_key)
        if not tmpl:
            return {
                "resolved": False,
                "reason": "no_template",
                "destination_raw": raw_dest,
                "destination_key": dest_key,
                "route_key": route_key,
                **provenance_catalog.degraded_readiness_payload(
                    "no_template", raw_dest, dest_key, route_key
                ),
            }
        bind = self.ensure_case_readiness_binding(assignment_id)
        tid = tmpl["id"]
        watchouts = []
        try:
            watchouts = json.loads(tmpl.get("watchouts_json") or "[]")
        except Exception:
            watchouts = []
        if not isinstance(watchouts, list):
            watchouts = []
        top_watchouts = [str(w) for w in watchouts[:3]]

        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT
                        COUNT(c.id) AS total,
                        SUM(CASE WHEN COALESCE(s.status, 'pending') IN ('done', 'waived') THEN 1 ELSE 0 END) AS doneish
                    FROM readiness_template_checklist_items c
                    LEFT JOIN case_readiness_checklist_state s
                        ON s.template_checklist_id = c.id AND s.assignment_id = :aid
                    WHERE c.template_id = :tid
                    """
                ),
                {"aid": assignment_id, "tid": tid},
            ).fetchone()
        total_chk = int(row[0] or 0) if row else 0
        done_chk = int(row[1] or 0) if row else 0
        pending_chk = max(0, total_chk - done_chk)

        next_ms = None
        with self.engine.connect() as conn:
            mrows = conn.execute(
                text(
                    """
                    SELECT m.id, m.title, m.sort_order, m.phase, m.relative_timing, ms.completed_at
                    FROM readiness_template_milestones m
                    LEFT JOIN case_readiness_milestone_state ms
                        ON ms.template_milestone_id = m.id AND ms.assignment_id = :aid
                    WHERE m.template_id = :tid
                    ORDER BY m.sort_order ASC, m.id ASC
                    """
                ),
                {"aid": assignment_id, "tid": tid},
            ).fetchall()
        for mr in mrows:
            r = dict(mr._mapping)
            if not r.get("completed_at"):
                next_ms = {
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "phase": r.get("phase"),
                    "relative_timing": r.get("relative_timing"),
                }
                break

        base_summary = {
            "resolved": True,
            "assignment_id": assignment_id,
            "destination_raw": raw_dest,
            "destination_key": dest_key,
            "route_key": route_key,
            "template_id": tid,
            "route_title": tmpl.get("route_title"),
            "employee_summary": tmpl.get("employee_summary"),
            "hr_summary": tmpl.get("hr_summary"),
            "top_watchouts": top_watchouts,
            "checklist": {
                "total": total_chk,
                "completed_or_waived": done_chk,
                "pending": pending_chk,
            },
            "next_milestone": next_ms,
            "updated_at": tmpl.get("updated_at"),
            "case_readiness_updated_at": (bind or {}).get("updated_at"),
        }
        prov = provenance_catalog.readiness_summary_provenance_block(dest_key, route_key, True)
        return {**base_summary, **prov}

    def get_hr_readiness_detail(self, assignment_id: str) -> Dict[str, Any]:
        """Full checklist + milestones merged with case state (two queries)."""
        from .. import provenance_catalog  # backend.provenance_catalog (NOT backend.db)

        summary = self.get_hr_readiness_summary(assignment_id)
        if not summary.get("resolved"):
            return {"summary": summary, "checklist_items": [], "milestones": []}
        tid = summary["template_id"]
        with self.engine.connect() as conn:
            crows = conn.execute(
                text(
                    """
                    SELECT c.id, c.sort_order, c.title, c.owner_role, c.required, c.depends_on_sort_order,
                           c.notes_employee, c.notes_hr, c.stable_key,
                           COALESCE(s.status, 'pending') AS status, s.notes AS state_notes, s.updated_at AS state_updated_at
                    FROM readiness_template_checklist_items c
                    LEFT JOIN case_readiness_checklist_state s
                        ON s.template_checklist_id = c.id AND s.assignment_id = :aid
                    WHERE c.template_id = :tid
                    ORDER BY c.sort_order ASC, c.id ASC
                    """
                ),
                {"aid": assignment_id, "tid": tid},
            ).fetchall()
            mrows = conn.execute(
                text(
                    """
                    SELECT m.id, m.sort_order, m.phase, m.title, m.body_employee, m.body_hr, m.owner_role, m.relative_timing,
                           ms.completed_at, ms.notes AS state_notes, ms.updated_at AS state_updated_at
                    FROM readiness_template_milestones m
                    LEFT JOIN case_readiness_milestone_state ms
                        ON ms.template_milestone_id = m.id AND ms.assignment_id = :aid
                    WHERE m.template_id = :tid
                    ORDER BY m.sort_order ASC, m.id ASC
                    """
                ),
                {"aid": assignment_id, "tid": tid},
            ).fetchall()
        checklist_items = [dict(r._mapping) for r in crows]
        milestones = [dict(r._mapping) for r in mrows]
        dk = str(summary.get("destination_key") or "")
        rk = str(summary.get("route_key") or DEFAULT_ROUTE_KEY)
        enriched_checklist = [
            provenance_catalog.enrich_checklist_row(row, dk, rk) for row in checklist_items
        ]
        detail_provenance = provenance_catalog.readiness_summary_provenance_block(dk, rk, True)
        return {
            "summary": summary,
            "checklist_items": enriched_checklist,
            "milestones": milestones,
            "provenance": detail_provenance,
        }

    def list_hr_backlog(self, org_id: str) -> List[Dict[str, Any]]:
        """HR-side backlog: every employee_task for the org that is still
        pending (status='pending' or 'revision_requested'). Used by the
        /api/hr/backlog endpoint to give HR a single-page view of "what my
        employees still owe us" across all their cases.

        Joins to profiles for employee_name/email when available; falls back
        to a no-join query if the profiles join fails (some local schemas
        don't have all the columns yet)."""
        # Try the joined query first — gives us employee names directly.
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text(
                    """
                    -- AIQ-1591: column was renamed `type` → `task_type` (migration
                    -- 20260513280000). Alias back to `type` so the HrBacklogTask contract
                    -- (frontend expects `type`) is unchanged; the pre-fix `t.type` raised
                    -- `column "type" does not exist`, which forced the fallback below —
                    -- and the fallback used `type` too, so the HR backlog was always empty.
                    SELECT t.id, t.case_id, t.employee_id, t.org_id, t.task_type AS type, t.title,
                           t.description, t.due_date, t.status, t.required_file_upload,
                           t.submitted_at, t.reviewed_at, t.created_at, t.updated_at,
                           p.full_name AS employee_name, p.email AS employee_email
                    FROM employee_tasks t
                    LEFT JOIN profiles p ON CAST(p.id AS TEXT) = t.employee_id
                    WHERE t.org_id = :org
                      AND t.status IN ('pending', 'revision_requested')
                    ORDER BY
                        CASE t.status
                            WHEN 'revision_requested' THEN 1
                            WHEN 'pending'            THEN 2
                            ELSE 3
                        END,
                        t.due_date ASC NULLS LAST,
                        t.created_at ASC
                    """
                ), {"org": org_id}).fetchall()
                result = []
                for row in rows:
                    d = dict(row._mapping)
                    for k in ("due_date", "submitted_at", "reviewed_at", "created_at", "updated_at"):
                        if d.get(k) is not None:
                            d[k] = str(d[k])
                    result.append(d)
                return result
        except Exception as e:
            log.warning("list_hr_backlog joined query failed (will retry without join): %s", e)

        # Fallback: no join. Frontend will show employee_id (uuid prefix) only.
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text(
                    """
                    SELECT id, case_id, employee_id, org_id, task_type AS type, title, description,
                           due_date, status, required_file_upload, submitted_at,
                           reviewed_at, created_at, updated_at
                    FROM employee_tasks
                    WHERE org_id = :org
                      AND status IN ('pending', 'revision_requested')
                    ORDER BY
                        CASE status
                            WHEN 'revision_requested' THEN 1
                            WHEN 'pending'            THEN 2
                            ELSE 3
                        END,
                        due_date ASC NULLS LAST,
                        created_at ASC
                    """
                ), {"org": org_id}).fetchall()
                result = []
                for row in rows:
                    d = dict(row._mapping)
                    for k in ("due_date", "submitted_at", "reviewed_at", "created_at", "updated_at"):
                        if d.get(k) is not None:
                            d[k] = str(d[k])
                    result.append(d)
                return result
        except Exception as e:
            log.warning("list_hr_backlog fallback query failed org_id=%s: %s", org_id, e)
            return []
