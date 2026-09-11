"""Parity guard: the FR/ES radio choice rows seeded as data (form-onboarding Phase 1b) must rebuild
`CHOICE_GROUPS` in `form_prefill_service.py` 1:1. `load_choice_groups` (Task 3) reads field_kind ∈
{single_radio, checkbox_option} rows and falls back to the in-code CHOICE_GROUPS when the DB carries
none — this test proves the seed migration (20261142000000) is a faithful data mirror of the code
fallback, the same way test_fr_cerfa_real_acroform.py locks the text-field re-seed to reality.

DB-free: parses the migration SQL into the {form_field_id, vault_field_path, field_kind,
transform_spec} shape `load_choice_groups` expects, exactly as `mappings` would arrive from a real
`form_field_mappings` query.
"""
import json
import re
from pathlib import Path

from backend.app.services import form_prefill_service as fps

_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION = _ROOT / "supabase" / "migrations" / "20261142000000_seed_fr_es_radio_choice_rows.sql"

# One INSERT row: form_id, form_name, corridor_to, visa_type, form_field_id, form_field_label,
# vault_field_path, field_kind, transform_spec (jsonb literal as its own quoted string).
_ROW = re.compile(
    r"'([^']+)',\s*'[^']*',\s*'[^']*',\s*'[^']*',\s*"
    r"'([^']+)',\s*'[^']*',\s*'([^']+)',\s*'(single_radio|checkbox_option)',\s*'({.*?})'",
)


def _seed_rows(form_id):
    """Rows for one form_id, parsed from the seed migration, shaped for load_choice_groups."""
    text = _MIGRATION.read_text(encoding="utf-8")
    out = []
    for fid, field_id, vault, kind, spec_json in _ROW.findall(text):
        if fid != form_id:
            continue
        out.append({
            "form_field_id": field_id,
            "vault_field_path": vault,
            "field_kind": kind,
            "transform_spec": json.loads(spec_json),
        })
    return out


def test_migration_exists_and_seeds_both_forms():
    assert _MIGRATION.exists(), "seed migration missing"
    for form_id in ("FR_cerfa_14571_v2024", "ES_ex17_v2024"):
        assert _seed_rows(form_id), f"no seeded choice rows parsed for {form_id}"


def test_seed_rebuilds_choice_groups_for_fr_and_es():
    for form_id in ("FR_cerfa_14571_v2024", "ES_ex17_v2024"):
        rows = _seed_rows(form_id)
        rebuilt = fps.load_choice_groups(form_id, rows)
        assert rebuilt == fps.CHOICE_GROUPS[form_id], f"{form_id} seed != code CHOICE_GROUPS"
