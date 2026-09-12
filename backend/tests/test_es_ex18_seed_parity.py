"""Parity guard: the ES EX-18 seed must rebuild CHOICE_GROUPS 1:1 and only name real fields.

Mirrors test_choice_seed_parity.py for the third fillable government form. DB-free: parses
supabase/migrations/20261143000000_es_ex18_rce_acroform_fields.sql into the shape
load_choice_groups / build_fill_plan expect.
"""
import json
import re
from pathlib import Path

from backend.app.services import fact_dictionary as fd
from backend.app.services import form_prefill_service as fps

_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION = _ROOT / "supabase" / "migrations" / "20261143000000_es_ex18_rce_acroform_fields.sql"
_ARTIFACT = _ROOT / "docs" / "form-autofill" / "artifacts" / "es_ex18_acroform_fields.json"
FORM = "ES_ex18_v2024"

_TEXT = re.compile(
    r"'ES_ex18_v2024',\s*'[^']*',\s*'ES',\s*'eea_registration',\s*"
    r"'([^']+)',\s*'[^']*',\s*'([^']+)',\s*'([^']*)',\s*(TRUE|FALSE),\s*'text'",
)
_CHOICE = re.compile(
    r"'ES_ex18_v2024',\s*'[^']*',\s*'ES',\s*'eea_registration',\s*"
    r"'([^']+)',\s*'[^']*',\s*'([^']+)',\s*NULL,\s*(?:TRUE|FALSE),\s*"
    r"'(checkbox_option)',\s*'({.*?})'",
)


def _choice_rows():
    text = _MIGRATION.read_text(encoding="utf-8")
    out = []
    for field_id, vault, kind, spec_json in _CHOICE.findall(text):
        out.append({
            "form_field_id": field_id,
            "vault_field_path": vault,
            "field_kind": kind,
            "transform_spec": json.loads(spec_json),
        })
    return out


def _text_rows():
    text = _MIGRATION.read_text(encoding="utf-8")
    out = []
    for field_id, vault, fmt, exact in _TEXT.findall(text):
        out.append({
            "form_field_id": field_id,
            "vault_field_path": vault,
            "format_rule": fmt or None,
            "exact_match_required": exact.upper() == "TRUE",
            "field_kind": "text",
        })
    return out


def _fact_governs(vault_path: str) -> bool:
    for f in fd._FACTS:
        if f.prefill_source and f.prefill_source.split(".")[-1] == vault_path:
            return True
        if vault_path in f.field_ids:
            return True
    return False


def test_delete_is_scoped_to_form_and_kinds():
    text = _MIGRATION.read_text(encoding="utf-8")
    assert "WHERE form_id = 'ES_ex18_v2024'" in text
    assert "field_kind IN ('text', 'checkbox_option')" in text
    # Unscoped `WHERE form_id = '…'` without a kind filter would wipe sibling rows.
    assert re.search(
        r"DELETE FROM public\.form_field_mappings\s+WHERE form_id = 'ES_ex18_v2024'\s*;",
        text,
    ) is None


def test_seed_rebuilds_choice_groups_1to1():
    rows = _choice_rows()
    assert rows, "no checkbox_option rows parsed from the EX-18 seed"
    rebuilt = fps.load_choice_groups(FORM, rows)
    assert rebuilt == fps.CHOICE_GROUPS[FORM]


def test_every_seeded_id_is_a_real_acroform_field():
    data = json.loads(_ARTIFACT.read_text(encoding="utf-8"))
    real = {f["name"] for f in data["fields"]}
    seeded = [r["form_field_id"] for r in _text_rows() + _choice_rows()]
    assert seeded, "seed parsed no rows"
    bogus = sorted(n for n in seeded if n not in real)
    assert bogus == [], f"mapping field ids not in the real EX-18 AcroForm: {bogus}"


def test_every_vault_path_is_governed():
    paths = {r["vault_field_path"] for r in _text_rows() + _choice_rows()}
    ungoverned = sorted(p for p in paths if not _fact_governs(p))
    assert ungoverned == [], f"vault paths with no governing FactEntry: {ungoverned}"
