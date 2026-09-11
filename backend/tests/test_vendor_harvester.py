"""[AIQ-1788] Tests for the accreditation-registry harvester.

No network, no database. The harvester's decision surface (validate / classify /
plan_pair) is deliberately pure so the rules that matter — what gets staged, what is
suppressed, what is refused and why — can be asserted directly rather than inferred from
rows that appeared in a table somewhere.

The dedupe cases use the real shapes found in prod `suppliers.website` on 2026-08-10,
including bare hosts and hosts carrying a path, because those are exactly the inputs a
naive urlsplit gets wrong.
"""
from __future__ import annotations

import pytest

from backend.app.services.registry_sources import (
    Acquisition,
    RegistrySource,
    confidence_for,
    effective_tier,
    ingestable_sources,
    pairs_in_scope,
    sources_for,
    unavailable_reasons,
)
from backend.app.services.vendor_harvester import (
    Candidate,
    HarvestRejected,
    STATUS_DUPLICATE,
    STATUS_PENDING,
    classify,
    normalise_domain,
    plan_pair,
    render_report,
    to_insert_params,
    validate,
)

TIER1 = RegistrySource(
    name="FIDI FAIM member directory",
    base_url="https://www.fidi.org/find-mover",
    tier=1,
    acquisition=Acquisition.MANUAL_EVIDENCED,
    corridors=("FR-DE", "FR-NO"),
    categories=("movers",),
    entry_url_pattern=r"/find-fidi-affiliate/[^/]",
)


def make(**kw) -> Candidate:
    base = dict(
        name="Acme Movers GmbH",
        website_url="https://www.acme-movers.de/",
        corridor="FR-DE",
        service_category="movers",
        source=TIER1,
        # A real per-affiliate entry, not the /find-mover search page — TIER1 declares an
        # entry_url_pattern, and the search page is exactly what it exists to reject.
        source_url="https://www.fidi.org/find-fidi-affiliate/acme",
        accreditation_body="FIDI FAIM",
        accreditation_number="FAIM-12345",
        accreditation_expiry="2027-06-30",
    )
    base.update(kw)
    return Candidate(**base)


# ── domain normalisation — the dedupe primitive ──────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://www.example.com", "example.com"),
        ("http://example.com/", "example.com"),
        ("HTTPS://WWW.Example.COM/a/b?q=1#f", "example.com"),
        ("example.com", "example.com"),                     # bare host, no scheme
        ("www.example.com", "example.com"),
        ("sub.example.com", "example.com"),
        ("deep.sub.example.com", "example.com"),
        ("example.co.uk", "example.co.uk"),                 # compound suffix kept whole
        ("www.sub.example.co.uk", "example.co.uk"),
        # Corridor ccTLDs must NOT collapse to the bare suffix (the .com.au regression):
        ("https://www.widen.com.au", "widen.com.au"),
        ("dmamigration.com.au", "dmamigration.com.au"),
        ("foo.net.au", "foo.net.au"),
        ("sub.example.co.nz", "example.co.nz"),
        ("firm.com.sg/office", "firm.com.sg"),
        ("bureau.co.za", "bureau.co.za"),
        # .adv.br = the Brazilian LAWYER second-level (BR/legal regression, 2026-09-11):
        ("https://droliveira.adv.br", "droliveira.adv.br"),
        ("mcbs.adv.br", "mcbs.adv.br"),
        ("https://example.com:8443/x", "example.com"),      # port stripped
        # The shapes that actually live in prod suppliers.website:
        ("agsmovers.com/branches/movers-europe/norway/norway/", "agsmovers.com"),
        ("crownrelo.com/norway/en-no", "crownrelo.com"),
        ("bdo.no/en-gb/services/tax-and-legal/international-tax-consultancy", "bdo.no"),
        ("dnb.no/en/", "dnb.no"),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_normalise_domain(raw, expected):
    assert normalise_domain(raw) == expected


def test_normalise_domain_is_case_and_slash_insensitive():
    """The same company written four ways must collapse to one key, or dedupe is theatre."""
    variants = [
        "https://www.Acme-Movers.de/",
        "http://acme-movers.de",
        "ACME-MOVERS.DE/contact",
        "www.acme-movers.de",
    ]
    assert len({normalise_domain(v) for v in variants}) == 1


def test_normalise_domain_distinct_firms_on_same_cctld_do_not_collide():
    """Different firms on the same multi-part ccTLD must key distinctly — the false-dedup
    regression that collapsed every *.com.au to `com.au` and dropped a whole AU harvest."""
    firms = [
        "https://www.widen.com.au",
        "https://www.dmamigration.com.au",
        "https://baymigration.com.au",
        "https://www.kanmigration.com.au",
    ]
    keys = {normalise_domain(f) for f in firms}
    assert len(keys) == 4                       # four firms, four keys
    assert "com.au" not in keys                 # never the bare public suffix


def test_normalise_domain_distinct_firms_on_same_adv_br_do_not_collide():
    """Brazilian law firms live on `.adv.br`; two distinct firms there must key distinctly.
    The São Paulo BR/legal batch (droliveira.adv.br + mcbs.adv.br) would otherwise collapse to
    the bare `adv.br` and drop one — the same class as the .com.au regression."""
    firms = ["https://droliveira.adv.br", "https://mcbs.adv.br"]
    keys = {normalise_domain(f) for f in firms}
    assert keys == {"droliveira.adv.br", "mcbs.adv.br"}
    assert "adv.br" not in keys


# ── validation — the rules that keep bad rows out ────────────────────────────

def test_rejects_candidate_with_no_source_url():
    with pytest.raises(HarvestRejected, match="source_url is required"):
        validate(make(source_url=None))


def test_rejects_tier_3_only_evidence():
    own_site = RegistrySource(
        name="provider website", base_url="https://x.de", tier=3,
        acquisition=Acquisition.HTTP_LISTING, corridors=("FR-DE",), categories=("movers",),
    )
    with pytest.raises(HarvestRejected, match="tier 3"):
        validate(make(source=own_site))


def test_rejects_candidate_from_an_unavailable_source():
    """A blocked registry is a finding. Routing around it is what the brief forbids."""
    blocked = RegistrySource(
        name="IVD", base_url="https://ivd.net/", tier=1,
        acquisition=Acquisition.UNAVAILABLE, corridors=("FR-DE",),
        categories=("housing_agencies",), unavailable_reason="login-gated",
    )
    with pytest.raises(HarvestRejected, match="UNAVAILABLE"):
        validate(make(source=blocked, service_category="housing_agencies"))


def test_rejects_named_individual_email_gdpr():
    with pytest.raises(HarvestRejected, match="named individual"):
        validate(make(email="anna.schmidt@acme-movers.de"))


@pytest.mark.parametrize("addr", [
    "info@acme.de", "kontakt@acme.de", "post@acme.no",
    # Widened 2026-08-30 for the moving/relocation trade, which lives on these role inboxes.
    # A Madrid->Dublin batch published sales@/enquiries@/hq@ and the old list rejected them.
    "sales@johnmason.com", "enquiries@bishopsmove.com", "hq@whiteandcompany.co.uk",
    "ventas@mudanzas.es", "comercial@mudanzas.es", "contacto@mudanzas.es",
    "removals@abels.co.uk", "bookings@mover.ie", "support@mover.ie",
])
def test_accepts_company_level_email(addr):
    validate(make(email=addr))  # must not raise


@pytest.mark.parametrize("addr", [
    "anna.schmidt@acme-movers.de", "john@acme.de", "maria.garcia@mudanzas.es",
])
def test_still_rejects_named_individual_email(addr):
    # The widening added role inboxes only — first-name addresses stay rejected (GDPR).
    with pytest.raises(HarvestRejected):
        validate(make(email=addr))


def test_no_website_falls_back_to_a_name_key_instead_of_rejecting():
    """Changed deliberately for the first real harvest — see Candidate.dedupe_key.

    This used to reject. Every one of Card C's 38 registry-sourced rows arrived with an empty
    `website_url` (the evidence URL points at the *register*, not the company), so the
    domain-only rule rejected the entire file. A name key is weaker than a domain and is
    namespaced so the two can never collide.
    """
    cand = make(website_url="   ", name="Hasenkamp Relocation Services GmbH", corridor="FR-DE")
    validate(cand)                                     # must not raise
    assert cand.dedupe_key == "name:hasenkamprelocationservices@fr-de"


def test_rejects_only_when_there_is_neither_domain_nor_usable_name():
    with pytest.raises(HarvestRejected, match="no dedupe key"):
        validate(make(website_url="", name="—"))


def test_name_key_ignores_legal_form_and_accents():
    """'Deloitte AS' and 'Deloitte' are the same company; 'Déménagement' and
    'Demenagement' are the same word. Both would otherwise stage twice."""
    a = make(website_url="", name="Deloitte AS", corridor="FR-NO")
    b = make(website_url="", name="Deloitte", corridor="FR-NO")
    assert a.dedupe_key == b.dedupe_key

    accented = make(website_url="", name="Société Française de Déménagement", corridor="FR-DE")
    plain = make(website_url="", name="Societe Francaise de Demenagement", corridor="FR-DE")
    assert accented.dedupe_key == plain.dedupe_key


def test_name_key_is_corridor_scoped_and_cannot_collide_with_a_domain():
    de = make(website_url="", name="AGS France", corridor="FR-DE")
    no = make(website_url="", name="AGS France", corridor="FR-NO")
    assert de.dedupe_key != no.dedupe_key
    assert de.dedupe_key.startswith("name:")
    assert make(website_url="https://ags-france.com").dedupe_key == "ags-france.com"


# ── dedupe ───────────────────────────────────────────────────────────────────

def test_dedupe_against_a_seeded_supplier_domain():
    """A domain already in the live directory stages as 'duplicate', not 'pending'."""
    known = {"acme-movers.de"}
    assert classify(make(), known) == STATUS_DUPLICATE
    assert classify(make(website_url="https://other.de"), known) == STATUS_PENDING


def test_dedupe_matches_across_url_shapes():
    """The supplier row has a path; the candidate has www + scheme. Same company."""
    known = {normalise_domain("agsmovers.com/branches/movers-europe/norway/norway/")}
    assert classify(make(website_url="https://www.agsmovers.com/"), known) == STATUS_DUPLICATE


def test_duplicates_are_inserted_not_dropped():
    """Suppressed rows must remain visible, or the run report cannot explain the shortfall."""
    rows, result, rejections = plan_pair(
        "FR-DE", "movers",
        [make(), make(name="Other", website_url="https://other.de")],
        known_keys={"acme-movers.de"},
    )
    assert not rejections
    assert len(rows) == 2, "the duplicate must still be written"
    assert result.staged == 1
    assert result.suppressed_duplicates == 1
    assert {r["status"] for r in rows} == {STATUS_PENDING, STATUS_DUPLICATE}


def test_two_candidates_sharing_a_domain_in_one_run_dedupe_against_each_other():
    rows, result, _ = plan_pair(
        "FR-DE", "movers",
        [make(), make(name="Acme Movers (Berlin office)")],
        known_keys=set(),
    )
    assert result.staged == 1
    assert result.suppressed_duplicates == 1


# ── idempotency ──────────────────────────────────────────────────────────────

def test_rerun_of_a_processed_pair_stages_zero_new_rows():
    """Validation Criterion 7, asserted directly.

    The second run sees the first run's dedupe_keys, so every row comes back as a
    duplicate and `staged` is 0.
    """
    cands = [make(), make(name="Bravo", website_url="https://bravo.de")]
    _, first, _ = plan_pair("FR-DE", "movers", cands, known_keys=set())
    assert first.staged == 2

    after_first = {c.dedupe_key for c in cands}
    _, second, _ = plan_pair("FR-DE", "movers", cands, known_keys=after_first)
    assert second.staged == 0, "a re-run must add no new pending rows"
    assert second.suppressed_duplicates == 2


# ── constraint-shaped output ─────────────────────────────────────────────────

def test_insert_params_respect_db_check_constraints():
    p = to_insert_params(make(), run_id="r1", status=STATUS_PENDING)
    assert p["source_tier"] in (1, 2, 3)
    assert 0 <= float(p["confidence_score"]) <= 1
    assert p["status"] in (
        "pending", "approved", "rejected", "duplicate", "needs_reverification",
    )
    assert p["corridor"] in ("FR-DE", "FR-NO")
    assert p["dedupe_key"] == "acme-movers.de"


def test_confidence_never_reaches_one():
    """1.0 is reserved for human verification — a harvest proves membership, not fitness."""
    best = confidence_for(1, True, True, "movers")
    assert best == 0.9
    assert best < 1.0


def test_banks_are_capped_and_downgraded_to_tier_2():
    """Banks are licensed, not accredited: the register confirms the entity and no more."""
    assert confidence_for(1, True, True, "banks") == 0.5
    assert effective_tier("banks", 1) == 2
    p = to_insert_params(
        make(service_category="banks", corridor="FR-NO"), run_id="r", status=STATUS_PENDING
    )
    assert p["source_tier"] == 2
    assert float(p["confidence_score"]) == 0.5


def test_missing_expiry_lowers_confidence():
    assert confidence_for(1, True, False, "movers") == 0.7
    assert confidence_for(1, True, True, "movers") == 0.9


# ── source catalogue policy ──────────────────────────────────────────────────

def test_pairs_in_scope_is_corridors_x_categories():
    # 6 corridors (FR-DE, FR-NO, ES-IE, NO-FR, FR-SG, US-EC) x 6 categories (movers,
    # housing_agencies, legal_admin, tax_finance, banks, schools). ES-IE/NO-FR + schools were
    # added 2026-08-30 for the Dublin/Paris batches; FR-SG/US-EC for the Singapore/Quito batches.
    # Not every pair has a source yet, which is what unavailable_reasons() and empty
    # ingestable_sources() are for.
    from backend.app.services.registry_sources import CORRIDORS, CATEGORIES
    # + XX-ZA (Johannesburg Tier-3 wave-5) added 2026-08-31 → 50 corridors.
    # + XX-TW/VN/ID/PH (wave-9 Asia-Pacific tail) 2026-08-31 → 54 corridors.
    # + XX-CO/PE/UY/CR/PA (wave-10 LatAm cluster) 2026-09-02 → 59 corridors.
    # + XX-HR/SI/SK/LT/LV (wave-11 EU cluster) 2026-09-02 → 64 corridors.
    assert len(pairs_in_scope()) == len(CORRIDORS) * len(CATEGORIES) == 384


def test_unavailable_sources_are_declared_not_hidden():
    """FR-DE housing_agencies is the pair recon proved unharvestable. It must say so."""
    reasons = unavailable_reasons("FR-DE", "housing_agencies")
    assert reasons, "the blocked registries for this pair must be recorded"
    assert any("login" in r.lower() for r in reasons.values())
    assert ingestable_sources("FR-DE", "housing_agencies") == [], (
        "no ingestable source for this pair — staging anything here would mean "
        "substituting a weaker source, which the brief forbids"
    )
    assert sources_for("FR-DE", "housing_agencies"), "but the sources are still listed"


def test_public_register_is_admitted_only_at_tier_2():
    """A permalink-less statutory register (Option C, 2026-08-30) is the one source allowed to
    skip entry_url_pattern — but only at tier 2, so its rows stage 'claimed' at reduced
    confidence for the vetting-queue human to confirm."""
    from backend.app.services.registry_sources import Acquisition, RegistrySource
    with pytest.raises(ValueError, match="tier 2"):
        RegistrySource(name="bad", base_url="https://x.ie/", tier=1,
                       acquisition=Acquisition.PUBLIC_REGISTER,
                       corridors=("ES-IE",), categories=("banks",))
    ok = RegistrySource(name="ok", base_url="https://x.ie/", tier=2,
                        acquisition=Acquisition.PUBLIC_REGISTER,
                        corridors=("ES-IE",), categories=("banks",))
    assert ok.entry_url_pattern is None  # the whole point: no per-entity URL, yet ingestable


def test_unavailable_source_must_state_a_reason():
    with pytest.raises(ValueError, match="must state a reason"):
        RegistrySource(
            name="x", base_url="https://x", tier=1,
            acquisition=Acquisition.UNAVAILABLE,
            corridors=("FR-DE",), categories=("movers",),
        )


def test_source_rejects_unknown_corridor_or_category():
    with pytest.raises(ValueError, match="unknown corridor"):
        RegistrySource(
            name="x", base_url="https://x", tier=1,
            acquisition=Acquisition.HTTP_LISTING,
            corridors=("FR-XX",), categories=("movers",),
        )
    with pytest.raises(ValueError, match="unknown category"):
        RegistrySource(
            name="x", base_url="https://x", tier=1,
            acquisition=Acquisition.HTTP_LISTING,
            corridors=("FR-DE",), categories=("nope",),
        )


# ── run report ───────────────────────────────────────────────────────────────

def test_report_names_every_empty_pair_and_why():
    """Criterion 9: a report that omits the zeros turns a blocked registry into a mystery."""
    _, empty, _ = plan_pair("FR-DE", "housing_agencies", [], known_keys=set())
    _, full, _ = plan_pair("FR-DE", "movers", [make()], known_keys=set())

    md = render_report([empty, full])
    assert "Pairs still at zero" in md
    assert "FR-DE / housing_agencies" in md
    assert "login-gated" in md
    assert "current_verified_count" in md, "the report must state what it did NOT touch"


# ── Registry-gap wiring 2026-09-09 ───────────────────────────────────────────
# The 15 (corridor, category) pairs the vendor re-sourcing brief flagged as having no wired
# register. Each register was identified and probed live, then wired. These pins prove that,
# for every pair: it is now ingestable, its evidence domain maps OFF SELF_DECLARED at an
# ingestable tier, a candidate citing the record/register page passes validate(), and — where
# the register exposes per-entity pages — the search/listing root is still REJECTED (the gate
# must keep discriminating a record page from a search form).
from backend.imports.suppliers.parsers import SELF_DECLARED, source_for_url  # noqa: E402

_WIRED_GAP_PAIRS = [
    ("FR-NO", "schools",
     "https://nsr.udir.no/enheter/971845635", "https://nsr.udir.no/enheter"),
    ("FR-DE", "schools",
     "https://www.bildung.berlin.de/Schulverzeichnis/Schulportrait.aspx?IDSchulzweig=31353",
     "https://www.bildung.berlin.de/Schulverzeichnis/SchulListe.aspx"),
    ("FR-DE", "schools",
     "https://schul-db.bildung.hessen.de/schul_db.html/details/?school_no=6055",
     "https://schul-db.bildung.hessen.de/schul_db.html"),
    ("XX-ES", "housing_agencies",
     "https://www.comunidad.madrid/vivienda/registro-agentes-inmobiliarios-rain", None),
    ("XX-ES", "legal_admin",
     "https://censo.abogacia.es/ecensofront/html/homeColegiados.iface", None),
    ("XX-ES", "tax_finance", "https://www.icac.gob.es/buscador-roac", None),
    ("XX-ES", "banks", "https://app.bde.es/rbe_spa/", None),
    ("XX-SE", "housing_agencies", "https://fmi.se/soktjanster/sok-maklare/", None),
    ("XX-SE", "legal_admin",
     "https://www.advokatsamfundet.se/Sok-advokat/Sokresultat/Kontorsdetaljer/?companyid=5615",
     "https://www.advokatsamfundet.se/Sok-advokat/Sokresultat/?City=Stockholm"),
    ("XX-SE", "tax_finance",
     "https://www.revisorsinspektionen.se/link/0df3cdc13e0f4fa38dbf58e7f163ed4f.aspx",
     "https://www.revisorsinspektionen.se/revisorssok/sokrevisor/"),
    ("XX-SE", "banks",
     "https://www.fi.se/en/our-registers/company-register/details?id=1826",
     "https://www.fi.se/en/our-registers/company-register/"),
    ("XX-FI", "housing_agencies", "https://vasa.lvv.fi", None),
    ("XX-IT", "housing_agencies", "https://www.registroimprese.it/", None),
    ("XX-IT", "legal_admin", "https://www.consiglionazionaleforense.it/ricerca-avvocati", None),
    ("XX-IT", "tax_finance", "https://commercialisti.it/albo-nazionale/ricerca-iscritti/", None),
    ("XX-IT", "banks", "https://infostat.bancaditalia.it/GIAVAInquiry-public/ng/banche", None),
]


@pytest.mark.parametrize("corridor,category,entry_url,search_root", _WIRED_GAP_PAIRS)
def test_registry_gap_pair_now_ingestable_and_maps(corridor, category, entry_url, search_root):
    assert ingestable_sources(corridor, category), f"{corridor}/{category} still has no register"
    src = source_for_url(entry_url)
    assert src.name != SELF_DECLARED, f"{entry_url} did not map to a wired register"
    assert effective_tier(category, src.tier) in (1, 2)
    # a candidate citing the record/register page passes validation
    validate(make(corridor=corridor, service_category=category, source=src, source_url=entry_url,
                  website_url="https://vendor.example/", accreditation_body="",
                  accreditation_number="", accreditation_expiry=""))


@pytest.mark.parametrize(
    "corridor,category,entry_url,search_root",
    [w for w in _WIRED_GAP_PAIRS if w[3] is not None],
)
def test_registry_gap_pattern_rejects_search_root(corridor, category, entry_url, search_root):
    """Where the register exposes per-entity pages, its search/listing root evidences nobody."""
    src = source_for_url(entry_url)
    assert src.entry_url_pattern, f"{src.name} should declare an entry_url_pattern"
    with pytest.raises(HarvestRejected):
        validate(make(corridor=corridor, service_category=category, source=src,
                      source_url=search_root, website_url="https://vendor.example/",
                      accreditation_body="", accreditation_number="", accreditation_expiry=""))
