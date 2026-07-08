"""AIQ-1473c — fail-closed on an unresolved destination.

The full end-to-end "unknown destination on a real case → covered=False" path is
covered by 1473e (with case fixtures). Here we unit-test the fail-closed DTO
builder + the DTO default directly (no DB), which is where the behaviour lives.
"""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.app.schemas import CaseRequirementsDTO
from backend.app.services.requirements_builder import _not_covered


def test_covered_defaults_true():
    # Existing (covered) callers don't set it → must default True so the field is
    # backward-compatible for consumers that ignore it.
    dto = CaseRequirementsDTO(
        caseId="c1", destCountry="GERMANY", purpose="employment",
        computedAt=__import__("datetime").datetime.utcnow(),
        requirements=[], sources=[],
    )
    assert dto.covered is True


def test_not_covered_is_fail_closed():
    dto = _not_covered("case-123", "Atlantis", "employment")
    assert dto.covered is False
    assert dto.requirements == []          # empty because uncatalogued, not "nothing required"
    assert dto.sources == []
    assert dto.caseId == "case-123"
    assert dto.destCountry == "ATLANTIS"   # echoed via resolve_catalog_country (raw upper)
    assert dto.disclaimer                  # non-liability disclaimer still present
    assert dto.staWaived == []
