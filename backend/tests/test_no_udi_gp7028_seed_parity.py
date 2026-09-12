"""Parity guard for Norway UDI GP7028 (third real fillable form).

Mirrors test_choice_seed_parity.py: the seed's radio rows must rebuild CHOICE_GROUPS via
load_choice_groups. Also locks the seed to the committed 232-field AcroForm artifact and to
the nightly seed/prod parity manifest counts.

DB-free: parses the migration SQL; reads the committed PDF + NDJSON fixtures.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

from pypdf import PdfReader

from backend.app.services import fact_dictionary as fd
from backend.app.services import form_prefill_service as fps

_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION = _ROOT / "supabase" / "migrations" / "20261143000000_no_udi_gp7028_fields.sql"
_PDF = _ROOT / "docs" / "form-autofill" / "artifacts" / "no_udi_gp7028.pdf"
_NDJSON = _ROOT / "docs" / "form-autofill" / "artifacts" / "no_udi_gp7028_acroform_fields.ndjson"
_MANIFEST = _ROOT / "scripts" / "seed_prod_parity_manifest.json"
FORM = "NO_udi_gp7028_v2024"

_ROW = re.compile(
    r"'NO_udi_gp7028_v2024',\s*'[^']*',\s*'NO',\s*'skilled_worker',\s*"
    r"'([^']+)',\s*'[^']*',\s*'([^']+)',\s*(?:'([^']*)'|NULL),\s*(TRUE|FALSE),\s*"
    r"'(text|single_radio)',\s*(?:'({.*?})'|NULL)",
)


def _seed_rows():
    text = _MIGRATION.read_text(encoding="utf-8")
    out = []
    for field_id, vault, fmt, _exact, kind, spec_json in _ROW.findall(text):
        row = {
            "form_field_id": field_id,
            "vault_field_path": vault,
            "field_kind": kind,
            "format_rule": fmt or None,
            "transform_spec": json.loads(spec_json) if spec_json else None,
        }
        out.append(row)
    return out


def _fact_governs(vault_path: str) -> bool:
    for f in fd._FACTS:
        if f.prefill_source and f.prefill_source.split(".")[-1] == vault_path:
            return True
        if vault_path in f.field_ids:
            return True
    return False


def test_migration_exists_and_delete_is_kind_scoped():
    assert _MIGRATION.exists()
    sql = _MIGRATION.read_text(encoding="utf-8")
    assert "WHERE form_id = 'NO_udi_gp7028_v2024'" in sql
    assert "field_kind IN ('text', 'single_radio')" in sql
    # Unscoped `WHERE form_id = ...` with no kind filter is the FR/ES wipe hazard.
    assert re.search(
        r"DELETE FROM public\.form_field_mappings\s+WHERE form_id = 'NO_udi_gp7028_v2024'\s*;",
        sql,
    ) is None


def test_seed_rebuilds_choice_groups():
    rows = [r for r in _seed_rows() if r["field_kind"] == "single_radio"]
    assert len(rows) == 2
    rebuilt = fps.load_choice_groups(FORM, rows)
    assert rebuilt == fps.CHOICE_GROUPS[FORM]


def test_manifest_counts_match_seed():
    rows = _seed_rows()
    by_kind: dict[str, list[str]] = {}
    for r in rows:
        by_kind.setdefault(r["field_kind"], []).append(r["form_field_id"])
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))["form_field_mappings"][FORM]
    assert set(by_kind["text"]) == set(manifest["text"])
    assert set(by_kind["single_radio"]) == set(manifest["single_radio"])
    assert len(manifest["text"]) == 11
    assert len(manifest["single_radio"]) == 2


def test_every_seeded_field_is_a_real_acroform_name_and_governed():
    ndjson_names = {json.loads(line)["name"] for line in _NDJSON.read_text(encoding="utf-8").splitlines() if line}
    pdf_names = set(PdfReader(io.BytesIO(_PDF.read_bytes())).get_fields() or {})
    assert len(ndjson_names) == 232
    assert ndjson_names == pdf_names
    rows = _seed_rows()
    assert len(rows) == 13
    for r in rows:
        assert r["form_field_id"] in pdf_names, r["form_field_id"]
        assert _fact_governs(r["vault_field_path"]), r["vault_field_path"]


def test_real_pdf_fill_lands_governed_subset():
    mappings = [
        {
            "form_field_id": r["form_field_id"],
            "form_field_label": r["form_field_id"],
            "vault_field_path": r["vault_field_path"],
            "format_rule": r["format_rule"],
            "exact_match_required": False,
        }
        for r in _seed_rows()
        if r["field_kind"] == "text"
    ]
    profile = {
        "legal_last_name": "Diallo",
        "legal_first_name": "Awa",
        "date_of_birth": "1990-05-12",
        "place_of_birth": "Dakar",
        "nationality": "Senegalese",
        "passport_number": "ab 123 4567",
        "passport_expiry": "2031-03-01",
        "passport_country": "sn",
        "job_title": "Software Engineer",
        "employer_name": "Acme AS",
        "salary_amount": "650000",
        "gender": "female",
        "marital_status": "married",
    }
    field_values, report = fps.build_fill_plan(mappings, profile)
    choice_values, choice_report = fps.build_choice_fill(FORM, profile)
    field_values.update(choice_values)
    report.extend(choice_report)
    filled = fps.fill_acroform(_PDF.read_bytes(), field_values)
    report, _n, _unmapped = fps.reconcile_report_against_pdf(filled, report)
    assert not [f for f in report if f.status == fps.STATUS_NOT_IN_PDF]
    fields = PdfReader(io.BytesIO(filled)).get_fields() or {}
    assert str(fields["Family name"].get("/V")) == "Diallo"
    assert str(fields["Gender"].get("/V")) in ("/Female", "Female")
    assert str(fields["Marital status group 1"].get("/V")) in (
        "/Married / civil partner",
        "Married / civil partner",
    )
