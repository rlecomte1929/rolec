"""
[AIQ-1788] Stage accreditation-backed supplier candidates for FR-DE / FR-NO.

WRITE PATH — the whole safety model in one line:
    vendor_curation_runs -> vendor_candidates    (this module writes here, only here)
    suppliers, supplier_service_capabilities, supplier_accreditations   (READ ONLY)

Promotion into the live directory is human-gated and deliberately not implemented here. A
registry listing proves membership, not fitness; a staged candidate is a lead, not a
vetted supplier, and the gap between those two is the entire point of the staging table.

Baselines verified against prod (nsvefcvpvwwwhuqyuqmp) on 2026-08-10 before writing:
    suppliers = 67, supplier_accreditations = 0, vendor_candidates = 0,
    corridor_coverage_targets = 20 with 0 unmapped against supplier_service_categories.

`corridor_coverage_targets.current_verified_count` is NOT touched. That counter reflects
promoted suppliers; moving it here would overstate coverage on the strength of leads.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit

from sqlalchemy import text

from .registry_sources import (
    Acquisition,
    RegistrySource,
    confidence_for,
    effective_tier,
    ingestable_sources,
    pairs_in_scope,
    unavailable_reasons,
)

log = logging.getLogger(__name__)

#: DB CHECK: status = ANY('pending','approved','rejected','duplicate','needs_reverification')
STATUS_PENDING = "pending"
STATUS_DUPLICATE = "duplicate"

#: DB CHECK: vendor_curation_runs.status = ANY('queued','searching','staged','reviewed','completed','failed')
RUN_SEARCHING = "searching"
RUN_STAGED = "staged"
RUN_FAILED = "failed"

# Multi-part public suffixes we actually meet in these corridors. A full PSL is overkill
# here and would add a dependency; these are the ones that would otherwise mis-normalise.
_COMPOUND_SUFFIXES = ("co.uk", "com.de", "org.uk", "co.no")


def normalise_domain(url: Optional[str]) -> Optional[str]:
    """Registrable domain: lowercased, scheme / 'www.' / path / port / credentials stripped.

    This is the dedupe primitive, so its edge cases are the ones that decide whether a
    supplier we already have gets staged again under a slightly different URL.

    Deliberately handles input that is not really a URL — `suppliers.website` in prod
    contains bare hosts AND hosts with paths (e.g. 'agsmovers.com/branches/movers-europe/
    norway/norway/'), so a naive urlsplit on a scheme-less value puts the whole thing in
    `path` and returns nothing. Verified against the live column 2026-08-10.

        >>> normalise_domain("https://WWW.Example.com/a/b?q=1")
        'example.com'
        >>> normalise_domain("agsmovers.com/branches/norway/")
        'agsmovers.com'
        >>> normalise_domain("sub.example.co.uk")
        'example.co.uk'
    """
    if not url or not url.strip():
        return None
    raw = url.strip()
    if "//" not in raw:
        raw = "//" + raw  # let urlsplit treat a bare host as a host, not a path
    host = (urlsplit(raw).hostname or "").lower().strip(".")
    if not host:
        return None
    for suffix in _COMPOUND_SUFFIXES:
        if host.endswith("." + suffix):
            parts = host.split(".")
            return ".".join(parts[-(suffix.count(".") + 2):])
    parts = [p for p in host.split(".") if p]
    if len(parts) <= 2:
        return ".".join(parts) or None
    return ".".join(parts[-2:])


#: Legal-form suffixes stripped before name matching, so "Deloitte AS" and "Deloitte" collide.
#: Deliberately short — over-stripping merges genuinely different companies, which is the
#: worse error of the two.
_LEGAL_FORMS = (
    "gmbh co kg", "gmbh", "ag", "se", "kg", "ohg", "ug", "mbh", "partg", "partgmbb",
    "as", "asa", "ans", "da", "nuf", "sarl", "sa", "sas", "eurl", "scp", "snc",
    "ltd", "limited", "llp", "plc", "bv", "nv",
)


def _name_key(name: Optional[str]) -> Optional[str]:
    """Lowercased alphanumeric name with legal form, asides and punctuation removed.

    Only used as a dedupe fallback when there is no domain. Accent-folded so
    'Déménagement' and 'Demenagement' agree.

    Parenthetical asides are dropped, which is what makes
    'AGS France (SOFDI – Société Française de Déménagement International)' and
    'AGS France (SOFDI)' — the same FIDI affiliate written two ways in one harvest — resolve
    to one supplier instead of two.

    The consequence is deliberate: 'Crown Relocations (Norway)' also collapses onto 'Crown
    Relocations'. That matches the data model rather than fighting it — a supplier holds many
    per-country capabilities, so one Crown with a Norway capability is more correct than two
    Crown rows. Nothing merges silently; every match is named in the promotion summary.

    Em-dash and comma suffixes are NOT stripped, so 'AGS Global Solutions GmbH — Berlin' and
    '— Koblenz' stay distinct. Those are genuinely different branches.
    """
    if not name:
        return None
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = re.sub(r"\([^)]*\)", " ", folded)          # drop parenthetical asides
    words = re.sub(r"[^a-z0-9]+", " ", folded.lower()).split()
    while words:
        for n in (3, 2, 1):                       # longest legal form first: "gmbh co kg"
            if len(words) > n and " ".join(words[-n:]) in _LEGAL_FORMS:
                del words[-n:]
                break
        else:
            break
    return "".join(words) or None


@dataclass
class Candidate:
    """One harvested row, before it becomes a vendor_candidates insert."""

    name: str
    website_url: str
    corridor: str
    service_category: str
    source: RegistrySource
    accreditation_body: Optional[str] = None
    accreditation_number: Optional[str] = None
    accreditation_expiry: Optional[str] = None  # ISO date
    source_url: Optional[str] = None            # the exact evidence page
    legal_name: Optional[str] = None
    country_code: Optional[str] = None
    city: Optional[str] = None
    email: Optional[str] = None                 # company-level only (info@/contact@)
    phone: Optional[str] = None
    vat_number: Optional[str] = None
    notes: Optional[str] = None

    @property
    def dedupe_key(self) -> Optional[str]:
        """Registrable domain where we have one; a namespaced name key where we do not.

        Domain is the strong key and stays the default. But a registry harvest often yields
        no supplier domain at all — the evidence URL points at the *register*, not the
        company. All 38 rows of the first real harvest (Card C) came in that way, and a
        domain-only key rejected every one of them.

        The fallback is namespaced (`name:…`) so it can never collide with a domain key, and
        it is deliberately weaker: it will not notice that we already hold this company under
        a domain. That gap is handled downstream — the review UI must surface near-name
        matches before anyone approves a candidate.
        """
        domain = normalise_domain(self.website_url)
        if domain:
            return domain
        slug = _name_key(self.name)
        return f"name:{slug}@{self.corridor.strip().lower()}" if slug else None


@dataclass
class PairResult:
    corridor: str
    service_category: str
    run_id: Optional[str] = None
    staged: int = 0
    suppressed_duplicates: int = 0
    sources_searched: List[str] = field(default_factory=list)
    unavailable: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None


class HarvestRejected(ValueError):
    """A candidate that must not reach the database."""


def validate(cand: Candidate) -> None:
    """Reject anything the DB or the task's constraints forbid — before the insert.

    Failing here rather than at the DB gives a message naming the rule, and keeps a bad
    row from aborting a transaction that is staging good ones.
    """
    if not cand.name or not cand.name.strip():
        raise HarvestRejected("name is required (NOT NULL)")
    if not cand.source_url:
        raise HarvestRejected(
            f"{cand.name}: source_url is required — a candidate with no evidence URL "
            "cannot be spot-checked, which is the only thing making it better than a scrape"
        )
    tier = effective_tier(cand.service_category, cand.source.tier)
    if tier not in (1, 2):
        raise HarvestRejected(
            f"{cand.name}: source_tier {tier} — tier 3 (the provider's own site) is never "
            "sufficient evidence on its own"
        )
    if cand.source.entry_url_pattern and not re.search(
        cand.source.entry_url_pattern, cand.source_url
    ):
        raise HarvestRejected(
            f"{cand.name}: {cand.source_url} is on {cand.source.name}'s domain but is not an "
            "entry for one entity — a search form or landing page evidences nobody. "
            "Re-source to the record page for this company."
        )
    if cand.source.acquisition is Acquisition.UNAVAILABLE:
        raise HarvestRejected(
            f"{cand.name}: source {cand.source.name} is marked UNAVAILABLE "
            f"({cand.source.unavailable_reason}) — do not route around it"
        )
    if not cand.dedupe_key:
        raise HarvestRejected(
            f"{cand.name}: no dedupe key — website_url yields no domain and the name "
            "reduces to nothing after stripping punctuation and legal form"
        )
    # GDPR: company-level contacts only. A named-individual address is a personal-data
    # collection we have no basis for at harvest time.
    #
    # The prefix set is role-based inboxes only — never a personal name. It was widened
    # 2026-08-30 after a Madrid->Dublin mover batch: 6 of 10 firms published a real company
    # inbox, but 5 used sales@/enquiries@/hq@ and the old list (info|contact|hello|office...)
    # rejected them. Discarding valid B2B addresses is a measured root cause of the
    # "115 of 122 suppliers uncontactable" problem — the moving and relocation trade lives on
    # sales@ and enquiries@, not info@. Spanish/multilingual role inboxes are included because
    # the corridors are cross-border (ventas@, comercial@, contacto@). Still no first names.
    if cand.email and not re.match(
        r"^(info|contact|contacto|kontakt|post|hello|hola|office|mail|firmapost|sekretariat"
        r"|sales|ventas|comercial|enquiries|enquiry|hq|moving|movers|move|removals"
        r"|relocation|relocations|customerservice|customercare|support|help|helpdesk"
        r"|bookings|booking|quote|quotes|admin|reception|atencion)@",
        cand.email.strip().lower(),
    ):
        raise HarvestRejected(
            f"{cand.name}: {cand.email!r} looks like a named individual — harvest "
            "company-level contacts only (GDPR)"
        )


#: Also matches the name-fallback key produced by `Candidate.dedupe_key` when a supplier row
#: has no website. Kept in SQL so one query covers both key spaces.
_SQL_SUPPLIER_WEBSITES = text(
    "SELECT website FROM suppliers WHERE website IS NOT NULL AND website <> ''"
)
#: BOTH names. `suppliers.legal_name` is where the registered entity lives, and a harvest
#: sources from a register so it reports the LEGAL name — "Expat Relocation Norway" carries
#: legal_name "Expat Relocation AS", which is character-for-character what the harvest found.
#: Matching only on `name` re-imports the company we already have.
_SQL_SUPPLIER_NAMES = text(
    "SELECT name, legal_name FROM suppliers WHERE name IS NOT NULL"
)
_SQL_CANDIDATE_KEYS = text(
    "SELECT dedupe_key FROM vendor_candidates WHERE dedupe_key IS NOT NULL"
)


def existing_dedupe_keys(conn: Any, *, corridor: Optional[str] = None) -> set:
    """Every key already known, from BOTH the live directory and prior stagings.

    Checking only vendor_candidates would re-stage suppliers we already have; checking
    only suppliers would re-stage within a single run.

    Takes a SQLAlchemy `Connection` (or `Session`) — `text()` is mandatory on SQLAlchemy 2,
    where a bare string raises `ObjectNotExecutableError`. This function had no test and no
    caller when it was written, so that never surfaced.

    `corridor` mirrors `Candidate.dedupe_key`'s name fallback: a supplier with no website is
    keyed by name, and the name key is corridor-scoped. Pass the corridor you are staging so
    those keys line up; omit it and only domain keys are compared.
    """
    keys: set = set()

    for (website,) in conn.execute(_SQL_SUPPLIER_WEBSITES):
        k = normalise_domain(website)
        if k:
            keys.add(k)

    if corridor:
        for name, legal_name in conn.execute(_SQL_SUPPLIER_NAMES):
            for candidate_name in (name, legal_name):
                slug = _name_key(candidate_name)
                if slug:
                    keys.add(f"name:{slug}@{corridor.strip().lower()}")

    for (key,) in conn.execute(_SQL_CANDIDATE_KEYS):
        if key:
            keys.add(key)

    return keys


def classify(cand: Candidate, known_keys: set) -> str:
    """pending, or duplicate when the domain is already known.

    Duplicates are INSERTED with status='duplicate' rather than dropped: a silently
    skipped row is invisible, and the run report has to be able to show what was
    suppressed and why. It also keeps the re-run idempotent — the second run recognises
    its own first-run rows.
    """
    return STATUS_DUPLICATE if cand.dedupe_key in known_keys else STATUS_PENDING


def to_insert_params(cand: Candidate, run_id: str, status: str) -> Dict[str, Any]:
    """Map a Candidate onto the vendor_candidates columns verified in prod."""
    tier = effective_tier(cand.service_category, cand.source.tier)
    return {
        "run_id": run_id,
        "name": cand.name.strip(),
        "legal_name": cand.legal_name,
        "website_url": cand.website_url,
        "email": cand.email,
        "phone": cand.phone,
        "city": cand.city,
        "country_code": cand.country_code,
        "vat_number": cand.vat_number,
        "corridor": cand.corridor,
        "service_category": cand.service_category,
        "source_url": cand.source_url,
        "source_name": cand.source.name,
        "source_tier": tier,
        "confidence_score": confidence_for(
            tier,
            bool(cand.accreditation_number),
            bool(cand.accreditation_expiry),
            cand.service_category,
        ),
        "accreditation_body": cand.accreditation_body,
        "accreditation_number": cand.accreditation_number,
        "accreditation_expiry": cand.accreditation_expiry,
        "bar_registered": cand.service_category == "legal_admin" or None,
        "dedupe_key": cand.dedupe_key,
        "status": status,
        "notes": cand.notes,
    }


def plan_pair(
    corridor: str,
    service_category: str,
    candidates: Sequence[Candidate],
    known_keys: set,
) -> Tuple[List[Dict[str, Any]], PairResult, List[str]]:
    """Pure planning step: validate, classify and shape rows without touching the DB.

    Separated from execution so the whole decision surface — which rows stage, which are
    duplicates, which are rejected and why — is unit-testable with no database at all.
    Returns (rows_without_run_id, result, rejections).
    """
    result = PairResult(
        corridor=corridor,
        service_category=service_category,
        sources_searched=[s.name for s in ingestable_sources(corridor, service_category)],
        unavailable=unavailable_reasons(corridor, service_category),
    )
    rows: List[Dict[str, Any]] = []
    rejections: List[str] = []
    seen_this_pair = set(known_keys)

    for cand in candidates:
        try:
            validate(cand)
        except HarvestRejected as exc:
            rejections.append(str(exc))
            continue
        status = classify(cand, seen_this_pair)
        if status == STATUS_PENDING:
            result.staged += 1
            seen_this_pair.add(cand.dedupe_key)
        else:
            result.suppressed_duplicates += 1
        rows.append(to_insert_params(cand, run_id="", status=status))

    return rows, result, rejections


def render_report(results: Sequence[PairResult]) -> str:
    """The markdown run report (Expected Output #4).

    States every in-scope pair including the empty ones — "0 candidates, IVD is
    login-gated" is the actionable sentence, and a report that omits zero rows silently
    turns a blocked registry into an unexplained gap.
    """
    total_staged = sum(r.staged for r in results)
    total_dupes = sum(r.suppressed_duplicates for r in results)
    empty = [r for r in results if r.staged == 0]

    lines = [
        "# Vendor harvest run report",
        "",
        f"**Staged (pending):** {total_staged} · **Suppressed as duplicate:** {total_dupes} "
        f"· **Pairs processed:** {len(results)}",
        "",
        "| Corridor | Category | Staged | Dupes | Sources searched |",
        "|---|---|---|---|---|",
    ]
    for r in sorted(results, key=lambda x: (x.corridor, x.service_category)):
        srcs = ", ".join(r.sources_searched) or "—"
        lines.append(
            f"| {r.corridor} | {r.service_category} | {r.staged} | "
            f"{r.suppressed_duplicates} | {srcs} |"
        )

    lines += ["", "## Pairs still at zero", ""]
    if not empty:
        lines.append("None — every in-scope pair staged at least one candidate.")
    for r in empty:
        lines.append(f"- **{r.corridor} / {r.service_category}** — nothing staged.")
        for name, reason in r.unavailable.items():
            lines.append(f"  - `{name}` unavailable: {reason}")
        if not r.unavailable:
            lines.append("  - No registry marked unavailable; the sources returned nothing usable.")

    # A pair that staged SOMETHING can still have had a registry blocked, and that used to go
    # unsaid: the loop above only visits pairs at zero. FR-DE/legal_admin stages one row, so
    # the RAK being unlinkable would have been invisible — a partial success reads as a full
    # one. Report every blocked registry, then say which pairs those pairs still produced.
    partial = [r for r in results if r.unavailable and r.staged > 0]
    if partial:
        lines += ["", "## Pairs that staged rows but still had a registry blocked", ""]
        for r in sorted(partial, key=lambda x: (x.corridor, x.service_category)):
            lines.append(
                f"- **{r.corridor} / {r.service_category}** — {r.staged} staged, "
                "but not from every registry:"
            )
            for name, reason in r.unavailable.items():
                lines.append(f"  - `{name}` unavailable: {reason}")

    lines += [
        "",
        "## Not done here, on purpose",
        "",
        "- Nothing was written to `suppliers`, `supplier_service_capabilities` or "
        "`supplier_accreditations`. Promotion is human-gated.",
        "- `corridor_coverage_targets.current_verified_count` is unchanged — it counts "
        "promoted suppliers, and moving it on staged leads would overstate coverage.",
    ]
    return "\n".join(lines)
