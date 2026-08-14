"""Tests for E-PIPE-1 rce.documents ingest + classification + bridge.

Pure logic (classification) and the adapter glue are tested with a fake
SQLAlchemy connection/engine (no DB). The migration + ingest SQL are validated
separately against prod in a rollback transaction (see PR description).
"""

from __future__ import annotations

from uuid import uuid4

from backend.app.services.rce_document_ingest import (
    bridge_case_document_to_rce,
    classify_rce_document_type,
    ingest_rce_document,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fakes
# ─────────────────────────────────────────────────────────────────────────────


class _FakeResult:
    def __init__(self, *, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def scalar(self):
        return self._scalar

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(self, results):
        self._queue = list(results)
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((str(sql), params))
        return self._queue.pop(0)


class _FakeEngine:
    """engine.begin() context manager yielding a fixed fake conn."""

    def __init__(self, conn):
        self._conn = conn

    def begin(self):
        conn = self._conn

        class _Ctx:
            def __enter__(self):
                return conn

            def __exit__(self, *a):
                return False

        return _Ctx()


# ─────────────────────────────────────────────────────────────────────────────
# Classification
# ─────────────────────────────────────────────────────────────────────────────


def test_classify_maps_known_filenames():
    cases = {
        "john_passport.jpg": "PASSPORT_TD3",
        "national_id_card.png": "ID_CARD",
        "acte_de_mariage.pdf": "MARRIAGE_CERT",
        "geburtsurkunde.pdf": "BIRTH_CERT",
        "foster_care_order.pdf": "FOSTER_CARE_ORDER",
        "masters_diploma.pdf": "DIPLOMA",
        # [AIQ-1774] One code per locale — each routes to its own agent.
        "avis_imposition_2024.pdf": "TAX_CERT_FR",
        "lohnsteuerbescheinigung_2024.pdf": "TAX_CERT_DE",
        "skattemelding_2024.pdf": "TAX_CERT_NO",
    }
    for name, expected in cases.items():
        assert classify_rce_document_type(name) == expected, name


def test_classify_unknown_returns_none():
    assert classify_rce_document_type("random_scan_0042.pdf") is None
    assert classify_rce_document_type(None) is None


def test_classify_ambiguous_tax_filename_refuses_to_guess():
    """[AIQ-1774] A bare "tax" filename names no locale, and DE/FR/NO tax
    certificates are genuinely different documents with different agents. Guessing
    one would emit confidently wrong fields, so it stays unclassified (NULL
    document_type_id) and the document goes to human review.

    This is not a regression: "tax.pdf" previously classified as the bare TAX_CERT
    code, which routed to no agent, so extraction was skipped then too.
    """
    assert classify_rce_document_type("tax_document_2024.pdf") is None
    assert classify_rce_document_type("my_taxes.pdf") is None


# ─────────────────────────────────────────────────────────────────────────────
# ingest_rce_document
# ─────────────────────────────────────────────────────────────────────────────


def test_ingest_resolves_type_and_returns_new_id():
    dt_id, doc_id = uuid4(), uuid4()
    conn = _FakeConn([
        _FakeResult(scalar=dt_id),          # _document_type_id lookup
        _FakeResult(rows=[(doc_id,)]),       # INSERT ... RETURNING
    ])
    out = ingest_rce_document(
        conn, case_id=str(uuid4()), sha256="abc", document_type_code="PASSPORT_TD3",
        mime_type="image/jpeg", storage_uri="c/x.jpg", original_filename="p.jpg",
        uploaded_by="u1",
    )
    assert out == str(doc_id)
    # the INSERT bound the resolved document_type_id
    insert_params = conn.calls[1][1]
    assert insert_params["doc_type_id"] == dt_id
    assert insert_params["sha256"] == "abc"


def test_ingest_unknown_type_passes_null_type():
    # _document_type_id short-circuits on a None code, so the FIRST queued result is
    # consumed by the INSERT itself — it must carry a RETURNING row, or the insert reads
    # as a conflict and triggers the re-select.
    conn = _FakeConn([
        _FakeResult(rows=[(uuid4(),)]),      # INSERT ... RETURNING (no type lookup ran)
    ])
    ingest_rce_document(conn, case_id=str(uuid4()), sha256="z", document_type_code=None)
    assert len(conn.calls) == 1
    assert conn.calls[0][1]["doc_type_id"] is None


def test_ingest_conflict_returns_the_existing_id():
    """Re-uploading identical bytes must return the EXISTING document_id.

    ON CONFLICT DO NOTHING yields no RETURNING row. This used to return None, which the
    caller read as "not bridged" — so the extraction pipeline was never kicked and a
    re-upload was a silent no-op even though a valid rce.documents row existed.
    """
    existing_id = uuid4()
    conn = _FakeConn([
        _FakeResult(scalar=uuid4()),         # document_type lookup
        _FakeResult(rows=[]),                # ON CONFLICT DO NOTHING → no RETURNING row
        _FakeResult(rows=[(existing_id,)]),  # re-select finds the row that already existed
    ])
    out = ingest_rce_document(conn, case_id=str(uuid4()), sha256="dup",
                              document_type_code="ID_CARD")
    assert out == str(existing_id)
    # The re-select is scoped to the same (case_id, sha256) the INSERT targeted.
    reselect_sql, reselect_params = conn.calls[2]
    assert "SELECT document_id FROM rce.documents" in reselect_sql
    assert reselect_params["sha256"] == "dup"


def test_ingest_conflict_with_no_row_found_still_returns_none():
    """Defensive: if the conflict came from some OTHER constraint the re-select cannot
    find, stay None rather than inventing an id."""
    conn = _FakeConn([
        _FakeResult(scalar=uuid4()),
        _FakeResult(rows=[]),                # no RETURNING row
        _FakeResult(rows=[]),                # and no matching (case_id, sha256) row either
    ])
    out = ingest_rce_document(conn, case_id=str(uuid4()), sha256="dup",
                              document_type_code="ID_CARD")
    assert out is None


def test_ingest_success_does_not_re_select():
    """The happy path must stay a single INSERT — no extra round-trip."""
    conn = _FakeConn([
        _FakeResult(scalar=uuid4()),
        _FakeResult(rows=[(uuid4(),)]),
    ])
    ingest_rce_document(conn, case_id=str(uuid4()), sha256="new",
                        document_type_code="ID_CARD")
    assert len(conn.calls) == 2  # type lookup + INSERT only


# ─────────────────────────────────────────────────────────────────────────────
# bridge_case_document_to_rce (fail-soft)
# ─────────────────────────────────────────────────────────────────────────────


def test_bridge_skips_when_case_not_in_rce():
    conn = _FakeConn([_FakeResult(rows=[])])  # _case_exists → None
    out = bridge_case_document_to_rce(
        case_id=str(uuid4()), content=b"data", original_filename="passport.jpg",
        engine=_FakeEngine(conn),
    )
    assert out is None
    assert len(conn.calls) == 1  # only the case-exists check ran; no ingest


def test_bridge_ingests_when_case_exists():
    doc_id = uuid4()
    conn = _FakeConn([
        _FakeResult(rows=[(1,)]),             # _case_exists → exists
        _FakeResult(scalar=uuid4()),          # document_type lookup
        _FakeResult(rows=[(doc_id,)]),        # INSERT RETURNING
    ])
    out = bridge_case_document_to_rce(
        case_id=str(uuid4()), content=b"passport-bytes", original_filename="passport.jpg",
        engine=_FakeEngine(conn),
    )
    assert out == str(doc_id)


def test_bridge_is_fail_soft_on_error():
    class _BoomEngine:
        def begin(self):
            raise RuntimeError("db down")

    out = bridge_case_document_to_rce(
        case_id=str(uuid4()), content=b"x", original_filename="passport.jpg",
        engine=_BoomEngine(),
    )
    assert out is None  # swallowed, never raises
