"""Write parsed facts into `otto_staging`, reconcile the batch honestly, and promote it.

Three separate operations, mirroring `../suppliers/executor.py`:

    stage()      immigration_entities -> immigration_fact_candidates
    reconcile()  + load_log, processing_queue
    promote()    + public.requirement_items          (opt-in, --promote)

`promote()` is the step that was missing from every content system in this repo. Staging
tables had approve buttons and no promoters: `/admin/requirement-facts` flips a status column
nothing reads, and 85 approved `requirement_facts` feed an endpoint no screen calls. Staged
rows that never move are indistinguishable from research nobody did.

**`reconcile()` is the reason this module is worth reading.** On 2026-08-12 at 01:04 UTC the
batch `WATCH-2026-08-12-w3` wrote a `load_log` row reading `reconcile_status='pass'`,
`loaded_count=24` — while loading nothing at all. 24 was the row count of the whole table,
carried over from the France batch that had failed hours earlier at 24 of 109. A reconciler
that answers "how many rows are in the table?" instead of "how many did *this run* put there?"
reports success forever, and the run it is covering for never gets re-issued.

So `loaded_count` here is only ever the count of rows **this call inserted**, and
`reconcile_status` is *derived* from arithmetic rather than passed in by the caller. There is
no argument a caller can supply that makes a batch pass without the numbers agreeing.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text

from backend.imports.otto.parsers import FactRow

log = logging.getLogger(__name__)

PASS = "pass"
PARTIAL = "partial"
FAIL = "fail"

QUEUE_DONE = "done"
QUEUE_IN_PROGRESS = "in_progress"
QUEUE_STUCK = "stuck"

_UPSERT_ENTITY = text(
    """
    INSERT INTO otto_staging.immigration_entities
        (destination_country, domain_area, topic_key, title, batch_id, source)
    VALUES (:destination_country, 'immigration', :topic_key, :title, :batch_id, 'otto_research')
    ON CONFLICT (destination_country, topic_key) DO NOTHING
    """
)

#: `ON CONFLICT (dedupe_key) DO NOTHING` + `RETURNING id` is what makes a re-run safe AND
#: countable: a row that was already present returns nothing, so it is never counted as loaded.
#: This is the mechanism the false-green lacked.
_INSERT_FACT = text(
    """
    INSERT INTO otto_staging.immigration_fact_candidates
        (destination_country, entity_topic_key, fact_type, fact_key, fact_text, applies_to,
         source_url, evidence_quote, confidence, confidence_score, accuracy_tier,
         extraction_method, batch_id, dedupe_key, status)
    VALUES
        (:destination_country, :entity_topic_key, :fact_type, :fact_key, :fact_text,
         CAST(:applies_to AS jsonb), :source_url, :evidence_quote, :confidence,
         :confidence_score, :accuracy_tier, 'otto_research', :batch_id, :dedupe_key, 'new')
    ON CONFLICT (dedupe_key) DO NOTHING
    RETURNING id
    """
)

_INSERT_LOAD_LOG = text(
    """
    INSERT INTO otto_staging.load_log
        (batch_id, source_label, expected_count, loaded_count, reconcile_status,
         discrepancy, notes)
    VALUES (:batch_id, :source_label, :expected_count, :loaded_count, :reconcile_status,
            :discrepancy, :notes)
    RETURNING id
    """
)

_UPDATE_QUEUE = text(
    """
    UPDATE otto_staging.processing_queue
       SET status = :status,
           loaded_count = :loaded_count,
           attempts = attempts + 1,
           last_note = :last_note,
           updated_at = now()
     WHERE source_label = :source_label
    """
)

_QUEUE_EXPECTED = text(
    "SELECT expected_count FROM otto_staging.processing_queue WHERE source_label = :source_label"
)


@dataclass
class StageResult:
    """What a single `stage()` call actually did. Every count is of *this* run."""

    batch_id: str
    inserted: int = 0
    already_present: int = 0
    entities: int = 0
    rejections: List[str] = field(default_factory=list)
    downgraded: List[str] = field(default_factory=list)
    unscoped: List[str] = field(default_factory=list)

    @property
    def accounted_for(self) -> int:
        """Rows this run put in the table plus rows a previous run already had.

        The right numerator for "is this batch complete?" — a re-run of a fully-loaded batch
        inserts 0 and is still complete, which a bare `inserted` count would call a failure.
        """
        return self.inserted + self.already_present


def _unscoped_topics(rows: Sequence[FactRow]) -> List[str]:
    """Topics whose facts will promote to `purpose='other'` because nobody said otherwise.

    `mappings.resolve()` derives purpose from `applies_to.status`, and `PURPOSES.get(status or
    '', 'other')` turns an ABSENT status into a real enum value. That is the quiet half of the
    contract: `crud.list_requirements` filters `purpose` with strict equality and no catch-all,
    so a row that lands at 'other' is approved, live, and permanently invisible to the
    `purpose=employment` readers — the dossier and the public corridor endpoint. The count does
    not move and nothing errors. All nine VE->IE facts shipped this way (AIQ-2035); the
    converter now sets it, but Otto writes batches with no converter in the path at all.

    Reported per `entity_topic_key`, because the topic is the unit of promotion — one
    requirement, however many facts fed it.

    An explicit `"any"` is NOT flagged: 'other' is a legitimate purpose that FRANCE already
    serves an approved row at, so choosing it deliberately is a decision, not an omission. Only
    absent, unrecognised, or self-contradicting statuses appear here — the three ways a topic
    arrives at 'other' without anyone having chosen it.
    """
    # Local, mirroring promote(): mappings pulls in backend.app.services, and stage() has no
    # other reason to drag that into the import graph.
    from backend.imports.otto.mappings import PURPOSES

    by_topic: Dict[Any, List[FactRow]] = {}
    for row in rows:
        by_topic.setdefault((row.destination_country, row.entity_topic_key), []).append(row)

    out: List[str] = []
    for (country, topic), facts in by_topic.items():
        values = {(f.applies_to or {}).get("status") for f in facts}
        known = {v for v in values if v in PURPOSES}
        if len(known) == 1 and len(values) == 1:
            continue                      # one recognised status, agreed on — nothing to say
        if not known:
            why = ("no fact carries applies_to.status"
                   if values == {None}
                   else f"applies_to.status {sorted(str(v) for v in values)} is not a "
                        f"recognised purpose")
        else:
            why = (f"facts disagree on applies_to.status "
                   f"({sorted(str(v) for v in values)}), so the group is not one requirement")
        out.append(
            f"{country}/{topic}: {why} — will promote as purpose='other' and be invisible "
            f"to the purpose=employment readers"
        )
    return sorted(out)


def stage(
    conn: Any,
    rows: Sequence[FactRow],
    *,
    rejections: Sequence[str] = (),
    dry_run: bool = True,
) -> StageResult:
    """Insert entities and facts. Returns counts of what THIS call wrote.

    `rejections` are the parser's — rows that never became `FactRow`s because their publisher
    failed the sourcing gate. They are carried through rather than dropped because a batch
    that lost rows to bad sourcing is not complete, and `reconcile()` has to say so.

    Takes a Connection inside a transaction the CALLER owns, so a failure halfway through
    rolls the whole batch back rather than leaving a country half-loaded.

    A dry run takes the same code path and performs the same reads, so its numbers are the
    numbers a real run produces — except that it cannot know which rows the inserts would have
    skipped, so it asks the table directly (`_existing_keys`) instead of guessing.
    """
    result = StageResult(
        batch_id=rows[0].batch_id if rows else "",
        rejections=list(rejections),
    )
    if not rows:
        return result

    existing = _existing_keys(conn, [r.dedupe_key for r in rows])

    for row in rows:
        if row.downgrades:
            result.downgraded.append(f"{row.dedupe_key}: {'; '.join(row.downgrades)}")

    result.unscoped = _unscoped_topics(rows)

    if dry_run:
        result.already_present = sum(1 for r in rows if r.dedupe_key in existing)
        result.inserted = len(rows) - result.already_present
        result.entities = len({(r.destination_country, r.entity_topic_key) for r in rows})
        return result

    seen_entities = set()
    for row in rows:
        key = (row.destination_country, row.entity_topic_key)
        if key not in seen_entities:
            seen_entities.add(key)
            conn.execute(
                _UPSERT_ENTITY,
                {
                    "destination_country": row.destination_country,
                    "topic_key": row.entity_topic_key,
                    "title": row.entity_title,
                    "batch_id": row.batch_id,
                },
            )
    result.entities = len(seen_entities)

    for row in rows:
        inserted_id = conn.execute(
            _INSERT_FACT,
            {
                "destination_country": row.destination_country,
                "entity_topic_key": row.entity_topic_key,
                "fact_type": row.fact_type,
                "fact_key": row.fact_key,
                "fact_text": row.fact_text,
                "applies_to": json.dumps(row.applies_to) if row.applies_to else None,
                "source_url": row.source_url,
                "evidence_quote": row.evidence_quote,
                "confidence": row.confidence,
                "confidence_score": row.confidence_score,
                "accuracy_tier": row.accuracy_tier,
                "batch_id": row.batch_id,
                "dedupe_key": row.dedupe_key,
            },
        ).scalar()
        if inserted_id is None:
            result.already_present += 1
        else:
            result.inserted += 1

    log.info(
        "%s: inserted %d fact(s), %d already present, %d entit(ies)",
        result.batch_id, result.inserted, result.already_present, result.entities,
    )
    return result


def _existing_keys(conn: Any, keys: Sequence[str]) -> set:
    if not keys:
        return set()
    stmt = text(
        "SELECT dedupe_key FROM otto_staging.immigration_fact_candidates "
        "WHERE dedupe_key = ANY(:keys)"
    )
    return {k for (k,) in conn.execute(stmt, {"keys": list(keys)}) if k}


def queue_expected(conn: Any, source_label: str) -> Optional[int]:
    """Otto's own metrics count for this deliverable, if the queue recorded one."""
    got = conn.execute(_QUEUE_EXPECTED, {"source_label": source_label}).first()
    return got[0] if got else None


def derive_status(expected: Optional[int], accounted_for: int) -> str:
    """`pass` only when the arithmetic supports it. Not a parameter — a conclusion.

        >>> derive_status(109, 24)
        'partial'
        >>> derive_status(109, 109)
        'pass'
        >>> derive_status(None, 24)
        'partial'
        >>> derive_status(109, 0)
        'fail'

    With no `expected` the answer is `partial`, never `pass`. "We loaded some rows and nobody
    told us how many there should have been" is precisely the state that produced a green
    ledger over an empty load — an unknown denominator is a reason to withhold `pass`, not to
    assume it.
    """
    if accounted_for == 0:
        return FAIL
    if expected is None:
        return PARTIAL
    return PASS if accounted_for >= expected else PARTIAL


def reconcile(
    conn: Any,
    result: StageResult,
    *,
    source_label: str,
    expected_count: Optional[int],
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Write the `load_log` row and update `processing_queue`. Returns the ledger row.

    `loaded_count` is `result.inserted` — rows THIS run wrote — and never a count of the
    table. See the module docstring for the incident this prevents.
    """
    status = derive_status(expected_count, result.accounted_for)

    discrepancy: Optional[str] = None
    if status != PASS:
        shortfall = (
            f"{expected_count - result.accounted_for} of {expected_count} fact(s) not delivered"
            if expected_count is not None
            else "no expected_count recorded for this deliverable, so completeness is unproven"
        )
        discrepancy = shortfall
        if result.rejections:
            discrepancy += f"; {len(result.rejections)} row(s) rejected on sourcing"

    notes_parts = [
        f"file channel; {result.inserted} inserted, {result.already_present} already present, "
        f"{result.entities} entity(ies)"
    ]
    if result.downgraded:
        notes_parts.append(f"{len(result.downgraded)} row(s) downgraded to needs_review")
    if result.rejections:
        notes_parts.append(f"rejected: {'; '.join(result.rejections[:5])}")
    notes = " · ".join(notes_parts)

    ledger = {
        "batch_id": result.batch_id,
        "source_label": source_label,
        "expected_count": expected_count,
        "loaded_count": result.inserted,
        "reconcile_status": status,
        "discrepancy": discrepancy,
        "notes": notes,
    }

    if not dry_run:
        conn.execute(_INSERT_LOAD_LOG, ledger)
        conn.execute(
            _UPDATE_QUEUE,
            {
                "source_label": source_label,
                "status": QUEUE_DONE if status == PASS else QUEUE_IN_PROGRESS,
                "loaded_count": result.accounted_for,
                "last_note": f"[{status}] {notes}"[:2000],
            },
        )
    return ledger


STATUS_READY = "ready"
STATUS_PROMOTED = "promoted"
EXPERT_VERIFIED = "expert_verified"

#: Every verification_status that means "a human stood behind this row", so promote() must not
#: overwrite it. `expert_verified` is the value the backend constants use; **`verified` is the
#: value production actually stores** — 10 rows carry it and none carry `expert_verified`.
#: Testing only the constant meant the guard below protected nothing that exists, and a
#: re-promote would rewrite a human-raised row's description, severity and owner. The same
#: split is documented client-side at `frontend/src/api/admin.ts:24-26` and asserted in
#: `supabase/migrations/20261112000000_cite_served_requirement_items.sql:126`.
HUMAN_VERIFIED = (EXPERT_VERIFIED, "verified")

_PROMOTABLE = text(
    """
    SELECT e.destination_country, e.topic_key, e.title, e.domain_area,
           f.id, f.fact_type, f.fact_key, f.fact_text, f.applies_to, f.source_url,
           f.evidence_quote, f.accuracy_tier
      FROM otto_staging.immigration_entities e
      JOIN otto_staging.immigration_fact_candidates f
        ON f.destination_country = e.destination_country
       AND f.entity_topic_key = e.topic_key
     WHERE f.status = :ready
       AND (:country IS NULL OR e.destination_country = :country)
     ORDER BY e.destination_country, e.topic_key, f.fact_key
    """
)

_MARK_PROMOTED = text(
    "UPDATE otto_staging.immigration_fact_candidates SET status = :promoted "
    "WHERE id = ANY(CAST(:ids AS uuid[]))"
)


@dataclass
class PromoteResult:
    promoted: int = 0
    skipped_verified: List[str] = field(default_factory=list)
    unmapped: List[str] = field(default_factory=list)
    drafts: List[Any] = field(default_factory=list)


def promote(session: Any, *, country: Optional[str] = None, dry_run: bool = True) -> PromoteResult:
    """Promote ready facts into `public.requirement_items`, one row per entity.

    Writes through `backend.app.crud.create_requirement_item`, which owns the upsert on the
    natural key `(country_code, purpose, title)`. Reusing it — rather than hand-rolling the
    SQL — is what lets a promoted row and a later YAML re-seed of the same requirement
    converge on one row instead of racing each other.

    Nothing here writes `expert_verified`. Promoted rows land `corpus_grounded` at best and
    render behind the provenance badge in `RequirementList.tsx`, so a reader always sees what
    the evidence supports. Raising a requirement to expert-verified stays a human act.

    Returns a `PromoteResult`; idempotent, because promoted facts leave `status='ready'`.
    """
    import uuid
    from datetime import datetime

    from backend.app import crud
    from backend.app.models import RequirementItem
    # Same namespace as the YAML seeder, so both writers derive the SAME id for the same
    # natural key. A second namespace here would make `seed_requirements.py` and this promoter
    # insert two rows for one requirement the moment their titles agreed.
    from backend.scripts.seed_requirements import _SEED_NS
    from backend.imports.otto import mappings

    result = PromoteResult()
    rows = session.execute(
        _PROMOTABLE, {"ready": STATUS_READY, "country": country}
    ).mappings().all()

    groups: Dict[Any, List[Any]] = {}
    entities: Dict[Any, Any] = {}
    for row in rows:
        key = (row["destination_country"], row["topic_key"])
        groups.setdefault(key, []).append(SimpleNamespace(**dict(row)))
        entities[key] = SimpleNamespace(
            destination_country=row["destination_country"],
            topic_key=row["topic_key"],
            title=row["title"],
            domain_area=row["domain_area"],
        )

    stamp = datetime.utcnow()

    for key, facts in groups.items():
        draft = mappings.resolve(entities[key], facts)
        if isinstance(draft, mappings.Unmapped):
            result.unmapped.append(f"{key[0]}/{draft.topic_key}: {draft.reason}")
            continue

        # Never overwrite a human. crud.create_requirement_item upserts on the natural key and
        # WILL rewrite description, severity, owner and citations of whatever it finds. FRANCE
        # already holds 26 curated rows; silently winning against an expert-verified one would
        # replace a lawyer's answer with an agent's.
        existing = (
            session.query(RequirementItem)
            .filter(RequirementItem.country_code == draft.country_code)
            .filter(RequirementItem.purpose == draft.purpose)
            .filter(RequirementItem.title == draft.title)
            .first()
        )
        if existing is not None and existing.verification_status in HUMAN_VERIFIED:
            result.skipped_verified.append(
                f"{draft.country_code}/{draft.purpose}/{draft.title} "
                f"is {existing.verification_status}"
            )
            continue

        result.drafts.append(draft)
        if dry_run:
            result.promoted += 1
            continue

        payload = dict(draft.payload)
        payload["id"] = str(
            uuid.uuid5(_SEED_NS, f"{draft.country_code}|{draft.purpose}|{draft.title}")
        )
        payload["last_verified_at"] = stamp
        # Agent-derived content is never published by the act of promoting it. It waits at
        # /admin/countries for a human, exactly as a harvested supplier waits in the vetting
        # queue. Ignored on the update branch, so approving a row once makes it stick.
        payload["review_status"] = "pending"
        crud.create_requirement_item(session, payload)
        session.execute(_MARK_PROMOTED, {"promoted": STATUS_PROMOTED, "ids": draft.fact_ids})
        session.commit()
        result.promoted += 1

    log.info(
        "promote: %d requirement(s), %d unmapped, %d expert-verified collision(s)",
        result.promoted, len(result.unmapped), len(result.skipped_verified),
    )
    return result


def summarise_promotion(result: PromoteResult) -> str:
    """The promotion block the CLI prints. The unmapped list is a worklist, not an error."""
    lines = [f"promote:  {result.promoted} requirement(s) into requirement_items"]
    for draft in result.drafts:
        lines.append(f"    + [{draft.verification_status}] {draft.country_code} · "
                     f"{draft.purpose} · {draft.title}")
        for note in draft.derivations:
            lines.append(f"        {note}")
    if result.skipped_verified:
        lines.append(f"\n  {len(result.skipped_verified)} skipped — a human already owns these:")
        lines += [f"    - {s}" for s in result.skipped_verified]
    if result.unmapped:
        lines.append(f"\n  {len(result.unmapped)} entit(ies) NOT promoted — this is the "
                     "research worklist, not a failure:")
        lines += [f"    - {u}" for u in result.unmapped]
    return "\n".join(lines)


def summarise(result: StageResult, ledger: Dict[str, Any]) -> str:
    """The block the CLI prints. Leads with the reconciliation, because that is the finding."""
    status = ledger["reconcile_status"]
    mark = {PASS: "✔", PARTIAL: "◐", FAIL: "✖"}[status]
    expected = ledger["expected_count"]

    lines = [
        f"{mark} {status.upper()}  batch {result.batch_id!r}",
        f"    inserted this run: {result.inserted}",
        f"    already present:   {result.already_present}",
        f"    accounted for:     {result.accounted_for}"
        + (f" of {expected} expected" if expected is not None else " (no expected_count)"),
        f"    entities touched:  {result.entities}",
    ]
    if ledger["discrepancy"]:
        lines.append(f"    discrepancy:       {ledger['discrepancy']}")
    if result.downgraded:
        lines.append(f"\n  {len(result.downgraded)} row(s) downgraded to needs_review:")
        lines += [f"    - {d}" for d in result.downgraded[:10]]
        if len(result.downgraded) > 10:
            lines.append(f"    … and {len(result.downgraded) - 10} more")
    if result.unscoped:
        lines.append(f"\n  {len(result.unscoped)} topic(s) with NO usable applies_to.status:")
        lines += [f"    - {u}" for u in result.unscoped]
    if result.rejections:
        lines.append(f"\n  {len(result.rejections)} row(s) REJECTED (nothing staged for these):")
        lines += [f"    - {r}" for r in result.rejections]
    return "\n".join(lines)
