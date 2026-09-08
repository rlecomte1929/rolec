"""
SEC-RLSd (AIQ-661) — RLS integration tests for the public-read catalog / seed
tables policed in supabase/migrations/20260531010000_rls_catalog_seed.sql.

These hit PostgREST DIRECTLY (not the FastAPI backend) with the public anon key
plus a per-persona Supabase JWT, so they exercise the exact path a client
holding the (public) anon key would use. Seeding + cleanup go through the
service-role DATABASE_URL connection, which connects as `postgres` and bypasses
RLS.

What the migration intends (and what we assert):
  • country_events / country_profiles / country_resource_items /
    country_resource_sections / requirements_catalog / requirement_items
        → PUBLIC read (anon + authenticated), admin-only write.

(TPL-3/AIQ-1133: default_policy_templates was retired — its auth-only read +
admin-write assertions were removed with the table.)

Three personas (per the execution prompt):
  1. Anon (no user JWT)              → reads public catalog; cannot write.
  2. Authenticated non-admin         → reads public catalog + templates; cannot write.
  3. Admin (admin_allowlist member)  → can write (insert/delete).

Requires a database with the migration APPLIED (staging / supabase branch /
local). Skips cleanly when the live-Supabase env vars are absent. The
admin-write positive case additionally needs at least one row in auth.users
(it temporarily allowlists a real user and removes it afterwards); it skips
on its own if none exists.

Env:
  DATABASE_URL              service-role Postgres URL (seed/cleanup, bypasses RLS)
  SUPABASE_URL              https://<ref>.supabase.co
  SUPABASE_ANON_KEY         public anon apikey (also the anon-role bearer)
  SUPABASE_JWT_SECRET       legacy HS256 JWT secret (to mint per-persona JWTs)
"""
from __future__ import annotations

import os
import time
import uuid

import pytest

httpx = pytest.importorskip("httpx")
jwt = pytest.importorskip("jwt")
psycopg2 = pytest.importorskip("psycopg2")

DATABASE_URL = os.environ.get("DATABASE_URL")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")

pytestmark = pytest.mark.skipif(
    not (DATABASE_URL and SUPABASE_URL and ANON_KEY and JWT_SECRET),
    reason="SEC-RLSd live RLS test needs DATABASE_URL + SUPABASE_URL + "
    "SUPABASE_ANON_KEY + SUPABASE_JWT_SECRET (run against staging / a supabase "
    "branch / local with the migration applied).",
)

# Public-read catalog tables (anon + authenticated may SELECT).
PUBLIC_READ_TABLES = [
    "country_events",
    "country_profiles",
    "country_resource_items",
    "country_resource_sections",
    "requirements_catalog",
    "requirement_items",
]
# Authenticated-only read (anon denied). (TPL-3: default_policy_templates retired.)
AUTH_ONLY_TABLES: list[str] = []


def _new_uuid() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="module")
def seed():
    """Seed one sentinel row per in-scope table; yield identifiers + cleanup tag."""
    tag = f"rlscat_{uuid.uuid4().hex[:12]}"
    section_id = _new_uuid()
    ctx = {
        "tag": tag,
        "sentinel": tag,             # filterable marker on every seeded row
        "section_id": section_id,
        # A real auth user we temporarily allowlist for the admin-write case.
        "admin_uid": None,
    }
    now_ts = "2026-06-01T00:00:00Z"
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO country_profiles (id, country_code) VALUES (%s,%s)",
                (f"{tag}_cp", "XX"),
            )
            cur.execute(
                "INSERT INTO requirements_catalog (requirement_code) VALUES (%s)",
                (f"{tag}_rc",),
            )
            cur.execute(
                "INSERT INTO country_events (country_code, name, category) VALUES (%s,%s,%s)",
                ("XX", tag, "test"),
            )
            cur.execute(
                "INSERT INTO country_resource_sections (id, country_code, section_key, title) "
                "VALUES (%s,%s,%s,%s)",
                (section_id, "XX", tag, "RLS test section"),
            )
            cur.execute(
                "INSERT INTO country_resource_items (section_id, item_type, title) "
                "VALUES (%s,%s,%s)",
                (section_id, "link", tag),
            )
            cur.execute(
                "INSERT INTO requirement_items "
                "(id, purpose, pillar, title, description, severity, owner, "
                " required_fields_json, citations_json, last_verified_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (f"{tag}_ri", "test", "test", tag, "desc", "info",
                 "system", "[]", "[]", now_ts),
            )
            # Temporarily allowlist a real auth user for the admin-write case.
            cur.execute("SELECT id FROM auth.users LIMIT 1")
            row = cur.fetchone()
            if row:
                ctx["admin_uid"] = str(row[0])
                cur.execute(
                    "INSERT INTO public.admin_allowlist "
                    "(user_id, email, enabled, added_by_user_id, created_at) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (ctx["admin_uid"], f"{tag}__admin", 1, "rls-test", now_ts),
                )
        yield ctx
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM admin_allowlist WHERE email=%s", (f"{tag}__admin",))
            cur.execute("DELETE FROM country_profiles WHERE id IN (%s,%s)",
                        (f"{tag}_cp", f"{tag}_postcp"))
            cur.execute("DELETE FROM requirements_catalog WHERE requirement_code=%s", (f"{tag}_rc",))
            cur.execute("DELETE FROM country_events WHERE name=%s", (tag,))
            cur.execute("DELETE FROM country_resource_items WHERE title=%s", (tag,))
            cur.execute("DELETE FROM country_resource_sections WHERE id=%s", (section_id,))
            cur.execute("DELETE FROM requirement_items WHERE id=%s", (f"{tag}_ri",))
        conn.close()


def _mint(sub: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "role": "authenticated", "aud": "authenticated",
         "iat": now, "exp": now + 3600},
        JWT_SECRET, algorithm="HS256",
    )


def _headers(bearer: str) -> dict:
    return {"apikey": ANON_KEY, "Authorization": f"Bearer {bearer}"}


def _rest_get(table: str, params: dict, bearer: str):
    with httpx.Client(timeout=20) as client:
        r = client.get(f"{SUPABASE_URL}/rest/v1/{table}", params=params, headers=_headers(bearer))
    rows = r.json() if r.status_code == 200 else None
    return r.status_code, rows


def _rest_post(table: str, body: dict, bearer: str):
    headers = {**_headers(bearer), "Content-Type": "application/json",
               "Prefer": "return=representation"}
    with httpx.Client(timeout=20) as client:
        r = client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=body, headers=headers)
    return r.status_code


def _visible_sentinel(table: str, filt: dict, bearer: str) -> int:
    status, rows = _rest_get(table, {**filt, "select": "*"}, bearer)
    if status == 200 and isinstance(rows, list):
        return len(rows)
    assert status in (200, 401, 403, 404), f"{table}: unexpected status {status}"
    return 0


def _sentinel_filter(table: str, tag: str) -> dict:
    """Column to match the seeded sentinel row for each table."""
    return {
        "country_profiles": {"id": f"eq.{tag}_cp"},
        "requirements_catalog": {"requirement_code": f"eq.{tag}_rc"},
        "country_events": {"name": f"eq.{tag}"},
        "country_resource_sections": {"section_key": f"eq.{tag}"},
        "country_resource_items": {"title": f"eq.{tag}"},
        "requirement_items": {"id": f"eq.{tag}_ri"},
    }[table]


# ---------------------------------------------------------------------------
# 1. Anon can still read the public-read catalog tables.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_anon_reads_public_catalog(seed):
    for table in PUBLIC_READ_TABLES:
        n = _visible_sentinel(table, _sentinel_filter(table, seed["tag"]), ANON_KEY)
        assert n >= 1, (
            f"{table}: anon could not read its seeded row — public-read policy/grant "
            "missing or migration 20260531010000 not applied."
        )


# ---------------------------------------------------------------------------
# 2. Anon cannot write to a public-read catalog table.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_anon_cannot_write_public_catalog(seed):
    status = _rest_post("country_profiles", {"id": f"{seed['tag']}_postcp", "country_code": "XX"}, ANON_KEY)
    assert status in (401, 403), f"anon write should be denied, got {status}"


# ---------------------------------------------------------------------------
# 3. Authenticated (non-admin) reads public catalog + templates.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_authenticated_reads_catalog_and_templates(seed):
    user = _mint(_new_uuid())  # arbitrary non-allowlisted authenticated user
    for table in PUBLIC_READ_TABLES + AUTH_ONLY_TABLES:
        n = _visible_sentinel(table, _sentinel_filter(table, seed["tag"]), user)
        assert n >= 1, f"{table}: authenticated user could not read its seeded row"


# ---------------------------------------------------------------------------
# 4. Non-admin authenticated user cannot write.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_nonadmin_cannot_write(seed):
    user = _mint(_new_uuid())
    status = _rest_post("country_profiles", {"id": f"{seed['tag']}_postcp", "country_code": "YY"}, user)
    assert status in (401, 403), f"non-admin write should be denied, got {status}"


# ---------------------------------------------------------------------------
# 5. Admin (admin_allowlist member) can write.
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_admin_can_write(seed):
    if not seed["admin_uid"]:
        pytest.skip("no auth.users row available to allowlist as admin for the write test")
    admin = _mint(seed["admin_uid"])
    status = _rest_post(
        "country_profiles", {"id": f"{seed['tag']}_postcp", "country_code": "ZZ"}, admin
    )
    assert status == 201, f"admin write should succeed (201), got {status}"
    # Clean the row up via the admin (delete is admin-allowed); fixture also sweeps it.
    with httpx.Client(timeout=20) as client:
        client.delete(
            f"{SUPABASE_URL}/rest/v1/country_profiles",
            params={"id": f"eq.{seed['tag']}_postcp"},
            headers=_headers(admin),
        )
