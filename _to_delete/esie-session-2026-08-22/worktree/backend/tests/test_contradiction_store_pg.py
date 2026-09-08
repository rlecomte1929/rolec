"""Tests for the production ContradictionStore adapter (C2-09b).

Pure mapping helpers + the adapter glue are tested with a fake SQLAlchemy
connection (no DB). The full real-DB round-trip is validated separately against
prod in a rollback transaction (see the PR description); an env-gated integration
test is included for anyone with an rce-capable DATABASE_URL.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.relopass.agents.contradiction import (
    Candidate,
    Contradiction,
    _synthetic_field_id,
)
from backend.relopass.agents.models import ExtractedField
from backend.app.services.contradiction_store_pg import (
    SupabaseContradictionStore,
    _candidates_to_jsonb,
    _contradiction_params,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fake SQLAlchemy connection
# ─────────────────────────────────────────────────────────────────────────────


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def scalar(self):
        if not self._rows:
            return None
        first = self._rows[0]
        return next(iter(first.values()))

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    """Returns queued results, one per execute() call (FIFO)."""

    def __init__(self, results):
        self._queue = list(results)
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((str(sql), params))
        return self._queue.pop(0)


# ─────────────────────────────────────────────────────────────────────────────
# Pure helpers
# ─────────────────────────────────────────────────────────────────────────────


def _candidate(value, doc_id=None):
    return Candidate(
        value=value,
        document_id=doc_id or uuid4(),
        page=2,
        bbox=(1, 2, 3, 4),
        source_agent_run_id=uuid4(),
        confidence=0.9,
        document_type_code="PASSPORT_TD3",
    )


def test_candidates_to_jsonb_is_json_safe():
    c = _candidate("FRA")
    out = _candidates_to_jsonb((c,))
    # must round-trip through json without error (UUIDs/tuples serialised)
    blob = json.dumps(out)
    parsed = json.loads(blob)[0]
    assert parsed["value"] == "FRA"
    assert parsed["document_id"] == str(c.document_id)
    assert parsed["bbox"] == [1, 2, 3, 4]
    assert parsed["document_type_code"] == "PASSPORT_TD3"


def test_candidates_to_jsonb_handles_none_bbox_and_run_id():
    c = Candidate(value="DEU", document_id=uuid4(), confidence=0.5)
    out = _candidates_to_jsonb((c,))[0]
    assert out["bbox"] is None
    assert out["source_agent_run_id"] is None


def test_contradiction_params_maps_type_to_column_and_serialises():
    c = Contradiction(
        contradiction_id=uuid4(),
        case_id=uuid4(),
        canonical_entity_id=uuid4(),
        field_key="nationality_iso3",
        type="CONTRADICTION_NATIONALITY",
        candidates=(_candidate("FRA"), _candidate("DEU")),
        resolution_status="Requires attention",
        suggested_winner=None,
        content_hash="abc123",
        detected_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
    )
    p = _contradiction_params(c)
    assert p["contradiction_type"] == "CONTRADICTION_NATIONALITY"
    assert p["field_key"] == "nationality_iso3"
    assert p["resolution_status"] == "Requires attention"
    assert p["suggested_winner"] is None  # None → SQL NULL, not jsonb 'null'
    # candidates serialised to a JSON string (cast to jsonb in SQL)
    assert isinstance(p["candidates"], str)
    assert len(json.loads(p["candidates"])) == 2
    assert p["content_hash"] == "abc123"


def test_contradiction_params_null_canonical_entity_id():
    c = Contradiction(
        contradiction_id=uuid4(),
        case_id=uuid4(),
        canonical_entity_id=None,
        field_key="parent_names",
        type="CONTRADICTION_CHILD_PARENT",
        candidates=(_candidate("Ghost PARENT"),),
        content_hash="h",
        detected_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
    )
    assert _contradiction_params(c)["canonical_entity_id"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Adapter glue (fake conn)
# ─────────────────────────────────────────────────────────────────────────────


def _ef_row(*, document_id, field_key, value_raw, canonical_entity_id):
    return {
        "extracted_field_id": uuid4(),
        "document_id": document_id,
        "field_key": field_key,
        "value_raw": value_raw,
        "value_canonical": None,
        "confidence": 0.95,
        "bbox_page": None,
        "bbox_x0": None,
        "bbox_y0": None,
        "bbox_x1": None,
        "bbox_y1": None,
        "agent_run_id": uuid4(),
        "canonical_entity_id": canonical_entity_id,
    }


def test_list_fields_builds_models_and_primes_entity_cache():
    case_id, doc, entity = uuid4(), uuid4(), uuid4()
    rows = [
        _ef_row(document_id=doc, field_key="nationality_iso3", value_raw="FRA",
                canonical_entity_id=entity),
        _ef_row(document_id=doc, field_key="surname", value_raw="DUPONT",
                canonical_entity_id=None),
    ]
    store = SupabaseContradictionStore(_FakeConn([_FakeResult(rows)]))
    fields = store.list_extracted_fields_for_case(case_id)
    assert len(fields) == 2
    assert all(isinstance(f, ExtractedField) for f in fields)

    # the detector resolves the canonical entity via the synthetic id of each field
    nat = next(f for f in fields if f.field_key == "nationality_iso3")
    sur = next(f for f in fields if f.field_key == "surname")
    assert store.get_canonical_entity_for_field(_synthetic_field_id(nat)) == entity
    assert store.get_canonical_entity_for_field(_synthetic_field_id(sur)) is None


def test_null_confidence_coerced_so_model_validates():
    case_id, doc = uuid4(), uuid4()
    row = _ef_row(document_id=doc, field_key="dob", value_raw="2015-01-01",
                  canonical_entity_id=None)
    row["confidence"] = None  # ExtractedField requires 0..1; adapter must coerce
    store = SupabaseContradictionStore(_FakeConn([_FakeResult([row])]))
    fields = store.list_extracted_fields_for_case(case_id)
    assert fields[0].confidence == 0.0


def test_upsert_counts_inserted_vs_skipped():
    c1 = Contradiction(
        contradiction_id=uuid4(), case_id=uuid4(), canonical_entity_id=uuid4(),
        field_key="marriage_date", type="CONTRADICTION_MARRIAGE_DATE",
        candidates=(_candidate("2019-06-15"),), content_hash="h1",
        detected_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
    )
    c2 = Contradiction(
        contradiction_id=uuid4(), case_id=uuid4(), canonical_entity_id=uuid4(),
        field_key="marriage_date", type="CONTRADICTION_MARRIAGE_DATE",
        candidates=(_candidate("2019-06-15"),), content_hash="h2",
        detected_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
    )
    # first INSERT returns a row (inserted); second hits ON CONFLICT (no row).
    conn = _FakeConn([_FakeResult([{"contradiction_id": uuid4()}]), _FakeResult([])])
    store = SupabaseContradictionStore(conn)
    inserted, skipped = store.upsert_contradictions([c1, c2])
    assert (inserted, skipped) == (1, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Real-DB integration (opt-in) — needs an rce-capable Postgres
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(
    not os.environ.get("RCE_TEST_DATABASE_URL"),
    reason="set RCE_TEST_DATABASE_URL to run the live rce.* round-trip",
)
def test_round_trip_against_real_db():
    from sqlalchemy import create_engine

    from backend.app.services.contradiction_store_pg import (
        run_contradiction_detection_for_case,
    )

    engine = create_engine(os.environ["RCE_TEST_DATABASE_URL"])
    # Caller is expected to point this at a disposable/seeded case.
    case_id = uuid4()
    out = run_contradiction_detection_for_case(case_id, engine=engine)
    assert isinstance(out, tuple)
