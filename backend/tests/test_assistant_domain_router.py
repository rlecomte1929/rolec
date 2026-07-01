"""
Backend assistant domain router (single source of truth for the policy-bridge
routing). Ports the shipped frontend classifier so routing is testable + eval-
measurable. immigration vs policy vs ambiguous, deterministic; coverage-intent
("does my company pay for…") beats a bare immigration noun.
"""
import pytest

from backend.app.services.assistant_domain_router import classify_domain


@pytest.mark.parametrize("q", [
    "What documents do I need for my visa?",
    "How long does the work permit take?",
    "Do I need an apostille for my passport?",
    "Where do I register my residence?",
])
def test_immigration(q):
    assert classify_domain(q)["domain"] == "immigration"


@pytest.mark.parametrize("q", [
    "Does my company cover temporary housing?",
    "What is my relocation allowance?",
    "Will my employer reimburse my flights?",
    "Am I entitled to school fees for my kids?",
])
def test_policy(q):
    assert classify_domain(q)["domain"] == "policy"


@pytest.mark.parametrize("q", ["Can you help me?", "", "Tell me more about this"])
def test_ambiguous(q):
    assert classify_domain(q)["domain"] == "ambiguous"


def test_coverage_intent_beats_visa_noun():
    assert classify_domain("Does my company pay for the visa?")["domain"] == "policy"


def test_returns_scores():
    out = classify_domain("visa")
    assert out["immigration_score"] >= 1
    assert out["policy_score"] == 0
