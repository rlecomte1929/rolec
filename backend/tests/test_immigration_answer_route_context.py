"""
Slice 3 route contract for POST /api/immigration/answer:
- with case_id → ownership is verified AND the anonymised applicant context is
  passed to the engine,
- without case_id → no ownership check, no context (unchanged behavior).
The retrieval pipeline is stubbed; we assert the wiring, not the RAG.
"""
import backend.app.routers.immigration_retrieve as route
from backend.app.routers.immigration_retrieve import ImmigrationAnswerBody


def _stub_pipeline(monkeypatch, chunks):
    monkeypatch.setattr(
        route.immigration_retriever, "retrieve_multi_source",
        lambda **k: {"official_chunks": chunks, "secondary_chunks": []},
    )
    monkeypatch.setattr(route, "reconcile", lambda off, sec: {"reconciled_chunks": off})


def test_case_id_checks_ownership_then_passes_context(monkeypatch):
    seen = {}
    monkeypatch.setattr(route, "require_case_access", lambda cid, user: seen.setdefault("access", cid))
    monkeypatch.setattr(route, "build_applicant_context", lambda cid: "Relocating with a spouse")
    _stub_pipeline(monkeypatch, [{"adjusted_score": 1.0, "fetched_at": "2026-06-06T00:00:00+00:00"}])
    captured = {}

    def fake_gen(payload, query, corridor, applicant_context=None):
        captured["ctx"] = applicant_context
        return {"answer_kind": "answer"}

    monkeypatch.setattr(route.immigration_answer_engine, "generate_immigration_answer", fake_gen)

    body = ImmigrationAnswerBody(corridor_from="IN", corridor_to="DE", nationality="IN",
                                 permit_type="blue_card", query="q", case_id="c1")
    out = route.answer_immigration_question(body, user={"id": "e1"})

    assert seen["access"] == "c1"  # ownership verified for the case
    assert captured["ctx"] == "Relocating with a spouse"  # context reached the engine
    assert out["answer_kind"] == "answer"


def test_no_case_id_skips_ownership_and_context(monkeypatch):
    def must_not_call(*a, **k):
        raise AssertionError("ownership/context invoked without a case_id")

    monkeypatch.setattr(route, "require_case_access", must_not_call)
    monkeypatch.setattr(route, "build_applicant_context", must_not_call)
    _stub_pipeline(monkeypatch, [])
    captured = {}

    def fake_gen(payload, query, corridor, applicant_context=None):
        captured["ctx"] = applicant_context
        return {"answer_kind": "refusal_insufficient_context"}

    monkeypatch.setattr(route.immigration_answer_engine, "generate_immigration_answer", fake_gen)

    body = ImmigrationAnswerBody(corridor_from="IN", corridor_to="DE", nationality="IN",
                                 permit_type="blue_card", query="q")
    route.answer_immigration_question(body, user={"id": "e1"})

    assert captured["ctx"] is None
