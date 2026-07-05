"""Regression guard for the SQLAlchemy `:param::type` bind-cast anti-pattern in the
employee quote-request INSERT (found in the 2026-07-05 admin audit).

`text("... :cats::text[] ...")` makes SQLAlchemy register the WRONG bind name and leave
a literal `:cats::text[]` in the emitted SQL, so the INSERT is malformed at execution
(param mismatch / Postgres error) — a 500 on a real employee action. The fix is the
equivalent `CAST(:cats AS text[])`, which binds correctly. See
reference_sqlalchemy_jsonb_bind_cast_500.
"""
import inspect
import re

from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from backend.app.routers import employee_quotes


def test_no_bind_then_cast_antipattern_in_employee_quotes():
    """No `:<name>::<type>` occurrences — that form mis-binds under SQLAlchemy text()."""
    src = inspect.getsource(employee_quotes)
    offenders = re.findall(r":\w+::\w", src)
    assert not offenders, f"bind-then-cast anti-pattern (mis-binds on Postgres): {offenders}"


def test_cast_form_binds_the_param_name_correctly():
    """The CAST(:cats AS text[]) form must register `cats` as a bind and emit the
    psycopg2 %(cats)s placeholder (proving the param actually reaches Postgres)."""
    good = text("INSERT INTO quote_requests (service_categories) VALUES (CAST(:cats AS text[]))")
    assert list(good._bindparams.keys()) == ["cats"]
    assert "%(cats)s" in str(good.compile(dialect=postgresql.dialect()))

    # And prove the old form was genuinely broken (does NOT bind `cats`).
    bad = text("INSERT INTO quote_requests (service_categories) VALUES (:cats::text[])")
    assert "cats" not in bad._bindparams
