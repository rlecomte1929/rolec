"""
Canonical (document-normalized) policy Draft vs Live diff.

Covers:
  * empty state — neither live nor draft exists → zero counts
  * added / removed / changed / unchanged categorisation on rules
  * changed_fields report only fields that actually moved
  * exclusions diff mirrors rule shape
  * rule identity is (benefit_key, calc_type, amount_unit, frequency):
    changing frequency becomes remove+add, not a field change
  * dict/json fields compared stably (sorted keys)
  * resolve_primary_policy_id_for_company returns the latest policy

Uses a tiny fake DB so the diff logic runs without a sqlite engine.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.policy_canonical_diff import (
    compute_canonical_diff,
    resolve_primary_policy_id_for_company,
)


def _rule(**overrides) -> dict:
    base = {
        "id": "r",
        "benefit_key": "relocation_allowance",
        "benefit_category": "allowance",
        "calc_type": "lump_sum",
        "amount_value": 5000,
        "amount_unit": "EUR",
        "currency": "EUR",
        "frequency": "per_assignment",
        "description": "Relocation allowance",
        "raw_text": "source wording",
        "review_status": "reviewed",
        "confidence": 0.9,
        "metadata_json": {},
    }
    base.update(overrides)
    return base


def _exclusion(**overrides) -> dict:
    base = {
        "id": "e",
        "benefit_key": "shipment",
        "domain": "shipment",
        "description": "No storage after 90 days",
        "raw_text": "source",
        "review_status": "reviewed",
        "confidence": 0.8,
    }
    base.update(overrides)
    return base


class _FakeDb:
    """Mirrors just the surface compute_canonical_diff and
    resolve_primary_policy_id_for_company use."""

    class _Engine:
        class _Conn:
            def __init__(self, responses):
                self._responses = list(responses)

            def execute(self, _text, _params=None):
                # pop the next canned response as the "row"
                return self

            def fetchone(self):
                if not self._responses:
                    return None
                return self._responses.pop(0)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def __init__(self, draft_row=None):
            self._draft_row = draft_row

        def connect(self):
            # _load_draft_version runs a single SELECT. Return one row
            # (the draft) or None.
            return self._Conn([self._draft_row] if self._draft_row else [])

    def __init__(self):
        self.engine = self._Engine(draft_row=None)
        self.live_version = None
        self.rules_by_version = {}
        self.excl_by_version = {}
        self.latest_policy = None

    # Methods compute_canonical_diff calls
    def get_published_policy_version(self, _policy_id):
        return self.live_version

    def list_policy_benefit_rules(self, vid):
        return list(self.rules_by_version.get(str(vid), []))

    def list_policy_exclusions(self, vid):
        return list(self.excl_by_version.get(str(vid), []))

    def _row_to_dict(self, row):
        # our fake row is already a dict
        return dict(row) if row else None

    def _decode_policy_version_row(self, _d):
        return None

    def get_latest_company_policy(self, _cid):
        return self.latest_policy

    # Seeders
    def seed_live(self, rules=None, exclusions=None, vid="live-1"):
        self.live_version = {"id": vid, "version_number": 1, "status": "published"}
        self.rules_by_version[vid] = list(rules or [])
        self.excl_by_version[vid] = list(exclusions or [])

    def seed_draft(self, rules=None, exclusions=None, vid="draft-1"):
        self.engine = self._Engine(draft_row={"id": vid, "version_number": 2, "status": "draft"})
        self.rules_by_version[vid] = list(rules or [])
        self.excl_by_version[vid] = list(exclusions or [])


class ComputeCanonicalDiffTests(unittest.TestCase):
    def test_empty_state(self):
        db = _FakeDb()
        out = compute_canonical_diff(db, "pol-1")
        self.assertEqual(
            out["diff"]["summary"],
            {
                "rules": {"added": 0, "removed": 0, "changed": 0, "unchanged": 0},
                "exclusions": {"added": 0, "removed": 0, "changed": 0, "unchanged": 0},
            },
        )
        self.assertIsNone(out["live"]["version"])
        self.assertIsNone(out["draft"]["version"])

    def test_added_rule(self):
        db = _FakeDb()
        db.seed_live(rules=[_rule(benefit_key="relocation_allowance")])
        db.seed_draft(
            rules=[
                _rule(benefit_key="relocation_allowance"),
                _rule(benefit_key="home_leave", amount_value=1500),  # new
            ]
        )
        out = compute_canonical_diff(db, "pol-1")
        self.assertEqual(out["diff"]["summary"]["rules"]["added"], 1)
        self.assertEqual(out["diff"]["summary"]["rules"]["unchanged"], 1)
        self.assertEqual(out["diff"]["rules"]["added"][0]["benefit_key"], "home_leave")

    def test_removed_rule(self):
        db = _FakeDb()
        db.seed_live(
            rules=[
                _rule(benefit_key="relocation_allowance"),
                _rule(benefit_key="home_leave", amount_value=1500),
            ]
        )
        db.seed_draft(rules=[_rule(benefit_key="relocation_allowance")])
        out = compute_canonical_diff(db, "pol-1")
        self.assertEqual(out["diff"]["summary"]["rules"]["removed"], 1)
        self.assertEqual(out["diff"]["rules"]["removed"][0]["benefit_key"], "home_leave")

    def test_changed_rule_tracks_fields(self):
        db = _FakeDb()
        db.seed_live(rules=[_rule(amount_value=5000, description="original")])
        db.seed_draft(rules=[_rule(amount_value=6500, description="updated")])
        out = compute_canonical_diff(db, "pol-1")
        self.assertEqual(out["diff"]["summary"]["rules"]["changed"], 1)
        entry = out["diff"]["rules"]["changed"][0]
        self.assertIn("amount_value", entry["changed_fields"])
        self.assertIn("description", entry["changed_fields"])
        # changed_fields only includes fields in _RULE_COMPARE_FIELDS
        self.assertNotIn("benefit_key", entry["changed_fields"])
        self.assertEqual(entry["before"]["amount_value"], 5000)
        self.assertEqual(entry["after"]["amount_value"], 6500)

    def test_unchanged_rule_is_not_marked_changed(self):
        row = _rule()
        db = _FakeDb()
        db.seed_live(rules=[row])
        db.seed_draft(rules=[dict(row)])
        out = compute_canonical_diff(db, "pol-1")
        self.assertEqual(out["diff"]["summary"]["rules"]["changed"], 0)
        self.assertEqual(out["diff"]["summary"]["rules"]["unchanged"], 1)

    def test_frequency_change_is_remove_plus_add_not_field_change(self):
        """Identity is (benefit_key, calc_type, amount_unit, frequency).
        Changing frequency => rules are semantically different, so the
        live row is 'removed' and the draft row is 'added' — not a
        field change."""
        db = _FakeDb()
        db.seed_live(rules=[_rule(frequency="per_assignment")])
        db.seed_draft(rules=[_rule(frequency="monthly")])
        out = compute_canonical_diff(db, "pol-1")
        self.assertEqual(out["diff"]["summary"]["rules"]["changed"], 0)
        self.assertEqual(out["diff"]["summary"]["rules"]["removed"], 1)
        self.assertEqual(out["diff"]["summary"]["rules"]["added"], 1)

    def test_metadata_json_dict_order_does_not_trigger_change(self):
        db = _FakeDb()
        db.seed_live(rules=[_rule(metadata_json={"tier": "std", "source": "doc"})])
        db.seed_draft(rules=[_rule(metadata_json={"source": "doc", "tier": "std"})])
        out = compute_canonical_diff(db, "pol-1")
        self.assertEqual(out["diff"]["summary"]["rules"]["changed"], 0)

    def test_exclusions_diff(self):
        db = _FakeDb()
        db.seed_live(exclusions=[_exclusion(description="live text")])
        db.seed_draft(exclusions=[_exclusion(description="draft text")])
        out = compute_canonical_diff(db, "pol-1")
        self.assertEqual(out["diff"]["summary"]["exclusions"]["changed"], 1)
        self.assertEqual(out["diff"]["summary"]["exclusions"]["added"], 0)
        self.assertEqual(out["diff"]["summary"]["exclusions"]["removed"], 0)


class ResolvePrimaryPolicyTests(unittest.TestCase):
    def test_returns_latest_policy_id(self):
        db = _FakeDb()
        db.latest_policy = {"id": "pol-42"}
        self.assertEqual(resolve_primary_policy_id_for_company(db, "co-1"), "pol-42")

    def test_returns_none_when_no_policy(self):
        db = _FakeDb()
        self.assertIsNone(resolve_primary_policy_id_for_company(db, "co-1"))


if __name__ == "__main__":
    unittest.main()
