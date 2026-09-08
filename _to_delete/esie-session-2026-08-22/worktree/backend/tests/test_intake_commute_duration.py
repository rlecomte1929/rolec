"""AIQ-1603: backend validation for the new intake fields.

commute_preference is validated against a fixed enum and expected_duration_months must be a
positive integer — an invalid value is a 422 at the API (AssignmentContextDTO), not silent
bad data written to public.cases.
"""
import pytest
from pydantic import ValidationError

from backend.app.schemas import AssignmentContextDTO

COMMUTE_ENUM = ["car", "public_transport", "bike", "walk", "no_preference"]


def test_valid_commute_and_duration_accepted():
    dto = AssignmentContextDTO(commutePreference="public_transport", expectedDurationMonths=18)
    assert dto.commutePreference == "public_transport"
    assert dto.expectedDurationMonths == 18


@pytest.mark.parametrize("val", COMMUTE_ENUM)
def test_all_five_enum_values_accepted(val):
    assert AssignmentContextDTO(commutePreference=val).commutePreference == val


def test_invalid_commute_rejected():
    with pytest.raises(ValidationError):
        AssignmentContextDTO(commutePreference="teleport")


def test_non_positive_duration_rejected():
    with pytest.raises(ValidationError):
        AssignmentContextDTO(expectedDurationMonths=0)
    with pytest.raises(ValidationError):
        AssignmentContextDTO(expectedDurationMonths=-3)


def test_none_values_allowed():
    dto = AssignmentContextDTO()
    assert dto.commutePreference is None
    assert dto.expectedDurationMonths is None
