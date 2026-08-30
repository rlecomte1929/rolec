"""Read an Otto immigration-research JSONL file into `FactRow` objects.

Why this module exists: on 2026-08-11 the France immigration batch loaded **24 of 109 facts**
and `otto_staging.load_log` recorded the reason as *"85 facts unreachable via browser (systemic
capture ceiling on large threads)"*. Extraction was being done by scrolling Otto's chat thread,
and that method is capped. The vendor workstream had already hit the same wall and solved it:
Otto writes a *file* into the git-synced workspace, the `[audos-sync]` bot commits it, and a
repo-side reader loads it (`backend/imports/suppliers/`). This is that reader, for facts.

**Format is JSONL — one JSON object per line**, not CSV. `applies_to` is `jsonb` and
`evidence_quote` is a verbatim multi-line source quote full of commas and quote marks; pushing
those through CSV means inventing escaping rules an agent will get wrong. JSONL is also
self-delimiting, so a truncated file loses only its last record instead of corrupting from the
truncation point onward — which matters when the producer is an agent that may hit a ceiling
mid-write.

Two decisions live here rather than in the executor, because both are properties of *this file
format* and of what an immigration fact is:

**The publisher's domain decides how far a fact may be trusted — `source_name` gets no vote.**
Same reasoning as the supplier parser (`../suppliers/parsers.py:10-15`): the domain cannot lie
about who published the page. Three classes, and the middle one is the point:

    OFFICIAL       a government or statutory body      may be auto_accepted
    SEMI_OFFICIAL  a public agency without a gov TLD   forced to needs_review
    UNOFFICIAL     blog, law firm, relocation vendor   rejected outright

A blunt official-or-rejected rule was the first design and it is wrong here. The 24 rows already
in the table include 3 from `campusfrance.org` — Campus France is a French public establishment,
so the fact is worth keeping, but it is not `service-public.gouv.fr` and must not be
auto-accepted. Those 3 rows are already `needs_review`/`medium` in production, so this tiering
is not a new policy; it is the existing one, made explicit and enforced.

**A fact with no `evidence_quote` cannot be auto_accepted.** All 24 rows currently in the table
have `evidence_quote IS NULL`, which means nothing in them can be re-checked without re-reading
the source. In a compliance product one wrong fact destroys trust, so an unquotable fact is
allowed in — downgraded to `needs_review` — but never waved through.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import urlsplit

#: Keys every record must carry. Mirrors the NOT NULL columns of
#: `otto_staging.immigration_fact_candidates`, minus the ones this module derives
#: (`confidence_score`, `accuracy_tier`, `dedupe_key`, `extraction_method`).
REQUIRED_FIELDS: Tuple[str, ...] = (
    "destination_country",
    "entity_topic_key",
    "fact_key",
    "fact_text",
    "source_url",
)

#: Accepted and understood, but not required.
OPTIONAL_FIELDS: Tuple[str, ...] = (
    "entity_title", "fact_type", "applies_to", "evidence_quote", "confidence",
)

#: `fact_type` values already in production. An unknown type is not fatal — research finds
#: shapes we did not predict — but it is normalised to `other` so the column stays queryable.
KNOWN_FACT_TYPES: Tuple[str, ...] = (
    "fee", "eligibility", "document", "deadline", "step", "where_to_apply", "other",
)

#: `confidence` -> `confidence_score`, matching the values in production (high -> 0.9).
CONFIDENCE_SCORES: Dict[str, float] = {"high": 0.9, "medium": 0.6, "low": 0.3}

TIER_AUTO = "auto_accepted"
TIER_REVIEW = "needs_review"

OFFICIAL = "official"
SEMI_OFFICIAL = "semi_official"
UNOFFICIAL = "unofficial"

#: Host patterns that make a domain governmental on their own, without an allowlist entry.
#: Suffix-matched against the hostname, so `www.service-public.gouv.fr` matches `.gouv.fr`.
_OFFICIAL_SUFFIXES: Tuple[str, ...] = (
    "gouv.fr", "gov.uk", "gov.pt", "gov.pl", "gov.ie", "gov.it", "gov.gr",
    "gob.es", "governo.it", "admin.ch", "overheid.nl", "public.lu",
    "europa.eu", "bund.de", "gc.ca", "govt.nz", "gov.au", "gov",
)

#: Statutory bodies whose domain does not advertise itself as governmental. These publish the
#: rule; they are the primary source even though the TLD does not say so.
_OFFICIAL_HOSTS: Tuple[str, ...] = (
    # France
    "service-public.fr", "legifrance.gouv.fr", "urssaf.fr", "ameli.fr",
    "impots.gouv.fr", "france-visas.gouv.fr", "ofii.fr",
    # France — the two social-security bodies a mover actually deals with, neither of which
    # sits under `gouv.fr`. CLEISS is the French liaison body for international social
    # security: it publishes the coordination and totalisation rules for a move between
    # France and another state, which is the single most load-bearing source for an inbound
    # EEA corridor, and it scored UNOFFICIAL. The CAF is the family-benefits arm of the
    # Sécurité sociale and publishes its own entitlement conditions. Both publish the rule
    # rather than restating one. This is the fourth time this list has been too narrow, and
    # the failure mode is always the same: the rejects cluster by country.
    "cleiss.fr", "caf.fr",
    # Norway
    "udi.no", "skatteetaten.no", "politiet.no", "nav.no", "altinn.no", "lovdata.no",
    "helsenorge.no", "brreg.no", "folkeregisteret.no",
    # Germany
    "bamf.de", "auswaertiges-amt.de", "gesetze-im-internet.de", "bundesregierung.de",
    "make-it-in-germany.com", "arbeitsagentur.de",
    # Portugal
    "aima.gov.pt", "seg-social.pt", "portaldasfinancas.gov.pt",
    # Ireland. Immigration Service Delivery, the Department of Justice unit that operates
    # registration and issues the IRP — it publishes the rule, it does not restate one, which
    # is what separates it from citizensinformation.ie below. The `.ie` domain does not end in
    # `gov.ie`, so the suffix rule alone rejected it and took the whole first-time
    # registration entity with it: the 90-day deadline, the €300 fee, the 10-working-day card
    # delivery. This repo's own Otto card contract already names the host as statutory
    # (docs/audos/otto-batch-2026-08-13/otto-batch.json:699, otto_verify.py:56) — the
    # importer's allowlist had simply never been told.
    "irishimmigration.ie",
    # Ireland — the statutory bodies an EU/EEA free mover actually deals with. Immigration
    # Service Delivery above covers the non-EEA track; none of it applies to a free mover, who
    # instead needs a PPSN, health entitlement, a tenancy and a driving licence. Every one of
    # those is published by a body outside `gov.ie`, so the suffix rule scored them UNOFFICIAL
    # and rejected the facts outright — the same failure the Spain block below records. The HSE
    # is the health service setting out its own ordinary-residence entitlement; the RTB is the
    # statutory board that runs tenancy registration; the NDLS and its parent RSA run licence
    # exchange; welfare.ie and mywelfare.ie are the Department of Social Protection's own
    # portals, and MyWelfare is where a PPSN application is actually made. Each publishes its
    # own rule rather than restating one, which is the line this list draws.
    "hse.ie", "rtb.ie", "ndls.ie", "rsa.ie", "welfare.ie", "mywelfare.ie",
    # Ireland — municipal and transport, for city-level settle-in content. Same call as
    # `madrid.es` and `service.berlin.de` below and above: Dublin City Council runs and
    # publishes its own services rather than restating a national rule. Transport for Ireland
    # and the Leap card scheme are operated by the National Transport Authority, which sets
    # and publishes the fare and card rules it describes — the same reasoning that admits
    # `rundfunkbeitrag.de`, the body that levies the fee it explains.
    "dublincity.ie", "transportforireland.ie", "leapcard.ie", "nationaltransport.ie",
    # Denmark. Denmark uses no governmental suffix at all, so the suffix rule scored the
    # national tax authority itself as a relocation blog and rejected it.
    "skat.dk",
    # Germany. `bund.de` covers the federal portal, but the bodies that actually publish the
    # rule mostly do not sit under it: the BZSt issues the tax ID, service.berlin.de is the
    # Land of Berlin's own service catalogue for the Anmeldung, and Rundfunkbeitrag is the
    # body that levies the broadcasting fee it describes.
    "bzst.de", "service.berlin.de", "rundfunkbeitrag.de",
    # Spain. Only the `gob.es` suffix was recognised, so every statutory body that does not
    # sit under it scored UNOFFICIAL and was rejected outright — which is every Spain-side
    # fact in an ES->IE deliverable. `boe.es` is the starkest: the Boletín Oficial del Estado
    # publishes the law itself, exactly as `legifrance.gouv.fr` and `lovdata.no` do, and both
    # of those were already listed. The AEAT was *half* admitted, because
    # `agenciatributaria.gob.es` (the sede) passes on the suffix while `agenciatributaria.es`
    # does not — so a tax fact survived or died on which of the agency's own two domains the
    # researcher happened to cite. All five publish their own rule rather than restating one.
    "boe.es", "seg-social.es", "agenciatributaria.es", "policia.es", "sepe.es",
    # Spain — municipal (padrón). Same call as `service.berlin.de` above: the town hall runs
    # and publishes its own registration procedure, so it is the publisher, not a portal
    # restating someone else's rule. Neither `.es` nor `.cat` carries a governmental suffix
    # (`.cat` is a *linguistic* TLD), so both councils were scored as relocation blogs and the
    # padrón vanished from any ES-side deliverable. Named hosts only — a third city is a
    # decision, not a silent addition.
    "madrid.es", "barcelona.cat",
    # Cross-border / EU
    "eur-lex.europa.eu", "ec.europa.eu", "efta.int",
)

#: Public agencies and para-statal bodies: authoritative enough to keep, not authoritative
#: enough to auto-accept. A fact sourced here always lands in the review queue.
_SEMI_OFFICIAL_HOSTS: Tuple[str, ...] = (
    "campusfrance.org", "welcometofrance.com", "workinnorway.no",
    "newtonorway.no", "study.eu", "youreurope.europa.eu",
    # Ireland. Both are statutory bodies whose domain does not end in `.gov.ie`, so the
    # suffix rule alone read them as a relocation blog and REJECTED them outright. That
    # cost us the facts nobody else publishes plainly: emergency tax until the Revenue
    # job registration lands, RTB tenancy registration, and the non-Schengen consequence
    # of an Irish permission. Citizens Information is run by the Citizens Information
    # Board (a statutory agency under the Department of Social Protection); Revenue is
    # the tax authority itself. Semi-official, not official: both restate rules published
    # elsewhere, so a fact from here is worth keeping and belongs in the review queue.
    "citizensinformation.ie", "revenue.ie",
    # Denmark. borger.dk is the Danish state's official citizen portal, run by the Agency
    # for Digital Government — so it belongs in, not out. Semi-official for the same reason
    # as citizensinformation.ie: it is a portal that restates what SKAT, the CPR office and
    # the regions publish elsewhere, so a fact from here belongs in the review queue.
    "borger.dk",
)


class FactRowError(ValueError):
    """A record whose *shape* is unusable — bad JSON, missing key, unparseable number.

    Distinct from a record that parses fine but fails the sourcing gate: that one is a
    *rejection*, collected and reported, not an exception.
    """


@dataclass
class FactRow:
    """One validated fact, ready for `otto_staging.immigration_fact_candidates`."""

    destination_country: str
    entity_topic_key: str
    fact_key: str
    fact_text: str
    source_url: str
    batch_id: str
    entity_title: str
    fact_type: str = "other"
    applies_to: Optional[Dict[str, Any]] = None
    evidence_quote: Optional[str] = None
    confidence: str = "medium"
    confidence_score: float = 0.6
    accuracy_tier: str = TIER_REVIEW
    source_class: str = SEMI_OFFICIAL
    #: Every downgrade applied to this row, so a reviewer sees what was derived, not read.
    #: The table has no `notes` column, so these surface in the CLI and in `load_log.notes`.
    downgrades: List[str] = field(default_factory=list)

    @property
    def dedupe_key(self) -> str:
        """`FR|eu_free_movement_worker|cardFee` — the convention already in production."""
        return f"{self.destination_country}|{self.entity_topic_key}|{self.fact_key}"


def _host(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    if "//" not in raw:
        raw = "//" + raw
    return (urlsplit(raw).hostname or "").lower().lstrip(".")


def _matches(host: str, suffixes: Tuple[str, ...]) -> bool:
    return any(host == s or host.endswith("." + s) for s in suffixes)


def classify_source(source_url: str) -> str:
    """OFFICIAL / SEMI_OFFICIAL / UNOFFICIAL for an evidence URL.

    Unrecognised is UNOFFICIAL, deliberately. The safe default for a compliance fact is to
    refuse it and put it on the re-sourcing worklist, not to admit it on the chance that the
    domain is fine — an unrecognised host is exactly where a relocation blog paraphrasing a
    2019 rule would land.

        >>> classify_source("https://www.service-public.gouv.fr/particuliers/F16003")
        'official'
        >>> classify_source("https://www.campusfrance.org/en/fees")
        'semi_official'
        >>> classify_source("https://some-relocation-blog.com/moving-to-france")
        'unofficial'
    """
    host = _host(source_url)
    if not host:
        return UNOFFICIAL
    if _matches(host, _OFFICIAL_HOSTS) or _matches(host, _OFFICIAL_SUFFIXES):
        return OFFICIAL
    if _matches(host, _SEMI_OFFICIAL_HOSTS):
        return SEMI_OFFICIAL
    return UNOFFICIAL


# Single-segment paths that address a SITE rather than a rule. `classify_source` cannot see
# these because it only ever looks at the host: `https://www.urssaf.fr/accueil` is served by a
# statutory publisher and identifies nothing.
_HOMEPAGE_SEGMENTS = frozenset(
    {"accueil", "home", "index", "index.html", "index.htm", "en", "fr", "de", "no", "es", "nl"}
)

# A directory record — a contact card for an office — is not a normative page. The ws 630
# fabrication was cited to one of these.
_DIRECTORY_HOSTS = ("lannuaire.service-public.gouv.fr", "lannuaire.service-public.fr")
_DIRECTORY_SEGMENTS = frozenset({"centres-contact", "annuaire"})

#: Citation forms that are not URLs and resolve anyway. NOT REJECTED: a bare UUID. It looks like a dangling reference and is not one —
# `requirement_items.citations_json` legitimately carries three formats (raw URL,
# `source_records` UUID, `immigration_rule.*` corpus ref) and all three resolve. Checked
# 2026-08-23: all four FRANCE rows citing a raw UUID resolve to a `source_records` row with a
# real url, publisher_domain, published_date and snippet — they are the best-cited rows in the
# set, not the worst. `scripts/check_requirement_provenance.py` refuses this check for the same
# reason and says so: "A checker that demanded one format would flag 24 legitimate rows and be
# switched off within a day." Zero of the 940 distinct `source_url` values in prod are a UUID,
# so a rule here would fire on nothing while encoding a false premise for whoever copies it.
_RESOLVABLE_NON_URL_REF = re.compile(
    r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"|immigration_rule\.[\w.]+)$",
    re.I,
)


def unspecific_citation_reason(source_url: str) -> Optional[str]:
    """Why this citation cannot evidence a specific claim, or None when it can.

    A companion to `classify_source`, which answers "is the publisher official?" and stops
    there. Both questions have to be asked, because the existing checks are each blind to this
    in a different way: the publisher test passes (a homepage on a statutory domain is on a
    statutory domain), and the verbatim-quote test passes too, since navigation-menu words
    really are on the page. Measured on the NO->FR corpus 2026-08-23: three SERVED FRANCE rows
    cite a bare domain and two cite a bare UUID.

        >>> unspecific_citation_reason(
        ...     "https://www.service-public.gouv.fr/particuliers/vosdroits/F16003") is None
        True
        >>> "homepage" in unspecific_citation_reason("https://www.urssaf.fr/accueil")
        True
    """
    raw = (source_url or "").strip()
    if not raw:
        return "no source_url"
    if _RESOLVABLE_NON_URL_REF.match(raw):
        return None

    host = _host(raw)
    if not host:
        return "not a resolvable URL"

    path = urlsplit(raw if "//" in raw else "//" + raw).path or ""
    segments = [seg for seg in path.split("/") if seg]

    if _matches(host, _DIRECTORY_HOSTS) or (segments and segments[0] in _DIRECTORY_SEGMENTS):
        return "a directory contact record, not a normative page"
    if not segments:
        return "a bare domain with no path — identifies a site, not a rule"
    if len(segments) == 1 and segments[0].lower() in _HOMEPAGE_SEGMENTS:
        return "a homepage — identifies a site, not a rule"
    return None


def _humanise(topic_key: str) -> str:
    """`eu_free_movement_worker` -> `Eu free movement worker`, a last-resort entity title."""
    return re.sub(r"[_\-]+", " ", topic_key).strip().capitalize()


def grade(row: FactRow) -> FactRow:
    """Set `accuracy_tier` and `confidence_score` from the evidence, recording every downgrade.

    `auto_accepted` requires an official publisher, a quotable line of evidence, and that the
    quote has not been explicitly marked unconfirmed. Otto's own `confidence` is an input, never
    the last word: an agent calling its own finding "high" is not evidence, and every one of the
    24 rows already staged called itself high.
    """
    row.confidence_score = CONFIDENCE_SCORES.get(row.confidence, CONFIDENCE_SCORES["medium"])

    if row.source_class != OFFICIAL:
        row.downgrades.append(
            f"publisher {_host(row.source_url)!r} is not a statutory source "
            f"({row.source_class})"
        )
    unspecific = unspecific_citation_reason(row.source_url)
    if unspecific:
        row.downgrades.append(f"source_url is {unspecific}")
    if not (row.evidence_quote or "").strip():
        row.downgrades.append("no evidence_quote — the claim cannot be re-checked from the row")
    # A batch that captured a quote but never re-read it against the page says so, via
    # `quote_verbatim_confirmed`. There is no column for that flag, so it rides in
    # `applies_to`. Without this, an unchecked quote scores exactly like a checked one and a
    # row a lawyer still has to clear is badged as though the evidence were verified — which is
    # how an unreviewed claim survives review by looking already-done.
    #
    # Tested with `is False`, never falsiness: an absent key and `None` mean "not claimed", not
    # "not confirmed". Every batch before ve-ie-entry-family-2026-08-20 omits the key, and
    # re-grading those rows would invalidate reviews that have already happened.
    if (row.applies_to or {}).get("quote_verbatim_confirmed") is False:
        row.downgrades.append(
            "evidence_quote is not verbatim-confirmed — captured but never re-checked "
            "against the source page"
        )
    if row.confidence not in CONFIDENCE_SCORES:
        row.downgrades.append(f"unrecognised confidence {row.confidence!r}, scored as medium")

    row.accuracy_tier = TIER_AUTO if not row.downgrades else TIER_REVIEW
    if row.downgrades:
        # A row the evidence will not carry must not also claim high confidence.
        row.confidence_score = min(row.confidence_score, CONFIDENCE_SCORES["medium"])
    return row


def _to_row(rec: Dict[str, Any], batch_id: str, lineno: int) -> FactRow:
    missing = [k for k in REQUIRED_FIELDS if not str(rec.get(k) or "").strip()]
    if missing:
        raise FactRowError(f"missing required field(s): {', '.join(missing)}")

    applies_to = rec.get("applies_to")
    if applies_to is not None and not isinstance(applies_to, dict):
        raise FactRowError(f"applies_to must be an object, got {type(applies_to).__name__}")

    fact_type = str(rec.get("fact_type") or "other").strip().lower()
    if fact_type not in KNOWN_FACT_TYPES:
        fact_type = "other"

    row = FactRow(
        destination_country=str(rec["destination_country"]).strip().upper(),
        entity_topic_key=str(rec["entity_topic_key"]).strip(),
        fact_key=str(rec["fact_key"]).strip(),
        fact_text=str(rec["fact_text"]).strip(),
        source_url=str(rec["source_url"]).strip(),
        batch_id=batch_id,
        entity_title=str(rec.get("entity_title") or "").strip()
        or _humanise(str(rec["entity_topic_key"])),
        fact_type=fact_type,
        applies_to=applies_to,
        evidence_quote=(str(rec.get("evidence_quote") or "").strip() or None),
        confidence=str(rec.get("confidence") or "medium").strip().lower(),
    )
    row.source_class = classify_source(row.source_url)
    return grade(row)


def read_jsonl(path: Path, *, batch_id: str) -> Tuple[List[FactRow], List[str]]:
    """Parse the file into (accepted rows, rejection messages).

    A malformed line raises `FactRowError` and stops the read: a file we cannot parse is a
    delivery failure, and importing its readable half would report a partial batch as a
    complete one. A well-formed line from an unofficial publisher is a *rejection* — collected,
    reported, and left for re-sourcing, because that is a research problem, not a file problem.
    """
    rows: List[FactRow] = []
    rejections: List[str] = []
    seen: Dict[str, int] = {}

    with Path(path).open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise FactRowError(f"line {lineno}: not valid JSON — {exc}") from exc
            if not isinstance(rec, dict):
                raise FactRowError(f"line {lineno}: expected an object, got {type(rec).__name__}")
            try:
                row = _to_row(rec, batch_id, lineno)
            except FactRowError as exc:
                raise FactRowError(f"line {lineno}: {exc}") from exc

            if row.source_class == UNOFFICIAL:
                rejections.append(
                    f"line {lineno}: {row.dedupe_key} — source {_host(row.source_url)!r} "
                    "is not an official or public-agency publisher"
                )
                continue

            # Two rows claiming the same fact key would collide on the table's UNIQUE
            # (dedupe_key). Catch it here, naming both lines, rather than as an IntegrityError
            # that names neither.
            if row.dedupe_key in seen:
                rejections.append(
                    f"line {lineno}: {row.dedupe_key} duplicates line {seen[row.dedupe_key]} "
                    "in this same file"
                )
                continue
            seen[row.dedupe_key] = lineno
            rows.append(row)

    return rows, rejections
