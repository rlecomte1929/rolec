"""Partner career support is a first-class recommendation category (AIQ-2269)."""
from __future__ import annotations

import json
import os
import sys
import types
from typing import Any, Dict, List
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.app.recommendations.types import RecommendationResponse  # noqa: E402


def test_partner_career_in_registry_and_categories():
    from backend.app.recommendations.registry import list_categories, _REGISTRY

    keys = {c["key"] for c in list_categories()}
    assert "partner_career" in keys, f"got {sorted(keys)}"
    plug = _REGISTRY["partner_career"]
    assert plug.title == "Partner Career Support"
    data = plug.load_dataset()
    assert isinstance(data, list) and data
    r = plug.score(
        plug.CriteriaModel(),
        {"name": "X", "rating": 4.0, "availability_level": "high", "confidence": 60},
    )
    assert "score_raw" in r
    norms = plug.normalize([r["score_raw"], r["score_raw"] + 1])
    assert len(norms) == 2


def test_partner_career_in_recommendation_whitelists():
    from backend.app.recommendations.criteria_builder import SERVICE_KEY_TO_BACKEND

    assert SERVICE_KEY_TO_BACKEND.get("spouse") == "partner_career"
    from backend.app.recommendations.plugins.partner_career import PartnerCareerPlugin

    assert PartnerCareerPlugin.advisory is True


def test_partner_career_questions_registered():
    from backend.app.services.question_schema import get_questions_for_services

    qs = [q.question_key for q in get_questions_for_services(["spouse"])]
    assert qs == ["spouse_employment", "spouse_language", "spouse_wants_to_work"], qs


def test_spouse_saved_answers_win_over_case_profile():
    from backend.app.recommendations.criteria_builder import build_criteria_for_assignment

    out = build_criteria_for_assignment(
        assignment_id="a1",
        case_id="c1",
        selected_services=["spouse"],
        saved_answers={
            "spouse_employment": "Student",
            "spouse_language": "Fluent",
            "spouse_wants_to_work": False,
        },
        case_context={
            "destCity": "Berlin",
            "destCountry": "DE",
            "familyMembers": {
                "spouse": {
                    "fullName": "Priya",
                    "employment": "Working",
                    "languageLevel": "Beginner",
                    "wantsToWork": True,
                }
            },
        },
    )
    crit = out["partner_career"]
    assert crit["employment"] == "Student"
    assert crit["language_level"] == "Fluent"
    assert crit["wants_to_work"] is False


def test_spouse_criteria_shape_employment_and_language():
    from backend.app.recommendations.criteria_builder import build_criteria_for_assignment

    out = build_criteria_for_assignment(
        assignment_id="a1",
        case_id="c1",
        selected_services=["spouse"],
        saved_answers={},
        case_context={
            "destCity": "Berlin",
            "destCountry": "DE",
            "familyMembers": {
                "spouse": {
                    "fullName": "Priya",
                    "employment": "Working",
                    "languageLevel": "Beginner",
                    "wantsToWork": True,
                }
            },
        },
    )
    crit = out["partner_career"]
    assert crit["employment"] == "Working"
    assert crit["language_level"] == "Beginner"
    assert crit["wants_to_work"] is True


class _DummySession:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


class _Case:
    def __init__(self, draft: Dict[str, Any]):
        self.draft_json = json.dumps(draft)
        self.dest_city = "Berlin"
        self.dest_country = "DE"
        self.origin_city = None
        self.origin_country = None


_EMP = {"id": "emp-1", "role": "EMPLOYEE"}
_ASG = {
    "id": "asg-1",
    "case_id": "case-1",
    "employee_user_id": "emp-1",
    "hr_user_id": "hr-1",
    "company_id": "co-1",
}


def _run_batch(draft: Dict[str, Any], selected: List[str]) -> Dict[str, Any]:
    from backend.app.recommendations import router as rec_router
    import backend.main as main

    def _fake_recommend(backend_key, criteria, top_n=10, company_id=None):
        return RecommendationResponse(
            category=backend_key,
            generated_at="2026-09-11T00:00:00+00:00",
            criteria_echo=dict(criteria),
            recommendations=[],
        )

    patches = [
        mock.patch.object(rec_router, "require_assignment_visibility", lambda _i, _u: dict(_ASG)),
        mock.patch.object(rec_router, "recommend", side_effect=_fake_recommend),
        mock.patch.object(rec_router, "_log_slate", lambda *a, **k: None),
        mock.patch.object(main.db, "list_case_services", return_value=[]),
        mock.patch.object(main.db, "list_case_service_answers", return_value=[]),
        mock.patch("backend.app.db.SessionLocal", lambda: _DummySession()),
        mock.patch("backend.app.crud.get_case", return_value=_Case(draft)),
        mock.patch("backend.policy_engine.PolicyEngine", side_effect=RuntimeError("no policy")),
    ]
    for p in patches:
        p.start()
    try:
        request = types.SimpleNamespace(state=types.SimpleNamespace(request_id="req-pc"))
        return rec_router.post_recommendations_batch(
            request=request,
            user=dict(_EMP),
            body={"assignment_id": "asg-1", "selected_services": selected},
        )
    finally:
        for p in patches:
            p.stop()


def test_batch_returns_partner_career_when_partner_present():
    result = _run_batch(
        {"familyMembers": {"spouse": {"fullName": "Priya"}}},
        ["spouse", "movers"],
    )
    assert "partner_career" in result["results"]
    assert "movers" in result["results"]


def test_batch_omits_partner_career_when_no_partner():
    result = _run_batch({"familyMembers": {}}, ["spouse", "movers"])
    assert "partner_career" not in result["results"]
    assert "movers" in result["results"]
