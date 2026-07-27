"""AIQ-1694·5 — end-to-end: produce → masked 'produced' row → read the linked triplet.

Mirrors test_ai_decisions_router.py's sqlite harness (in-memory ai_decisions + a
before_cursor_execute listener that strips the Postgres-only CAST(... AS jsonb|uuid)),
extended with the AIQ-1694 columns. Proves the audit trail is queryable end-to-end:
the production-time write helper (record_ai_recommendation) and the read view
(list_ai_decisions) share `backend.database.db`, so one patched engine exercises both.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine, event, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import ai_decisions as router_module  # noqa: E402
from backend.app.routers.ai_decisions import AIDecisionRead, list_ai_decisions  # noqa: E402
from backend.app.services.ai_decision_logger import record_ai_recommendation  # noqa: E402

# ai_decisions with the AIQ-1694 columns + the widened 'produced' decision state.
SCHEMA = """
CREATE TABLE ai_decisions (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  actor_id TEXT,
  company_id TEXT,
  feature TEXT NOT NULL,
  recommendation_id TEXT NOT NULL,
  ai_output TEXT NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('accept','override','reject','produced')),
  reason TEXT,
  outcome TEXT,
  input_context TEXT,
  model_name TEXT,
  produced_at TEXT
);
"""

_PG_CAST_RE = re.compile(r"CAST\s*\(\s*(\?|\:\w+)\s+AS\s+(?:jsonb|uuid)\s*\)", re.IGNORECASE)

PII = ["+33612345678", "jean.dupont@acme.com"]


def _hr(company: str) -> dict:
    return {"id": str(uuid.uuid4()), "role": "HR", "company": company, "is_admin": False}


class AiDecisionAuditE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )

        @event.listens_for(self.engine, "before_cursor_execute", retval=True)
        def _strip_pg_casts(conn, cursor, statement, parameters, context, executemany):
            return _PG_CAST_RE.sub(r"\1", statement), parameters

        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))

        # list_ai_decisions uses the import-bound `router_module.db`; record_ai_recommendation
        # reads `backend.database.db` FRESH at call time. Normally the same object, but in a
        # full-suite run another test may rebind backend.database.db — so patch the engine on
        # BOTH views to our sqlite engine, independently.
        import backend.database as _bdb  # noqa: E402
        patchers = [
            mock.patch.object(router_module.db, "engine", self.engine),
            mock.patch.object(router_module.db, "get_profile_record",
                              side_effect=lambda uid: {"id": uid, "company_id": None}),
            mock.patch.object(router_module.db, "get_hr_company_id", return_value=None),
        ]
        if _bdb.db is not router_module.db:
            patchers.append(mock.patch.object(_bdb.db, "engine", self.engine))
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _produce(self, company: str, rec_id: str = "rec-e2e"):
        return record_ai_recommendation(
            feature="supplier_reco:movers",
            recommendation_id=rec_id,
            input_context={"origin_phone": "+33612345678", "note": "email jean.dupont@acme.com"},
            ai_output={"picks": ["m1", "m2"]},
            company_id=company,
            model_name="rule-based",
        )

    def test_response_model_exposes_the_new_audit_fields(self):
        for field in ("input_context", "model_name", "produced_at"):
            self.assertIn(field, AIDecisionRead.model_fields)

    def test_produce_then_read_returns_the_masked_linked_triplet(self):
        rid = self._produce("company-a")
        self.assertTrue(rid, "helper wrote a produced row")

        view = list_ai_decisions(user=_hr("company-a"), feature=None, decision="produced", limit=100)
        self.assertEqual(len(view), 1)
        row = view[0]

        # the triplet is linked
        self.assertEqual(row["decision"], "produced")
        self.assertEqual(row["model_name"], "rule-based")
        self.assertIsNotNone(row.get("produced_at"))
        ao = row["ai_output"]
        ao = json.loads(ao) if isinstance(ao, str) else ao
        self.assertEqual(ao, {"picks": ["m1", "m2"]})

        # input_context is present AND masked — no raw PII survived the round-trip
        ic = row["input_context"]
        ic_s = ic if isinstance(ic, str) else json.dumps(ic)
        for raw in PII:
            self.assertNotIn(raw, ic_s, f"raw PII exposed in the read view: {raw}")

    def test_read_is_company_scoped(self):
        self._produce("company-a", rec_id="rec-a")
        self._produce("company-b", rec_id="rec-b")

        a_view = list_ai_decisions(user=_hr("company-a"), feature=None, decision="produced", limit=100)
        b_view = list_ai_decisions(user=_hr("company-b"), feature=None, decision="produced", limit=100)
        self.assertEqual({r["company_id"] for r in a_view}, {"company-a"})
        self.assertEqual({r["company_id"] for r in b_view}, {"company-b"})


if __name__ == "__main__":
    unittest.main()
