"""Regression: JSON params must bind under the Postgres dialect.

The historical ``f":{name}{_jb}"`` idiom rendered ``:param::jsonb`` on Postgres.
SQLAlchemy's text() bind-parameter regex has a negative lookahead for ``:``
after a placeholder, so ``:param`` immediately followed by ``::`` was NOT
treated as a bind — the literal ``:param`` reached Postgres and raised
``syntax error at or near ":"`` (a 500 on the employee policy-service-comparison
endpoint, which writes a resolved-policy row via upsert_resolved_assignment_policy).

These tests compile against the *postgresql* dialect on purpose: on SQLite
(``_jb == ""``) the bug is masked, which is why the curated SQLite CI suite
never caught it. They assert the param is bound, not left literal.
"""

from sqlalchemy import text
from sqlalchemy.dialects import postgresql


def _compiled(sql: str) -> str:
    return str(text(sql).compile(dialect=postgresql.dialect()))


def test_jbind_demonstrates_the_old_break():
    """Document the exact failure mode: ``:ctx::jsonb`` is left literal."""
    broken = _compiled("INSERT INTO t (a, ctx) VALUES (:a, :ctx::jsonb)")
    # :a binds, but :ctx::jsonb survives un-bound — this is the prod 500.
    assert "%(a)s" in broken
    assert ":ctx" in broken  # literal placeholder reached the driver


def test_jbind_binds_under_postgres(monkeypatch):
    """The fix: CAST(:param AS jsonb) binds correctly under Postgres.

    Forces the Postgres branch regardless of the test DB (CI runs SQLite, where
    the helper degrades to a bare ``:param`` and the bug can't surface). Asserts
    against backend.db.cases._jbind — the real helper on the reproduced
    policy-service-comparison 500 path. (backend.database._jbind is identical
    source but is a MagicMock under the test harness, so it can't be exercised
    here; it is covered by code parity.)
    """
    import backend.db.cases as cases_mod

    monkeypatch.setattr(cases_mod, "_is_sqlite", False)
    fixed = _compiled(f"INSERT INTO t (a, ctx) VALUES (:a, {cases_mod._jbind('ctx')})")
    assert "%(ctx)s" in fixed          # ctx is now a bound parameter
    assert ":ctx" not in fixed         # no literal placeholder survives
    assert "CAST" in fixed and "jsonb" in fixed


def test_jbind_sqlite_emits_bare_param(monkeypatch):
    """On SQLite (_is_sqlite True) the helper degrades to a bare ``:param``."""
    import backend.db.cases as cases_mod

    monkeypatch.setattr(cases_mod, "_is_sqlite", True)
    assert cases_mod._jbind("ctx") == ":ctx"


def test_jbind_postgres_wraps_in_cast(monkeypatch):
    import backend.db.cases as cases_mod

    monkeypatch.setattr(cases_mod, "_is_sqlite", False)
    assert cases_mod._jbind("ctx") == "CAST(:ctx AS jsonb)"


# ── Tree-wide guard ───────────────────────────────────────────────────────────
#
# The tests above prove the helper is correct. They cannot see a hand-written
# `:param::type` somewhere else in the tree — and there were EIGHT of them when
# this guard was added (AIQ-1780), including four `pgp_sym_decrypt(:enc::bytea…)`
# calls on the passport-decryption and GDPR-export paths, every one wrapped in a
# bare `except Exception` that swallowed the syntax error silently.
#
# Why the pattern is so easy to write and so hard to notice: SQLAlchemy's bind
# regex refuses to match a name followed by ':', so it BACKTRACKS and binds a
# truncated name — `:enc::bytea` binds a param called `en` and leaves the literal
# `:enc::bytea` in the SQL. Postgres then says `syntax error at or near ":"`.
# SQLite never sees a cast, so the curated CI suite cannot catch it.

import os
import re

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SCAN_ROOTS = ("backend/app", "backend/db", "backend/relopass")
_SCAN_FILES = ("backend/database.py",)

# `:name::` — a bind placeholder immediately followed by a Postgres cast.
_BAD = re.compile(r":[A-Za-z_][A-Za-z0-9_]*::")

# Prose that deliberately names the broken form to warn about it. Key = repo path,
# value = how many such mentions are expected. A NEW match in one of these files
# still fails, because the count moves.
_DOC_MENTIONS = {
    "backend/app/routers/feedback.py": 1,
    "backend/app/services/coordinator_session_store.py": 1,
    "backend/database.py": 1,
    "backend/db/cases.py": 1,
}


def _scan() -> dict:
    hits: dict = {}
    paths = []
    for root in _SCAN_ROOTS:
        for dirpath, _dirs, files in os.walk(os.path.join(_REPO_ROOT, root)):
            if "__pycache__" in dirpath:
                continue
            paths += [os.path.join(dirpath, f) for f in files if f.endswith(".py")]
    paths += [os.path.join(_REPO_ROOT, f) for f in _SCAN_FILES]

    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                n = len(_BAD.findall(fh.read()))
        except OSError:
            continue
        if n:
            hits[os.path.relpath(path, _REPO_ROOT)] = n
    return hits


def test_no_unbound_postgres_cast_placeholders():
    """`:param::type` anywhere in the backend is a latent Postgres-only failure.

    Fix by writing `CAST(:param AS type)`. If your match is prose warning about
    the bug, add the file to _DOC_MENTIONS with its expected count.
    """
    unexpected = {
        path: n for path, n in _scan().items() if _DOC_MENTIONS.get(path) != n
    }
    assert unexpected == {}, (
        "Unbound Postgres cast placeholder(s) — SQLAlchemy binds a TRUNCATED name and "
        "leaves the literal `:param` in the SQL, so Postgres raises "
        'syntax error at or near ":". SQLite masks it. Use CAST(:param AS type). '
        f"Offenders {{path: count}}: {unexpected}"
    )
