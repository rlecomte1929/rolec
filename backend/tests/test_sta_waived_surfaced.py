"""AIQ-1349 gap #3: STA-suppressed requirements are recorded in
flags["staWaived"] (producer) and surfaced on CaseRequirementsDTO (schema) so
the employee UI can explain the shorter list instead of silently dropping items.
"""
from backend.app.services.rules_engine import apply_rules
from backend.app import schemas


def _draft(assignment_type):
    return {
        "relocationBasics": {"purpose": "WORK", "hasDependents": True},
        "assignmentContext": {"assignmentType": assignment_type},
        "familyMembers": {
            "spouse": {"wantsToWork": True},
            "children": [{"dateOfBirth": "2015-06-01"}],  # school age
        },
        "employeeProfile": {},
    }


def test_sta_waives_school_and_spouse_work():
    _fields, _expanded, flags = apply_rules(_draft("STA"), [])
    waived = flags.get("staWaived") or []
    assert "Dependent work authorization rules" in waived
    assert "School enrollment documents" in waived


def test_lta_keeps_them_and_waives_nothing():
    _fields, expanded, flags = apply_rules(_draft("LTA"), [])
    assert not flags.get("staWaived")
    titles = [r.get("title") for r in expanded]
    assert "School enrollment documents" in titles
    assert "Dependent work authorization rules" in titles


def test_dto_carries_sta_waived_field():
    dto = schemas.CaseRequirementsDTO(
        caseId="c1", destCountry="FRANCE", purpose="WORK",
        computedAt="2026-07-01T00:00:00", requirements=[], sources=[],
        staWaived=["School enrollment documents"],
    )
    assert dto.staWaived == ["School enrollment documents"]
    # default is empty for LTA/PERMANENT
    dto2 = schemas.CaseRequirementsDTO(
        caseId="c2", destCountry="FRANCE", purpose="WORK",
        computedAt="2026-07-01T00:00:00", requirements=[], sources=[],
    )
    assert dto2.staWaived == []
