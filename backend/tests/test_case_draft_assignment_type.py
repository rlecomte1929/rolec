"""AIQ-1349 PR4 — the PATCH body schema must PRESERVE assignmentType.

CaseDraftDTO is ``extra="ignore"``, so a field missing from AssignmentContextDTO
is silently dropped before it reaches the canonical-case bridge. This regression
test caught exactly that (assignment_type never persisted to public.cases despite
the intake + bridge being wired)."""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.app.schemas import CaseDraftDTO


def test_case_draft_preserves_assignment_type_and_duration():
    d = CaseDraftDTO.model_validate(
        {"assignmentContext": {"assignmentType": "STA", "expectedDurationMonths": 6}}
    )
    assert d.assignmentContext is not None
    assert d.assignmentContext.assignmentType == "STA"
    assert d.assignmentContext.expectedDurationMonths == 6


def test_assignment_type_survives_model_dump():
    # The router does patch.model_dump(mode="json") then deep-merges — the field
    # must survive that round-trip or the bridge never sees it.
    d = CaseDraftDTO.model_validate({"assignmentContext": {"assignmentType": "PERMANENT"}})
    dumped = d.model_dump(mode="json")
    assert dumped["assignmentContext"]["assignmentType"] == "PERMANENT"
