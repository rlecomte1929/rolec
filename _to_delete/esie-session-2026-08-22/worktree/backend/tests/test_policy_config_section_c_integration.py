"""
Integration tests for Section C wiring through PolicyConfigMatrixService.

Covers the full round-trip:
  put_draft (with overrides) -> reload draft -> publish ->
  employee_grouped_payload(country=..., employee_level=...) -> resolved row.

Plus validation (bad country, conflict, tier ordering) and a regression
test that templates still apply cleanly when overrides exist.

Uses an in-memory mock DB extending the pattern from
test_policy_config_matrix_service.py — same shape, just adds the two
override-related methods I introduced in PR 2.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.policy_config_matrix_service import (  # noqa: E402
    CONFIG_KEY,
    PolicyConfigMatrixService,
)


def _dec(val_err: ValueError) -> dict:
    return json.loads(str(val_err))


class _SectionCDb:
    """Fake DB with both base-row and override-row support."""

    def __init__(self) -> None:
        self.company_id = "co-test"
        self.pc_id = "pc-test"
        self._benefits: dict[str, list[dict]] = {}
        self._overrides: dict[str, list[dict]] = {}  # benefit_row_id -> overrides
        self._version_meta: dict[str, dict] = {}
        self.draft_id: str | None = None
        self.published_id: str | None = None

    # --- config / version housekeeping ----------------------------------

    def ensure_policy_config(self, company_id: str, config_key: str) -> dict:
        return {"id": self.pc_id, "company_id": company_id, "config_key": config_key}

    def get_policy_config_draft_for_config(self, pid: str) -> dict | None:
        return self._version_row(self.draft_id) if self.draft_id else None

    def get_latest_published_policy_config_version(
        self, company_id: str, config_key: str
    ) -> dict | None:
        return self._version_row(self.published_id) if self.published_id else None

    def get_policy_config_version_row(self, vid: str) -> dict | None:
        return self._version_row(vid)

    def get_policy_config_version_with_config(self, vid: str) -> dict | None:
        vm = self._version_meta.get(str(vid))
        if not vm:
            return None
        return {**vm, "_company_id": self.company_id, "_config_key": CONFIG_KEY}

    def max_policy_config_version_number(self, pid: str) -> int:
        return 0

    def insert_policy_config_version(
        self, pid, vernum, status, eff, created_by=None
    ) -> str:
        vid = f"v-{status}-{vernum}-{uuid.uuid4().hex[:6]}"
        self._version_meta[vid] = {
            "id": vid,
            "policy_config_id": pid,
            "version_number": vernum,
            "status": status,
            "effective_date": eff,
            "published_at": None,
        }
        self._benefits[vid] = []
        if status == "draft":
            self.draft_id = vid
        if status == "published":
            self.published_id = vid
        return vid

    def update_policy_config_version_effective_date(
        self, vid: str, ed: str, only_if_draft: bool = True
    ) -> None:
        self._version_meta[str(vid)]["effective_date"] = ed[:10]

    def publish_policy_config_version_atomic(self, vid: str) -> None:
        m = self._version_meta[str(vid)]
        if self.published_id and self.published_id != vid:
            self._version_meta[self.published_id]["status"] = "archived"
        m["status"] = "published"
        m["published_at"] = "2026-04-27T00:00:00"
        self.published_id = str(vid)
        self.draft_id = None

    # --- benefit rows ----------------------------------------------------

    def insert_policy_config_benefit_row(self, row: dict) -> str:
        vid = str(row["policy_config_version_id"])
        bid = str(row.get("id") or uuid.uuid4())
        stored = dict(row)
        stored["id"] = bid
        self._benefits.setdefault(vid, []).append(stored)
        return bid

    def delete_policy_config_benefits_for_version(self, vid: str) -> None:
        # Cascade: drop overrides for any benefit row in this version.
        for r in self._benefits.get(str(vid), []):
            self._overrides.pop(str(r.get("id") or ""), None)
        self._benefits[str(vid)] = []

    def list_policy_config_benefits(self, vid: str) -> list[dict]:
        return list(self._benefits.get(str(vid), []))

    # --- Section C overrides (the new helpers PR 2 introduced) ----------

    def list_jurisdiction_overrides_for_benefit_rows(
        self, benefit_row_ids
    ) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {str(b): [] for b in (benefit_row_ids or [])}
        for bid in (benefit_row_ids or []):
            out[str(bid)] = list(self._overrides.get(str(bid), []))
        return out

    def replace_jurisdiction_overrides_for_benefit(
        self, benefit_row_id: str, overrides: list[dict]
    ) -> None:
        bid = str(benefit_row_id)
        clean = []
        for ov in overrides or []:
            row = dict(ov)
            row.setdefault("id", str(uuid.uuid4()))
            row["benefit_row_id"] = bid
            clean.append(row)
        self._overrides[bid] = clean

    # --- private ---------------------------------------------------------

    def _version_row(self, vid: str | None) -> dict | None:
        if not vid:
            return None
        return self._version_meta.get(str(vid))


def _body_with_overrides() -> dict:
    """A draft body where one benefit has two overrides:
      - SEA group (SG/MY/TH) at director level → 8500 SGD (specificity 2)
      - SG-only at director + permanent → 12000 SGD (specificity 3, wins
        for SG directors on permanent assignments).

    The shape exercises the resolver's tie-break: same country list size
    is irrelevant, but level (+2) + assignment_type (+1) beats level
    alone (+2)."""
    return {
        "policy_version": "PLACEHOLDER",
        "effective_date": "2026-06-01",
        "categories": [
            {
                "category_key": "compensation_allowances",
                "benefits": [
                    {
                        "benefit_key": "housing_allowance",
                        "benefit_label": "Housing allowance",
                        "covered": True,
                        "value_type": "currency",
                        "amount_value": 5000,
                        "currency_code": "USD",
                        "unit_frequency": "monthly",
                        "jurisdiction_overrides": [
                            {
                                "jurisdiction_countries": ["SG", "MY", "TH"],
                                "employee_level": "director",
                                "amount_value": 8500,
                                "currency_code": "SGD",
                                "reimbursement_md": "SEA director cap.",
                            },
                            {
                                "jurisdiction_countries": ["SG"],
                                "employee_level": "director",
                                "assignment_type": "permanent",
                                "amount_value": 12000,
                                "currency_code": "SGD",
                            },
                        ],
                    }
                ],
            }
        ],
    }


class SectionCRoundTripTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _SectionCDb()
        self.svc = PolicyConfigMatrixService(self.db)

    def test_put_draft_persists_overrides(self) -> None:
        vid = self.db.insert_policy_config_version(self.db.pc_id, 1, "draft", "2026-04-01")
        body = _body_with_overrides()
        body["policy_version"] = vid
        out = self.svc.put_draft(self.db.company_id, body)
        # Overrides land in the fake DB.
        bens = self.db.list_policy_config_benefits(vid)
        self.assertEqual(len(bens), 1)
        bid = bens[0]["id"]
        ovs = self.db._overrides[bid]
        self.assertEqual(len(ovs), 2)
        self.assertEqual({tuple(sorted(o["jurisdiction_countries"])) for o in ovs},
                         {("MY", "SG", "TH"), ("SG",)})
        # And the response payload includes them.
        cats = out["categories"]
        sec_c = cats[0]["benefits"][0]["jurisdiction_overrides"]
        self.assertEqual(len(sec_c), 2)

    def test_round_trip_via_get_working_payload(self) -> None:
        vid = self.db.insert_policy_config_version(self.db.pc_id, 1, "draft", "2026-04-01")
        body = _body_with_overrides()
        body["policy_version"] = vid
        self.svc.put_draft(self.db.company_id, body)
        # Reload via the getter that the GET /policy-config endpoint uses.
        payload = self.svc.get_working_payload(self.db.company_id)
        ben = payload["categories"][0]["benefits"][0]
        self.assertEqual(len(ben["jurisdiction_overrides"]), 2)
        # Country list normalized to ISO-2 upper.
        for ov in ben["jurisdiction_overrides"]:
            for c in ov["jurisdiction_countries"]:
                self.assertEqual(c, c.upper())
                self.assertEqual(len(c), 2)

    def test_employee_grouped_payload_resolves_for_country(self) -> None:
        vid = self.db.insert_policy_config_version(self.db.pc_id, 1, "draft", "2026-04-01")
        body = _body_with_overrides()
        body["policy_version"] = vid
        self.svc.put_draft(self.db.company_id, body)
        self.svc.publish_draft(self.db.company_id, policy_version_id=vid, created_by=None)

        # Director in Singapore (permanent) -> the more-specific
        # SG+permanent override wins (12000 SGD), not the SEA director
        # override (8500 SGD).
        out = self.svc.employee_grouped_payload(
            self.db.company_id,
            assignment_type="permanent",
            family_status=None,
            country="SG",
            employee_level="director",
        )
        ben = out["categories"][0]["benefits"][0]
        self.assertEqual(ben["amount_value"], 12000)
        self.assertEqual(ben["currency_code"], "SGD")
        self.assertTrue(ben["override_applied"])

    def test_employee_grouped_payload_falls_back_to_base_when_no_match(self) -> None:
        vid = self.db.insert_policy_config_version(self.db.pc_id, 1, "draft", "2026-04-01")
        body = _body_with_overrides()
        body["policy_version"] = vid
        self.svc.put_draft(self.db.company_id, body)
        self.svc.publish_draft(self.db.company_id, policy_version_id=vid, created_by=None)
        # Manager in Japan: no override matches (SEA director / SG permanent
        # only). Base row applies.
        out = self.svc.employee_grouped_payload(
            self.db.company_id,
            assignment_type="permanent",
            family_status=None,
            country="JP",
            employee_level="manager",
        )
        ben = out["categories"][0]["benefits"][0]
        self.assertEqual(ben["amount_value"], 5000)
        self.assertEqual(ben["currency_code"], "USD")
        self.assertFalse(ben["override_applied"])

    def test_employee_grouped_payload_without_country_returns_base_plus_overrides(self) -> None:
        vid = self.db.insert_policy_config_version(self.db.pc_id, 1, "draft", "2026-04-01")
        body = _body_with_overrides()
        body["policy_version"] = vid
        self.svc.put_draft(self.db.company_id, body)
        self.svc.publish_draft(self.db.company_id, policy_version_id=vid, created_by=None)
        # No country: resolver should not collapse — base values stay,
        # but overrides are still surfaced alongside.
        out = self.svc.employee_grouped_payload(
            self.db.company_id,
            assignment_type=None,
            family_status=None,
        )
        ben = out["categories"][0]["benefits"][0]
        self.assertEqual(ben["amount_value"], 5000)
        self.assertEqual(len(ben["jurisdiction_overrides"]), 2)
        self.assertFalse(ben["override_applied"])


class SectionCValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _SectionCDb()
        self.svc = PolicyConfigMatrixService(self.db)

    def _put_with_override(self, override_payload: dict) -> dict:
        vid = self.db.insert_policy_config_version(self.db.pc_id, 1, "draft", "2026-04-01")
        body = {
            "policy_version": vid,
            "effective_date": "2026-06-01",
            "categories": [
                {
                    "category_key": "compensation_allowances",
                    "benefits": [
                        {
                            "benefit_key": "housing_allowance",
                            "benefit_label": "Housing",
                            "covered": True,
                            "value_type": "currency",
                            "amount_value": 5000,
                            "currency_code": "USD",
                            "unit_frequency": "monthly",
                            "jurisdiction_overrides": [override_payload],
                        }
                    ],
                }
            ],
        }
        return self.svc.put_draft(self.db.company_id, body)

    def test_unknown_country_code_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self._put_with_override({
                "jurisdiction_countries": ["ZZ"],
                "amount_value": 10000,
            })
        d = _dec(ctx.exception)
        self.assertEqual(d["code"], "validation_error")
        self.assertTrue(
            any("ZZ" in str(e.get("message", "")) for e in d["errors"]),
            f"Expected ZZ in errors; got {d['errors']}",
        )

    def test_empty_country_list_rejected(self) -> None:
        with self.assertRaises(Exception):
            # Pydantic min_length=1 catches this before our validator;
            # either ValidationError or ValueError is acceptable here —
            # the point is HR can't author an override targeting nothing.
            self._put_with_override({
                "jurisdiction_countries": [],
                "amount_value": 10000,
            })

    def test_broken_tier_ordering_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self._put_with_override({
                "jurisdiction_countries": ["SG"],
                "cap_rule_json": {
                    "tiers": [{"max": 5000}, {"max": 2000}, {"max": 8000}],
                },
            })
        d = _dec(ctx.exception)
        self.assertEqual(d["code"], "validation_error")
        self.assertTrue(
            any("non-decreasing" in str(e.get("message", "")).lower() for e in d["errors"])
        )

    def test_collision_on_same_level_assignment_tuple_rejected(self) -> None:
        vid = self.db.insert_policy_config_version(self.db.pc_id, 1, "draft", "2026-04-01")
        body = {
            "policy_version": vid,
            "effective_date": "2026-06-01",
            "categories": [
                {
                    "category_key": "compensation_allowances",
                    "benefits": [
                        {
                            "benefit_key": "housing_allowance",
                            "benefit_label": "Housing",
                            "covered": True,
                            "value_type": "currency",
                            "amount_value": 5000,
                            "currency_code": "USD",
                            "unit_frequency": "monthly",
                            "jurisdiction_overrides": [
                                {
                                    "jurisdiction_countries": ["SG"],
                                    "employee_level": "manager",
                                    "amount_value": 8000,
                                },
                                {
                                    "jurisdiction_countries": ["MY"],
                                    "employee_level": "manager",
                                    "amount_value": 7500,
                                },
                            ],
                        }
                    ],
                }
            ],
        }
        with self.assertRaises(ValueError) as ctx:
            self.svc.put_draft(self.db.company_id, body)
        d = _dec(ctx.exception)
        self.assertEqual(d["code"], "validation_error")
        msg = " ".join(str(e.get("message", "")) for e in d["errors"])
        self.assertIn("Duplicate override", msg)


class SectionCTemplateRegressionTests(unittest.TestCase):
    """Regression: applying a template (which has zero overrides) followed
    by a put_draft round-trip must leave no orphan override data and must
    not introduce override fields on rows that didn't have them."""

    def setUp(self) -> None:
        self.db = _SectionCDb()
        self.svc = PolicyConfigMatrixService(self.db)

    def test_template_apply_then_round_trip_preserves_empty_overrides(self) -> None:
        vid = self.db.insert_policy_config_version(self.db.pc_id, 1, "draft", "2026-04-01")
        # Simulate a template insert: rows with no overrides field.
        self.db._benefits[vid] = [
            {
                "id": "b-1",
                "policy_config_version_id": vid,
                "benefit_key": "shipment",
                "benefit_label": "Shipment",
                "category": "relocation_assistance",
                "covered": True,
                "value_type": "currency",
                "amount_value": 8000,
                "currency_code": "USD",
                "unit_frequency": "one_time",
                "cap_rule_json": {},
                "conditions_json": {},
                "assignment_types": [],
                "family_statuses": [],
                "employee_levels": [],
                "targeting_signature": "global",
                "is_active": True,
                "display_order": 0,
            }
        ]
        # Read it back via the same getter HR uses — should round-trip
        # cleanly with empty jurisdiction_overrides on the row.
        payload = self.svc.get_working_payload(self.db.company_id)
        ben = payload["categories"][0]["benefits"][0]
        self.assertEqual(ben["benefit_key"], "shipment")
        self.assertEqual(ben["jurisdiction_overrides"], [])

    def test_round_trip_with_no_overrides_clears_orphans(self) -> None:
        # Pre-populate a benefit + an override, then send a put_draft
        # body for the same benefit_key with NO overrides. The override
        # should be dropped (cascade via delete-and-reinsert).
        vid = self.db.insert_policy_config_version(self.db.pc_id, 1, "draft", "2026-04-01")
        # Seed: one benefit with one override.
        self.db._benefits[vid] = [
            {
                "id": "b-1",
                "policy_config_version_id": vid,
                "benefit_key": "housing_allowance",
                "benefit_label": "Housing",
                "category": "compensation_allowances",
                "covered": True,
                "value_type": "currency",
                "amount_value": 5000,
                "currency_code": "USD",
                "unit_frequency": "monthly",
                "cap_rule_json": {},
                "conditions_json": {},
                "assignment_types": [],
                "family_statuses": [],
                "employee_levels": [],
                "targeting_signature": "global",
                "is_active": True,
                "display_order": 0,
            }
        ]
        self.db._overrides["b-1"] = [
            {"id": "ov-old", "benefit_row_id": "b-1",
             "jurisdiction_countries": ["SG"], "employee_level": "manager",
             "amount_value": 9000}
        ]
        # Now write the SAME benefit with no overrides.
        body = {
            "policy_version": vid,
            "effective_date": "2026-06-01",
            "categories": [
                {
                    "category_key": "compensation_allowances",
                    "benefits": [
                        {
                            "benefit_key": "housing_allowance",
                            "benefit_label": "Housing",
                            "covered": True,
                            "value_type": "currency",
                            "amount_value": 5000,
                            "currency_code": "USD",
                            "unit_frequency": "monthly",
                            # Note: no jurisdiction_overrides field at all.
                        }
                    ],
                }
            ],
        }
        self.svc.put_draft(self.db.company_id, body)
        # The OLD benefit row (b-1) was deleted; orphan override b-1 should
        # have been cleaned up by delete_policy_config_benefits_for_version
        # (cascade in the fake mirrors the FK ON DELETE CASCADE).
        self.assertNotIn("b-1", self.db._overrides)
        # New benefit row has no overrides.
        bens = self.db.list_policy_config_benefits(vid)
        self.assertEqual(len(bens), 1)
        new_bid = bens[0]["id"]
        self.assertEqual(self.db._overrides.get(new_bid, []), [])


if __name__ == "__main__":
    unittest.main()
