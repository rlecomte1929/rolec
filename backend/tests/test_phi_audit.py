"""SEC-RLSc (AIQ-660) — BIOMETRIC/CRIMINAL reads via rce.read_phi_field() are
logged to rce.phi_access_log; NONE reads and service/owner reads are not.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"


@pytest.fixture(scope="module")
def migration_sql() -> str:
    matches = sorted(MIGRATIONS_DIR.glob("*_rce_tenant_rls.sql"))
    assert matches, "SEC-RLSc migration not found"
    return matches[-1].read_text()


class TestPhiStatic:
    def test_phi_class_column_added(self, migration_sql: str) -> None:
        assert re.search(r"phi_class\s+text", migration_sql, re.IGNORECASE)
        assert "BIOMETRIC" in migration_sql and "CRIMINAL" in migration_sql

    def test_audit_sink_and_accessor_present(self, migration_sql: str) -> None:
        assert re.search(r"create\s+table\s+if\s+not\s+exists\s+rce\.phi_access_log",
                         migration_sql, re.IGNORECASE)
        assert re.search(r"function\s+rce\.read_phi_field", migration_sql, re.IGNORECASE)

    def test_does_not_write_read_to_audit_logs(self, migration_sql: str) -> None:
        # public.audit_logs.action_type CHECK forbids 'read'; ensure we don't write to it.
        # (A header comment may *mention* it; what matters is we never INSERT/UPDATE it.)
        assert not re.search(
            r"(insert\s+into|update)\s+public\.audit_logs", migration_sql, re.IGNORECASE
        ), "PHI reads must log to rce.phi_access_log, not public.audit_logs"


def _live_conn():
    url = os.environ.get("RELOPASS_TEST_DB_URL")
    if not url:
        pytest.skip("Set RELOPASS_TEST_DB_URL (migration applied) to run live PHI audit test.")
    try:
        import psycopg2
    except ImportError:  # pragma: no cover
        pytest.skip("psycopg2 not installed")
    return psycopg2.connect(url)


@pytest.mark.integration
class TestPhiAuditLive:
    def _seed_field(self, cur, phi_class: str) -> str:
        emp, case_, doc = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        field = uuid.uuid4()
        cur.execute("insert into rce.employers (employer_id, legal_name) values (%s,'A')", (str(emp),))
        cur.execute("insert into rce.cases (case_id, employer_id, status) values (%s,%s,'ACTIVE')",
                    (str(case_), str(emp)))
        cur.execute("insert into rce.documents (document_id, case_id, sha256) values (%s,%s,%s)",
                    (str(doc), str(case_), uuid.uuid4().hex))
        cur.execute(
            "insert into rce.extracted_fields "
            "(extracted_field_id, document_id, field_key, confidence, phi_class) "
            "values (%s,%s,'x',1.0,%s)", (str(field), str(doc), phi_class),
        )
        return str(field)

    def test_owner_reads_are_not_audited(self) -> None:
        conn = _live_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("reset role")
                field = self._seed_field(cur, "BIOMETRIC")
                conn.commit()
                cur.execute("select rce.read_phi_field(%s)", (field,))
                cur.execute("select count(*) from rce.phi_access_log where extracted_field_id=%s",
                            (field,))
                logged = cur.fetchone()[0]
            # owner (postgres) path must NOT log — only non-system principals are audited.
            assert logged == 0, "owner/service reads must not be audited"
        finally:
            conn.rollback(); conn.close()

    def test_none_class_never_logged(self) -> None:
        conn = _live_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("reset role")
                field = self._seed_field(cur, "NONE")
                conn.commit()
                cur.execute("select rce.read_phi_field(%s)", (field,))
                cur.execute("select count(*) from rce.phi_access_log where extracted_field_id=%s",
                            (field,))
                assert cur.fetchone()[0] == 0
        finally:
            conn.rollback(); conn.close()
