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
    summarise,
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
        # Singapore statutory bodies publish under `.gov.sg`; the bare `gov` suffix does not
        # catch them (host ends in `.sg`). Regression guard for the FR->SG batch.
        ("https://www.mom.gov.sg/passes-and-permits/employment-pass/eligibility", OFFICIAL),
        ("https://www.ica.gov.sg/enter-transit-depart/entering-singapore", OFFICIAL),
        # Ecuador statutory bodies publish under `.gob.ec`; `gob.es` (Spain) does not catch
        # `.ec`, and the bare `gov` does not either. Regression guard for the US->EC batch.
        ("https://www.registrocivil.gob.ec/cedulacion/", OFFICIAL),
        ("https://www.iess.gob.ec/es/afiliados", OFFICIAL),
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


def test_truncated_evidence_quote_is_rejected_not_stored(tmp_path):
    path = _write(tmp_path, [_record(evidence_quote="a" * 255)])
    rows, rejections = read_jsonl(path, batch_id="b1")
    assert rows == []
    assert len(rejections) == 1
    assert "column limit" in rejections[0]


def test_utf8_evidence_quote_is_kept_verbatim(tmp_path):
    quote = "La carte de séjour est délivrée gratuitement."
    path = _write(tmp_path, [_record(evidence_quote=quote)])
    rows, rejections = read_jsonl(path, batch_id="b1")
    assert rejections == []
    assert rows[0].evidence_quote == quote


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


@pytest.mark.parametrize(
    "url",
    [
        "https://www.irishimmigration.ie/registering-your-immigration-permission/",
        "irishimmigration.ie/registering-your-immigration-permission/required-documents/",
        "http://irishimmigration.ie/",
    ],
)
def test_immigration_service_delivery_is_official_not_merely_semi(url):
    """ISD publishes the rule; Citizens Information restates it. That is the whole line.

    Immigration Service Delivery is the Department of Justice unit that runs registration
    and issues the IRP, so it is the primary source for first-time registration even though
    the host is `irishimmigration.ie` and not `gov.ie`. Left unlisted, the suffix rule scored
    it UNOFFICIAL and rejected the entire entity — the 90-day registration deadline, the €300
    fee and the 10-working-day card delivery all vanished from a 20-fact deliverable while
    the import still reported success on the other 16.

    OFFICIAL, unlike revenue.ie/citizensinformation.ie above, because a fact here needs no
    human to confirm it against a further source; it is already at the publisher.
    """
    assert classify_source(url) == OFFICIAL


def test_admitting_the_irish_bodies_did_not_admit_the_whole_ie_tld(tmp_path):
    """The fix is named hostnames, not a `.ie` suffix. An Irish relocation blog stays out."""
    assert classify_source("https://dublinrelocationblog.ie/moving-guide") == UNOFFICIAL
    assert classify_source("https://www.irish-immigration-lawyers.ie/permits") == UNOFFICIAL
    # Nor a lookalike that merely ends with the string.
    assert classify_source("https://notrevenue.ie/tax") == UNOFFICIAL
    assert classify_source("https://not-irishimmigration.ie/permits") == UNOFFICIAL


@pytest.mark.parametrize(
    "url",
    [
        "https://www2.hse.ie/services/schemes-allowances/medical-cards/",
        "https://www.rtb.ie/registration-and-compliance/tenancy-registration",
        "https://www.ndls.ie/exchange-a-foreign-driving-licence.html",
        "https://www.rsa.ie/services/licensed-drivers/exchange-your-licence",
        "https://www.gov.ie/en/service/12e6c-get-a-personal-public-service-ppsn-number/",
        "https://services.mywelfare.ie/en/topics/identity/ppsn/",
        "https://www.welfare.ie/en/Pages/PPSN.aspx",
    ],
)
def test_the_bodies_an_eu_free_mover_deals_with_are_official(url):
    """The non-EEA track is allowlisted; the free-mover track was not, and that is AIQ-1994.

    `irishimmigration.ie` above covers registration and the IRP — none of which an EU/EEA
    national ever touches. What a free mover actually needs is a PPSN, health entitlement, a
    tenancy and a driving licence, and every one of those is published by a body outside
    `gov.ie`. Unlisted, the suffix rule scored them UNOFFICIAL and `stage()` rejects rather
    than downgrades, so an Ireland deliverable would lose those topics entirely while
    reporting success on whatever survived — exactly the Spain failure recorded below.
    """
    assert classify_source(url) == OFFICIAL


def test_admitting_the_free_mover_bodies_did_not_admit_their_lookalikes(tmp_path):
    """Named hosts, not substrings: `_matches` requires the host or a dotted subdomain."""
    assert classify_source("https://nothse.ie/medical-cards") == UNOFFICIAL
    assert classify_source("https://myrtb.ie/tenancy") == UNOFFICIAL
    assert classify_source("https://ndls-guide.ie/exchange") == UNOFFICIAL
    # `mywelfare.ie` does not end in `.welfare.ie`, so both are listed separately and
    # neither one admits the other's lookalikes.
    assert classify_source("https://fakewelfare.ie/ppsn") == UNOFFICIAL


@pytest.mark.parametrize(
    "url",
    [
        "https://skat.dk/en-us/businesses/employees-and-pay/non-danish-labour/",
        "https://www.bzst.de/EN/Private_individuals/Tax_identification_number/",
        "https://service.berlin.de/dienstleistung/120686/",
        "https://www.rundfunkbeitrag.de/welcome/english",
        # Bare host and http, to prove the match is on the hostname and not the full URL.
        "skat.dk/en-us/individuals",
        "http://bzst.de/EN/Home/home_node.html",
    ],
)
def test_the_danish_and_german_tax_and_registration_bodies_are_official(url):
    """Neither `.dk` nor `.de` has a governmental suffix in the allowlist, so all four of
    these scored UNOFFICIAL and were rejected outright.

    That is not a tidy default — it silently removed **9 of the 20 facts** in the B3
    Nordics/UK/DE batch, and it removed them by country: NO->DK, DK->DE and DE->DK each
    ended with zero surviving facts while the import reported success on the other 11. A
    rejection list that clusters on a country is an allowlist bug, not a research failure.

    All four publish their own rule rather than restating one, which is what puts them here
    and not in `_SEMI_OFFICIAL_HOSTS`: SKAT is the Danish tax authority, the BZSt is the
    Federal Central Tax Office that issues the German tax ID, service.berlin.de is the Land
    of Berlin's own service catalogue for the Anmeldung, and Rundfunkbeitrag is the body
    that levies the fee it describes.
    """
    assert classify_source(url) == OFFICIAL


@pytest.mark.parametrize(
    "url",
    [
        "https://lifeindenmark.borger.dk/apps-and-digital-services/mitid",
        "https://borger.dk/",
        "http://lifeindenmark.borger.dk/theme/when-you-arrive",
    ],
)
def test_borger_dk_is_admitted_for_review_not_rejected(url):
    """borger.dk is the Danish state's official citizen portal, run by the Agency for
    Digital Government — so it belongs in, not out.

    SEMI_OFFICIAL and not OFFICIAL for the same reason as citizensinformation.ie: it is a
    portal that restates what SKAT, the CPR office and the regions publish elsewhere. A
    fact sourced here is worth keeping and belongs in the review queue.
    """
    assert classify_source(url) == SEMI_OFFICIAL


def test_a_danish_fact_reaches_the_review_queue_instead_of_the_rejection_list(tmp_path):
    """End to end through `read_jsonl` — the gate has to admit the ROW, not just the URL."""
    path = _write(tmp_path, [_record(
        destination_country="DK",
        entity_topic_key="registration_cpr",
        fact_key="cprDeadline",
        source_url="https://lifeindenmark.borger.dk/theme/when-you-arrive",
    )])
    rows, rejections = read_jsonl(path, batch_id="dk-1")

    assert rejections == []
    assert len(rows) == 1
    assert rows[0].source_class == SEMI_OFFICIAL
    # Kept, but never auto-accepted: a human still signs this off.
    assert rows[0].accuracy_tier == TIER_REVIEW


def test_admitting_the_dk_de_bodies_did_not_admit_the_whole_tld(tmp_path):
    """The fix is named hostnames, not a `.dk`/`.de` suffix. Blogs and law firms stay out."""
    assert classify_source("https://copenhagenrelocationblog.dk/guide") == UNOFFICIAL
    assert classify_source("https://www.berlin-immigration-lawyers.de/permits") == UNOFFICIAL
    assert classify_source("https://expat-guide.de/anmeldung") == UNOFFICIAL
    # Nor a lookalike that merely ends with the string.
    assert classify_source("https://notskat.dk/tax") == UNOFFICIAL
    assert classify_source("https://not-rundfunkbeitrag.de/fee") == UNOFFICIAL
    assert classify_source("https://fake-borger.dk/mitid") == UNOFFICIAL
@pytest.mark.parametrize(
    "url",
    [
        "https://www.boe.es/buscar/act.php?id=BOE-A-2000-544",
        "https://www.seg-social.es/wps/portal/wss/internet/Trabajadores",
        "https://www.agenciatributaria.es/AEAT.internet/Inicio.shtml",
        "https://www.policia.es/_es/extranjeria_documentacion.php",
        "https://www.sepe.es/HomeSepe/en/Personas.html",
        # Bare host and http, to prove the match is on the hostname and not the full URL.
        "seg-social.es/wps/portal/wss/internet/Inicio",
        "http://boe.es/diario_boe/",
    ],
)
def test_the_spanish_statutory_bodies_are_official(url):
    """Spain was recognised only through the `gob.es` suffix, so every statutory body that
    does not sit under `gob.es` scored UNOFFICIAL and was rejected outright.

    Two of these are worth naming individually. `boe.es` is the Boletín Oficial del Estado,
    which publishes the law itself — the direct counterpart of `legifrance.gouv.fr` and
    `lovdata.no`, both of which were already allowlisted; Spain's state gazette being scored
    as a relocation blog is the starkest gap in the set. And the AEAT was *half* admitted:
    `agenciatributaria.gob.es` (the sede) passed on the suffix while `agenciatributaria.es`
    did not, so whether a tax fact survived depended on which of the agency's own two domains
    the researcher happened to cite.

    All five publish their own rule rather than restating one, which is what puts them here
    and not in `_SEMI_OFFICIAL_HOSTS`: the BOE is the gazette of record, the Seguridad Social
    administers and publishes social security registration, the AEAT is the tax authority,
    the Policía Nacional issues the NIE and TIE, and the SEPE is the state employment service.
    """
    assert classify_source(url) == OFFICIAL


@pytest.mark.parametrize(
    "url",
    [
        "https://www.madrid.es/portales/munimadrid/es/Inicio/El-Ayuntamiento/Padron",
        "https://sede.madrid.es/portal/site/tramites",
        "https://www.barcelona.cat/es/canals-window/padro-municipal",
        "http://barcelona.cat/",
    ],
)
def test_the_spanish_municipal_padron_offices_are_official(url):
    """The padrón is a core relocation step and the town hall is the body that runs it.

    Same call as `service.berlin.de` above: a municipality publishing its own registration
    procedure is the publisher of that procedure, not a portal restating someone else's rule.
    Left unlisted, `.es` and `.cat` carry no governmental suffix, so both town halls scored
    UNOFFICIAL and the padrón vanished from any ES-side deliverable.

    Named hosts only — Madrid and Barcelona. A third city is a decision, not a silent
    addition.
    """
    assert classify_source(url) == OFFICIAL


def test_admitting_the_spanish_bodies_did_not_admit_the_whole_es_tld():
    """The fix is named hostnames, not an `.es`/`.cat` suffix.

    `.es` is an open commercial TLD and `.cat` is a *linguistic* one — neither says anything
    about who published the page, which is the whole basis of the gate.
    """
    assert classify_source("https://madrid-relocation.es/guide") == UNOFFICIAL
    assert classify_source("https://www.spanish-immigration-lawyers.es/nie") == UNOFFICIAL
    assert classify_source("https://barcelona-relocation.cat/guide") == UNOFFICIAL
    # Nor a lookalike that merely ends with the string.
    assert classify_source("https://fake-madrid.es/padron") == UNOFFICIAL
    assert classify_source("https://notseg-social.es/afiliacion") == UNOFFICIAL
    assert classify_source("https://not-policia.es/nie") == UNOFFICIAL
    assert classify_source("https://notboe.es/diario") == UNOFFICIAL


def test_a_spanish_fact_reaches_the_staging_rows_instead_of_the_rejection_list(tmp_path):
    """End to end through `read_jsonl` — the gate has to admit the ROW, not just the URL."""
    path = _write(tmp_path, [_record(
        destination_country="ES",
        entity_topic_key="social_security_registration",
        fact_key="ssNumberWhereToApply",
        source_url="https://www.seg-social.es/wps/portal/wss/internet/Trabajadores",
    )])
    rows, rejections = read_jsonl(path, batch_id="es-1")

    assert rejections == []
    assert len(rows) == 1
    assert rows[0].source_class == OFFICIAL
    # Official publisher AND a quotable line of evidence, so this one clears the bar.
    assert rows[0].accuracy_tier == TIER_AUTO




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


# ── AIQ-2035: an absent applies_to.status is silent all the way to invisible ─────────

def _staged(tmp_path, records):
    """stage() a batch and return (result, the CLI text the operator would see)."""
    path = _write(tmp_path, records)
    rows, rejections = read_jsonl(path, batch_id="b-scope")
    result = stage(_NullConn(), rows, rejections=rejections, dry_run=True)
    ledger = reconcile(
        _NullConn(), result, source_label="x", expected_count=len(records), dry_run=True
    )
    return result, summarise(result, ledger)


def test_a_topic_with_no_applies_to_status_is_reported_before_anything_is_written(tmp_path):
    """The failure this guard exists for, and it is invisible at every other layer.

    `PURPOSES.get(status or "", "other")` turns an absent status into a real enum value, and
    `crud.list_requirements` filters purpose with strict equality and no catch-all. So the row
    promotes fine, approves fine, and is never returned to the dossier or the public corridor
    endpoint. Nothing errors and no count moves — which is why it has to be said out loud on
    the dry run, before a single row is staged.

    All nine VE->IE facts shipped without it (AIQ-2035). The converter sets it now, but Otto
    writes batches straight to the workspace with no converter in the path.
    """
    result, text = _staged(tmp_path, [_record()])          # _record carries no status
    assert len(result.unscoped) == 1
    assert "eu_free_movement_worker" in result.unscoped[0]
    assert "no fact carries applies_to.status" in result.unscoped[0]
    assert "purpose='other'" in result.unscoped[0]
    assert "NO usable applies_to.status" in text


def test_a_topic_that_declares_its_status_is_not_reported(tmp_path):
    """The control. Passes before this change and after — it tracks the rule, not the diff."""
    _, text = _staged(tmp_path, [_record(applies_to={"nationality": "EU",
                                                     "status": "professional"})])
    assert "NO usable applies_to.status" not in text


def test_an_explicit_any_is_a_decision_and_is_left_alone(tmp_path):
    """`other` is a legitimate purpose — FRANCE serves an approved row at it.

    So the guard must separate "nobody said" from "somebody chose 'any'". Flagging the second
    would train the reader to skip the block, which is exactly how the original omission
    survived. Also passes on both sides of the change.
    """
    _, text = _staged(tmp_path, [_record(applies_to={"nationality": "EU", "status": "any"})])
    assert "NO usable applies_to.status" not in text


def test_facts_that_disagree_on_status_are_reported_as_a_disagreement(tmp_path):
    """`_one_value()` returns None when a topic's facts conflict, which also lands 'other'.

    Absent and conflicting are different problems with different fixes, so the message has to
    say which — the same distinction `mappings.resolve()` draws for nationality after the B3
    batch blamed a conflict that did not exist.
    """
    result, _ = _staged(tmp_path, [
        _record(fact_key="a", applies_to={"nationality": "EU", "status": "professional"}),
        _record(fact_key="b", applies_to={"nationality": "EU", "status": "student"}),
    ])
    assert len(result.unscoped) == 1
    assert "disagree" in result.unscoped[0]


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


@pytest.mark.parametrize(
    "url",
    [
        # CLEISS is the French liaison body for international social security. It publishes the
        # coordination and totalisation rules for a move between France and another state —
        # the single most load-bearing source for an inbound EEA corridor — and it scored
        # UNOFFICIAL, so every fact citing it was thrown away before staging.
        "https://www.cleiss.fr/docs/regimes/regime_norvege.html",
        # The CAF is the family-benefits arm of the Sécurité sociale, publishing its own
        # entitlement conditions.
        "https://www.caf.fr/allocataires/caf-de-paris",
    ],
)
def test_the_french_social_security_bodies_are_official(url):
    """The fourth time this list was too narrow, and the tell was the same each time: the
    rejects clustered by country. A NO->FR batch researched from CLEISS would have lost its
    entire social-security half at import, silently, at exit 0."""
    assert classify_source(url) == OFFICIAL


@pytest.mark.parametrize(
    "url",
    [
        "https://www.dublincity.ie/residential/housing",
        "https://about.leapcard.ie/",
        "https://www.transportforireland.ie/fares/",
    ],
)
def test_the_irish_municipal_and_transport_publishers_are_official(url):
    """City-level settle-in content has no home otherwise: the council runs its own services
    and the NTA sets the fares it publishes, the same reasoning that admits rundfunkbeitrag.de.
    """
    assert classify_source(url) == OFFICIAL


def test_admitting_those_did_not_admit_the_whole_fr_or_ie_tld():
    """The opposite error to the one above, and the one that would let a relocation vendor
    publish a legal requirement."""
    assert classify_source("https://www.expat-in-paris.fr/social-security") == UNOFFICIAL
    assert classify_source("https://notcleiss.fr/regimes") == UNOFFICIAL
    assert classify_source("https://www.dublin-movers.ie/leap-card-guide") == UNOFFICIAL
    assert classify_source("https://not-dublincity.ie/housing") == UNOFFICIAL


@pytest.mark.parametrize(
    "url",
    [
        # Germany (Tier-1): ELSTER tax-filing portal + Zoll customs, neither under bund.de.
        "https://www.elster.de/eportal/infoseite/registrierung",
        "https://www.zoll.de/EN/Private-individuals/Moving-and-inheritance/moving-and-inheritance_node.html",
        # Netherlands (Tier-1): the core authorities, none under overheid.nl.
        "https://ind.nl/en/residence-permits",
        "https://www.belastingdienst.nl/wps/wcm/connect/en/individuals/individuals",
        "https://www.svb.nl/en/aow-pension",
        "https://www.uwv.nl/particulieren/",
        "https://www.rijksoverheid.nl/onderwerpen/immigratie",
        "https://www.government.nl/topics/immigration",
        # United Kingdom (Tier-1): NHS health entitlement + devolved Scottish/Welsh governments.
        "https://www.nhs.uk/nhs-services/gps/how-to-register-with-a-gp-surgery/",
        "https://www.mygov.scot/register-gp",
        "https://www.gov.scot/publications/",
        "https://www.gov.wales/get-help-nhs-costs",
        "https://www.llyw.cymru/cael-help-gyda-chostau-r-gig",
    ],
)
def test_tier1_gb_de_nl_authorities_are_official(url):
    """Tier-1 destinations GB/DE/NL: the statutory bodies a mover actually deals with.

    NL is the starkest case — only `overheid.nl` was recognised, so the IND, Belastingdienst,
    SVB and UWV all scored UNOFFICIAL and `stage()` rejects rather than downgrades, losing the
    residence/tax/social-security topics outright. GB adds the NHS (health, like `hse.ie`) and
    the devolved Scottish/Welsh governments; DE adds ELSTER and Zoll. Same too-narrow-allowlist
    failure the country clusters above record.
    """
    assert classify_source(url) == OFFICIAL


def test_admitting_the_tier1_authorities_did_not_admit_their_tlds_or_lookalikes():
    """Named hosts / devolved suffixes, not a blanket `.nl` / `.uk` / `.scot` / `.wales` admission."""
    # A Dutch relocation blog stays out despite the new ind.nl / belastingdienst.nl hosts.
    assert classify_source("https://www.expat-in-amsterdam.nl/bsn-guide") == UNOFFICIAL
    assert classify_source("https://notind.nl/residence") == UNOFFICIAL
    assert classify_source("https://belastingdienst-help.nl/bsn") == UNOFFICIAL
    # An NHS lookalike, and generic `.scot` / `.wales` sites, are not the government.
    assert classify_source("https://www.nhs-advice.uk/register") == UNOFFICIAL
    assert classify_source("https://relocate.scot/schools") == UNOFFICIAL
    assert classify_source("https://movetocardiff.wales/renting") == UNOFFICIAL
