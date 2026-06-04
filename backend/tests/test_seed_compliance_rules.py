"""BL-Compliance.2 — seed test for the launch compliance rule set (AIQ-744).

Two-mode pattern (cf. test_compliance_tables_schema.py):

  * **Static mode (always runs):** parses the seed migration, asserts the 3
    expected rules are inserted and that every trigger_condition is valid JSON
    carrying the evaluator contract keys (type / field / operator). No DB.

  * **Live mode (skipped unless RELOPASS_TEST_DB_URL is set):** asserts the 3
    rules are present in the DB and that each trigger_condition is valid jsonb.

Validation criteria: "SELECT returns 3 rules; conditions parseable by evaluator."
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, Tuple

import pytest


EXPECTED_RULES: Tuple[str, ...] = (
    "permit_expiry_date",          # date_threshold field
    "days_present_in_host",        # day_count field
    "employer_registration_id",    # missing_field field
)

EXPECTED_TYPES: Tuple[str, ...] = ("date_threshold", "day_count", "missing_field")

CONTRACT_KEYS: Tuple[str, ...] = ("type", "field", "operator")

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "20260607010000_seed_compliance_rules.sql"
)


@pytest.fixture(scope="module")
def migration_sql() -> str:
    assert MIGRATION_PATH.exists(), (
        f"Seed migration missing: {MIGRATION_PATH}. Did BL-Compliance.2 land?"
    )
    return MIGRATION_PATH.read_text()


@pytest.fixture(scope="module")
def trigger_conditions(migration_sql: str) -> Tuple[Dict, ...]:
    # Extract every '{...}'::jsonb literal and parse it.
    raw = re.findall(r"'(\{.*?\})'::jsonb", migration_sql, re.DOTALL)
    return tuple(json.loads(r) for r in raw)


# ─────────────────────────────────────────────────────────────────────────────
# Static-mode tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSeedStatic:
    def test_inserts_into_compliance_rules(self, migration_sql: str) -> None:
        assert re.search(
            r"insert\s+into\s+public\.compliance_rules\b", migration_sql, re.IGNORECASE
        ), "Seed must INSERT INTO public.compliance_rules"

    def test_three_rules_seeded(self, trigger_conditions: Tuple[Dict, ...]) -> None:
        assert len(trigger_conditions) == 3, (
            f"Expected exactly 3 seeded rules, found {len(trigger_conditions)}"
        )

    def test_replay_safe(self, migration_sql: str) -> None:
        assert re.search(
            r"on\s+conflict\s*\(\s*id\s*\)\s+do\s+nothing", migration_sql, re.IGNORECASE
        ), "Seed must be idempotent (ON CONFLICT (id) DO NOTHING)"

    @pytest.mark.parametrize("field", EXPECTED_RULES)
    def test_expected_rule_field_present(self, migration_sql: str, field: str) -> None:
        assert field in migration_sql, f"Expected rule field {field!r} not seeded"

    def test_conditions_have_contract_keys(
        self, trigger_conditions: Tuple[Dict, ...]
    ) -> None:
        # "conditions parseable by evaluator" — each is valid JSON with the
        # type/field/operator contract the BL-Compliance.3 evaluator relies on.
        seen_types = set()
        for cond in trigger_conditions:
            for key in CONTRACT_KEYS:
                assert key in cond, f"trigger_condition {cond} missing key {key!r}"
            seen_types.add(cond["type"])
        for t in EXPECTED_TYPES:
            assert t in seen_types, f"Expected a rule of type {t!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Live-mode tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def live_db_conn():
    url = os.environ.get("RELOPASS_TEST_DB_URL")
    if not url:
        pytest.skip("Set RELOPASS_TEST_DB_URL to run live-DB seed checks.")
    try:
        import psycopg2  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover
        pytest.skip("psycopg2 not installed; cannot run live-DB seed checks.")
    conn = psycopg2.connect(url)
    try:
        yield conn
    finally:
        conn.close()


class TestSeedLive:
    def test_three_rules_selectable(self, live_db_conn) -> None:
        with live_db_conn.cursor() as cur:
            cur.execute(
                "SELECT trigger_condition FROM public.compliance_rules "
                "WHERE id IN (%s, %s, %s)",
                (
                    "c0119a01-0000-4000-8000-000000000001",
                    "c0119a02-0000-4000-8000-000000000002",
                    "c0119a03-0000-4000-8000-000000000003",
                ),
            )
            rows = cur.fetchall()
        assert len(rows) == 3, "Expected all 3 seeded rules present in the DB"
        for (cond,) in rows:
            # psycopg2 returns jsonb as a parsed dict; assert the contract keys.
            assert all(k in cond for k in CONTRACT_KEYS), f"Bad condition: {cond}"
