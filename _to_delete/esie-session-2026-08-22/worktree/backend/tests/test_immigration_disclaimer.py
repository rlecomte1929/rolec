"""AIQ-1349 P1 — the immigration non-liability disclaimer + DTO carriage."""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from datetime import datetime

from backend.app.schemas import CaseRequirementsDTO
from backend.app.services.disclaimers import (
    DEFAULT_VERIFICATION_STATUS,
    IMMIGRATION_DISCLAIMER,
    IMMIGRATION_DISCLAIMER_VERSION,
)


def test_disclaimer_states_the_legal_posture():
    text = IMMIGRATION_DISCLAIMER.lower()
    assert "not legal advice" in text
    assert "no liability" in text or "accepts no liability" in text
    assert "licensed immigration professional" in text
    assert IMMIGRATION_DISCLAIMER_VERSION  # versioned


def test_case_requirements_dto_carries_disclaimer():
    dto = CaseRequirementsDTO(
        caseId="c1", destCountry="FRANCE", purpose="employment",
        computedAt=datetime.utcnow(), requirements=[], sources=[],
        disclaimer=IMMIGRATION_DISCLAIMER, verificationStatus=DEFAULT_VERIFICATION_STATUS,
    )
    assert dto.disclaimer == IMMIGRATION_DISCLAIMER
    assert dto.verificationStatus == "representative"
    # serializes (API response)
    assert "not legal advice" in dto.model_dump()["disclaimer"].lower()
