"""The Otto fact reader, and the reconciliation bug it exists to prevent.

On 2026-08-12 at 01:04 UTC, `otto_staging.load_log` recorded batch `WATCH-2026-08-12-w3` as
`reconcile_status='pass'` with `loaded_count=24`, having loaded nothing. 24 was the whole
table's row count, left over from the France batch that had failed at 24 of 109 hours earlier.
The reconciler was answering "how many rows are in the table?" instead of "how many did this
run put there?", so it would have reported success indefinitely while the 85 missing France
facts sat in a chat thread nobody could reach.

`test_a_run_that_loaded_nothing_cannot_report_pass` is that incident. The rest pins the
sourcing gate.

Unlike `test_supplier_csv_ingest.py`, which fixtures the real Card C harvest, these build their
own JSONL: this channel is new and no Otto deliverable has come through it yet. That is a real
limitation — these tests prove the reader handles the format we asked for, not that Otto emits
it. The first card is what proves that.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Sequence

import pytest

from backend.imports.otto.executor import (
    FAIL,
    PARTIAL,
    PASS,
    StageResult,
    derive_status,
    reconcile,
    stage,
)
from backend.imports.otto.parsers import (
    OFFICIAL,
    SEMI_OFFICIAL,
    TIER_AUTO,
    TIER_REVIEW,
    UNOFFICIAL,
    FactRowError,
    classify_source,
    read_jsonl,
)

OFFICIAL_URL = "https://www.service-public.gouv.fr/particuliers/vosdroits/F16003"


def _record(**overrides: Any) -> Dict[str, Any]:
    rec = {
        "destination_country": "FR",
        "entity_topic_key": "eu_free_movement_worker",
        "entity_title": "EU/EEA/Swiss citizen – worker right of residence",
        "fact_type": "fee",
        "fact_key": "cardFee",
        "fact_text": "The EU/EEA/Swiss worker residence card is free of charge.",
        "applies_to": {"role": "primary", "nationality": "EU"},
        "source_url": OFFICIAL_URL,
        "evidence_quote": "La carte de séjour est délivrée gratuitement.",
        "confidence": "high",
    }
    rec.update(overrides)
    return rec


def _write(tmp_path: Path, records: Sequence[Dict[str, Any]]) -> Path:
    path = tmp_path / "FR-immig-test.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


# ── the reconciliation incident ──────────────────────────────────────────────────────

def test_a_run_that_loaded_nothing_cannot_report_pass():
    """The 2026-08-12 false green, pinned.

    A run that inserted 0 rows into a table already holding 24 must not be `pass`. The old
    reconciler counted the table (24), matched nothing against it, and called it success.
    """
    result = StageResult(batch_id="WATCH-2026-08-12-w3", inserted=0, already_present=0)
    ledger = reconcile(
        _NullConn(), result, source_label="(routine)", expected_count=None, dry_run=True
    )
    assert ledger["reconcile_status"] == FAIL
    assert ledger["loaded_count"] == 0


def test_loaded_count_is_this_runs_inserts_never_the_table_total():
    """`loaded_count` reports 3 — what this run wrote — not 27, what the table now holds."""
    result = StageResult(batch_id="FR-immig", inserted=3, already_present=24)
    ledger = reconcile(
        _NullConn(), result, source_label="France", expected_count=109, dry_run=True
    )
    assert ledger["loaded_count"] == 3


def test_an_unknown_expected_count_withholds_pass():
    """No denominator means completeness is unproven, so `partial` — never an assumed pass."""
    assert derive_status(None, 24) == PARTIAL


@pytest.mark.parametrize(
    "expected,accounted,want",
    [(109, 24, PARTIAL), (109, 109, PASS), (109, 110, PASS), (109, 0, FAIL), (None, 0, FAIL)],
)
def test_status_is_derived_from_arithmetic(expected, accounted, want):
    assert derive_status(expected, accounted) == want


def test_the_france_batch_stays_partial_until_a_file_delivers_the_missing_85():
    result = StageResult(batch_id="FR-immig-2026-08-11", inserted=0, already_present=24)
    ledger = reconcile(
        _NullConn(),
        result,
        source_label="France Immigration Research",
        expected_count=109,
        dry_run=True,
    )
    assert ledger["reconcile_status"] == PARTIAL
    assert "85 of 109" in ledger["discrepancy"]


# ── the sourcing gate ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "url,want",
    [
        (OFFICIAL_URL, OFFICIAL),
        ("https://www.udi.no/en/want-to-apply/", OFFICIAL),
        ("https://www.gov.uk/skilled-worker-visa", OFFICIAL),
        ("https://eur-lex.europa.eu/legal-content/EN/TXT/", OFFICIAL),
        ("https://www.campusfrance.org/en/tuition-fees", SEMI_OFFICIAL),
        ("https://some-relocation-blog.com/moving-to-france", UNOFFICIAL),
        ("https://bigmoverslaw.fr/blog/visas", UNOFFICIAL),
        ("", UNOFFICIAL),
    ],
)
def test_the_publisher_domain_decides_the_class(url, want):
    assert classify_source(url) == want


def test_an_unofficial_publisher_is_rejected_not_downgraded(tmp_path):
    path = _write(tmp_path, [_record(source_url="https://some-relocation-blog.com/fr")])
    rows, rejections = read_jsonl(path, batch_id="b1")
    assert rows == []
    assert len(rejections) == 1
    assert "not an official or public-agency publisher" in rejections[0]


def test_a_public_agency_is_kept_but_never_auto_accepted(tmp_path):
    """Campus France is a French public establishment — worth keeping, not statutory.

    The 3 rows already in production from this domain are `needs_review`/`medium`, so this
    tier is the existing convention made enforceable rather than a new policy.
    """
    path = _write(tmp_path, [_record(source_url="https://www.campusfrance.org/en/fees")])
    rows, rejections = read_jsonl(path, batch_id="b1")
    assert rejections == []
    assert rows[0].accuracy_tier == TIER_REVIEW
    assert rows[0].confidence_score <= 0.6


@pytest.mark.parametrize(
    "url",
    [
        "https://www.citizensinformation.ie/en/moving-country/moving-to-ireland/",
        "https://www.revenue.ie/en/jobs-and-pensions/emergency-tax/index.aspx",
        # Bare host and http, to prove the match is on the hostname and not the full URL.
        "revenue.ie/en/starting-work",
        "http://citizensinformation.ie/en/money-and-tax/tax/",
    ],
)
def test_the_irish_statutory_bodies_are_admitted_for_review_not_rejected(url):
    """`.ie` is not `.gov.ie`, so the suffix rule alone read both as a relocation blog.

    That is a real loss, not a tidy default: these two publish the Irish realities nobody
    else states plainly — emergency tax until the Revenue job registration lands, RTB
    tenancy registration, and the non-Schengen consequence of an Irish permission. The
    Citizens Information Board is a statutory agency under the Department of Social
    Protection; Revenue is the tax authority itself.

    SEMI_OFFICIAL and not OFFICIAL on purpose: both restate rules published elsewhere, so
    a fact from here belongs in the review queue rather than being waved through.
    """
    assert classify_source(url) == SEMI_OFFICIAL


def test_an_irish_fact_reaches_the_review_queue_instead_of_the_rejection_list(tmp_path):
    """End to end through `read_jsonl` — the gate has to admit the ROW, not just the URL."""
    path = _write(tmp_path, [_record(
        destination_country="IE",
        entity_topic_key="emergency_tax",
        fact_key="emergencyTaxRate",
        source_url="https://www.revenue.ie/en/jobs-and-pensions/emergency-tax/index.aspx",
    )])
    rows, rejections = read_jsonl(path, batch_id="ie-1")

    assert rejections == []
    assert len(rows) == 1
    assert rows[0].source_class == SEMI_OFFICIAL
    # Kept, but never auto-accepted: a human still signs this off.
    assert rows[0].accuracy_tier == TIER_REVIEW
    assert rows[0].confidence_score <= 0.6
    assert any("not a statutory source" in d for d in rows[0].downgrades)


def test_admitting_the_irish_bodies_did_not_admit_the_whole_ie_tld(tmp_path):
    """The fix is two hostnames, not a `.ie` suffix. An Irish relocation blog stays out."""
    assert classify_source("https://dublinrelocationblog.ie/moving-guide") == UNOFFICIAL
    assert classify_source("https://www.irish-immigration-lawyers.ie/permits") == UNOFFICIAL
    # Nor a lookalike that merely ends with the string.
    assert classify_source("https://notrevenue.ie/tax") == UNOFFICIAL


def test_a_fact_with_no_evidence_quote_cannot_be_auto_accepted(tmp_path):
    """All 24 rows in production have `evidence_quote IS NULL` — nothing in them can be
    re-checked without re-reading the source. Allowed in, never waved through."""
    path = _write(tmp_path, [_record(evidence_quote=None)])
    rows, _ = read_jsonl(path, batch_id="b1")
    assert rows[0].accuracy_tier == TIER_REVIEW
    assert any("evidence_quote" in d for d in rows[0].downgrades)


def test_an_official_source_with_a_quote_is_auto_accepted(tmp_path):
    path = _write(tmp_path, [_record()])
    rows, rejections = read_jsonl(path, batch_id="b1")
    assert rejections == []
    assert rows[0].accuracy_tier == TIER_AUTO
    assert rows[0].downgrades == []


def test_otto_calling_its_own_finding_high_does_not_win(tmp_path):
    """`confidence: high` on a blog is still a rejection; on a public agency still a review."""
    path = _write(
        tmp_path,
        [_record(confidence="high", source_url="https://www.campusfrance.org/en/fees")],
    )
    rows, _ = read_jsonl(path, batch_id="b1")
    assert rows[0].accuracy_tier == TIER_REVIEW


# ── file shape ───────────────────────────────────────────────────────────────────────

def test_dedupe_key_matches_the_convention_already_in_production(tmp_path):
    path = _write(tmp_path, [_record()])
    rows, _ = read_jsonl(path, batch_id="b1")
    assert rows[0].dedupe_key == "FR|eu_free_movement_worker|cardFee"


def test_two_rows_with_the_same_fact_key_collide_here_naming_both_lines(tmp_path):
    """The table's UNIQUE (dedupe_key) would raise an IntegrityError naming neither line."""
    path = _write(tmp_path, [_record(), _record(fact_text="different wording")])
    rows, rejections = read_jsonl(path, batch_id="b1")
    assert len(rows) == 1
    assert "duplicates line 1" in rejections[0]


def test_a_missing_required_field_names_the_line_and_the_field(tmp_path):
    path = _write(tmp_path, [_record(), _record(fact_key="", entity_topic_key="other")])
    with pytest.raises(FactRowError, match="line 2.*fact_key"):
        read_jsonl(path, batch_id="b1")


def test_malformed_json_stops_the_read_rather_than_importing_the_readable_half(tmp_path):
    """Importing the parseable prefix would report a truncated batch as a complete one."""
    path = tmp_path / "b.jsonl"
    path.write_text(json.dumps(_record()) + "\n{ truncated…\n", encoding="utf-8")
    with pytest.raises(FactRowError, match="line 2"):
        read_jsonl(path, batch_id="b1")


def test_an_unknown_fact_type_is_normalised_not_rejected(tmp_path):
    """Research finds shapes we did not predict; the column still has to stay queryable."""
    path = _write(tmp_path, [_record(fact_type="biometrics_appointment")])
    rows, _ = read_jsonl(path, batch_id="b1")
    assert rows[0].fact_type == "other"


# ── staging ──────────────────────────────────────────────────────────────────────────

def test_a_dry_run_counts_rows_already_in_the_table_as_already_present(tmp_path):
    path = _write(tmp_path, [_record(), _record(fact_key="cardDuration")])
    rows, _ = read_jsonl(path, batch_id="b1")
    conn = _NullConn(existing={"FR|eu_free_movement_worker|cardFee"})
    result = stage(conn, rows, dry_run=True)
    assert result.already_present == 1
    assert result.inserted == 1


def test_a_rerun_of_a_fully_loaded_batch_inserts_nothing_and_still_passes(tmp_path):
    """`accounted_for` is inserted + already_present, so re-running a complete batch is a
    pass with `loaded_count=0` — distinct from the false green, which had neither."""
    path = _write(tmp_path, [_record(), _record(fact_key="cardDuration")])
    rows, _ = read_jsonl(path, batch_id="b1")
    conn = _NullConn(existing={
        "FR|eu_free_movement_worker|cardFee",
        "FR|eu_free_movement_worker|cardDuration",
    })
    result = stage(conn, rows, dry_run=True)
    ledger = reconcile(conn, result, source_label="x", expected_count=2, dry_run=True)
    assert result.inserted == 0
    assert ledger["reconcile_status"] == PASS
    assert ledger["loaded_count"] == 0


def test_rejections_are_carried_into_the_discrepancy(tmp_path):
    result = stage(_NullConn(), [], rejections=["line 4: bad source"], dry_run=True)
    ledger = reconcile(
        _NullConn(), result, source_label="x", expected_count=5, dry_run=True
    )
    assert "1 row(s) rejected on sourcing" in ledger["discrepancy"]


class _NullConn:
    """Minimal SQLAlchemy Connection stand-in: answers the one SELECT `stage()` makes."""

    def __init__(self, existing: set | None = None) -> None:
        self._existing = existing or set()

    def execute(self, _stmt: Any, params: Dict[str, Any] | None = None) -> Any:
        keys = (params or {}).get("keys") or []
        return _Rows([(k,) for k in keys if k in self._existing])


class _Rows:
    def __init__(self, rows: List[Any]) -> None:
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return self._rows[0][0] if self._rows else None
