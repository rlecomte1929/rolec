#!/usr/bin/env python3
"""
Create the runtime app schema (including policy_documents), then align Alembic state.

On **SQLite**, `database.init_db()` already creates canonical policy tables (same as runtime
DDL). Running `alembic upgrade head` would try to create them again and fail. So when the
`alembic_version` table is empty, this script runs `alembic stamp head` after `init_db()`.

On **Postgres** (or any non-SQLite URL), `alembic upgrade head` is used so migrations apply
normally. Ensure `policy_documents` and other prerequisites exist for your environment
(Supabase migrations, or run `init_db()` without DISABLE_RUNTIME_DDL).

Usage (from repository root):

  PYTHONPATH=. python backend/scripts/bootstrap_backend_database.py

If `DATABASE_URL` is unset, defaults to an absolute path: `<repo>/backend/relopass.db`.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _default_sqlite_url() -> str:
    path = (BACKEND_DIR / "relopass.db").resolve()
    return f"sqlite:///{path.as_posix()}"


def _alembic_revision(database: object) -> Optional[str]:
    try:
        with database.engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        return str(row[0]) if row else None
    except Exception:
        return None


def main() -> int:
    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = _default_sqlite_url()

    from backend.database import db  # noqa: E402 — after DATABASE_URL

    u = os.environ["DATABASE_URL"]
    print(f"DATABASE_URL={u.split('@')[-1] if '@' in u else u}")
    print("Running database.init_db() (runtime DDL)...")
    db.init_db()

    env = os.environ.copy()
    rev = _alembic_revision(db)
    dialect = db.engine.dialect.name

    if dialect == "sqlite" and rev is None:
        print(
            "SQLite: no alembic_version row — stamping head "
            "(canonical tables already created by init_db)."
        )
        subprocess.check_call(
            [sys.executable, "-m", "alembic", "stamp", "head"],
            cwd=str(BACKEND_DIR),
            env=env,
        )
    else:
        print("Running alembic upgrade head...")
        subprocess.check_call(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(BACKEND_DIR),
            env=env,
        )
    print("Done. Canonical policy tables should exist; run the audit script next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
