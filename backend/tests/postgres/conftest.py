"""[AIQ-1852] Schema for the Postgres lane — built from the MIGRATIONS, not from the models.

WHY THIS FILE IS NOT JUST `Base.metadata.create_all`
-----------------------------------------------------
Adding a `postgres:16` service and calling `create_all` would have caught nothing. Measured
on 2026-08-16 against the pre-#1865 commit `c35f696b` on a real Postgres 16:

    schema from create_all   ->  22 passed     (the bug is invisible)
    schema from the migration -> 16 failed     (the bug fires)

`create_all` renders the models, so the table always agrees with the model that drew it.
#1864's bug was precisely a DISAGREEMENT between the two: the migration declares

    id uuid PRIMARY KEY DEFAULT gen_random_uuid()

while the model said `Column(String)`. Render the model and you get `varchar`, the mismatch
vanishes, and every test passes while production 500s. A model-built schema can never
express a model/migration divergence — it is the one bug class it is structurally blind to.

So for tables whose production DDL lives in a migration, this fixture drops what `create_all`
built and replays the real migration file over it. That is what makes the lane load-bearing:
regress `_UUID` back to `String` in models.py and the regression test goes red, because the
table is still `uuid`.

ADDING A TABLE TO THIS LANE
---------------------------
Append to `_AUTHORITATIVE_DDL`: the migration file, and the tables it owns. The tables are
dropped (CASCADE) after `create_all` and recreated by replaying the file.

Deliberately NOT replaying the whole `supabase/migrations/` tree: 600+ files, ~147 of them
never applied to prod, and at least two destructive (CLAUDE.md, "Never run `supabase db push`
against prod"). Replaying all of them is neither safe nor meaningful. This is a curated list
of the tables actually exercised here.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = REPO_ROOT / "supabase" / "migrations"

#: (migration filename, tables that migration is the source of truth for)
_AUTHORITATIVE_DDL: List[Tuple[str, Tuple[str, ...]]] = [
    (
        "20261104000000_counsel_attestation_phase1.sql",
        (
            "corridor_attestation_signatures",
            "corridor_attestation_items",
            "corridor_attestation_requests",
        ),
    ),
]

#: Supabase ships these; a bare postgres:16 container does not. The migration GRANTs to them
#: and enables RLS, so they must exist or the replay aborts. Tests connect as the superuser,
#: which bypasses RLS — this lane checks type parity, not policy behaviour (that is what the
#: `integration` RLS suites against a real Supabase project are for).
_SUPABASE_ROLES = ("anon", "authenticated", "service_role")


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", "")


def _is_postgres(url: str) -> bool:
    return url.startswith("postgres://") or url.startswith("postgresql")


@pytest.fixture(scope="session", autouse=True)
def pg_schema():
    """Create every table, then make the migration-owned ones authoritative."""
    url = _database_url()
    if not _is_postgres(url):
        pytest.skip(
            "postgres lane needs a real Postgres DATABASE_URL "
            f"(got {url or '<unset>'!r}); run it via the backend-tests-postgres CI job"
        )

    # Imported here, not at module scope: importing backend.app.db binds the engine to
    # whatever DATABASE_URL held at import time, and skipping above must happen first.
    from backend.app.db import Base, engine

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        for role in _SUPABASE_ROLES:
            # postgres:16 has no Supabase roles. DO-block because CREATE ROLE has no
            # IF NOT EXISTS and the container is reused across a rerun.
            cur.execute(
                f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') "
                f"THEN CREATE ROLE {role} NOLOGIN; END IF; END $$;"
            )
        raw.commit()
    finally:
        raw.close()

    Base.metadata.create_all(bind=engine)

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        for filename, tables in _AUTHORITATIVE_DDL:
            path = MIGRATIONS / filename
            if not path.is_file():
                raise AssertionError(
                    f"{filename} is listed in _AUTHORITATIVE_DDL but does not exist. "
                    "If the migration was renamed, update this list — silently skipping it "
                    "would leave the lane green while testing a model-built schema, which is "
                    "exactly the blindness this file exists to remove."
                )
            cur.execute("DROP TABLE IF EXISTS " + ", ".join(tables) + " CASCADE;")
            cur.execute(path.read_text())
        raw.commit()
    finally:
        raw.close()

    yield engine
