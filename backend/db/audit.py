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
        """Append-only audit log. Never raises: failures are logged and ignored so callers are not broken."""
        now = datetime.utcnow().isoformat()
        try:
            with self.engine.begin() as conn:
                conn.execute(text(
                    "INSERT INTO audit_log (id, actor_user_id, action_type, target_type, target_id, reason, metadata_json, created_at) "
                    "VALUES (:id, :actor, :action, :target_type, :target_id, :reason, :meta, :created_at)"
                ), {
                    "id": str(uuid.uuid4()),
                    "actor": actor_user_id,
                    "action": action_type,
                    "target_type": target_type,
                    "target_id": target_id,
                    "reason": reason,
                    "meta": json.dumps(metadata or {}),
                    "created_at": now,
                })
        except Exception as e:
            log.warning("log_audit failed (non-fatal): %s", e)

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
