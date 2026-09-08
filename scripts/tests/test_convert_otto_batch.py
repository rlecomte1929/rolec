"""Offline tests for scripts/convert_otto_batch.py."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "convert_otto_batch.py"


def _load():
    spec = importlib.util.spec_from_file_location("convert_otto_batch_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


c = _load()


def _write(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return path


def _run(tmp_path: Path, rows: list[dict], extra: list[str] | None = None) -> tuple[int, Path, Path]:
    inp = _write(tmp_path / "in.ndjson", rows)
    out = tmp_path / "out.ndjson"
    report = tmp_path / "report.json"
    argv = [str(inp), "--out", str(out), "--report", str(report)]
    if extra:
        argv.extend(extra)
    code = c.main(argv)
    return code, out, report


def test_parsers_profile_emits_both_spellings(tmp_path):
    rec = {
        "destination_country": "PT",
        "entity_topic_key": "residence_permit",
        "entity_title": "Residence permit",
        "fact_key": "processing_time",
        "fact_text": "Decision in 90 days.",
        "source_url": "https://imigrante.aima.gov.pt/x",
        "fact_type": "deadline",
        "confidence": "high",
        "applies_to": {"nationality": "non-EEA", "status": "professional"},
        "evidence_quote": "o prazo de decisão é de 90 dias",
    }
    code, out, _ = _run(tmp_path, [rec])
    assert code == 0
    got = json.loads(out.read_text().splitlines()[0])
    assert got["topic_key"] == got["entity_topic_key"] == got["entity"]["topic_key"] == "residence_permit"
    assert got["entity"]["destination_country"] == got["destination_country"] == "PT"
    assert got["entity"]["title"] == got["entity_title"]
    assert got["domain_area"] == got["entity"]["domain_area"]
    assert got["confidence_score"] == 0.9
    assert got["target_table"] == "requirement_facts"
    assert got["evidence_quote"] == rec["evidence_quote"]
    c.assert_paired(got)


def test_requirement_items_profile_renames(tmp_path):
    rec = {
        "fact_uid": "ve-ie-visa-1",
        "topic_key": "entry_visa",
        "destination_country_code": "IE",
        "title": "Irish entry visa",
        "fact_text": "A visa is required.",
        "source_url": "https://www.irishimmigration.ie/x",
        "applies_to": {"nationality": "non-EEA", "status": "family"},
    }
    code, out, report_path = _run(tmp_path, [rec])
    assert code == 0
    got = json.loads(out.read_text().splitlines()[0])
    report = json.loads(report_path.read_text())
    assert report["profile"] == "requirement_items"
    assert got["fact_key"] == "ve-ie-visa-1"
    assert got["entity_topic_key"] == "entry_visa"
    assert got["destination_country"] == "IE"
    assert got["entity_title"] == "Irish entry visa"


def test_nested_entity_flattens(tmp_path):
    rec = {
        "fact_key": "n1",
        "fact_text": "Need a permit.",
        "source_url": "https://example.gov/x",
        "applies_to": {"status": "professional", "nationality": "EEA"},
        "entity": {
            "destination_country": "PT",
            "topic_key": "residence_permit",
            "title": "Residence permit",
            "domain_area": "immigration",
        },
    }
    code, out, report_path = _run(tmp_path, [rec])
    assert code == 0
    got = json.loads(out.read_text().splitlines()[0])
    assert json.loads(report_path.read_text())["profile"] == "nested_entity"
    assert got["entity_title"] == "Residence permit"
    assert got["entity_topic_key"] == "residence_permit"
    assert got["destination_country"] == "PT"


def test_beam_profile_composes_and_preserves_count(tmp_path):
    rec = {
        "category": "eligibility",
        "fact_key": "b3_no_gb_1",
        "official_guidance": "You need a visa.",
        "actual_reality": "Sponsors file first.",
        "action_required": "Start 8 weeks out.",
        "source_url": "https://www.gov.uk/x",
        "corridor": "NO->GB",
        "applies_to": {"nationality": "EEA", "status": "professional"},
        "source": "gov.uk",
    }
    code, out, report_path = _run(tmp_path, [rec])
    assert code == 0
    report = json.loads(report_path.read_text())
    assert report["profile"] == "beam"
    assert report["records_in"] == report["records_out"] == 1
    got = json.loads(out.read_text().splitlines()[0])
    assert got["fact_type"] == "eligibility"
    assert "Official guidance:" in got["fact_text"]
    assert "Actual reality:" in got["fact_text"]
    assert "Action required:" in got["fact_text"]
    assert got["applies_to"]["_beam"]["official_guidance"] == "You need a visa."
    assert got["destination_country"] == "GB"


def test_status_required_and_default_status(tmp_path):
    rec = {
        "destination_country": "PT",
        "entity_topic_key": "residence_permit",
        "fact_key": "processing_time",
        "fact_text": "x",
        "source_url": "https://example.gov/x",
        "applies_to": {"nationality": "EEA"},
    }
    code, _, _ = _run(tmp_path, [rec])
    assert code == 1

    code2, out, _ = _run(tmp_path, [rec], extra=["--default-status", "professional"])
    assert code2 == 0
    got = json.loads(out.read_text().splitlines()[0])
    assert got["applies_to"]["status"] == "professional"


def test_nationality_not_derived_from_corridor(tmp_path):
    rec = {
        "destination_country": "IE",
        "entity_topic_key": "entry_visa",
        "fact_key": "visa-required",
        "fact_text": "Visa required.",
        "source_url": "https://www.irishimmigration.ie/x",
        "corridor": "ES-IE",
        "applies_to": {"nationality": "non-EEA", "status": "professional"},
    }
    code, out, _ = _run(tmp_path, [rec])
    assert code == 0
    got = json.loads(out.read_text().splitlines()[0])
    assert got["applies_to"]["nationality"] == "non-EEA"

    rec2 = {
        "destination_country": "IE",
        "entity_topic_key": "entry_visa",
        "fact_key": "visa-required-2",
        "fact_text": "Visa required.",
        "source_url": "https://www.irishimmigration.ie/x",
        "applies_to": {"status": "professional"},
    }
    code3, out2, report_path = _run(tmp_path, [rec2])
    assert code3 == 0
    got2 = json.loads(out2.read_text().splitlines()[0])
    assert "nationality" not in got2["applies_to"]
    report = json.loads(report_path.read_text())
    assert any("visa-required-2" in x for x in report["missing_nationality"])


def test_fact_type_mapping(tmp_path):
    base = {
        "destination_country": "PT",
        "entity_topic_key": "t",
        "fact_text": "x",
        "source_url": "https://example.gov/x",
        "applies_to": {"status": "any", "nationality": "EEA"},
    }
    code, out, report_path = _run(
        tmp_path,
        [
            {**base, "fact_key": "a", "fact_type": "timeline"},
            {**base, "fact_key": "b", "fact_type": "garbage"},
        ],
    )
    assert code == 0
    rows = [json.loads(l) for l in out.read_text().splitlines() if l]
    types = {r["fact_key"]: r["fact_type"] for r in rows}
    assert types["a"] == "deadline"
    assert types["b"] == "other"
    downs = json.loads(report_path.read_text())["downgrades"]["fact_type"]
    assert any(d["from"] == "garbage" for d in downs)


def test_domain_area_mapping(tmp_path):
    rec_ok = {
        "destination_country": "PT",
        "entity_topic_key": "t",
        "fact_key": "ok",
        "fact_text": "x",
        "source_url": "https://example.gov/x",
        "domain_area": "tax",
        "applies_to": {"status": "professional"},
    }
    rec_bad = {**rec_ok, "fact_key": "bad", "domain_area": "not-a-domain"}
    code, out, report_path = _run(tmp_path, [rec_ok, rec_bad])
    assert code == 0
    rows = {json.loads(l)["fact_key"]: json.loads(l) for l in out.read_text().splitlines() if l}
    assert rows["ok"]["domain_area"] == "tax"
    assert rows["bad"]["domain_area"] == "other"
    downs = json.loads(report_path.read_text())["downgrades"]["domain_area"]
    assert any(d["from"] == "not-a-domain" for d in downs)


def test_confidence_score(tmp_path):
    rec_high = {
        "destination_country": "PT",
        "entity_topic_key": "t",
        "fact_key": "h",
        "fact_text": "x",
        "source_url": "https://example.gov/x",
        "confidence": "high",
        "applies_to": {"status": "professional"},
    }
    rec_abs = {**rec_high, "fact_key": "m"}
    rec_abs.pop("confidence")
    code, out, _ = _run(tmp_path, [rec_high, rec_abs])
    assert code == 0
    rows = {json.loads(l)["fact_key"]: json.loads(l) for l in out.read_text().splitlines() if l}
    assert rows["h"]["confidence_score"] == 0.9
    assert rows["m"]["confidence_score"] == 0.6
    for r in rows.values():
        assert r["confidence_score"] is not None
        assert r["confidence_score"] != 0
        assert 0 < r["confidence_score"] <= 1


def test_no_fact_dropped_unconvertible_fails(tmp_path):
    good = {
        "destination_country": "PT",
        "entity_topic_key": "t",
        "fact_key": "ok",
        "fact_text": "x",
        "source_url": "https://example.gov/x",
        "applies_to": {"status": "professional"},
    }
    bad = {**good, "fact_key": "drop-me"}
    bad.pop("source_url")
    code, out, _ = _run(tmp_path, [good, bad])
    assert code == 1
    assert not out.is_file() or out.read_text() == ""


def test_paired_equality_guard_raises():
    broken = {
        "destination_country": "PT",
        "entity_topic_key": "residence_permit",
        "entity_title": "Residence permit",
        "fact_key": "x",
        "fact_text": "x",
        "source_url": "https://example.gov/x",
        "fact_type": "other",
        "confidence": "medium",
        "confidence_score": 0.6,
        "topic_key": "NOT-THE-SAME",
        "domain_area": "immigration",
        "entity": {
            "destination_country": "PT",
            "topic_key": "residence_permit",
            "domain_area": "immigration",
            "title": "Residence permit",
        },
    }
    with pytest.raises(c.ConvertError):
        c.assert_paired(broken)


def test_check_passes_then_mutated_fails(tmp_path):
    rec = {
        "destination_country": "PT",
        "entity_topic_key": "residence_permit",
        "entity_title": "Residence permit",
        "fact_key": "processing_time",
        "fact_text": "Decision in 90 days.",
        "source_url": "https://imigrante.aima.gov.pt/x",
        "applies_to": {"nationality": "non-EEA", "status": "professional"},
    }
    code, out, _ = _run(tmp_path, [rec])
    assert code == 0
    inp = tmp_path / "in.ndjson"
    check_code = c.main([str(inp), "--out", str(out), "--check"])
    assert check_code == 0
    mutated = json.loads(out.read_text().splitlines()[0])
    mutated["entity_title"] = "MUTATED"
    _write(out, [mutated])
    check_fail = c.main([str(inp), "--out", str(out), "--check"])
    assert check_fail == 1


def test_unknown_profile_exit_2(tmp_path):
    rec = {"foo": 1, "bar": 2}
    code, _, _ = _run(tmp_path, [rec])
    assert code == 2


@pytest.mark.integration
def test_integration_parity_b3_ve_ie_es_ie():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("applier-owned live parity")
    pytest.skip("applier-owned live parity")
