"""Offline tests for scripts/verify_batch_quotes.py (Brief B graft)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "scripts" / "verify_batch_quotes.py"


def _load():
    spec = importlib.util.spec_from_file_location("verify_batch_quotes_under_test", MODULE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


vbq = _load()

QUOTE = "o prazo de decisão é de 90 dias"
URL = "https://imigrante.sef.pt/visados/residencia"


def _batch(tmp_path: Path, rows: list[dict], name: str = "facts.ndjson") -> Path:
    d = tmp_path / "batch"
    d.mkdir()
    (d / name).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return d


def _row(**over) -> dict:
    rec = {
        "destination_country": "PT",
        "entity_topic_key": "residence_permit",
        "fact_key": "processing_time",
        "source_url": URL,
        "evidence_quote": QUOTE,
        "applies_to": {"nationality": "EEA"},
    }
    rec.update(over)
    return rec


def test_report_and_grounding_dir_without_network(tmp_path):
    rec = _row()
    batch = _batch(tmp_path, [rec])
    gdir = tmp_path / "grounding"
    gdir.mkdir()
    (gdir / "page.txt").write_text(f"intro {QUOTE} outro", encoding="utf-8")
    (gdir / "index.json").write_text(json.dumps({URL: "page.txt"}), encoding="utf-8")
    report = tmp_path / "quotes.json"
    code = vbq.main(
        [str(batch), "--grounding-dir", str(gdir), "--report", str(report)]
    )
    assert code == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["sources"][0]["status"] == "confirmed"
    assert payload["sources"][0]["grounded_by"] == "browser_grounded"
    assert payload["needs_grounding"] == []
    assert "--report" in MODULE.read_text(encoding="utf-8")
    assert "--grounding-dir" in MODULE.read_text(encoding="utf-8")


def test_unreachable_lands_on_needs_grounding(tmp_path, monkeypatch):
    rec = _row()
    batch = _batch(tmp_path, [rec])
    report = tmp_path / "quotes.json"

    def _no_net(_url: str) -> bytes:
        raise RuntimeError("offline")

    monkeypatch.setattr(vbq, "fetch", _no_net)
    code = vbq.main([str(batch), "--report", str(report)])
    assert code == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["sources"][0]["status"] == "unreachable"
    assert payload["needs_grounding"][0]["source_url"] == URL


def test_stamp_never_sets_researcher_flag_for_browser_grounded(tmp_path):
    rec = _row()
    batch = _batch(tmp_path, [rec])
    gdir = tmp_path / "grounding"
    gdir.mkdir()
    (gdir / "page.txt").write_text(QUOTE, encoding="utf-8")
    (gdir / "index.json").write_text(json.dumps({URL: "page.txt"}), encoding="utf-8")
    code = vbq.main(
        [str(batch), "--grounding-dir", str(gdir), "--stamp"]
    )
    assert code == 0
    got = json.loads((batch / "facts.ndjson").read_text().splitlines()[0])
    assert got["applies_to"].get("quote_verbatim_confirmed") is False


def test_target_selects_named_ndjson(tmp_path):
    rec = _row()
    batch = _batch(tmp_path, [rec], name="facts.ndjson")
    other = _row(fact_key="other", evidence_quote="not on page")
    (batch / "clean.ndjson").write_text(json.dumps(rec) + "\n", encoding="utf-8")
    (batch / "facts.ndjson").write_text(json.dumps(other) + "\n", encoding="utf-8")
    gdir = tmp_path / "grounding"
    gdir.mkdir()
    (gdir / "page.txt").write_text(QUOTE, encoding="utf-8")
    (gdir / "index.json").write_text(json.dumps({URL: "page.txt"}), encoding="utf-8")
    report = tmp_path / "quotes.json"
    code = vbq.main(
        [
            str(batch),
            "--target",
            str(batch / "clean.ndjson"),
            "--grounding-dir",
            str(gdir),
            "--report",
            str(report),
        ]
    )
    assert code == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["sources"][0]["status"] == "confirmed"
    assert payload["ndjson"].endswith("clean.ndjson")
