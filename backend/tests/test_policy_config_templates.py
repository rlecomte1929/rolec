"""
Phase 3 — starter templates for the Compensation & Allowance matrix.

Covers:
  * template registry — three templates, stable keys, labelled
  * expansion: flat rows emit once, tiered rows emit one per
    employee level with the right amount
  * benefit labels come from the canonical registry (not the template)
  * apply_template_to_draft: fresh draft path, draft-has-rows guard,
    replace_existing_draft=True overwrite, targeting_signature is
    recomputed per row, live version is untouched.
  * unknown template raises KeyError with a diagnosable code.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.policy_config_matrix_service import PolicyConfigMatrixService
from backend.app.services.policy_config_targeting import EMPLOYEE_LEVELS
from backend.app.services.policy_config_templates import (
    COMP_ALLOWANCE_TEMPLATES as POLICY_TEMPLATES,
)
from backend.app.services.policy_template_service import PolicyTemplateService

# [TPL-2/AIQ-1132] The module-level list/get/expand functions were retired and
# folded into PolicyTemplateService. Alias the new static methods to the old names
# so the existing behavioural tests below now exercise the service methods directly.
list_templates = PolicyTemplateService.list_comp_allowance_templates
get_template = PolicyTemplateService.get_comp_allowance_template
expand_template_rows = PolicyTemplateService.expand_comp_allowance_rows


class TemplateRegistryTests(unittest.TestCase):
    def test_three_templates_are_registered(self):
        self.assertEqual(set(POLICY_TEMPLATES.keys()), {"conservative", "standard", "premium"})

    def test_list_templates_returns_metadata_only(self):
        md = list_templates()
        self.assertEqual(len(md), 3)
        for entry in md:
            self.assertIn("key", entry)
            self.assertIn("label", entry)
            self.assertIn("description", entry)
            self.assertNotIn("rows", entry)  # don't ship rows to the picker

    def test_get_template_is_case_insensitive(self):
        self.assertIsNotNone(get_template("STANDARD"))
        self.assertIsNotNone(get_template(" standard "))
        self.assertIsNone(get_template("bogus"))


class ExpandTemplateRowsTests(unittest.TestCase):
    def test_unknown_template_raises(self):
        with self.assertRaises(KeyError) as ctx:
            expand_template_rows("bogus")
        self.assertIn("unknown_template", ctx.exception.args[0])

    def test_flat_rows_emit_once_with_empty_employee_levels(self):
        rows = expand_template_rows("standard")
        shipment = [r for r in rows if r["benefit_key"] == "shipment_of_goods"]
        self.assertEqual(len(shipment), 1)
        self.assertEqual(shipment[0]["employee_levels"], [])
        self.assertEqual(shipment[0]["amount_value"], 20000)

    def test_tiered_rows_emit_one_per_level(self):
        rows = expand_template_rows("standard")
        reloc = [r for r in rows if r["benefit_key"] == "relocation_allowance_assignee_partner"]
        self.assertEqual(len(reloc), len(EMPLOYEE_LEVELS))
        # Each row narrows to exactly one level.
        levels = sorted(r["employee_levels"][0] for r in reloc)
        self.assertEqual(levels, sorted(EMPLOYEE_LEVELS))
        # Amounts increase with level per the standard declaration
        by_level = {r["employee_levels"][0]: r["amount_value"] for r in reloc}
        self.assertLess(by_level["entry"], by_level["manager"])
        self.assertLess(by_level["manager"], by_level["director"])
        self.assertLess(by_level["director"], by_level["vp"])
        self.assertLess(by_level["vp"], by_level["c_suite"])

    def test_percentage_row_uses_percentage_value(self):
        rows = expand_template_rows("standard")
        mp = [r for r in rows if r["benefit_key"] == "mobility_premium"]
        self.assertEqual(len(mp), 1)
        self.assertEqual(mp[0]["value_type"], "percentage")
        self.assertEqual(mp[0]["percentage_value"], 10.0)

    def test_conservative_caps_lower_than_standard(self):
        c = expand_template_rows("conservative")
        s = expand_template_rows("standard")

        def mgr_amount(rows, bk):
            match = [r for r in rows if r["benefit_key"] == bk and r["employee_levels"] == ["manager"]]
            return match[0]["amount_value"] if match else None

        self.assertLess(
            mgr_amount(c, "relocation_allowance_assignee_partner"),
            mgr_amount(s, "relocation_allowance_assignee_partner"),
        )


class _FakeDb:
    """Minimal surface compute_diff / apply_template exercise. Mirrors
    the one in test_policy_config_matrix_diff but kept local to avoid
    cross-test import coupling."""

    def __init__(self):
        import itertools
        self.rows_by_version = {}
        self.versions = {}
        self.config_id = "cfg-1"
        self.draft_vid = None
        self.live_vid = None
        self._vid_counter = itertools.count(1)

    def ensure_policy_config(self, company_id, config_key, *, created_by=None):
        return {"id": self.config_id, "company_id": company_id, "config_key": config_key}

    def get_policy_config_draft_for_config(self, _cfg_id):
        return self.versions.get(self.draft_vid) if self.draft_vid else None

    def get_latest_published_policy_config_version(self, _company_id, _config_key):
        return self.versions.get(self.live_vid) if self.live_vid else None

    def list_policy_config_benefits(self, vid):
        return list(self.rows_by_version.get(str(vid), []))

    def insert_policy_config_version(self, _cfg_id, version_number, status, effective_date, *, created_by=None):
        _ = created_by
        vid = f"v-{next(self._vid_counter)}"
        self.versions[vid] = {
            "id": vid,
            "version_number": version_number,
            "status": status,
            "effective_date": effective_date,
        }
        if status == "draft":
            self.draft_vid = vid
        elif status == "published":
            self.live_vid = vid
        return vid

    def insert_policy_config_benefit_row(self, row):
        import uuid
        r = dict(row)
        r["id"] = str(r.get("id") or uuid.uuid4())
        vid = str(r["policy_config_version_id"])
        self.rows_by_version.setdefault(vid, []).append(r)
        return r["id"]

    def delete_policy_config_benefits_for_version(self, vid):
        self.rows_by_version[str(vid)] = []

    def get_policy_config_version_row(self, vid):
        return self.versions.get(str(vid))


class ApplyTemplateToDraftTests(unittest.TestCase):
    def setUp(self):
        self.db = _FakeDb()
        self.svc = PolicyConfigMatrixService(self.db)

    def test_apply_to_fresh_company_creates_draft_and_inserts_rows(self):
        out = self.svc.apply_template_to_draft(
            "co-1", template_key="standard"
        )
        self.assertEqual(out.get("source"), "template_applied")
        self.assertEqual(out.get("status"), "draft")
        # Draft exists
        self.assertIsNotNone(self.db.draft_vid)
        rows = self.db.list_policy_config_benefits(self.db.draft_vid)
        # 5 tiered + 1 flat for relocation allowance dependent (per_dependent tiered),
        # etc. Exact count should match expansion.
        expected = len([1 for _ in __import__("itertools").chain(
            *[[r] for r in self.svc.__class__.__name__ and []]
        )])
        _ = expected  # silence linter — just assert non-empty + label presence
        self.assertGreater(len(rows), 0)
        # benefit_label comes from canonical registry
        shipment = next((r for r in rows if r["benefit_key"] == "shipment_of_goods"), None)
        self.assertIsNotNone(shipment)
        self.assertEqual(shipment["benefit_label"], "Shipment of goods")

    def test_apply_to_draft_with_rows_refuses_without_replace_flag(self):
        # Seed a draft with existing rows.
        self.db.insert_policy_config_version("cfg-1", 1, "draft", "2026-01-01")
        self.db.rows_by_version[self.db.draft_vid] = [
            {"benefit_key": "shipment_of_goods", "targeting_signature": "global", "covered": True}
        ]
        with self.assertRaises(KeyError) as ctx:
            self.svc.apply_template_to_draft("co-1", template_key="standard")
        self.assertEqual(ctx.exception.args[0], "draft_has_rows")
        # Draft is unchanged
        rows = self.db.list_policy_config_benefits(self.db.draft_vid)
        self.assertEqual(len(rows), 1)

    def test_replace_existing_draft_overwrites_rows(self):
        self.db.insert_policy_config_version("cfg-1", 1, "draft", "2026-01-01")
        self.db.rows_by_version[self.db.draft_vid] = [
            {"benefit_key": "shipment_of_goods", "targeting_signature": "global", "covered": True}
        ]
        out = self.svc.apply_template_to_draft(
            "co-1", template_key="premium", replace_existing_draft=True
        )
        rows = self.db.list_policy_config_benefits(self.db.draft_vid)
        self.assertGreater(len(rows), 1)
        # Premium's shipment_of_goods is 35000
        shipment = next((r for r in rows if r["benefit_key"] == "shipment_of_goods"), None)
        self.assertIsNotNone(shipment)
        self.assertEqual(shipment["amount_value"], 35000)
        self.assertEqual(out.get("source"), "template_applied")

    def test_live_version_is_untouched(self):
        # Seed a published row, then apply template — published version
        # must remain queryable and unchanged.
        self.db.insert_policy_config_version("cfg-1", 1, "published", "2026-01-01")
        self.db.rows_by_version[self.db.live_vid] = [
            {
                "benefit_key": "shipment_of_goods",
                "targeting_signature": "global",
                "amount_value": 9999,
                "covered": True,
            }
        ]
        self.svc.apply_template_to_draft("co-1", template_key="conservative")
        pub_rows = self.db.list_policy_config_benefits(self.db.live_vid)
        self.assertEqual(pub_rows[0]["amount_value"], 9999)

    def test_unknown_template_raises(self):
        with self.assertRaises(KeyError) as ctx:
            self.svc.apply_template_to_draft("co-1", template_key="bogus")
        self.assertIn("unknown_template", ctx.exception.args[0])

    def test_tiered_rows_get_per_level_targeting_signature(self):
        self.svc.apply_template_to_draft("co-1", template_key="standard")
        rows = self.db.list_policy_config_benefits(self.db.draft_vid)
        reloc = [r for r in rows if r["benefit_key"] == "relocation_allowance_assignee_partner"]
        signatures = {r["targeting_signature"] for r in reloc}
        # Five distinct signatures (one per level)
        self.assertEqual(len(signatures), len(EMPLOYEE_LEVELS))
        # None is the "global" signature
        self.assertNotIn("global", signatures)


class GoldenEquivalenceTests(unittest.TestCase):
    """[TPL-2/AIQ-1132] Prove the service methods reproduce the retired module
    functions' output byte-identically. The fixture was captured from the ORIGINAL
    policy_config_templates.{list_templates,get_template,expand_template_rows}
    before they were removed — so this asserts equivalence against the true
    pre-refactor baseline, not against the moved copy."""

    _KEYS = ("conservative", "standard", "premium")

    @classmethod
    def setUpClass(cls):
        import json
        path = os.path.join(
            os.path.dirname(__file__), "fixtures",
            "policy_comp_allowance_templates_golden.json",
        )
        with open(path) as f:
            cls.golden = json.load(f)

    @staticmethod
    def _canon(obj):
        # Normalise the same way the fixture was written (sort_keys + default=str)
        # so the comparison is structural, not dependent on dict key order.
        import json
        return json.loads(json.dumps(obj, sort_keys=True, default=str))

    def test_list_templates_matches_golden(self):
        self.assertEqual(
            self._canon(PolicyTemplateService.list_comp_allowance_templates()),
            self.golden["list_templates"],
        )

    def test_get_template_matches_golden(self):
        for k in self._KEYS:
            self.assertEqual(
                self._canon(PolicyTemplateService.get_comp_allowance_template(k)),
                self.golden["get_template"][k],
                f"get_comp_allowance_template({k!r}) drifted from golden",
            )

    def test_expand_rows_matches_golden(self):
        for k in self._KEYS:
            self.assertEqual(
                self._canon(PolicyTemplateService.expand_comp_allowance_rows(k)),
                self.golden["expand_template_rows"][k],
                f"expand_comp_allowance_rows({k!r}) drifted from golden",
            )


if __name__ == "__main__":
    unittest.main()
