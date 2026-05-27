"""
PR #4 — Draft vs Live diff for the Compensation & Allowance matrix.

Covers:
  * empty state (no live, no draft) — all counters zero
  * added / removed / changed / unchanged categorisation
  * changed_fields reports only fields that actually differ
  * revert_row_to_live handles the three cases (overwrite changed,
    delete added, re-insert removed)
  * idempotent revert returns the same diff without mutation
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.database import Database
from backend.app.services.policy_config_matrix_service import (
    PolicyConfigMatrixService,
    compute_targeting_signature,
)


def _row(
    *,
    benefit_key: str,
    label: str = "Test row",
    category: str = "compensation_allowances",
    covered: bool = True,
    amount: float | None = 1000.0,
    currency: str | None = "EUR",
    targeting_signature: str | None = None,
    assignment_types: list[str] | None = None,
    family_statuses: list[str] | None = None,
    employee_levels: list[str] | None = None,
    unit_frequency: str = "one_time",
    notes: str | None = None,
) -> dict:
    at = assignment_types or []
    fs = family_statuses or []
    el = employee_levels or []
    sig = targeting_signature or compute_targeting_signature(at, fs, el)
    return {
        "benefit_key": benefit_key,
        "benefit_label": label,
        "category": category,
        "covered": covered,
        "value_type": "currency" if amount is not None else "none",
        "amount_value": amount,
        "currency_code": currency,
        "percentage_value": None,
        "unit_frequency": unit_frequency,
        "cap_rule_json": {},
        "notes": notes,
        "conditions_json": {},
        "assignment_types": at,
        "family_statuses": fs,
        "employee_levels": el,
        "targeting_signature": sig,
        "is_active": True,
        "display_order": 0,
    }


class _FakeDb:
    """Small in-memory stand-in for Database so the diff logic can be
    exercised without touching sqlite. Only the surface compute_diff /
    revert_row_to_live use is modelled."""

    def __init__(self):
        self.rows_by_version = {}
        self.versions = {}  # vid -> version row
        self.config_id = "cfg-1"
        self.company_id = "co-1"
        self._draft_vid = None
        self._live_vid = None

    def ensure_policy_config(self, company_id, config_key, *, created_by=None):
        return {"id": self.config_id, "company_id": company_id, "config_key": config_key}

    def get_policy_config_draft_for_config(self, cfg_id):
        if not self._draft_vid:
            return None
        return self.versions[self._draft_vid]

    def get_latest_published_policy_config_version(self, company_id, config_key):
        if not self._live_vid:
            return None
        return self.versions[self._live_vid]

    def list_policy_config_benefits(self, vid):
        return list(self.rows_by_version.get(str(vid), []))

    def insert_policy_config_benefit_row(self, row):
        import uuid
        bid = str(row.get("id") or uuid.uuid4())
        row = dict(row)
        row["id"] = bid
        vid = str(row["policy_config_version_id"])
        self.rows_by_version.setdefault(vid, []).append(row)
        return bid

    def delete_policy_config_benefit_by_key(self, vid, *, benefit_key, targeting_signature):
        vid = str(vid)
        before = len(self.rows_by_version.get(vid, []))
        self.rows_by_version[vid] = [
            r for r in self.rows_by_version.get(vid, [])
            if not (
                str(r.get("benefit_key")) == str(benefit_key)
                and str(r.get("targeting_signature") or "global") == str(targeting_signature or "global")
            )
        ]
        return before - len(self.rows_by_version[vid])

    # Test helpers ----------------------------------------------------

    def seed_live(self, rows: list[dict], vid: str = "live-1"):
        self._live_vid = vid
        self.versions[vid] = {
            "id": vid,
            "status": "published",
            "version_number": 1,
            "effective_date": "2026-01-01",
        }
        self.rows_by_version[vid] = [dict(r) for r in rows]

    def seed_draft(self, rows: list[dict], vid: str = "draft-1"):
        self._draft_vid = vid
        self.versions[vid] = {
            "id": vid,
            "status": "draft",
            "version_number": 2,
            "effective_date": "2026-07-01",
        }
        self.rows_by_version[vid] = [dict(r) for r in rows]


class ComputeDiffTests(unittest.TestCase):
    def setUp(self):
        self.db = _FakeDb()
        self.svc = PolicyConfigMatrixService(self.db)

    def test_empty_state(self):
        out = self.svc.compute_diff("co-1")
        self.assertEqual(
            out["diff"]["summary"],
            {"added": 0, "removed": 0, "changed": 0, "unchanged": 0},
        )
        self.assertIsNone(out["live"]["version"])
        self.assertIsNone(out["draft"]["version"])

    def test_added_row(self):
        self.db.seed_live([_row(benefit_key="shipment", amount=5000)])
        self.db.seed_draft([
            _row(benefit_key="shipment", amount=5000),
            _row(benefit_key="home_leave_trips", amount=2000),  # new in draft
        ])
        out = self.svc.compute_diff("co-1")
        self.assertEqual(out["diff"]["summary"]["added"], 1)
        self.assertEqual(out["diff"]["summary"]["removed"], 0)
        self.assertEqual(out["diff"]["summary"]["unchanged"], 1)
        added_keys = [r["benefit_key"] for r in out["diff"]["added"]]
        self.assertEqual(added_keys, ["home_leave_trips"])

    def test_removed_row(self):
        self.db.seed_live([
            _row(benefit_key="shipment", amount=5000),
            _row(benefit_key="home_leave_trips", amount=2000),
        ])
        self.db.seed_draft([_row(benefit_key="shipment", amount=5000)])
        out = self.svc.compute_diff("co-1")
        self.assertEqual(out["diff"]["summary"]["removed"], 1)
        removed_keys = [r["benefit_key"] for r in out["diff"]["removed"]]
        self.assertEqual(removed_keys, ["home_leave_trips"])

    def test_changed_row_tracks_fields(self):
        self.db.seed_live([_row(benefit_key="shipment", amount=5000, notes="original")])
        self.db.seed_draft([_row(benefit_key="shipment", amount=6500, notes="updated per 2026 cap")])
        out = self.svc.compute_diff("co-1")
        self.assertEqual(out["diff"]["summary"]["changed"], 1)
        entry = out["diff"]["changed"][0]
        self.assertEqual(entry["before"]["amount_value"], 5000)
        self.assertEqual(entry["after"]["amount_value"], 6500)
        self.assertIn("amount_value", entry["changed_fields"])
        self.assertIn("notes", entry["changed_fields"])
        self.assertNotIn("benefit_key", entry["changed_fields"])

    def test_unchanged_row_is_not_marked_changed(self):
        row = _row(benefit_key="shipment", amount=5000)
        self.db.seed_live([row])
        self.db.seed_draft([dict(row)])
        out = self.svc.compute_diff("co-1")
        self.assertEqual(out["diff"]["summary"]["changed"], 0)
        self.assertEqual(out["diff"]["summary"]["unchanged"], 1)

    def test_different_targeting_creates_add_plus_remove_not_change(self):
        """Rows with different targeting signatures are logically
        distinct — moving a cap from 'all assignments' to
        'long_term only' should show up as one removed + one added,
        not as a change."""
        live_row = _row(benefit_key="shipment", amount=5000)  # global
        draft_row = _row(
            benefit_key="shipment", amount=5000, assignment_types=["long_term"]
        )
        self.db.seed_live([live_row])
        self.db.seed_draft([draft_row])
        out = self.svc.compute_diff("co-1")
        self.assertEqual(out["diff"]["summary"]["removed"], 1)
        self.assertEqual(out["diff"]["summary"]["added"], 1)
        self.assertEqual(out["diff"]["summary"]["changed"], 0)


class RevertRowTests(unittest.TestCase):
    def setUp(self):
        self.db = _FakeDb()
        self.svc = PolicyConfigMatrixService(self.db)

    def test_revert_changed_row_restores_live_values(self):
        self.db.seed_live([_row(benefit_key="shipment", amount=5000, notes="live")])
        self.db.seed_draft([_row(benefit_key="shipment", amount=6500, notes="draft")])
        out = self.svc.revert_row_to_live(
            "co-1", benefit_key="shipment", targeting_signature="global"
        )
        self.assertEqual(out["diff"]["summary"]["changed"], 0)
        self.assertEqual(out["diff"]["summary"]["unchanged"], 1)
        draft_rows = self.db.list_policy_config_benefits("draft-1")
        self.assertEqual(draft_rows[0]["amount_value"], 5000)
        self.assertEqual(draft_rows[0]["notes"], "live")

    def test_revert_added_row_deletes_from_draft(self):
        self.db.seed_live([_row(benefit_key="shipment", amount=5000)])
        self.db.seed_draft([
            _row(benefit_key="shipment", amount=5000),
            _row(benefit_key="home_leave_trips", amount=2000),
        ])
        out = self.svc.revert_row_to_live(
            "co-1", benefit_key="home_leave_trips", targeting_signature="global"
        )
        self.assertEqual(out["diff"]["summary"]["added"], 0)
        keys = [r["benefit_key"] for r in self.db.list_policy_config_benefits("draft-1")]
        self.assertEqual(sorted(keys), ["shipment"])

    def test_revert_removed_row_reinserts_into_draft(self):
        self.db.seed_live([
            _row(benefit_key="shipment", amount=5000),
            _row(benefit_key="home_leave_trips", amount=2000),
        ])
        self.db.seed_draft([_row(benefit_key="shipment", amount=5000)])
        out = self.svc.revert_row_to_live(
            "co-1", benefit_key="home_leave_trips", targeting_signature="global"
        )
        self.assertEqual(out["diff"]["summary"]["removed"], 0)
        keys = [r["benefit_key"] for r in self.db.list_policy_config_benefits("draft-1")]
        self.assertEqual(sorted(keys), ["home_leave_trips", "shipment"])

    def test_revert_is_idempotent_when_already_matching(self):
        row = _row(benefit_key="shipment", amount=5000)
        self.db.seed_live([row])
        self.db.seed_draft([dict(row)])
        before = self.svc.compute_diff("co-1")
        after = self.svc.revert_row_to_live(
            "co-1", benefit_key="shipment", targeting_signature="global"
        )
        self.assertEqual(before["diff"]["summary"], after["diff"]["summary"])

    def test_revert_without_draft_raises(self):
        self.db.seed_live([_row(benefit_key="shipment", amount=5000)])
        with self.assertRaises(KeyError) as ctx:
            self.svc.revert_row_to_live(
                "co-1", benefit_key="shipment", targeting_signature="global"
            )
        self.assertEqual(ctx.exception.args[0], "no_draft")

    def test_revert_unknown_row_raises(self):
        self.db.seed_live([_row(benefit_key="shipment", amount=5000)])
        self.db.seed_draft([_row(benefit_key="shipment", amount=5000)])
        with self.assertRaises(KeyError) as ctx:
            self.svc.revert_row_to_live(
                "co-1", benefit_key="made_up_benefit", targeting_signature="global"
            )
        self.assertEqual(ctx.exception.args[0], "row_not_found")

    def test_revert_blank_benefit_key_raises(self):
        self.db.seed_live([_row(benefit_key="shipment", amount=5000)])
        self.db.seed_draft([_row(benefit_key="shipment", amount=5000)])
        with self.assertRaises(ValueError):
            self.svc.revert_row_to_live(
                "co-1", benefit_key="", targeting_signature="global"
            )


if __name__ == "__main__":
    unittest.main()
