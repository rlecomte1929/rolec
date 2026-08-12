"""AIQ-1093 (P4-04) — requirement-fact extraction eval harness.

Mocks the extractor (no LLM/network/DB). Deliberately does NOT set DATABASE_URL at import
(the AIQ-1090 test-pollution lesson).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import backend.scripts.eval_requirement_extraction as ev
from backend.app.services.requirement_fact_extractor import RequirementFact


def _f(text: str, rtype: str) -> RequirementFact:
    return RequirementFact(
        text=text, requirement_type=rtype, corridor="IN-DE", confidence_score=0.9,
        source_quote="", source_url="https://gov.example", extraction_method="llm",
    )


async def _mock_extract(url, *, corridor="", content=None):
    # 4 of 5 facts match the golden (passport x2 + fee x2); 1 is a hallucination → precision 0.8.
    return [
        _f("A valid passport is required.", "document"),
        _f("Your passport must be valid for 6 months.", "document"),
        _f("Pay the application fee.", "fee"),
        _f("The fee is EUR 75.", "fee"),
        _f("You must bring a unicorn.", "other"),
    ]


def _golden(tmp_path) -> str:
    p = tmp_path / "golden.jsonl"
    p.write_text(json.dumps({
        "url": "https://gov.example", "corridor": "IN-DE", "requirement_type_hint": None,
        "expected_facts": [
            {"text_contains": "passport", "requirement_type": "document"},
            {"text_contains": "fee", "requirement_type": "fee"},
        ],
    }))
    return str(p)


def test_passes_at_threshold_070(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "extract_requirement_facts", _mock_extract)
    out = tmp_path / "r.json"
    ev.main(["--golden", _golden(tmp_path), "--out", str(out), "--threshold", "0.70", "--ci"])  # no SystemExit
    report = json.loads(out.read_text())
    for key in ("precision", "recall", "threshold", "passes_threshold", "by_url"):
        assert key in report
    assert report["precision"] == 0.8
    assert report["recall"] == 1.0           # both expected facts covered
    assert report["passes_threshold"] is True


def test_fails_at_threshold_099(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "extract_requirement_facts", _mock_extract)
    with pytest.raises(SystemExit) as e:
        ev.main(["--golden", _golden(tmp_path), "--out", str(tmp_path / "r.json"), "--threshold", "0.99", "--ci"])
    assert e.value.code == 1


# ── [AIQ-1821] the gate must not go green on a run that measured nothing ─────

async def _extract_nothing(url, *, corridor="", content=None):
    """The real failure mode: the page body never reached the model."""
    return []


def test_zero_yield_url_scores_zero_not_one(tmp_path, monkeypatch):
    """A URL the extractor read nothing from must score 0.0, not a perfect 1.0."""
    monkeypatch.setattr(ev, "extract_requirement_facts", _extract_nothing)
    out = tmp_path / "r.json"
    with pytest.raises(SystemExit) as e:
        ev.main(["--golden", _golden(tmp_path), "--out", str(out), "--threshold", "0.70", "--ci"])
    assert e.value.code == 1
    report = json.loads(out.read_text())
    assert report["precision"] == 0.0
    assert report["recall"] == 0.0
    assert report["passes_threshold"] is False
    assert report["by_url"][0]["precision"] == 0.0
    assert report["zero_yield_urls"] == ["https://gov.example"]


def test_all_entries_skipped_fails_ci(tmp_path, monkeypatch):
    """Every URL erroring means nothing was measured — that cannot be a pass."""
    async def _boom(url, *, corridor="", content=None):
        raise RuntimeError("network down")

    monkeypatch.setattr(ev, "extract_requirement_facts", _boom)
    out = tmp_path / "r.json"
    with pytest.raises(SystemExit) as e:
        ev.main(["--golden", _golden(tmp_path), "--out", str(out), "--threshold", "0.70", "--ci"])
    assert e.value.code == 1
    report = json.loads(out.read_text())
    assert report["entries_evaluated"] == 0
    assert report["entries_skipped"] == 1
    assert report["passes_threshold"] is False


def test_recall_is_gated_not_just_precision(tmp_path, monkeypatch):
    """High precision with poor recall must fail — extracting one safe fact isn't a pass."""
    async def _one_match(url, *, corridor="", content=None):
        # 1 extracted, 1 matched → precision 1.0, but only 1 of 2 expected → recall 0.5.
        return [_f("A valid passport is required.", "document")]

    monkeypatch.setattr(ev, "extract_requirement_facts", _one_match)
    out = tmp_path / "r.json"
    with pytest.raises(SystemExit) as e:
        ev.main(["--golden", _golden(tmp_path), "--out", str(out), "--threshold", "0.70", "--ci"])
    assert e.value.code == 1
    report = json.loads(out.read_text())
    assert report["precision"] == 1.0
    assert report["recall"] == 0.5
    assert report["passes_threshold"] is False


def test_no_db_imports():
    src = Path(ev.__file__).read_text()
    for forbidden in ("import sqlalchemy", "from sqlalchemy", "supabase", "from backend.database"):
        assert forbidden not in src, f"eval harness must not reference {forbidden!r}"
