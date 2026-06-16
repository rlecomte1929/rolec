"""[AUDIT-C1.6a] Audit-domain DB methods, extracted from backend/database.py.

These were methods on the monolithic ``Database`` class; they live here as a
mixin (:class:`AuditMixin`) that ``Database`` inherits, so every caller keeps
working unchanged via normal MRO. Pure relocation; ``..database`` module
helpers are imported lazily in-method to avoid an import cycle.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import logging
import uuid

from sqlalchemy import text

from ..db_config import DATABASE_URL as _raw_url

log = logging.getLogger(__name__)

_is_sqlite = _raw_url.startswith("sqlite")

# [AUDIT-2/AIQ-1126] log_audit consolidation — decision: Option C.
# Drain the legacy ``audit_log`` table by routing each event to its canonical home:
#   * READ / pure-access events  -> ``data_access_log`` (the GDPR PII-access log),
#   * true mutations             -> canonical ``audit_logs`` via insert_audit_log,
#     mapped onto the insert/update/delete CHECK with the semantic verb preserved
#     in ``new_value.event`` (the convention AIQ-932/942 already established).
_ACCESS_ACTIONS = frozenset({"READ", "VIEW", "LIST", "EXPORT", "DOWNLOAD", "ACCESS"})
_CREATE_ACTIONS = frozenset({"CREATE", "INSERT"})
_DELETE_ACTIONS = frozenset({"DELETE", "DESTROY", "PURGE"})
# target_type values that map onto data_access_log's case_id / profile_id columns.
_CASE_TARGETS = frozenset({"case", "assignment", "case_assignment"})
_PROFILE_TARGETS = frozenset({"person", "profile", "employee", "user"})


class AuditMixin:
    """Audit-domain methods mixed into :class:`backend.database.Database`."""

    def insert_analytics_event(
        self, event_name: str, payload: Dict[str, Any], request_id: Optional[str] = None
    ) -> None:
        """Insert an analytics event. Table may not exist in Postgres (use migration)."""
        event_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        payload_json = json.dumps(payload)
        try:
            with self.engine.begin() as conn:
                self._exec(
                    conn,
                    """
                    INSERT INTO analytics_events (id, event_name, payload_json, created_at)
                    VALUES (:id, :event_name, :payload_json, :created_at)
                    """,
                    {
                        "id": event_id,
                        "event_name": event_name,
                        "payload_json": payload_json,
                        "created_at": now,
                    },
                    op_name="insert_analytics_event",
                    request_id=request_id,
                )
        except Exception as e:
            log.debug("insert_analytics_event failed (table may not exist): %s", e)

    def list_analytics_events(
        self,
        event_name: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 1000,
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List analytics events for reporting. Requires analytics_events table."""
        try:
            sql = "SELECT id, event_name, payload_json, created_at FROM analytics_events WHERE 1=1"
            params: Dict[str, Any] = {}
            if event_name:
                sql += " AND event_name = :event_name"
                params["event_name"] = event_name
            if since:
                sql += " AND created_at >= :since"
                params["since"] = since
            sql += " ORDER BY created_at DESC LIMIT :limit"
            params["limit"] = limit
            with self.engine.connect() as conn:
                rows = self._exec(
                    conn, sql, params, op_name="list_analytics_events", request_id=request_id
                ).fetchall()
            out = []
            for r in rows:
                d = self._row_to_dict(r)
                if d and "payload_json" in d:
                    raw = d["payload_json"]
                    if isinstance(raw, dict):
                        d["payload"] = raw
                    else:
                        try:
                            d["payload"] = json.loads(raw or "{}")
                        except Exception:
                            d["payload"] = {}
                    del d["payload_json"]
                out.append(d)
            return out
        except Exception as e:
            log.debug("list_analytics_events failed: %s", e)
            return []

    def count_analytics_events_by_name(
        self, since: Optional[str] = None, request_id: Optional[str] = None
    ) -> Dict[str, int]:
        """Count events by event_name for admin analytics. Returns {event_name: count}."""
        try:
            sql = "SELECT event_name, COUNT(*) as cnt FROM analytics_events WHERE 1=1"
            params: Dict[str, Any] = {}
            if since:
                sql += " AND created_at >= :since"
                params["since"] = since
            sql += " GROUP BY event_name"
            with self.engine.connect() as conn:
                rows = self._exec(
                    conn, sql, params, op_name="count_analytics_events", request_id=request_id
                ).fetchall()
            return {r[0]: r[1] for r in rows}
        except Exception as e:
            log.debug("count_analytics_events_by_name failed: %s", e)
            return {}

    def list_trace_events(self, case_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM relocation_trace_events WHERE (canonical_case_id = :cid OR case_id = :cid) "
                "ORDER BY created_at DESC LIMIT :lim"
            ), {"cid": cid, "lim": limit}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["input"] = self._json_load(item.get("input_json")) or {}
            item["output"] = self._json_load(item.get("output_json")) or {}
        return items

    def insert_trace_event(
        self,
        trace_id: str,
        case_id: str,
        step_name: str,
        input_payload: Dict[str, Any],
        output_payload: Dict[str, Any],
        status: str,
        error: Optional[str],
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO relocation_trace_events "
                "(id, trace_id, case_id, step_name, input_json, output_json, status, error, created_at) "
                "VALUES (:id, :trace_id, :case_id, :step_name, :input_json, :output_json, :status, :error, :created_at)"
            ), {
                "id": str(uuid.uuid4()),
                "trace_id": trace_id,
                "case_id": case_id,
                "step_name": step_name,
                "input_json": json.dumps(input_payload),
                "output_json": json.dumps(output_payload),
                "status": status,
                "error": error,
                "created_at": now,
            })

    def save_compliance_report(self, report_id: str, assignment_id: str, report: Dict[str, Any]) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO compliance_reports (id, assignment_id, report_json, created_at) "
                "VALUES (:id, :aid, :rj, :ca)"
            ), {"id": report_id, "aid": assignment_id, "rj": json.dumps(report), "ca": datetime.utcnow().isoformat()})

    def get_latest_compliance_report(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT report_json FROM compliance_reports "
                "WHERE assignment_id = :aid ORDER BY created_at DESC LIMIT 1"
            ), {"aid": assignment_id}).fetchone()
        return json.loads(row._mapping["report_json"]) if row else None

    def save_compliance_run(self, run_id: str, assignment_id: str, report: Dict[str, Any]) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO compliance_runs (id, assignment_id, report_json, created_at) "
                "VALUES (:id, :aid, :rj, :ca)"
            ), {"id": run_id, "aid": assignment_id, "rj": json.dumps(report), "ca": datetime.utcnow().isoformat()})

    def get_latest_compliance_run(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT report_json, created_at FROM compliance_runs "
                "WHERE assignment_id = :aid ORDER BY created_at DESC LIMIT 1"
            ), {"aid": assignment_id}).fetchone()
        if not row:
            return None
        report = json.loads(row._mapping["report_json"])
        report["lastVerified"] = row._mapping["created_at"]
        return report

    def create_compliance_action(
        self,
        action_id: str,
        assignment_id: str,
        check_id: str,
        action_type: str,
        notes: Optional[str],
        actor_user_id: str,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO compliance_actions "
                "(id, assignment_id, check_id, action_type, notes, actor_user_id, created_at) "
                "VALUES (:id, :aid, :chk, :atype, :notes, :actor, :ca)"
            ), {
                "id": action_id, "aid": assignment_id, "chk": check_id,
                "atype": action_type, "notes": notes, "actor": actor_user_id,
                "ca": datetime.utcnow().isoformat(),
            })

    def list_compliance_actions(self, assignment_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM compliance_actions WHERE assignment_id = :aid ORDER BY created_at DESC"
            ), {"aid": assignment_id}).fetchall()
        return self._rows_to_list(rows)

    def log_audit(
        self,
        actor_user_id: str,
        action_type: str,
        target_type: str,
        target_id: Optional[str],
        reason: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append-only audit. Never raises: failures are logged and ignored so callers are not broken.

        [AUDIT-2/AIQ-1126] Consolidated off the legacy ``audit_log`` table (decision:
        Option C). READ/access events are routed to ``data_access_log``; every other
        (mutation) event lands in the canonical ``audit_logs`` via ``insert_audit_log``,
        with the original verb preserved in ``new_value.event``. Callers are unchanged.
        """
        verb = (action_type or "").strip().upper()
        try:
            with self.engine.begin() as conn:
                if verb in _ACCESS_ACTIONS:
                    self._log_data_access(conn, actor_user_id, verb, target_type, target_id, reason)
                else:
                    self._log_mutation(conn, actor_user_id, verb, target_type, target_id, reason, metadata)
        except Exception as e:
            log.warning("log_audit failed (non-fatal): %s", e)

    def _log_mutation(
        self,
        conn: Any,
        actor_user_id: str,
        verb: str,
        target_type: str,
        target_id: Optional[str],
        reason: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        """Write a mutation event to the canonical audit_logs (semantic verb in new_value.event)."""
        # Lazy import (matches this module's convention) — no cycle: audit_log_service
        # imports only stdlib + sqlalchemy.
        from ..app.services.audit_log_service import (
            insert_audit_log,
            ACTION_INSERT,
            ACTION_UPDATE,
            ACTION_DELETE,
            ACTOR_HUMAN,
        )

        if verb in _CREATE_ACTIONS:
            mapped = ACTION_INSERT
        elif verb in _DELETE_ACTIONS:
            mapped = ACTION_DELETE
        else:
            mapped = ACTION_UPDATE

        new_value: Dict[str, Any] = {"event": verb}
        if reason:
            new_value["reason"] = reason
        if metadata:
            new_value.update(metadata)

        insert_audit_log(
            conn,
            entity_type=target_type or "unknown",
            entity_id=str(target_id) if target_id is not None else "",
            action_type=mapped,
            new_value=new_value,
            actor_type=ACTOR_HUMAN,
            actor_id=actor_user_id,
        )

    def _log_data_access(
        self,
        conn: Any,
        actor_user_id: str,
        verb: str,
        target_type: str,
        target_id: Optional[str],
        reason: Optional[str],
    ) -> None:
        """Write a READ/access event to data_access_log (the GDPR PII-access trail)."""
        tt = (target_type or "").strip().lower()
        case_id = target_id if tt in _CASE_TARGETS else None
        profile_id = target_id if tt in _PROFILE_TARGETS else None
        # fields_accessed is text[] on Postgres (psycopg2 adapts a Python list);
        # SQLite (tests) has no array type, so store the JSON form there.
        fields_list = [target_type] if target_type else None
        is_pg = getattr(conn, "dialect", None) is not None and conn.dialect.name == "postgresql"
        fields_param = fields_list if (is_pg or fields_list is None) else json.dumps(fields_list)
        conn.execute(
            text(
                """
                INSERT INTO data_access_log
                    (case_id, profile_id, accessed_by_user_id, accessed_by_role,
                     action, fields_accessed, purpose, accessed_at)
                VALUES
                    (:case_id, :profile_id, :user_id, :role,
                     :action, :fields, :purpose, :accessed_at)
                """
            ),
            {
                "case_id": case_id,
                "profile_id": profile_id,
                "user_id": actor_user_id,
                "role": "admin",
                "action": verb,
                "fields": fields_param,
                "purpose": reason or "admin_audit",
                "accessed_at": datetime.utcnow().isoformat(),
            },
        )

    @staticmethod
    def log_expected_tables_status() -> None:
        """
        Log which expected production tables exist. Use at startup to verify
        migrations have been applied. Expected tables from Supabase migrations.
        """
        from ..database import _engine  # lazy: avoid import cycle
        expected = [
            "rfqs", "rfq_items", "rfq_recipients", "quotes", "quote_lines",
            "case_milestones", "analytics_events", "suppliers",
            "supplier_service_capabilities", "supplier_scoring_metadata",
            "company_preferred_suppliers",
            "policy_documents",
            "policy_document_clauses",
        ]
        if _is_sqlite:
            try:
                with _engine.connect() as conn:
                    present = []
                    missing = []
                    for t in expected:
                        r = conn.execute(text(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name=:n"
                        ), {"n": t}).fetchone()
                        (present if r else missing).append(t)
                    log.info(
                        "db_tables: present=%s missing=%s (sqlite)",
                        present, missing,
                    )
            except Exception as e:
                log.warning("db_tables check failed: %s", e)
            return
        try:
            with _engine.connect() as conn:
                placeholders = ",".join([f":t{i}" for i in range(len(expected))])
                params = {f"t{i}": t for i, t in enumerate(expected)}
                rows = conn.execute(text(f"""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name IN ({placeholders})
                """), params).fetchall()
                found = {r[0] for r in rows}
                present = [t for t in expected if t in found]
                missing = [t for t in expected if t not in found]
                log.info(
                    "db_tables: present=%s missing=%s (postgres). Apply migrations if missing.",
                    present, missing,
                )
                if missing:
                    log.warning(
                        "db_tables: Run supabase migrations for: %s. See docs/SUPABASE_MIGRATIONS.md",
                        missing,
                    )
        except Exception as e:
            log.warning("db_tables check failed: %s", e)
