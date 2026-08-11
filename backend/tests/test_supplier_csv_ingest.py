"""[AIQ-1788] The harvest CSV reader, and the two rules that let real data through.

`vendor_harvester` shipped with no reader and no caller, so its assumptions had never met a
real file. When they did, all 38 rows of the Card C harvest failed. This pins the three
changes that followed, and the one bug the exercise exposed.

The real file is used as a fixture on purpose: a synthetic CSV would have agreed with whatever
the code already believed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.services.registry_sources import effective_tier
from backend.app.services.vendor_harvester import Candidate, HarvestRejected, validate
from backend.imports.suppliers.parsers import (
    RowError,
    SELF_DECLARED,
    coerce_expiry,
    read_csv,
    source_for_url,
)

REPO = Path(__file__).resolve().parents[2]
HARVEST = REPO / "audos-workspace-776786" / "data" / "card-c-harvest.csv"


# ── expiry coercion ──────────────────────────────────────────────────────────────────

def test_bare_year_becomes_the_FIRST_of_january_not_the_last_of_december():
    """The whole point. December would claim up to twelve months of accreditation nobody
    verified, on the field a procurement review re-checks. January under-claims instead."""
    assert coerce_expiry("2028") == "2028-01-01"


def test_iso_date_passes_through():
    assert coerce_expiry("2027-06-30") == "2027-06-30"


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_blank_expiry_is_none_not_a_guess(blank):
    assert coerce_expiry(blank) is None


@pytest.mark.parametrize("junk", ["soon", "2028-13-01x", "06/2028"])
def test_unparseable_expiry_raises_rather_than_guessing(junk):
    with pytest.raises(RowError, match="refusing to guess"):
        coerce_expiry(junk)


# ── source identification ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.fidi.org/find-fidi-affiliate/ags-france", "FIDI FAIM member directory"),
        ("https://kontenvergleich.bafin.de/en/account/678272c6", "BaFin institute register (DE)"),
        ("https://www.finanstilsynet.no/en/finanstilsynets-registry/details/?id=104451",
         "Finanstilsynet — estate agency register (NO)"),
        ("https://virksomhet.brreg.no/nb/oppslag/enheter/917334110",
         "Advokatforeningen + Brønnøysund register (NO)"),
    ],
)
def test_registry_is_identified_by_domain(url, expected):
    assert source_for_url(url).name == expected


@pytest.mark.parametrize("url", [
    "https://www.ey.com/de_de/legal-and-privacy/impressum",
    "https://www.wikidata.org/wiki/Q27479372",
    "https://se-legal.de/impressum/",
    "",
])
def test_a_non_registry_url_is_self_declared_not_a_guess(url):
    assert source_for_url(url).name == SELF_DECLARED


def test_domain_wins_over_the_free_text_source_name():
    """`source_name` is prose an agent wrote, and a row citing the provider's own Impressum can
    describe itself using a chamber's name — one in this very file does ("Firm Impressum (RAK
    Berlin stated)"). The publishing domain cannot lie about who published it."""
    assert source_for_url("https://db.com/legal-resources").name == SELF_DECLARED


# ── the real file ────────────────────────────────────────────────────────────────────

def test_reads_all_38_rows():
    assert len(list(read_csv(HARVEST))) == 38


def test_every_row_used_to_be_rejected_and_now_29_pass():
    """Before the dedupe fallback, `website_url` was empty on all 38 rows so every one failed
    on 'no domain'. Now the only rejects are the nine whose evidence is not a registry record.

    Was SEVEN until 2026-08-12, and both additions were holes in the check rather than changes
    to the rule:

    - BLKR — `blkr-berlin.de`, the firm's OWN website, was in the domain allowlist mapped to
      the Rechtsanwaltskammer, so the row passed as tier-1 evidence on its own homepage.
    - Advokatfirmaet Sulland — cited Advokatforeningen's generic `/search-for-members/` page.
      Right domain, evidences nobody. Caught by `entry_url_pattern`.

    Together they are the reason the tier check now asks two questions instead of one: who
    published the page, AND is the page about this company.
    """
    accepted, rejected = [], []
    for cand in read_csv(HARVEST):
        try:
            validate(cand)
            accepted.append(cand)
        except HarvestRejected:
            rejected.append(cand)

    assert len(accepted) == 29
    assert {c.name for c in rejected} == {
        "Advokatfirmaet Sulland AS",
        "Schlun & Elseven Rechtsanwälte PartG mbB",
        "Matzenbach & Sternberg Partnerschaft mbB Steuerberatungsgesellschaft (MSP Beratung)",
        "EY Tax GmbH Steuerberatungsgesellschaft",
        "Kanzlei Thalmeir — Julian Thalmeir",
        "Deutsche Bank AG",
        "Commerzbank AG",
        "N26 Bank SE",
        "BLKR Rechtsanwältinnen",
    }, "the reject list IS the re-sourcing worklist — it must match the PROVENANCE doc"


def test_a_law_firms_own_domain_is_not_a_registry():
    """Regression guard for the allowlist bug removed 2026-08-12.

    `blkr-berlin.de` sat in `_DOMAIN_TO_SOURCE` mapped to the Rechtsanwaltskammer. Verified by
    fetching it: BLKR Rechtsanwält*innen is an independent Berlin law firm, not a chamber. A
    provider domain in the allowlist silently converts 'the supplier says so' into 'a registry
    says so', which is the one thing the sourcing rule exists to prevent.
    """
    assert source_for_url("https://www.blkr-berlin.de/english/").name == SELF_DECLARED


def _bank(url: str):
    """A synthetic bank candidate carrying `url` as its only evidence."""
    return Candidate(
        name="Some Bank AG",
        website_url="https://example.de/",
        corridor="FR-DE",
        service_category="banks",
        source=source_for_url(url),
        source_url=url,
        accreditation_body="BaFin",
        accreditation_number="",
        accreditation_expiry="",
    )


def test_a_registry_search_page_is_not_evidence_for_a_bank():
    """The hole `entry_url_pattern` closes, stated as the case that motivated it.

    `portal.mvp.bafin.de/database/InstInfo/` is BaFin's search FORM. It is on a tier-1 domain,
    so before 2026-08-12 pasting it into all three bank rows would have made them pass while
    proving nothing about any of them. The domain says who published the page; it cannot say
    the page is about this company.
    """
    with pytest.raises(HarvestRejected, match="not an entry for one entity"):
        validate(_bank("https://portal.mvp.bafin.de/database/InstInfo/"))


def test_a_bafin_per_institution_page_IS_evidence():
    """The other half — the guard must not reject the real thing.

    Shape verified 2026-08-12: this URL returns HTTP 200 with no login and lists the
    institution's authorisations and their dates.
    """
    url = (
        "https://portal.mvp.bafin.de/database/InstInfo/institutDetails.do"
        "?cmd=loadInstitutAction&institutId=118938"
    )
    validate(_bank(url))  # must not raise


def test_the_association_search_page_that_slipped_through():
    """Advokatfirmaet Sulland's real evidence URL, kept as the concrete regression case."""
    cand = Candidate(
        name="Advokatfirmaet Sulland AS",
        website_url="https://sulland.no/",
        corridor="FR-NO",
        service_category="legal_admin",
        source=source_for_url(
            "https://www.advokatforeningen.no/en/about-advokatforeningen/search-for-members/"
        ),
        source_url="https://www.advokatforeningen.no/en/about-advokatforeningen/search-for-members/",
        accreditation_body="Advokatforeningen",
        accreditation_number="",
        accreditation_expiry="",
    )
    with pytest.raises(HarvestRejected, match="not an entry for one entity"):
        validate(cand)


def test_rows_carry_a_note_explaining_every_inference():
    """A reviewer must be able to tell a read value from a derived one."""
    by_name = {c.name: c for c in read_csv(HARVEST)}
    ags = by_name["AGS France (SOFDI – Société Française de Déménagement International)"]
    assert "expiry coerced from bare year 2028" in ags.notes
    assert "deduped by name+corridor" in ags.notes


def test_no_row_silently_loses_its_evidence_url():
    assert all(c.source_url for c in read_csv(HARVEST))


def test_header_drift_is_a_hard_error():
    """A reordered or renamed column would otherwise map values into the wrong fields."""
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
        fh.write("corridor,company_name\nFR-DE,Acme\n")
        path = Path(fh.name)
    with pytest.raises(RowError, match="unexpected header"):
        list(read_csv(path))


# ── the bug this exercise exposed ────────────────────────────────────────────────────

def test_banks_tier_is_capped_not_forced():
    """`return 2 if category == "banks"` was written to DOWNGRADE a tier-1 bank register. It
    also upgraded tier 3 to 2, so three bank rows evidenced only by the bank's own site — one
    of them a Wikidata entry — passed validation while every other self-declared row in the
    same file was correctly rejected."""
    assert effective_tier("banks", 1) == 2, "a BaFin listing still stages as entity-confirmation"
    assert effective_tier("banks", 2) == 2
    assert effective_tier("banks", 3) == 3, "tier 3 must stay tier 3 and be rejected"
    assert effective_tier("movers", 3) == 3


def test_the_three_self_declared_banks_are_rejected():
    rejected = set()
    for cand in read_csv(HARVEST):
        try:
            validate(cand)
        except HarvestRejected:
            rejected.add(cand.name)
    assert {"Deutsche Bank AG", "Commerzbank AG", "N26 Bank SE"} <= rejected
