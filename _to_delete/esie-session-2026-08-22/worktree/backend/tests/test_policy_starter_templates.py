"""Starter policy templates: init service, entitlements metadata, comparison readiness, duplicate guard."""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from typing import Any, Dict, List, Optional

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.policy_company_policy_template_init import (  # noqa: E402
    StarterPolicyTemplateInitError,
    initialize_company_policy_from_starter_template,
)
from backend.app.services.policy_rule_comparison_readiness import (  # noqa: E402
    RULE_COMPARISON_FULL,
    evaluate_policy_comparison_readiness,
    evaluate_rule_comparison_readiness,
)
from backend.app.services.policy_starter_templates import (  # noqa: E402
    build_starter_template_benefit_rows,
)
from backend.app.services.policy_template_service import PolicyTemplateService  # noqa: E402
from backend.app.services.policy_entitlement_model import (  # noqa: E402
    CANONICAL_SERVICE_TO_LEGACY_BENEFIT_KEY,
)


class _FakeTemplateInitDB:
    """Minimal DB surface for initialize_company_policy_from_starter_template."""

    def __init__(self) -> None:
        self.policies_by_company: Dict[str, List[Dict[str, Any]]] = {}
        self.policy_by_id: Dict[str, Dict[str, Any]] = {}
        self.versions: List[Dict[str, Any]] = []
        self.benefits_by_vid: Dict[str, List[Dict[str, Any]]] = {}
        self.assignment_apps: List[Dict[str, Any]] = []
        self.normalization_drafts: Dict[str, Dict[str, Any]] = {}

    def list_company_policies(self, company_id: str) -> List[Dict[str, Any]]:
        return list(self.policies_by_company.get(company_id, []))

    def create_company_policy(self, **kwargs: Any) -> None:
        pid = str(kwargs["policy_id"])
        row = dict(kwargs)
        row.setdefault("extraction_status", "pending")
        self.policy_by_id[pid] = row
        cid = str(kwargs["company_id"])
        self.policies_by_company.setdefault(cid, []).append(row)

    def update_company_policy_status(
        self, policy_id: str, status: str, extracted_at: Optional[str] = None
    ) -> None:
        if policy_id in self.policy_by_id:
            self.policy_by_id[policy_id]["extraction_status"] = status
            self.policy_by_id[policy_id]["extracted_at"] = extracted_at

    def create_policy_version(
        self,
        version_id: str,
        policy_id: str,
        source_policy_document_id: Optional[str] = None,
        version_number: int = 1,
        status: str = "draft",
        auto_generated: bool = True,
        review_status: str = "pending",
        confidence: Optional[float] = None,
        created_by: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        self.versions.append(
            {
                "id": version_id,
                "policy_id": policy_id,
                "source_policy_document_id": source_policy_document_id,
                "version_number": version_number,
                "status": status,
                "auto_generated": auto_generated,
                "review_status": review_status,
                "confidence": confidence,
            }
        )

    def insert_policy_benefit_rule(self, rule: Dict[str, Any]) -> str:
        rid = str(uuid.uuid4())
        vid = str(rule["policy_version_id"])
        self.benefits_by_vid.setdefault(vid, []).append({**rule, "id": rid})
        return rid

    def insert_policy_assignment_applicability(self, app: Dict[str, Any]) -> str:
        self.assignment_apps.append(dict(app))
        return str(uuid.uuid4())

    def update_policy_version_normalization_draft(
        self, version_id: str, draft: Dict[str, Any], *, request_id: Optional[str] = None
    ) -> None:
        self.normalization_drafts[str(version_id)] = draft

    def list_policy_benefit_rules(self, policy_version_id: str) -> List[Dict[str, Any]]:
        return list(self.benefits_by_vid.get(policy_version_id, []))


class StarterTemplateTests(unittest.TestCase):
    def test_initialize_from_template_creates_draft_and_five_rules(self) -> None:
        company_id = str(uuid.uuid4())
        db = _FakeTemplateInitDB()
        out = initialize_company_policy_from_starter_template(
            db,
            company_id=company_id,
            template_key="standard",
            comparison_ready_structure=True,
            created_by="hr-1",
        )
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("version_status"), "draft")
        self.assertEqual(out.get("benefit_rules_created"), 5)
        vid = out.get("policy_version_id")
        assert isinstance(vid, str)
        rules = db.list_policy_benefit_rules(vid)
        self.assertEqual(len(rules), 5)
        self.assertEqual(len(db.assignment_apps), 10)
        self.assertIn(vid, db.normalization_drafts)
        nd = db.normalization_drafts[vid]
        self.assertEqual(nd.get("schema_version"), 1)

    def test_duplicate_init_guard(self) -> None:
        company_id = str(uuid.uuid4())
        db = _FakeTemplateInitDB()
        initialize_company_policy_from_starter_template(
            db, company_id=company_id, template_key="conservative"
        )
        with self.assertRaises(StarterPolicyTemplateInitError) as ctx:
            initialize_company_policy_from_starter_template(
                db, company_id=company_id, template_key="premium"
            )
        self.assertEqual(ctx.exception.code, "POLICY_ALREADY_EXISTS")

    def test_entitlement_metadata_on_rules(self) -> None:
        company_id = str(uuid.uuid4())
        db = _FakeTemplateInitDB()
        out = initialize_company_policy_from_starter_template(
            db, company_id=company_id, template_key="premium"
        )
        vid = str(out["policy_version_id"])
        for r in db.list_policy_benefit_rules(vid):
            meta = r.get("metadata_json") or {}
            ce = meta.get("canonical_entitlement") or {}
            self.assertTrue(ce.get("service_key"))
            self.assertTrue(ce.get("category"))
            self.assertEqual(ce.get("coverage_status"), "included")
            self.assertIn("employee_visible_value", ce)
            self.assertIn("comparison_readiness", ce)
            self.assertTrue(meta.get("template_baseline"))
            self.assertTrue(meta.get("not_company_approved_until_published"))

    def test_comparison_engine_with_template_backed_rules(self) -> None:
        rows = build_starter_template_benefit_rows(
            "standard",
            policy_version_id="vid-test",
            comparison_ready_structure=True,
        )
        br = [{k: v for k, v in r.items() if k != "policy_version_id"} for r in rows]
        normalized: Dict[str, Any] = {"benefit_rules": br, "exclusions": []}
        pol = evaluate_policy_comparison_readiness(normalized=normalized)
        self.assertIn(pol.get("policy_level"), ("full", "partial"))
        for r in br:
            rr = evaluate_rule_comparison_readiness(r)
            self.assertIn(rr.get("level"), (RULE_COMPARISON_FULL, "partial", "not_ready"))

    def test_narrative_template_comparison_partial(self) -> None:
        rows = build_starter_template_benefit_rows(
            "standard",
            policy_version_id="vid-test",
            comparison_ready_structure=False,
        )
        br = [{k: v for k, v in r.items() if k != "policy_version_id"} for r in rows]
        pol = evaluate_policy_comparison_readiness(normalized={"benefit_rules": br, "exclusions": []})
        self.assertNotEqual(pol.get("policy_level"), "full")


# [TPL-1/AIQ-1131] Golden values — the EXACT per-service caps the retired
# _TIER_CAPS dict held. PolicyTemplateService.get_starter_template_caps() must
# return these verbatim, and the produced benefit rows must carry them unchanged.
_GOLDEN_STARTER_CAPS = {
    "conservative": {
        "visa_support": 2500, "temporary_housing": 3500, "home_search": 1500,
        "school_search": 8000, "household_goods_shipment": 5000,
    },
    "standard": {
        "visa_support": 4000, "temporary_housing": 5500, "home_search": 2500,
        "school_search": 15000, "household_goods_shipment": 10000,
    },
    "premium": {
        "visa_support": 6500, "temporary_housing": 8500, "home_search": 4000,
        "school_search": 25000, "household_goods_shipment": 18000,
    },
}


class StarterTemplateCapsGoldenTests(unittest.TestCase):
    """TPL-1: the verbatim _TIER_CAPS → PolicyTemplateService port is byte-identical."""

    def test_service_caps_returned_verbatim(self):
        self.assertEqual(PolicyTemplateService.get_starter_template_caps(), _GOLDEN_STARTER_CAPS)

    def test_home_search_cap_present(self):
        # The trap: the service's _LTA_TIER_DEFAULTS is keyed by benefit-taxonomy and
        # has NO home_search. The starter caps MUST keep it (1500/2500/4000).
        caps = PolicyTemplateService.get_starter_template_caps()
        self.assertEqual(caps["conservative"]["home_search"], 1500)
        self.assertEqual(caps["standard"]["home_search"], 2500)
        self.assertEqual(caps["premium"]["home_search"], 4000)

    def test_built_rows_carry_exact_caps(self):
        for tier, expected in _GOLDEN_STARTER_CAPS.items():
            rows = build_starter_template_benefit_rows(
                tier, policy_version_id="v-golden", comparison_ready_structure=True
            )
            by_bk = {r["benefit_key"]: r["amount_value"] for r in rows}
            for service, cap in expected.items():
                bk = CANONICAL_SERVICE_TO_LEGACY_BENEFIT_KEY[service]
                self.assertEqual(
                    by_bk.get(bk), float(cap),
                    f"{tier}/{service} ({bk}) cap drifted: {by_bk.get(bk)} != {float(cap)}",
                )

    def test_returns_fresh_copy(self):
        a = PolicyTemplateService.get_starter_template_caps()
        a["standard"]["home_search"] = 999
        self.assertEqual(PolicyTemplateService.get_starter_template_caps()["standard"]["home_search"], 2500)


if __name__ == "__main__":
    unittest.main()
