"""
AIQ-797 (P1-08d-FU) — unit tests for the rule-change notifier's REAL logic.

The existing TestNotifierTrigger in test_roadmap_audit.py mocks
`notify_superseded_rules`, so its SQL (`_AFFECTED_SQL`), idempotency
(`_already_notified`), and `since`-window behaviour have no coverage — a
regression there passes CI silently. This drives the actual function.

Harness: the notifier runs raw Postgres SQL against the `rce.*` + `public.*`
schemas via `backend.database.db`. We point `db.engine` at an in-memory SQLite
db (StaticPool so the schema persists across the notifier's repeated
`engine.connect()` calls), ATTACH `rce`/`public` schema namespaces, and rewrite
the three Postgres-only constructs at the cursor boundary so the same query
text runs on SQLite:
  - `= ANY(:open_statuses)`  -> `IN (:_st0, :_st1, ...)` (params expanded)
  - `col->>'key'`            -> `json_extract(col, '$.key')`
  - (schema-qualified names + CURRENT_DATE are native to SQLite)
`db.get_relocation_case` / `db.create_notification_with_preferences` are
db-method seams (no raw SQL), so they're stubbed: the create stub writes into
the same SQLite `public.notifications` table the real `_already_notified`
reads, so idempotency is exercised end-to-end.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest import mock

from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import rule_change_notifier as notifier  # noqa: E402

_NOW = datetime(2026, 6, 8, 12, 0, 0)

_SCHEMA = """
CREATE TABLE rce.rule_versions (
  rule_version_id TEXT PRIMARY KEY,
  rule_id TEXT,
  version_label TEXT,
  superseded_by TEXT,
  effective_to TEXT,
  updated_at TEXT
);
CREATE TABLE rce.roadmap_audit_log (
  case_id TEXT,
  rule_version_id TEXT
);
CREATE TABLE rce.cases (
  case_id TEXT PRIMARY KEY,
  status TEXT
);
CREATE TABLE public.notifications (
  case_id TEXT,
  type TEXT,
  metadata TEXT
);
"""

# col->>'key'  ->  json_extract(col, '$.key')   (operates on statement text only)
_ARROW_RE = re.compile(r"(\w+)->>'(\w+)'")
# `= ANY(?)` after SQLAlchemy has compiled named params to positional `?`.
_ANY_RE = re.compile(r"=\s*ANY\(\?\)")


def _rewrite(statement: str, parameters: Any) -> tuple[str, Any]:
    statement = _ARROW_RE.sub(r"json_extract(\1, '$.\2')", statement)
    m = _ANY_RE.search(statement)
    if m and isinstance(parameters, (tuple, list)):
        # The ANY's `?` is the Nth positional placeholder, where N = number of
        # `?` before it. That param is the status list; expand it into IN (?,?,…).
        idx = statement[: m.start()].count("?")
        params = list(parameters)
        list_val = params[idx]
        seq = list(list_val) if isinstance(list_val, (list, tuple)) else [list_val]
        placeholders = ", ".join(["?"] * len(seq))
        statement = statement[: m.start()] + f"IN ({placeholders})" + statement[m.end():]
        parameters = tuple(params[:idx] + seq + params[idx + 1:])
    return statement, parameters


class RuleChangeNotifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def _attach_and_create(dbapi_conn, _rec):
            cur = dbapi_conn.cursor()
            cur.execute("ATTACH ':memory:' AS rce")
            cur.execute("ATTACH ':memory:' AS public")
            for stmt in _SCHEMA.split(";"):
                if stmt.strip():
                    cur.execute(stmt)
            cur.close()

        @event.listens_for(self.engine, "before_cursor_execute", retval=True)
        def _pg_to_sqlite(conn, cursor, statement, parameters, context, executemany):
            if executemany:
                return statement, parameters
            return _rewrite(statement, parameters)

        # Touch a connection so the schema exists before any patch reads it.
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # Recipients per case (the get_relocation_case seam).
        self._recipients: Dict[str, Dict[str, Any]] = {}

        self.engine_patch = mock.patch.object(notifier.db, "engine", self.engine)
        self.engine_patch.start()
        self.addCleanup(self.engine_patch.stop)

        self.case_patch = mock.patch.object(
            notifier.db,
            "get_relocation_case",
            side_effect=lambda cid: self._recipients.get(cid),
        )
        self.case_patch.start()
        self.addCleanup(self.case_patch.stop)

        # create_notification stub writes into the SAME notifications table the
        # real _already_notified reads, so idempotency is genuinely exercised.
        def _create(**kw):
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO public.notifications (case_id, type, metadata) "
                        "VALUES (:cid, :type, :meta)"
                    ),
                    {
                        "cid": kw["case_id"],
                        "type": kw["type_"],
                        "meta": json.dumps(kw["metadata"]),
                    },
                )

        self.create_mock = mock.Mock(side_effect=_create)
        self.create_patch = mock.patch.object(
            notifier.db, "create_notification_with_preferences", self.create_mock
        )
        self.create_patch.start()
        self.addCleanup(self.create_patch.stop)

    # -- seed helpers ---------------------------------------------------------
    def _add_version(self, vid, rule_id, *, superseded_by=None, effective_to=None, updated_at):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO rce.rule_versions "
                    "(rule_version_id, rule_id, version_label, superseded_by, effective_to, updated_at) "
                    "VALUES (:id, :rid, '1.0', :sb, :et, :ua)"
                ),
                {"id": vid, "rid": rule_id, "sb": superseded_by,
                 "et": effective_to.isoformat() if effective_to else None,
                 "ua": updated_at.isoformat(sep=" ")},
            )

    def _add_case(self, case_id, status, *, cites=None, hr=None, employee=None):
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO rce.cases (case_id, status) VALUES (:c, :s)"),
                         {"c": case_id, "s": status})
            if cites:
                conn.execute(
                    text("INSERT INTO rce.roadmap_audit_log (case_id, rule_version_id) VALUES (:c, :v)"),
                    {"c": case_id, "v": cites},
                )
        if hr or employee:
            self._recipients[case_id] = {"hr_user_id": hr, "employee_id": employee}

    def _notif_count(self) -> int:
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT count(*) FROM public.notifications")).scalar() or 0

    # -- tests ----------------------------------------------------------------
    def test_affected_case_notified_others_not(self) -> None:
        # caseA cites rv1 which is superseded (superseded_by) recently -> notify both recipients.
        self._add_version("rv1", "R1", superseded_by="rv2", updated_at=_NOW)
        self._add_version("rv2", "R1", updated_at=_NOW)  # the new (current) version
        self._add_case("caseA", "ACTIVE", cites="rv1", hr="hrA", employee="empA")
        # caseC cites a NON-superseded version -> not affected.
        self._add_case("caseC", "ACTIVE", cites="rv2", hr="hrC")
        # caseClosed cites the superseded rv1 but is CLOSED -> excluded by status.
        self._add_case("caseClosed", "CLOSED", cites="rv1", hr="hrX")

        result = notifier.notify_superseded_rules(since=_NOW - timedelta(hours=24))

        self.assertEqual(result["affected_pairs"], 1)  # only caseA/rv1
        self.assertEqual(result["notifications_created"], 2)  # hrA + empA
        self.assertEqual(self._notif_count(), 2)
        # Each notification carries the prior version + case.
        self.create_mock.assert_called()
        meta = self.create_mock.call_args_list[0].kwargs["metadata"]
        self.assertEqual(meta["old_rule_version_id"], "rv1")
        self.assertEqual(meta["case_id"], "caseA")

    def test_effective_to_in_past_is_superseded(self) -> None:
        # rv5 has no superseded_by but effective_to in the past -> treated as superseded.
        self._add_version("rv5", "R5", effective_to=datetime(2026, 6, 1), updated_at=_NOW)
        self._add_case("caseD", "ACTIVE", cites="rv5", hr="hrD")

        result = notifier.notify_superseded_rules(since=_NOW - timedelta(hours=24))
        self.assertEqual(result["affected_pairs"], 1)
        self.assertEqual(result["notifications_created"], 1)

    def test_idempotent_on_rerun(self) -> None:
        self._add_version("rv1", "R1", superseded_by="rv2", updated_at=_NOW)
        self._add_case("caseA", "ACTIVE", cites="rv1", hr="hrA", employee="empA")

        first = notifier.notify_superseded_rules(since=_NOW - timedelta(hours=24))
        self.assertEqual(first["notifications_created"], 2)

        second = notifier.notify_superseded_rules(since=_NOW - timedelta(hours=24))
        self.assertEqual(second["affected_pairs"], 1)
        self.assertEqual(second["notifications_created"], 0)
        self.assertEqual(second["skipped_idempotent"], 1)
        self.assertEqual(self._notif_count(), 2)  # no duplicates

    def test_since_window_excludes_old_supersession(self) -> None:
        # Supersession recorded 48h ago.
        self._add_version("rv9", "R9", superseded_by="rv10", updated_at=_NOW - timedelta(hours=48))
        self._add_case("caseOld", "ACTIVE", cites="rv9", hr="hrOld")

        # Default-style 24h window: excluded.
        recent = notifier.notify_superseded_rules(since=_NOW - timedelta(hours=24))
        self.assertEqual(recent["affected_pairs"], 0)
        self.assertEqual(recent["notifications_created"], 0)

        # Widen the window to 72h: now included.
        wide = notifier.notify_superseded_rules(since=_NOW - timedelta(hours=72))
        self.assertEqual(wide["affected_pairs"], 1)
        self.assertEqual(wide["notifications_created"], 1)

    def test_no_recipient_is_counted_not_notified(self) -> None:
        self._add_version("rv1", "R1", superseded_by="rv2", updated_at=_NOW)
        self._add_case("caseNoRecip", "ACTIVE", cites="rv1")  # no hr/employee seeded

        result = notifier.notify_superseded_rules(since=_NOW - timedelta(hours=24))
        self.assertEqual(result["affected_pairs"], 1)
        self.assertEqual(result["notifications_created"], 0)
        self.assertEqual(result["skipped_no_recipient"], 1)


if __name__ == "__main__":
    unittest.main()
