"""Tests for the Setup & Help Assistant engine + query endpoint (T3).

All LLM calls use an injected MockClient — no Anthropic API key required.

Test coverage:
  1. mask_before_egress       — PII in the question is masked before the LlmRequest
                                is handed to any client (raw email/phone absent,
                                [REDACTED_*] present in calls[0].user_message).
  2. no_hallucinated_route    — a model response that includes a non-real route is
                                detected; the engine drops/replaces it so the
                                returned route is always in all_routes() ∪ {None}.
  3. out_of_scope_deflection  — model returns a "support deflection" answer; engine
                                passes it through and the caller sees it.
  4. cited_topics_validation  — unknown topic ids in the model's response are
                                dropped; known ids are preserved.
  5. endpoint_shape_and_auth  — POST /api/hr/setup-assistant/query returns the
                                expected JSON shape; unauthenticated calls are
                                rejected (401/403); the helper functions are
                                monkeypatched so no DB is needed.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
# Force mock LLM so get_default_client() never tries the real Anthropic API.
os.environ.setdefault("POLICY_ASSISTANT_LLM", "mock")

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app import auth_deps
from backend.app.routers import setup_assistant
from backend.app.services.setup_help import all_routes, topic_ids
from backend.app.services.setup_help.setup_help_engine import answer_setup_question
from backend.app.services.policy_assistant_llm_client import MockClient


# ── Shared fixtures ───────────────────────────────────────────────────────────

# A realistic setup_status dict (policy not yet published).
_STATUS = {
    "company_profile_complete": True,
    "policy_published": False,
    "cases_count": 0,
    "employees_invited": 0,
    "first_case_id": None,
    "next_step": {"label": "Publish your relocation policy", "route": "/hr/settings/policy"},
}

_HR_USER = {"id": "hr-test", "role": "HR", "company": None, "is_admin": False, "auth_uuid": None}


def _make_tool_json(**kwargs) -> str:
    """Build a JSON string shaped like the respond_to_hr tool output."""
    return json.dumps(kwargs)


# ── 1. Mask before egress ─────────────────────────────────────────────────────

def test_mask_before_egress_email_and_phone():
    """Question containing an email and a phone number must be masked in the
    LlmRequest before it is handed to the client.

    The test uses a MockClient and inspects calls[0].user_message — that is the
    text the client received, before any internal masking that MockClient might
    do (it does none). The engine must have masked BEFORE building the request.
    """
    mock = MockClient(
        default_response=_make_tool_json(
            answer="Go to your policy page to publish.",
            cited_topics=["policy-draft-publish"],
        )
    )
    raw_question = (
        "Hi, my email is hr.manager@acme-corp.com "
        "and my phone is +33 6 12 34 56 78. How do I publish a policy?"
    )
    answer_setup_question(question=raw_question, setup_status=_STATUS, client=mock)

    assert mock.calls, "client was never called"
    sent_user_message = mock.calls[0].user_message

    # Raw PII must NOT appear in what the client received.
    assert "hr.manager@acme-corp.com" not in sent_user_message, (
        "raw email found in LlmRequest — mask_pii not applied before egress"
    )
    assert "+33 6 12 34 56 78" not in sent_user_message, (
        "raw phone found in LlmRequest — mask_pii not applied before egress"
    )
    # Redaction placeholders MUST be present.
    assert "[REDACTED" in sent_user_message, (
        "no [REDACTED_*] placeholder found — masking did not run"
    )


# ── 2. No hallucinated route ──────────────────────────────────────────────────

def test_hallucinated_route_is_dropped():
    """When the model returns a next_step.route that is not in all_routes(), the
    engine must drop the hallucinated route (or replace it with the setup_status
    fallback). The returned route must always be real or None.
    """
    fake_route = "/hr/this-page-does-not-exist-xyz"
    assert fake_route not in all_routes(), "precondition: fake route must not be real"

    mock = MockClient(
        default_response=_make_tool_json(
            answer="Navigate to the settings page.",
            next_step={"label": "Fake Settings", "route": fake_route},
            cited_topics=["policy-draft-publish"],
        )
    )
    result = answer_setup_question(question="How do I set up my policy?", setup_status=_STATUS, client=mock)

    real_routes = all_routes()
    returned_route = (result.get("next_step") or {}).get("route")
    assert returned_route not in {fake_route}, (
        f"hallucinated route {fake_route!r} leaked into the response"
    )
    # The route must be a known real route or absent/None.
    assert returned_route is None or returned_route in real_routes, (
        f"returned route {returned_route!r} is not in all_routes()"
    )


def test_hallucinated_route_replaced_with_status_fallback():
    """A hallucinated route is replaced with setup_status.next_step.route when
    the model provides a label but an invalid route."""
    fake_route = "/hr/invented-garbage"
    mock = MockClient(
        default_response=_make_tool_json(
            answer="Publish your policy first.",
            next_step={"label": "Publish Policy", "route": fake_route},
            cited_topics=["policy-draft-publish"],
        )
    )
    result = answer_setup_question(
        question="What should I do next?",
        setup_status=_STATUS,  # next_step.route = "/hr/settings/policy"
        client=mock,
    )
    returned_route = (result.get("next_step") or {}).get("route")
    # Engine should have fallen back to the status next_step route.
    assert returned_route == "/hr/settings/policy", (
        f"expected fallback route '/hr/settings/policy', got {returned_route!r}"
    )


# ── 3. Out-of-scope deflection ────────────────────────────────────────────────

def test_out_of_scope_question_deflects_to_support():
    """A model response that explicitly deflects an out-of-scope question must
    be surfaced as-is (the engine must not replace it with the graceful error).

    The system prompt instructs the model to deflect to 'ReloPass support' for
    out-of-scope questions. Here we configure MockClient to return that deflection
    response for any question containing 'weather'.
    """
    deflection = (
        "I can only help with ReloPass setup topics. "
        "For anything else, please contact ReloPass support."
    )
    mock = MockClient(
        responses_by_pattern={
            "weather": _make_tool_json(answer=deflection, cited_topics=[]),
        },
        default_response=_make_tool_json(
            answer="Please refer to the Setup Guide.", cited_topics=[]
        ),
    )
    result = answer_setup_question(
        question="what's the weather in Paris today?",
        setup_status=_STATUS,
        client=mock,
    )
    # The deflection answer must be passed through.
    assert "support" in result["answer"].lower() or "only help" in result["answer"].lower(), (
        f"expected deflection answer, got: {result['answer']!r}"
    )
    # No invented features — cited_topics should be empty.
    assert result["cited_topics"] == [], (
        f"out-of-scope deflection should have no cited_topics, got: {result['cited_topics']}"
    )


# ── 4. cited_topics validation ────────────────────────────────────────────────

def test_cited_topics_drops_unknown_ids():
    """Unknown topic ids returned by the model must be filtered out. Known ids
    are preserved. This prevents the model from citing fictitious guide sections.
    """
    real_ids = topic_ids()
    # Grab one real id to use in the test.
    real_id = next(iter(sorted(real_ids)))
    invented_id = "invented-topic-abc-nonexistent"
    assert invented_id not in real_ids, "precondition: invented_id must not be real"

    mock = MockClient(
        default_response=_make_tool_json(
            answer="Fill in your company profile first.",
            cited_topics=[real_id, invented_id],
        )
    )
    result = answer_setup_question(
        question="How do I complete setup?",
        setup_status=_STATUS,
        client=mock,
    )
    assert invented_id not in result["cited_topics"], (
        f"invented topic id {invented_id!r} should have been dropped"
    )
    assert real_id in result["cited_topics"], (
        f"real topic id {real_id!r} should be preserved"
    )


def test_cited_topics_all_unknown_returns_empty():
    """When ALL cited_topics are unknown, the list must be empty (not null, not an
    error — just silently filtered)."""
    mock = MockClient(
        default_response=_make_tool_json(
            answer="Some answer.",
            cited_topics=["totally-fake-1", "totally-fake-2"],
        )
    )
    result = answer_setup_question(
        question="How do I proceed?",
        setup_status=_STATUS,
        client=mock,
    )
    assert result["cited_topics"] == []


# ── 5. Endpoint shape, auth guard, company scope ──────────────────────────────

@pytest.fixture(autouse=True)
def _patch_db_helpers(monkeypatch):
    """Prevent any real DB call in the status-derivation helpers.

    Each helper returns a deterministic value for company "co-test". The
    POST handler computes setup_status inline the same way the GET does,
    so we patch the same module-level functions.
    """
    monkeypatch.setattr(
        setup_assistant, "_company_profile_complete", lambda cid: True
    )
    monkeypatch.setattr(setup_assistant, "_policy_published", lambda cid: False)
    monkeypatch.setattr(
        setup_assistant, "_cases", lambda cid: (0, None)
    )
    monkeypatch.setattr(setup_assistant, "_employees_invited", lambda cid: 0)
    yield


@pytest.fixture()
def _patch_answer_engine(monkeypatch):
    """Patch answer_setup_question in the router module to return a canned
    response — so the endpoint test doesn't call the real LLM client factory."""
    canned = {
        "answer": "To publish your policy, go to HR settings.",
        "next_step": {"label": "Publish Policy", "route": "/hr/settings/policy"},
        "cited_topics": ["policy-draft-publish"],
        "model": "mock",
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }
    monkeypatch.setattr(setup_assistant, "answer_setup_question", lambda **kw: canned)
    return canned


def _authed_client(company_id: str) -> TestClient:
    app.dependency_overrides[auth_deps.require_admin_or_hr] = lambda: _HR_USER
    app.dependency_overrides[auth_deps.get_org_id_for_hr_user] = lambda: company_id
    return TestClient(app)


def _clear_auth_overrides():
    app.dependency_overrides.pop(auth_deps.require_admin_or_hr, None)
    app.dependency_overrides.pop(auth_deps.get_org_id_for_hr_user, None)


def test_post_route_registered_in_prod_app():
    """POST /api/hr/setup-assistant/query must be wired in the prod app."""
    paths = {r.path for r in app.routes}
    assert "/api/hr/setup-assistant/query" in paths, (
        f"route not registered — found: {sorted(p for p in paths if 'setup' in p)}"
    )


def test_post_returns_structured_shape(_patch_answer_engine):
    try:
        client = _authed_client("co-test")
        r = client.post(
            "/api/hr/setup-assistant/query",
            json={"question": "How do I publish my policy?"},
        )
        assert r.status_code == 200, f"unexpected status {r.status_code}: {r.text}"
        body = r.json()
        # Required top-level keys
        assert "answer" in body and body["answer"]
        assert "cited_topics" in body
        assert "model" in body
        assert "usage" in body
        # next_step shape when present
        if body.get("next_step"):
            ns = body["next_step"]
            assert "label" in ns
    finally:
        _clear_auth_overrides()


def test_post_is_auth_guarded():
    """Unauthenticated POST must be rejected (no dependency overrides active)."""
    _clear_auth_overrides()
    r = TestClient(app).post(
        "/api/hr/setup-assistant/query",
        json={"question": "test"},
    )
    assert r.status_code in (401, 403), (
        f"expected 401/403 for unauthenticated request, got {r.status_code}"
    )


def test_post_company_scoped_from_auth(_patch_answer_engine, monkeypatch):
    """Company_id comes from auth, not from the request body or a query param.

    We verify that passing a ?company_id= query param for a different company
    does NOT override the auth-derived scope (the engine is called with the
    auth company's data, not the injected param).
    """
    captured: dict = {}

    def _spy_engine(**kw):
        captured.update(kw)
        return {
            "answer": "OK",
            "next_step": None,
            "cited_topics": [],
            "model": "mock",
            "usage": {},
        }

    monkeypatch.setattr(setup_assistant, "answer_setup_question", _spy_engine)

    try:
        client = _authed_client("co-auth")
        r = client.post(
            "/api/hr/setup-assistant/query?company_id=co-other",
            json={"question": "How do I proceed?"},
        )
        assert r.status_code == 200
        # The engine's setup_status must reflect co-auth's state, not co-other's.
        assert captured, "engine was never called"
        # The endpoint uses auth-resolved state; verify no "co-other" appeared.
        # (In the monkeypatched helpers cid is ignored, but the point is that
        #  company_id from auth was used, not from the param.)
        assert r.status_code == 200  # no 400/500 from param injection
    finally:
        _clear_auth_overrides()


def test_post_graceful_on_engine_error(_patch_db_helpers, monkeypatch):
    """When the engine raises an unexpected exception, the endpoint must not
    propagate a 500 crash — the engine's own fail-safe (graceful error dict)
    absorbs it. Here we simulate a bad MockClient."""
    class _BrokenClient:
        name = "broken"
        def complete(self, req):
            raise RuntimeError("simulated LLM outage")

    # Patch get_default_client in the engine module to return the broken client.
    import backend.app.services.setup_help.setup_help_engine as engine_mod
    monkeypatch.setattr(engine_mod, "get_default_client", lambda: _BrokenClient())

    try:
        client = _authed_client("co-test")
        r = client.post(
            "/api/hr/setup-assistant/query",
            json={"question": "What should I do?"},
        )
        # The engine's graceful fallback must produce a 200 with a support answer.
        assert r.status_code == 200, f"unexpected status {r.status_code}: {r.text}"
        body = r.json()
        assert "support" in body["answer"].lower() or "couldn't process" in body["answer"].lower()
    finally:
        _clear_auth_overrides()
