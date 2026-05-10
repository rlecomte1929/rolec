"""Tests for summary row -> canonical LTA template mapping and deduplication."""
from __future__ import annotations

from backend.services.policy_row_to_template_mapper import (
    map_and_deduplicate_row_candidates,
    map_single_row_candidate,
    normalize_row_text_for_dedup,
)
from backend.services.policy_summary_row_parser import (
    PolicyRowCandidate,
    summary_row_candidates_to_clause_dicts,
)


def _row(
    row_id: str,
    summary: str,
    *,
    label: str | None = None,
    section_ctx: str | None = None,
    section_ref: str | None = None,
) -> PolicyRowCandidate:
    return PolicyRowCandidate(
        row_id=row_id,
        source_document_id="doc-1",
        page_number=1,
        section_context=section_ctx,
        component_label=label,
        summary_text=summary,
        section_reference=section_ref,
    )


def test_grouped_relocation_amount_tiers_assignee_and_dependant():
    m = map_single_row_candidate(
        _row(
            "r1",
            "assignee 5000 / each dependant 1000",
            label="Relocation allowance",
            section_ref="4.2",
        )
    )
    assert m.primary_canonical_key == "relocation_allowance"
    assert m.draft_only_unresolved is False
    tiers = m.sub_values.get("amount_tiers") or []
    roles = {t["role"] for t in tiers}
    assert roles == {"assignee", "each_dependant"}
    assert m.comparison_readiness_hint == "ready"


def test_grouped_home_leave_variants():
    m = map_single_row_candidate(
        _row(
            "r1",
            "Home leave standard / split family / dependant in education / R&R",
            label="Home leave",
        )
    )
    assert m.primary_canonical_key == "home_leave"
    variants = m.sub_values.get("leave_variants") or []
    assert len(variants) >= 3
    assert any("split" in v.lower() for v in variants)
    assert m.coverage_status == "specified"
    assert m.comparison_readiness_hint == "ready"


def test_single_immigration_row_assignee_and_family():
    m = map_single_row_candidate(
        _row(
            "r1",
            "Work permits and visa processing for assignee and accompanying family members.",
            label="Immigration",
        )
    )
    assert m.primary_canonical_key == "work_permits_and_visas"
    assert "family" in m.applicability or "employee" in m.applicability
    assert m.comparison_readiness_hint == "ready"


def test_temporary_living_outbound_duration():
    m = map_single_row_candidate(
        _row(
            "r1",
            "Temporary living provided up to 30 days maximum.",
            label="Temporary living",
        )
    )
    assert m.primary_canonical_key == "temporary_living_outbound"
    assert m.quantification.get("duration_days") == 30
    assert m.comparison_readiness_hint == "ready"


def test_host_housing_external_cap_comparison_hint():
    m = map_single_row_candidate(
        _row(
            "r1",
            "Host housing benefit with capped level determined by third party data.",
            label="Host housing",
        )
    )
    assert m.primary_canonical_key == "host_housing"
    assert m.coverage_status == "capped_external"
    assert m.comparison_readiness_hint in ("external_reference", "not_ready")
    assert m.sub_values.get("cap_basis") == "external_or_third_party"


def test_ambiguous_row_is_draft_only_unresolved():
    m = map_single_row_candidate(
        _row(
            "r1",
            "Various internal procedures and local practices may apply as described elsewhere.",
            label="General",
        )
    )
    assert m.primary_canonical_key is None
    assert m.draft_only_unresolved is True
    assert m.comparison_readiness_hint == "draft_only"
    assert m.coverage_status == "ambiguous"


def test_dedup_same_key_source_ref_and_normalized_text():
    a = _row(
        "a",
        "Relocation allowance assignee 4000 each dependant 800",
        label="Relocation",
        section_ref="2.1",
    )
    b = _row(
        "b",
        "Relocation allowance assignee 4000 each dependant 800",
        label="Relocation",
        section_ref="2.1",
    )
    merged = map_and_deduplicate_row_candidates([a, b])
    assert len(merged) == 1
    assert set(merged[0].merged_source_row_ids) == {"a", "b"}


def test_dedup_distinct_section_ref_stays_separate():
    a = _row("a", "Home leave once per year", label="Leave", section_ref="1")
    b = _row("b", "Home leave once per year", label="Leave", section_ref="2")
    merged = map_and_deduplicate_row_candidates([a, b])
    assert len(merged) == 2


def test_summary_row_candidates_to_clause_dicts_includes_mapping():
    c = _row("x", "Visa support for employee and dependents", label="Visa", section_ref="3")
    clauses = summary_row_candidates_to_clause_dicts([c])
    assert len(clauses) == 1
    hints = clauses[0]["normalized_hint_json"]
    assert "canonical_lta_row_mapping" in hints
    m = hints["canonical_lta_row_mapping"]
    assert m["primary_canonical_key"] == "work_permits_and_visas"


def test_child_education_difference_logic_grouped_in_mapping():
    m = map_single_row_candidate(
        _row(
            "r1",
            "Tuition difference reimbursement for dependent children where eligible.",
            label="Child education",
        )
    )
    assert m.primary_canonical_key == "child_education"
    assert m.sub_values.get("reimbursement_logic") == "difference_only"


def test_normalize_row_text_for_dedup_collapses_whitespace():
    assert normalize_row_text_for_dedup("  A  |  B  ", "X") == normalize_row_text_for_dedup(
        "a b", "x"
    )
