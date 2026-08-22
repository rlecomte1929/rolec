#!/usr/bin/env python3
"""Fail when the ORM declares a column production does not have.

WHY THIS EXISTS — an outage, 2026-08-22, 09:44–17:13 UTC (7h29m).

`GET /api/public/corridor-requirements` returned HTTP 500 for both flagship corridors
(ES→IE and FR→NO) with

    sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedColumn)
    column requirement_items.verified_by does not exist

Commit `4b3b11d4` merged `supabase/migrations/20261117000000_...sql` and the matching
`verified_by = Column(Text)` / `verified_at = Column(DateTime)` in `backend/app/models.py`
together. Migrations here are applied out of band (CLAUDE.md, "Migration discipline"), and
this one never was. It was found by accident, hours later, while auditing something else.

WHY AN ORM COLUMN IS THE WORST FORM OF THIS BUG. A stray `SELECT ft.sections` breaks one
route. A mapped column enters the SELECT list of EVERY query on that table, so every read
path 500s at once — and nothing in the diff looks like a query.

WHAT THIS IS *NOT* A DUPLICATE OF. `scripts/check_column_read_before_apply.py` (hardened in
#2001 to recognise `= Column(` / `= mapped_column(` / `: Mapped[...]`) is the pre-merge half.
It is static by design and it fires only when a migration file and the read are in the SAME
PR:

    migrations = [p for p in changed if p.startswith("supabase/migrations/") ...]
    if not migrations:
        return 0

That is the case we are told NOT to produce. Follow the prescribed split — migration first,
operator applies, then the code that reads it — and the second merge carries a bare
`Column()` with no migration beside it, which that guard structurally cannot see. It happened
six minutes after #2001 landed: #1998 added `case_id = Column(_UUID(...))` with no migration
in the PR, and the guard exited 0 without looking. It was safe only because the migration had
been applied an hour earlier — which no static check can know.

"Does production actually have this column?" is a question about production state. This
script asks production.

DIRECTION. Only `model declares → prod lacks` fails; that is the 500. Prod carrying columns
the ORM does not map is normal and stays silent — `suppliers`, `wizard_cases` and
`supplier_service_capabilities` all legitimately do.

NO ALLOWLIST, deliberately. There is no legitimate reason for the ORM to declare a column
production lacks; an allowlist would only re-open the hole. If a column is genuinely being
introduced, the migration goes first — that IS the escape hatch.

WHY AST AND NOT AN IMPORT. Importing `backend.app.models` pulls in `backend.app.db`, which
binds the engine to whatever `DATABASE_URL` holds at import time (see the note in
`backend/tests/postgres/conftest.py`). Parsing keeps this a dependency-light script that
cannot accidentally connect to the wrong database.

Exit codes:
  0 — every mapped column exists in the target database
  1 — a mapped column (or whole table) is missing; OR the parse found 0 models, OR the
      database reported 0 of them (either means the check examined nothing)
  2 — could not connect / query failed

Usage:
  DATABASE_URL=postgresql://... python scripts/check_model_schema_drift.py
  DATABASE_URL=postgresql://... python scripts/check_model_schema_drift.py --json
  DATABASE_URL=postgresql://... python scripts/check_model_schema_drift.py \
      --models /path/to/models.py       # for tests; defaults to backend/app/models.py
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODELS = REPO_ROOT / "backend" / "app" / "models.py"

# The schema the ORM maps into. Everything in models.py is unqualified, so it lands here.
SCHEMA = "public"

# One round trip: every column of every table in the schema. Cheaper and more robust than
# a query per model, and it lets a green run state how many tables it actually saw.
COLUMNS_SQL = """
SELECT table_name, column_name
FROM information_schema.columns
WHERE table_schema = %s;
"""


def parse_models(path: Path) -> Dict[str, Set[str]]:
    """Map ``{__tablename__: {column names}}`` from a SQLAlchemy models module.

    Recognises both the classic ``x = Column(...)`` and the 2.0 annotated
    ``x: Mapped[str] = mapped_column(...)`` forms, and honours an explicit first string
    argument (``x = Column("db_name", Text)``), which overrides the attribute name as the
    actual database column.
    """
    tree = ast.parse(path.read_text())
    models: Dict[str, Set[str]] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        tablename: str | None = None
        columns: Set[str] = set()

        for stmt in node.body:
            # `__tablename__ = "foo"`
            if (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and stmt.targets[0].id == "__tablename__"
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            ):
                tablename = stmt.value.value
                continue

            # `name = Column(...)` or `name: Mapped[...] = mapped_column(...)`
            target: str | None = None
            value = None
            if (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
            ):
                target, value = stmt.targets[0].id, stmt.value
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                target, value = stmt.target.id, stmt.value

            if target is None or not isinstance(value, ast.Call):
                continue

            func = value.func
            fname = getattr(func, "id", None) or getattr(func, "attr", None)
            if fname not in ("Column", "mapped_column"):
                continue

            # An explicit string first arg is the real column name.
            column = target
            for arg in value.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    column = arg.value
                    break
            columns.add(column)

        if tablename and columns:
            models.setdefault(tablename, set()).update(columns)

    return models


def fetch_live_columns(db_url: str) -> Dict[str, Set[str]]:
    """``{table_name: {column names}}`` for the mapped schema in the target database."""
    try:
        import psycopg2
    except ImportError:
        print(
            "psycopg2 not installed — `pip install psycopg2-binary` or run from the backend venv",
            file=sys.stderr,
        )
        sys.exit(2)

    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://") :]

    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
    except Exception as exc:  # connection / DNS / auth
        print(f"could not connect to DATABASE_URL: {exc}", file=sys.stderr)
        sys.exit(2)

    live: Dict[str, Set[str]] = {}
    try:
        with conn.cursor() as cur:
            cur.execute(COLUMNS_SQL, (SCHEMA,))
            for table, column in cur.fetchall():
                live.setdefault(table, set()).add(column)
    finally:
        conn.close()
    return live


def find_drift(
    models: Dict[str, Set[str]], live: Dict[str, Set[str]]
) -> Tuple[List[Tuple[str, str]], List[str]]:
    """Return ``(missing_columns, missing_tables)``.

    Pure function — no DB — so both failure paths are unit-testable without a database.
    ``missing_columns`` is ``[(table, column), ...]`` the ORM maps and the database lacks;
    ``missing_tables`` is every mapped table absent from the database entirely. Columns of
    a missing table are reported once as the table, not N times as columns.
    """
    missing_columns: List[Tuple[str, str]] = []
    missing_tables: List[str] = []

    for table in sorted(models):
        if table not in live:
            missing_tables.append(table)
            continue
        for column in sorted(models[table] - live[table]):
            missing_columns.append((table, column))

    return missing_columns, missing_tables


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail when the ORM declares a column the database does not have."
    )
    parser.add_argument("--json", action="store_true", help="Emit the drift as JSON.")
    parser.add_argument(
        "--models",
        default=str(DEFAULT_MODELS),
        help="Path to the SQLAlchemy models module (default: backend/app/models.py).",
    )
    args = parser.parse_args()

    models_path = Path(args.models)
    if not models_path.is_file():
        print(f"models module not found: {models_path}", file=sys.stderr)
        return 2

    models = parse_models(models_path)

    # A parse that finds nothing is the same output as a clean run. This guard's job is to
    # be believed when it is green, so it must be able to say what it examined — the same
    # rule check_rls_coverage.py, check_route_auth.py and check_compliance_claims.py apply.
    if not models:
        print(
            f"[model-schema-drift] FAIL — parsed 0 mapped tables from {models_path}. "
            "Either the file moved or the parser no longer recognises its shape; "
            "either way this check is examining nothing.",
            file=sys.stderr,
        )
        return 1

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2

    live = fetch_live_columns(db_url)
    missing_columns, missing_tables = find_drift(models, live)

    # Same reasoning as the 0-models guard, from the other side: if the database reported
    # none of our tables, every one is "missing" and the report is noise, not a finding.
    seen = [t for t in models if t in live]
    if not seen:
        print(
            f"[model-schema-drift] FAIL — the database reported none of the {len(models)} "
            f"mapped tables in schema '{SCHEMA}'. Wrong database, wrong schema, or the "
            "read-only role cannot see information_schema.",
            file=sys.stderr,
        )
        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "tables_mapped": len(models),
                    "tables_found": len(seen),
                    "missing_tables": missing_tables,
                    "missing_columns": [
                        {"table": t, "column": c} for t, c in missing_columns
                    ],
                },
                indent=2,
            )
        )

    if not missing_columns and not missing_tables:
        if not args.json:
            columns_checked = sum(len(models[t]) for t in seen)
            print(
                f"[model-schema-drift] OK — {columns_checked} mapped columns across "
                f"{len(seen)} tables all exist in '{SCHEMA}'."
            )
        return 0

    if not args.json:
        print(
            "[model-schema-drift] FAIL — the ORM maps schema the database does not have. "
            "Every query against these tables will raise UndefinedColumn in production.",
            file=sys.stderr,
        )
        for table in missing_tables:
            print(f"  MISSING TABLE   {SCHEMA}.{table}", file=sys.stderr)
        for table, column in missing_columns:
            print(f"  MISSING COLUMN  {SCHEMA}.{table}.{column}", file=sys.stderr)
        print(
            "\n  Almost always: a migration was merged but never applied. Apply it "
            "out-of-band and reconcile with `supabase migration repair` (CLAUDE.md, "
            "'Ledger reconciliation'). Do NOT make the model tolerant of the missing "
            "column — that hides the class of mistake.",
            file=sys.stderr,
        )

    return 1


if __name__ == "__main__":
    sys.exit(main())
