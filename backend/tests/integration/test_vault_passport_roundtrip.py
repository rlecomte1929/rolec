"""[AIQ-1800] The passport vault must survive a real encrypt → store → decrypt round trip.

WHY THIS EXISTS
---------------
`IMMIGRATION_ENCRYPTION_KEY` has never been set in production, and
`imm_employee_profiles` has 0 rows. Every existing vault test mocks the database
(`patch("backend.database.db")`). So the fail-closed behaviour is well covered and the
**happy path has never executed anywhere** — not in CI, not in prod.

That matters more than it sounds, because the two halves disagree on type:

    write:  SELECT pgp_sym_encrypt(:val, :key)      -> bytea
    column: imm_employee_profiles.passport_number   -> text
    read:   SELECT pgp_sym_decrypt(CAST(:enc AS bytea), :key)

Measured on the live database 2026-08-11: `pg_cast` has **no bytea → text entry at all**,
so Postgres will reject that assignment in a normal INSERT. Whether the production path
works therefore depends entirely on what the driver puts on the wire for the value
`_encrypt_passport_number` returns — which is a Python-side question that SQL alone cannot
answer, and which nothing has ever exercised.

If the key were simply switched on, the first real passport would be the experiment, on an
Article 9 special-category identifier, in production. This test is that experiment, run
first, on a synthetic value, inside a transaction that is always rolled back.

SAFETY
------
Nothing here commits. Every test opens a transaction and rolls it back, so the table is in
exactly the state it started in. The key used is a local test passphrase; the real key is
never read, required, or referenced.

RUNNING
-------
Needs a Postgres `DATABASE_URL` (pgcrypto is not available in the sqlite unit lane), and
is `integration`-marked so CI's `-m "not integration"` run skips it.

    DATABASE_URL=postgresql://... RELOPASS_ALLOW_REMOTE_DB_IN_TESTS=1 \
      pytest backend/tests/integration/test_vault_passport_roundtrip.py -v
"""
from __future__ import annotations

import os

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, text  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL", "")
_IS_PG = DATABASE_URL.startswith("postgres")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _IS_PG,
        reason="needs a Postgres DATABASE_URL — pgcrypto does not exist in the sqlite lane, "
        "and mocking it is exactly what left this path unproven.",
    ),
]

#: A local passphrase. Deliberately NOT the production key: this test must never depend on
#: the real secret, and must pass before that decision is made.
TEST_KEY = "aiq1800-local-test-passphrase-not-the-real-one"

#: Shaped like a passport number so a failure message is recognisable, but synthetic.
PLAINTEXT = "X1234567Z"

PROFILES = "public.imm_employee_profiles"


@pytest.fixture()
def conn():
    """A connection whose transaction is ALWAYS rolled back.

    Not `engine.begin()` — that commits on success, and nothing in this file should ever
    reach the table permanently.
    """
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    with engine.connect() as c:
        tx = c.begin()
        try:
            yield c
        finally:
            tx.rollback()
    engine.dispose()


def _encrypt(conn, value: str, key: str = TEST_KEY):
    """Exactly what `_encrypt_passport_number` does — same SQL, same driver, same result type."""
    row = conn.execute(
        text("SELECT pgp_sym_encrypt(:val, :key) AS encrypted"),
        {"val": value, "key": key},
    ).mappings().first()
    return row["encrypted"]


def test_pgcrypto_is_available(conn):
    """Everything below is meaningless if the extension is missing."""
    got = conn.execute(
        text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='pgcrypto') AS ok")
    ).scalar()
    assert got, "pgcrypto is not installed — the vault cannot encrypt anything"


def test_bytea_to_text_has_no_registered_cast(conn):
    """Pin the fact that makes the write path fragile, so a future reader does not re-derive it.

    If Postgres ever gains an implicit bytea→text cast this test fails, which is the signal
    that the write path's type mismatch stopped mattering.
    """
    ctx = conn.execute(
        text(
            "SELECT c.castcontext FROM pg_cast c "
            "JOIN pg_type s ON s.oid=c.castsource JOIN pg_type t ON t.oid=c.casttarget "
            "WHERE s.typname='bytea' AND t.typname='text'"
        )
    ).scalar()
    assert ctx is None, (
        f"bytea→text now has a cast (context {ctx!r}). The write path's assumption that a "
        "bytea value can land in a text column may have changed — re-check "
        "_encrypt_passport_number."
    )


def test_ciphertext_survives_the_text_column_round_trip(conn):
    """THE test: encrypt → store in a text column → read → decrypt → same plaintext.

    Uses a temp table with the same column type as the real one, so this isolates the
    type round-trip from anything else about the schema.
    """
    conn.execute(text("CREATE TEMPORARY TABLE _vault_rt (passport_number text) ON COMMIT DROP"))
    ciphertext = _encrypt(conn, PLAINTEXT)

    conn.execute(
        text("INSERT INTO _vault_rt (passport_number) VALUES (:enc)"),
        {"enc": ciphertext},
    )

    stored = conn.execute(text("SELECT passport_number FROM _vault_rt")).scalar()
    assert stored is not None, "nothing was stored"
    assert stored != PLAINTEXT, "the PLAINTEXT passport number was stored — the vault is not encrypting"
    assert PLAINTEXT not in str(stored), "the plaintext is recoverable from the stored value by substring"

    back = conn.execute(
        text("SELECT pgp_sym_decrypt(CAST(:enc AS bytea), :key) AS d"),
        {"enc": stored, "key": TEST_KEY},
    ).scalar()
    assert back == PLAINTEXT, (
        f"round trip lost the value: stored {stored!r} decrypted to {back!r}. The read paths "
        "(immigration_forms.py:53, immigration_gdpr.py:88, immigration_intake_profile.py:310, "
        "prefill_engine.py:624) all use this exact CAST — if this fails they are all broken."
    )


def test_round_trip_through_the_real_profiles_table(conn):
    """Same proof against `imm_employee_profiles` itself, so the real schema is what is tested.

    Rolled back — the row never persists. The table has no FKs (only a PK on id, verified
    2026-08-11), so a synthetic row needs nothing else to exist.
    """
    ciphertext = _encrypt(conn, PLAINTEXT)

    row_id = conn.execute(
        text(
            f"INSERT INTO {PROFILES} (case_id, employee_id, org_id, passport_number) "
            "VALUES (:c, :e, :o, :enc) RETURNING id"
        ),
        {
            "c": "aiq1800-test-case",
            "e": "aiq1800-test-employee",
            "o": "aiq1800-test-org",
            "enc": ciphertext,
        },
    ).scalar()
    assert row_id, "insert did not return an id"

    stored = conn.execute(
        text(f"SELECT passport_number FROM {PROFILES} WHERE id = :id"), {"id": row_id}
    ).scalar()
    assert stored != PLAINTEXT, "plaintext reached the real column"

    back = conn.execute(
        text("SELECT pgp_sym_decrypt(CAST(:enc AS bytea), :key) AS d"),
        {"enc": stored, "key": TEST_KEY},
    ).scalar()
    assert back == PLAINTEXT, f"real-table round trip failed: {stored!r} → {back!r}"


def test_wrong_key_fails_loudly_rather_than_returning_garbage(conn):
    """A wrong key must raise, not quietly hand back something that looks like data.

    This is the property the four read paths depend on. If decryption degraded to returning
    bytes-that-happen-to-decode, a key rotation mistake would surface as corrupted passport
    numbers shown to employees instead of an error somebody notices.
    """
    ciphertext = _encrypt(conn, PLAINTEXT)
    with pytest.raises(Exception) as exc:
        conn.execute(
            text("SELECT pgp_sym_decrypt(CAST(:enc AS bytea), :key) AS d"),
            {"enc": ciphertext, "key": "definitely-the-wrong-passphrase"},
        ).scalar()
    assert "wrong key" in str(exc.value).lower() or "corrupt" in str(exc.value).lower(), (
        f"decrypting with the wrong key raised something unexpected: {exc.value!r}"
    )


def test_encryption_is_not_deterministic(conn):
    """Two encryptions of the same value must differ.

    pgp_sym_encrypt salts each call. If this ever became deterministic, equal ciphertexts
    would leak that two employees share a passport number — and would make the column
    dictionary-attackable over a small domain.
    """
    a = _encrypt(conn, PLAINTEXT)
    b = _encrypt(conn, PLAINTEXT)
    assert bytes(a) != bytes(b), "ciphertext is deterministic — equality leaks plaintext equality"


def test_no_plaintext_passport_numbers_exist_today(conn):
    """The live invariant, asserted as a test so it keeps being true.

    Anything that is not NULL must be pgcrypto output, which renders with a `\\x` prefix
    when read out of a text column. A row failing this is a plaintext leak, and is the
    single highest-severity thing this file can detect.
    """
    bad = conn.execute(
        text(
            f"SELECT count(*) FROM {PROFILES} "
            "WHERE passport_number IS NOT NULL AND passport_number NOT LIKE '\\x%'"
        )
    ).scalar()
    assert bad == 0, (
        f"{bad} row(s) in {PROFILES} hold a passport_number that is not pgcrypto ciphertext. "
        "That is a plaintext Article 9 identifier at rest — treat as an incident, not a test failure."
    )
