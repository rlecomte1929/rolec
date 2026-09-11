from backend.app.services import form_prefill_service as fps


def _rows(*triples):
    # (form_field_id, vault_field_path, field_kind, transform_spec)
    return [{"form_field_id": a, "vault_field_path": b, "field_kind": c, "transform_spec": d}
            for a, b, c, d in triples]


def test_loader_builds_single_radio_from_rows():
    rows = _rows(("Sexo", "gender", "single_radio", {"values": {"M": "/Hombre", "F": "/Mujer"}}))
    groups = fps.load_choice_groups("ES_ex17_v2024", rows)
    g = groups["gender"]
    assert isinstance(g, fps.RadioField) and g.field_id == "Sexo" and g.values["F"] == "/Mujer"


def test_loader_builds_checkbox_options_from_rows():
    rows = _rows(("applicantGenderM", "gender", "checkbox_option", {"code": "M"}),
                 ("applicantGenderF", "gender", "checkbox_option", {"code": "F"}))
    groups = fps.load_choice_groups("FR_cerfa_14571_v2024", rows)
    assert groups["gender"] == {"M": "applicantGenderM", "F": "applicantGenderF"}


def test_loader_falls_back_to_code_when_no_rows():
    assert fps.load_choice_groups("FR_cerfa_14571_v2024", []) == fps.CHOICE_GROUPS["FR_cerfa_14571_v2024"]


def test_build_choice_fill_unchanged_when_groups_none():
    # the live-path regression guarantee: no groups passed == read CHOICE_GROUPS
    vals, _ = fps.build_choice_fill("ES_ex17_v2024", {"gender": "female", "marital_status": "single"})
    assert vals == {"Sexo": "/Mujer", "Estado Civil": "/Soltero"}
