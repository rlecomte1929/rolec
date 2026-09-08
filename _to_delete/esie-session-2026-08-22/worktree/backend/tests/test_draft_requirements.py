"""AIQ-1349 — the LLM requirement-drafter's core logic (transport-decoupled).

Asserts the citation-bound contract: uncited drafts are dropped, the kept ones
carry assignment-type applicability + expert-review flag, and the emitted YAML is
marked draft + round-trips into the seed_requirements loader shape.
"""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import yaml

from backend.scripts.draft_requirements import build_context, draft_requirements, to_seed_yaml
from backend.scripts.seed_requirements import build_payloads

CHUNKS = [
    {"id": "c1", "source_url": "https://bamf.de/anmeldung", "chunk_text": "Register your address within 14 days."},
    {"id": "c2", "source_url": "https://make.de/visa", "chunk_text": "A work visa is required before entry."},
]


def _fake_complete(_context):
    # Mirrors the parsed emit_requirements tool input.
    return {"requirements": [
        {"title": "Residence registration", "pillar": "RESIDENCE",
         "description": "Register your address. Indicative — confirm with the Bürgeramt.",
         "severity": "WARN", "owner": "EMPLOYEE",
         "applies_to_assignment_types": ["LTA", "PERMANENT"],
         "citations": ["https://bamf.de/anmeldung"], "confidence": "high", "requires_expert_review": True},
        {"title": "Work visa", "pillar": "EMPLOYMENT",
         "description": "Obtain a work visa. Indicative — confirm with the consulate.",
         "severity": "BLOCKER", "owner": "EMPLOYEE",
         "applies_to_assignment_types": None,
         "citations": ["https://make.de/visa"], "confidence": "high", "requires_expert_review": False},
        {"title": "Hallucinated requirement", "pillar": "IDENTITY",
         "description": "No source. Indicative — confirm with nobody.",
         "severity": "INFO", "owner": "EMPLOYEE", "citations": [], "requires_expert_review": True},
    ]}


def test_drops_uncited_requirements():
    out = draft_requirements("GERMANY", "employment", CHUNKS, _fake_complete)
    titles = {r["title"] for r in out}
    assert "Residence registration" in titles
    assert "Work visa" in titles
    assert "Hallucinated requirement" not in titles  # no citation → dropped


def test_carries_applies_to_and_review_flag():
    out = draft_requirements("GERMANY", "employment", CHUNKS, _fake_complete)
    res = next(r for r in out if r["title"] == "Residence registration")
    assert res["applies_to_assignment_types"] == ["LTA", "PERMANENT"]
    assert res["requires_expert_review"] is True
    visa = next(r for r in out if r["title"] == "Work visa")
    assert visa["applies_to_assignment_types"] is None  # universal


def test_empty_corpus_yields_nothing():
    assert draft_requirements("GERMANY", "employment", [], _fake_complete) == []


def test_yaml_is_draft_and_loader_compatible():
    out = draft_requirements("GERMANY", "employment", CHUNKS, _fake_complete)
    text = to_seed_yaml("GERMANY", "employment", out)
    doc = yaml.safe_load(text)
    assert doc["verification_status"] == "draft"
    # the drafted YAML feeds straight into the loader's expansion
    payloads = build_payloads(doc)
    assert len(payloads) == 2  # GERMANY×[employment] × 2 valid requirements
    assert {p["title"] for p in payloads} == {"Residence registration", "Work visa"}


def test_build_context_includes_source_urls():
    ctx = build_context("GERMANY", "employment", CHUNKS)
    assert "source_url: https://bamf.de/anmeldung" in ctx
    assert "SUBJECT: country=GERMANY, purpose=employment" in ctx
