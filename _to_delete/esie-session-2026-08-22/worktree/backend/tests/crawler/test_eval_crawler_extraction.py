"""AIQ-1096 (CRAWL-03) — crawler LLM-extraction eval harness.

Mocks every seam (fetch / parse / chunk / both extractors) — no network, no real LLM, no DB.
Deliberately does NOT set DATABASE_URL at import (the AIQ-1090 test-pollution lesson).
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.scripts.eval_crawler_extraction as ev


class _Cand:  # stand-in candidate — only the count matters to the harness
    pass


def _wire(monkeypatch, *, low_recall_url: str, llm_recovers: bool = True) -> None:
    monkeypatch.setattr(ev, "fetch_page", lambda url, *a, **k: SimpleNamespace(
        success=True, content="<html>x</html>", final_url=url, error=None, http_status=200))
    monkeypatch.setattr(ev, "parse_html", lambda content, url="": SimpleNamespace(page_title="Title"))
    monkeypatch.setattr(ev, "chunk_document", lambda doc, **k: [object()])

    def fake_rule(chunks, source, url, title):
        return [] if url == low_recall_url else [_Cand()]

    async def fake_llm(chunks, source, url, title):
        if url == low_recall_url:
            return [_Cand()] if llm_recovers else []
        return [_Cand()]

    monkeypatch.setattr(ev, "extract_resource_candidates", fake_rule)
    monkeypatch.setattr(ev, "extract_resource_candidates_llm", fake_llm)


def _fixture(tmp_path) -> tuple[str, str]:
    rows = [
        {"url": "https://gov.de/visa", "country_code": "DE", "country_name": "Germany",
         "content_domain": "admin_essentials", "trust_tier": "T0", "expected_min_candidates": 1},
        {"url": "https://gov.pt/imm", "country_code": "PT", "country_name": "Portugal",
         "content_domain": "admin_essentials", "trust_tier": "T0", "expected_min_candidates": 1},
    ]
    p = tmp_path / "pages.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows))
    return str(p), "https://gov.pt/imm"  # PT = the low-recall page (rule-based yields 0)


def test_report_shape_and_recall_recovery(tmp_path, monkeypatch):
    pages, low = _fixture(tmp_path)
    _wire(monkeypatch, low_recall_url=low, llm_recovers=True)
    out = tmp_path / "report.json"
    ev.main(["--pages", pages, "--out", str(out)])  # no --ci → no sys.exit
    report = json.loads(out.read_text())
    for key in ("rule_based_yield", "llm_yield", "llm_lift", "by_page", "pages_where_llm_recovers_recall"):
        assert key in report
    # DE: rule=1, llm=1 ; PT: rule=0, llm=1 (recovered)
    assert report["rule_based_yield"] == 1
    assert report["llm_yield"] == 2
    assert report["llm_lift"] == 1
    assert report["pages_where_llm_recovers_recall"] == 1
    pt = next(r for r in report["by_page"] if r["url"] == low)
    assert pt["rule_based_count"] == 0 and pt["llm_count"] > 0 and pt["recovered"] is True


def test_ci_exit_0_when_llm_recovers(tmp_path, monkeypatch):
    pages, low = _fixture(tmp_path)
    _wire(monkeypatch, low_recall_url=low, llm_recovers=True)
    with pytest.raises(SystemExit) as e:
        ev.main(["--pages", pages, "--out", str(tmp_path / "r.json"), "--ci"])
    assert e.value.code == 0


def test_ci_exit_1_when_llm_fails_to_recover(tmp_path, monkeypatch):
    pages, low = _fixture(tmp_path)
    _wire(monkeypatch, low_recall_url=low, llm_recovers=False)  # LLM yields 0 on the low-recall page
    with pytest.raises(SystemExit) as e:
        ev.main(["--pages", pages, "--out", str(tmp_path / "r.json"), "--ci"])
    assert e.value.code == 1


def test_no_db_imports():
    src = Path(ev.__file__).read_text()
    for forbidden in ("import sqlalchemy", "from sqlalchemy", "supabase", "from backend.database"):
        assert forbidden not in src, f"eval harness must not reference {forbidden!r}"
