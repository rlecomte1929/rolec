"""Write the seed into `knowledge_packs -> knowledge_docs -> requirement_entities ->
requirement_facts`, all new content `status='pending'`.

**This module never overwrites content a human could have reviewed.** That is the one design
decision worth reading, because the obvious implementation gets it wrong: `backend/db/misc.py`
already ships `upsert_knowledge_doc_by_url` and `upsert_requirement_entity`, both of which take
the natural key this importer dedupes on, and reusing them would have been three lines. But
measured against production on 2026-08-12, this seed's 86 URLs collide with **23 existing
`knowledge_docs`** and its topics with **5 existing `requirement_entities`**. Those upserts
would have overwritten the `text_content`, `title` and `publisher` of 23 documents the product
already serves, and rewritten 5 entity titles while forcing their status back to `'pending'` —
silently un-approving whatever a human had already signed off. A seed importer that can revoke
an approval is not a seed importer.

So a pre-existing doc or entity is *adopted*: read, reused as an FK target, and left exactly as
it was. Only `requirement_facts` rows are created, and only where `(entity_id, fact_key)` is
absent. None of these tables has a unique index, so every dedupe below is app-level and reads
the live table first — including the pre-existing product rows, not just this seed's own.

**One exception, added after the first live run exposed the hole: a *stub* document is
repaired.** Adopting any existing row regardless of its contents attached 32 of this seed's 92
facts to bodies reading `"Otto bridge capture, unverified — see source_url"` (48 characters)
— rows an earlier pipeline wrote, 22 of them still flagged `fetch_status='not_fetched'` —
even though the page had been fetched successfully moments earlier. The fact ended up citing a
placeholder instead of its source, which is the exact failure guard #1816 exists to prevent,
arrived at from the opposite direction. `MIN_REAL_DOC_CHARS` is what keeps the repair from
becoming the destructive upsert rejected above: a row already holding a real document is never
written to, so nothing a human could have read is replaced, and going from a stub to the actual
page cannot lose information. It also repairs every other fact hanging off the same stub.

Evidence, per guard #1816: `evidence_quote` must appear in the document body actually fetched.
A quote that does not match is dropped to the manual worklist and its fact is **not** written.
The seed's other facts carry no quote at all (134 of 142); they are stored with a real fetched
document behind them and `evidence_quote = NULL`, which is what an unverified-but-sourced claim
honestly looks like. `--require-evidence` narrows the run to quoted facts only.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text

from backend.imports.immigration.fetcher import FetchedDoc, Fetcher, fetch_url
from backend.imports.immigration.parsers import (
    DOMAIN,
    FactRow,
    group_by_url,
    normalise_text,
)

log = logging.getLogger(__name__)

PENDING = "pending"

#: A stored body shorter than this is a stub, not a document — the Otto bridge wrote 121 rows
#: reading "Otto bridge capture, unverified — see source_url" (48 chars), 22 of them still
#: flagged fetch_status='not_fetched'. Matches fetcher.MIN_TEXT_CHARS, which is the floor a
#: freshly fetched page must clear to be stored at all; a row below it is repairable.
MIN_REAL_DOC_CHARS = 600

_SELECT_PACK = text(
    "SELECT id FROM knowledge_packs WHERE destination_country = :country AND domain = :domain "
    "AND status = 'active' ORDER BY created_at DESC LIMIT 1"
)
_INSERT_PACK = text(
    "INSERT INTO knowledge_packs (id, destination_country, domain, version, status, "
    "last_verified_at, created_at) "
    "VALUES (:id, :destination_country, :domain, 1, 'active', :now, :now)"
)
_SELECT_DOC = text(
    "SELECT id, coalesce(length(text_content), 0) AS len FROM knowledge_docs "
    "WHERE source_url = :url LIMIT 1"
)
#: Repairs a stub body in place. Deliberately narrow: only `text_content` and the fetch
#: bookkeeping, and only on rows whose body is already too short to be a document.
_REPAIR_DOC = text(
    "UPDATE knowledge_docs SET text_content = :text_content, content_excerpt = :content_excerpt, "
    "content_sha256 = :content_sha256, fetch_status = :fetch_status, fetched_at = :now, "
    "last_verified_at = :now, title = coalesce(nullif(title, ''), :title), "
    "publisher = coalesce(nullif(publisher, ''), :publisher) "
    "WHERE id = :id AND coalesce(length(text_content), 0) < :floor"
)
_INSERT_DOC = text(
    "INSERT INTO knowledge_docs (id, pack_id, title, publisher, source_url, text_content, "
    "fetched_at, fetch_status, content_excerpt, content_sha256, last_verified_at, created_at) "
    "VALUES (:id, :pack_id, :title, :publisher, :source_url, :text_content, :now, "
    ":fetch_status, :content_excerpt, :content_sha256, :now, :now)"
)
_SELECT_ENTITY = text(
    "SELECT id FROM requirement_entities WHERE destination_country = :country "
    "AND topic_key = :topic_key LIMIT 1"
)
_INSERT_ENTITY = text(
    "INSERT INTO requirement_entities (id, destination_country, domain_area, topic_key, title, "
    "status, created_at, updated_at) "
    "VALUES (:id, :destination_country, :domain_area, :topic_key, :title, :status, :now, :now)"
)
_SELECT_FACT_KEYS = text(
    "SELECT fact_key FROM requirement_facts WHERE entity_id = :entity_id"
)
_INSERT_FACT = text(
    "INSERT INTO requirement_facts (id, entity_id, fact_type, fact_key, fact_text, applies_to, "
    "required_fields, source_doc_id, source_url, evidence_quote, confidence, status, created_at) "
    "VALUES (:id, :entity_id, :fact_type, :fact_key, :fact_text, CAST(:applies_to AS jsonb), "
    "CAST('[]' AS jsonb), :source_doc_id, :source_url, :evidence_quote, :confidence, :status, :now)"
)


@dataclass
class IngestResult:
    """Counts of what THIS call did. `facts_inserted` never counts an adopted row."""

    packs_created: int = 0
    packs_adopted: int = 0
    docs_created: int = 0
    docs_adopted: int = 0
    docs_repaired: int = 0
    entities_created: int = 0
    entities_adopted: int = 0
    facts_inserted: int = 0
    facts_already_present: int = 0

    fetch_ok: int = 0
    fetch_failed: List[str] = field(default_factory=list)
    evidence_verified: List[str] = field(default_factory=list)
    needs_manual_evidence: List[str] = field(default_factory=list)
    skipped_no_document: int = 0
    skipped_unquoted: int = 0

    per_country: Dict[str, int] = field(default_factory=dict)

    @property
    def facts_accounted_for(self) -> int:
        """Inserted now + already there. A clean re-run inserts 0 and is still complete."""
        return self.facts_inserted + self.facts_already_present


def _one(conn: Any, stmt: Any, params: Dict[str, Any]) -> Optional[str]:
    row = conn.execute(stmt, params).first()
    return row[0] if row else None


def _resolve_pack(conn: Any, country: str, result: IngestResult,
                  created: Dict[str, str], dry_run: bool) -> Optional[str]:
    if country in created:
        return created[country]
    existing = _one(conn, _SELECT_PACK, {"country": country, "domain": DOMAIN})
    if existing:
        result.packs_adopted += 1
        created[country] = existing
        return existing
    result.packs_created += 1
    pack_id = str(uuid.uuid4())
    created[country] = pack_id
    if not dry_run:
        conn.execute(_INSERT_PACK, {
            "id": pack_id, "destination_country": country, "domain": DOMAIN,
            "now": datetime.utcnow().isoformat(),
        })
    return pack_id


def ingest(
    conn: Any,
    rows: Sequence[FactRow],
    *,
    fetcher: Fetcher = fetch_url,
    dry_run: bool = True,
    require_evidence: bool = False,
    keep_unmatched: bool = False,
) -> IngestResult:
    """Run the whole chain. Takes a Connection whose transaction the CALLER owns.

    A dry run performs every read, every fetch and every decision a live run performs, and
    differs only in issuing no INSERT. Its counts are therefore the counts a live run produces —
    which is what makes approving the preview meaningful rather than a formality.
    """
    result = IngestResult()
    if not rows:
        return result

    by_url = group_by_url(rows)
    pack_ids: Dict[str, str] = {}
    doc_ids: Dict[str, str] = {}
    entity_ids: Dict[Tuple[str, str], str] = {}
    #: (entity_key -> fact_keys) already in the table, plus what this run has written, so two
    #: seed rows landing on one new entity cannot both insert the same fact_key.
    known_fact_keys: Dict[Tuple[str, str], set] = {}
    now = datetime.utcnow().isoformat()

    for url, url_rows in by_url.items():
        doc = fetcher(url)
        if not doc.ok:
            result.fetch_failed.append(f"{url} — {doc.error}")
            result.skipped_no_document += len(url_rows)
            continue
        result.fetch_ok += 1

        haystack = normalise_text(doc.text_content)

        # Decide every fact on this URL before writing anything, so a document is only created
        # when at least one fact will actually reference it (no orphan docs on a full skip).
        writable: List[Tuple[FactRow, Optional[str]]] = []
        for row in url_rows:
            label = f"{row.destination_country}/{row.topic_key}/{row.fact_key}"
            if row.evidence_quote:
                if normalise_text(row.evidence_quote) in haystack:
                    result.evidence_verified.append(label)
                    writable.append((row, row.evidence_quote))
                else:
                    result.needs_manual_evidence.append(
                        f"{label} — quote not found in {doc.final_url}"
                    )
                    # The unverified string NEVER reaches evidence_quote either way — that
                    # invariant is guard #1816 and is not configurable. What is configurable is
                    # the fate of the fact it was attached to. In this seed all 8 such strings
                    # are reviewer caveats ("…confirm precise deep link"), so dropping the fact
                    # would discard a sourced claim over a column misuse; the fact still gets a
                    # real fetched document and is flagged needs_review for the human pass.
                    if keep_unmatched:
                        writable.append((row, None))
                continue
            if require_evidence:
                result.skipped_unquoted += 1
                continue
            writable.append((row, None))

        if not writable:
            continue

        country_of_doc = writable[0][0].destination_country
        pack_id = _resolve_pack(conn, country_of_doc, result, pack_ids, dry_run)

        existing = conn.execute(_SELECT_DOC, {"url": url}).first()
        if existing:
            doc_id, existing_len = existing[0], existing[1]
            if existing_len < MIN_REAL_DOC_CHARS:
                # Repair, not overwrite. Adoption originally reused ANY existing row, which
                # silently attached 32 of this seed's 92 facts to bodies like "Otto bridge
                # capture, unverified — see source_url" (48 chars) while the page had in fact
                # been fetched successfully. The fact then cited a stub instead of its source.
                #
                # The floor is what keeps this from becoming the destructive upsert the module
                # docstring rejects: a row that already holds a real document is never written
                # to, so no human-reviewed body is replaced. Going from a placeholder to the
                # actual page cannot lose information, and it repairs every other fact hanging
                # off the same stub rather than only this run's.
                result.docs_repaired += 1
                if not dry_run:
                    conn.execute(_REPAIR_DOC, {
                        **_doc_params(doc_id, pack_id, doc, url, now),
                        "floor": MIN_REAL_DOC_CHARS,
                    })
            else:
                result.docs_adopted += 1
        else:
            result.docs_created += 1
            doc_id = str(uuid.uuid4())
            if not dry_run:
                conn.execute(_INSERT_DOC, _doc_params(doc_id, pack_id, doc, url, now))
        doc_ids[url] = doc_id

        for row, quote in writable:
            entity_id = _resolve_entity(conn, row, result, entity_ids, known_fact_keys,
                                        dry_run, now)
            keys = known_fact_keys[row.entity_key]
            if row.fact_key in keys:
                result.facts_already_present += 1
                continue
            keys.add(row.fact_key)
            result.facts_inserted += 1
            result.per_country[row.destination_country] = (
                result.per_country.get(row.destination_country, 0) + 1
            )
            if dry_run:
                continue
            conn.execute(_INSERT_FACT, {
                "id": str(uuid.uuid4()),
                "entity_id": entity_id,
                "fact_type": row.fact_type,
                "fact_key": row.fact_key,
                "fact_text": row.fact_text,
                "applies_to": json.dumps(row.applies_to or {}),
                "source_doc_id": doc_id,
                "source_url": row.source_url,
                "evidence_quote": quote,
                "confidence": row.confidence,
                "status": PENDING,
                "now": now,
            })

    log.info(
        "immigration seed: %d fact(s) inserted, %d already present, %d doc(s) created, "
        "%d adopted, %d fetch failure(s)",
        result.facts_inserted, result.facts_already_present, result.docs_created,
        result.docs_adopted, len(result.fetch_failed),
    )
    return result


def _doc_params(doc_id: str, pack_id: Optional[str], doc: FetchedDoc, url: str,
                now: str) -> Dict[str, Any]:
    return {
        "id": doc_id,
        "pack_id": pack_id,
        "title": doc.title[:500] or url,
        "publisher": doc.publisher,
        # The seed's URL, not `final_url`: it is the key this importer dedupes on, so storing
        # the post-redirect URL would make the next run miss the row and insert a second copy.
        "source_url": url,
        "text_content": doc.text_content,
        "fetch_status": doc.fetch_status,
        "content_excerpt": doc.text_content[:5000],
        "content_sha256": doc.content_sha256,
        "now": now,
    }


def _resolve_entity(conn: Any, row: FactRow, result: IngestResult,
                    entity_ids: Dict[Tuple[str, str], str],
                    known_fact_keys: Dict[Tuple[str, str], set],
                    dry_run: bool, now: str) -> str:
    key = row.entity_key
    if key in entity_ids:
        return entity_ids[key]

    existing = _one(conn, _SELECT_ENTITY,
                    {"country": row.destination_country, "topic_key": row.topic_key})
    if existing:
        # Adopted: title and status left untouched, so an approved entity stays approved.
        result.entities_adopted += 1
        entity_ids[key] = existing
        known_fact_keys[key] = {
            k for (k,) in conn.execute(_SELECT_FACT_KEYS, {"entity_id": existing})
        }
        return existing

    result.entities_created += 1
    entity_id = str(uuid.uuid4())
    entity_ids[key] = entity_id
    known_fact_keys[key] = set()
    if not dry_run:
        conn.execute(_INSERT_ENTITY, {
            "id": entity_id,
            "destination_country": row.destination_country,
            "domain_area": DOMAIN,
            "topic_key": row.topic_key,
            "title": row.entity_title,
            "status": PENDING,
            "now": now,
        })
    return entity_id


def summarise(result: IngestResult, *, dry_run: bool, keep_unmatched: bool = False) -> str:
    """The report the CLI prints. The two worklists are the point, not the totals."""
    verb = "would write" if dry_run else "wrote"
    lines = [
        f"{'DRY RUN — nothing written' if dry_run else 'APPLIED'}",
        "",
        f"  fetch:    {result.fetch_ok} URL(s) fetched, {len(result.fetch_failed)} failed",
        f"  packs:    {result.packs_created} created, {result.packs_adopted} adopted",
        f"  docs:     {result.docs_created} created, {result.docs_adopted} adopted "
        f"(reused untouched), {result.docs_repaired} repaired (stub body -> fetched page)",
        f"  entities: {result.entities_created} created, {result.entities_adopted} adopted",
        f"  facts:    {verb} {result.facts_inserted}, "
        f"{result.facts_already_present} already present "
        f"({result.facts_accounted_for} accounted for)",
        "",
        f"  evidence: {len(result.evidence_verified)} quote(s) verified against the fetched body",
    ]
    if result.needs_manual_evidence:
        fate = ("fact still written with evidence_quote=NULL" if keep_unmatched
                else "fact skipped")
        lines.append(
            f"            {len(result.needs_manual_evidence)} quote(s) NOT found — "
            f"{fate}, needs manual sourcing:"
        )
        lines += [f"              - {m}" for m in result.needs_manual_evidence]
    if result.skipped_unquoted:
        lines.append(
            f"            {result.skipped_unquoted} unquoted fact(s) skipped (--require-evidence)"
        )
    if result.skipped_no_document:
        lines.append(
            f"            {result.skipped_no_document} fact(s) skipped — their source could "
            "not be fetched, and a fact cannot be stored without its document"
        )
    if result.fetch_failed:
        lines.append(f"\n  {len(result.fetch_failed)} fetch failure(s) — re-source or retry:")
        lines += [f"    - {f}" for f in result.fetch_failed]
    if result.per_country:
        lines.append(f"\n  per country ({verb}):")
        for country in sorted(result.per_country):
            lines.append(f"    {country}  {result.per_country[country]:>3}")
    return "\n".join(lines)
