"""
[AIQ-1788] Declarative catalogue of accreditation registries, per corridor x category.

WHY A CATALOGUE AND NOT SCRAPERS
--------------------------------
The task brief assumed every registry here is scrapable and specified per-source HTML
parsers. A reconnaissance pass over these exact registries on 2026-08-10 found that is
only partly true: the German IVD directory is login-gated, FNAIM has no public search,
and BRAV was unreachable. That is not a parser bug to work around — the brief's own rule
is "if a registry has no usable public listing, record that in the run report rather than
silently substituting a weaker source."

So each source declares HOW it can be acquired (`Acquisition`), and an unusable one is a
first-class recorded fact rather than an empty result somebody has to re-investigate. The
knowledge that IVD is login-gated cost a research pass to obtain; losing it would mean
paying for it again.

WHY TIERING MATTERS MORE THAN COVERAGE
--------------------------------------
The moat is provenance. An HR buyer's security review asks where supplier data came from,
and "FIDI FAIM registry, entry #1234, verified 2026-08-xx, evidence URL attached" is an
answer a scraped listing cannot give. Hence `tier`:

  1 — accreditation registry or public/government register (FIDI FAIM, BaFin,
      Finanstilsynet, a national bar, a chamber of commerce)
  2 — recognised industry association member list
  3 — the provider's own website

Tier 3 is never sufficient on its own. `ingestable_sources()` enforces that rather than
leaving it to each caller to remember.

FORBIDDEN, and not negotiable: Google Maps scraping (breaches Google's ToS, which surfaces
in exactly the enterprise security review this data exists to satisfy) and consumer review
aggregators as a primary source.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

# Corridors in scope. The original FR-DE / FR-NO pair was the AIQ-1788 harvest; ES-IE (Andrea,
# Madrid→Dublin) and NO-FR (Denis, Norway→Paris) were added 2026-08-30 as the Otto provider
# batches for the two demo corridors came in. Note `validate()` does NOT gate on corridor — this
# tuple only bounds which (corridor, category) pairs the run report and source metadata cover, so
# adding a corridor never loosens validation; it just lets a source declare it honestly.
# `XX-GB` is a DESTINATION-COVERAGE pseudo-corridor: the UK is authored as a destination
# (coverage-master rank 3), not a persona origin→dest pair, so the origin token is the `XX`
# wildcard and only the destination (`GB`) is meaningful. `_dest_iso_from_corridor` reads the
# second token, so a candidate row `corridor="XX-GB"` scopes to country_code `GB`. Same shape
# will follow for the next coverage-master destinations (XX-CA, XX-AU, …).
CORRIDORS: Tuple[str, ...] = ("FR-DE", "FR-NO", "ES-IE", "NO-FR", "FR-SG", "US-EC", "XX-GB", "XX-CA", "XX-AU", "XX-ES", "XX-NL", "XX-AE", "XX-CH", "XX-IT", "XX-SE", "XX-BE", "XX-AT", "XX-DK", "XX-SA", "XX-FI", "XX-PT", "XX-JP", "XX-HK", "XX-PL", "XX-NZ", "XX-QA", "XX-KW", "XX-KR", "XX-IL", "XX-LU", "XX-CZ", "XX-GR", "XX-MX", "XX-BR")

# Categories with live suppliers. `schools` joined the original five on 2026-08-30 (the Dublin/
# Paris batches source it from Tusla / annuaire-education). rmc / dsp / healthcare_ipmi /
# language_cultural stay OUT of scope: zero suppliers and weaker public registries — their own
# task, not a weaker source here.
CATEGORIES: Tuple[str, ...] = (
    "movers",
    "housing_agencies",
    "legal_admin",
    "tax_finance",
    "banks",
    "schools",
)


class Acquisition(str, Enum):
    """How a source's listing can actually be obtained."""

    #: A public listing that can be fetched and parsed programmatically.
    HTTP_LISTING = "http_listing"
    #: A public registry that answers per-entity lookups but has no listable index.
    #: Usable to VERIFY a candidate found elsewhere; not to enumerate candidates.
    HTTP_LOOKUP = "http_lookup"
    #: Publicly readable by a human but not automatable (JS-gated, captcha, no index).
    #: Candidates come from a recorded research pass, each row carrying its own evidence
    #: URL so the manual spot-check in the Validation Criteria still works.
    MANUAL_EVIDENCED = "manual_evidenced"
    #: Confirmed NOT publicly usable. Kept so the run report can say why, and so nobody
    #: silently substitutes a weaker source for this pair.
    UNAVAILABLE = "unavailable"
    #: A public/statutory register that is authoritative for membership but exposes NO stable
    #: per-entity URL — the register answers only a search form or a flat page (Ireland's Law
    #: Society, PSRA, Tusla and the Central Bank register are all this shape). The row cites the
    #: register page rather than a per-entity record, so it CANNOT self-evidence one company the
    #: way an entry_url_pattern demands. It is admitted at TIER 2 only, staged `claimed`, and the
    #: human at /admin/vetting-queue confirms the firm against the register — which is what that
    #: gate exists for. This is a deliberate, founder-approved exception to the "a search page
    #: evidences nobody" rule, scoped to genuinely permalink-less STATUTORY registers; it must
    #: never be used to launder a provider's own site (that is still SELF_DECLARED / tier 3).
    PUBLIC_REGISTER = "public_register"


@dataclass(frozen=True)
class RegistrySource:
    name: str
    base_url: str
    tier: int
    acquisition: Acquisition
    corridors: Tuple[str, ...]
    categories: Tuple[str, ...]
    #: Required when acquisition is UNAVAILABLE — the run report prints it verbatim.
    unavailable_reason: Optional[str] = None
    #: Regex an evidence URL must match to count as a record for ONE entity.
    #:
    #: The domain says who PUBLISHED a page; this says the page is about the candidate rather
    #: than about the register. Without it, `advokatforeningen.no/.../search-for-members/` and
    #: `portal.mvp.bafin.de/database/InstInfo/` are tier-1 evidence for anybody at all — a
    #: search form evidences nobody. Both of those were live in the first real harvest.
    #:
    #: It checks SHAPE, not existence: nothing in this pipeline fetches the URL, so an invented
    #: deep link still passes. The existence check is the human at /admin/vetting-queue, which
    #: is why promotion writes accreditations with status='claimed'. Do not describe this as
    #: provenance being verified.
    entry_url_pattern: Optional[str] = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.tier not in (1, 2, 3):
            raise ValueError(f"{self.name}: tier must be 1..3 (DB CHECK), got {self.tier}")
        if self.acquisition is Acquisition.UNAVAILABLE and not self.unavailable_reason:
            raise ValueError(f"{self.name}: UNAVAILABLE sources must state a reason")
        for c in self.corridors:
            if c not in CORRIDORS:
                raise ValueError(f"{self.name}: unknown corridor {c!r}")
        for c in self.categories:
            if c not in CATEGORIES:
                raise ValueError(f"{self.name}: unknown category {c!r}")
        # A permalink-less statutory register (PUBLIC_REGISTER) is the ONE case allowed to skip
        # entry_url_pattern — and only at tier 2, so its rows stage at reduced confidence and are
        # human-confirmed. Anything higher would let a register root pose as verified provenance.
        if self.acquisition is Acquisition.PUBLIC_REGISTER and self.tier != 2:
            raise ValueError(
                f"{self.name}: PUBLIC_REGISTER is tier 2 only — no per-entity URL means reduced "
                "confidence, staged 'claimed' for the vetting-queue human to confirm"
            )
        # Last, so a source with several problems still reports the more basic one first.
        # Mandatory rather than opt-in: an unguarded ingestable source is exactly how the
        # search-page hole appeared, and the next domain someone adds would reopen it.
        # UNAVAILABLE has nothing to read; PUBLIC_REGISTER has no per-entity URL by nature and
        # carries its reduced-confidence tier-2 rule above instead.
        if (
            self.tier < 3
            and self.acquisition not in (Acquisition.UNAVAILABLE, Acquisition.PUBLIC_REGISTER)
            and not self.entry_url_pattern
        ):
            raise ValueError(
                f"{self.name}: an ingestable registry must declare entry_url_pattern — "
                "otherwise its own search page counts as evidence for every candidate"
            )


# ── The catalogue ────────────────────────────────────────────────────────────
# Acquisition modes reflect a reconnaissance pass on 2026-08-10. Re-verify before
# assuming a source still behaves this way; registries redesign without notice, and a
# source that silently stops listing is indistinguishable from a category with no members.
SOURCES: Tuple[RegistrySource, ...] = (
    # ── movers — the highest-yield structured sources in the project ──────────
    RegistrySource(
        name="FIDI FAIM member directory",
        # Re-verified 2026-08-13 (Stage 9 Phase 0). The old base_url `/find-mover` now 404s,
        # which is what made this source look MANUAL_EVIDENCED. It is not: the country-scoped
        # index below is live and lists a per-entity detail link for every affiliate
        # (France, country=101, returns 11). Promoted to HTTP_LISTING accordingly — this is
        # exactly the drift the module docstring warns about, where a source that stopped
        # listing is indistinguishable from a category with no members.
        base_url="https://www.fidi.org/find-fidi-affiliate",
        tier=1,
        acquisition=Acquisition.HTTP_LISTING,
        corridors=CORRIDORS,
        categories=("movers",),
        entry_url_pattern=r"/find-fidi-affiliate/[^/]",
        notes=(
            "FAIM is the strongest accreditation in this category: audited, numbered, and "
            "renewed every 3 years — so accreditation_expiry is meaningful here and must be "
            "captured. Recon 2026-08-10 yielded 11 FR-DE and 4 FR-NO affiliates."
        ),
    ),
    RegistrySource(
        name="IAM member directory",
        base_url="https://www.iamovers.org/Members",
        tier=1,
        acquisition=Acquisition.UNAVAILABLE,
        corridors=CORRIDORS,
        categories=("movers",),
        unavailable_reason=(
            "The member directory has moved to the IAMX platform on a separate domain "
            "(mobilityex.com); no per-entity URL was confirmed under iamovers.org "
            "(probed 2026-08-12). Marked unavailable rather than left ingestable, because "
            "without a confirmed entry-URL shape any iamovers.org page would count as "
            "evidence for any candidate. No harvest row cites it today."
        ),
    ),
    # ── housing_agencies ─────────────────────────────────────────────────────
    RegistrySource(
        name="Finanstilsynet — estate agency register (NO)",
        base_url="https://www.finanstilsynet.no/en/registers/",
        tier=1,
        acquisition=Acquisition.HTTP_LOOKUP,
        corridors=("FR-NO",),
        categories=("housing_agencies", "tax_finance", "banks"),
        entry_url_pattern=r"[?&]id=\d+",
        notes=(
            "One register serving three categories: estate agencies, state-authorised "
            "auditors, and licensed banks. Per-entity lookup, no listable index."
        ),
    ),
    RegistrySource(
        name="IVD — Immobilienverband Deutschland directory",
        base_url="https://ivd.net/",
        tier=1,
        acquisition=Acquisition.UNAVAILABLE,
        corridors=("FR-DE",),
        categories=("housing_agencies",),
        unavailable_reason=(
            "Member directory is login-gated (recon 2026-08-10). Requires a direct "
            "membership enquiry to info@ivd.net — a human step, not a parser change."
        ),
    ),
    RegistrySource(
        name="FNAIM (FR)",
        base_url="https://www.fnaim.fr/",
        tier=1,
        acquisition=Acquisition.UNAVAILABLE,
        corridors=("FR-DE",),
        categories=("housing_agencies",),
        unavailable_reason="No public member search (recon 2026-08-10).",
    ),
    # ── legal_admin (immigration) ────────────────────────────────────────────
    RegistrySource(
        name="Rechtsanwaltskammer (RAK) + Partnerschaftsregister (DE)",
        # Corrected 2026-08-12: rechtsanwaltsregister.org is a redirector, not the register.
        # It 301s to bea-brak.de and then to bravsearch.bea-brak.de/bravsearch.
        base_url="https://bravsearch.bea-brak.de/bravsearch/",
        tier=1,
        acquisition=Acquisition.UNAVAILABLE,
        corridors=("FR-DE",),
        categories=("legal_admin",),
        unavailable_reason=(
            "The official register (BRAV) is reachable but is a form search; no stable "
            "per-entity URL was confirmed (probed 2026-08-12). Usable by a human, not "
            "linkable as evidence — so a row citing it cannot be spot-checked, which is the "
            "whole point of the source_url. Filter to firms publishing Ausländerrecht / "
            "immigration practice areas when checking by hand."
        ),
    ),
    # BRAV had its own entry here until 2026-08-12, marked UNAVAILABLE with
    # "Unreachable during recon 2026-08-10". Two things were wrong: it resolves fine (it moved
    # to bea-brak.de), and BRAV *is* the bundesweites amtliches Anwaltsverzeichnis — the same
    # register as the RAK entry above, under its formal name. Two names for one register meant
    # the duplicate was unreachable from any URL, because _DOMAIN_TO_SOURCE mapped the domain
    # to the RAK entry. Merged into it rather than left as dead weight.
    RegistrySource(
        name="Advokatforeningen + Brønnøysund register (NO)",
        base_url="https://www.advokatenhjelperdeg.no/",
        tier=1,
        acquisition=Acquisition.MANUAL_EVIDENCED,
        corridors=("FR-NO",),
        categories=("legal_admin",),
        # brreg  -> /nb/oppslag/enheter/917334110
        # advokatguiden -> /advokat/22051-thomas-reinholdt
        # The association's own /search-for-members/ page matches NEITHER, which is the point:
        # one harvest row cited it and was being counted as registry-evidenced.
        entry_url_pattern=r"/oppslag/enheter/\d+|/advokat/\d+",
        notes="Brønnøysund org numbers give a second, government-issued identifier.",
    ),
    # ── cross-category membership + entity confirmation ──────────────────────
    #
    # Added 2026-08-11 from the first real harvest (Card C): three of its evidence domains
    # had no source here, so honest rows had nowhere to map. Modelling a source you actually
    # used is the only way `validate()`'s tier rule can mean anything.
    RegistrySource(
        name="EuRA member directory",
        base_url="https://www.eura-relocation.com/members/",
        tier=1,
        acquisition=Acquisition.MANUAL_EVIDENCED,
        corridors=("FR-NO",),
        categories=("movers", "housing_agencies"),
        entry_url_pattern=r"/members/[^/]",
        notes="European Relocation Association. Membership is audited (EuRA Global Quality "
              "Seal), so it evidences standing — but it is an association, not a statutory "
              "register, and carries no licence number. Scoped to FR-NO deliberately: it is "
              "the only corridor the harvest actually sourced from it, and widening it to "
              "FR-DE would make FR-DE housing_agencies look ingestable when recon proved it "
              "is not (IVD login-gated, FNAIM no public search). Zero rows there is the "
              "correct answer, and a test pins it.",
    ),
    RegistrySource(
        name="Official public business register (DE)",
        base_url="https://www.hamburg.de/branchenbuch/",
        tier=2,
        acquisition=Acquisition.MANUAL_EVIDENCED,
        corridors=("FR-DE",),
        categories=("legal_admin", "tax_finance"),
        # /branchenbuch/hamburg/eintrag/10824243/ — the directory root is not an entry.
        entry_url_pattern=r"/branchenbuch/.+/eintrag/\d+",
        notes="City/state business directories confirm the ENTITY exists and is registered. "
              "They do not evidence professional accreditation — a chamber roll does. Tier 2 "
              "so it stages at reduced confidence and never poses as a bar or StBK listing.",
    ),
    RegistrySource(
        name="Self-declared (provider site / non-registry reference)",
        base_url="",
        tier=3,
        acquisition=Acquisition.MANUAL_EVIDENCED,
        corridors=("FR-DE", "FR-NO"),
        categories=CATEGORIES,
        notes="NOT a registry. Exists so a row whose only evidence is the provider's own "
              "Impressum, marketing site, or a Wikidata entry can be MODELLED honestly — at "
              "which point validate() rejects it on the tier-3 rule instead of letting it "
              "through wearing a registry's name. The rejects are the re-sourcing worklist.",
    ),
    # ── FR origin — entity register, NOT professional accreditation ──────────
    #
    # [AIQ-1827] Added after the four FR anchors the brief named turned out to be
    # unusable on 2026-08-12: CCI fichier national 403, FIDI find-mover 404, and both the
    # CNB annuaire and the OEC tableau are JS-driven with no listable index. That left
    # FR-NO's origin half with zero sources and zero suppliers.
    #
    # recherche-entreprises.api.gouv.fr (INSEE SIRENE + RNE) IS enumerable: free, no auth,
    # filterable by NAF activity code and postcode, and it answered for all four categories
    # (69.10Z avocats, 49.42Z demenagement, 68.31Z agences immobilieres, 69.20Z
    # experts-comptables) scoped to Paris.
    #
    # TIER 2, and the distinction is the whole point. SIRENE proves a company is REGISTERED
    # and what activity it SELF-DECLARED at registration. It does not evidence bar
    # membership, a carte T, or a place on the Ordre's tableau — those are the tier-1 claims,
    # and conflating them is exactly the defect found in the Den Norske Advokatforening rows,
    # where a Bronnoysund organisation number was sitting under a bar's name. Rows sourced
    # here stage at reduced confidence and must never be written `verified`.
    RegistrySource(
        name="INSEE SIRENE / recherche-entreprises (FR)",
        base_url="https://recherche-entreprises.api.gouv.fr/search",
        tier=2,
        acquisition=Acquisition.HTTP_LISTING,
        corridors=("FR-NO",),
        categories=("legal_admin", "movers", "housing_agencies", "tax_finance"),
        # One entity per SIREN: annuaire-entreprises.data.gouv.fr/entreprise/<9 digits>.
        entry_url_pattern=r"^https://annuaire-entreprises\.data\.gouv\.fr/entreprise/\d{9}$",
        notes=(
            "Entity confirmation only: registered company + self-declared NAF activity. "
            "Enumerable by activite_principale + code_postal. Scoped to FR-NO deliberately "
            "\u2014 that is the only corridor sourced from it; widening it to FR-DE would make "
            "FR-DE look covered by a source no one has run there. The per-entity evidence "
            "page at annuaire-entreprises.data.gouv.fr is a JS shell (212 bytes to a fetch), "
            "so it is human-checkable but cannot self-verify \u2014 which is consistent with "
            "tier 2: these rows stay `claimed`."
        ),
    ),
    # ── tax_finance ──────────────────────────────────────────────────────────
    RegistrySource(
        name="Bundessteuerberaterkammer / regional StBK (DE)",
        # Corrected 2026-08-12: bstbk.de is the federal chamber's CORPORATE site, not the
        # register. The official one is the amtliches Steuerberaterverzeichnis, below.
        base_url="https://steuerberaterverzeichnis.berufs-org.de/",
        tier=1,
        acquisition=Acquisition.UNAVAILABLE,
        corridors=("FR-DE",),
        categories=("tax_finance",),
        unavailable_reason=(
            "The amtliches Steuerberaterverzeichnis is a form search; no stable per-entity "
            "URL was confirmed (probed 2026-08-12). A human can verify a Steuerberater "
            "there, but the result is not linkable, so it cannot serve as a source_url. "
            "Until a per-entity URL shape is confirmed, FR-DE tax_finance rows have no "
            "ingestable registry — which is the honest answer, not a reason to accept the "
            "firms' own Impressum pages."
        ),
    ),
    # ── banks ────────────────────────────────────────────────────────────────
    RegistrySource(
        name="BaFin institute register (DE)",
        base_url="https://portal.mvp.bafin.de/database/InstInfo/",
        tier=1,
        acquisition=Acquisition.HTTP_LOOKUP,
        corridors=("FR-DE",),
        categories=("banks", "tax_finance"),
        # Two shapes, both verified 2026-08-12:
        #   institutDetails.do?cmd=loadInstitutAction&institutId=118938  (HTTP 200, public,
        #     lists the institution's authorisations with dates — the real licence evidence)
        #   kontenvergleich.bafin.de/en/account/678272c6                 (one harvest row)
        # The bare /database/InstInfo/ search form matches neither, by design.
        entry_url_pattern=r"institutId=\d+|/account/\w+",
        notes=(
            "Confirms the legal entity and licence. Banks are not accredited in the "
            "BRAIN-3C sense, so entity confirmation is all this proves — see "
            "confidence_for()."
        ),
    ),
    # ── Ireland (ES-IE / Andrea, Madrid→Dublin) ──────────────────────────────
    #
    # Otto's Dublin register preflight (2026-08-30) confirmed all five below are the
    # authoritative registers for their category, but NONE exposes a stable per-entity URL —
    # each answers only a search form (Law Society, CPA, Central Bank) or a flat register page
    # (Tusla, PSRA). So a harvested row cites the register page, not a record. Founder decision
    # 2026-08-30: admit them as PUBLIC_REGISTER (tier 2, staged `claimed`) rather than lose 15 of
    # 17 real Dublin providers to the permalink rule; the /admin/vetting-queue human confirms each
    # firm against the register. See the PUBLIC_REGISTER docstring for the rationale and its limits.
    RegistrySource(
        name="Law Society of Ireland — Find a Solicitor",
        base_url="https://www.lawsociety.ie/Find-a-Solicitor/",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("ES-IE",),
        categories=("legal_admin",),
        notes="Mandatory register — every practising solicitor in Ireland is on it. Search form, "
              "no per-entity URL; vetter confirms the firm's roll entry by name.",
    ),
    RegistrySource(
        name="CPA Ireland — firm directory",
        base_url="https://www.cpaireland.ie/find-a-cpa/",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("ES-IE",),
        categories=("tax_finance",),
        notes="No mandatory public register for Irish tax advisors; CPA Ireland's directory is the "
              "strongest available. Professional body, not statutory — tier 2 is the ceiling anyway.",
    ),
    RegistrySource(
        name="Central Bank of Ireland — Register of Authorised Firms",
        base_url="https://registers.centralbank.ie/",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("ES-IE",),
        categories=("banks",),
        notes="Statutory register of authorised credit institutions. Search form, no per-entity "
              "URL. Banks are capped at tier 2 by effective_tier regardless — entity/licence "
              "confirmation only, nothing about relocation-banking fitness.",
    ),
    RegistrySource(
        name="Tusla — Register of Independent Schools",
        base_url="https://www.tusla.ie/services/preschool-services/independent-schools/",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("ES-IE",),
        categories=("schools",),
        notes="Statutory register of private independent schools. Published as a single flat HTML "
              "page — no per-school URL; vetter confirms the school by name on that page.",
    ),
    RegistrySource(
        name="PSRA — Register of Licensed Property Services Providers",
        base_url="https://www.psr.ie/en/psra/register/",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("ES-IE",),
        categories=("housing_agencies",),
        notes="Statutory mandatory register — every letting/estate agent in Ireland must hold a "
              "PSRA licence. Search form, no per-entity URL; the licence number is the vetter's "
              "check against the register.",
    ),
    # ── France / Paris (NO-FR / Denis, Norway→Paris) ─────────────────────────
    #
    # Otto's Paris preflight (2026-08-30) found most French registers DO expose per-entity URLs,
    # so these carry a real entry_url_pattern (stronger provenance than the Irish set) — only the
    # Barreau is search-only and takes PUBLIC_REGISTER. Scoped to NO-FR; the older UNAVAILABLE
    # "FNAIM (FR)" entry above stays as the FR-DE recon record (that corridor's housing is still
    # unharvestable), and a test pins its emptiness — this NO-FR FNAIM is a separate source so it
    # does not reopen it.
    RegistrySource(
        name="REGAFI — registre des agents financiers (ACPR / Banque de France)",
        base_url="https://www.regafi.fr/",
        tier=2,
        acquisition=Acquisition.HTTP_LOOKUP,
        corridors=("NO-FR",),
        categories=("banks",),
        # fiche-banque?refine.id_referentiel=20556 — the bare /pages/fiche-banque form matches none.
        entry_url_pattern=r"id_referentiel=\d+",
        notes="Statutory register of authorised credit institutions (ACPR). Banks cap at tier 2 by "
              "effective_tier regardless — entity/licence confirmation only.",
    ),
    RegistrySource(
        name="Annuaire de l'Éducation nationale (annuaire-education.fr)",
        base_url="https://annuaire-education.fr/",
        tier=2,
        acquisition=Acquisition.HTTP_LISTING,
        corridors=("NO-FR",),
        categories=("schools",),
        # /etablissement/paris/lycee-... — one page per establishment, sourced from MEN open data.
        entry_url_pattern=r"/etablissement/",
        notes="Aggregator of official Ministère de l'Éducation nationale establishment data, with a "
              "stable per-school page. Tier 2: it confirms the school exists and is MEN-listed, not "
              "an accreditation.",
    ),
    RegistrySource(
        name="Ordre des Experts-Comptables — annuaire",
        base_url="https://annuaire.experts-comptables.org/",
        tier=1,
        acquisition=Acquisition.HTTP_LISTING,
        corridors=("NO-FR",),
        categories=("tax_finance",),
        # /expert-comptable/36523-sclover — one page per inscrit on the Ordre's tableau.
        entry_url_pattern=r"/expert-comptable/\d+",
        notes="The statutory professional order — inscription au tableau is mandatory to practise, "
              "so this is a genuine accreditation register with per-entity pages (tier 1).",
    ),
    RegistrySource(
        name="FNAIM — annuaire des adhérents (Paris)",
        base_url="https://www.fnaim.fr/",
        tier=2,
        acquisition=Acquisition.HTTP_LISTING,
        corridors=("NO-FR",),
        categories=("housing_agencies",),
        # /agence-immobiliere/21241/43-paris-17-... — one page per member agency. The
        # /agences-immobilieres/43-paris-75.htm LISTING page matches none, by design.
        entry_url_pattern=r"/agence-immobiliere/\d+",
        notes="Professional federation with per-agency member pages (re-verified 2026-08-30 — the "
              "2026-08-10 recon that marked FNAIM UNAVAILABLE for FR-DE predates this listing). "
              "Tier 2: membership + carte-T holder, entity-level.",
    ),
    RegistrySource(
        name="Chambre Syndicale du Déménagement (CSD) — annuaire adhérents",
        base_url="https://www.csdemenagement.fr/",
        tier=2,
        acquisition=Acquisition.HTTP_LISTING,
        corridors=("NO-FR",),
        categories=("movers",),
        # /annuaire-adherents/annuaire-demenageurs/3617-... — one page per member firm.
        entry_url_pattern=r"/annuaire-demenageurs/\d+",
        notes="French removals trade chamber. Membership directory with per-firm pages; tier 2 "
              "(association member list, not a FAIM-style audited accreditation).",
    ),
    RegistrySource(
        name="Barreau de Paris — annuaire des avocats",
        base_url="https://www.avocatparis.org/annuaire",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("NO-FR",),
        categories=("legal_admin",),
        notes="The Paris bar — inscription is mandatory to practise there. The annuaire is a search "
              "form with no per-entity URL, so it takes PUBLIC_REGISTER (tier 2, claimed): the "
              "vetter confirms the avocat on the roll by name.",
    ),
    # ── Singapore (FR-SG / Adrien) ────────────────────────────────────────────
    # Otto's FR-SG sourcing (2026-08-30) reached MAS FID and FIDI per-entity pages directly; the
    # rest (CEA/ACEAS, Law Society, ACRA, MOE/CPE) are JS-rendered SPAs that only answer a search
    # form, so they take PUBLIC_REGISTER (tier 2, staged `claimed`) exactly like the Dublin set.
    # MAS is the exception — its /fid/institution/detail/<id> pages ARE per-entity, so it is a
    # normal HTTP_LISTING with a real entry_url_pattern.
    RegistrySource(
        name="MAS Financial Institutions Directory",
        base_url="https://eservices.mas.gov.sg/fid",
        tier=1,
        acquisition=Acquisition.HTTP_LISTING,
        corridors=("FR-SG",),
        categories=("banks",),
        # /fid/institution/detail/3064-BNP-PARIBAS — one page per authorised institution.
        entry_url_pattern=r"/fid/institution/detail/",
        notes="Monetary Authority of Singapore — the statutory register of licensed financial "
              "institutions. Per-entity detail pages render server-side. Banks are capped at tier 2 "
              "by effective_tier regardless — identity/licence confirmation, not banking fitness.",
    ),
    RegistrySource(
        name="CEA Public Register (ACEAS)",
        base_url="https://eservices.cea.gov.sg/aceas/public-register/",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("FR-SG",),
        categories=("housing_agencies",),
        notes="Council for Estate Agencies — the mandatory register of licensed estate agencies "
              "(every agency carries a CEA licence no., e.g. L3008022J). JS SPA with no reliable "
              "per-entity URL; vetter confirms the agency by licence number.",
    ),
    RegistrySource(
        name="Law Society of Singapore — Find a Lawyer",
        base_url="https://www.lawsociety.org.sg/for-public/find-a-lawyer/",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("FR-SG",),
        categories=("legal_admin",),
        notes="The Singapore bar — membership is mandatory to practise. Search form / featured "
              "directory, no per-entity URL; vetter confirms the firm on the roll by name.",
    ),
    RegistrySource(
        name="ACRA Company Register",
        base_url="https://www.acra.gov.sg/",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("FR-SG",),
        categories=("tax_finance",),
        notes="Accounting & Corporate Regulatory Authority — the statutory company register (and "
              "public-accounting-firm registrar). Per-entity records are behind the BizFile+ portal, "
              "so this takes PUBLIC_REGISTER; vetter confirms the firm/UEN in BizFile+.",
    ),
    RegistrySource(
        name="MOE International Schools List",
        base_url="https://www.moe.gov.sg/international-schools",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("FR-SG",),
        categories=("schools",),
        notes="Ministry of Education list of international schools (CPE-registered private education "
              "institutions). JS-rendered index, no per-school URL; vetter confirms the school by name.",
    ),
    # ── Ecuador (US-EC / Abraham) ─────────────────────────────────────────────
    # EC registers are mostly JS/login/iframe-gated (superbancos, MinEduc AMIE, Colegio de Abogados
    # iframe, CCPP login) — sourced by browser-grounding, not Otto's scraper. CAINEC is the one that
    # exposes real per-entity records: ficha.php?codigo=INMO-GP-... pages rendered in a browser (Otto's
    # scraper saw only JS shells). CAINEC is a national body (Cuenca-based) so its accredited firms are
    # not city-scoped — the /admin/vetting-queue human confirms Quito service. Tier 2, HTTP_LISTING.
    RegistrySource(
        name="CAINEC — Great Place Inmobiliario",
        base_url="https://www.cainec.com/greatplace.php",
        tier=2,
        acquisition=Acquisition.HTTP_LISTING,
        corridors=("US-EC",),
        categories=("housing_agencies",),
        # /ficha.php?codigo=INMO-GP-2026-06-005 — one certificate record per accredited firm.
        entry_url_pattern=r"/ficha\.php\?codigo=",
        notes="Cámara Inmobiliaria Ecuatoriana accreditation directory — the only EC real-estate "
              "register with public per-entity records. National (Cuenca-based); vetter confirms the "
              "firm actually serves Quito, since CAINEC does not scope by city.",
    ),
    # ── United Kingdom (XX-GB destination-coverage / London) ───────────────────
    # UK statutory/professional registers, all exposing stable per-entity URLs (unlike the
    # Irish set, which had none and took PUBLIC_REGISTER). Movers are already covered by the
    # global FIDI source above (corridors=CORRIDORS now includes XX-GB). Banks are capped at
    # tier 2 by effective_tier regardless — the FCA record confirms identity/authorisation, not
    # banking fitness. Sourced 2026-08-31 (London batch).
    RegistrySource(
        name="SRA — Solicitors Regulation Authority register",
        base_url="https://www.sra.org.uk/consumers/register/",
        tier=2,
        acquisition=Acquisition.HTTP_LISTING,
        corridors=("XX-GB",),
        categories=("legal_admin",),
        # /consumers/register/organisation/?sraNumber=459836 — one page per SRA-regulated firm.
        entry_url_pattern=r"sraNumber=\d+",
        notes="The Solicitors Regulation Authority is the statutory regulator of solicitors' "
              "firms in England & Wales; its consumer register exposes a per-firm page keyed on "
              "SRA number. Immigration solicitors are the corporate-mobility legal category.",
    ),
    RegistrySource(
        name="ICAEW — Find a Chartered Accountant",
        base_url="https://find.icaew.com/",
        tier=2,
        acquisition=Acquisition.HTTP_LISTING,
        corridors=("XX-GB",),
        categories=("tax_finance",),
        # /firms/london/blick-rothenberg-limited/1CT85L — one page per member firm.
        entry_url_pattern=r"/firms/",
        notes="Institute of Chartered Accountants in England & Wales — statutory-recognised "
              "supervisory body; its Find-a-Chartered-Accountant directory lists per-firm pages.",
    ),
    RegistrySource(
        name="FCA Financial Services Register",
        base_url="https://register.fca.org.uk/s/",
        tier=2,
        acquisition=Acquisition.HTTP_LISTING,
        corridors=("XX-GB",),
        categories=("banks",),
        # /s/firm?id=001b000003ZcFXFAA3 — one page per authorised firm (carries the FRN).
        entry_url_pattern=r"/s/firm",
        notes="Financial Conduct Authority — the statutory register of authorised firms; each "
              "row carries a Firm Reference Number. Per-entity firm pages render server-side.",
    ),
    RegistrySource(
        name="GIAS — Get Information About Schools (DfE)",
        base_url="https://get-information-schools.service.gov.uk/",
        tier=2,
        acquisition=Acquisition.HTTP_LISTING,
        corridors=("XX-GB",),
        categories=("schools",),
        # /Establishments/Establishment/Details/101168 — one page per school, keyed on URN.
        entry_url_pattern=r"/Establishment/Details/\d+",
        notes="The Department for Education's official register of schools (GIAS); every "
              "establishment has a per-entity page keyed on its URN, with open/closed status.",
    ),
    RegistrySource(
        name="ARLA Propertymark — member directory",
        base_url="https://www.propertymark.co.uk/",
        tier=2,
        acquisition=Acquisition.HTTP_LISTING,
        corridors=("XX-GB",),
        categories=("housing_agencies",),
        # /company/foxtons-wembley.html — one page per member branch.
        entry_url_pattern=r"/company/",
        notes="Propertymark (ARLA) is the professional body for UK letting agents; its member "
              "directory exposes a per-branch company page. Membership is the letting-agent "
              "quality mark short of the mandatory redress-scheme registration.",
    ),
    # ── Canada (XX-CA destination-coverage / Toronto) ──────────────────────────
    # Movers are covered by the global FIDI source above. The other Ontario/Canada registers are
    # search-form or flat-list with no stable per-entity URL (like the Dublin set), so they take
    # PUBLIC_REGISTER tier 2, staged 'claimed', and the /admin/vetting-queue human confirms each
    # firm against the register. Sourced 2026-08-31 (Toronto batch).
    RegistrySource(
        name="LSO — Law Society of Ontario directory",
        base_url="https://lso.ca/public-resources/finding-a-lawyer-or-paralegal/lawyer-and-paralegal-directory",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("XX-CA",),
        categories=("legal_admin",),
        notes="The Law Society of Ontario — mandatory regulator to practise law in Ontario. Its "
              "Lawyer & Paralegal Directory is a search form with no per-entity URL; vetter "
              "confirms the immigration firm/lawyer on the roll by name.",
    ),
    RegistrySource(
        name="CPA Ontario — firm directory",
        base_url="https://www.cpaontario.ca/protecting-the-public/directories/firm",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("XX-CA",),
        categories=("tax_finance",),
        notes="Chartered Professional Accountants of Ontario — the statutory accounting regulator. "
              "Firm directory is a flat/search page (403 to automated fetch), no per-entity URL; "
              "vetter confirms the firm's CPA Ontario registration.",
    ),
    RegistrySource(
        name="CDIC — member institutions list",
        base_url="https://www.cdic.ca/depositors/list-of-members/",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("XX-CA",),
        categories=("banks",),
        notes="Canada Deposit Insurance Corporation — the federal deposit insurer; its member list "
              "is the authoritative confirmation that a firm is a real Canadian bank. Flat list, no "
              "per-entity URL; vetter confirms membership. (Banks are capped at tier 2 regardless.)",
    ),
    RegistrySource(
        name="Ontario Ministry of Education — Private School Location List",
        base_url="https://data.ontario.ca/dataset/private-school-location-list",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("XX-CA",),
        categories=("schools",),
        notes="The Government of Ontario's official private-school list (open-data dataset, BSID per "
              "school). Published as an XLSX with no per-school URL; vetter confirms the school by "
              "its BSID (carried in accreditation_number).",
    ),
    RegistrySource(
        name="RECO — Real Estate Council of Ontario registrant search",
        base_url="https://registrantsearch.reco.on.ca/",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("XX-CA",),
        categories=("housing_agencies",),
        notes="The Real Estate Council of Ontario — mandatory registrar for real-estate brokerages "
              "in Ontario. Registrant search form, no per-entity URL; vetter confirms the brokerage "
              "is RECO-registered.",
    ),
    # ── Australia (XX-AU destination-coverage / Sydney) ────────────────────────
    # Movers on the global FIDI source. The other Australian registers are search-form/flat with no
    # stable per-entity URL, so PUBLIC_REGISTER tier 2 (staged 'claimed', vetter confirms). Sourced
    # 2026-08-31 (Sydney batch); CPA Australia / CA-ANZ / REINSW were Cloudflare/JS-blocked and
    # substituted with the statutory TPB and NSW Fair Trading registers.
    RegistrySource(
        name="OMARA — Register of Migration Agents",
        base_url="https://portal.mara.gov.au/search-the-register-of-migration-agents/",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("XX-AU",),
        categories=("legal_admin",),
        notes="Office of the Migration Agents Registration Authority — the statutory register of "
              "registered migration agents (mandatory to give immigration assistance for a fee). "
              "Search form, no per-entity URL; vetter confirms the agent/firm on the register.",
    ),
    RegistrySource(
        name="TPB — Tax Practitioners Board register",
        base_url="https://myprofile.tpb.gov.au/public-register/",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("XX-AU",),
        categories=("tax_finance",),
        notes="Tax Practitioners Board — the statutory register of registered tax agents (mandatory "
              "to prepare Australian tax returns for a fee). Public register search; the practitioner "
              "detail page carries the registration number, but no stable per-entity URL — vetter confirms.",
    ),
    RegistrySource(
        name="APRA — Register of authorised ADIs",
        base_url="https://www.apra.gov.au/registers/list-registered-authorised-deposit-taking-institutions",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("XX-AU",),
        categories=("banks",),
        notes="Australian Prudential Regulation Authority — the statutory list of authorised "
              "deposit-taking institutions (banks). Flat list, no per-entity URL; vetter confirms "
              "membership. (Banks are capped at tier 2 regardless.)",
    ),
    RegistrySource(
        name="NESA — Approved NSW school providers (CRICOS)",
        base_url="https://www.nsw.gov.au/education-and-training/nesa/overseas-students/approved-nsw-school-providers",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("XX-AU",),
        categories=("schools",),
        notes="NSW Education Standards Authority list of NSW schools approved to enrol overseas "
              "students (CRICOS). Table page with CRICOS code per school but no per-school URL; "
              "vetter confirms the school by CRICOS code (carried in accreditation_number).",
    ),
    RegistrySource(
        name="NSW Fair Trading — property agents register",
        base_url="https://verify.licence.nsw.gov.au/home/Property",
        tier=2,
        acquisition=Acquisition.PUBLIC_REGISTER,
        corridors=("XX-AU",),
        categories=("housing_agencies",),
        notes="NSW Fair Trading (Verify NSW) — the statutory licence register for property/real-estate "
              "agents under the Property and Stock Agents Act. Search form, no per-entity URL; vetter "
              "confirms the current licence number (carried in accreditation_number).",
    ),
    # ── Amsterdam (XX-NL) + Madrid (XX-ES) + Dubai (XX-AE) — Otto batch 2026-08-31 ──────────────
    # Movers reuse the global FIDI source. Only bona-fide statutory/professional registers are wired;
    # Otto's law-firm-website and mis-cited rows (Spanish tax agency for banks, Dubai Land Dept for
    # tax, aggregator sites) stay unmapped → SELF_DECLARED → rejected by validate(), honestly.
    RegistrySource(
        name="DNB — De Nederlandsche Bank register",
        base_url="https://www.dnb.nl/en/public-register/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-NL",), categories=("banks",),
        notes="De Nederlandsche Bank — the Dutch central-bank register of licensed banks. Search "
              "register, no stable per-entity URL; vetter confirms. (Banks capped at tier 2 regardless.)",
    ),
    RegistrySource(
        name="NOvA — Dutch Bar find-a-lawyer register",
        base_url="https://zoekeenadvocaat.advocatenorde.nl/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-NL",), categories=("legal_admin",),
        notes="Nederlandse orde van advocaten — the statutory Dutch bar register (mandatory to practise). "
              "Search form, no per-entity URL; vetter confirms the immigration lawyer on the roll.",
    ),
    RegistrySource(
        name="AFM — Autoriteit Financiële Markten register",
        base_url="https://www.afm.nl/en/sector/registers",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-NL",), categories=("tax_finance",),
        notes="Dutch Authority for the Financial Markets — statutory register of financial-service firms. "
              "Search register, no per-entity URL; vetter confirms the firm's AFM registration.",
    ),
    RegistrySource(
        name="MVA — Makelaarsvereniging Amsterdam members",
        base_url="https://www.mva.nl/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-NL",), categories=("housing_agencies",),
        notes="Makelaarsvereniging Amsterdam — the Amsterdam real-estate brokers' association. Member "
              "directory without a stable per-entity URL; vetter confirms membership.",
    ),
    RegistrySource(
        name="CBUAE — Central Bank of the UAE register",
        base_url="https://www.centralbank.ae/en/our-operations/licensing-and-authorisation/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-AE",), categories=("banks",),
        notes="Central Bank of the UAE — the statutory register of licensed banks. No stable per-entity "
              "URL; vetter confirms. (Banks capped at tier 2 regardless.)",
    ),
    RegistrySource(
        name="KHDA — Dubai schools directory",
        base_url="https://web.khda.gov.ae/en/education-directory",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-AE",), categories=("schools",),
        notes="Knowledge and Human Development Authority — the Dubai education regulator's directory of "
              "licensed private schools. JS-rendered directory, no stable per-entity URL; vetter confirms.",
    ),
    RegistrySource(
        name="IBO — IB World Schools directory",
        base_url="https://www.ibo.org/programmes/find-an-ib-school/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-ES", "XX-NL", "XX-AE", "XX-CH", "XX-IT", "XX-SE", "XX-BE", "XX-AT", "XX-DK", "XX-SA", "XX-FI", "XX-PT", "XX-JP", "XX-HK", "XX-PL", "XX-NZ", "XX-QA", "XX-KW", "XX-KR", "XX-IL", "XX-LU", "XX-CZ", "XX-GR", "XX-MX", "XX-BR"), categories=("schools",),
        notes="International Baccalaureate Organization — the authoritative directory of authorised IB "
              "World Schools. Search directory; a school's IB authorisation is the accreditation the "
              "vetter confirms. Used for international schools where a national per-entity register is "
              "login/JS-gated.",
    ),
    # ── Zurich (XX-CH) + Milan (XX-IT) + Stockholm (XX-SE) — Otto batch 2026-08-31 ──────────────
    # Thin batch (national legal/tax/housing registers are JS-only): movers reuse FIDI, SE schools
    # reuse IBO. Only two new registers needed.
    RegistrySource(
        name="FINMA — Swiss financial-market authority register",
        base_url="https://www.finma.ch/en/finma-public/authorised-institutions-individuals-and-products/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-CH",), categories=("banks",),
        notes="Swiss Financial Market Supervisory Authority — the statutory register of authorised "
              "banks. JS/PDF register, no stable per-entity URL; vetter confirms against FINMA's list. "
              "(Banks capped at tier 2 regardless.)",
    ),
    RegistrySource(
        name="SGIS — Swiss Group of International Schools members",
        base_url="https://www.sgischools.com/schools/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-CH",), categories=("schools",),
        notes="Swiss Group of International Schools — the membership body for accredited international "
              "schools in Switzerland. Member directory; vetter confirms membership.",
    ),
    # ── Brussels (XX-BE) + Vienna (XX-AT) + Copenhagen (XX-DK) — Otto/subagent batch 2026-08-31 ──
    # Movers reuse FIDI; schools reuse IBO. BE/AT legal + tax registers are anti-bot/JS-gated (blocked,
    # re-source worklist), so only the reachable statutory registers are wired.
    RegistrySource(
        name="NBB — National Bank of Belgium credit-institutions list",
        base_url="https://www.nbb.be/en/financial-oversight/prudential-supervision/areas-responsibility/credit-institutions/lists",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-BE",), categories=("banks",),
        notes="National Bank of Belgium — statutory list of authorised credit institutions. Flat list, "
              "no per-entity URL; vetter confirms. (Banks capped at tier 2 regardless.)",
    ),
    RegistrySource(
        name="FMA — Austrian Financial Market Authority company database",
        base_url="https://www.fma.gv.at/en/search-company-database/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-AT",), categories=("banks",),
        notes="Finanzmarktaufsicht — the Austrian financial regulator's company database of licensed "
              "banks. Search form; vetter confirms. (Banks capped at tier 2 regardless.)",
    ),
    RegistrySource(
        name="Finanstilsynet — Danish FSA company register",
        base_url="https://virksomhedsregister.finanstilsynet.dk/index-en.html",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-DK",), categories=("banks",),
        notes="Danish Financial Supervisory Authority — statutory register of licensed banks (FTID). "
              "Search register; vetter confirms. (Banks capped at tier 2 regardless.)",
    ),
    RegistrySource(
        name="BIV/IPI — Belgian real-estate agents register",
        base_url="https://www.biv.be/vastgoedmakelaars",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-BE",), categories=("housing_agencies",),
        notes="Beroepsinstituut van Vastgoedmakelaars / Institut professionnel des agents immobiliers — "
              "the statutory register of recognised Belgian estate agents (IPI/BIV number). Search form; "
              "vetter confirms the recognition number.",
    ),
    RegistrySource(
        name="WKO — Austrian real-estate agents register",
        base_url="https://firmen.wko.at/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-AT",), categories=("housing_agencies",),
        notes="Wirtschaftskammer Österreich Firmen A-Z — the register of licensed Immobilienmakler "
              "(membership is mandatory to trade). Search form; vetter confirms.",
    ),
    RegistrySource(
        name="MDE — Dansk Ejendomsmæglerforening members",
        base_url="https://www.de.dk/boligkob-salg/find-medlem",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-DK",), categories=("housing_agencies",),
        notes="Dansk Ejendomsmæglerforening — the Danish estate-agents' association member directory. "
              "Search form; vetter confirms membership.",
    ),
    RegistrySource(
        name="Advokatsamfundet — Advokatnøglen (Danish bar)",
        base_url="https://www.advokatnoeglen.dk/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-DK",), categories=("legal_admin",),
        notes="The Danish Bar and Law Society register (mandatory to practise). Search directory; vetter "
              "confirms the firm/lawyer on the roll.",
    ),
    RegistrySource(
        name="FSR — danske revisorer member directory",
        base_url="https://www.fsr.dk/vaerktoejer/find-revisor",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-DK",), categories=("tax_finance",),
        notes="FSR – danske revisorer — the Danish auditors' & accountants' professional body member "
              "directory. Search directory; vetter confirms membership.",
    ),
    # ── Tier-3 hub cities: Riyadh (XX-SA) + Helsinki (XX-FI) + Lisbon (XX-PT), subagent batch 2026-08-31 ──
    # Movers reuse the FIDI FAIM directory (corridors=CORRIDORS covers them); schools reuse IBO above.
    # Riyadh legal is the Saudi Bar Association public firms directory; SA housing/tax registers are
    # verify-by-number-only / geoblocked (skipped, re-source worklist). Lisbon legal (Ordem dos
    # Advogados) is individual-only, no firm listing (skipped). FI/PT banks cite the EU-level
    # ECB/EBA registers (the national SPAs are Cloudflare/JS-gated) — same authorisation data.
    RegistrySource(
        name="SAMA — Saudi Central Bank licensed local banks",
        base_url="https://www.sama.gov.sa/en-US/Licensing/Pages/LicensedBanks.aspx",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-SA",), categories=("banks",),
        notes="Saudi Central Bank (SAMA) — statutory list of licensed local banks. Flat list; vetter "
              "confirms. (Banks capped at tier 2 regardless.)",
    ),
    RegistrySource(
        name="Saudi Bar Association — legal firms directory",
        base_url="https://eservice.sba.gov.sa/directory",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-SA",), categories=("legal_admin",),
        notes="Saudi Bar Association — public register of licensed legal firms (each firm has an "
              "eservice.sba.gov.sa/directory/<id> page). Vetter confirms the firm on the roll.",
    ),
    RegistrySource(
        name="ECB Banking Supervision — supervised entities (SSM)",
        base_url="https://www.bankingsupervision.europa.eu/banking/list/who/html/index.en.html",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-FI", "XX-GR"), categories=("banks",),
        notes="ECB/SSM list of supervised entities — the euro-area credit institutions authorised in each "
              "country, each with an LEI. Used where the national regulator's register is a JS SPA "
              "(FIN-FSA / Bank of Greece); the ECB list carries the same authorisation status. Filter by "
              "the country section. (Banks capped at tier 2.)",
    ),
    RegistrySource(
        name="PRH — Finnish auditor register (Tilintarkastajahaku)",
        base_url="https://tietopalvelut.prh.fi/tilintarkastajahaku/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-FI",), categories=("tax_finance",),
        notes="Finnish Patent and Registration Office (PRH) auditor oversight — statutory register of "
              "authorised audit firms (Tilintarkastusyhteisö). Search register; vetter confirms.",
    ),
    RegistrySource(
        name="Finnish Bar Association — Find an Attorney",
        base_url="https://www.findanattorney.fi/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-FI",), categories=("legal_admin",),
        notes="Suomen Asianajajaliitto — the Finnish Bar Association member directory (membership is "
              "mandatory to use the asianajaja title). Search directory; vetter confirms membership.",
    ),
    RegistrySource(
        name="EBA Credit Institutions Register (Portugal)",
        base_url="https://euclid.eba.europa.eu/register/cir/search",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-PT",), categories=("banks",),
        notes="European Banking Authority Credit Institutions Register — data owned by Banco de Portugal; "
              "each entry carries the BdP institution code + LEI. Used because bportugal.pt is "
              "Cloudflare-gated. (Banks capped at tier 2.)",
    ),
    RegistrySource(
        name="IMPIC — Portuguese estate-agent (AMI) register",
        base_url="https://www.impic.pt/impic/pt-pt/atividades/mediacao-imobiliaria",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-PT",), categories=("housing_agencies",),
        notes="Instituto dos Mercados Públicos, do Imobiliário e da Construção — statutory register of "
              "licensed estate agents (AMI licence number). Vetter confirms the AMI number.",
    ),
    RegistrySource(
        name="OROC — Portuguese statutory auditors (SROC) register",
        base_url="https://www.oroc.pt/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-PT",), categories=("tax_finance",),
        notes="Ordem dos Revisores Oficiais de Contas — the official list of registered audit firms "
              "(SROC number). Vetter confirms the SROC number.",
    ),
    # ── Tokyo (XX-JP) — subagent batch 2026-08-31. Movers reuse FIDI; schools reuse IBO. Legal
    # skipped (JFBA Himawari 403, gyoseishoshi login-gated — re-source worklist in batch README).
    RegistrySource(
        name="FSA — Japan licensed financial institutions list",
        base_url="https://www.fsa.go.jp/en/regulated/licensed/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-JP",), categories=("banks",),
        notes="Financial Services Agency (Japan) — the statutory List of Licensed (Registered) Financial "
              "Institutions (City Banks & Trust Banks). Vetter confirms. (Banks capped at tier 2.)",
    ),
    RegistrySource(
        name="MLIT — Japan real-estate broker (Takken) licence search",
        base_url="https://etsuran2.mlit.go.jp/TAKKEN/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-JP",), categories=("housing_agencies",),
        notes="Ministry of Land, Infrastructure, Transport and Tourism — national 宅地建物取引業 (Takken) "
              "licence register; name+prefecture search returns the 免許番号 licence number. Vetter confirms it.",
    ),
    RegistrySource(
        name="Nichizeiren — Japan certified tax accountant (zeirishi) register",
        base_url="https://www.zeirishikensaku.jp/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-JP",), categories=("tax_finance",),
        notes="Japan Federation of Certified Public Tax Accountants' Associations (Nichizeiren) — the "
              "statutory zeirishi search site; a firm's registered zeirishi confirm membership. Vetter confirms.",
    ),
    # ── Hong Kong (XX-HK) — subagent batch 2026-08-31. Movers FIDI, schools IBO. Housing (EAA,
    # CAPTCHA-gated) + tax (HKICPA 404 / AFRC postback, no stable per-firm URL) skipped — worklist.
    RegistrySource(
        name="HKMA — register of authorized institutions (Hong Kong)",
        base_url="https://www.hkma.gov.hk/eng/smart-consumers/register-of-authorized-institutions/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-HK",), categories=("banks",),
        notes="Hong Kong Monetary Authority — statutory register of authorized institutions; each licensed "
              "bank has a vpr.hkma.gov.hk detail page with its AI code. Vetter confirms. (Banks capped tier 2.)",
    ),
    RegistrySource(
        name="Law Society of Hong Kong — The Law List",
        base_url="https://www.hklawsoc.org.hk/en/Serve-the-Public/The-Law-List",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-HK",), categories=("legal_admin",),
        notes="The Law Society of Hong Kong — statutory roll of solicitors' firms (each firm has a "
              "Firm-Detail?FirmId=<id> page). Vetter confirms the firm on the roll.",
    ),
    # ── Warsaw (XX-PL) — subagent batch 2026-08-31. Movers FIDI, schools IBO. Housing skipped:
    # Poland abolished mandatory estate-agent licensing on 2014-01-01, so no statutory register exists.
    RegistrySource(
        name="KNF — Polish Financial Supervision Authority entity register",
        base_url="https://www.knf.gov.pl/podmioty/wyszukiwarka_podmiotow",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-PL",), categories=("banks",),
        notes="Komisja Nadzoru Finansowego — the register of supervised entities (Poland is outside the "
              "euro area/SSM, so KNF, not the ECB, is the supervisor). Per-bank searchPhrase URLs. Vetter "
              "confirms. (Banks capped at tier 2.)",
    ),
    RegistrySource(
        name="PANA — Polish audit-firm register (Lista firm audytorskich)",
        base_url="https://strefa.pana.gov.pl/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-PL",), categories=("tax_finance",),
        notes="Polska Agencja Nadzoru Audytowego — the statutory register of audit firms, each with a "
              "register number. Vetter confirms the number.",
    ),
    RegistrySource(
        name="Krajowy Rejestr Adwokatów — Polish Bar register",
        base_url="https://rejestradwokatow.pl/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-PL",), categories=("legal_admin",),
        notes="Krajowy Rejestr Adwokatów i Aplikantów Adwokackich — the Polish Bar's statutory register "
              "(each advocate has a WAW/Adw/<no> profile). Vetter confirms the advocate/firm on the roll.",
    ),
    # ── Auckland (XX-NZ) — subagent batch 2026-08-31. Movers FIDI, schools IBO. Legal (NZLS per-lawyer
    # only) + tax (CA ANZ Cloudflare-gated) skipped — worklist in batch README.
    RegistrySource(
        name="RBNZ — Registered banks in New Zealand",
        base_url="https://www.rbnz.govt.nz/regulation-and-supervision/cross-industry-regulation/register-of-registered-banks-in-new-zealand",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-NZ",), categories=("banks",),
        notes="Reserve Bank of New Zealand — the statutory register of registered banks. Flat list; vetter "
              "confirms. (Banks capped at tier 2.)",
    ),
    RegistrySource(
        name="REA — New Zealand real-estate licensee public register",
        base_url="https://publicregister.rea.govt.nz/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-NZ",), categories=("housing_agencies",),
        notes="Real Estate Authority — the public register of licensed real-estate companies/agents; each "
              "has a per-licence detail page with its licence number. Vetter confirms the number.",
    ),
    # ── Doha (XX-QA) — subagent batch 2026-08-31. Movers FIDI, schools IBO. Banks (QCB register JS/
    # geo-gated) + housing (broker register geo-fenced) skipped — worklist in batch README.
    RegistrySource(
        name="QFC — Qatar Financial Centre public register",
        base_url="https://eservices.qfc.qa/qfcpublicregister/publicregister.aspx",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-QA",), categories=("legal_admin", "tax_finance"),
        notes="Qatar Financial Centre Authority public register — lists QFCA-licensed approved service "
              "providers (law firms) and approved auditors (audit firms). Vetter confirms the firm on the "
              "register (tables ApprovedServiceProvider / ApprovedAuditors).",
    ),
    # ── Kuwait City (XX-KW) — subagent batch 2026-08-31. Movers FIDI, schools IBO. Legal (Lawyers
    # Association/MoJ), tax (MOCI auditors) and housing (MOCI broker e-service) have no reachable public
    # register — skipped, worklist in batch README.
    RegistrySource(
        name="CBK — Central Bank of Kuwait regulated banks",
        base_url="https://www.cbk.gov.kw/en/cbk-news/regulated-entities/kuwaiti-banks",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-KW",), categories=("banks",),
        notes="Central Bank of Kuwait — the register of regulated Kuwaiti banks (conventional + Islamic). "
              "Flat list; vetter confirms. (Banks capped at tier 2.)",
    ),
    # ── Seoul (XX-KR) — subagent batch 2026-08-31. Movers FIDI, schools IBO. Legal (Korean Bar),
    # tax (KICPA) and housing (공인중개사, local-gov) are Korean-only JS/POST portals with no stable
    # per-firm URL — skipped, worklist in batch README.
    RegistrySource(
        name="KFB — Korea Federation of Banks member list",
        base_url="https://www.kfb.or.kr/eng/about/member.php",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-KR",), categories=("banks",),
        notes="Korea Federation of Banks — the member list of FSS-supervised banks. Flat list; vetter "
              "confirms. (Banks capped at tier 2.)",
    ),
    # ── Tel Aviv (XX-IL) — subagent batch 2026-08-31. Movers FIDI, schools IBO. Legal (Israel Bar
    # geo-blocked + individual-only), tax (ICPAS voluntary, no per-firm), housing (MoJ broker register
    # individual-only) skipped — worklist in batch README.
    RegistrySource(
        name="Bank of Israel — supervised banking corporations",
        base_url="https://www.boi.org.il/en/banking-supervision/supervised-banking-corporations/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-IL",), categories=("banks",),
        notes="Bank of Israel Banking Supervision — the register of supervised banking corporations; each "
              "carries its official BoI reporting symbol. Vetter confirms. (Banks capped at tier 2.)",
    ),
    # ── Luxembourg City (XX-LU) — subagent batch 2026-08-31. Movers FIDI (the 1 LU affiliate),
    # schools IBO. Legal (Barreau tableau is a client-side DataTable, no per-firm permalink) skipped.
    RegistrySource(
        name="CSSF — Luxembourg supervised entities & audit register",
        base_url="https://www.cssf.lu/en/regulated-entities/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-LU",), categories=("banks", "tax_finance"),
        notes="Commission de Surveillance du Secteur Financier — the register of supervised credit "
              "institutions (edesk.apps.cssf.lu, type-B banks) and the Public Register of the Audit "
              "Profession (audit.apps.cssf.lu, approved audit firms, status AGR). Vetter confirms.",
    ),
    RegistrySource(
        name="CIGDL — Chambre Immobilière du Grand-Duché member directory",
        base_url="https://www.chambre-immobiliere.lu/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-LU",), categories=("housing_agencies",),
        notes="Chambre Immobilière du Grand-Duché de Luxembourg — the recognized real-estate professional "
              "body's member directory (agence-immobiliere category). Vetter confirms membership.",
    ),
    # ── Athens (XX-GR) — subagent batch 2026-08-31. Movers FIDI, schools IBO, banks ECB SSM (above).
    # Legal (Athens Bar contact-lookup, no permalink) + housing (no per-firm realtor register) skipped.
    RegistrySource(
        name="ELTE/HAASOB — Greek public register of audit firms",
        base_url="https://dbapplication.elte.org.gr/",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-GR",), categories=("tax_finance",),
        notes="Hellenic Accounting and Auditing Standards Oversight Board (ELTE) — the statutory Public "
              "Register of Audit Firms; each firm has a companyDetails page with its ELTE ID. Vetter confirms.",
    ),
    # ── Mexico City (XX-MX) — subagent batch 2026-08-31. Movers FIDI, schools IBO. Tax (IMCP individual-
    # only), legal (no unified bar), housing (AMPI voluntary) skipped — worklist in batch README.
    RegistrySource(
        name="CONDUSEF SIPRES — Mexican supervised financial entities",
        base_url="https://webapps.condusef.gob.mx/SIPRES/jsp/pub/index.jsp",
        tier=2, acquisition=Acquisition.PUBLIC_REGISTER, corridors=("XX-MX",), categories=("banks",),
        notes="CONDUSEF SIPRES — the official register of supervised financial entities (CNBV-supervised "
              "banks), each with a Clave de Registro and per-entity home_publico.jsp page. Vetter confirms. "
              "(Banks capped at tier 2.)",
    ),
)


# ── Policy helpers — encode the rules once, not at every call site ───────────

def sources_for(corridor: str, category: str) -> List[RegistrySource]:
    """Every declared source for a pair, including UNAVAILABLE ones.

    Unavailable sources are returned deliberately: the run report has to be able to say
    "this pair produced nothing and here is which registry refused", which is a different
    and far more actionable statement than "0 candidates".
    """
    return [
        s for s in SOURCES
        if corridor in s.corridors and category in s.categories
    ]


def ingestable_sources(corridor: str, category: str) -> List[RegistrySource]:
    """Sources a candidate may actually be ingested from.

    Excludes UNAVAILABLE (nothing to read) and tier 3 (never sufficient alone).
    """
    return [
        s for s in sources_for(corridor, category)
        if s.acquisition is not Acquisition.UNAVAILABLE and s.tier < 3
    ]


def unavailable_reasons(corridor: str, category: str) -> Dict[str, str]:
    """{source_name: reason} for the run report."""
    return {
        s.name: s.unavailable_reason or "unspecified"
        for s in sources_for(corridor, category)
        if s.acquisition is Acquisition.UNAVAILABLE
    }


def confidence_for(tier: int, has_accreditation_number: bool, has_expiry: bool,
                   category: str) -> float:
    """Confidence for a harvested row. Never returns 1.0.

    1.0 is reserved for a human who has verified the entry — a harvest establishes that a
    registry lists the company, which is membership, not fitness. Conflating the two is
    how a staged candidate quietly becomes a recommended supplier.

    Banks cap at 0.5: they are licensed, not accredited, so the register confirms the
    entity exists and nothing about corporate relocation capability.
    """
    if category == "banks":
        return 0.5
    if tier >= 2:
        return 0.5
    if has_accreditation_number and has_expiry:
        return 0.9
    if has_accreditation_number:
        return 0.7
    return 0.6


def effective_tier(category: str, declared_tier: int) -> int:
    """Banks are entity-confirmation only, so they never score better than tier 2.

    `max`, not a flat 2. The original `return 2 if category == "banks"` was written to
    DOWNGRADE a tier-1 bank register (a BaFin listing proves the institute is authorised, not
    that it is a good relocation banking partner) — but it also silently UPGRADED tier 3 to 2,
    which is the opposite of the intent and defeats the tier-3 rule in `validate()`.

    Measured on the first real harvest: three bank rows whose only evidence was the bank's own
    site — one of them a **Wikidata** entry — passed validation because of this. Every other
    self-declared row in the same file was correctly rejected. Fixed 2026-08-11 (AIQ-1788).
    """
    return max(2, declared_tier) if category == "banks" else declared_tier


def pairs_in_scope() -> List[Tuple[str, str]]:
    """The 10 (corridor, category) pairs this run covers."""
    return [(c, cat) for c in CORRIDORS for cat in CATEGORIES]
