import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.guidance_pack_service import (
    enforce_citations,
    build_checklist,
    build_coverage,
    generate_guidance_pack,
    MIN_PLAN_ITEMS,
    MIN_CHECKLIST_ITEMS,
)
from services.guidance_markdown import render_guidance_markdown


def test_citations_enforced():
    rules = [{"id": "r1", "title": "Rule 1", "citations": []}]
    docs = {}
    out = enforce_citations(rules, docs)
    assert out["usable"] == []
    assert "Rule 1" in out["not_covered"]


def test_due_date_computation():
    plan = {"items": [{"phase": "pre_move", "title": "T1", "description_md": "D", "citations": []}]}
    checklist = build_checklist(plan, "2026-05-01")
    assert checklist["items"][0]["due_date"] == "2026-04-03"


def test_markdown_contains_disclaimer():
    md = render_guidance_markdown(
        snapshot={"origin_country": "SG", "destination_country": "US", "move_date": "2026-05-01"},
        plan={"items": []},
        checklist={"items": []},
        sources=[],
        coverage={"score": 0, "domains_covered": [], "missing_info": [], "not_covered": []},
    )
    assert "Disclaimer" in md


def test_coverage_score_range():
    cov = build_coverage(
        snapshot={"origin_country": "SG", "destination_country": "US", "move_date": None, "employment_type": None},
        plan={"items": []},
        sources=[],
        not_covered=[],
    )
    assert 0 <= cov["score"] <= 100


def test_demo_mode_injects_baseline_minimums():
    rules = []
    docs_by_id = {"doc1": {"id": "doc1", "title": "Doc", "source_url": "https://example.com"}}
    for i, phase in enumerate(["pre_move", "arrival", "first_90_days", "first_tax_year", "pre_move", "arrival"], start=1):
        rules.append({
            "id": f"r{i}",
            "pack_id": "pack1",
            "pack_version": 1,
            "rule_key": f"BASE_{i}",
            "version": 1,
            "title": f"Baseline {i}",
            "phase": phase,
            "category": "immigration",
            "guidance_md": "Do the thing.",
            "citations": ["doc1"],
            "is_baseline": True,
            "baseline_priority": i * 10,
            "is_active": True,
        })
    outputs = generate_guidance_pack(
        case_id="case1",
        user_id="user1",
        destination_country="SG",
        draft={"relocationBasics": {"originCountry": "SG", "destCountry": "US", "targetMoveDate": "2026-05-01"}},
        dossier_answers={},
        rules=rules,
        docs_by_id=docs_by_id,
        guidance_mode="demo",
    )
    assert len(outputs["plan"]["items"]) >= MIN_PLAN_ITEMS
    assert len(outputs["checklist"]["items"]) >= MIN_CHECKLIST_ITEMS
    assert outputs["coverage"]["baseline_injected_count"] > 0
    assert len(outputs["rule_logs"]) == len(rules)


def test_strict_mode_allows_small_output():
    outputs = generate_guidance_pack(
        case_id="case1",
        user_id="user1",
        destination_country="SG",
        draft={"relocationBasics": {"originCountry": "SG", "destCountry": "US", "targetMoveDate": "2026-05-01"}},
        dossier_answers={},
        rules=[],
        docs_by_id={},
        guidance_mode="strict",
    )
    assert len(outputs["plan"]["items"]) == 0
