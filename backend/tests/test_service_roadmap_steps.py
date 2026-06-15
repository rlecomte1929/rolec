from backend.app.services.service_roadmap_steps import (
    SERVICE_STEPS, steps_for_service, service_key_for_category, ServiceStep,
)


def test_every_service_has_at_least_one_well_formed_step():
    assert SERVICE_STEPS, "step library must not be empty"
    for key, steps in SERVICE_STEPS.items():
        assert steps, f"{key} has no steps"
        for s in steps:
            assert isinstance(s, ServiceStep)
            assert s.key and s.title and s.phase
            assert s.phase in {"pre_departure", "during", "arrival"}


def test_steps_for_known_and_unknown_service():
    assert steps_for_service("immigration")  # known
    assert steps_for_service("does_not_exist") == []  # unknown -> empty, no crash


def test_immigration_has_an_embassy_step_and_schools_has_admissions():
    imm_titles = " ".join(s.title.lower() for s in steps_for_service("immigration"))
    assert "embassy" in imm_titles or "consular" in imm_titles
    sch_titles = " ".join(s.title.lower() for s in steps_for_service("schools"))
    assert "admission" in sch_titles


def test_quote_step_key_is_stable_for_quote_trigger():
    housing = {s.key for s in steps_for_service("housing")}
    assert any(k.endswith("quote") for k in housing)


def test_category_label_maps_to_service_key():
    assert service_key_for_category("Housing search") == "housing"
    assert service_key_for_category("Schools / Childcare") == "schools"
    assert service_key_for_category("Banking") in {"banking", "banks"}
    assert service_key_for_category("totally unknown category") is None
