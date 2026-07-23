"""
[feat/rfq-hr-loop-inbox] GET /api/hr/rfq-requests reads the CANONICAL rfqs model.

Before this, the handler read `rfq_requests` — a table that does not exist in prod, so every
call 500'd. The employee's real RFQs live in `rfqs` / `rfq_recipients` (written by POST /api/rfqs),
and HR had no surface that read them. This repoint gives HR the vendors the employee actually
picked, with live status, scoped to the HR's company via relocation_cases.company_id.

The handler is async; this repo has no pytest-asyncio, so we drive it with a plain asyncio.run()
inside a normal sync test. A sqlite mirror stands in for Postgres — the query uses
CAST(... AS TEXT) rather than the PG-only `::text` so it runs unchanged here. (The end-to-end
chain against real Postgres is verified separately; a mocked/sqlite pass would happily "green" a
schema that does not exist — see the AIQ-1523 uuid/text bug for what that costs.)
"""
from __future__ import annotations

import asyncio
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine, text

from backend.app.routers import hr_rfq as router_module

# Minimal sqlite mirror of the columns the repointed list query touches.
SCHEMA = """
CREATE TABLE relocation_cases (
  id TEXT PRIMARY KEY, company_id TEXT
);
CREATE TABLE rfqs (
  id TEXT PRIMARY KEY, case_id TEXT, rfq_ref TEXT, created_at TEXT,
  created_by_user_id TEXT
);
CREATE TABLE rfq_recipients (
  id TEXT PRIMARY KEY, rfq_id TEXT, vendor_id TEXT, status TEXT,
  quote_submitted_at TEXT, first_viewed_at TEXT
);
CREATE TABLE suppliers (
  id TEXT PRIMARY KEY, name TEXT
);
"""


class HrRfqCanonicalListTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
        self.company_id = str(uuid.uuid4())
        self.other_company = str(uuid.uuid4())
        self.engine_patcher = mock.patch.object(router_module.db, "engine", self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)
        # _require_hr resolves company/tenant; stub it to our company so the list is scoped.
        self.hr_patcher = mock.patch.object(
            router_module, "_require_hr", return_value=(self.company_id, None, None)
        )
        self.hr_patcher.start()
        self.addCleanup(self.hr_patcher.stop)
        self.user = {"id": "seed-hr-testingapril", "role": "HR"}

    def _seed_case(self, company_id: str) -> str:
        case_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO relocation_cases (id, company_id) VALUES (:i, :c)"),
                {"i": case_id, "c": company_id},
            )
        return case_id

    def _seed_rfq(self, case_id: str, recipients: list) -> str:
        rfq_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO rfqs (id, case_id, rfq_ref, created_at) "
                    "VALUES (:i, :c, :r, :t)"
                ),
                {"i": rfq_id, "c": case_id, "r": "RFQ-TEST", "t": "2026-07-22T00:00:00+00:00"},
            )
            for name, submitted in recipients:
                vid = str(uuid.uuid4())
                conn.execute(
                    text("INSERT INTO suppliers (id, name) VALUES (:i, :n)"),
                    {"i": vid, "n": name},
                )
                conn.execute(
                    text(
                        "INSERT INTO rfq_recipients (id, rfq_id, vendor_id, status, quote_submitted_at) "
                        "VALUES (:i, :rf, :v, :s, :q)"
                    ),
                    {
                        "i": str(uuid.uuid4()), "rf": rfq_id, "v": vid,
                        "s": "replied" if submitted else "sent",
                        "q": "2026-07-22T01:00:00+00:00" if submitted else None,
                    },
                )
        return rfq_id

    def test_empty_list_returns_200_shape(self) -> None:
        res = asyncio.run(router_module.list_rfqs(case_id=None, user=self.user))
        self.assertEqual(res, {"rfqs": [], "total": 0})

    def test_lists_the_employee_picked_recipients_with_status(self) -> None:
        case_id = self._seed_case(self.company_id)
        # Six recipients: the schools have no quote yet, one mover replied.
        self._seed_rfq(case_id, [
            ("Oslo International School", False),
            ("The British School of Oslo", False),
            ("Lycée Français René Cassin", False),
            ("Crown Relocations (Norway)", False),
            ("AGS Movers Norway", False),
            ("Déménagements Delahaye", True),
        ])
        res = asyncio.run(router_module.list_rfqs(case_id=case_id, user=self.user))

        self.assertEqual(res["total"], 1)
        rfq = res["rfqs"][0]
        self.assertEqual(rfq["recipient_count"], 6)
        self.assertEqual(rfq["quote_count"], 1)
        self.assertEqual(rfq["status"], "quotes_in")  # at least one reply
        names = {r["supplier_name"] for r in rfq["recipients"]}
        self.assertIn("Crown Relocations (Norway)", names)
        replied = [r for r in rfq["recipients"] if r["has_quote"]]
        self.assertEqual(len(replied), 1)
        self.assertEqual(replied[0]["supplier_name"], "Déménagements Delahaye")

    def test_scoped_to_the_hr_company(self) -> None:
        # An RFQ on ANOTHER company's case must never surface for this HR.
        mine = self._seed_case(self.company_id)
        theirs = self._seed_case(self.other_company)
        self._seed_rfq(mine, [("Crown", False)])
        self._seed_rfq(theirs, [("SIRVA", False)])

        res = asyncio.run(router_module.list_rfqs(case_id=None, user=self.user))
        self.assertEqual(res["total"], 1)
        self.assertEqual(res["rfqs"][0]["case_id"], mine)


if __name__ == "__main__":
    unittest.main()
