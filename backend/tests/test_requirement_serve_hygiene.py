from backend.app.services.requirement_serve_hygiene import (
    addressed_to_third_country_only,
    display_title,
    is_generic_thirty_day_lead,
)
from backend.app.services.rules_engine import apply_rules


def test_display_title_replaces_ellipsis_cut_with_full_description_line():
    title = "Employees who arrive mid-year and have income from both their home country and Ireland in …"
    desc = (
        "Employees who arrive mid-year and have income from both their home country "
        "and Ireland in the same tax year may become chargeable persons.\n"
        "Second paragraph stays off the label."
    )
    assert display_title(title, desc).endswith("chargeable persons.")
    assert "…" not in display_title(title, desc)


def test_display_title_leaves_complete_titles_alone():
    assert display_title("Employment Pass (EP)", "Longer body") == "Employment Pass (EP)"


def test_non_eea_title_is_third_country_addressed():
    assert addressed_to_third_country_only(
        "Non-EEA nationals (including employment permit holders) must register with ISD"
    )
    assert addressed_to_third_country_only("Non-EU citizens must present their current passport")
    assert not addressed_to_third_country_only("Emergency tax — missing RPN")
    assert not addressed_to_third_country_only("Ireland EU/EEA Free-Mover Entry Rights")


def test_eea_mover_does_not_receive_null_scoped_non_eea_irp_title():
    irp = {
        "id": "irp",
        "pillar": "TIMELINE",
        "title": "Non-EEA nationals (including employment permit holders) must register with Immigration Service Delivery (ISD)",
        "description": "IRP within 90 days",
        "appliesToNationalityClasses": None,
    }
    tax = {
        "id": "et",
        "pillar": "TIMELINE",
        "title": "Emergency tax — missing RPN",
        "description": "Register the job",
        "appliesToNationalityClasses": None,
    }
    draft = {
        "relocationBasics": {"purpose": "employment", "destCountry": "IE"},
        "assignmentContext": {"assignmentType": "LTA"},
        "employeeProfile": {"nationality": "ES"},
    }
    _req, expanded, flags = apply_rules(draft, [irp, tax])
    titles = {i.get("title") for i in expanded}
    assert "Emergency tax — missing RPN" in titles
    assert irp["title"] not in titles
    assert flags.get("nationalityClass") == "EU_EEA"


def test_third_country_still_sees_non_eea_addressed_title():
    irp = {
        "id": "irp",
        "pillar": "TIMELINE",
        "title": "Non-EEA nationals must register with ISD",
        "description": "IRP",
        "appliesToNationalityClasses": None,
    }
    draft = {
        "relocationBasics": {"purpose": "employment", "destCountry": "IE"},
        "assignmentContext": {"assignmentType": "LTA"},
        "employeeProfile": {"nationality": "VE"},
    }
    _req, expanded, _flags = apply_rules(draft, [irp])
    assert any(i.get("id") == "irp" for i in expanded)


def test_generic_30_day_lead_is_dropped_for_third_country():
    lead = {
        "id": "lead",
        "pillar": "TIMELINE",
        "title": "Minimum lead time",
        "description": "Submit documents at least 30 days before start date.",
        "appliesToNationalityClasses": None,
    }
    ep = {
        "id": "ep",
        "pillar": "EMPLOYMENT",
        "title": "Employment Pass (EP)",
        "description": "Employer files with MOM.",
        "appliesToNationalityClasses": ["THIRD_COUNTRY"],
    }
    draft = {
        "relocationBasics": {"purpose": "employment", "destCountry": "SG"},
        "assignmentContext": {"assignmentType": "LTA"},
        "employeeProfile": {"nationality": "FR"},
    }
    _req, expanded, _flags = apply_rules(draft, [lead, ep])
    titles = {i.get("title") for i in expanded}
    assert "Employment Pass (EP)" in titles
    assert "Minimum lead time" not in titles
    assert is_generic_thirty_day_lead(lead)


def test_own_national_confirmation_carries_a_url():
    visa = {
        "id": "visa",
        "pillar": "RESIDENCE",
        "title": "Long-stay visa",
        "appliesToNationalityClasses": ["THIRD_COUNTRY"],
    }
    draft = {
        "relocationBasics": {"purpose": "employment", "destCountry": "FR"},
        "assignmentContext": {"assignmentType": "LTA"},
        "employeeProfile": {"nationality": "FR"},
    }
    _req, expanded, _flags = apply_rules(draft, [visa])
    conf = next(i for i in expanded if i.get("id") == "immigration_nothing_to_do")
    assert conf["citations"]
    assert conf["citations"][0].startswith("https://europa.eu/")
