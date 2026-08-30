#!/usr/bin/env python3
"""Corridor Verifier Service, P1 — gate a corridor batch before it becomes data.

WHAT THIS IS FOR. A research batch arrives as NDJSON and is, at that moment, a set of
claims. This runs V0-V3 over it and decides which claims are allowed to become rows:

    V0  ingest / normalise   parse, repair source_url, stamp fetched_at, upsert candidates
    V1  schema / enum gate   required fields, LIVE vocabularies, uid uniqueness
    V2  source gate          https, resolves, published by a body allowed to publish it
    V3  evidence grounding   the quote is actually on the page it cites

Facts that clear V1-V3 land in `public.requirement_entities` / `public.requirement_facts`
at `status='pending'`. Everything else goes to a re-sourcing worklist.

**DRY RUN IS THE DEFAULT.** `--apply` writes. This mirrors `scripts/import_otto_facts.py`
deliberately: same muscle memory, same blast radius.

THREE THINGS THIS DELIBERATELY DOES NOT DO
------------------------------------------
**It never writes `verified`.** The machine's ceiling is `representative`. On
`requirement_facts` that is `status='pending'` — the table has no `verification_status`
column at all (measured 2026-08-30; `verification_status` and `review_status` live on
`requirement_items`). Nothing here is served: the publication gate is
`crud.list_requirements` filtering `review_status == 'approved'` on `requirement_items`,
which this script never touches.

**It does not fuzzy-match.** The P1 brief asks for `rapidfuzz` above a threshold. That
would silently redefine what `evidence_verified = true` already means for the 357 rows
holding it today, which is *exact substring after normalisation* (`fact_evidence.py`).
A looser rule under the same column makes those 357 unauditable. If fuzzy matching is
wanted it needs its own verdict, not a threshold slipped under this one.

**It makes no LLM call.** The brief allows one bounded "is this quote supported?" call
when there is no literal match. Omitted here: `check_evidence` already separates
TRANSLATED (a match was impossible by construction) from UNVERIFIED (same language,
quote absent), so the case an LLM would adjudicate is already labelled — and an
unreviewed model judgement is exactly the kind of provenance this service exists to
refuse. UNVERIFIED goes to a human via the worklist.

WHAT IT REUSES, RATHER THAN REBUILDS
------------------------------------
  parsers.classify_source()          OFFICIAL / SEMI_OFFICIAL / UNOFFICIAL (V2)
  fact_evidence.check_evidence()     the quote-in-source verdict (V3)
  backfill_fact_evidence.fetch_and_parse()  multi-UA + robots + JS-shell-aware fetch

Usage:
    python scripts/verify_ledger.py backend/imports/otto/fixtures/us_ec        # dry run
    python scripts/verify_ledger.py <dir> --apply                              # write
    python scripts/verify_ledger.py <dir> --apply --promote                    # + importer
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.app.services.fact_evidence import (  # noqa: E402
    TRANSLATED,
    VERIFIED,
    check_evidence,
)
from backend.imports.otto.parsers import (  # noqa: E402
    OFFICIAL,
    SEMI_OFFICIAL,
    UNOFFICIAL,
    classify_source,
)

log = logging.getLogger("verify_ledger")

# ── live vocabularies ────────────────────────────────────────────────────────
# Read off the production CHECK constraints on 2026-08-30, NOT guessed. A value outside
# these is refused rather than defaulted, matching how mappings.py returns Unmapped: a
# batch that invents a vocabulary is a batch to send back, not one to coerce.
#   requirement_entities_domain_area_check
DOMAIN_AREAS = frozenset({
    "immigration", "registration", "tax", "social_security", "healthcare", "housing",
    "other", "vehicle", "vehicle_import", "domestic_move", "financial",
    "employer_compliance", "pet",
})
#   requirement_facts_fact_type_check
FACT_TYPES = frozenset({
    "eligibility", "document", "step", "deadline", "fee", "where_to_apply", "account",
    "other",
})
#   requirement_facts_confidence_check
CONFIDENCES = frozenset({"low", "medium", "high"})

#: The only status this script ever writes. `approved` is a human act.
STATUS_PENDING = "pending"

#: V2 authority rank, derived from the source class rather than a hand-kept host list.
#: parsers.classify_source() already encodes which statutory bodies publish on a non-gov
#: TLD — knowledge that cost three separate incidents to accumulate (irishimmigration.ie,
#: the citizensinformation.ie/revenue.ie pair, and the DK/DE set that silently rejected 9
#: of B3's 20 facts). A second allowlist here would drift from it.
AUTHORITY_RANK: Dict[str, int] = {OFFICIAL: 1, SEMI_OFFICIAL: 2, UNOFFICIAL: 3}
MIN_ACCEPTABLE_RANK = 2  # UNOFFICIAL (3) never lands.

VERDICT_PASS = "pass"
VERDICT_FLAG = "flag"
VERDICT_REJECT = "reject"

#: `requirement_facts.fact_type` -> `requirement_fact_candidates.requirement_type`.
#:
#: The two tables do not share a vocabulary, and the candidates CHECK is the narrower of
#: the two: it admits document|fee|timeline|eligibility|other, so `deadline`, `step`,
#: `where_to_apply` and `account` — all legal on requirement_facts — violate it outright.
#: Staging without this map raises 23514 on any batch containing a step or a deadline.
#:
#: The mapping is LOSSY and deliberately one-way: `step`, `where_to_apply` and `account`
#: all collapse to `other`, so the candidates row cannot be read back as the authority on
#: what a fact is. requirement_facts keeps the real type; this is a staging shadow.
FACT_TYPE_TO_REQUIREMENT_TYPE: Dict[str, str] = {
    "document": "document",
    "fee": "fee",
    "eligibility": "eligibility",
    "deadline": "timeline",
    "step": "other",
    "where_to_apply": "other",
    "account": "other",
    "other": "other",
}

#: `confidence` -> `confidence_score`. The candidates CHECK is `> 0 AND <= 1`, so there is
#: no zero option: an unknown confidence is `low`, not absent.
CONFIDENCE_TO_SCORE: Dict[str, float] = {"high": 0.9, "medium": 0.6, "low": 0.3}

#: Stable ids. uuid5 over the batch's natural key means a re-run computes the same uuid
#: and ON CONFLICT (id) updates in place — `requirement_facts` has no other unique
#: constraint, so ON CONFLICT on anything else silently matches nothing.
NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")


def entity_uuid(destination_country: str, domain_area: str, topic_key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{destination_country}|{domain_area}|{topic_key}"))


def fact_uuid(fact_uid: str) -> str:
    return str(uuid.uuid5(NAMESPACE, fact_uid))


# ── V0: normalisation ────────────────────────────────────────────────────────

def normalise_source_url(raw: Optional[str]) -> str:
    """Repair the URL garble a research pipeline introduces, and only that.

    Three specific breakages, all seen in delivered batches: a trailing `%22` from a
    quote swallowed into the href, a fragment repeated after itself, and a bare host
    with no scheme. Anything else is left alone — a URL this cannot repair is a URL a
    human should look at, not one to guess at.
    """
    url = (raw or "").strip()
    if not url:
        return ""
    while url.endswith("%22") or url.endswith('"') or url.endswith("'"):
        url = url[:-3] if url.endswith("%22") else url[:-1]
    url = url.rstrip(").,;")
    if "//" not in url:
        url = "https://" + url.lstrip("/")
    parts = urlsplit(url)
    # A duplicated fragment ("#a#a") — keep the first.
    frag = parts.fragment.split("#")[0] if parts.fragment else ""
    scheme = parts.scheme or "https"
    return urlunsplit((scheme, parts.netloc, parts.path, parts.query, frag))


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── record shapes ────────────────────────────────────────────────────────────

@dataclass
class Entity:
    entity_uid: str
    destination_country: str
    domain_area: str
    topic_key: str
    title: str
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Fact:
    fact_uid: str
    entity_uid: str
    fact_type: str
    fact_key: str
    fact_text: str
    source_url: str
    evidence_quote: Optional[str]
    confidence: str
    raw: Dict[str, Any] = field(default_factory=dict)

    # filled in by the gates
    checks: Dict[str, Any] = field(default_factory=dict)
    verdict: str = VERDICT_REJECT
    authority_rank: Optional[int] = None
    fetched_at: Optional[datetime] = None
    evidence_verified: Optional[bool] = None
    evidence_offset: Optional[int] = None


# ── batch loading ────────────────────────────────────────────────────────────

def _read_ndjson(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            # JSONL is self-delimiting on purpose: one bad line loses one record, and
            # saying which one is more useful than aborting the batch.
            log.warning("%s:%d — unparseable JSON, skipped (%s)", path.name, n, exc)
    return rows


def load_batch(batch_dir: Path) -> Tuple[List[Entity], List[Fact], List[str]]:
    """Read `01_requirement_entities_*.ndjson` + `02_requirement_facts_*.ndjson`."""
    problems: List[str] = []
    ent_files = sorted(batch_dir.glob("01_requirement_entities*.ndjson"))
    fact_files = sorted(batch_dir.glob("02_requirement_facts*.ndjson"))
    if not ent_files:
        problems.append(f"no 01_requirement_entities*.ndjson in {batch_dir}")
    if not fact_files:
        problems.append(f"no 02_requirement_facts*.ndjson in {batch_dir}")

    entities = [
        Entity(
            entity_uid=str(r.get("entity_uid") or "").strip(),
            destination_country=str(r.get("destination_country") or "").strip().upper(),
            domain_area=str(r.get("domain_area") or "").strip().lower(),
            topic_key=str(r.get("topic_key") or "").strip(),
            title=str(r.get("title") or "").strip(),
            raw=r,
        )
        for f in ent_files for r in _read_ndjson(f)
    ]
    facts = [
        Fact(
            fact_uid=str(r.get("fact_uid") or "").strip(),
            entity_uid=str(r.get("entity_uid") or "").strip(),
            fact_type=str(r.get("fact_type") or "other").strip().lower(),
            fact_key=str(r.get("fact_key") or "").strip(),
            fact_text=str(r.get("fact_text") or "").strip(),
            source_url=normalise_source_url(r.get("source_url")),
            evidence_quote=(r.get("evidence_quote") or None),
            confidence=str(r.get("confidence") or "medium").strip().lower(),
            raw=r,
        )
        for f in fact_files for r in _read_ndjson(f)
    ]
    return entities, facts, problems


# ── V1: schema / enum gate ───────────────────────────────────────────────────

def v1_entity(e: Entity) -> List[str]:
    bad: List[str] = []
    if not e.entity_uid:
        bad.append("entity_uid missing")
    if len(e.destination_country) != 2 or not e.destination_country.isalpha():
        bad.append(f"destination_country must be ISO-3166-1 alpha-2, got {e.destination_country!r}")
    if e.domain_area not in DOMAIN_AREAS:
        bad.append(f"domain_area {e.domain_area!r} not in live vocab")
    if not e.topic_key:
        bad.append("topic_key missing")
    if not e.title:
        bad.append("title missing")
    return bad


def v1_fact(f: Fact, known_entity_uids: set) -> List[str]:
    bad: List[str] = []
    if not f.fact_uid:
        bad.append("fact_uid missing")
    if not f.entity_uid:
        bad.append("entity_uid missing")
    elif f.entity_uid not in known_entity_uids:
        bad.append(f"entity_uid {f.entity_uid!r} has no matching entity")
    if f.fact_type not in FACT_TYPES:
        bad.append(f"fact_type {f.fact_type!r} not in live vocab")
    if f.confidence not in CONFIDENCES:
        bad.append(f"confidence {f.confidence!r} not in live vocab")
    if not f.fact_key:
        bad.append("fact_key missing")
    if not f.fact_text:
        bad.append("fact_text missing")
    return bad


# ── V2: source gate ──────────────────────────────────────────────────────────

def v2_source(f: Fact) -> Tuple[List[str], Optional[int]]:
    bad: List[str] = []
    if not f.source_url:
        return ["source_url missing"], None
    parts = urlsplit(f.source_url)
    if parts.scheme != "https":
        bad.append(f"source_url is not https ({parts.scheme or 'no scheme'})")
    klass = classify_source(f.source_url)
    rank = AUTHORITY_RANK.get(klass, 3)
    if rank > MIN_ACCEPTABLE_RANK:
        bad.append(f"source host is {klass} — not a body entitled to publish this rule")
    return bad, rank


# ── verdict ──────────────────────────────────────────────────────────────────

def verdict_for(schema_bad: List[str], source_bad: List[str], evidence_status: Optional[str]) -> str:
    """reject = must not land. flag = landed decision deferred. pass = clean.

    A failed V1 or V2 is a REJECT: the row is either malformed or cites a source we are
    not willing to stand behind, and neither is fixable downstream.

    A failed V3 is a FLAG, not a reject — UNVERIFIED means "we have the page and could
    not find the quote", which is frequently the extractor recomposing a bullet list
    into a sentence rather than an invention. That is a human's call, so it goes to the
    worklist without being landed.
    """
    if schema_bad or source_bad:
        return VERDICT_REJECT
    if evidence_status == VERIFIED:
        return VERDICT_PASS
    if evidence_status == TRANSLATED:
        # A verbatim match was impossible by construction. Says nothing about the fact.
        return VERDICT_FLAG
    return VERDICT_FLAG


def run_gates(
    entities: List[Entity],
    facts: List[Fact],
    *,
    fetcher: Any = None,
    robots: Any = None,
    limiter: Any = None,
) -> Tuple[List[Entity], List[Fact], List[Dict[str, Any]]]:
    """Run V1-V3 over the batch. Returns (clean_entities, facts, worklist)."""
    worklist: List[Dict[str, Any]] = []

    seen_entity_uids: set = set()
    good_entities: List[Entity] = []
    for e in entities:
        bad = v1_entity(e)
        if e.entity_uid in seen_entity_uids:
            bad.append(f"duplicate entity_uid {e.entity_uid!r}")
        if bad:
            worklist.append({"kind": "entity", "uid": e.entity_uid, "reasons": bad})
            continue
        seen_entity_uids.add(e.entity_uid)
        good_entities.append(e)

    page_cache: Dict[str, str] = {}
    seen_fact_uids: set = set()
    for f in facts:
        schema_bad = v1_fact(f, seen_entity_uids)
        if f.fact_uid and f.fact_uid in seen_fact_uids:
            schema_bad.append(f"duplicate fact_uid {f.fact_uid!r}")
        if f.fact_uid:
            seen_fact_uids.add(f.fact_uid)

        source_bad, rank = v2_source(f)
        f.authority_rank = rank

        evidence_status: Optional[str] = None
        if not schema_bad and not source_bad and fetcher is not None:
            if f.source_url not in page_cache:
                res = fetcher(f.source_url, robots=robots, limiter=limiter)
                page_cache[f.source_url] = res.get("text") or ""
                if not res.get("ok"):
                    source_bad.append(f"source did not resolve: {res.get('reason')}")
            text = page_cache.get(f.source_url, "")
            f.fetched_at = _now()
            if not source_bad:
                ev = check_evidence(f.evidence_quote, text)
                evidence_status = ev.status
                f.evidence_verified = ev.verified
                f.evidence_offset = ev.offset

        f.checks = {
            "v1_schema": {"ok": not schema_bad, "problems": schema_bad},
            "v2_source": {"ok": not source_bad, "problems": source_bad,
                          "authority_rank": rank},
            "v3_evidence": {"status": evidence_status, "verified": f.evidence_verified},
        }
        f.verdict = verdict_for(schema_bad, source_bad, evidence_status)
        if f.verdict != VERDICT_PASS:
            worklist.append({
                "kind": "fact", "uid": f.fact_uid, "verdict": f.verdict,
                "source_url": f.source_url,
                "reasons": schema_bad + source_bad
                           + ([f"evidence {evidence_status}"] if evidence_status
                              and evidence_status != VERIFIED else []),
            })

    return good_entities, facts, worklist


# ── reporting ────────────────────────────────────────────────────────────────

def build_report(entities: List[Entity], facts: List[Fact], worklist: List[Dict[str, Any]],
                 *, batch_id: str, applied: bool) -> Dict[str, Any]:
    by_verdict: Dict[str, int] = {}
    for f in facts:
        by_verdict[f.verdict] = by_verdict.get(f.verdict, 0) + 1
    checked = [f for f in facts if f.evidence_verified is not None]
    verified = [f for f in checked if f.evidence_verified]
    return {
        "batch_id": batch_id,
        "mode": "apply" if applied else "dry-run",
        "entities_in": len(entities),
        "facts_in": len(facts),
        "by_verdict": by_verdict,
        "evidence_checked": len(checked),
        "evidence_verified": len(verified),
        "evidence_verified_rate": round(len(verified) / len(checked), 3) if checked else None,
        "worklist_size": len(worklist),
    }


def print_report(rep: Dict[str, Any]) -> None:
    print(f"\nVerifier report — batch {rep['batch_id']} [{rep['mode']}]")
    print(f"  entities in : {rep['entities_in']}")
    print(f"  facts in    : {rep['facts_in']}")
    for v in (VERDICT_PASS, VERDICT_FLAG, VERDICT_REJECT):
        print(f"    {v:<7}: {rep['by_verdict'].get(v, 0)}")
    rate = rep["evidence_verified_rate"]
    print(f"  evidence    : {rep['evidence_verified']}/{rep['evidence_checked']} verified"
          f"{f' ({rate:.1%})' if rate is not None else ''}")
    print(f"  worklist    : {rep['worklist_size']} item(s) to re-source")


# ── main ─────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Verify a corridor batch before it becomes data.")
    ap.add_argument("batch_dir", help="directory holding 01_requirement_entities*.ndjson "
                                      "and 02_requirement_facts*.ndjson")
    ap.add_argument("--apply", action="store_true",
                    help="actually write (default: dry run, writes nothing)")
    ap.add_argument("--promote", action="store_true",
                    help="passthrough to scripts/import_otto_facts.py after landing")
    ap.add_argument("--batch-id", help="override the batch id (default: the directory name)")
    ap.add_argument("--no-fetch", action="store_true",
                    help="skip V3 network fetch (V0-V2 only) — for offline checks")
    ap.add_argument("--worklist", default="verifier_worklist.json",
                    help="where to write the re-sourcing worklist")
    args = ap.parse_args(argv)

    batch_dir = Path(args.batch_dir)
    if not batch_dir.is_dir():
        print(f"✖ not a directory: {batch_dir}", file=sys.stderr)
        return 2
    batch_id = args.batch_id or batch_dir.name

    entities, facts, problems = load_batch(batch_dir)
    for p in problems:
        print(f"✖ {p}", file=sys.stderr)
    if problems:
        return 2
    if not facts:
        print("✖ batch contains no facts", file=sys.stderr)
        return 2

    fetcher = robots = limiter = None
    if not args.no_fetch:
        # Imported lazily: it pulls httpx, and V0-V2 must stay runnable without network.
        from backend.scripts.backfill_fact_evidence import (  # noqa: E402
            HostRateLimiter,
            RobotsPolicy,
            fetch_and_parse,
        )
        fetcher, robots, limiter = fetch_and_parse, RobotsPolicy(), HostRateLimiter()

    entities, facts, worklist = run_gates(
        entities, facts, fetcher=fetcher, robots=robots, limiter=limiter
    )

    rep = build_report(entities, facts, worklist, batch_id=batch_id, applied=args.apply)
    print_report(rep)

    Path(args.worklist).write_text(json.dumps(worklist, indent=2), encoding="utf-8")
    print(f"  worklist written to {args.worklist}")

    landed = [f for f in facts if f.verdict == VERDICT_PASS]
    if not args.apply:
        print(f"\nDRY RUN — nothing written. {len(landed)} fact(s) would land at "
              f"status='{STATUS_PENDING}'. Re-run with --apply to write.")
        return 0

    if not os.environ.get("DATABASE_URL"):
        print("✖ DATABASE_URL is not set — cannot --apply.", file=sys.stderr)
        return 2

    from backend.app.db import SessionLocal  # noqa: E402

    with SessionLocal() as session:
        # V0 first: the candidates row is the audit trail, and it is written for EVERY
        # fact including the rejects, which by definition never reach requirement_facts.
        staged = stage_candidates(session, facts, corridor=batch_id)
        written = land(session, entities, landed, batch_id=batch_id)
    print(f"\nAPPLIED — {staged} candidate(s) staged, "
          f"{written['entities']} entit(ies), {written['facts']} fact(s) "
          f"at status='{STATUS_PENDING}' (unserved).")

    if args.promote:
        print("\n--promote: hand off to scripts/import_otto_facts.py "
              "(run it directly; this script does not shell out).")
    return 0


def stage_candidates(session: Any, facts: List[Fact], *, corridor: str) -> int:
    """V0: upsert every fact — verdict and all — into `requirement_fact_candidates`.

    EVERY fact, not just the clean ones. This table is the verifier's audit trail: a row
    rejected at V1 is exactly what someone re-sourcing the batch needs to see, and it
    never reaches requirement_facts. Writing only the passes would make the trail agree
    with the outcome by construction.

    Idempotent on `fact_uid`, which the accompanying migration adds together with a
    partial unique index. Without that column there is no natural key here at all — `id`
    is a table-generated uuid — so this cannot run until the migration is applied.

    NOTE the type narrowing: `requirement_type` admits fewer values than
    `requirement_facts.fact_type`, so FACT_TYPE_TO_REQUIREMENT_TYPE collapses four of
    them onto `other`. See that map for why that is lossy on purpose.
    """
    from sqlalchemy import text  # noqa: E402

    sql = text("""
        INSERT INTO public.requirement_fact_candidates
            (source_url, corridor, requirement_type, fact_text, confidence_score,
             source_quote, extraction_method, status, fact_uid, verdict,
             source_authority_rank, contradiction, checks_json, fetched_at, dimension)
        VALUES
            (:url, :corridor, :rtype, :ftext, :score,
             :quote, :method, :status, :fact_uid, :verdict,
             :rank, false, cast(:checks as jsonb), :fetched, :dimension)
        ON CONFLICT (fact_uid) WHERE fact_uid IS NOT NULL DO UPDATE SET
            source_url            = EXCLUDED.source_url,
            fact_text             = EXCLUDED.fact_text,
            source_quote          = EXCLUDED.source_quote,
            verdict               = EXCLUDED.verdict,
            source_authority_rank = EXCLUDED.source_authority_rank,
            checks_json           = EXCLUDED.checks_json,
            fetched_at            = EXCLUDED.fetched_at
    """)
    # `status` and `reviewed_by`/`reviewed_at` are omitted from the UPDATE for the same
    # reason as in land(): a re-run must not walk back a reviewer's decision.

    n = 0
    for f in facts:
        session.execute(sql, {
            "url": f.source_url or "",
            "corridor": corridor,
            "rtype": FACT_TYPE_TO_REQUIREMENT_TYPE.get(f.fact_type, "other"),
            "ftext": f.fact_text or "",
            "score": CONFIDENCE_TO_SCORE.get(f.confidence, 0.3),
            "quote": f.evidence_quote,
            "method": "verifier_v1",
            "status": STATUS_PENDING,
            "fact_uid": f.fact_uid,
            "verdict": f.verdict,
            "rank": f.authority_rank,
            "checks": json.dumps(f.checks),
            "fetched": f.fetched_at,
            "dimension": f.fact_type,
        })
        n += 1
    session.commit()
    return n


def land(session: Any, entities: List[Entity], facts: List[Fact], *, batch_id: str) -> Dict[str, int]:
    """Write clean entities/facts at status='pending'. Idempotent on the uuid5 id.

    ON CONFLICT (id) and nothing else: `requirement_facts` carries no unique constraint
    besides its primary key, so a conflict target on any other column matches nothing and
    the insert duplicates silently.

    The UPDATE deliberately does NOT touch `status`, `reviewed_by` or `reviewed_at` — a
    re-run must never walk back a decision a reviewer has already made.
    """
    from sqlalchemy import text  # noqa: E402

    ent_sql = text("""
        INSERT INTO public.requirement_entities
            (id, destination_country, domain_area, topic_key, title, status)
        VALUES (:id, :dc, :da, :tk, :title, :status)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            updated_at = now()
    """)
    fact_sql = text("""
        INSERT INTO public.requirement_facts
            (id, entity_id, fact_type, fact_key, fact_text, source_url, evidence_quote,
             confidence, status, evidence_verified, evidence_offset, evidence_checked_at,
             last_checked_at)
        VALUES (:id, :eid, :ft, :fk, :ftext, :url, :quote, :conf, :status,
                :ev, :eoff, :echecked, :echecked)
        ON CONFLICT (id) DO UPDATE SET
            fact_text = EXCLUDED.fact_text,
            source_url = EXCLUDED.source_url,
            evidence_quote = EXCLUDED.evidence_quote,
            evidence_verified = EXCLUDED.evidence_verified,
            evidence_offset = EXCLUDED.evidence_offset,
            evidence_checked_at = EXCLUDED.evidence_checked_at,
            last_checked_at = EXCLUDED.last_checked_at
    """)

    landed_entity_uids = {f.entity_uid for f in facts}
    n_ent = 0
    for e in entities:
        if e.entity_uid not in landed_entity_uids:
            continue  # an entity with no clean fact is not worth a row
        session.execute(ent_sql, {
            "id": entity_uuid(e.destination_country, e.domain_area, e.topic_key),
            "dc": e.destination_country, "da": e.domain_area, "tk": e.topic_key,
            "title": e.title, "status": STATUS_PENDING,
        })
        n_ent += 1

    by_uid = {e.entity_uid: e for e in entities}
    n_fact = 0
    for f in facts:
        e = by_uid.get(f.entity_uid)
        if e is None:
            continue
        session.execute(fact_sql, {
            "id": fact_uuid(f.fact_uid),
            "eid": entity_uuid(e.destination_country, e.domain_area, e.topic_key),
            "ft": f.fact_type, "fk": f.fact_key, "ftext": f.fact_text,
            "url": f.source_url, "quote": f.evidence_quote, "conf": f.confidence,
            "status": STATUS_PENDING,
            "ev": f.evidence_verified, "eoff": f.evidence_offset,
            "echecked": f.fetched_at or _now(),
        })
        n_fact += 1

    session.commit()
    return {"entities": n_ent, "facts": n_fact}


if __name__ == "__main__":
    raise SystemExit(main())
