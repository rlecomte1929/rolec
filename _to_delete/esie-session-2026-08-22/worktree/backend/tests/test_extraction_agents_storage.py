"""Tests for E-PIPE-3 production ExtractionSink + AgentStorage.

Pure mapping helpers + adapter glue tested with a fake connection (no DB). The
full round-trip (agent → version → run → field, against real FKs/CHECKs) is
validated against prod in a rollback transaction (see PR description).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from backend.relopass.agents.models import ExtractedField, ExtractionAgentVersion
from backend.app.services.extraction_agents_storage import (
    SupabaseAgentStorage,
    SupabaseExtractionSink,
    _extracted_field_params,
    _phi_class,
    _version_params,
)


class _FakeResult:
    def __init__(self, *, scalar=None):
        self._scalar = scalar

    def scalar(self):
        return self._scalar


class _FakeConn:
    def __init__(self, results=None):
        self._queue = list(results or [])
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((str(sql), params))
        return self._queue.pop(0) if self._queue else _FakeResult()


def _ef(**kw) -> ExtractedField:
    base = dict(
        document_id=uuid4(), field_key="nationality_iso3", value_raw="FRA",
        value_canonical=None, confidence=0.95, bbox_page=None,
        bbox_x0=None, bbox_y0=None, bbox_x1=None, bbox_y1=None,
        agent_run_id=uuid4(), resolution_status=None,
    )
    base.update(kw)
    return ExtractedField(**base)


def _version() -> ExtractionAgentVersion:
    return ExtractionAgentVersion(
        agent_version_id=uuid4(), agent_id=uuid4(), name="passport_td3",
        version_number=1, version_hash="h1", extraction_instructions="x",
        value_type="string", unit=None, dimensions=None,
        resolution_instructions=None, inconsistency_instructions=None,
        enable_web_search=False, enable_complex_calculations_in_resolution=False,
        examples=(), output_schema_required_keys=("is_passport",),
        created_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
    )


# ── phi_class ────────────────────────────────────────────────────────────────


def test_phi_class_from_value_canonical():
    assert _phi_class(_ef(value_canonical={"phi_class": "BIOMETRIC"})) == "BIOMETRIC"


def test_phi_class_defaults_to_pii_not_none():
    """[AIQ-1805] This test previously asserted the DEFECT.

    It read `== "NONE"` and passed, which is how every passport field in production —
    the passport number and the national ID included — came to be stamped "not personal
    data". The old default was NONE and only the photo bbox ever carried a hint, so the
    column said the opposite of the truth for every row.

    Defaulting to PII makes an unrecognised field over-protected rather than
    under-protected. A field extracted from someone's identity document relates to an
    identified person, which is what Art. 4(1) covers.
    """
    assert _phi_class(_ef(value_canonical=None)) == "PII"
    assert _phi_class(_ef(value_canonical={"source": "x"})) == "PII"
    # A value outside the CHECK set must not be trusted through — it falls back to the
    # key-based default rather than being written and rejected by Postgres.
    assert _phi_class(_ef(value_canonical={"phi_class": "BOGUS"})) == "PII"


def test_every_passport_field_key_in_production_is_classified():
    """Pins the ruling of 2026-08-11 against the exact 13 keys production holds.

    A future agent change that renames or drops a key fails here rather than silently
    reverting a row to NONE.
    """
    expected = {
        "document_number": "PII",     # the passport number
        "personal_number": "PII",     # national ID / D-number
        "surname": "PII",
        "given_names": "PII",
        "date_of_birth": "PII",
        "sex": "PII",                 # administrative sex is not Art. 9
        "nationality_iso3": "PII",    # nationality is not ethnicity under Art. 9
        "issuing_state_iso3": "PII",
        "issuing_authority": "PII",
        "expiry_date": "PII",
        "endorsements": "PII",
        "mrz_body_discrepancies": "PII",  # can quote field values back
        "agent_confidence": "NONE",   # the model's confidence, not the subject's data
    }
    for key, want in expected.items():
        assert _phi_class(_ef(field_key=key)) == want, key


def test_an_agent_hint_still_wins_over_the_key_default():
    """BIOMETRIC on the photo region is more specific than any key rule, and is the one
    classification the agents got right before this fix."""
    f = _ef(field_key="portrait_bbox", value_canonical={"phi_class": "BIOMETRIC"})
    assert _phi_class(f) == "BIOMETRIC"


def test_an_unknown_future_field_key_is_pii():
    """The point of the change: a key nobody has classified yet fails SAFE."""
    assert _phi_class(_ef(field_key="some_field_invented_next_year")) == "PII"


# ── param builders ───────────────────────────────────────────────────────────


def test_extracted_field_params_maps_and_jsonifies():
    f = _ef(value_canonical={"phi_class": "PII", "source": "mrz"})
    p = _extracted_field_params(f)
    assert p["field_key"] == "nationality_iso3"
    assert p["phi_class"] == "PII"
    assert isinstance(p["value_canonical"], str)  # json string, cast to jsonb in SQL
    assert p["document_id"] == str(f.document_id)


def test_version_params_serialises_examples_and_schema():
    p = _version_params(_version())
    assert p["examples"] == "[]"
    assert '"required_keys"' in p["output_schema"]
    assert p["value_type"] == "string"
    assert p["version_hash"] == "h1"


# ── storage glue ─────────────────────────────────────────────────────────────


def test_next_version_number_increments_max():
    conn = _FakeConn([_FakeResult(scalar=3)])
    assert SupabaseAgentStorage(conn).next_version_number(uuid4()) == 4


def test_next_version_number_first_is_one():
    conn = _FakeConn([_FakeResult(scalar=None)])
    assert SupabaseAgentStorage(conn).next_version_number(uuid4()) == 1


def test_write_extracted_fields_one_insert_per_field():
    conn = _FakeConn()
    SupabaseExtractionSink(conn).write_extracted_fields((_ef(), _ef(field_key="surname", value_raw="X")))
    assert len(conn.calls) == 2
    # [AIQ-1805] was "NONE" — nationality_iso3 is personal data.
    assert conn.calls[0][1]["phi_class"] == "PII"


def test_write_extracted_fields_empty_noop():
    conn = _FakeConn()
    SupabaseExtractionSink(conn).write_extracted_fields(())
    assert conn.calls == []


def test_write_agent_run_maps_tokens_and_version_ref():
    conn = _FakeConn()
    run_id, vid = uuid4(), uuid4()
    SupabaseExtractionSink(conn).write_agent_run(
        agent_run_id=run_id, agent_version_id=vid, case_id=uuid4(), document_id=uuid4(),
        model_name="claude-haiku", tokens_in=100, tokens_out=40, cost_usd=0.01,
        inputs_digest="i", output_digest="o",
        started_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
        finished_at=datetime(2026, 6, 10, tzinfo=timezone.utc), status="OK",
    )
    p = conn.calls[0][1]
    assert p["vref"] == str(vid)
    assert p["cost_tokens"] == 140  # tokens_in + tokens_out
    assert p["model"] == "claude-haiku"
