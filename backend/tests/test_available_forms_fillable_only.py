"""get_available_forms must offer ONLY genuinely-fillable government forms.

Regression guard for the discovery that DE_blue_card_v2024 is a synthetic stand-in
(Germany's Blue Card process is online — the PDF is an output, not a fillable input; see
docs/form-autofill/ACROFORM-FEASIBILITY-DE-FR.md) yet carried 15 field mappings, so the
available-forms endpoint would have offered it as a fillable form. Only FR CERFA and ES
EX-17 are real fillable AcroForms.

DB-free: the raw row-fetch (_available_form_rows) is patched, so these assert the
fillable-only FILTER, not the query.
"""
from __future__ import annotations

from unittest import mock

from backend.app.services import form_prefill_service as fps


def _row(form_id, corridor_to, visa_type, field_count=5):
    return {
        "form_id": form_id,
        "form_name": f"{form_id} name",
        "corridor_to": corridor_to,
        "visa_type": visa_type,
        "form_url": None,
        "field_count": field_count,
    }


def test_fillable_allowlist_is_exactly_the_two_real_forms():
    assert fps.FILLABLE_FORM_IDS == {"FR_cerfa_14571_v2024", "ES_ex17_v2024"}


def test_synthetic_and_datasheet_forms_are_not_fillable():
    # The whole point: these carry field mappings but must never be offered.
    assert "DE_blue_card_v2024" not in fps.FILLABLE_FORM_IDS
    assert "NO_datasheet_v2026" not in fps.FILLABLE_FORM_IDS


def test_get_available_forms_drops_synthetic_de():
    rows = [_row("DE_blue_card_v2024", "DE", "blue_card", 15)]
    with mock.patch.object(fps, "_available_form_rows", return_value=rows):
        forms = fps.get_available_forms("DE", "blue_card")
    assert forms == [], "DE_blue_card_v2024 is synthetic and must not be offered"


def test_get_available_forms_keeps_the_real_fr_form():
    rows = [_row("FR_cerfa_14571_v2024", "FR", "long_stay", 18)]
    with mock.patch.object(fps, "_available_form_rows", return_value=rows):
        forms = fps.get_available_forms("FR", "long_stay")
    assert [f.form_id for f in forms] == ["FR_cerfa_14571_v2024"]
    assert forms[0].field_count == 18


def test_get_available_forms_filters_a_mixed_result():
    # A corridor/visa whose query happens to return both a real and a synthetic form.
    rows = [
        _row("DE_blue_card_v2024", "DE", "blue_card", 15),
        _row("ES_ex17_v2024", "ES", "residence", 10),
    ]
    with mock.patch.object(fps, "_available_form_rows", return_value=rows):
        forms = fps.get_available_forms("ES", "residence")
    assert [f.form_id for f in forms] == ["ES_ex17_v2024"]
