"""[AIQ-1826] Decide which supplier accreditations may move `claimed` -> `verified`.

WHY THIS IS A PURE MODULE
-------------------------
Mirrors the `vendor_harvester.plan_pair()` / `executor.stage()` split: every decision about
what counts as a confirmation lives here and is testable with no database and no network.
The half that fetches pages and writes rows is `backend/imports/suppliers/harden.py`.

That separation matters more here than it did for the harvester. This routine EDITS rows
that already exist and that feed the vetting queue, and its whole purpose is to attach the
word "verified" to a supplier. If the rule that grants that word is entangled with HTTP and
SQL, nobody can read it and check it is honest.

WHAT "VERIFIED" IS ALLOWED TO MEAN
----------------------------------
Exactly one thing: we fetched the register entry named in `body`, at the row's own
`evidence_url`, and that page names this entity. Nothing weaker. In particular:

  * A reachable registry is not a confirmation. HTTP 200 is not evidence — a register's
    "no results" page is also 200. Only a name match on the fetched page confirms.
  * A registered COMPANY is not an accredited PROFESSIONAL. Brønnøysund proves an AS
    exists; it says nothing about bar membership. See `BLOCKED_BODIES`.
  * A failed match is not a disproof. Nothing here ever writes `status='not_found'`,
    because a per-entity page cannot establish absence — see the note above
    `ACTION_NAME_MISMATCH`. `verified` is the only status this routine writes.

SCOPE
-----
FR-NO corridor only, four categories only. The table currently holds 27 accreditations, but
12 of those are German entities whose only capabilities are `country_code='DE'` (the FR-DE
corridor), one of them a bank. The task brief says "harden the 27" and also says "FR-NO ONLY
· banks OUT"; those two instructions contradict each other, and `in_scope()` resolves it in
favour of the guardrail. The 12 are reported as skipped, never silently dropped.

DB CHECK CONSTRAINTS THIS MODULE ENCODES (verified against prod 2026-08-12)
---------------------------------------------------------------------------
    status                ∈ claimed | verified | expired | revoked | not_found
    verification_method   ∈ public_registry | supplier_document | manual_email
                            | directory_listing        (NULL allowed)
    verified              ⇒ evidence_url IS NOT NULL AND verified_at IS NOT NULL

Note `registry_lookup` — the value the brief specified — is NOT permitted by the CHECK. The
correct value for a register fetch is `public_registry`.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Optional, Sequence, Tuple

# ── Scope ────────────────────────────────────────────────────────────────────

IN_SCOPE_CATEGORIES: FrozenSet[str] = frozenset(
    {"legal_admin", "movers", "housing_agencies", "tax_finance"}
)
#: FR is here for the France-origin half (AIQ-1827). Today it matches nothing — prod has 0
#: French capabilities — so including it changes no current behaviour and a test pins that.
IN_SCOPE_COUNTRIES: FrozenSet[str] = frozenset({"NO", "FR"})

# ── DB CHECK mirrors. Keep in sync or the write fails at the constraint. ─────

STATUS_CLAIMED = "claimed"
STATUS_VERIFIED = "verified"

METHOD_PUBLIC_REGISTRY = "public_registry"
METHOD_DIRECTORY_LISTING = "directory_listing"

VALID_STATUSES: FrozenSet[str] = frozenset(
    {"claimed", "verified", "expired", "revoked", "not_found"}
)
VALID_METHODS: FrozenSet[str] = frozenset(
    {"public_registry", "supplier_document", "manual_email", "directory_listing"}
)


# ── Per-body policy ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BodyPolicy:
    """How a given accreditation body may be confirmed, if at all."""

    #: Substring that identifies the body in `supplier_accreditations.body`, casefolded.
    match: str
    #: False -> never auto-verify, whatever the fetch returns. `blocked_reason` says why.
    auto_verifiable: bool
    method: Optional[str] = None
    #: Registers that publish no per-member number. Their rows stay number-less and that is
    #: not a defect — flagging it keeps the preview honest about what the evidence covers.
    publishes_membership_number: bool = True
    blocked_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.auto_verifiable and self.method not in VALID_METHODS:
            raise ValueError(f"{self.match}: method {self.method!r} violates the DB CHECK")
        if not self.auto_verifiable and not self.blocked_reason:
            raise ValueError(f"{self.match}: a non-verifiable body must state why")


BODY_POLICIES: Tuple[BodyPolicy, ...] = (
    # Per-entity detail pages keyed by the id already stored in membership_number, e.g.
    # .../virksomhetsregisteret/detalj/?id=99004 -> "DELOITTE AS". Confirmed reachable and
    # name-bearing 2026-08-12.
    BodyPolicy(
        match="finanstilsynet",
        auto_verifiable=True,
        method=METHOD_PUBLIC_REGISTRY,
    ),
    # FIDI publishes an affiliate page per member but no public membership number, so these
    # rows verify with `membership_number IS NULL` and the preview says so.
    BodyPolicy(
        match="fidi",
        auto_verifiable=True,
        method=METHOD_PUBLIC_REGISTRY,
        publishes_membership_number=False,
    ),
    # An association roll, not a statutory register — the registry_sources catalogue is
    # explicit that EuRA "carries no licence number". directory_listing, not public_registry.
    BodyPolicy(
        match="eura",
        auto_verifiable=True,
        method=METHOD_DIRECTORY_LISTING,
        publishes_membership_number=False,
    ),
    # BLOCKED. All four rows carrying this body store a 9-digit Brønnøysund ORGANISATION
    # number in `membership_number` (914 450 133, 917 334 110, 915 363 954, 926 162 578) and
    # point `evidence_url` at brreg.no, advokatguiden.no (a commercial directory), or the
    # Advokatforening search FORM — never at a bar member record. Brønnøysund confirms the
    # company is registered; bar membership is a different claim. Verifying these under this
    # body would be a fabricated accreditation, which is the one thing the task forbids.
    BodyPolicy(
        match="advokatforening",
        auto_verifiable=False,
        blocked_reason=(
            "body claims Den Norske Advokatforening but membership_number is a Brønnøysund "
            "organisation number and evidence_url is not a bar member record — company "
            "registration does not evidence bar membership. Needs re-sourcing against the "
            "Advokatforening member register, or the body corrected to Brønnøysund."
        ),
    ),
)

#: Bodies that must never be auto-verified, by policy rather than by fetch outcome.
BLOCKED_BODIES: Tuple[str, ...] = tuple(p.match for p in BODY_POLICIES if not p.auto_verifiable)


def policy_for_body(body: str) -> Optional[BodyPolicy]:
    """The policy whose `match` appears in `body`, or None if the body is unknown.

    Unknown is deliberately not an error and deliberately not verifiable: a body nobody has
    modelled cannot have a confirmation rule, so `decide()` keeps it `claimed`.
    """
    hay = (body or "").casefold()
    for pol in BODY_POLICIES:
        if pol.match in hay:
            return pol
    return None


# ── Name normalisation ───────────────────────────────────────────────────────

_LEGAL_FORMS = (
    "as", "asa", "a/s", "sarl", "s.a.r.l", "sa", "gmbh", "co", "kg", "ag", "ab", "oy",
    "ltd", "limited", "bv", "nv", "plc", "inc",
)
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def normalise_text(value: str) -> str:
    """Casefold, strip diacritics and punctuation, collapse whitespace.

    Diacritics are folded because registers are inconsistent about them (Kløvfjell vs
    Klovfjell) while the underlying entity is the same. This is a matching aid only — it is
    never written back to the database.
    """
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _WS.sub(" ", _PUNCT.sub(" ", stripped.casefold())).strip()


def entity_key(name: str) -> str:
    """The comparable core of a supplier name.

    Drops a trailing person or branch qualifier after an em/en dash ("Humlen Advokater AS —
    Félix Olivier Helle"), a parenthetical trading name, and trailing legal forms. What is
    left is what a register's own listing is likely to print.
    """
    if not name:
        return ""
    # Parentheticals first: a trading name can itself contain a spaced dash
    # ("AGS France (SOFDI – Société Française…)"), and splitting before stripping would
    # cut inside the bracket and leave the fragment behind.
    head = re.sub(r"\([^)]*\)", " ", name)
    head = re.split(r"\s[—–-]\s", head, maxsplit=1)[0]
    tokens = normalise_text(head).split()
    while tokens and tokens[-1] in _LEGAL_FORMS:
        tokens.pop()
    return " ".join(tokens)


def page_confirms_entity(page_text: str, supplier_name: str) -> bool:
    """True when the fetched register page names this entity.

    Two candidate spellings are tried, because neither alone is sufficient:

      * the FULL normalised name, legal form included — "deloitte as". Short brand names
        collapse to a single token once the form is stripped, and a lone "deloitte" is too
        weak to accept; keeping "as" restores the second token honestly.
      * the stripped `entity_key` — "humlen advokater". Needed where the row carries a
        person or branch suffix the register does not print.

    A two-token floor applies to both: a one-token match could hit a register footer or an
    unrelated listing, and a false verification is worse than an unverified row.

    The floor bit on the first real run: Deloitte AS, KPMG AS and PricewaterhouseCoopers AS
    were all reported `not_found` against Finanstilsynet pages whose titles name them
    exactly. `not_found` is a positive claim — "the register answered and this entity is
    absent" — so a false one is worse than a missed verification, not merely equivalent.
    """
    hay = normalise_text(page_text)
    if not hay:
        return False
    for candidate in (normalise_text(supplier_name), entity_key(supplier_name)):
        if candidate and len(candidate.split()) >= 2 and candidate in hay:
            return True
    return False


# ── Inputs and outputs ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class Capability:
    service_category: str
    country_code: Optional[str]
    city_name: Optional[str] = None
    platform_vetting_status: str = "pending"


@dataclass(frozen=True)
class AccreditationRow:
    accreditation_id: str
    supplier_id: str
    supplier_name: str
    body: str
    status: str
    membership_number: Optional[str] = None
    evidence_url: Optional[str] = None
    #: Existing notes. Carried so the writer can MERGE rather than clobber — the harvest
    #: wrote real provenance here on every row.
    notes: Optional[str] = None
    capabilities: Tuple[Capability, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LookupResult:
    """Outcome of fetching an accreditation's `evidence_url`."""

    ok: bool
    http_status: Optional[int] = None
    text: str = ""
    error: Optional[str] = None


# Actions, so the report and the writer agree on vocabulary.
ACTION_VERIFY = "verify"
ACTION_KEEP_CLAIMED = "keep_claimed"
#: The register answered and the page did not carry this name. Its own bucket in the report
#: because it is a worklist item, but its STATUS stays `claimed` — see below.
ACTION_NAME_MISMATCH = "name_mismatch"
ACTION_SKIP_OUT_OF_SCOPE = "skip_out_of_scope"

# WHY THERE IS NO `not_found` OUTCOME
# -----------------------------------
# The schema offers `status='not_found'` and an earlier draft of this module used it when a
# fetched page failed to name the entity. That is an overclaim, and the first live run proved
# it: `Expat Relocation Norway` did not match its EuRA page, but the page exists and is
# titled "Expat Relocation AS" — the register lists the entity under a different legal name.
#
# We fetch a PER-ENTITY url. A non-match therefore means "this page did not confirm this
# name" — a stale link or a naming difference — and never "the register does not contain
# this entity", which could only be established by searching the register's index and
# getting zero results. Nothing here does that. So a non-match keeps `claimed` and is
# surfaced for a human instead of being written as a finding we did not make.


@dataclass(frozen=True)
class Decision:
    accreditation_id: str
    supplier_name: str
    body: str
    action: str
    status: str
    reason: str
    verification_method: Optional[str] = None
    membership_number_missing: bool = False
    existing_notes: Optional[str] = None

    @property
    def writes(self) -> bool:
        """Only a confirmation changes a row's status. Everything else is a note."""
        return self.action == ACTION_VERIFY


# ── The rules ────────────────────────────────────────────────────────────────


def in_scope(row: AccreditationRow) -> bool:
    """FR-NO corridor, four categories.

    A supplier is in scope when at least one capability is in an in-scope country AND an
    in-scope category. `banks` never qualifies, which is what keeps ING-DiBa out.
    """
    return any(
        (cap.country_code or "").upper() in IN_SCOPE_COUNTRIES
        and cap.service_category in IN_SCOPE_CATEGORIES
        for cap in row.capabilities
    )


def decide(row: AccreditationRow, lookup: Optional[LookupResult]) -> Decision:
    """Resolve one accreditation. Pure — `lookup` is the only evidence considered."""

    def _d(action: str, status: str, reason: str, **kw) -> Decision:
        return Decision(
            accreditation_id=row.accreditation_id,
            supplier_name=row.supplier_name,
            body=row.body,
            action=action,
            status=status,
            reason=reason,
            existing_notes=row.notes,
            **kw,
        )

    if not in_scope(row):
        cats = ", ".join(sorted({c.service_category for c in row.capabilities})) or "none"
        countries = ", ".join(sorted({(c.country_code or "?") for c in row.capabilities}))
        return _d(
            ACTION_SKIP_OUT_OF_SCOPE,
            row.status,
            f"outside FR-NO scope (categories: {cats}; countries: {countries})",
        )

    if row.status != STATUS_CLAIMED:
        return _d(ACTION_KEEP_CLAIMED, row.status, f"already {row.status} — left untouched")

    policy = policy_for_body(row.body)
    if policy is None:
        return _d(
            ACTION_KEEP_CLAIMED,
            STATUS_CLAIMED,
            "no confirmation rule declared for this body — add one to BODY_POLICIES "
            "rather than verifying on an unmodelled source",
        )

    if not policy.auto_verifiable:
        return _d(ACTION_KEEP_CLAIMED, STATUS_CLAIMED, policy.blocked_reason or "blocked")

    if not row.evidence_url:
        return _d(ACTION_KEEP_CLAIMED, STATUS_CLAIMED,
                  "no evidence_url to fetch — cannot confirm")

    if lookup is None:
        return _d(ACTION_KEEP_CLAIMED, STATUS_CLAIMED, "not looked up in this run")

    if not lookup.ok:
        detail = lookup.error or f"HTTP {lookup.http_status}"
        # An unreachable register is OUR failure to check, not a finding about the supplier.
        return _d(ACTION_KEEP_CLAIMED, STATUS_CLAIMED,
                  f"register unreachable ({detail}) — unchecked, not disproved")

    if not page_confirms_entity(lookup.text, row.supplier_name):
        return _d(
            ACTION_NAME_MISMATCH,
            STATUS_CLAIMED,
            "register page fetched but it does not carry this name — the link may be stale "
            "or the register may list a different legal name. Stays claimed; needs a human "
            "look. Not recorded as not_found: a per-entity page cannot prove absence.",
        )

    return _d(
        ACTION_VERIFY,
        STATUS_VERIFIED,
        f"confirmed on {policy.match} register page at evidence_url",
        verification_method=policy.method,
        membership_number_missing=(
            not row.membership_number and policy.publishes_membership_number
        ),
    )


#: Prefix for this routine's line in `notes`. Also how a re-run finds and replaces its own
#: previous line instead of stacking duplicates.
NOTE_MARKER = "[AIQ-1826]"


def merge_note(existing: Optional[str], reason: str) -> str:
    """Add this run's reason to `notes` without destroying what is already there.

    `notes` is not scratch space. The 2026-08-11 harvest wrote real provenance into it
    ("expiry coerced from bare year 2026 to 1 Jan…", "no supplier domain in the harvest…")
    on all 27 rows, and an earlier draft of this module overwrote the column outright —
    which would have silently deleted the only record of how those rows were built.

    Idempotent: a second run replaces this routine's own line rather than appending a
    second copy, so notes cannot grow without bound.
    """
    kept = [
        line for line in (existing or "").splitlines()
        if not line.startswith(NOTE_MARKER)
    ]
    base = "\n".join(kept).rstrip()
    line = f"{NOTE_MARKER} {reason}"
    return f"{base}\n{line}" if base else line


def render_report(decisions: Sequence[Decision], *, dry_run: bool) -> str:
    """Human-readable preview. This is the artifact a human approves before any write."""
    buckets: Dict[str, list] = {}
    for d in decisions:
        buckets.setdefault(d.action, []).append(d)

    mode = "DRY RUN — nothing written" if dry_run else "APPLY"
    out = [f"accreditation hardening — {mode}", ""]

    order = (
        (ACTION_VERIFY, "VERIFY"),
        (ACTION_NAME_MISMATCH, "NAME MISMATCH (stays claimed — human look)"),
        (ACTION_KEEP_CLAIMED, "KEEP claimed"),
        (ACTION_SKIP_OUT_OF_SCOPE, "SKIP (out of FR-NO scope)"),
    )
    for action, label in order:
        rows = buckets.get(action, [])
        out.append(f"{label}: {len(rows)}")
        for d in rows:
            flag = "  [no membership number in register]" if d.membership_number_missing else ""
            out.append(f"  - {d.supplier_name}  ({d.body})")
            out.append(f"      {d.reason}{flag}")
        out.append("")

    in_scope_total = sum(
        len(buckets.get(a, []))
        for a in (ACTION_VERIFY, ACTION_NAME_MISMATCH, ACTION_KEEP_CLAIMED)
    )
    out.append(
        f"in scope: {in_scope_total}   "
        f"writes: {sum(1 for d in decisions if d.writes)}   "
        f"total considered: {len(decisions)}"
    )
    return "\n".join(out)
