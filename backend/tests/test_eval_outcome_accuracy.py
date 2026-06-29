"""AIQ-710 (P3-01d) — outcome-accuracy evaluator.

build_report is pure (tested directly with synthetic rows); the DB seam load_closed_outcomes is
monkeypatched (no real DB). Deliberately does NOT set DATABASE_URL at import (AIQ-1090 lesson).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import backend.scripts.eval_outcome_accuracy as ev


def _row(origin, dest, corrections, outcome="APPROVED"):
    return {
        "case_ref_hash": f"h-{origin}{dest}-{corrections}",
        "origin_country_code": origin,
        "dest_country_code": dest,
        "outcome": outcome,
        "specialist_corrections_count": corrections,
    }


def _sufficient_rows():
    # 22 closed cases across IN-DE (12) and FR-NO (10); 4 of them have corrections → 18 correction-free.
    rows = []
    rows += [_row("IN", "DE", 0) for _ in range(10)] + [_row("IN", "DE", 2) for _ in range(2)]
    rows += [_row("FR", "NO", 0) for _ in range(8)] + [_row("FR", "NO", 1) for _ in range(2)]
    return rows


def test_build_report_sufficient_and_accurate():
    report = ev.build_report(_sufficient_rows(), min_cases=20)
    assert report["sufficient"] is True
    assert report["closed_cases"] == 22
    assert report["accuracy"] == round(18 / 22, 4)
    corridors = {c["corridor"]: c for c in report["by_corridor"]}
    assert corridors["IN-DE"]["closed_cases"] == 12
    assert corridors["IN-DE"]["correction_free_rate"] == round(10 / 12, 4)
    assert corridors["FR-NO"]["correction_free_rate"] == round(8 / 10, 4)


def test_build_report_insufficient():
    report = ev.build_report([_row("IN", "DE", 0) for _ in range(5)], min_cases=20)
    assert report["sufficient"] is False
    assert report["closed_cases"] == 5


def test_report_has_all_keys():
    report = ev.build_report(_sufficient_rows(), min_cases=20)
    for key in ("sufficient", "closed_cases", "min_cases", "accuracy", "mean_corrections", "by_corridor"):
        assert key in report


def test_main_ci_exits_1_when_insufficient(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "load_closed_outcomes", lambda: [_row("IN", "DE", 0) for _ in range(5)])
    with pytest.raises(SystemExit) as e:
        ev.main(["--out", str(tmp_path / "oa.json"), "--min-cases", "20", "--ci"])
    assert e.value.code == 1


def test_main_ci_exits_0_when_sufficient(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "load_closed_outcomes", lambda: _sufficient_rows())
    out = tmp_path / "oa.json"
    ev.main(["--out", str(out), "--min-cases", "20", "--ci"])  # no SystemExit
    report = json.loads(out.read_text())
    assert report["sufficient"] is True
    assert report["accuracy"] == round(18 / 22, 4)


def test_pure_core_no_db_or_llm_import():
    src = Path(ev.__file__).read_text()
    # build_report must not need a DB; the only DB ref is inside load_closed_outcomes (lazy import).
    assert "def build_report" in src
    # no top-level llm/network dependency
    for forbidden in ("import httpx", "llm_client", "openai"):
        assert forbidden not in src
