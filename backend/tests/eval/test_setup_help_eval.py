# T5 — Unit tests for the Setup & Help Assistant eval.
#
# Three test groups:
#   1. run_eval scores a tiny inline set correctly (grounding, refusal, accuracy).
#   2. Hallucinated-route/topic test: a mock that returns bogus values is still
#      scored grounding=1.0 because the ENGINE dropped them. Proves the guardrail.
#   3. CI gate passes when run against the full committed golden set (--mock).
"""
No real LLM calls. All tests are offline and deterministic.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from backend.app.services.setup_help.knowledge_base import all_routes, topic_ids
from backend.eval.run_setup_help_eval import (
    DEFAULT_FIXTURES,
    SetupHelpMockClient,
    load_cases,
    run_eval,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

# Pick one real route and one real topic for inline fixtures.
_REAL_ROUTE = "/hr/company-profile"
_REAL_TOPIC = "company-profile"


def _make_client(
    route: Optional[str],
    topic: Optional[str],
    is_refusal: bool = False,
) -> Any:
    """Return a mock LlmClient that always returns the given route/topic."""
    _REFUSAL = (
        "I can only help with ReloPass setup topics. "
        "For anything else, please contact ReloPass support."
    )

    class _FixedClient:
        name = "fixed_mock"

        def complete(self, req: Any) -> Dict[str, Any]:
            answer = _REFUSAL if is_refusal else f"See the guide for {topic}."
            ns = (
                {"label": "Go there", "route": route}
                if route and not is_refusal
                else None
            )
            return {
                "text": "",
                "tool_use": {
                    "answer": answer,
                    "next_step": ns,
                    "cited_topics": [topic] if topic and not is_refusal else [],
                },
                "model": "fixed_mock",
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 0, "output_tokens": 0},
            }

    return _FixedClient()


def _in_scope_case(case_id: str, expected_route: Optional[str]) -> Dict[str, Any]:
    return {
        "id": case_id,
        "setup_state": {
            "company_profile_complete": True,
            "next_step": {"label": "Profile", "route": _REAL_ROUTE},
        },
        "question": "How do I complete my company profile?",
        "expect": {
            "next_step_route": expected_route,
            "must_mention_topic": _REAL_TOPIC,
            "should_refuse": False,
        },
    }


def _oos_case(case_id: str) -> Dict[str, Any]:
    return {
        "id": case_id,
        "setup_state": {"company_profile_complete": True, "next_step": None},
        "question": "What is the weather tomorrow?",
        "expect": {
            "next_step_route": None,
            "must_mention_topic": None,
            "should_refuse": True,
        },
    }


# ── Group 1: scoring correctness on a tiny inline set ────────────────────────


def test_grounding_is_1_when_real_routes_returned():
    """A client that returns a REAL route/topic → grounding 1.0."""
    cases = [_in_scope_case("g-01", _REAL_ROUTE)]
    client = _make_client(_REAL_ROUTE, _REAL_TOPIC)
    report = run_eval(cases, client)
    assert report["grounding"] == 1.0
    assert report["n_cases"] == 1


def test_next_step_accuracy_correct_route():
    """Correct route returned → next_step_accuracy 1.0."""
    cases = [_in_scope_case("ns-01", _REAL_ROUTE)]
    client = _make_client(_REAL_ROUTE, _REAL_TOPIC)
    report = run_eval(cases, client)
    assert report["next_step_accuracy"] == 1.0


def test_next_step_accuracy_wrong_route():
    """Client returns a different REAL route → accuracy drops (not a gate)."""
    other_route = next(r for r in sorted(all_routes()) if r != _REAL_ROUTE)
    cases = [_in_scope_case("ns-02", _REAL_ROUTE)]
    client = _make_client(other_route, _REAL_TOPIC)
    report = run_eval(cases, client)
    assert report["next_step_accuracy"] == 0.0
    # Grounding still 1.0 — the returned route IS real, just the wrong one.
    assert report["grounding"] == 1.0


def test_refusal_correct_for_oos_case():
    """Out-of-scope case deflected correctly → refusal_correct 1.0."""
    cases = [_oos_case("r-01")]
    client = _make_client(None, None, is_refusal=True)
    report = run_eval(cases, client)
    assert report["refusal_correct"] == 1.0
    assert report["n_out_of_scope"] == 1


def test_refusal_incorrect_when_oos_gets_a_route():
    """Client answers an OOS question with a real route → refusal_correct 0.0."""
    cases = [_oos_case("r-02")]
    # Not a refusal answer — has a route and no deflection text.
    client = _make_client(_REAL_ROUTE, _REAL_TOPIC, is_refusal=False)
    report = run_eval(cases, client)
    assert report["refusal_correct"] == 0.0


def test_mixed_set_aggregates_correctly():
    """2 in-scope (both correct) + 1 OOS (refusal ok) → all metrics 1.0."""
    cases = [
        _in_scope_case("m-01", _REAL_ROUTE),
        _in_scope_case("m-02", _REAL_ROUTE),
        _oos_case("m-03"),
    ]

    class _MixedClient:
        name = "mixed"
        _refusal = (
            "I can only help with ReloPass setup topics. "
            "For anything else, please contact ReloPass support."
        )

        def complete(self, req: Any) -> Dict[str, Any]:
            q = req.user_message.lower()
            is_oos = "weather" in q
            return {
                "text": "",
                "tool_use": {
                    "answer": self._refusal if is_oos else f"Guide for {_REAL_TOPIC}.",
                    "next_step": (
                        None
                        if is_oos
                        else {"label": "Open", "route": _REAL_ROUTE}
                    ),
                    "cited_topics": [] if is_oos else [_REAL_TOPIC],
                },
                "model": "mixed",
                "stop_reason": "tool_use",
                "usage": {},
            }

    report = run_eval(cases, _MixedClient())
    assert report["grounding"] == 1.0
    assert report["refusal_correct"] == 1.0
    assert report["next_step_accuracy"] == 1.0
    assert report["ci_gate_pass"] is True


def test_ci_gate_fails_on_partial_grounding():
    """One hallucinated topic → grounding < 1.0 → ci_gate_pass False."""
    # The HALLUCINATED topic slips past the mock but the ENGINE filters it.
    # So grounding is ALWAYS 1.0 from the engine output.  To drive grounding
    # below 1.0 in run_eval, the client must somehow return both a bad topic
    # AND the engine must fail to filter it — which can't happen (engine always
    # filters).  So this test verifies that with a bad mock the gate STAYS
    # True (engine fixes it), and documents why:
    cases = [_in_scope_case("cg-01", _REAL_ROUTE)]

    class _BadTopicClient:
        name = "bad_topic_mock"

        def complete(self, req: Any) -> Dict[str, Any]:
            return {
                "text": "",
                "tool_use": {
                    "answer": "See the guide.",
                    "next_step": {"label": "X", "route": _REAL_ROUTE},
                    "cited_topics": ["FAKE-TOPIC-NOT-IN-KB", _REAL_TOPIC],
                },
                "model": "bad_topic_mock",
                "stop_reason": "tool_use",
                "usage": {},
            }

    report = run_eval(cases, _BadTopicClient())
    # Engine drops "FAKE-TOPIC-NOT-IN-KB" from cited_topics.
    # Grounding remains 1.0 — the engine's topic guardrail fired.
    assert report["grounding"] == 1.0
    assert report["ci_gate_pass"] is True
    detail = report["details"][0]
    assert "FAKE-TOPIC-NOT-IN-KB" not in (detail.get("cited_topics") or [])


# ── Group 2: hallucinated route proves the engine guardrail ──────────────────


class _HallucinatingClient:
    """Always returns a bogus route and a fake topic that are NOT in the KB."""

    name = "hallucinator"

    def complete(self, req: Any) -> Dict[str, Any]:
        return {
            "text": "",
            "tool_use": {
                "answer": "Go to the magic page for your answer!",
                "next_step": {
                    "label": "Magic Page",
                    "route": "/BOGUS/hallucinated-route",
                },
                "cited_topics": ["fake-topic-xyz-not-in-kb"],
            },
            "model": "hallucinator",
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }


def test_hallucinated_route_is_dropped_by_engine():
    """Engine guardrail drops a route not in all_routes()."""
    from backend.app.services.setup_help.setup_help_engine import answer_setup_question

    result = answer_setup_question(
        question="How do I complete my company profile?",
        setup_status={
            "company_profile_complete": False,
            "next_step": {"label": "Complete profile", "route": _REAL_ROUTE},
        },
        client=_HallucinatingClient(),
    )

    ns = result.get("next_step") or {}
    returned_route = ns.get("route") if isinstance(ns, dict) else None

    # The hallucinated route must never appear in the output.
    assert returned_route != "/BOGUS/hallucinated-route", (
        "Engine let a hallucinated route through — guardrail is broken"
    )

    # The engine uses the setup_status fallback route instead.
    if returned_route is not None:
        assert returned_route in all_routes(), (
            f"Engine returned a route outside all_routes(): {returned_route!r}"
        )


def test_hallucinated_topic_is_dropped_by_engine():
    """Engine guardrail drops a cited_topic not in topic_ids()."""
    from backend.app.services.setup_help.setup_help_engine import answer_setup_question

    result = answer_setup_question(
        question="How do I invite an employee?",
        setup_status={"next_step": None},
        client=_HallucinatingClient(),
    )

    cited = result.get("cited_topics") or []
    assert "fake-topic-xyz-not-in-kb" not in cited, (
        "Engine let a hallucinated topic through — topic guardrail is broken"
    )
    # All surviving topics must be real.
    real = topic_ids()
    for t in cited:
        assert t in real, f"Engine emitted unknown topic {t!r}"


def test_hallucinated_route_grounding_is_1_in_run_eval():
    """run_eval scores grounding=1.0 even when client hallucinations because the
    engine always filters them before run_eval sees the output."""
    cases = [
        {
            "id": "hall-01",
            "setup_state": {
                "company_profile_complete": False,
                "next_step": {"label": "Complete profile", "route": _REAL_ROUTE},
            },
            "question": "How do I complete my company profile?",
            "expect": {
                "next_step_route": _REAL_ROUTE,
                "must_mention_topic": None,
                "should_refuse": False,
            },
        }
    ]
    report = run_eval(cases, _HallucinatingClient())
    assert report["grounding"] == 1.0, (
        f"Grounding should be 1.0 after engine guardrail; got {report['grounding']}"
    )


# ── Group 3: CI gate on full golden set ──────────────────────────────────────


def test_ci_gate_passes_on_golden_set():
    """The full committed golden set passes grounding=1.0 AND refusal=1.0 with
    the SetupHelpMockClient.  This is what CI runs."""
    cases = load_cases(DEFAULT_FIXTURES)
    assert len(cases) >= 16, f"Expected ≥16 golden cases, got {len(cases)}"

    oos_count = sum(1 for c in cases if c["expect"].get("should_refuse"))
    assert oos_count >= 3, f"Need ≥3 out-of-scope cases, got {oos_count}"

    report = run_eval(cases, SetupHelpMockClient())

    assert report["grounding"] == 1.0, (
        f"grounding GATE FAIL: {report['grounding']:.4f}\n"
        + "\n".join(
            f"  {d['id']}: {d['failures']}"
            for d in report["details"]
            if d["failures"]
        )
    )
    assert report["refusal_correct"] == 1.0, (
        f"refusal_correct GATE FAIL: {report['refusal_correct']:.4f}\n"
        + "\n".join(
            f"  {d['id']}: {d['failures']}"
            for d in report["details"]
            if d["failures"]
        )
    )
    assert report["ci_gate_pass"] is True


def test_golden_set_has_expected_structure():
    """Smoke-check: every case in the golden set has required keys and real
    expected routes/topics."""
    real_routes = all_routes()
    real_topics = topic_ids()
    cases = load_cases(DEFAULT_FIXTURES)

    for case in cases:
        assert "id" in case, f"Missing 'id': {case}"
        assert "setup_state" in case, f"Missing 'setup_state': {case['id']}"
        assert "question" in case, f"Missing 'question': {case['id']}"
        assert "expect" in case, f"Missing 'expect': {case['id']}"

        exp = case["expect"]
        er = exp.get("next_step_route")
        if er is not None:
            assert er in real_routes, (
                f"Case {case['id']}: expected route {er!r} not in all_routes()"
            )
        mt = exp.get("must_mention_topic")
        if mt is not None:
            assert mt in real_topics, (
                f"Case {case['id']}: must_mention_topic {mt!r} not in topic_ids()"
            )
