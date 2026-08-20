#!/usr/bin/env python3
"""Load corridor fact packs into source_records + requirement_items, with their evidence.

WHY THIS EXISTS. `seed_requirements.py` writes `citations_json` as bare URL strings.
`requirements_builder` resolves every citation against a `source_records` map and silently
drops what does not resolve, so those citations reach no screen:
`20261031000000_frno_source_records.sql` measured 90 items carrying citations and 27
resolving. This loader mints the source record FIRST and cites it by id, which is the
documented contract and the only shape the renderer can resolve.

WHAT IT WRITES

  every promoted fact          -> one public.source_records row (url, quote, dates)
  destination-bound facts only -> one public.requirement_items row citing that source id

Origin-side and EU-level facts get a source record and NO requirement row.
`requirement_items.country_code` is the DESTINATION, so a Norwegian exit obligation is not a
French requirement. Which side a fact sits on is read from `corridors/<ID>/facts.yaml`,
never from the fact itself — the same fact is origin-side for one corridor and
destination-side for its reverse.

FOUR PROTECTIONS, EACH ONE EARNED

1. HOLD LIST. The natural key `(country_code, purpose, title)` has NO unique index behind it
   (see docs/corridors/DATA-PATHS.md), so a fact whose title merely *resembles* an existing
   row INSERTS beside it instead of updating it, and there is no delete path to undo that.
   Ireland already holds an approved row "PPSN (…) — application and emergency tax" covering
   what these packs split into three separately-sourced facts. Those three are HELD and
   reported, never written. Holding is a loader decision, not a pack edit: the packs stay
   intact and the gate still passes.
2. NEVER UN-APPROVE. `crud.create_requirement_item` deliberately omits `review_status` from
   its update branch. Do not add it — re-running any seed would otherwise silently
   un-approve live content.
3. NEVER OVERWRITE A HUMAN. Skip any existing row that is `verification_status='verified'`
   (Otto's promote() does the same) and — the guard it lacks — any row that is
   `attestation_status='attested'`. Overwriting counsel-signed text with a seed file is
   strictly worse than overwriting an agent's.
4. FULL TITLE DISCLOSURE. Before writing anything, print every LIVE title for each country
   being written, next to the titles about to be inserted. Not a similarity threshold: the
   token-overlap hint in `overlap_hint()` surfaces only two of the three known Ireland
   collisions, and a difflib ratio missed all three. A human found that collision by reading
   the titles, so the loader shows the human the titles.

SOURCE RECORDS ARE WRITTEN WITH text(), NOT THE ORM, ON PURPOSE. `published_date` is not
declared on `models.SourceRecord`, so nothing else that reads that table through the ORM can
break, and this file can merge before the column is applied. Running it before the apply
fails loudly on the missing column, which is the correct outcome.

USAGE
    python3 backend/scripts/seed_corridor_facts.py --dry-run           # default
    python3 backend/scripts/seed_corridor_facts.py --apply --report r.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

#: Same namespace as seed_requirements.py, so this loader and the YAML seeder derive the SAME
#: id for the same natural key. Otto's executor.promote() imports it for exactly this reason:
#: a second namespace would make two writers insert two rows for one requirement the moment
#: their titles agreed.
from backend.scripts.seed_requirements import _SEED_NS  # noqa: E402

#: Distinct namespace for source records — a different kind of object, keyed on (url, quote).
_SOURCE_NS = uuid.UUID("a1c9e349-0000-4000-8000-000000000002")

FACTS_DIR = os.path.join("backend", "seeds", "facts")
CORRIDORS_DIR = "corridors"

PROMOTED = ("active", "representative")

#: pack status -> requirement_items.verification_status. `verified` is NEVER produced here:
#: raising a requirement to expert-verified is a human act (otto/executor.py:403-407).
VERIFICATION_BY_STATUS = {"active": "corpus_grounded", "representative": "representative"}

#: Facts whose title would land beside an existing approved row rather than updating it.
#: Each entry names the live row it collides with. Remove an entry only together with a
#: decision about that row — see docs/corridors/DATA-PATHS.md.
HOLD: Dict[str, str] = {
    "IE:registration-pps:pps_number":
        'overlaps approved IRELAND row "PPSN (Personal Public Service Number) '
        '— application and emergency tax"',
    "IE:registration-pps:pps_proof_of_address":
        'overlaps approved IRELAND row "PPSN (Personal Public Service Number) '
        '— application and emergency tax" (its evidence covers the address document)',
    "IE:tax-paye:emergency_tax":
        'overlaps approved IRELAND row "PPSN (Personal Public Service Number) '
        '— application and emergency tax"',
}


def _norm(text: str) -> str:
    return " ".join((text or "").split())


def quote_digest(quote: str) -> str:
    return hashlib.sha256(_norm(quote).encode("utf-8")).hexdigest()


def source_id_for(url: str, quote_sha256: str) -> str:
    return str(uuid.uuid5(_SOURCE_NS, f"{url}|{quote_sha256}"))


def content_hash_for(url: str, quote_sha256: str) -> str:
    """Keyed on (url, quote), NOT url alone.

    `source_records.content_hash` is UNIQUE. Rows written by
    20261031000000_frno_source_records.sql hash the url only — and four of these source pages
    back TWO facts each with DIFFERENT quotes (gov.ie's PPS page, impots.gouv.fr's
    resident-de-france, helsenorge's posted-workers, revenue.ie's first-job). A url-only hash
    would collide on the unique index and silently drop half the evidence.
    """
    return hashlib.sha256(f"{url}\x1f{quote_sha256}".encode("utf-8")).hexdigest()


def requirement_id_for(country: str, purpose: str, title: str) -> str:
    return str(uuid.uuid5(_SEED_NS, f"{country}|{purpose}|{title}"))


# ── loading the packs ────────────────────────────────────────────────────────────────────

def load_packs(root: str) -> Dict[str, Dict[str, Any]]:
    import yaml

    facts: Dict[str, Dict[str, Any]] = {}
    directory = os.path.join(root, FACTS_DIR)
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".yaml"):
            continue
        with open(os.path.join(directory, name), encoding="utf-8") as handle:
            pack = yaml.safe_load(handle) or {}
        jurisdiction = pack["jurisdiction"]
        for fact in pack.get("facts") or []:
            key = f"{jurisdiction}:{fact['topic']}:{fact['fact_key']}"
            fact["_key"] = key
            fact["_jurisdiction"] = jurisdiction
            fact["_catalog_country"] = pack.get("catalog_country")
            fact["_defaults"] = {
                "purposes": pack.get("default_purposes") or ["employment"],
                "owner": pack.get("default_owner") or "EMPLOYEE",
                "severity": pack.get("default_severity") or "WARN",
            }
            facts[key] = fact
    return facts


def load_destination_bound(root: str) -> Dict[str, str]:
    """canonical key -> destination ISO, for facts some corridor binds destination-side.

    A fact reaches requirement_items ONLY through a destination binding. Origin and EU-level
    facts are bound elsewhere and get a source record but no requirement row.
    """
    import yaml

    bound: Dict[str, str] = {}
    corridors = os.path.join(root, CORRIDORS_DIR)
    for entry in sorted(os.listdir(corridors)):
        path = os.path.join(corridors, entry, "facts.yaml")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            doc = yaml.safe_load(handle) or {}
        for item in doc.get("destination_facts") or []:
            ref = item.get("ref") if isinstance(item, dict) else item
            bound[ref] = doc["destination_iso"]
    return bound


# ── the pure half ────────────────────────────────────────────────────────────────────────

def build_payloads(
    facts: Dict[str, Dict[str, Any]],
    destination_bound: Dict[str, str],
    *,
    hold: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Expand packs into source_records + requirement_items payloads. Pure: no DB, no clock.

    `last_verified_at` comes from the fact's own `last_verified_date`, never utcnow() — the
    date a human checked the source is a property of the evidence, not of this run.
    """
    hold = HOLD if hold is None else hold
    sources: Dict[str, Dict[str, Any]] = {}
    requirements: List[Dict[str, Any]] = []
    held: List[Dict[str, str]] = []
    skipped_unpromoted: List[str] = []

    for key in sorted(facts):
        fact = facts[key]
        if fact.get("kind") == "preparation_item" or fact.get("status") not in PROMOTED:
            skipped_unpromoted.append(key)
            continue

        source = fact.get("source") or {}
        url = source["url"]
        digest = source.get("quote_sha256") or quote_digest(source["evidence_quote"])
        sid = source_id_for(url, digest)

        # De-duplicated on (url, quote): two facts citing the SAME sentence from the SAME page
        # share one source record, while the same page with different quotes yields two.
        sources.setdefault(sid, {
            "id": sid,
            "country_code": fact["_catalog_country"],
            "url": url,
            # source_records.title is NOT NULL. The pack's source_version is the human-readable
            # identification of the exact document revision, which is what a title should be.
            "title": source.get("source_version") or fact["title"],
            "publisher_domain": source["publisher_domain"],
            "retrieved_at": source["retrieved_at"],
            "published_date": source["published_date"],
            "snippet": _norm(source["evidence_quote"]),
            "content_hash": content_hash_for(url, digest),
        })

        destination = destination_bound.get(key)
        if not destination:
            continue  # origin-side / EU-level: evidence is addressable, no requirement row

        if key in hold:
            held.append({"key": key, "title": fact["title"], "reason": hold[key]})
            continue

        defaults = fact["_defaults"]
        country = fact["_catalog_country"]
        for purpose in defaults["purposes"]:
            requirements.append({
                "id": requirement_id_for(country, purpose, fact["title"]),
                "country_code": country,
                "purpose": purpose,
                "pillar": fact["pillar"],
                "title": fact["title"],
                "description": _norm(fact["fact_text"]),
                "severity": fact.get("severity") or defaults["severity"],
                "owner": fact.get("owner") or defaults["owner"],
                "required_fields_json": json.dumps([]),
                # THE POINT OF THIS LOADER: source_record IDS, never bare URLs.
                "citations_json": json.dumps([sid]),
                "applies_to_nationality_classes_json": None,
                "applies_to_assignment_types_json": None,
                "verification_status": VERIFICATION_BY_STATUS[fact["status"]],
                "non_obvious": bool(fact.get("non_obvious")),
                "timing": fact.get("timing"),
                "review_status": "pending",
                "last_verified_at": _as_datetime(fact["last_verified_date"]),
                "_key": key,
            })

    return {
        "sources": list(sources.values()),
        "requirements": requirements,
        "held": held,
        "skipped_unpromoted": skipped_unpromoted,
    }


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


_STOPWORDS = {
    "a", "an", "and", "the", "of", "for", "to", "in", "on", "is", "are", "be", "by", "at",
    "from", "with", "or", "must", "can", "you", "your", "it", "its", "as", "that", "this",
    "not", "no", "if", "when", "than", "then", "into", "out", "up", "under", "over",
}


def significant_tokens(title: str) -> set:
    cleaned = "".join(c.lower() if (c.isalnum() or c.isspace()) else " " for c in title or "")
    return {t for t in cleaned.split() if len(t) > 2 and t not in _STOPWORDS}


def overlap_hint(title: str, existing: Sequence[str], floor: int = 2) -> List[str]:
    """Live titles sharing >= `floor` significant tokens. A HINT, not a verdict.

    IT IS NOT SUFFICIENT, AND MUST NOT BE TREATED AS IF IT WERE. Measured against the one
    collision we know about, it surfaces two of the three Ireland facts and misses
    "Proof of address for a PPS application ..." entirely, which shares only `application`
    with the live row it duplicates. A `difflib` ratio over whole titles did worse still —
    it missed all three, because the two phrasings share concepts rather than character runs.

    So the report prints EVERY live title for each affected country regardless of this
    function, and the loader's real protection is the explicit HOLD list. This exists only to
    order the human's attention, never to decide. If you are tempted to raise `floor` and
    call the check done, re-read this paragraph.
    """
    tokens = significant_tokens(title)
    hits = []
    for candidate in existing:
        if candidate == title:
            continue
        shared = tokens & significant_tokens(candidate)
        if len(shared) >= floor:
            hits.append(f"{len(shared)} shared {sorted(shared)}  {candidate}")
    return sorted(hits, reverse=True)


# ── the write half ───────────────────────────────────────────────────────────────────────

_SOURCE_UPSERT = """
INSERT INTO public.source_records
    (id, country_code, url, title, publisher_domain, retrieved_at, published_date,
     snippet, content_hash)
VALUES
    (:id, :country_code, :url, :title, :publisher_domain, :retrieved_at, :published_date,
     :snippet, :content_hash)
ON CONFLICT (id) DO UPDATE SET
    url            = EXCLUDED.url,
    title          = EXCLUDED.title,
    publisher_domain = EXCLUDED.publisher_domain,
    retrieved_at   = EXCLUDED.retrieved_at,
    published_date = EXCLUDED.published_date,
    snippet        = EXCLUDED.snippet
"""


def run(root: str, *, apply: bool) -> Dict[str, Any]:
    from sqlalchemy import text

    from backend.app import crud, models
    from backend.app.db import SessionLocal

    facts = load_packs(root)
    plan = build_payloads(facts, load_destination_bound(root))

    session = SessionLocal()
    try:
        countries = sorted({r["country_code"] for r in plan["requirements"]})
        live: Dict[str, Dict[str, Any]] = {}
        for row in (
            session.query(models.RequirementItem)
            .filter(models.RequirementItem.country_code.in_(countries))
            .all()
            if countries else []
        ):
            live[f'{row.country_code}|{row.purpose}|{row.title}'] = row

        live_titles: Dict[str, List[str]] = {}
        for row in live.values():
            live_titles.setdefault(row.country_code, []).append(row.title)

        report: Dict[str, Any] = {
            "mode": "apply" if apply else "dry-run",
            "sources": len(plan["sources"]),
            "created": 0, "updated": 0,
            "held": plan["held"],
            "skipped_verified": [], "skipped_attested": [],
            "title_near_matches": [],
            # Printed in full, unconditionally. The heuristic above misses real collisions,
            # so the report shows the reviewer everything that is already there rather than
            # only what a threshold happened to flag.
            "live_titles": {c: sorted(t) for c, t in live_titles.items()},
        }

        for payload in plan["requirements"]:
            key = f'{payload["country_code"]}|{payload["purpose"]}|{payload["title"]}'
            existing = live.get(key)
            if existing is None:
                hits = overlap_hint(payload["title"], live_titles.get(payload["country_code"], []))
                if hits:
                    report["title_near_matches"].append(
                        {"title": payload["title"], "country": payload["country_code"],
                         "close_to": hits})
            if existing is not None:
                if getattr(existing, "verification_status", None) == "verified":
                    report["skipped_verified"].append(payload["title"]); continue
                if getattr(existing, "attestation_status", None) == "attested":
                    report["skipped_attested"].append(payload["title"]); continue
                report["updated"] += 1
            else:
                report["created"] += 1

        if apply:
            for source in plan["sources"]:
                session.execute(text(_SOURCE_UPSERT), source)
            session.commit()
            for payload in plan["requirements"]:
                key = f'{payload["country_code"]}|{payload["purpose"]}|{payload["title"]}'
                existing = live.get(key)
                if existing is not None and (
                    getattr(existing, "verification_status", None) == "verified"
                    or getattr(existing, "attestation_status", None) == "attested"
                ):
                    continue
                crud.create_requirement_item(session, {k: v for k, v in payload.items()
                                                       if not k.startswith("_")})
        return report
    finally:
        session.close()


def _render(report: Dict[str, Any]) -> str:
    lines = [f"corridor fact load — {report['mode']}",
             f"  source_records : {report['sources']}",
             f"  requirements   : {report['created']} create, {report['updated']} update"]
    for label, entries in (("HELD", report["held"]),
                           ("skipped (verified)", report["skipped_verified"]),
                           ("skipped (attested)", report["skipped_attested"])):
        if entries:
            lines.append(f"  {label}: {len(entries)}")
            for entry in entries:
                lines.append(f"      {entry['title'] if isinstance(entry, dict) else entry}")
                if isinstance(entry, dict):
                    lines.append(f"        reason: {entry['reason']}")
    if report["title_near_matches"]:
        lines.append(f"  TITLE NEAR-MATCHES: {len(report['title_near_matches'])} "
                     "(would INSERT beside a live row, not update it)")
        for hit in report["title_near_matches"]:
            lines.append(f"      {hit['country']}  {hit['title']}")
            for close in hit["close_to"]:
                lines.append(f"        ~ {close}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=_REPO_ROOT)
    parser.add_argument("--apply", action="store_true",
                        help="write. Omitted = dry-run, which is the default on purpose.")
    parser.add_argument("--report", dest="report_path", default=None)
    args = parser.parse_args(argv)

    report = run(args.root, apply=args.apply)
    print(_render(report))
    if args.report_path:
        with open(args.report_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False, default=str)
        print(f"\nreport written to {args.report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
