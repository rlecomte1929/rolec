from pathlib import Path
M = Path(__file__).resolve().parents[2] / "supabase/migrations/20261140000000_form_field_mappings_kind_transform.sql"

def test_migration_is_additive_only():
    sql = M.read_text().upper()
    assert "ADD COLUMN IF NOT EXISTS FIELD_KIND" in sql
    assert "ADD COLUMN IF NOT EXISTS TRANSFORM_SPEC" in sql
    for forbidden in ("DROP COLUMN", "RENAME COLUMN", "DROP TABLE", "CREATE TABLE", "ALTER COLUMN"):
        assert forbidden not in sql, f"first-slice migration must be additive only, found {forbidden}"

def test_migration_timestamp_beats_repo_max():
    ts = M.name[:14]
    others = [p.name[:14] for p in M.parent.glob("*.sql") if p.name != M.name]
    assert ts >= max(others), "migration timestamp must be at least the repo max"
