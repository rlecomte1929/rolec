from pathlib import Path
M = Path(__file__).resolve().parents[2] / "supabase/migrations/20261140000000_form_field_mappings_kind_transform.sql"

def test_migration_is_additive_only():
    sql = M.read_text().upper()
    assert "ADD COLUMN IF NOT EXISTS FIELD_KIND" in sql
    assert "ADD COLUMN IF NOT EXISTS TRANSFORM_SPEC" in sql
    for forbidden in ("DROP COLUMN", "RENAME COLUMN", "DROP TABLE", "CREATE TABLE", "ALTER COLUMN"):
        assert forbidden not in sql, f"first-slice migration must be additive only, found {forbidden}"

def test_migration_timestamp_is_unique():
    ts = M.name[:14]
    same = [p.name for p in M.parent.glob("*.sql") if p.name[:14] == ts]
    assert same == [M.name], "migration timestamp must not collide with another file"
