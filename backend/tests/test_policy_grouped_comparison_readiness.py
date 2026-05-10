"""Grouped policy item comparison readiness classification."""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_grouped_comparison_readiness import (
    READINESS_COMPARISON_READY,
    READINESS_EXTERNAL_REFERENCE_PARTIAL,
    READINESS_INFORMATIONAL_ONLY,
    classify_grouped_item_readiness,
    enrich_grouped_items_with_readiness,
    build_comparison_engine_grouped_readiness_payload,
)


def _base_item(**overrides):
    base = {
        "grouped_item_id": "gpi-test",
        "canonical_key": "relocation_allowance",
        "comparison_readiness_hint": "ready",
        "coverage_status": "mentioned",
        "summary": "",
        "explicit_numeric_cap": False,
        "draft_only_unresolved": False,
        "grouped_values": {},
    }
    base.update(overrides)
    return base


def test_visa_support_no_amount_is_informational():
    item = _base_item(
        canonical_key="work_permits_and_visas",
        summary="The company provides support for work permits and visa processing.",
        comparison_readiness_hint="external_reference",
    )
    r = classify_grouped_item_readiness(item, [])
    assert r["comparison_readiness"] == READINESS_INFORMATIONAL_ONLY
    assert r["value_type"] == "narrative"


def test_relocation_allowance_with_explicit_amount_and_currency_is_comparison_ready():
    item = _base_item(
        canonical_key="relocation_allowance",
        summary="One-time relocation allowance of USD 12,000.",
        explicit_numeric_cap=True,
    )
    drafts = [{"amount_fragments": {"currency": "USD"}}]
    r = classify_grouped_item_readiness(item, drafts)
    assert r["comparison_readiness"] == READINESS_COMPARISON_READY
    assert r["value_type"] == "amount"
    assert r["coverage_status"] == "specified"


def test_home_leave_external_policy_dependency_is_partial():
    item = _base_item(
        canonical_key="home_leave",
        summary="Home leave flights as per the global travel policy.",
        comparison_readiness_hint="ready",
    )
    r = classify_grouped_item_readiness(item, [])
    assert r["comparison_readiness"] == READINESS_EXTERNAL_REFERENCE_PARTIAL
    assert "travel policy" in r["reason"].lower() or "external" in r["reason"].lower()


def test_host_housing_external_cap_is_partial_with_capped_external():
    item = _base_item(
        canonical_key="host_housing",
        summary="Housing capped per third-party benchmark.",
        grouped_values={"cap_basis": "external_or_third_party"},
    )
    r = classify_grouped_item_readiness(item, [])
    assert r["comparison_readiness"] == READINESS_EXTERNAL_REFERENCE_PARTIAL
    assert r["coverage_status"] == "capped_external"
    assert r["value_type"] == "external_reference"


def test_compensation_approach_informational_row():
    item = _base_item(
        canonical_key="policy_definitions_and_exceptions",
        summary="Compensation follows host approach with COLA review.",
    )
    r = classify_grouped_item_readiness(item, [])
    assert r["comparison_readiness"] == READINESS_INFORMATIONAL_ONLY
    assert r["value_type"] == "narrative"


def test_enrich_and_comparison_engine_payload_shape():
    cluster_id = "gpi-abc123def4567890123"
    grouped = [
        {
            "grouped_item_id": cluster_id,
            "canonical_key": "relocation_allowance",
            "taxonomy_service_key": "relocation_allowance",
            "comparison_readiness_hint": "ready",
            "coverage_status": "mentioned",
            "summary": "EUR 8000 lump sum",
            "explicit_numeric_cap": True,
            "draft_only_unresolved": False,
            "grouped_values": {},
        }
    ]
    by_id = {cluster_id: [{"amount_fragments": {"currency": "EUR"}}]}
    enrich_grouped_items_with_readiness(grouped, by_id)
    assert grouped[0].get("readiness", {}).get("comparison_readiness") == READINESS_COMPARISON_READY
    payload = build_comparison_engine_grouped_readiness_payload(grouped)
    assert len(payload) == 1
    assert payload[0]["grouped_item_id"] == cluster_id
    assert payload[0]["canonical_key"] == "relocation_allowance"
    assert payload[0]["readiness"]["value_type"] == "amount"
