"""C1-01b · Tests for the catalog seed migration.

Validates structural properties of the
`supabase/migrations/20260529130000_rce_catalog_seeds.sql` file:

1. Exactly 17 document_types rows
2. PASSPORT_TD3 row has populated expected_fields_json
3. ≥25 authorities rows
4. Idempotency — ON CONFLICT DO UPDATE on both INSERT blocks
5. Every row carries a source_url

These tests parse the SQL file (no Postgres required). A live-DB test
adapter belongs in a separate Cohort-1 integration suite.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Tuple

import pytest


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "20260529130000_rce_catalog_seeds.sql"
)


@pytest.fixture(scope="module")
def sql_text() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# SQL parsing helpers
# ─────────────────────────────────────────────────────────────────────────────


def _extract_insert_block(sql: str, table: str) -> str:
    """Return the text of the INSERT ... VALUES ... ON CONFLICT block for ``table``."""
    pattern = re.compile(
        rf"INSERT\s+INTO\s+{re.escape(table)}\s*\(.*?ON\s+CONFLICT.*?;",
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(sql)
    if not m:
        raise AssertionError(f"No INSERT block found for table {table}")
    return m.group(0)


def _split_value_rows(block: str) -> List[str]:
    """Return the per-row VALUES tuples (strings) inside an INSERT block.

    Counts top-level parenthesised groups after the VALUES keyword and before
    ON CONFLICT — tolerates nested parens inside JSONB literals and Postgres
    type-cast syntax. Treats commas only at depth 0 between rows.
    """
    after_values = block.split("VALUES", 1)[1]
    on_conflict_idx = after_values.upper().rfind("ON CONFLICT")
    body = after_values[:on_conflict_idx]

    rows: List[str] = []
    depth = 0
    in_single_quote = False
    current: List[str] = []

    for ch in body:
        if ch == "'" and (not current or current[-1] != "\\"):
            in_single_quote = not in_single_quote
        if not in_single_quote:
            if ch == "(":
                depth += 1
                if depth == 1:
                    current = []
                    continue
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    rows.append("".join(current).strip())
                    current = []
                    continue
        if depth >= 1:
            current.append(ch)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 1 — exactly 17 document_types rows
# ─────────────────────────────────────────────────────────────────────────────


def test_document_types_inserts_exactly_17_rows(sql_text: str):
    block = _extract_insert_block(sql_text, "rce.document_types")
    rows = _split_value_rows(block)
    assert len(rows) == 17, f"expected 17 document_types rows, got {len(rows)}"


REQUIRED_DOCUMENT_CODES = {
    "PASSPORT_TD3",
    "EU_NATIONAL_ID",
    "RESIDENCE_PERMIT_EU",
    "EMPLOYMENT_CONTRACT",
    "PAYSLIP",
    "DIPLOMA_BACHELOR",
    "DIPLOMA_MASTER",
    "ANABIN_EVIDENCE",
    "ZAB_STATEMENT_OF_COMPARABILITY",
    "IT_EXPERIENCE_PORTFOLIO",
    "HEALTH_INSURANCE_PROOF",
    "MARRIAGE_CERT",
    "BIRTH_CERT",
    "FOSTER_CARE_ORDER",
    "CRIMINAL_RECORD",
    "TAX_CERT",
    "HOUSING_LEASE",
}


def test_all_required_document_codes_present(sql_text: str):
    block = _extract_insert_block(sql_text, "rce.document_types")
    rows = _split_value_rows(block)
    codes = {row.split(",", 1)[0].strip().strip("'") for row in rows}
    missing = REQUIRED_DOCUMENT_CODES - codes
    assert not missing, f"missing document codes: {missing}"


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 2 — PASSPORT_TD3 has populated expected_fields_json
# ─────────────────────────────────────────────────────────────────────────────


def test_passport_td3_expected_fields_json_is_populated(sql_text: str):
    block = _extract_insert_block(sql_text, "rce.document_types")
    rows = _split_value_rows(block)
    passport_row = next((r for r in rows if r.startswith("'PASSPORT_TD3'")), None)
    assert passport_row is not None, "PASSPORT_TD3 row not found"

    # The JSONB literal is between the first '{' and the matching '}' (no
    # nested objects in our seed rows). Strip the ::jsonb cast.
    m = re.search(r"'(\{[^']+\})'::jsonb", passport_row)
    assert m, "expected_fields_json literal not found on PASSPORT_TD3 row"
    parsed = json.loads(m.group(1))
    assert "fields" in parsed
    assert isinstance(parsed["fields"], list)
    assert "surname" in parsed["fields"]
    assert "document_number" in parsed["fields"]
    assert "photo_bbox" in parsed["fields"]
    assert "issuing_authority" in parsed["fields"]


def test_every_document_type_has_expected_fields_json(sql_text: str):
    block = _extract_insert_block(sql_text, "rce.document_types")
    rows = _split_value_rows(block)
    for row in rows:
        assert "::jsonb" in row, f"row missing JSONB literal: {row[:80]}…"


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 3 — ≥25 authorities rows
# ─────────────────────────────────────────────────────────────────────────────


def test_authorities_inserts_at_least_25_rows(sql_text: str):
    block = _extract_insert_block(sql_text, "rce.authorities")
    rows = _split_value_rows(block)
    assert len(rows) >= 25, f"expected ≥25 authority rows, got {len(rows)}"


REQUIRED_AUTHORITY_NAMES = {
    # Norway
    "UDI", "Politiet", "Lovdata", "Folkeregister", "NAV",
    # Germany
    "BAMF", "anabin", "ZAB", "Bundesagentur für Arbeit",
    "Gesetze-im-Internet", "BGBl.", "Bundesanzeiger",
    "Munich KVR", "Berlin LEA", "Make it in Germany",
    # France
    "Service-Public.fr", "Légifrance",
    # India
    "Passport Seva", "MEA Apostille",
    # International / EU
    "EUR-Lex", "ICAO",
}


def test_required_authority_names_present(sql_text: str):
    block = _extract_insert_block(sql_text, "rce.authorities")
    rows = _split_value_rows(block)
    # First element of each row is the name literal.
    names = set()
    for row in rows:
        first = row.split(",", 1)[0].strip()
        if first.startswith("'") and first.endswith("'"):
            names.add(first[1:-1])
    missing = REQUIRED_AUTHORITY_NAMES - names
    assert not missing, f"missing authority names: {missing}"


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 4 — Idempotency (ON CONFLICT DO UPDATE on both blocks)
# ─────────────────────────────────────────────────────────────────────────────


def test_document_types_insert_block_is_idempotent(sql_text: str):
    block = _extract_insert_block(sql_text, "rce.document_types")
    upper = block.upper()
    assert "ON CONFLICT (CODE)" in upper or "ON CONFLICT(CODE)" in upper, (
        "document_types INSERT must use ON CONFLICT (code) DO UPDATE"
    )
    assert "DO UPDATE" in upper, "DO UPDATE clause missing"
    # The updated_at refresh is what makes re-runs observable in the audit
    # trail without producing duplicate rows.
    assert "UPDATED_AT = NOW()" in upper


def test_authorities_insert_block_is_idempotent(sql_text: str):
    block = _extract_insert_block(sql_text, "rce.authorities")
    upper = block.upper()
    assert "ON CONFLICT" in upper, "authorities INSERT must use ON CONFLICT"
    assert "DO UPDATE" in upper, "authorities ON CONFLICT must DO UPDATE"
    assert "UPDATED_AT = NOW()" in upper


def test_authorities_uniqueness_is_name_country_pair(sql_text: str):
    # The conflict target for authorities must be the (name, country_iso3)
    # pair, NOT just name. Same name in different countries is allowed.
    assert (
        "UNIQUE (name, country_iso3)" in sql_text
        or "UNIQUE(name, country_iso3)" in sql_text
    )


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 5 — Every row carries a source_url
# ─────────────────────────────────────────────────────────────────────────────


def test_document_types_table_has_source_url_column_added(sql_text: str):
    upper = sql_text.upper()
    assert (
        "ALTER TABLE RCE.DOCUMENT_TYPES" in upper
        and "ADD COLUMN IF NOT EXISTS SOURCE_URL" in upper
    )


def test_authorities_table_has_source_url_column_added(sql_text: str):
    upper = sql_text.upper()
    assert (
        "ALTER TABLE RCE.AUTHORITIES" in upper
        and "ADD COLUMN IF NOT EXISTS SOURCE_URL" in upper
    )


def test_every_document_types_row_carries_source_url(sql_text: str):
    block = _extract_insert_block(sql_text, "rce.document_types")
    rows = _split_value_rows(block)
    for row in rows:
        # Every row should mention a notion.so URL.
        assert "notion.so" in row, f"row missing source_url: {row[:80]}…"


def test_every_authorities_row_carries_source_url(sql_text: str):
    block = _extract_insert_block(sql_text, "rce.authorities")
    rows = _split_value_rows(block)
    for row in rows:
        assert "notion.so" in row, f"row missing source_url: {row[:80]}…"


# ─────────────────────────────────────────────────────────────────────────────
# Schema safety
# ─────────────────────────────────────────────────────────────────────────────


def test_alter_table_uses_if_not_exists(sql_text: str):
    """The migration is safe to apply on a DB where the columns already
    exist (e.g. after a manual hotfix). IF NOT EXISTS prevents the
    re-run from erroring."""
    upper = sql_text.upper()
    assert upper.count("ADD COLUMN IF NOT EXISTS") >= 2
