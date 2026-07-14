"""[AUDIT-C1.6a] Vendors-domain DB methods, extracted from backend/database.py.

These were methods on the monolithic ``Database`` class; they live here as a
mixin (:class:`VendorsMixin`) that ``Database`` inherits, so every caller keeps
working unchanged via normal MRO. Pure relocation; ``..database`` module
helpers are imported lazily in-method to avoid an import cycle.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import json
import logging
import uuid

from sqlalchemy import text

from ..db_config import DATABASE_URL as _raw_url

log = logging.getLogger(__name__)


class VendorsMixin:
    """Vendors-domain methods mixed into :class:`backend.database.Database`."""

    def create_rfq(
        self,
        case_id: str,
        creator_user_id: str,
        items: List[Dict[str, Any]],
        vendor_ids: List[str],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        rfq_id = str(uuid.uuid4())
        rfq_ref = f"RFQ-{datetime.utcnow().strftime('%Y%m%d')}-{rfq_id.split('-')[0]}"
        with self.engine.begin() as conn:
            self._exec(
                conn,
                """
                INSERT INTO rfqs (id, rfq_ref, case_id, canonical_case_id, created_by_user_id, status, created_at)
                VALUES (:id, :rfq_ref, :case_id, :canonical_case_id, :created_by_user_id, :status, :created_at)
                """,
                {
                    "id": rfq_id,
                    "rfq_ref": rfq_ref,
                    "case_id": case_id,
                    "canonical_case_id": case_id,
                    "created_by_user_id": creator_user_id,
                    "status": "sent",
                    "created_at": now,
                },
                op_name="create_rfq",
                request_id=request_id,
            )
            for item in items:
                self._exec(
                    conn,
                    """
                    INSERT INTO rfq_items (id, rfq_id, service_key, requirements, created_at)
                    VALUES (:id, :rfq_id, :service_key, :requirements, :created_at)
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "rfq_id": rfq_id,
                        "service_key": item.get("service_key", "unknown"),
                        "requirements": json.dumps(item.get("requirements", {})),
                        "created_at": now,
                    },
                    op_name="create_rfq_item",
                    request_id=request_id,
                )
            for vendor_id in vendor_ids:
                self._exec(
                    conn,
                    """
                    INSERT INTO rfq_recipients (id, rfq_id, vendor_id, status, last_activity_at)
                    VALUES (:id, :rfq_id, :vendor_id, :status, :last_activity_at)
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "rfq_id": rfq_id,
                        "vendor_id": vendor_id,
                        "status": "sent",
                        "last_activity_at": now,
                    },
                    op_name="create_rfq_recipient",
                    request_id=request_id,
                )
            self._exec(
                conn,
                """
                INSERT INTO quote_conversations (id, thread_type, case_id, rfq_id, created_at)
                VALUES (:id, :thread_type, :case_id, :rfq_id, :created_at)
                """,
                {
                    "id": str(uuid.uuid4()),
                    "thread_type": "vendor_quote",
                    "case_id": case_id,
                    "rfq_id": rfq_id,
                    "created_at": now,
                },
                op_name="create_quote_conversation",
                request_id=request_id,
            )
        return {"id": rfq_id, "rfq_ref": rfq_ref}

    def _list_rfq_items(self, conn, rfq_id: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            text("SELECT * FROM rfq_items WHERE rfq_id = :rfq_id ORDER BY created_at"),
            {"rfq_id": rfq_id},
        ).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["requirements"] = self._json_load(item.get("requirements")) or {}
        return items

    def _list_rfq_recipients(self, conn, rfq_id: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            text("SELECT * FROM rfq_recipients WHERE rfq_id = :rfq_id"),
            {"rfq_id": rfq_id},
        ).fetchall()
        return self._rows_to_list(rows)

    def get_rfq(
        self, rfq_id: str, request_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get single RFQ with items and recipients."""
        with self.engine.connect() as conn:
            row = self._exec(
                conn,
                "SELECT * FROM rfqs WHERE id = :id",
                {"id": rfq_id},
                op_name="get_rfq",
                request_id=request_id,
            ).fetchone()
        if not row:
            return None
        rfq = self._row_to_dict(row)
        with self.engine.connect() as conn:
            rfq["items"] = self._list_rfq_items(conn, rfq_id)
            rfq["recipients"] = self._list_rfq_recipients(conn, rfq_id)
        return rfq

    def list_quotes_for_rfq(
        self, rfq_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List quotes for an RFQ with quote_lines."""
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                "SELECT * FROM quotes WHERE rfq_id = :rfq_id ORDER BY created_at DESC",
                {"rfq_id": rfq_id},
                op_name="list_quotes_for_rfq",
                request_id=request_id,
            ).fetchall()
            quotes = self._rows_to_list(rows)
            for q in quotes:
                line_rows = conn.execute(
                    text("SELECT * FROM quote_lines WHERE quote_id = :quote_id ORDER BY id"),
                    {"quote_id": q["id"]},
                ).fetchall()
                q["quote_lines"] = self._rows_to_list(line_rows)
        return quotes

    def create_quote(
        self,
        rfq_id: str,
        vendor_id: str,
        currency: str,
        total_amount: float,
        valid_until: Optional[str],
        quote_lines: List[Dict[str, Any]],
        created_by_user_id: Optional[str],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a quote with line items."""
        quote_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            self._exec(
                conn,
                """INSERT INTO quotes (id, rfq_id, vendor_id, currency, total_amount, valid_until, status, created_by_user_id, created_at)
                   VALUES (:id, :rfq_id, :vendor_id, :currency, :total_amount, :valid_until, :status, :created_by_user_id, :created_at)""",
                {
                    "id": quote_id,
                    "rfq_id": rfq_id,
                    "vendor_id": vendor_id,
                    "currency": currency,
                    "total_amount": total_amount,
                    "valid_until": valid_until,
                    "status": "proposed",
                    "created_by_user_id": created_by_user_id,
                    "created_at": now,
                },
                op_name="create_quote",
                request_id=request_id,
            )
            for line in quote_lines:
                self._exec(
                    conn,
                    """INSERT INTO quote_lines (id, quote_id, label, amount)
                       VALUES (:id, :quote_id, :label, :amount)""",
                    {
                        "id": str(uuid.uuid4()),
                        "quote_id": quote_id,
                        "label": line.get("label", ""),
                        "amount": float(line.get("amount", 0)),
                    },
                    op_name="create_quote_line",
                    request_id=request_id,
                )
        return {
            "id": quote_id,
            "rfq_id": rfq_id,
            "vendor_id": vendor_id,
            "currency": currency,
            "total_amount": total_amount,
            "valid_until": valid_until,
            "status": "proposed",
        }

    def update_quote_status(
        self,
        quote_id: str,
        status: str,
        request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update quote status (e.g. accepted, rejected).

        AIQ-1524: this used `engine.connect()`, and `_exec` never commits — so the UPDATE
        was rolled back on context exit and the status change was silently discarded. It
        went unnoticed only because `quotes` has never had a row in prod. `engine.begin()`
        commits on exit, which is what `create_quote` above already does.
        """
        with self.engine.begin() as conn:
            self._exec(
                conn,
                "UPDATE quotes SET status = :status WHERE id = :id",
                {"status": status, "id": quote_id},
                op_name="update_quote_status",
                request_id=request_id,
            )
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM quotes WHERE id = :id"), {"id": quote_id}
            ).fetchone()
        return self._row_to_dict(row)

    def set_rfq_preferred_quote(
        self,
        rfq_id: str,
        quote_id: str,
        user_id: Optional[str],
        request_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """AIQ-1524: the EMPLOYEE proposes an offer. A proposal commits no spend, so this
        deliberately does NOT touch quotes.status — only HR's validation does that."""
        with self.engine.begin() as conn:
            self._exec(
                conn,
                """UPDATE rfqs
                      SET preferred_quote_id = :quote_id,
                          preferred_by_user_id = :user_id,
                          preferred_at = :now
                    WHERE id = :rfq_id""",
                {
                    "quote_id": quote_id,
                    "user_id": user_id,
                    "now": datetime.utcnow().isoformat(),
                    "rfq_id": rfq_id,
                },
                op_name="set_rfq_preferred_quote",
                request_id=request_id,
            )
        return self.get_rfq(rfq_id, request_id=request_id)

    def validate_rfq_quote(
        self,
        rfq_id: str,
        quote_id: str,
        user_id: Optional[str],
        reason: Optional[str],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """AIQ-1524: HR (the payer) validates the offer the company will pay for.

        One transaction, because these must not diverge:
          * the chosen quote  -> accepted
          * every sibling     -> rejected  (an RFQ ends with exactly one accepted offer)
          * the RFQ           -> records who validated, when, and why
          * case_services     -> the agreed cost, but ONLY where it can be attributed honestly

        Returns a dict describing what was written, including `cost_attributed` and, when it
        was not, `cost_not_attributed_reason` — we never guess a per-service figure.
        """
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            quote = conn.execute(
                text("SELECT * FROM quotes WHERE id = :id AND rfq_id = :rfq_id"),
                {"id": quote_id, "rfq_id": rfq_id},
            ).fetchone()
            if not quote:
                return {"ok": False, "error": "quote_not_found"}
            q = self._row_to_dict(quote) or {}

            self._exec(
                conn,
                "UPDATE quotes SET status = 'accepted' WHERE id = :id",
                {"id": quote_id},
                op_name="validate_quote_accept",
                request_id=request_id,
            )
            self._exec(
                conn,
                "UPDATE quotes SET status = 'rejected' WHERE rfq_id = :rfq_id AND id <> :id",
                {"rfq_id": rfq_id, "id": quote_id},
                op_name="validate_quote_reject_siblings",
                request_id=request_id,
            )
            self._exec(
                conn,
                """UPDATE rfqs
                      SET validated_quote_id = :quote_id,
                          validated_by_user_id = :user_id,
                          validated_at = :now,
                          validation_reason = :reason,
                          status = 'closed'
                    WHERE id = :rfq_id""",
                {
                    "quote_id": quote_id,
                    "user_id": user_id,
                    "now": now,
                    "reason": reason,
                    "rfq_id": rfq_id,
                },
                op_name="validate_rfq",
                request_id=request_id,
            )

            rfq_row = conn.execute(
                text("SELECT case_id FROM rfqs WHERE id = :id"), {"id": rfq_id}
            ).fetchone()
            case_id = (self._row_to_dict(rfq_row) or {}).get("case_id")
            items = [
                self._row_to_dict(r) or {}
                for r in conn.execute(
                    text("SELECT service_key FROM rfq_items WHERE rfq_id = :id ORDER BY created_at"),
                    {"id": rfq_id},
                ).fetchall()
            ]
            lines = [
                self._row_to_dict(r) or {}
                for r in conn.execute(
                    text("SELECT label, amount FROM quote_lines WHERE quote_id = :id"),
                    {"id": quote_id},
                ).fetchall()
            ]

            # Attribute the agreed cost to services ONLY where it is unambiguous. Mirrors the
            # HR cap comparison (AIQ-1526): a lump sum covering several services cannot be
            # split across them without inventing numbers, so we record nothing rather than
            # write a figure nobody quoted.
            attribution: List[tuple] = []
            not_attributed: Optional[str] = None
            if not case_id or not items:
                not_attributed = "no_case_or_items"
            elif len(items) == 1:
                attribution = [(items[0].get("service_key"), q.get("total_amount"))]
            elif len(lines) == len(items):
                attribution = [
                    (items[i].get("service_key"), lines[i].get("amount")) for i in range(len(items))
                ]
            else:
                not_attributed = "lump_sum_across_multiple_services"

            for service_key, amount in attribution:
                if not service_key or amount is None:
                    continue
                self._exec(
                    conn,
                    """UPDATE case_services
                          SET estimated_cost = :amount,
                              currency = :currency,
                              updated_at = :now
                        WHERE case_id = :case_id AND service_key = :service_key""",
                    {
                        "amount": amount,
                        "currency": q.get("currency") or "EUR",
                        "now": now,
                        "case_id": case_id,
                        "service_key": service_key,
                    },
                    op_name="validate_quote_write_estimated_cost",
                    request_id=request_id,
                )

        return {
            "ok": True,
            "quote_id": quote_id,
            "rfq_id": rfq_id,
            "quote": {**q, "status": "accepted"},
            "cost_attributed": bool(attribution),
            "cost_not_attributed_reason": not_attributed,
            "services_costed": [sk for sk, _ in attribution],
        }

    def list_rfqs_for_vendor(
        self, vendor_id: str, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List RFQs where rfq_recipients.vendor_id = vendor_id."""
        with self.engine.connect() as conn:
            rows = self._exec(
                conn,
                """SELECT r.* FROM rfqs r
                   INNER JOIN rfq_recipients rr ON rr.rfq_id = r.id
                   WHERE rr.vendor_id = :vendor_id
                   ORDER BY r.created_at DESC""",
                {"vendor_id": vendor_id},
                op_name="list_rfqs_for_vendor",
                request_id=request_id,
            ).fetchall()
        rfqs = self._rows_to_list(rows)
        for rfq in rfqs:
            with self.engine.connect() as c:
                rfq["items"] = self._list_rfq_items(c, rfq["id"])
                rfq["recipients"] = self._list_rfq_recipients(c, rfq["id"])
        return rfqs

    def validate_vendor_ids(
        self, vendor_ids: List[str], request_id: Optional[str] = None
    ) -> Tuple[List[str], List[str]]:
        """[AIQ-1520] Check each RFQ recipient id exists in `suppliers`.

        Was `SELECT 1 FROM vendors`. `vendors` is deprecated for writes and holds 8 rows
        against 90 suppliers, so this gate rejected almost every real recipient. RFQ
        recipients are suppliers now (migration 20260918000000).

        The name is kept because callers and a test refer to it. Returns (valid_ids, errors).
        """
        valid: List[str] = []
        errors: List[str] = []
        for vid in vendor_ids:
            if not vid or not str(vid).strip():
                continue
            vid = str(vid).strip()
            try:
                with self.engine.connect() as conn:
                    row = self._exec(
                        conn,
                        "SELECT 1 FROM suppliers WHERE id = :vid",
                        {"vid": vid},
                        op_name="validate_recipient_supplier_id",
                        request_id=request_id,
                    ).fetchone()
                if row:
                    valid.append(vid)
                else:
                    errors.append(f"Supplier {vid} is not in the supplier registry.")
            except Exception as e:
                # Was: valid.append(vid) — a silent fail-OPEN. A validation gate that accepts
                # the id when its own check errored is not a gate. Fail closed, and say so.
                log.warning("validate_vendor_ids: supplier check failed for %s: %s", vid, e)
                errors.append(f"Could not verify supplier {vid}; not adding it to the RFQ.")
        return (valid, errors)

    def _vendor_names_for_rfq(self, rfq_id: Optional[str]) -> Optional[str]:
        if not rfq_id or not str(rfq_id).strip():
            return None
        try:
            with self.engine.connect() as conn:
                # [AIQ-1520] rr.vendor_id holds a suppliers.id now, not a vendors.id.
                # Joining `vendors` would match nothing and the employee's quote-thread
                # label would silently degrade to "Service provider".
                rows = conn.execute(
                    text(
                        "SELECT s.name AS name FROM rfq_recipients rr "
                        "LEFT JOIN suppliers s ON s.id = rr.vendor_id "
                        "WHERE rr.rfq_id = :r ORDER BY rr.created_at"
                    ),
                    {"r": str(rfq_id).strip()},
                ).fetchall()
            names: List[str] = []
            for row in rows:
                m = row._mapping if hasattr(row, "_mapping") else dict(row)
                nm = (m.get("name") or "").strip()
                if nm:
                    names.append(nm)
            if not names:
                return None
            if len(names) == 1:
                return names[0]
            return f"{names[0]} (+{len(names) - 1})"
        except Exception:
            return None

    def list_quote_threads_for_employee(self, employee_user_id: str, request_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Quote / vendor threads for all assignments linked to this employee.
        Same quote_messages model as RFQ flows; empty list if none.
        """
        linked = self.list_linked_assignments_for_employee(employee_user_id, request_id=request_id)
        if not linked:
            return []
        case_to_assignment: Dict[str, str] = {}
        for a in linked:
            aid = a.get("id")
            if not aid:
                continue
            for cid_raw in (a.get("canonical_case_id"), a.get("case_id")):
                cid = (cid_raw or "").strip()
                if cid:
                    case_to_assignment[cid] = str(aid).strip()
        case_ids = list(case_to_assignment.keys())
        if not case_ids:
            return []
        n = len(case_ids)
        ph = ", ".join(f":c{i}" for i in range(n))
        params = {f"c{i}": case_ids[i] for i in range(n)}
        sql = (
            f"SELECT qc.id AS conversation_id, qc.thread_type, qc.case_id, qc.rfq_id, qc.created_at, r.rfq_ref AS rfq_ref "
            f"FROM quote_conversations qc "
            f"LEFT JOIN rfqs r ON r.id = qc.rfq_id "
            f"WHERE qc.case_id IN ({ph}) "
            f"ORDER BY qc.created_at DESC"
        )
        try:
            with self.engine.connect() as conn:
                rows = self._exec(
                    conn, sql, params, op_name="list_quote_conversations_for_employee", request_id=request_id
                ).fetchall()
        except Exception:
            return []
        out: List[Dict[str, Any]] = []
        for row in rows:
            m = row._mapping if hasattr(row, "_mapping") else dict(row)
            cid = (m.get("case_id") or "").strip()
            aid = case_to_assignment.get(cid)
            conv_id = m.get("conversation_id")
            if not aid or not conv_id:
                continue
            label = self._vendor_names_for_rfq(m.get("rfq_id")) or "Service provider"
            try:
                with self.engine.connect() as conn:
                    qrows = conn.execute(
                        text(
                            "SELECT * FROM quote_messages WHERE conversation_id = :qid ORDER BY created_at ASC"
                        ),
                        {"qid": str(conv_id)},
                    ).fetchall()
                msgs = self._rows_to_list(qrows)
            except Exception:
                msgs = []
            out.append(
                {
                    "conversation_id": str(conv_id),
                    "assignment_id": aid,
                    "case_id": cid,
                    "rfq_id": m.get("rfq_id"),
                    "rfq_ref": m.get("rfq_ref"),
                    "thread_type": m.get("thread_type"),
                    "counterparty_label": label,
                    "messages": msgs,
                }
            )
        return out

    def get_provider_status_grid(
        self,
        company_id: Optional[str] = None,
        hr_user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Returns a matrix of (case × provider_service_type) status cells
        for the HR Provider Status Grid view.

        Each row represents one active case_assignment. Cells contain one
        of: 'on-track' | 'at-risk' | 'blocked' | 'complete' | 'not-assigned'.

        Isolation: same company_id / hr_user_id guard as list_command_center_cases.
        """
        PROVIDER_TYPES = ("housing", "immigration", "shipping", "other")

        def _cell_status(tasks: List[Dict[str, Any]]) -> str:
            if not tasks:
                return "not-assigned"
            statuses = [t.get("status", "") for t in tasks]
            due_dates = [t.get("due_date") for t in tasks]
            today_str = datetime.utcnow().date().isoformat()
            if "blocked" in statuses:
                return "blocked"
            overdue = any(
                s != "completed" and d is not None and str(d) < today_str
                for s, d in zip(statuses, due_dates)
            )
            if overdue:
                return "at-risk"
            if all(s == "completed" for s in statuses):
                return "complete"
            return "on-track"

        try:
            rc_join = self._command_center_join_relocation_cases()
            wc_join = self._command_center_join_wizard_cases()
            dest_sql = self._command_center_dest_country_sql()

            with self.engine.connect() as conn:
                params: Dict[str, Any] = {}
                if company_id:
                    where = "WHERE " + self._command_center_company_where()
                    params["cid"] = company_id
                elif hr_user_id:
                    where = (
                        "WHERE ca.hr_user_id = :hr "
                        "AND ca.archived_at IS NULL "
                        "AND NOT EXISTS (SELECT 1 FROM hr_users WHERE profile_id = :hr)"
                    )
                    params["hr"] = hr_user_id
                else:
                    where = "WHERE ca.archived_at IS NULL"

                cases_sql = f"""
                    SELECT
                        ca.id,
                        ca.employee_identifier,
                        ca.employee_first_name,
                        ca.employee_last_name,
                        ca.coordination_status,
                        ca.expected_start_date,
                        {dest_sql} AS dest_country
                    FROM case_assignments ca
                    LEFT JOIN relocation_cases rc ON {rc_join}
                    LEFT JOIN wizard_cases wc ON {wc_join}
                    LEFT JOIN hr_users hu ON hu.profile_id = ca.hr_user_id
                    {where}
                    ORDER BY ca.expected_start_date ASC NULLS LAST, ca.created_at DESC
                """
                case_rows = conn.execute(text(cases_sql), params).fetchall()
                cases = self._rows_to_list(case_rows)

                if not cases:
                    return []

                case_ids = [c["id"] for c in cases]
                # Parameterise the IN list safely
                id_params = {f"cid{i}": cid for i, cid in enumerate(case_ids)}
                id_placeholders = ", ".join(f":cid{i}" for i in range(len(case_ids)))

                tasks_sql = f"""
                    SELECT
                        pt.case_id,
                        pt.status,
                        pt.due_date,
                        COALESCE(p.service_type, 'other') AS service_type
                    FROM provider_tasks pt
                    JOIN providers p ON p.id = pt.provider_id
                    WHERE pt.case_id IN ({id_placeholders})
                """
                task_rows = conn.execute(text(tasks_sql), id_params).fetchall()
                tasks_list = self._rows_to_list(task_rows)

            # Group tasks by (case_id, service_type)
            from collections import defaultdict
            task_map: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
            for t in tasks_list:
                svc = t.get("service_type") or "other"
                if svc not in PROVIDER_TYPES:
                    svc = "other"
                task_map[t["case_id"]][svc].append(t)

            result = []
            for c in cases:
                cid = c["id"]
                name_parts = [
                    c.get("employee_first_name") or "",
                    c.get("employee_last_name") or "",
                ]
                display_name = " ".join(p for p in name_parts if p).strip() or c.get("employee_identifier") or cid
                cells = {svc: _cell_status(task_map[cid][svc]) for svc in PROVIDER_TYPES}
                result.append({
                    "case_id": cid,
                    "employee_name": display_name,
                    "employee_identifier": c.get("employee_identifier") or "",
                    "dest_country": c.get("dest_country") or None,
                    "move_date": str(c["expected_start_date"]) if c.get("expected_start_date") else None,
                    "coordination_status": c.get("coordination_status") or "not-started",
                    "cells": cells,
                })
            return result

        except Exception as e:
            log.warning("get_provider_status_grid: %s", e)
            return []
