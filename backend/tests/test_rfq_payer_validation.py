"""AIQ-1524 — the employee PROPOSES; HR (the payer) VALIDATES.

Three defects lived on one code path, all invisible to the existing suite:

  1. update_quote_status used engine.connect() and _exec never commits, so accepting a quote
     was SILENTLY DISCARDED. A mocked test, or one that re-reads on the SAME connection,
     cannot see this — so the test below re-reads on a FRESH connection. That is the whole
     point of it.
  2. Accepting wrote one status column: no cost, no sibling rejection, nothing downstream.
  3. The accept endpoint was require_hr_or_employee — the EMPLOYEE could approve the
     company's money.

These run against a real SQLite engine (not mocks) precisely because the bug is about
transaction handling, which mocks paper over.
"""
from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.db.misc import MiscMixin  # noqa: E402  (_exec / _row_to_dict live here)
from backend.db.vendors import VendorsMixin  # noqa: E402


class _Host(MiscMixin, VendorsMixin):
    def __init__(self, engine) -> None:
        self.engine = engine
        self._initialized = True


def _engine():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with e.begin() as c:
        c.execute(text(
            "CREATE TABLE rfqs (id TEXT, rfq_ref TEXT, case_id TEXT, created_by_user_id TEXT, "
            "status TEXT, created_at TEXT, canonical_case_id TEXT, preferred_quote_id TEXT, "
            "preferred_by_user_id TEXT, preferred_at TEXT, validated_quote_id TEXT, "
            "validated_by_user_id TEXT, validated_at TEXT, validation_reason TEXT)"
        ))
        c.execute(text("CREATE TABLE rfq_items (id TEXT, rfq_id TEXT, service_key TEXT, requirements TEXT, created_at TEXT)"))
        c.execute(text("CREATE TABLE rfq_recipients (id TEXT, rfq_id TEXT, vendor_id TEXT, status TEXT)"))
        c.execute(text(
            "CREATE TABLE quotes (id TEXT, rfq_id TEXT, vendor_id TEXT, currency TEXT, "
            "total_amount REAL, valid_until TEXT, status TEXT, created_at TEXT, created_by_user_id TEXT)"
        ))
        c.execute(text("CREATE TABLE quote_lines (id TEXT, quote_id TEXT, label TEXT, amount REAL)"))
        c.execute(text(
            "CREATE TABLE case_services (id TEXT, case_id TEXT, assignment_id TEXT, service_key TEXT, "
            "category TEXT, selected BOOLEAN, estimated_cost REAL, currency TEXT, created_at TEXT, "
            "updated_at TEXT, canonical_case_id TEXT)"
        ))
        c.execute(text(
            "INSERT INTO rfqs (id, case_id, status) VALUES ('rfq-1', 'case-1', 'sent')"
        ))
        c.execute(text(
            "INSERT INTO quotes (id, rfq_id, vendor_id, currency, total_amount, status) "
            "VALUES ('q-win', 'rfq-1', 'v-1', 'EUR', 4000, 'proposed')"
        ))
        c.execute(text(
            "INSERT INTO quotes (id, rfq_id, vendor_id, currency, total_amount, status) "
            "VALUES ('q-lose', 'rfq-1', 'v-2', 'EUR', 5200, 'proposed')"
        ))
    return e


def _status(engine, quote_id: str) -> str:
    """Re-read on a FRESH connection — an uncommitted UPDATE is invisible here."""
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT status FROM quotes WHERE id = :id"), {"id": quote_id}
        ).scalar()


class UpdateQuoteStatusCommitsTests(unittest.TestCase):
    def test_status_change_is_actually_committed(self):
        # THE REGRESSION GUARD. Before the fix this used engine.connect() and _exec never
        # commits, so the UPDATE was discarded and this read still returned 'proposed'.
        e = _engine()
        _Host(e).update_quote_status("q-win", "accepted")
        self.assertEqual(_status(e, "q-win"), "accepted",
                         "quote status was not committed — the transaction was rolled back")


class ProposeTests(unittest.TestCase):
    def test_employee_proposal_records_preference_without_approving_spend(self):
        e = _engine()
        _Host(e).set_rfq_preferred_quote("rfq-1", "q-win", "emp-1")
        with e.connect() as conn:
            row = conn.execute(text(
                "SELECT preferred_quote_id, preferred_by_user_id FROM rfqs WHERE id='rfq-1'"
            )).fetchone()
        self.assertEqual(row[0], "q-win")
        self.assertEqual(row[1], "emp-1")
        # A proposal commits no money: the quote must NOT be accepted.
        self.assertEqual(_status(e, "q-win"), "proposed")


class ValidateTests(unittest.TestCase):
    def test_validate_accepts_rejects_siblings_and_records_the_reason(self):
        e = _engine()
        host = _Host(e)
        host.set_rfq_preferred_quote("rfq-1", "q-win", "emp-1")

        # HR validates the OTHER offer — the override case, which is exactly why a reason exists.
        res = host.validate_rfq_quote("rfq-1", "q-lose", "hr-1", "Better insurance cover")
        self.assertTrue(res["ok"])

        self.assertEqual(_status(e, "q-lose"), "accepted")
        self.assertEqual(_status(e, "q-win"), "rejected", "sibling quotes must be rejected")

        with e.connect() as conn:
            row = conn.execute(text(
                "SELECT validated_quote_id, validated_by_user_id, validation_reason, status "
                "FROM rfqs WHERE id='rfq-1'"
            )).fetchone()
        self.assertEqual(row[0], "q-lose")
        self.assertEqual(row[1], "hr-1")
        self.assertEqual(row[2], "Better insurance cover")
        self.assertEqual(row[3], "closed")

    def test_single_item_rfq_writes_the_agreed_cost_to_case_services(self):
        e = _engine()
        with e.begin() as c:
            c.execute(text("INSERT INTO rfq_items (id, rfq_id, service_key) VALUES ('i1','rfq-1','moving')"))
            c.execute(text(
                "INSERT INTO case_services (id, case_id, service_key, selected, estimated_cost) "
                "VALUES ('cs1','case-1','moving',1,NULL)"
            ))
        res = _Host(e).validate_rfq_quote("rfq-1", "q-win", "hr-1", None)

        self.assertTrue(res["cost_attributed"])
        with e.connect() as conn:
            cost = conn.execute(text(
                "SELECT estimated_cost FROM case_services WHERE case_id='case-1' AND service_key='moving'"
            )).scalar()
        self.assertEqual(cost, 4000)

    def test_lump_sum_across_several_services_is_NOT_split_by_guesswork(self):
        # The honesty rule (mirrors AIQ-1526): 4000 across 2 services with no per-line
        # breakdown must NOT become 2000 + 2000. We record nothing and say why.
        e = _engine()
        with e.begin() as c:
            c.execute(text("INSERT INTO rfq_items (id, rfq_id, service_key) VALUES ('i1','rfq-1','moving')"))
            c.execute(text("INSERT INTO rfq_items (id, rfq_id, service_key) VALUES ('i2','rfq-1','storage')"))
            c.execute(text(
                "INSERT INTO case_services (id, case_id, service_key, selected, estimated_cost) "
                "VALUES ('cs1','case-1','moving',1,NULL)"
            ))
        res = _Host(e).validate_rfq_quote("rfq-1", "q-win", "hr-1", None)

        self.assertFalse(res["cost_attributed"])
        self.assertEqual(res["cost_not_attributed_reason"], "lump_sum_across_multiple_services")
        with e.connect() as conn:
            cost = conn.execute(text(
                "SELECT estimated_cost FROM case_services WHERE service_key='moving'"
            )).scalar()
        self.assertIsNone(cost, "a per-service cost was invented from a lump sum")

    def test_supplier_line_items_are_used_when_they_map_to_the_requested_services(self):
        e = _engine()
        with e.begin() as c:
            c.execute(text("INSERT INTO rfq_items (id, rfq_id, service_key, created_at) VALUES ('i1','rfq-1','moving','1')"))
            c.execute(text("INSERT INTO rfq_items (id, rfq_id, service_key, created_at) VALUES ('i2','rfq-1','storage','2')"))
            c.execute(text("INSERT INTO quote_lines (id, quote_id, label, amount) VALUES ('l1','q-win','Move',3000)"))
            c.execute(text("INSERT INTO quote_lines (id, quote_id, label, amount) VALUES ('l2','q-win','Storage',1000)"))
            c.execute(text(
                "INSERT INTO case_services (id, case_id, service_key, selected) VALUES ('cs1','case-1','moving',1)"
            ))
            c.execute(text(
                "INSERT INTO case_services (id, case_id, service_key, selected) VALUES ('cs2','case-1','storage',1)"
            ))
        res = _Host(e).validate_rfq_quote("rfq-1", "q-win", "hr-1", None)

        self.assertTrue(res["cost_attributed"])
        with e.connect() as conn:
            rows = dict(conn.execute(text(
                "SELECT service_key, estimated_cost FROM case_services WHERE case_id='case-1'"
            )).fetchall())
        self.assertEqual(rows["moving"], 3000)
        self.assertEqual(rows["storage"], 1000)

    def test_unknown_quote_is_reported_not_silently_accepted(self):
        self.assertFalse(_Host(_engine()).validate_rfq_quote("rfq-1", "nope", "hr-1", None)["ok"])


if __name__ == "__main__":
    unittest.main()
