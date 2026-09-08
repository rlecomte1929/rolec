"""P2-07a (AIQ-698) — regression test: RoadmapStep schema carries the
dependency-id list.

The dependency graph is the basis for "available now" computation (P2-07b), so
the field that holds the upstream step IDs MUST be present on the RoadmapStep
Pydantic model. The canonical name in this repo is ``dependency_ids: List[str]``
(matches docs/platform-redesign/relopass-api-contracts.ts and the synced
frontend/src/types/relopass-api-contracts.ts) — this guard pins that.

The original task title used ``dependencies: step_id[]``; in practice the field
already exists across the canonical contract as ``dependency_ids: string[]``
with the comment "IDs of steps that must complete first". This test asserts the
field is present, correctly typed, defaults to ``[]``, and survives a
round-trip through model_validate / model_dump for a sample roadmap step JSON
with the field populated.
"""
from __future__ import annotations

from typing import Any, Dict, List, get_args, get_origin

import pytest

# The live router is cases_read.py (AIQ-178/199 confirmed cases.py is the
# unwired/dead duplicate; the production /api/cases routes resolve to
# cases_read.py). We guard the live model first, then the duplicate, so a
# regression in the dead module can't pass while the live one breaks silently.
from backend.app.routers.cases_read import RoadmapStepV2 as LiveRoadmapStepV2
from backend.app.routers.cases import RoadmapStepV2 as LegacyRoadmapStepV2


CANONICAL_FIELD = "dependency_ids"


def _typed_as_list_of_str(annotation: Any) -> bool:
    """True iff `annotation` is `list[str]` / `List[str]`."""
    if get_origin(annotation) is not list:
        return False
    args = get_args(annotation)
    return args == (str,)


@pytest.mark.parametrize(
    "model,label",
    [(LiveRoadmapStepV2, "cases_read.py (live)"),
     (LegacyRoadmapStepV2, "cases.py (legacy duplicate)")],
)
class TestRoadmapStepDependencyField:
    def test_field_is_present(self, model, label):
        assert CANONICAL_FIELD in model.model_fields, (
            f"{label}: RoadmapStepV2 is missing the {CANONICAL_FIELD!r} field "
            "— the dependency graph (basis for available-now computation) "
            "cannot work without it. See "
            "docs/platform-redesign/relopass-api-contracts.ts for the canonical "
            "shape."
        )

    def test_field_is_list_of_str(self, model, label):
        f = model.model_fields[CANONICAL_FIELD]
        assert _typed_as_list_of_str(f.annotation), (
            f"{label}: {CANONICAL_FIELD} must be List[str] (got {f.annotation!r})."
        )

    def test_field_defaults_to_empty_list(self, model, label):
        f = model.model_fields[CANONICAL_FIELD]
        # Pydantic v2: default is exposed directly.
        assert f.default == [], (
            f"{label}: {CANONICAL_FIELD} must default to [] (got {f.default!r})."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Sample roadmap JSON populates dependencies and round-trips cleanly
# ─────────────────────────────────────────────────────────────────────────────


def _sample_step(dependency_ids: List[str]) -> Dict[str, Any]:
    return {
        "id": "step-2",
        "title": "Submit work permit application",
        "description": "After biometrics are booked.",
        "status": "pending",
        "owner": "employee",
        "due_date": "2026-07-01",
        "sort_order": 2,
        "ai_suggestion": None,
        "dependency_ids": dependency_ids,
        "vendor_id": None,
        "doc_count": 0,
        "worst_doc_status": None,
    }


class TestSampleRoadmapJsonRoundTrips:
    def test_populated_dependency_ids_validate_and_dump(self):
        deps = ["step-1a", "step-1b"]
        m = LiveRoadmapStepV2.model_validate(_sample_step(deps))
        assert m.dependency_ids == deps
        dumped = m.model_dump()
        assert dumped["dependency_ids"] == deps

    def test_missing_dependency_ids_uses_empty_default(self):
        payload = _sample_step([])
        del payload["dependency_ids"]
        m = LiveRoadmapStepV2.model_validate(payload)
        assert m.dependency_ids == []

    def test_non_str_dependency_id_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            LiveRoadmapStepV2.model_validate(_sample_step([123]))  # type: ignore[list-item]
