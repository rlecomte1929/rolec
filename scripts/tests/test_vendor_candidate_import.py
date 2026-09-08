"""Converter + scoped promote helper for Otto vendor NDJSON.

No database. The converter runs on a fixture NDJSON; the lander is asserted through
mocked ``stage`` / ``promote`` so ``run_ids`` is always passed and ``--promote`` is not
on the CLI.
"""
from __future__ import annotations

import csv
import importlib.util
import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.imports.suppliers.parsers import EXPECTED_HEADER, SELF_DECLARED, source_for_url

REPO = Path(__file__).resolve().parents[2]


def _load(name: str):
    path = REPO / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


convert = _load("convert_vendor_ndjson_to_csv")
land = _load("land_vendor_candidates")


def _ndjson(path: Path, records: list[dict]) -> Path:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8",
    )
    return path


def test_header_matches_the_importer():
    assert convert.EXPECTED_HEADER == EXPECTED_HEADER


def test_origin_dest_from_bidirectional_and_arrow_corridors():
    paris = convert.corridor_pairs("FR-NO,NO-FR", country="FR")
    assert paris == ["NO-FR"], "dest token 2 must be the vendor's country (FR)"
    frankfurt = convert.corridor_pairs("FR↔DE, ES↔DE, NO↔DE", country="DE")
    assert frankfurt == ["FR-DE", "ES-DE", "NO-DE"]
    milan = convert.corridor_pairs("IT↔DE", country="IT")
    assert milan == ["DE-IT"]


def test_convert_sample_ndjson_blank_accreditation_and_unknown_domain(tmp_path):
    """One FIDI row (known domain), one missing accreditation, one unknown register host."""
    records = [
        {
            "external_id": "paris-movers-ags",
            "category": "movers",
            "city": "Paris",
            "country": "FR",
            "name": "AGS France",
            "website": "https://www.ags-globalsolutions.com",
            "source_name": "FIDI FAIM member directory",
            "source_url": "https://www.ags-globalsolutions.com",
            "corridor": "FR-NO,NO-FR",
            "accreditation_body": "FIDI",
            "accreditation_number": None,
            "accreditation_expiry": "2028",
            "accreditation_source_url": "https://www.fidi.org/find-fidi-affiliate/ags-france",
        },
        {
            "category": "banks",
            "country": "FR",
            "name": "BNP Paribas",
            "website": "https://group.bnpparibas",
            "source_name": "BNP Paribas non-residents page",
            "source_url": "https://group.bnpparibas/en/news/non-residents",
            "corridor": "FR-NO,NO-FR",
            "accreditation_body": None,
            "accreditation_number": None,
            "accreditation_expiry": None,
            "accreditation_source_url": None,
        },
        {
            "category": "legal_admin",
            "country": "ES",
            "name": "Garrigues",
            "website": "https://www.garrigues.com",
            "source_name": "Censo de letrados",
            "source_url": "https://www.garrigues.com/en_GB/services",
            "corridor": "ES-IE,IE-ES",
            "accreditation_body": "Ilustre Colegio de la Abogacia de Madrid",
            "accreditation_number": None,
            "accreditation_expiry": None,
            "accreditation_source_url": "https://www.abogacia.es/servicios-abogacia/censo-de-letrados/",
        },
    ]
    inp = _ndjson(tmp_path / "vendors.ndjson", records)
    out = tmp_path / "vendors.csv"
    assert convert.main([str(inp), "--out", str(out)]) == 0

    with out.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == EXPECTED_HEADER
        rows = list(reader)

    by_name = {r["company_name"]: r for r in rows}
    ags = by_name["AGS France"]
    assert ags["corridor"] == "NO-FR"
    assert ags["service_category"] == "movers"
    assert ags["website_url"] == "https://www.ags-globalsolutions.com"
    assert ags["source_url"] == "https://www.fidi.org/find-fidi-affiliate/ags-france"
    assert ags["accreditation_body"] == "FIDI"
    assert ags["accreditation_number"] == ""
    assert ags["accreditation_expiry"] == "2028"
    assert source_for_url(ags["source_url"]).name != SELF_DECLARED

    bnp = by_name["BNP Paribas"]
    assert bnp["accreditation_body"] == ""
    assert bnp["accreditation_number"] == ""
    assert bnp["accreditation_expiry"] == ""
    assert bnp["source_url"] == "https://group.bnpparibas/en/news/non-residents"

    garrigues = by_name["Garrigues"]
    assert garrigues["corridor"] == "IE-ES"
    assert garrigues["source_url"].startswith("https://www.abogacia.es/")
    assert source_for_url(garrigues["source_url"]).name != SELF_DECLARED

    _rows, unknown, skips = convert.convert(records)
    assert skips == []
    assert "abogacia.es" not in unknown
    assert "fidi.org" not in unknown
    assert any("bnpparibas" in h for h in unknown)


def test_never_invents_accreditation_from_adjacent_fields():
    rec = {
        "name": "No Acc Ltd",
        "category": "movers",
        "country": "IE",
        "corridor": "ES-IE",
        "website": "https://example.com",
        "source_url": "https://www.fidi.org/x",
        "notes": "FIDI 12345 expires 2029",
        "legal_name": "No Acc Limited 999",
        "external_id": "acc-should-not-copy",
    }
    rows, skip = convert.convert_record(rec)
    assert skip is None
    assert rows[0]["accreditation_body"] == ""
    assert rows[0]["accreditation_number"] == ""
    assert rows[0]["accreditation_expiry"] == ""


def test_land_always_passes_run_ids_and_never_exposes_promote_flag():
    src = (REPO / "scripts" / "land_vendor_candidates.py").read_text(encoding="utf-8")
    assert 'add_argument("--promote"' not in src
    assert 'add_argument("--promote"' not in inspect.getsource(land.main)
    assert "from scripts.import_supplier_candidates" not in src

    captured: dict = {}

    def fake_stage(conn, candidates, *, dry_run):
        captured["stage_dry_run"] = dry_run
        captured["n_candidates"] = len(candidates)
        return (
            [
                SimpleNamespace(run_id="run-aaa", corridor="NO-FR", staged=1),
                SimpleNamespace(run_id="run-bbb", corridor="IE-ES", staged=2),
            ],
            [],
        )

    def fake_promote(session, *, dry_run, run_ids=None):
        captured["promote_dry_run"] = dry_run
        captured["run_ids"] = run_ids
        assert run_ids is not None, "promote() must never be called without run_ids"
        return (2, 0, [])

    results, rejections, run_ids, promo = land.land(
        [object(), object()],
        conn=object(),
        session=object(),
        dry_run=True,
        stage_fn=fake_stage,
        promote_fn=fake_promote,
    )
    assert rejections == []
    assert run_ids == ["run-aaa", "run-bbb"]
    assert captured["run_ids"] == ["run-aaa", "run-bbb"]
    assert captured["stage_dry_run"] is True
    assert captured["promote_dry_run"] is True
    assert promo == (2, 0, [])
    assert results[0].run_id == "run-aaa"


def test_land_passes_empty_run_ids_rather_than_omitting_the_kwarg():
    """A dry-run stage writes no runs. Passing [] is scoped (promotes nothing); omitting
    run_ids would promote every pending row in the table."""

    def fake_stage(conn, candidates, *, dry_run):
        return ([SimpleNamespace(run_id=None), SimpleNamespace(run_id="")], [])

    seen = {}

    def fake_promote(session, *, dry_run, run_ids=None):
        seen["run_ids"] = run_ids
        return (0, 0, [])

    _, _, run_ids, promo = land.land(
        [],
        conn=object(),
        session=object(),
        dry_run=True,
        stage_fn=fake_stage,
        promote_fn=fake_promote,
    )
    assert run_ids == []
    assert seen["run_ids"] == []
    assert promo == (0, 0, [])


def test_land_apply_forwards_dry_run_false_with_the_same_run_ids():
    def fake_stage(conn, candidates, *, dry_run):
        assert dry_run is False
        return ([SimpleNamespace(run_id="only-this-batch")], [])

    def fake_promote(session, *, dry_run, run_ids=None):
        assert dry_run is False
        assert run_ids == ["only-this-batch"]
        return (4, 1, ["note"])

    _, _, run_ids, promo = land.land(
        [object()],
        conn=object(),
        session=object(),
        dry_run=False,
        stage_fn=fake_stage,
        promote_fn=fake_promote,
    )
    assert run_ids == ["only-this-batch"]
    assert promo == (4, 1, ["note"])


def test_cli_rejects_promote_flag():
    with pytest.raises(SystemExit):
        land.main(["harvest.csv", "--promote"])
