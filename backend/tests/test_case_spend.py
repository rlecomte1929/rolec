"""[AIQ-2089] Tests for committed per-case / per-company spend derivation.

Pins the four card criteria and the two traps: spend comes only from validated RFQ quotes
(never case_services.estimated_cost), per-currency (never a blind cross-currency total), the
company rollup is tenant-scoped (negative test), and an absent spend is an honest empty state,
not a fabricated 0.
"""
from __future__ import annotations

import os
import unittest
from decimal import Decimal
from unittest import mock

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from sqlalchemy import create_engine, text  # noqa: E402

from backend.app.services import case_spend as cs  # noqa: E402

SCHEMA = """
CREATE TABLE relocation_cases (id TEXT PRIMARY KEY, company_id TEXT);
CREATE TABLE rfqs (
  id TEXT PRIMARY KEY, case_id TEXT, validated_quote_id TEXT, validated_at TEXT
);
CREATE TABLE quotes (
  id TEXT PRIMARY KEY, total_amount NUMERIC, currency TEXT, vendor_id TEXT, status TEXT
);
CREATE TABLE case_services (case_id TEXT, estimated_cost NUMERIC, currency TEXT);
CREATE TABLE rfq_items (id TEXT PRIMARY KEY, rfq_id TEXT, service_key TEXT);
"""


class CaseSpendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
        # case_spend is the only module issuing these queries, and it uses real sqlalchemy.text
        # (not main_db.text), so patching main_db.engine is enough — even under full-suite
        # collection where backend.database may be the conftest MagicMock.
        patcher = mock.patch.object(cs.main_db, "engine", self.engine)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _exec(self, sql: str, params: dict) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(sql), params)

    def _quote(self, qid, amount, currency, vendor="v1") -> None:
        self._exec(
            "INSERT INTO quotes (id, total_amount, currency, vendor_id, status) "
            "VALUES (:i,:a,:c,:v,'accepted')",
            {"i": qid, "a": amount, "c": currency, "v": vendor},
        )

    def _rfq(self, rid, case_id, validated_quote_id=None, validated_at=None) -> None:
        self._exec(
            "INSERT INTO rfqs (id, case_id, validated_quote_id, validated_at) "
            "VALUES (:i,:c,:q,:t)",
            {"i": rid, "c": case_id, "q": validated_quote_id, "t": validated_at},
        )

    def _reloc(self, case_id, company_id) -> None:
        self._exec(
            "INSERT INTO relocation_cases (id, company_id) VALUES (:i,:c)",
            {"i": case_id, "c": company_id},
        )

    # ── per-case ──────────────────────────────────────────────────────────────
    def test_a_validated_quote_becomes_committed_spend(self):
        self._quote("q1", "5120.50", "EUR", vendor="v1")
        self._rfq("r1", "case-A", validated_quote_id="q1", validated_at="2026-08-22T17:01:35")
        out = cs.committed_spend_for_case("case-A")
        self.assertTrue(out["has_spend"])
        self.assertEqual(set(out["by_currency"]), {"EUR"})
        self.assertEqual(Decimal(out["by_currency"]["EUR"]), Decimal("5120.50"))
        self.assertEqual(len(out["lines"]), 1)
        self.assertEqual(out["lines"][0]["vendor_id"], "v1")
        self.assertEqual(out["lines"][0]["quote_id"], "q1")

    def test_an_unvalidated_rfq_is_not_spend(self):
        self._quote("q1", "500", "EUR")
        self._rfq("r1", "case-U", validated_quote_id=None)
        out = cs.committed_spend_for_case("case-U")
        self.assertFalse(out["has_spend"])
        self.assertEqual(out["by_currency"], {})

    def test_case_services_estimate_is_never_counted(self):
        # Trap 1: a case with an estimated_cost but no validated quote has ZERO committed spend.
        self._exec(
            "INSERT INTO case_services (case_id, estimated_cost, currency) VALUES ('case-E','9999','EUR')",
            {},
        )
        out = cs.committed_spend_for_case("case-E")
        self.assertFalse(out["has_spend"])
        self.assertNotIn("9999", str(out))

    def test_multi_currency_is_per_currency_never_a_cross_total(self):
        # Trap 2: EUR + NOK on one case → two subtotals, and no invented cross-currency total.
        self._quote("q1", "1000", "EUR", vendor="v1")
        self._rfq("r1", "case-X", validated_quote_id="q1", validated_at="t1")
        self._quote("q2", "2000", "NOK", vendor="v2")
        self._rfq("r2", "case-X", validated_quote_id="q2", validated_at="t2")
        out = cs.committed_spend_for_case("case-X")
        self.assertEqual(set(out["by_currency"]), {"EUR", "NOK"})
        self.assertEqual(Decimal(out["by_currency"]["EUR"]), Decimal("1000"))
        self.assertEqual(Decimal(out["by_currency"]["NOK"]), Decimal("2000"))
        self.assertNotIn("total", out)

    def test_a_validated_quote_with_no_amount_is_skipped_not_zeroed(self):
        self._quote("q1", None, "EUR")
        self._rfq("r1", "case-N", validated_quote_id="q1", validated_at="t1")
        out = cs.committed_spend_for_case("case-N")
        self.assertFalse(out["has_spend"])
        self.assertEqual(out["lines"], [])

    # ── company rollup ──────────────────────────────────────────────────────────
    def test_company_rollup_is_tenant_scoped(self):
        # Criterion 3 + its negative test: company A's rollup must exclude company B's quote.
        self._reloc("case-A", "companyA")
        self._reloc("case-B", "companyB")
        self._quote("qA", "1000", "EUR", vendor="v1")
        self._rfq("rA", "case-A", validated_quote_id="qA", validated_at="t1")
        self._quote("qB", "9999", "EUR", vendor="v2")
        self._rfq("rB", "case-B", validated_quote_id="qB", validated_at="t2")

        a = cs.committed_spend_for_company("companyA")
        self.assertTrue(a["has_spend"])
        self.assertEqual(a["case_count"], 1)
        self.assertEqual(Decimal(a["by_currency"]["EUR"]), Decimal("1000"))
        self.assertNotIn("9999", str(a), "company B's validated quote leaked into company A's rollup")

    def test_company_with_no_validated_quote_is_an_honest_empty(self):
        self._reloc("case-A", "companyA")
        out = cs.committed_spend_for_company("companyA")
        self.assertFalse(out["has_spend"])
        self.assertEqual(out["by_currency"], {})
        self.assertEqual(out["case_count"], 0)

    def test_blank_company_id_returns_empty_without_querying(self):
        self.assertEqual(cs.committed_spend_for_company("")["has_spend"], False)

    def _item(self, iid, rfq_id, service_key) -> None:
        self._exec(
            "INSERT INTO rfq_items (id, rfq_id, service_key) VALUES (:i,:r,:k)",
            {"i": iid, "r": rfq_id, "k": service_key},
        )

    def test_service_key_filter_counts_only_partner_career_rfqs(self):
        self._quote("q1", "1000", "EUR", vendor="v1")
        self._rfq("r1", "case-A", validated_quote_id="q1", validated_at="t1")
        self._item("i1", "r1", "spouse")
        self._quote("q2", "5000", "EUR", vendor="v2")
        self._rfq("r2", "case-A", validated_quote_id="q2", validated_at="t2")
        self._item("i2", "r2", "movers")
        all_spend = cs.committed_spend_for_case("case-A")
        self.assertEqual(Decimal(all_spend["by_currency"]["EUR"]), Decimal("6000"))
        partner = cs.committed_spend_for_case(
            "case-A", service_keys=cs.PARTNER_CAREER_SERVICE_KEYS
        )
        self.assertEqual(Decimal(partner["by_currency"]["EUR"]), Decimal("1000"))

    def test_spouse_support_drawdown_same_currency_remaining(self):
        committed = {"has_spend": True, "by_currency": {"EUR": "2000"}}
        out = cs.spouse_support_drawdown(
            cap_amount=7623.0, cap_currency="EUR", committed=committed
        )
        self.assertTrue(out["comparable"])
        self.assertEqual(Decimal(out["remaining"]), Decimal("5623.0"))
        self.assertEqual(out["remaining_currency"], "EUR")

    def test_spouse_support_drawdown_cross_currency_is_not_comparable(self):
        committed = {"has_spend": True, "by_currency": {"NOK": "2000"}}
        out = cs.spouse_support_drawdown(
            cap_amount=7623.0, cap_currency="EUR", committed=committed
        )
        self.assertFalse(out["comparable"])
        self.assertIsNone(out["remaining"])

    def test_spouse_support_drawdown_no_cap_is_honest_empty(self):
        out = cs.spouse_support_drawdown(
            cap_amount=None, cap_currency=None, committed={"has_spend": False, "by_currency": {}}
        )
        self.assertFalse(out["has_cap"])
        self.assertFalse(out["has_spend"])
        self.assertIsNone(out["remaining"])
        self.assertNotEqual(out["remaining"], "0")


if __name__ == "__main__":
    unittest.main()
