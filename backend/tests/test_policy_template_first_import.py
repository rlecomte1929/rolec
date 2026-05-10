"""Template-first import: canonical LTA skeleton + import summary."""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_summary_row_parser import (
    PolicyRowCandidate,
    summary_row_candidates_to_clause_dicts,
)
from backend.services.policy_template_first_import import build_template_first_import_payload


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


def test_summary_partially_populates_template_rest_empty_unmapped():
    candidates = [
        _row(
            "r1",
            "Relocation lump sum USD 10,000 for employee.",
            label="Relocation allowance",
            section_ref="5.1",
        ),
        _row(
            "r2",
            "Temporary living up to 45 days in host location.",
            label="Temporary living",
            section_ref="5.2",
        ),
    ]
    clauses = summary_row_candidates_to_clause_dicts(candidates)
    payload = build_template_first_import_payload(clauses, [], grouped_policy_items_count=2)

    assert payload["mode"] == "canonical_lta_template_first"
    summary = payload["import_summary"]
    assert summary["mapped_items_count"] == 2
    assert summary["grouped_items_count"] == 2
    assert summary["unmapped_rows_count"] == 0
    assert summary["template_field_count"] == len(payload["template_items"])

    by_key = {it["canonical_key"]: it for it in payload["template_items"]}
    assert by_key["relocation_allowance"]["import_status"] == "mapped"
    assert by_key["relocation_allowance"]["coverage_status"] in ("specified", "mentioned")
    assert by_key["temporary_living_outbound"]["import_status"] == "mapped"
    assert by_key["temporary_living_outbound"]["quantification"].get("duration_days") == 45

    assert by_key["eligibility_and_assignment_scope"]["import_status"] == "unmapped"
    assert by_key["eligibility_and_assignment_scope"]["sub_values"] == {}
    assert by_key["eligibility_and_assignment_scope"]["coverage_status"] is None


def test_unmapped_template_fields_stay_empty_with_review_flag():
    candidates = [
        _row("r1", "One-off mobility payment USD 5000", label="Allowance", section_ref="1"),
    ]
    clauses = summary_row_candidates_to_clause_dicts(candidates)
    payload = build_template_first_import_payload(clauses, [], grouped_policy_items_count=1)
    host = next(it for it in payload["template_items"] if it["canonical_key"] == "host_housing")
    assert host["import_status"] == "unmapped"
    assert host["sub_values"] == {}
    assert host["review_needed"] is True


def test_duplicate_fragments_increase_duplicate_merge_count():
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
    clauses = summary_row_candidates_to_clause_dicts([a, b])
    payload = build_template_first_import_payload(clauses, [], grouped_policy_items_count=1)
    assert payload["import_summary"]["mapped_items_count"] == 1
    assert payload["import_summary"]["duplicate_rows_merged_count"] >= 1
    rel = next(it for it in payload["template_items"] if it["canonical_key"] == "relocation_allowance")
    assert set(rel["merged_source_row_ids"]) == {"a", "b"}


def test_external_reference_host_housing_flagged():
    candidates = [
        _row(
            "r1",
            "Host housing benefit capped per third party benchmark data.",
            label="Host housing",
            section_ref="6",
        ),
    ]
    clauses = summary_row_candidates_to_clause_dicts(candidates)
    payload = build_template_first_import_payload(clauses, [], grouped_policy_items_count=1)
    host = next(it for it in payload["template_items"] if it["canonical_key"] == "host_housing")
    assert host["import_status"] == "mapped"
    assert host["external_reference_flag"] is True
    assert host["comparison_readiness_hint"] in ("external_reference", "not_ready")
    assert host["review_needed"] is True


def test_draft_only_row_not_mapped_to_template_slot():
    candidates = [
        _row(
            "r1",
            "Various internal procedures may apply as described elsewhere.",
            label="General",
            section_ref="99",
        ),
    ]
    clauses = summary_row_candidates_to_clause_dicts(candidates)
    payload = build_template_first_import_payload(clauses, [], grouped_policy_items_count=0)
    assert payload["import_summary"]["unmapped_rows_count"] == 1
    assert len(payload["draft_only_import_rows"]) == 1
    assert payload["draft_only_import_rows"][0]["reason"] == "draft_only_unresolved"
    assert payload["import_summary"]["mapped_items_count"] == 0
