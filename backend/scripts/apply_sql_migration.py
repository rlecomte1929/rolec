#!/usr/bin/env python3
"""
Apply a SQL migration file using DATABASE_URL (from env or repo-root .env).

Requires a PostgreSQL URL (e.g. Supabase session or direct connection). If .env only
has sqlite, set DATABASE_URL temporarily or use: supabase db push --linked --include-all
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    in_single = False
    while i < len(sql):
        c = sql[i]
        if in_single:
            buf.append(c)
            if c == "'":
                # PostgreSQL escape: doubled single quote
                if i + 1 < len(sql) and sql[i + 1] == "'":
                    buf.append(sql[i + 1])
                    i += 2
                    continue
                in_single = False
            i += 1
            continue
        if c == "'":
            in_single = True
            buf.append(c)
            i += 1
            continue
        if c == ";":
            stmt = "".join(buf).strip()
            if stmt and not all(
                (ln.strip().startswith("--") or not ln.strip()) for ln in stmt.splitlines()
            ):
                statements.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    tail = "".join(buf).strip()
    if tail and not all(
        (ln.strip().startswith("--") or not ln.strip()) for ln in tail.splitlines()
    ):
        statements.append(tail)
    return statements


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)

    try:
        from dotenv import load_dotenv
    except ImportError:
        print("python-dotenv required", file=sys.stderr)
        return 1

    load_dotenv(root / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set (env or .env)", file=sys.stderr)
        return 1

    rel = sys.argv[1] if len(sys.argv) > 1 else None
    if not rel:
        print("usage: apply_sql_migration.py <path-to.sql>", file=sys.stderr)
        return 1

    path = Path(rel) if Path(rel).is_absolute() else root / rel
    if not path.is_file():
        print(f"not found: {path}", file=sys.stderr)
        return 1

    sql = path.read_text(encoding="utf-8")
    statements = _split_sql_statements(sql)
    if not statements:
        print("no statements parsed", file=sys.stderr)
        return 1

    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        print("sqlalchemy required", file=sys.stderr)
        return 1

    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        for idx, stmt in enumerate(statements, 1):
            conn.execute(text(stmt))
    print(f"Applied {len(statements)} statement(s) from {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
