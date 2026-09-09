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

from sqlalchemy import bindparam, text

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

    def insert_recommendation_slate(
        self,
        *,
        category: str,
        criteria: Dict[str, Any],
        items: List[Dict[str, Any]],
        segment: Optional[str] = None,
        case_id: Optional[str] = None,
        assignment_id: Optional[str] = None,
        company_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """[P2] Persist one recommendation candidate slate. Best-effort: never
        raises (table may not exist pre-migration), mirroring
        insert_analytics_event. ``criteria``/``items`` are stored as JSON."""
        slate_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        try:
            with self.engine.begin() as conn:
                self._exec(
                    conn,
                    """
                    INSERT INTO recommendation_slates
                        (id, case_id, assignment_id, company_id, category, segment,
                         criteria_json, items_json, created_at)
                    VALUES
                        (:id, :case_id, :assignment_id, :company_id, :category, :segment,
                         :criteria_json, :items_json, :created_at)
                    """,
                    {
                        "id": slate_id,
                        "case_id": case_id,
                        "assignment_id": assignment_id,
                        "company_id": company_id,
                        "category": category,
                        "segment": segment,
                        "criteria_json": json.dumps(criteria or {}),
                        "items_json": json.dumps(items or []),
                        "created_at": now,
                    },
                    op_name="insert_recommendation_slate",
                    request_id=request_id,
                )
        except Exception as e:
            log.debug("insert_recommendation_slate failed (table may not exist): %s", e)

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

    def count_assistant_events_by_topic(
        self, since: Optional[str] = None, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Count policy-assistant events grouped by canonical topic + event_name (AIQ-1438).

        The assistant telemetry never stores raw question text (PII-by-design) — only a
        coarse ``payload_json.extra.canonical_topic`` enum — so "top questions" is served
        at topic granularity. Returns rows ``[{topic, event_name, cnt}]`` (topic may be
        None when an event carries no canonical_topic). Degrades to ``[]`` on any error.
        """
        try:
            # Dialect-aware JSON extraction. payload_json is a TEXT column even on
            # Postgres (events are stored as json.dumps strings), so PG needs a ::jsonb
            # cast before the -> / ->> operators; SQLite reads TEXT via json_extract.
            if self.engine.dialect.name == "postgresql":
                topic_expr = "payload_json::jsonb -> 'extra' ->> 'canonical_topic'"
            else:
                topic_expr = "json_extract(payload_json, '$.extra.canonical_topic')"
            sql = (
                f"SELECT {topic_expr} AS topic, event_name, COUNT(*) as cnt "
                "FROM analytics_events "
                "WHERE event_name IN ("
                "'assistant_question_asked','assistant_question_supported',"
                "'assistant_question_unsupported','assistant_refusal_shown')"
            )
            params: Dict[str, Any] = {}
            if since:
                sql += " AND created_at >= :since"
                params["since"] = since
            sql += f" GROUP BY {topic_expr}, event_name"
            with self.engine.connect() as conn:
                rows = self._exec(
                    conn, sql, params, op_name="count_assistant_events_by_topic", request_id=request_id
                ).fetchall()
            return [{"topic": r[0], "event_name": r[1], "cnt": r[2]} for r in rows]
        except Exception as e:
            log.debug("count_assistant_events_by_topic failed: %s", e)
            return []

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

    def get_latest_compliance_reports_by_assignment_ids(
        self, assignment_ids: Optional[List[str]]
    ) -> Dict[str, Dict[str, Any]]:
        """Latest compliance_reports.report_json per assignment_id (one SELECT).

        Same pick as :meth:`get_latest_compliance_report` (ORDER BY created_at DESC).
        Used by GET /api/hr/assignments so the list does not N+1 the reports table.
        """
        ids: List[str] = []
        seen: set[str] = set()
        for raw in assignment_ids or []:
            if raw is None:
                continue
            aid = str(raw).strip()
            if not aid or aid in seen:
                continue
            seen.add(aid)
            ids.append(aid)
        if not ids:
            return {}

        ranked = text(
            """
            SELECT assignment_id, report_json FROM (
              SELECT
                assignment_id,
                report_json,
                ROW_NUMBER() OVER (
                  PARTITION BY assignment_id
                  ORDER BY created_at DESC
                ) AS rn
              FROM compliance_reports
              WHERE assignment_id IN :aids
            ) ranked
            WHERE rn = 1
            """
        ).bindparams(bindparam("aids", expanding=True))

        with self.engine.connect() as conn:
            rows = conn.execute(ranked, {"aids": ids}).fetchall()

        out: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            m = row._mapping
            aid = m.get("assignment_id")
            if not aid:
                continue
            raw = m.get("report_json")
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else (raw or None)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                out[str(aid)] = parsed
        return out

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

    # ------------------------------------------------------------------
    # [NAV-HR-3-FU / AIQ-1137] Case audit-trail aggregation + amend/reverse.
    #
    # A case is represented by several bridged ids (the assignment id the UI
    # passes, the relocation_cases uuid most legacy audit rows are keyed by, and
    # the mobility_cases uuid). The read-only #820 endpoint only matched the
    # single id it was given, so it missed every event keyed by a sibling id.
    # These helpers resolve the full id set, query audit_logs across all of them
    # with optional filters, and support append-only amend/reverse annotations.
    # Postgres-only SQL (casts + jsonb operators); the router mocks these in tests.
    # ------------------------------------------------------------------

    def resolve_case_audit_entity_ids(self, case_id: str) -> List[str]:
        """All audit entity-ids that represent this case.

        Accepts either the assignment id (what the case-detail UI passes) or a
        relocation_cases uuid, and returns the deduped set of related ids:
        the input, the assignment's case_id / canonical_case_id (relocation
        uuids), any assignment ids that point back to a relocation uuid, and the
        bridged mobility_cases id. Returns at least ``[case_id]``.
        """
        cid = (case_id or "").strip()
        if not cid:
            return []
        sql = """
            SELECT DISTINCT eid FROM (
                SELECT CAST(:cid AS TEXT) AS eid
                UNION SELECT ca.case_id FROM case_assignments ca
                    WHERE ca.id = :cid AND ca.case_id IS NOT NULL
                UNION SELECT ca.canonical_case_id FROM case_assignments ca
                    WHERE ca.id = :cid AND ca.canonical_case_id IS NOT NULL
                UNION SELECT ca.id FROM case_assignments ca
                    WHERE ca.case_id = :cid OR ca.canonical_case_id = :cid
                UNION SELECT aml.mobility_case_id::text FROM assignment_mobility_links aml
                    WHERE aml.assignment_id = :cid
                UNION SELECT aml.mobility_case_id::text FROM assignment_mobility_links aml
                    JOIN case_assignments ca ON ca.id = aml.assignment_id
                    WHERE ca.case_id = :cid OR ca.canonical_case_id = :cid
            ) s WHERE eid IS NOT NULL
        """
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text(sql), {"cid": cid}).fetchall()
            ids = {str(r[0]).strip() for r in rows if r[0] is not None}
            ids.add(cid)
            return sorted(ids)
        except Exception as e:
            log.debug("resolve_case_audit_entity_ids failed: %s", e)
            return [cid]

    def get_case_company_for_audit(self, case_id: str) -> Optional[str]:
        """Company id owning this case, resolved from an assignment id OR a
        relocation uuid. Used to tenant-gate the audit trail (404 on mismatch).
        Returns None when ownership can't be proven (caller treats as 404).
        """
        cid = (case_id or "").strip()
        if not cid:
            return None
        sql = """
            SELECT rc.company_id AS company_id
            FROM relocation_cases rc
            WHERE rc.id::text = :cid
               OR rc.id::text IN (
                    SELECT ca.case_id FROM case_assignments ca WHERE ca.id = :cid
                    UNION
                    SELECT ca.canonical_case_id FROM case_assignments ca WHERE ca.id = :cid
               )
            LIMIT 1
        """
        try:
            with self.engine.connect() as conn:
                row = conn.execute(text(sql), {"cid": cid}).mappings().first()
            return row["company_id"] if row and row.get("company_id") else None
        except Exception as e:
            log.debug("get_case_company_for_audit failed: %s", e)
            return None

    def query_case_audit_trail(
        self,
        entity_ids: List[str],
        *,
        action_type: Optional[str] = None,
        event: Optional[str] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Filtered, newest-first audit_logs rows across all of a case's ids.

        Parses old/new value json and derives the semantic ``event``. Filters are
        each null-guarded so an omitted filter is a no-op.
        """
        ids = [str(e).strip() for e in (entity_ids or []) if e]
        if not ids:
            return []
        sql = """
            SELECT
                al.id::text          AS id,
                al.entity_type       AS entity_type,
                al.entity_id::text   AS entity_id,
                al.action_type       AS action_type,
                al.actor_type        AS actor_type,
                al.actor_id::text    AS actor_id,
                al.old_value_json    AS old_value,
                al.new_value_json    AS new_value,
                al.created_at        AS created_at,
                ap.full_name         AS actor_name
            FROM audit_logs al
            LEFT JOIN profiles ap ON ap.id = al.actor_id
            WHERE al.entity_id::text = ANY(:ids)
              AND (:action_type IS NULL OR al.action_type = :action_type)
              AND (:event IS NULL OR al.new_value_json->>'event' = :event)
              AND (:from_ts IS NULL OR al.created_at >= CAST(:from_ts AS timestamptz))
              AND (:to_ts IS NULL OR al.created_at <= CAST(:to_ts AS timestamptz))
            ORDER BY al.created_at DESC, al.id DESC
            LIMIT :limit
        """
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(sql),
                {
                    "ids": ids,
                    "action_type": action_type,
                    "event": event,
                    "from_ts": from_ts,
                    "to_ts": to_ts,
                    "limit": limit,
                },
            ).mappings().all()
        return [self._shape_audit_row(dict(r)) for r in rows]

    def get_audit_log_entry(self, audit_id: str) -> Optional[Dict[str, Any]]:
        """One audit_logs row by id (for amend/reverse target validation)."""
        aid = (audit_id or "").strip()
        if not aid:
            return None
        sql = """
            SELECT
                al.id::text          AS id,
                al.entity_type       AS entity_type,
                al.entity_id::text   AS entity_id,
                al.action_type       AS action_type,
                al.old_value_json    AS old_value,
                al.new_value_json    AS new_value,
                al.created_at        AS created_at
            FROM audit_logs al
            WHERE al.id::text = :aid
            LIMIT 1
        """
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), {"aid": aid}).mappings().first()
        return self._shape_audit_row(dict(row)) if row else None

    def find_audit_amendments(self, original_id: str) -> List[Dict[str, Any]]:
        """Audit rows that amend or reverse ``original_id`` (to block double-reverse)."""
        oid = (original_id or "").strip()
        if not oid:
            return []
        sql = """
            SELECT al.id::text AS id,
                   al.new_value_json->>'event'    AS event,
                   al.new_value_json->>'amends'    AS amends,
                   al.new_value_json->>'reverses'  AS reverses
            FROM audit_logs al
            WHERE al.new_value_json->>'amends' = :oid
               OR al.new_value_json->>'reverses' = :oid
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"oid": oid}).mappings().all()
        return [dict(r) for r in rows]

    def insert_case_audit_annotation(
        self,
        *,
        entity_type: Optional[str],
        entity_id: str,
        event: str,
        reason: Optional[str],
        link_field: str,
        original_id: str,
        actor_id: Optional[str] = None,
    ) -> str:
        """Write an append-only amend/reverse annotation to audit_logs and return
        its new id. ``link_field`` is 'amends' or 'reverses'; the original row is
        never mutated. Raises on failure — the write IS the operation here, so it
        must not be swallowed like ``log_audit``.
        """
        from ..app.services.audit_log_service import (
            insert_audit_log,
            ACTION_UPDATE,
            ACTOR_HUMAN,
        )

        new_value: Dict[str, Any] = {"event": event, link_field: original_id}
        if reason:
            new_value["reason"] = reason
        with self.engine.begin() as conn:
            return insert_audit_log(
                conn,
                entity_type=entity_type or "assignment",
                entity_id=entity_id,
                action_type=ACTION_UPDATE,
                new_value=new_value,
                actor_type=ACTOR_HUMAN,
                actor_id=actor_id,
            )

    @staticmethod
    def _shape_audit_row(d: Dict[str, Any]) -> Dict[str, Any]:
        """Parse old/new json, derive ``event``, stringify created_at."""
        for k in ("old_value", "new_value"):
            v = d.get(k)
            if isinstance(v, str):
                try:
                    d[k] = json.loads(v) if v else None
                except Exception:
                    d[k] = None
        nv = d.get("new_value")
        d["event"] = nv.get("event") if isinstance(nv, dict) else None
        if d.get("created_at") is not None:
            d["created_at"] = str(d["created_at"])
        return d

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
