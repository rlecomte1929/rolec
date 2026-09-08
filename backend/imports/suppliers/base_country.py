"""[Stage 9 · Phase 1] Decide where each supplier is BASED, and record how we know.

Addendum A §S2 makes eligibility `vendor.based_in ∈ catchment.all`, and nothing in the schema
could answer it: `suppliers.incorporation_country` was 0 of 116, and
`supplier_service_capabilities.country_code` is the country SERVED, not the base — AGS France
and Grospiron are French firms whose rows read `DE` and `NO`.

TWO TIERS OF EVIDENCE, NEVER CONFLATED
--------------------------------------
Measured 2026-08-13 across 116 suppliers: 50 have a registry that states a country, 59 have
only a catalog listing, 7 have nothing.

A catalog listing is a *proxy* — it says where a directory placed the vendor, not where a
register says it is incorporated. Treating the two as the same claim is precisely the defect
found in the Den Norske Advokatforening rows, where a Brønnøysund organisation number sat under
a bar's name and looked like a confirmation. So every write records which tier it used in
`suppliers.entity_verified_source`, and Phase 2 gets to decide whether proxy-grade countries are
strong enough for a hard eligibility filter.

Registry rules always beat the proxy. Where nothing evidences a country the column stays NULL,
and `vendor_catchment.has_eligible_vendors` treats NULL as NOT eligible — a guessed base country
is the same class of error as a fabricated accreditation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

#: `entity_verified_source` values. The `registry:` prefix is the tier marker — a consumer that
#: wants registry-grade evidence only can filter on it without knowing every register's name.
SRC_FIDI = "registry:fidi"
SRC_SIRENE = "registry:insee_sirene"
SRC_FINANSTILSYNET = "registry:finanstilsynet"
SRC_BRONNOYSUND = "registry:bronnoysund"
SRC_DE_CHAMBER = "registry:de_chamber"
SRC_GB_REGISTER = "registry:gb_register"
SRC_CATALOG = "catalog_listing"   # ⚠ proxy, not a register

REGISTRY_PREFIX = "registry:"


@dataclass(frozen=True)
class SupplierEvidence:
    """Everything known about one supplier that could imply a base country."""

    supplier_id: str
    name: str
    #: (body, evidence_url) for each accreditation the supplier holds.
    accreditations: Sequence[tuple] = ()
    #: `service_catalog_items.country` reached via `supplier_id`, if any.
    catalog_country: Optional[str] = None
    #: Body text of the FIDI affiliate page, when the caller fetched it.
    fidi_page_text: Optional[str] = None
    #: membership_number on the SIRENE / Advokatforening rows.
    membership_numbers: Sequence[str] = ()


@dataclass(frozen=True)
class Resolution:
    supplier_id: str
    name: str
    country: Optional[str]
    source: Optional[str]
    legal_registration_number: Optional[str] = None
    reason: str = ""

    @property
    def is_registry_grade(self) -> bool:
        return bool(self.source and self.source.startswith(REGISTRY_PREFIX))

    @property
    def writes(self) -> bool:
        return self.country is not None


#: Country names as the FIDI affiliate pages print them in the postal address.
_FIDI_COUNTRY_NAMES: Dict[str, str] = {
    "FR": "France", "DE": "Germany", "NO": "Norway", "SE": "Sweden", "DK": "Denmark",
    "NL": "Netherlands", "BE": "Belgium", "ES": "Spain", "IT": "Italy", "CH": "Switzerland",
    "AT": "Austria", "PT": "Portugal", "PL": "Poland", "IE": "Ireland",
    "GB": "United Kingdom", "SG": "Singapore",
}

_TAG = re.compile(r"<[^>]+>")
_SCRIPTISH = re.compile(r"<(script|style).*?</\1>", re.S | re.I)


def _strip_markup(value: str) -> str:
    """HTML -> flat text. Idempotent, so passing already-clean text is safe."""
    if "<" not in value:
        return re.sub(r"\s+", " ", value)
    return re.sub(r"\s+", " ", _TAG.sub(" ", _SCRIPTISH.sub(" ", value)))


_SIREN = re.compile(r"^\s*(\d{9})\s*$")
#: Brønnøysund organisation numbers are 9 digits, conventionally printed "917 334 110".
_ORGNR = re.compile(r"^\s*(\d{3})\s?(\d{3})\s?(\d{3})\s*$")


#: The affiliate's postal address, which the page renders as
#: "address 6, RUE RENE RAZEL SACLAY France". Anchoring on it is what separates the affiliate's
#: own country from the chrome: every FIDI page also says "Belgium" because FIDI is
#: headquartered in Brussels, so a whole-page scan finds two countries on EVERY page and an
#: "exactly one" rule then resolves NOTHING. That is not hypothetical — it returned 0 of 21 on
#: the first live run and silently sent every FIDI supplier to the NULL bucket.
_ADDRESS_WINDOW = 200


def _country_from_fidi_page(text_body: str) -> Optional[str]:
    """The ISO2 named in the affiliate's own address block.

    Returns None when the window names no country or more than one — a wrong base country is
    worse than a NULL one.
    """
    if not text_body:
        return None
    # Normalise here rather than trusting the caller. The first live run passed raw HTML, so
    # `address` matched a markup attribute long before the postal block and the window was
    # tags — FIDI resolved 3 of 21 instead of 21 of 21. A pure function that silently depends
    # on pre-cleaned input is a trap for the next caller.
    text_body = _strip_markup(text_body)
    anchor = re.search(r"\baddress\b", text_body, re.I)
    if not anchor:
        return None
    window = text_body[anchor.end(): anchor.end() + _ADDRESS_WINDOW]
    hits = [
        iso for iso, name in _FIDI_COUNTRY_NAMES.items()
        if re.search(rf"\b{re.escape(name)}\b", window, re.I)
    ]
    return hits[0] if len(hits) == 1 else None


def _body_matches(accreditations: Sequence[tuple], needle: str) -> Optional[tuple]:
    for row in accreditations:
        body = (row[0] or "") if row else ""
        if needle.lower() in body.lower():
            return row
    return None


def resolve(ev: SupplierEvidence) -> Resolution:
    """Decide one supplier's base country. Pure — the caller does the fetching.

    Order matters: a register beats a directory listing, always.
    """
    def _r(country, source, reason, legal=None) -> Resolution:
        return Resolution(ev.supplier_id, ev.name, country, source, legal, reason)

    numbers = [n for n in (ev.membership_numbers or []) if n]

    # 1 — FIDI: the affiliate page prints a postal address.
    if _body_matches(ev.accreditations, "FIDI"):
        iso = _country_from_fidi_page(ev.fidi_page_text or "")
        if iso:
            return _r(iso, SRC_FIDI, "FIDI affiliate page address names exactly one country")
        # Fall through deliberately — an unfetched or ambiguous page is not evidence, but the
        # supplier may still have a weaker source below.

    # 2 — INSEE SIRENE is a French register; membership_number is the SIREN.
    if _body_matches(ev.accreditations, "INSEE SIRENE"):
        siren = next((m.group(1) for m in (_SIREN.match(n) for n in numbers) if m), None)
        return _r("FR", SRC_SIRENE, "registered in the French SIRENE register", siren)

    # 3 — Finanstilsynet is the Norwegian FSA.
    if _body_matches(ev.accreditations, "Finanstilsynet"):
        return _r("NO", SRC_FINANSTILSYNET, "listed in the Norwegian FSA register")

    # 4 — the Advokatforening rows carry a Brønnøysund organisation number. That number
    #     evidences a Norwegian COMPANY registration, which is a base country — it is only bar
    #     membership it cannot evidence. See accreditation_hardening.BODY_POLICIES.
    if _body_matches(ev.accreditations, "Advokatforening"):
        org = next((("".join(m.groups())) for m in (_ORGNR.match(n) for n in numbers) if m), None)
        return _r("NO", SRC_BRONNOYSUND,
                  "Brønnøysund organisation number evidences Norwegian registration "
                  "(company only — not bar membership)", org)

    # 5 — German chambers, BaFin, and the tax/property registers.
    for needle in ("BaFin", "Rechtsanwaltskammer", "RAK", "Steuerberaterkammer", "IVD"):
        if _body_matches(ev.accreditations, needle):
            return _r("DE", SRC_DE_CHAMBER, f"listed by {needle}, a German register")

    # 5b — UK statutory registers and regulated professional bodies. Movers already resolve via
    #      FIDI above; these cover legal / financial / accounting / property, which have no FIDI
    #      page. The specific body is named in the reason, one source tags the tier (as with DE).
    for needle in ("Solicitors Regulation Authority", "SRA", "Financial Conduct Authority", "FCA",
                   "ICAEW", "British Association of Removers", "Propertymark", "NAEA",
                   "Royal Institution of Chartered Surveyors", "RICS"):
        if _body_matches(ev.accreditations, needle):
            return _r("GB", SRC_GB_REGISTER, f"listed by {needle}, a UK register")

    # 6 — PROXY. A directory placed them here; no register says so.
    if ev.catalog_country:
        return _r(ev.catalog_country.strip().upper()[:2], SRC_CATALOG,
                  "catalog listing only — a directory's placement, NOT a register")

    # 7 — nothing.
    return _r(None, None, "no evidence of a base country; left NULL (not eligible)")


def summarise(resolutions: Sequence[Resolution], *, dry_run: bool) -> str:
    """The tier split. Reporting only the total would overstate what is known."""
    registry = [r for r in resolutions if r.is_registry_grade]
    proxy = [r for r in resolutions if r.source == SRC_CATALOG]
    unknown = [r for r in resolutions if not r.writes]

    by_source: Dict[str, int] = {}
    for r in resolutions:
        if r.source:
            by_source[r.source] = by_source.get(r.source, 0) + 1

    out = [
        f"supplier base country — {'DRY RUN — nothing written' if dry_run else 'APPLY'}",
        "",
        f"  registry-grade : {len(registry):>3}",
    ]
    for src in sorted(by_source):
        if src.startswith(REGISTRY_PREFIX):
            out.append(f"      {src:<28} {by_source[src]}")
    out += [
        f"  proxy (catalog): {len(proxy):>3}   ⚠ a directory's placement, not a register",
        f"  left NULL      : {len(unknown):>3}   (treated as NOT eligible downstream)",
        "",
        f"  total considered: {len(resolutions)}   would write: "
        f"{sum(1 for r in resolutions if r.writes)}",
    ]
    if unknown:
        out.append("")
        out.append("  no evidence:")
        for r in unknown[:15]:
            out.append(f"    - {r.name}")
    return "\n".join(out)
