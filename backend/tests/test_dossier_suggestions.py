"""[P3-02 / AIQ-1087] Tests for the RAG dossier suggestion service.

No DB, no network: retrieval is monkeypatched and the LLM is the in-repo
MockClient (which surfaces injected JSON as a tool_use block).

[OBS-01 / AIQ-1097] also covers the degraded-vs-empty distinction at both the
service layer (raises DossierSuggestionUnavailable on LLM failure) and the
/api/dossier/search-suggestions endpoint (returns degraded=True, not a 500).
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from unittest.mock import patch

import pytest

from backend.app.services import dossier_suggestion_service as svc
from backend.app.services.policy_assistant_llm_client import MockClient


_CHUNKS = [
    {"chunk_id": "us_fr_lsv_passport", "text": "A passport valid 3 months beyond stay is required.",
     "source_url": "https://france-visas.gouv.fr/passport"},
    {"chunk_id": "us_fr_lsv_proof_funds", "text": "Proof of sufficient funds is required for the long-stay visa.",
     "source_url": "https://france-visas.gouv.fr/funds"},
    {"chunk_id": "us_fr_lsv_accommodation", "text": "Proof of accommodation in France is required.",
     "source_url": None},
]


def test_corridor_for_case_builds_iso2_arrow():
    draft = {"relocationBasics": {"originCountry": "United States", "destCountry": "France"}}
    assert svc.corridor_for_case(draft) == "US→FR"
    # ISO2 inputs pass through
    assert svc.corridor_for_case({"relocationBasics": {"originCountry": "IN", "destCountry": "DE"}}) == "IN→DE"
    # missing origin/dest -> None
    assert svc.corridor_for_case({"relocationBasics": {"destCountry": "FR"}}) is None
    assert svc.corridor_for_case({}) is None


def test_happy_path_returns_structured_questions_with_source_ids(monkeypatch):
    monkeypatch.setattr(svc, "retrieve_chunks", lambda corridor, query, k=5: list(_CHUNKS))
    canned = json.dumps({
        "questions": [
            {"question_text": "Does your passport stay valid 3+ months beyond your visa?",
             "source_ids": ["us_fr_lsv_passport"], "rationale": "passport validity rule"},
            {"question_text": "Can you show proof of sufficient funds?",
             "source_ids": ["us_fr_lsv_proof_funds", "us_fr_lsv_accommodation"], "rationale": "funds + accommodation"},
        ]
    })
    client = MockClient(default_response=canned)

    out = svc.suggest_questions("US→FR", {"relocationBasics": {"purpose": "Employment"}}, client=client)

    assert len(out) == 2
    first = out[0]
    assert first["question_text"].startswith("Does your passport")
    assert first["answer_type"] == "text"
    assert first["sources"] == [{"chunk_id": "us_fr_lsv_passport", "url": "https://france-visas.gouv.fr/passport"}]
    # second question cites two chunks; the URL-less one still maps
    second_ids = {s["chunk_id"] for s in out[1]["sources"]}
    assert second_ids == {"us_fr_lsv_proof_funds", "us_fr_lsv_accommodation"}

    # the LLM prompt included the retrieved chunk texts as context (>=3)
    assert len(client.calls) == 1
    um = client.calls[0].user_message
    assert "us_fr_lsv_passport" in um and "us_fr_lsv_proof_funds" in um and "us_fr_lsv_accommodation" in um


def test_empty_corpus_fallback_returns_empty(monkeypatch):
    monkeypatch.setattr(svc, "retrieve_chunks", lambda corridor, query, k=5: [])
    client = MockClient(default_response=json.dumps({"questions": [{"question_text": "x", "source_ids": []}]}))
    out = svc.suggest_questions("ZZ→YY", {"relocationBasics": {}}, client=client)
    assert out == []
    # no LLM call when there's no corpus
    assert client.calls == []


def test_no_corridor_returns_empty():
    out = svc.suggest_questions(None, {"relocationBasics": {}})
    assert out == []


def test_malformed_llm_output_is_handled(monkeypatch):
    monkeypatch.setattr(svc, "retrieve_chunks", lambda corridor, query, k=5: list(_CHUNKS))
    client = MockClient(default_response="not json")  # tool_use parse fails -> None
    out = svc.suggest_questions("US→FR", {"relocationBasics": {}}, client=client)
    assert out == []


# ---------------------------------------------------------------------------
# [OBS-01 / AIQ-1097] degraded vs empty
# ---------------------------------------------------------------------------


class _RaisingClient:
    """LLM client whose complete() fails like a provider/transport outage."""

    def complete(self, req):  # noqa: ANN001 - mirrors the LlmClient protocol
        raise RuntimeError("anthropic: insufficient credits (402)")


def test_llm_failure_raises_unavailable_not_empty(monkeypatch):
    # Corpus retrieved fine, but the LLM call fails -> degraded, NOT a silent [].
    monkeypatch.setattr(svc, "retrieve_chunks", lambda corridor, query, k=5: list(_CHUNKS))
    with pytest.raises(svc.DossierSuggestionUnavailable):
        svc.suggest_questions("US→FR", {"relocationBasics": {}}, client=_RaisingClient())


# --- endpoint-level: /api/dossier/search-suggestions (degraded != 500, != empty) ---

from types import SimpleNamespace  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app, require_hr_or_employee  # noqa: E402

_EMP_USER = {"id": "emp-1", "role": "employee", "email": "emp@testco.test"}
_DRAFT = {"relocationBasics": {"originCountry": "United States", "destCountry": "France"}}
_FAKE_CASE = SimpleNamespace(draft_json=json.dumps(_DRAFT), dest_country="France")


def _client():
    app.dependency_overrides[require_hr_or_employee] = lambda: _EMP_USER
    return TestClient(app, raise_server_exceptions=False)


def _post():
    return _client().post("/api/dossier/search-suggestions", json={"case_id": "case-1"})


class _FakeSessionCM:
    """Stand-in for SessionLocal() — supports the `with ... as session` protocol
    without touching a real DB (get_case is mocked, so the session is unused)."""

    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


def _patches():
    """Patch the handler seams: auth-scope, DB session/case fetch."""
    return [
        patch("backend.main._require_case_id_assignment_visible", lambda *a, **k: None),
        patch("backend.main.SessionLocal", lambda: _FakeSessionCM()),
        patch("backend.main.app_crud.get_case", lambda session, cid: _FAKE_CASE),
    ]


def test_endpoint_degraded_on_llm_failure():
    """LLM outage -> 200 with degraded=True and no suggestions (NOT a 500)."""
    try:
        with _patches()[0], _patches()[1], _patches()[2], patch(
            "backend.app.services.dossier_suggestion_service.suggest_questions",
            side_effect=svc.DossierSuggestionUnavailable("US→FR"),
        ):
            resp = _post()
        assert resp.status_code == 200
        body = resp.json()
        assert body["degraded"] is True
        assert body["suggestions"] == []
    finally:
        app.dependency_overrides.clear()


def test_endpoint_not_degraded_on_success():
    """Suggestions present -> degraded is False (no regression)."""
    fake = [{"question_text": "Do you have a valid passport?", "answer_type": "text",
             "sources": [{"chunk_id": "us_fr_lsv_passport", "url": "https://x"}]}]
    try:
        with _patches()[0], _patches()[1], _patches()[2], patch(
            "backend.app.services.dossier_suggestion_service.suggest_questions",
            return_value=fake,
        ):
            resp = _post()
        assert resp.status_code == 200
        body = resp.json()
        assert body["degraded"] is False
        assert len(body["suggestions"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_endpoint_empty_corpus_is_not_degraded():
    """Uncovered corridor -> normal empty, degraded stays False."""
    try:
        with _patches()[0], _patches()[1], _patches()[2], patch(
            "backend.app.services.dossier_suggestion_service.suggest_questions",
            return_value=[],
        ):
            resp = _post()
        assert resp.status_code == 200
        body = resp.json()
        assert body["degraded"] is False
        assert body["suggestions"] == []
    finally:
        app.dependency_overrides.clear()
