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


def test_no_db_imports():
    src = Path(ev.__file__).read_text()
    for forbidden in ("import sqlalchemy", "from sqlalchemy", "supabase", "from backend.database"):
        assert forbidden not in src, f"eval harness must not reference {forbidden!r}"
