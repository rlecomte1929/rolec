"""
[Bridge 2/4] Regression tests for resolving config-matrix policies in the
benefit comparison.

Covers the three edits that wire the (previously unwired) config-matrix subsystem
into the comparison so an employee whose HR published only via "Matrix v1" stops
seeing "No published policy":
  1. resolve_policy_for_assignment falls back to the matrix bridge when there is
     no legacy company_policies/policy_versions policy.
  2. compute_policy_service_comparison consumes the matrix package's inline
     benefits + precomputed readiness (no policy_version_id / DB benefit re-query).
  3. matrix benefits are aliased onto the legacy benefit_key vocabulary so the
     per-service cap lookups actually match (caps render, not out_of_scope).
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import policy_resolution as pr
from backend.app.services import policy_service_comparison as psc
from backend.app.services import employee_policy_matrix_bridge as bridge


def _matrix_benefit_row():
    # Mirror the shape build_matrix_assignment_package consumes
    # (see tests/test_employee_policy_matrix_bridge.py), keyed by the config
    # vocabulary (temporary_living, not temporary_housing).
    return {
        "benefit_key": "temporary_living",
        "benefit_label": "Temporary living",
        "covered": True,
        "value_type": "currency",
        "amount_value": 3000,
        "currency_code": "EUR",
        "unit_frequency": "monthly",
        "is_active": True,
        "assignment_types": [],
        "family_statuses": [],
        "notes": None,
        "cap_rule_json": {},
        "conditions_json": {},
    }


def test_resolve_falls_back_to_matrix_when_no_legacy_policy():
    db = MagicMock()
    db.list_policy_config_benefits.return_value = [_matrix_benefit_row()]
    assignment = {"id": "a1", "case_id": "c1"}

    # find_published_matrix_version / build_matrix_assignment_package are imported
    # locally inside resolve_policy_for_assignment, so patch them on the bridge
    # module (their definition site). build_matrix_assignment_package stays real.
    with patch.object(pr, "find_first_published_company_policy", return_value=None), \
        patch.object(
            bridge, "find_published_matrix_version",
            return_value=("c0000000-0000-0000-0000-000000000001", {"id": "ver-1", "version_number": 1}),
        ), \
        patch.object(
            pr, "collect_company_id_candidates_for_assignment",
            return_value=["c0000000-0000-0000-0000-000000000001"],
        ):
        resolved = pr.resolve_policy_for_assignment(db, "a1", assignment, None, None, None)

    assert resolved is not None
    assert (resolved.get("resolution_context") or {}).get("source") == "policy_config_matrix"
    assert len(resolved.get("benefits") or []) >= 1
    assert "comparison_readiness_precalc" in resolved


def test_resolve_threads_normalized_employee_level_not_raw_tier():
    # The employee_level targeting axis must receive ctx["employee_level"] (the
    # normalized canonical slug, derived from tier OR seniorityBand OR ...), not
    # ctx["tier"]. Here the profile carries only a seniorityBand (no tier), so the
    # old tier-only wiring would pass None and every level-narrowed cap would be
    # filtered out.
    db = MagicMock()
    captured = {}

    def _fake_build(_db, **kwargs):
        captured.update(kwargs)
        return ({"resolution_context": {"source": "policy_config_matrix"}, "benefits": []}, {})

    assignment = {"id": "a1", "case_id": "c1"}
    profile = {"primaryApplicant": {"employer": {"seniorityBand": "manager"}}}

    with patch.object(pr, "find_first_published_company_policy", return_value=None), \
        patch.object(bridge, "find_published_matrix_version", return_value=("co-1", {"id": "ver-1"})), \
        patch.object(bridge, "build_matrix_assignment_package", side_effect=_fake_build), \
        patch.object(pr, "collect_company_id_candidates_for_assignment", return_value=["co-1"]):
        pr.resolve_policy_for_assignment(db, "a1", assignment, None, profile, None)

    assert captured.get("employee_level_ctx") is not None, \
        "employee_level must thread from seniorityBand; got None (raw-tier regression)"


def _matrix_resolved_package():
    return {
        "id": "policy_config_matrix:ver-1",
        "policy_id": "policy_config_matrix:ver-1",
        "policy": {"id": "policy_config_matrix:ver-1"},
        "benefits": [
            {
                "benefit_key": "temporary_living",  # config vocabulary
                "covered": True,
                "value_type": "currency",
                "min_value": 1000,
                "standard_value": 3000,
                "max_value": 5000,
                "currency": "EUR",
                "approval_required": False,
            }
        ],
        "resolution_context": {"source": "policy_config_matrix"},
        "comparison_readiness_precalc": {"comparison_ready": True},
    }


def test_comparison_renders_caps_for_matrix_policy():
    db = MagicMock()
    db.get_resolved_assignment_policy.return_value = _matrix_resolved_package()
    db.coalesce_case_lookup_id.return_value = "c1"
    # Employee selected a housing service; "housing" maps to legacy key temporary_housing.
    db.list_case_services.return_value = [
        {"category": "housing", "selected": True, "estimated_cost": 2000, "currency": "EUR"}
    ]
    db.list_case_service_answers.return_value = []

    out = psc.compute_policy_service_comparison(
        db, "a1", assignment={"id": "a1", "case_id": "c1"}, employee_gate=True
    )

    assert out["comparison_available"] is True
    assert len(out["comparisons"]) >= 1

    housing = next((c for c in out["comparisons"] if c["service_category"] == "housing"), None)
    assert housing is not None
    # The alias (temporary_living -> temporary_housing) must make the cap match,
    # otherwise the row falls to out_of_scope with no policy cap.
    assert housing["benefit_key"] == "temporary_housing"
    assert housing.get("policy_max_value") == 5000
    assert housing.get("currency") == "EUR"


def test_alias_map_only_adds_legacy_keys_and_keeps_originals():
    benefits = [{"benefit_key": "temporary_living", "max_value": 5000}]
    out = psc._with_legacy_benefit_key_aliases(benefits)
    keys = [b["benefit_key"] for b in out]
    assert "temporary_living" in keys  # original kept (config-keyed consumers still work)
    assert "temporary_housing" in keys  # legacy alias added
