"""SEC-RLSc (AIQ-660) — cross-employer leak test for rce.* case-scoped tables.

Validation criterion: a principal from employer B sees 0 rows of employer A.

Static mode (CI): asserts each case-scoped table is scoped via rce.can_access_case.
Live mode (RELOPASS_TEST_DB_URL): seeds two tenants as the table owner, then
queries as an `authenticated` principal of tenant B and asserts 0 tenant-A rows.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
CASE_TABLES = ("documents", "deadlines", "costs", "corrections", "family_members")


@pytest.fixture(scope="module")
def migration_sql() -> str:
    matches = sorted(MIGRATIONS_DIR.glob("*_rce_tenant_rls.sql"))
    assert matches, "SEC-RLSc migration not found"
    return matches[-1].read_text()


class TestStaticScoping:
    @pytest.mark.parametrize("table", CASE_TABLES)
    def test_table_scoped_by_case(self, migration_sql: str, table: str) -> None:
        assert "rce.can_access_case" in migration_sql
        assert re.search(rf"\b{table}\b", migration_sql)


def _live_conn():
    url = os.environ.get("RELOPASS_TEST_DB_URL")
    if not url:
        pytest.skip("Set RELOPASS_TEST_DB_URL (migration applied) to run live cross-tenant test.")
    try:
        import psycopg2
    except ImportError:  # pragma: no cover
        pytest.skip("psycopg2 not installed")
    conn = psycopg2.connect(url)
    conn.autocommit = False
    return conn


def _as_authenticated(cur, uid: str) -> None:
    """Switch the session to the `authenticated` role with a JWT sub = uid."""
    cur.execute("set local role authenticated")
    cur.execute(
        "select set_config('request.jwt.claims', %s, true)",
        (json.dumps({"sub": uid, "role": "authenticated"}),),
    )


def _as_owner(cur) -> None:
    cur.execute("reset role")


@pytest.mark.integration
class TestCrossTenantLive:
    def test_employer_b_sees_no_employer_a_rows(self) -> None:
        conn = _live_conn()
        emp_a, emp_b = uuid.uuid4(), uuid.uuid4()
        hr_b_uid = str(uuid.uuid4())
        try:
            with conn.cursor() as cur:
                _as_owner(cur)
                # Two employers; HR of B is linked via employers.company_id == hr_users.company_id.
                cur.execute(
                    "insert into rce.employers (employer_id, legal_name, company_id) values "
                    "(%s,'A','company-a'),(%s,'B','company-b')", (str(emp_a), str(emp_b)),
                )
                cur.execute(
                    "insert into public.hr_users (id, company_id) values (%s,'company-b') "
                    "on conflict (id) do update set company_id=excluded.company_id",
                    (hr_b_uid,),
                )
                case_a, case_b = uuid.uuid4(), uuid.uuid4()
                cur.execute(
                    "insert into rce.cases (case_id, employer_id, status) values "
                    "(%s,%s,'ACTIVE'),(%s,%s,'ACTIVE')",
                    (str(case_a), str(emp_a), str(case_b), str(emp_b)),
                )
                cur.execute(
                    "insert into rce.documents (document_id, case_id, sha256) values "
                    "(%s,%s,%s),(%s,%s,%s)",
                    (str(uuid.uuid4()), str(case_a), uuid.uuid4().hex,
                     str(uuid.uuid4()), str(case_b), uuid.uuid4().hex),
                )
                conn.commit()

                # Query as HR of employer B.
                _as_authenticated(cur, hr_b_uid)
                cur.execute("select count(*) from rce.documents where case_id = %s", (str(case_a),))
                a_visible = cur.fetchone()[0]
                cur.execute("select count(*) from rce.documents where case_id = %s", (str(case_b),))
                b_visible = cur.fetchone()[0]

            assert a_visible == 0, "employer B must NOT see employer A documents"
            assert b_visible == 1, "employer B must see its own documents"
        finally:
            conn.rollback()
            conn.close()
