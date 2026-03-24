"""
Unit tests for PolicyConfigMatrixService (Compensation & Allowance) with an in-memory mock DB.

Covers draft save validation, publish gate, employee/caps filtering, company scoping, and compare wiring.
DB uniqueness (one published / one draft) is enforced in SQL migrations — we assert the atomic publish call here.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_config_matrix_service import (  # noqa: E402
    CONFIG_KEY,
    PolicyConfigMatrixService,
    compute_targeting_signature,
)


def _dec(val_err: ValueError) -> dict:
    return json.loads(str(val_err))


class _StatefulPolicyDb:
    """Minimal fake DB for PolicyConfigMatrixService tests."""

    def __init__(self) -> None:
        self.company_id = "co-test"
        self.pc_id = "pc-test"
        self._benefits: dict[str, list[dict]] = {}
        self._version_meta: dict[str, dict] = {}
        self.draft_id: str | None = None
        self.published_id: str | None = None
        self.publish_atomic_calls: list[str] = []

    def ensure_policy_config(self, company_id: str, config_key: str) -> dict:
        return {"id": self.pc_id, "company_id": company_id, "config_key": config_key}

    def get_policy_config_draft_for_config(self, pid: str) -> dict | None:
        if not self.draft_id:
            return None
        return self._version_row(self.draft_id)

    def get_latest_published_policy_config_version(self, company_id: str, config_key: str) -> dict | None:
        if not self.published_id:
            return None
        return self._version_row(self.published_id)

    def get_policy_config_version_row(self, vid: str) -> dict | None:
        return self._version_row(vid)

    def list_policy_config_benefits(self, vid: str) -> list[dict]:
        return list(self._benefits.get(str(vid), []))

    def max_policy_config_version_number(self, pid: str) -> int:
        return 0

    def insert_policy_config_version(self, pid, vernum, status, eff, created_by=None) -> str:
        vid = f"v-{status}-{vernum}"
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

    def insert_policy_config_benefit_row(self, row: dict) -> None:
        vid = str(row["policy_config_version_id"])
        self._benefits.setdefault(vid, []).append(dict(row))

    def delete_policy_config_benefits_for_version(self, vid: str) -> None:
        self._benefits[str(vid)] = []

    def get_policy_config_version_with_config(self, vid: str) -> dict | None:
        vm = self._version_meta.get(str(vid))
        if not vm:
            return None
        return {**vm, "_company_id": self.company_id, "_config_key": CONFIG_KEY}

    def publish_policy_config_version_atomic(self, vid: str) -> None:
        self.publish_atomic_calls.append(str(vid))
        vid = str(vid)
        m = self._version_meta[vid]
        if self.published_id and self.published_id != vid:
            old = self._version_meta.get(self.published_id)
            if old:
                old["status"] = "archived"
        m["status"] = "published"
        m["published_at"] = "2025-03-01T00:00:00"
        self.published_id = vid
        self.draft_id = None

    def update_policy_config_version_effective_date(self, vid: str, ed: str, only_if_draft: bool = True) -> None:
        self._version_meta[str(vid)]["effective_date"] = ed[:10]

    def _version_row(self, vid: str | None) -> dict | None:
        if not vid:
            return None
        return self._version_meta.get(str(vid))


class PolicyConfigMatrixServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _StatefulPolicyDb()
        self.svc = PolicyConfigMatrixService(self.db)

    def test_put_draft_save_updates_benefits_and_effective_date(self) -> None:
        vid = self.db.insert_policy_config_version(self.db.pc_id, 1, "draft", "2025-01-01")
        body = {
            "policy_version": vid,
            "effective_date": "2025-06-15",
            "categories": [
                {
                    "category_key": "tax_payroll",
                    "benefits": [
                        {
                            "benefit_key": "tax_equalisation",
                            "benefit_label": "Tax equalisation",
                            "covered": True,
                            "value_type": "text",
                            "unit_frequency": "one_time",
                            "notes": "Programme applies per policy letter.",
                        }
                    ],
                }
            ],
        }
        self.svc.put_draft(self.db.company_id, body)
        self.assertEqual(self.db._version_meta[vid]["effective_date"], "2025-06-15")
        bens = self.db.list_policy_config_benefits(vid)
        self.assertEqual(len(bens), 1)
        self.assertEqual(bens[0]["benefit_key"], "tax_equalisation")

    def test_validate_put_body_rejects_missing_policy_version(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.svc.validate_put_body({"effective_date": "2025-01-01", "categories": [{"category_key": "tax_payroll", "benefits": []}]})
        d = _dec(ctx.exception)
        self.assertEqual(d["code"], "validation_error")
        self.assertTrue(any(e["field"] == "policy_version" for e in d["errors"]))

    def test_validate_put_body_rejects_currency_amount_without_currency_code(self) -> None:
        body = {
            "policy_version": "v1",
            "effective_date": "2025-01-01",
            "categories": [
                {
                    "category_key": "compensation_allowances",
                    "benefits": [
                        {
                            "benefit_key": "cola",
                            "benefit_label": "COLA",
                            "covered": True,
                            "value_type": "currency",
                            "amount_value": 500,
                            "unit_frequency": "monthly",
                        }
                    ],
                }
            ],
        }
        with self.assertRaises(ValueError) as ctx:
            self.svc.validate_put_body(body)
        d = _dec(ctx.exception)
        self.assertTrue(any("currency_code" in str(e.get("message", "")).lower() for e in d["errors"]))

    def test_put_draft_wrong_company_raises(self) -> None:
        vid = self.db.insert_policy_config_version(self.db.pc_id, 1, "draft", "2025-01-01")
        body = {
            "policy_version": vid,
            "effective_date": "2025-02-01",
            "categories": [
                {
                    "category_key": "tax_payroll",
                    "benefits": [
                        {
                            "benefit_key": "tax_equalisation",
                            "benefit_label": "Tax equalisation",
                            "covered": False,
                            "value_type": "none",
                            "unit_frequency": "one_time",
                        }
                    ],
                }
            ],
        }

        real = self.db.get_policy_config_version_with_config

        def _wrong_company(v: str):
            m = self.db._version_meta.get(str(v))
            if not m:
                return None
            return {**m, "_company_id": "intruder-corp", "_config_key": CONFIG_KEY}

        self.db.get_policy_config_version_with_config = _wrong_company  # type: ignore[method-assign]
        try:
            with self.assertRaises(KeyError) as ctx:
                self.svc.put_draft(self.db.company_id, body)
            self.assertEqual(str(ctx.exception), "'draft_not_found'")
        finally:
            self.db.get_policy_config_version_with_config = real  # type: ignore[method-assign]

    def test_publish_requires_effective_date(self) -> None:
        vid = self.db.insert_policy_config_version(self.db.pc_id, 1, "draft", "")
        self.db._version_meta[vid]["effective_date"] = None
        with self.assertRaises(ValueError) as ctx:
            self.svc.publish_draft(self.db.company_id, policy_version_id=vid, created_by=None)
        d = _dec(ctx.exception)
        self.assertTrue(any(e["field"] == "effective_date" for e in d["errors"]))

    def test_publish_calls_atomic_and_returns_published_payload(self) -> None:
        vid = self.db.insert_policy_config_version(self.db.pc_id, 1, "draft", "2025-04-01")
        self.db.insert_policy_config_benefit_row(
            {
                "policy_config_version_id": vid,
                "benefit_key": "mobility_premium",
                "benefit_label": "Mobility premium",
                "category": "compensation_allowances",
                "covered": True,
                "value_type": "currency",
                "amount_value": 1000,
                "currency_code": "USD",
                "unit_frequency": "monthly",
                "cap_rule_json": {},
                "conditions_json": {},
                "assignment_types": [],
                "family_statuses": [],
                "targeting_signature": compute_targeting_signature([], []),
                "is_active": True,
                "display_order": 0,
            }
        )
        out = self.svc.publish_draft(self.db.company_id, policy_version_id=vid, created_by="u1")
        self.assertEqual(self.db.publish_atomic_calls, [vid])
        self.assertEqual(out.get("status"), "published")
        self.assertEqual(out.get("source"), "published")

    def test_ensure_draft_reuses_existing_without_second_version_insert(self) -> None:
        calls = {"n": 0}
        orig = self.db.insert_policy_config_version

        def wrapped(*a, **k):
            calls["n"] += 1
            return orig(*a, **k)

        self.db.insert_policy_config_version = wrapped  # type: ignore[method-assign]
        self.db.insert_policy_config_version(self.db.pc_id, 1, "draft", "2025-01-01")
        self.assertEqual(calls["n"], 1)
        self.svc.ensure_draft(self.db.company_id, created_by="u")
        self.assertEqual(calls["n"], 1)
        self.svc.ensure_draft(self.db.company_id, created_by="u")
        self.assertEqual(calls["n"], 1)

    def test_employee_grouped_payload_only_covered_applicable_rows(self) -> None:
        vid = self.db.insert_policy_config_version(self.db.pc_id, 1, "published", "2025-01-01")
        self.db.published_id = vid
        rows = [
            {
                "benefit_key": "global_row",
                "benefit_label": "G",
                "category": "compensation_allowances",
                "covered": True,
                "value_type": "none",
                "assignment_types": [],
                "family_statuses": [],
                "is_active": True,
            },
            {
                "benefit_key": "hidden",
                "benefit_label": "H",
                "category": "compensation_allowances",
                "covered": False,
                "value_type": "none",
                "assignment_types": [],
                "family_statuses": [],
                "is_active": True,
            },
            {
                "benefit_key": "lta_only",
                "benefit_label": "LTA",
                "category": "compensation_allowances",
                "covered": True,
                "value_type": "none",
                "assignment_types": ["long_term"],
                "family_statuses": [],
                "is_active": True,
            },
        ]
        for r in rows:
            self.db.insert_policy_config_benefit_row(
                {
                    "policy_config_version_id": vid,
                    **r,
                    "unit_frequency": "one_time",
                    "cap_rule_json": {},
                    "conditions_json": {},
                    "targeting_signature": compute_targeting_signature(r.get("assignment_types") or [], []),
                    "display_order": 0,
                }
            )
        payload = self.svc.employee_grouped_payload(
            self.db.company_id, assignment_type=None, family_status=None
        )
        self.assertTrue(payload.get("has_policy_config"))
        flat = []
        for c in payload.get("categories") or []:
            flat.extend(c.get("benefits") or [])
        keys = {b.get("benefit_key") for b in flat}
        self.assertIn("global_row", keys)
        self.assertNotIn("hidden", keys)
        self.assertNotIn("lta_only", keys)

    def test_caps_payload_normalizes_currency_cap(self) -> None:
        vid = self.db.insert_policy_config_version(self.db.pc_id, 1, "published", "2025-01-01")
        self.db.published_id = vid
        self.db.insert_policy_config_benefit_row(
            {
                "policy_config_version_id": vid,
                "benefit_key": "host_housing_cap",
                "benefit_label": "Housing",
                "category": "compensation_allowances",
                "covered": True,
                "value_type": "currency",
                "amount_value": 5000,
                "currency_code": "USD",
                "unit_frequency": "monthly",
                "cap_rule_json": {"cap_amount": 3000, "currency": "USD"},
                "conditions_json": {},
                "assignment_types": [],
                "family_statuses": [],
                "targeting_signature": "global",
                "is_active": True,
                "display_order": 0,
            }
        )
        cap = self.svc.caps_payload(self.db.company_id, assignment_type=None, family_status=None, benefit_keys=None)
        self.assertTrue(cap["metadata"].get("has_published_config"))
        self.assertTrue(any(c.get("benefit_key") == "host_housing_cap" for c in cap["caps"]))
        row = next(c for c in cap["caps"] if c.get("benefit_key") == "host_housing_cap")
        self.assertEqual(row.get("normalized_cap_type"), "currency_amount")
        self.assertEqual(row.get("normalized_amount"), 3000.0)

    def test_compare_provider_estimates_wires_through(self) -> None:
        vid = self.db.insert_policy_config_version(self.db.pc_id, 1, "published", "2025-01-01")
        self.db.published_id = vid
        self.db.insert_policy_config_benefit_row(
            {
                "policy_config_version_id": vid,
                "benefit_key": "movers",
                "benefit_label": "Movers",
                "category": "relocation_assistance",
                "covered": True,
                "value_type": "currency",
                "amount_value": 10000,
                "currency_code": "USD",
                "unit_frequency": "one_time",
                "cap_rule_json": {},
                "conditions_json": {},
                "assignment_types": [],
                "family_statuses": [],
                "targeting_signature": "global",
                "is_active": True,
                "display_order": 0,
            }
        )
        out = self.svc.compare_provider_estimates_to_published_caps(
            self.db.company_id,
            assignment_type=None,
            family_status=None,
            estimates=[{"benefit_key": "movers", "amount": 50, "currency": "USD"}],
        )
        self.assertIn("results", out)
        self.assertEqual(len(out["results"]), 1)
        self.assertTrue(out["results"][0].get("matched_cap"))


if __name__ == "__main__":
    unittest.main()
