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

# The two corridors in scope. Must match corridor_coverage_targets.corridor EXACTLY —
# verified 2026-08-10: 20 rows, 0 unmapped against supplier_service_categories.
CORRIDORS: Tuple[str, ...] = ("FR-DE", "FR-NO")

# The five categories with live suppliers today. rmc / dsp / healthcare_ipmi /
# language_cultural are deliberately OUT of scope for this run: zero suppliers and weaker
# public registries. They need their own task, not a weaker source here.
CATEGORIES: Tuple[str, ...] = (
    "movers",
    "housing_agencies",
    "legal_admin",
    "tax_finance",
    "banks",
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


# ── The catalogue ────────────────────────────────────────────────────────────
# Acquisition modes reflect a reconnaissance pass on 2026-08-10. Re-verify before
# assuming a source still behaves this way; registries redesign without notice, and a
# source that silently stops listing is indistinguishable from a category with no members.
SOURCES: Tuple[RegistrySource, ...] = (
    # ── movers — the highest-yield structured sources in the project ──────────
    RegistrySource(
        name="FIDI FAIM member directory",
        base_url="https://www.fidi.org/find-mover",
        tier=1,
        acquisition=Acquisition.MANUAL_EVIDENCED,
        corridors=CORRIDORS,
        categories=("movers",),
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
        acquisition=Acquisition.MANUAL_EVIDENCED,
        corridors=CORRIDORS,
        categories=("movers",),
    ),
    # ── housing_agencies ─────────────────────────────────────────────────────
    RegistrySource(
        name="Finanstilsynet — estate agency register (NO)",
        base_url="https://www.finanstilsynet.no/en/registers/",
        tier=1,
        acquisition=Acquisition.HTTP_LOOKUP,
        corridors=("FR-NO",),
        categories=("housing_agencies", "tax_finance", "banks"),
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
        base_url="https://www.rechtsanwaltsregister.org/",
        tier=1,
        acquisition=Acquisition.MANUAL_EVIDENCED,
        corridors=("FR-DE",),
        categories=("legal_admin",),
        notes="Filter to firms publishing Ausländerrecht / immigration practice areas.",
    ),
    RegistrySource(
        name="BRAV — Bundesweites Amtliches Anwaltsverzeichnis",
        base_url="https://www.rechtsanwaltsregister.org/",
        tier=1,
        acquisition=Acquisition.UNAVAILABLE,
        corridors=("FR-DE",),
        categories=("legal_admin",),
        unavailable_reason="Unreachable during recon 2026-08-10; retry before relying on it.",
    ),
    RegistrySource(
        name="Advokatforeningen + Brønnøysund register (NO)",
        base_url="https://www.advokatenhjelperdeg.no/",
        tier=1,
        acquisition=Acquisition.MANUAL_EVIDENCED,
        corridors=("FR-NO",),
        categories=("legal_admin",),
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
    # ── tax_finance ──────────────────────────────────────────────────────────
    RegistrySource(
        name="Bundessteuerberaterkammer / regional StBK (DE)",
        base_url="https://www.bstbk.de/",
        tier=1,
        acquisition=Acquisition.MANUAL_EVIDENCED,
        corridors=("FR-DE",),
        categories=("tax_finance",),
    ),
    # ── banks ────────────────────────────────────────────────────────────────
    RegistrySource(
        name="BaFin institute register (DE)",
        base_url="https://portal.mvp.bafin.de/database/InstInfo/",
        tier=1,
        acquisition=Acquisition.HTTP_LOOKUP,
        corridors=("FR-DE",),
        categories=("banks", "tax_finance"),
        notes=(
            "Confirms the legal entity and licence. Banks are not accredited in the "
            "BRAIN-3C sense, so entity confirmation is all this proves — see "
            "confidence_for()."
        ),
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
