"""Unit tests for the migration-drift guard.

Focus is the #1708 regression: a migration whose version sits at or below the prod
ledger max can never apply (`db push` treats an out-of-order version as already
passed and skips it), yet every CI check went green because that direction was only
ever a warning.

The hard failures are scoped to migrations a change ADDS — the repo carries 100+
pre-existing below-max files and 5 already-duplicated versions, so an unscoped gate
would redden every migration PR for debt it did not create.

Pure stdlib + tmp files — no DB.
"""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_migration_drift as cmd  # noqa: E402


def _mkmigrations(tmp_path, *names):
    d = tmp_path / "migrations"
    d.mkdir(exist_ok=True)
    for n in names:
        (d / n).write_text("select 1;\n")
    return d


# ── split_dead_and_ahead — the core #1708 logic ────────────────────────────────


def test_version_above_ledger_max_is_ahead_not_dead():
    """Ordinary undeployed work: applies on the next push, must stay a warning."""
    applied = {"20261009000000": "case_assignments_canonical"}
    repo_only = [{"version": "20261010000000", "name": "brand_new"}]
    dead, ahead = cmd.split_dead_and_ahead(repo_only, applied)
    assert dead == []
    assert ahead == repo_only


def test_version_below_ledger_max_is_dead():
    """#1708: ES_IE seed at 20261004000000 vs ledger max 20261009000000."""
    applied = {"20261009000000": "case_assignments_canonical"}
    repo_only = [{"version": "20261004000000", "name": "seed_es_ie_immigration_corpus_docs"}]
    dead, ahead = cmd.split_dead_and_ahead(repo_only, applied)
    assert dead == repo_only
    assert ahead == []


def test_version_equal_to_ledger_max_is_dead():
    """Boundary: `db push` skips anything not strictly greater than the max."""
    applied = {"20261009000000": "winner"}
    repo_only = [{"version": "20261009000000", "name": "loser"}]
    dead, ahead = cmd.split_dead_and_ahead(repo_only, applied)
    assert [d["name"] for d in dead] == ["loser"]
    assert ahead == []


def test_empty_ledger_means_nothing_is_dead():
    """No rows at all → no max to be below; must not produce false positives."""
    repo_only = [{"version": "20200101000000", "name": "ancient"}]
    dead, ahead = cmd.split_dead_and_ahead(repo_only, {})
    assert dead == []
    assert ahead == repo_only


# ── find_duplicate_versions ────────────────────────────────────────────────────


def test_no_duplicates_on_clean_dir(tmp_path):
    d = _mkmigrations(tmp_path, "20261010000000_a.sql", "20261011000000_b.sql")
    assert cmd.find_duplicate_versions(d) == {}


def test_duplicate_versions_are_grouped(tmp_path):
    """Two files on one version: schema_migrations records one, the other is lost."""
    d = _mkmigrations(
        tmp_path,
        "20261004000000_catalog_destination_requests.sql",
        "20261004000000_cleanup_living_areas.sql",
        "20261011000000_unique.sql",
    )
    dups = cmd.find_duplicate_versions(d)
    assert list(dups) == ["20261004000000"]
    assert dups["20261004000000"] == [
        "catalog_destination_requests",
        "cleanup_living_areas",
    ]


def test_missing_dir_is_not_a_duplicate(tmp_path):
    assert cmd.find_duplicate_versions(tmp_path / "nope") == {}


def test_non_migration_filenames_are_ignored(tmp_path):
    d = _mkmigrations(tmp_path, "20261010000000_a.sql", "README.sql", "notes.txt")
    assert cmd.find_duplicate_versions(d) == {}


# ── parse_added_versions ───────────────────────────────────────────────────────


def test_parse_added_handles_paths_and_separators():
    raw = "supabase/migrations/20261010000000_a.sql\nsupabase/migrations/20261011000000_b.sql"
    assert cmd.parse_added_versions(raw) == {"20261010000000", "20261011000000"}


def test_parse_added_ignores_noise():
    assert cmd.parse_added_versions("") == set()
    assert cmd.parse_added_versions("not-a-migration.txt\n\n  \n") == set()


# ── main() — scoping is what keeps this shippable ──────────────────────────────


def _run_main(monkeypatch, tmp_path, *, applied, files, argv):
    d = _mkmigrations(tmp_path, *files)
    monkeypatch.setattr(cmd, "MIGRATIONS_DIR", d)
    monkeypatch.setattr(cmd, "query_applied_versions", lambda _url: applied)
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub")
    monkeypatch.setattr(sys, "argv", ["check_migration_drift.py"] + argv)
    return cmd.main()


def test_main_fails_when_the_PR_adds_a_dead_migration(monkeypatch, tmp_path):
    """The #1708 regression, end to end: adding a below-max migration fails CI."""
    rc = _run_main(
        monkeypatch, tmp_path,
        applied={"20261009000000": "winner"},
        files=["20261009000000_winner.sql", "20261004000000_es_ie_seed.sql"],
        argv=["--added", "supabase/migrations/20261004000000_es_ie_seed.sql"],
    )
    assert rc == 1


def test_main_passes_when_the_same_dead_file_is_pre_existing(monkeypatch, tmp_path):
    """Identical repo state, but the PR did not add it → audit warning, exit 0."""
    rc = _run_main(
        monkeypatch, tmp_path,
        applied={"20261009000000": "winner"},
        files=["20261009000000_winner.sql", "20261004000000_es_ie_seed.sql"],
        argv=[],
    )
    assert rc == 0


def test_main_passes_when_the_PR_adds_a_correctly_stamped_migration(monkeypatch, tmp_path):
    rc = _run_main(
        monkeypatch, tmp_path,
        applied={"20261009000000": "winner"},
        files=["20261009000000_winner.sql", "20261010000000_good.sql"],
        argv=["--added", "supabase/migrations/20261010000000_good.sql"],
    )
    assert rc == 0


def test_main_fails_when_the_PR_adds_a_colliding_version(monkeypatch, tmp_path):
    rc = _run_main(
        monkeypatch, tmp_path,
        applied={"20261009000000": "winner"},
        files=["20261009000000_winner.sql", "20261010000000_a.sql", "20261010000000_b.sql"],
        argv=["--added", "supabase/migrations/20261010000000_b.sql"],
    )
    assert rc == 1


def test_main_still_fails_on_direction_a_drift(monkeypatch, tmp_path):
    """Pre-existing behaviour must not regress: prod version with no repo file."""
    rc = _run_main(
        monkeypatch, tmp_path,
        applied={"20261009000000": "winner", "20260101000000": "ghost"},
        files=["20261009000000_winner.sql"],
        argv=[],
    )
    assert rc == 1


def test_no_db_mode_needs_no_database_url(monkeypatch, tmp_path):
    """The duplicate check must work with DATABASE_URL unset — it is ungated in CI."""
    d = _mkmigrations(tmp_path, "20261010000000_a.sql", "20261010000000_b.sql")
    monkeypatch.setattr(cmd, "MIGRATIONS_DIR", d)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(
        sys, "argv",
        ["check_migration_drift.py", "--no-db", "--added",
         "supabase/migrations/20261010000000_b.sql"],
    )
    assert cmd.main() == 1


def test_no_db_mode_audit_only_is_green(monkeypatch, tmp_path):
    """Without --added the pre-existing duplicates warn but do not fail."""
    d = _mkmigrations(tmp_path, "20261010000000_a.sql", "20261010000000_b.sql")
    monkeypatch.setattr(cmd, "MIGRATIONS_DIR", d)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(sys, "argv", ["check_migration_drift.py", "--no-db"])
    assert cmd.main() == 0
