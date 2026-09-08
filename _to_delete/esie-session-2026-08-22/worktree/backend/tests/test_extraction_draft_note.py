"""AIQ-938-FU — the import-extraction bridge must carry the source_quote
citation (and free-text eligibility/limits) into the config-matrix draft notes,
so the HR review UI surfaces what text each extracted value came from.

policy_config_benefits has no dedicated citation column, so the citation rides
in `notes`. This unit-tests the pure note builder (no DB).
"""
from backend.app.services.policy_config_matrix_service import _extraction_draft_note


def test_carries_source_quote_citation():
    note = _extraction_draft_note(
        {"benefit_key": "visa_support", "confidence": 0.4,
         "eligibility": None, "limits": None,
         "source_quote": "Assistance with obtaining necessary work permits and visas."}
    )
    assert "Source:" in note
    assert "work permits" in note


def test_combines_eligibility_limits_and_citation():
    note = _extraction_draft_note(
        {"eligibility": "All assignees", "limits": "90 days",
         "source_quote": "Only one storage location covered."}
    )
    assert "All assignees" in note
    assert "90 days" in note
    assert 'Source: "Only one storage location covered."' in note


def test_empty_when_no_fields():
    assert _extraction_draft_note({"benefit_key": "x", "confidence": 0.5}) == ""


def test_long_quote_is_truncated():
    long_quote = "x" * 500
    note = _extraction_draft_note({"source_quote": long_quote})
    assert "…" in note  # truncated (ellipsis sits before the closing quote)
    assert len(note) < 320
