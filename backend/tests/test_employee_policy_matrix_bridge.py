"""Matrix → employee package policy bridge (sync with Compensation & Allowance)."""
import os
import sys
from unittest.mock import MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.employee_policy_matrix_bridge import build_matrix_assignment_package
from services.policy_adapter import caps_from_resolved_benefits


def test_matrix_bridge_maps_currency_row_and_caps():
    db = MagicMock()
    db.list_policy_config_benefits.return_value = [
        {
            "benefit_key": "temporary_living",
            "benefit_label": "Temporary living",
            "covered": True,
            "value_type": "currency",
            "amount_value": 3000,
            "currency_code": "USD",
            "unit_frequency": "monthly",
            "is_active": True,
            "assignment_types": [],
            "family_statuses": [],
            "notes": None,
            "cap_rule_json": {},
            "conditions_json": {},
        }
    ]
    pub = {"id": "ver-1", "version_number": 1, "effective_date": "2026-03-24", "published_at": "2026-03-24T00:00:00"}
    resolved, precalc = build_matrix_assignment_package(
        db,
        company_id="co-1",
        pub_version=pub,
        assignment_type_ctx="LTA",
        family_status_ctx="single",
        company_name="Acme",
        assignment_id="asg-1",
        case_id="case-1",
    )
    assert resolved["has_policy"] is True
    assert resolved["benefits"][0]["benefit_key"] == "temporary_living"
    assert resolved["benefits"][0]["max_value"] == 3000
    budget = caps_from_resolved_benefits(resolved["benefits"])
    assert budget["caps"].get("housing") == 3000
    assert precalc["comparison_ready"] is True
