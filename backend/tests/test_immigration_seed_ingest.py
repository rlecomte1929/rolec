"""The rules that decide what the immigration seed is allowed to write.

Two of these tests exist for a specific hazard rather than for coverage.

`test_adopts_existing_doc_without_rewriting_it` and `test_adopts_existing_entity_without_
downgrading_status` cover the reason `executor.py` does not reuse `db.upsert_knowledge_doc_by_url`
/ `db.upsert_requirement_entity`. Measured against production on 2026-08-12, this seed's 86 URLs
collide with 23 existing `knowledge_docs` and its topics with 5 existing `requirement_entities`.
Those upserts rewrite `text_content` and force `status='pending'`, so the three-line
implementation silently un-approves rows a human already signed off. Both tests fail against an
upsert-based executor and pass against this one — the distinction they are here to hold.

`test_evidence_quote_absent_from_body_is_not_written` is guard #1816: a quote that does not
appear in the document actually fetched must not be stored, because a fabricated evidence row
reads as sourced and is worse than a missing one.

The parser tests run against the **real** seed file, so the UK->GB and med->medium mappings are
proven against the 8 and 7 rows that actually carry them rather than against a fixture written
to agree with the code.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from backend.imports.immigration import executor, parsers
from backend.imports.immigration.fetcher import FETCH_FAILED, FETCHED, FetchedDoc

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = REPO_ROOT / "supabase" / "seed" / "obligations" / "immigration_facts_seed.json"

BODY = (
    "To work in the country you need a residence permit. "
    "The application fee is 320 EUR and must be paid before you submit. "
    "Processing takes up to eight weeks."
)


def _doc(url: str = "https://example.gov/permit", body: str = BODY, ok: bool = True) -> FetchedDoc:
    return FetchedDoc(
        source_url=url,
        final_url=url,
        title="Residence permit",
        publisher="example.gov",
        text_content=body if ok else "",
        content_sha256="deadbeef" if ok else None,
        fetch_status=FETCHED if ok else FETCH_FAILED,
        error=None if ok else "HTTPError: 503",
    )


def _row(**over) -> parsers.FactRow:
    base = dict(
        destination_country="GB",
        topic_key="skilled_worker_visa",
        entity_title="Skilled Worker visa",
        fact_type="fee",
        fact_key="applicationFee",
        fact_text="The application fee is 320 EUR.",
        applies_to={"role": "primary"},
        source_url="https://example.gov/permit",
        evidence_quote=None,
        confidence="high",
        accuracy_tier="auto_accepted",
        fixes=(),
    )
    base.update(over)
    return parsers.FactRow(**base)


class FakeConn:
    """Records writes; answers the executor's four lookups from configured state.

    Deliberately not a SQLite engine: the executor's SQL uses `CAST(... AS jsonb)`, which SQLite
    cannot parse, and a fixture that had to drop the cast would stop testing the statement that
    actually runs. Real CHECK/FK/NOT NULL enforcement is verified against Postgres in the P5
    validation, not here.
    """

    def __init__(self, *, packs=None, docs=None, entities=None, fact_keys=None, doc_lens=None):
        self.packs = packs or {}            # country -> pack id
        self.docs = docs or {}              # url -> doc id
        self.doc_lens = doc_lens or {}      # doc id -> length(text_content); default a real body
        self.entities = entities or {}      # (country, topic) -> entity id
        self.fact_keys = fact_keys or {}    # entity id -> [fact_key]
        self.writes: List[Dict[str, Any]] = []
        self.updates: List[Dict[str, Any]] = []

    def execute(self, stmt, params=None):
        sql = " ".join(str(stmt).split())
        params = params or {}
        if sql.startswith("INSERT"):
            table = sql.split("INSERT INTO ")[1].split(" ")[0]
            self.writes.append({"table": table, **params})
            return _Result(None)
        if sql.startswith("UPDATE"):
            table = sql.split("UPDATE ")[1].split(" ")[0]
            self.updates.append({"table": table, **params})
            return _Result(None)
        if "FROM knowledge_packs" in sql:
            return _Result(self.packs.get(params["country"]))
        if "FROM knowledge_docs" in sql:
            doc_id = self.docs.get(params["url"])
            if not doc_id:
                return _Result(None)
            # default to a real body so existing tests keep exercising the adopt path
            return _Result(doc_id, extra=(self.doc_lens.get(doc_id, 20_000),))
        if "FROM requirement_entities" in sql:
            return _Result(self.entities.get((params["country"], params["topic_key"])))
        if "FROM requirement_facts" in sql:
            return _Result(None, rows=[(k,) for k in self.fact_keys.get(params["entity_id"], [])])
        raise AssertionError(f"unexpected statement: {sql}")

    def inserted(self, table: str) -> List[Dict[str, Any]]:
        return [w for w in self.writes if w["table"] == table]

    def updated(self, table: str) -> List[Dict[str, Any]]:
        return [u for u in self.updates if u["table"] == table]


class _Result:
    def __init__(self, value: Optional[str], rows: Optional[List] = None, extra: tuple = ()):
        self._value = value
        self._rows = rows or []
        self._extra = extra

    def first(self):
        return (self._value, *self._extra) if self._value else None

    def __iter__(self):
        return iter(self._rows)


# --------------------------------------------------------------------------- parser


def test_seed_file_is_readable_and_complete():
    seed = parsers.read_seed(SEED_PATH)
    assert seed.rejections == []
    assert len(seed.rows) == 140
    assert len({r.destination_country for r in seed.rows}) == 15
    assert len(seed.source_urls) == 83


def test_uk_is_stored_as_gb():
    """'UK' is not in the destination_country CHECK list; 8 real seed rows carry it."""
    raw = json.loads(SEED_PATH.read_text())
    assert sum(1 for f in raw if f["destination_country"] == "UK") == 8, "seed lost its UK rows"

    seed = parsers.read_seed(SEED_PATH)
    assert not [r for r in seed.rows if r.destination_country == "UK"]
    assert len([r for r in seed.rows if r.destination_country == "GB"]) == 8
    assert all(r.destination_country in parsers.DESTINATION_COUNTRIES for r in seed.rows)


def test_med_is_normalised_to_medium():
    raw = json.loads(SEED_PATH.read_text())
    assert sum(1 for f in raw if f["confidence"] == "med") == 7, "seed lost its 'med' rows"

    seed = parsers.read_seed(SEED_PATH)
    assert {r.confidence for r in seed.rows} <= parsers.CONFIDENCES
    assert len([r for r in seed.rows if r.confidence == "medium"]) == 10  # 7 fixed + 3 already


def test_every_seed_row_satisfies_the_check_enums():
    seed = parsers.read_seed(SEED_PATH)
    for row in seed.rows:
        assert row.fact_type in parsers.FACT_TYPES
        assert row.confidence in parsers.CONFIDENCES
        assert row.destination_country in parsers.DESTINATION_COUNTRIES


def test_unknown_fact_type_is_rejected_not_coerced(tmp_path):
    """`other` is a real category. Defaulting to it files a fee where no reviewer looks."""
    path = tmp_path / "seed.json"
    path.write_text(json.dumps([{
        "destination_country": "GB", "topic_key": "t", "entity_title": "T",
        "fact_type": "prerequisite", "fact_key": "k", "fact_text": "x",
        "source_url": "https://example.gov/a", "confidence": "high",
        "accuracy_tier": "auto_accepted", "applies_to": {},
    }]))
    seed = parsers.read_seed(path)
    assert seed.rows == []
    assert "fact_type 'prerequisite'" in seed.rejections[0]


def test_duplicate_natural_key_within_the_file_is_rejected(tmp_path):
    one = {
        "destination_country": "GB", "topic_key": "t", "entity_title": "T",
        "fact_type": "fee", "fact_key": "k", "fact_text": "x",
        "source_url": "https://example.gov/a", "confidence": "high",
        "accuracy_tier": "auto_accepted", "applies_to": {},
    }
    path = tmp_path / "seed.json"
    path.write_text(json.dumps([one, dict(one, fact_text="y")]))
    seed = parsers.read_seed(path)
    assert len(seed.rows) == 1
    assert "duplicate" in seed.rejections[0]


def test_http_source_url_is_upgraded_to_https_and_recorded():
    """One real seed row (BE) carries http://. The host 301s to https and serves the same page."""
    raw = json.loads(SEED_PATH.read_text())
    assert sum(1 for f in raw if f["source_url"].startswith("http://")) == 1

    seed = parsers.read_seed(SEED_PATH)
    upgraded = [r for r in seed.rows if "source_url http->https" in r.fixes]
    assert len(upgraded) == 1
    assert upgraded[0].source_url.startswith("https://")
    assert all(r.source_url.startswith("https://") for r in seed.rows)


def test_non_http_scheme_is_rejected(tmp_path):
    path = tmp_path / "seed.json"
    path.write_text(json.dumps([{
        "destination_country": "GB", "topic_key": "t", "entity_title": "T",
        "fact_type": "fee", "fact_key": "k", "fact_text": "x",
        "source_url": "ftp://example.gov/a", "confidence": "high",
        "accuracy_tier": "auto_accepted", "applies_to": {},
    }]))
    seed = parsers.read_seed(path)
    assert seed.rows == []
    assert "not http(s)" in seed.rejections[0]


def test_normalise_text_folds_presentation_without_changing_words():
    assert parsers.normalise_text("fee is  320–340") == "fee is 320-340"
    assert parsers.normalise_text("the “permit”") == 'the "permit"'
    assert "eight weeks" not in parsers.normalise_text("eight  months")


def test_truncated_evidence_quote_is_rejected_from_seed(tmp_path):
    path = tmp_path / "seed.json"
    path.write_text(json.dumps([{
        "destination_country": "GB", "topic_key": "t", "entity_title": "T",
        "fact_type": "fee", "fact_key": "k", "fact_text": "The fee is 320 EUR.",
        "source_url": "https://example.gov/a", "confidence": "high",
        "accuracy_tier": "auto_accepted", "applies_to": {},
        "evidence_quote": "a" * 255,
    }]))
    seed = parsers.read_seed(path)
    assert seed.rows == []
    assert "column limit" in seed.rejections[0]


def test_utf8_quote_is_kept_in_original_language(tmp_path):
    quote = "La carte de séjour est délivrée gratuitement."
    path = tmp_path / "seed.json"
    path.write_text(json.dumps([{
        "destination_country": "FR", "topic_key": "t", "entity_title": "T",
        "fact_type": "fee", "fact_key": "k", "fact_text": "The card is free.",
        "source_url": "https://example.gov/a", "confidence": "high",
        "accuracy_tier": "auto_accepted", "applies_to": {},
        "evidence_quote": quote,
    }]))
    seed = parsers.read_seed(path)
    assert seed.rejections == []
    assert seed.rows[0].evidence_quote == quote
    assert "séjour" in seed.rows[0].evidence_quote


# --------------------------------------------------------------------------- evidence


def test_evidence_quote_present_in_body_is_verified_and_stored():
    conn = FakeConn()
    row = _row(evidence_quote="The application fee is 320 EUR")
    result = executor.ingest(conn, [row], fetcher=lambda u: _doc(), dry_run=False)

    assert result.facts_inserted == 1
    assert result.evidence_verified == ["GB/skilled_worker_visa/applicationFee"]
    assert result.needs_manual_evidence == []
    assert conn.inserted("requirement_facts")[0]["evidence_quote"] == "The application fee is 320 EUR"


def test_evidence_quote_absent_from_body_is_not_written():
    """Guard #1816. A quote the document does not contain must never reach the table."""
    conn = FakeConn()
    row = _row(evidence_quote="The application fee is 999 EUR")
    result = executor.ingest(conn, [row], fetcher=lambda u: _doc(), dry_run=False)

    assert result.facts_inserted == 0
    assert conn.inserted("requirement_facts") == []
    assert len(result.needs_manual_evidence) == 1
    assert "quote not found" in result.needs_manual_evidence[0]


def test_keep_unmatched_writes_the_fact_but_never_the_unverified_string():
    """The configurable part is the fact's fate. Storing the unverified string is not.

    All 8 quoted rows in this seed are reviewer caveats ("…confirm precise deep link"), not
    citations, so dropping their facts would discard sourced claims over a column misuse. The
    string itself must still never reach `evidence_quote` — that is guard #1816, and this test
    is what stops `keep_unmatched` from quietly becoming a way around it.
    """
    conn = FakeConn()
    row = _row(evidence_quote="Otto flagged source ambiguity — confirm exact basis.")
    result = executor.ingest(
        conn, [row], fetcher=lambda u: _doc(), dry_run=False, keep_unmatched=True
    )

    assert result.facts_inserted == 1
    written = conn.inserted("requirement_facts")[0]
    assert written["evidence_quote"] is None, "the unverified string must never be stored"
    assert written["source_doc_id"], "the fact still gets a real fetched document"
    assert len(result.needs_manual_evidence) == 1, "still on the worklist"


def test_evidence_matching_tolerates_typography_but_not_different_words():
    conn = FakeConn()
    typographic = _row(evidence_quote="The application fee is 320 EUR")
    assert executor.ingest(
        conn, [typographic], fetcher=lambda u: _doc(), dry_run=True
    ).facts_inserted == 1

    reworded = _row(evidence_quote="The application fee is 320 GBP")
    assert executor.ingest(
        FakeConn(), [reworded], fetcher=lambda u: _doc(), dry_run=True
    ).facts_inserted == 0


def test_unquoted_fact_is_stored_with_a_real_document_by_default():
    """134 of 142 seed facts carry no quote. Nothing is fabricated: the doc body is fetched."""
    conn = FakeConn()
    result = executor.ingest(conn, [_row()], fetcher=lambda u: _doc(), dry_run=False)

    assert result.facts_inserted == 1
    assert conn.inserted("requirement_facts")[0]["evidence_quote"] is None
    assert conn.inserted("knowledge_docs")[0]["text_content"] == BODY


def test_require_evidence_narrows_the_run_to_quoted_facts():
    conn = FakeConn()
    result = executor.ingest(
        conn, [_row()], fetcher=lambda u: _doc(), dry_run=False, require_evidence=True
    )
    assert result.facts_inserted == 0
    assert result.skipped_unquoted == 1


# --------------------------------------------------------------------------- fetch


def test_fetch_failure_writes_no_document_and_no_fact():
    """`text_content` is NOT NULL. A fact with no document is skipped, never faked."""
    conn = FakeConn()
    result = executor.ingest(
        conn, [_row()], fetcher=lambda u: _doc(ok=False), dry_run=False
    )
    assert conn.writes == []
    assert result.facts_inserted == 0
    assert result.skipped_no_document == 1
    assert len(result.fetch_failed) == 1


def test_facts_sharing_a_url_fetch_once_and_share_one_document():
    conn = FakeConn()
    calls: List[str] = []

    def counting(url):
        calls.append(url)
        return _doc()

    rows = [_row(fact_key="applicationFee"), _row(fact_key="processingTime")]
    result = executor.ingest(conn, rows, fetcher=counting, dry_run=False)

    assert calls == ["https://example.gov/permit"]
    assert result.docs_created == 1
    assert result.facts_inserted == 2


def test_stored_source_url_is_the_seed_url_not_the_redirect_target():
    """Dedupe keys on source_url; storing the redirect target makes the next run re-insert."""
    conn = FakeConn()
    redirected = FetchedDoc(
        source_url="https://example.gov/permit", final_url="https://example.gov/en/permit-2024",
        title="T", publisher="example.gov", text_content=BODY,
        content_sha256="x", fetch_status=FETCHED,
    )
    executor.ingest(conn, [_row()], fetcher=lambda u: redirected, dry_run=False)
    assert conn.inserted("knowledge_docs")[0]["source_url"] == "https://example.gov/permit"


# --------------------------------------------------------------------------- adoption


def test_adopts_existing_doc_without_rewriting_it():
    """23 of the seed's 86 URLs already exist in production. Their bodies must survive."""
    conn = FakeConn(docs={"https://example.gov/permit": "doc-1"})
    result = executor.ingest(conn, [_row()], fetcher=lambda u: _doc(), dry_run=False)

    assert result.docs_adopted == 1
    assert result.docs_created == 0
    assert conn.inserted("knowledge_docs") == [], "must not rewrite an existing document"
    assert conn.inserted("requirement_facts")[0]["source_doc_id"] == "doc-1"


def test_repairs_a_stub_document_body():
    """A stub is repaired, not adopted — the hole the first live run exposed.

    Adopting any existing row regardless of contents attached 32 of the seed's 92 facts to
    `"Otto bridge capture, unverified — see source_url"` (48 chars) while the page had been
    fetched fine. The fact then cited a placeholder as its source.
    """
    conn = FakeConn(docs={"https://example.gov/permit": "doc-1"},
                    doc_lens={"doc-1": 48})
    result = executor.ingest(conn, [_row()], fetcher=lambda u: _doc(), dry_run=False)

    assert result.docs_repaired == 1
    assert result.docs_adopted == 0
    repaired = conn.updated("knowledge_docs")
    assert len(repaired) == 1
    assert repaired[0]["text_content"] == BODY
    assert repaired[0]["floor"] == executor.MIN_REAL_DOC_CHARS, "guarded in SQL, not just here"


def test_never_repairs_a_document_that_already_has_a_real_body():
    """The floor is what stops the repair becoming the destructive upsert. No real body is lost."""
    conn = FakeConn(docs={"https://example.gov/permit": "doc-1"},
                    doc_lens={"doc-1": 20_000})
    result = executor.ingest(conn, [_row()], fetcher=lambda u: _doc(), dry_run=False)

    assert result.docs_adopted == 1
    assert result.docs_repaired == 0
    assert conn.updated("knowledge_docs") == [], "must not touch a real document"


def test_dry_run_does_not_repair():
    conn = FakeConn(docs={"https://example.gov/permit": "doc-1"}, doc_lens={"doc-1": 48})
    result = executor.ingest(conn, [_row()], fetcher=lambda u: _doc(), dry_run=True)
    assert result.docs_repaired == 1
    assert conn.writes == []


def test_adopts_existing_entity_without_downgrading_status():
    """An approved entity must not be forced back to 'pending' by a seed run."""
    conn = FakeConn(entities={("GB", "skilled_worker_visa"): "ent-1"})
    result = executor.ingest(conn, [_row()], fetcher=lambda u: _doc(), dry_run=False)

    assert result.entities_adopted == 1
    assert conn.inserted("requirement_entities") == [], "must not touch an existing entity"
    assert conn.inserted("requirement_facts")[0]["entity_id"] == "ent-1"


def test_adopts_existing_pack_rather_than_creating_a_second():
    conn = FakeConn(packs={"GB": "pack-1"})
    result = executor.ingest(conn, [_row()], fetcher=lambda u: _doc(), dry_run=False)

    assert result.packs_adopted == 1
    assert conn.inserted("knowledge_packs") == []
    assert conn.inserted("knowledge_docs")[0]["pack_id"] == "pack-1"


# --------------------------------------------------------------------------- idempotency


def test_second_run_inserts_nothing():
    """Validation criterion 1. Dedupe is on (entity_id, fact_key) — there is no unique index."""
    conn = FakeConn(
        entities={("GB", "skilled_worker_visa"): "ent-1"},
        docs={"https://example.gov/permit": "doc-1"},
        packs={"GB": "pack-1"},
        fact_keys={"ent-1": ["applicationFee"]},
    )
    result = executor.ingest(conn, [_row()], fetcher=lambda u: _doc(), dry_run=False)

    assert result.facts_inserted == 0
    assert result.facts_already_present == 1
    assert result.facts_accounted_for == 1
    assert conn.writes == []


def test_two_seed_rows_with_one_fact_key_insert_once():
    """The in-run guard: a new entity has no rows to read, so dedupe must track what it wrote."""
    conn = FakeConn()
    rows = [_row(), _row(fact_text="restated")]
    result = executor.ingest(conn, rows, fetcher=lambda u: _doc(), dry_run=False)

    assert result.facts_inserted == 1
    assert result.facts_already_present == 1
    assert len(conn.inserted("requirement_facts")) == 1


def test_dry_run_writes_nothing_but_returns_the_live_counts():
    """Validation criterion 4: the preview's numbers must be the numbers --apply produces."""
    rows = [_row(fact_key="applicationFee"), _row(fact_key="processingTime")]

    dry = executor.ingest(FakeConn(), rows, fetcher=lambda u: _doc(), dry_run=True)
    live_conn = FakeConn()
    live = executor.ingest(live_conn, rows, fetcher=lambda u: _doc(), dry_run=False)

    assert dry.facts_inserted == live.facts_inserted == 2
    assert dry.docs_created == live.docs_created == 1
    assert dry.entities_created == live.entities_created == 1
    assert dry.per_country == live.per_country == {"GB": 2}
    assert len(live_conn.writes) > 0


def test_dry_run_issues_no_insert():
    conn = FakeConn()
    executor.ingest(conn, [_row()], fetcher=lambda u: _doc(), dry_run=True)
    assert conn.writes == []


# --------------------------------------------------------------------------- shape


def test_everything_written_is_pending():
    conn = FakeConn()
    executor.ingest(conn, [_row()], fetcher=lambda u: _doc(), dry_run=False)

    assert conn.inserted("requirement_facts")[0]["status"] == "pending"
    assert conn.inserted("requirement_entities")[0]["status"] == "pending"
    assert conn.inserted("requirement_entities")[0]["domain_area"] == "immigration"


def test_applies_to_is_serialised_as_json():
    conn = FakeConn()
    executor.ingest(conn, [_row(applies_to={"role": "primary"})],
                    fetcher=lambda u: _doc(), dry_run=False)
    assert json.loads(conn.inserted("requirement_facts")[0]["applies_to"]) == {"role": "primary"}


@pytest.mark.parametrize("country", ["GB", "FR", "SG"])
def test_per_country_counts_are_reported(country):
    conn = FakeConn()
    result = executor.ingest(conn, [_row(destination_country=country)],
                             fetcher=lambda u: _doc(), dry_run=True)
    assert result.per_country == {country: 1}
