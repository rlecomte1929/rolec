#!/usr/bin/env python3
"""Convert the VE→IE entry-visa + dependant deliverable into the otto fact JSONL shape.

    python scripts/convert_ve_ie_to_otto_jsonl.py            # write the JSONL
    python scripts/convert_ve_ie_to_otto_jsonl.py --check    # validate only, write nothing

Then stage it with the importer that already exists — this script does not write to any
database:

    ./.venv311/bin/python scripts/import_otto_facts.py ve-ie-entry-family-2026-08-20

WHY A CONVERTER AT ALL
----------------------
AIQ-1993 delivered `docs/imports/ve-ie-entry-family-2026-08-20/` in the *requirement_items*
field vocabulary (`fact_uid`, `topic_key`, `destination_country_code`). The otto reader wants
`fact_key`, `entity_topic_key`, `destination_country`, and does no aliasing, so the deliverable
fails its own card's Test Command at line 1:

    ✖ line 1: missing required field(s): destination_country, entity_topic_key, fact_key

This is the same gap `convert_b3_to_otto_jsonl.py` closes for the B3 batch, and this module
follows it deliberately: rename into the reader's vocabulary, compose the divergence into the
single `fact_text` the channel carries, and park everything the channel has no column for in
`applies_to` so a reviewer can still see it. The importer itself is untouched.

WHAT IT REFUSES TO DO
---------------------
**It does not derive nationality from the corridor.** B3's converter calls
`nationality_class.classify(origin, dest)` because B3 carries the literal wildcard
`employee_type: "all"`. Doing that here would be wrong and dangerous: the corridor is ES→IE,
so classify() would answer EEA — a Spanish national has free movement into Ireland. But the
subject of this batch is a **Venezuelan** national resident in Spain, and the whole point of
the deliverable is that her Spanish residence does not carry into Ireland. The artifact states
the class outright in `applies_to_nationality_classes`, so that delivered field is used and the
corridor derivation is not. Getting this backwards would serve the free-mover track to a
visa-required national — the exact failure `nationality_class.py` exists to prevent.

**It does not invent an evidence quote, a source, a confidence or a fact_type.** Every row in
this batch already carries a real `evidence_quote`; none carries `confidence` or `fact_type`,
so those take the reader's honest defaults (`medium`, `other`) rather than a guess dressed up
as a reading.

**It does not resolve `quote_verbatim_confirmed`.** Every row in the batch carries it as
`false` — the quote was captured but never re-checked against the page. The otto `grade()`
function has no vocabulary for that flag, so the four rows published by a statutory host
(`irishimmigration.ie`, `enterprise.gov.ie`) will still score `auto_accepted` on
"official publisher + a quotable line". The flag is carried verbatim in `applies_to` and the
overlap is called out in the batch doc; nothing here is promotable regardless, because the
importer stages every row at `status='new'` and `promote()` only ever reads `status='ready'`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent

BATCH_ID = "ve-ie-entry-family-2026-08-20"
SOURCE = (
    REPO_ROOT / "docs" / "imports" / BATCH_ID / "ve_ie_entry_family_requirement_facts.ndjson"
)
MANIFEST = REPO_ROOT / "docs" / "imports" / BATCH_ID / "manifest.json"
#: Where `import_otto_facts.py` looks when handed the bare batch id, so the card's Test
#: Command works verbatim rather than needing an explicit path.
OUT = REPO_ROOT / "audos-workspace-776786" / "data" / f"{BATCH_ID}.jsonl"

#: `applies_to.nationality` vocabulary accepted by `mappings.NATIONALITY_CLASSES`.
NATIONALITY_BY_CLASS: Dict[str, str] = {
    "THIRD_COUNTRY": "non-EEA",
    "EU_EEA": "EEA",
    "OWN_NATIONAL": "EEA",
}


def nationality_for(rec: Dict[str, Any]) -> str:
    """The `applies_to.nationality` value, read from the artifact — never from the corridor.

    See the module docstring: the corridor is ES→IE but the subject is Venezuelan, so the
    corridor derivation gives precisely the wrong answer.
    """
    classes = rec.get("applies_to_nationality_classes") or []
    if not isinstance(classes, list) or not classes:
        raise ValueError(
            f"{rec.get('fact_uid')!r}: no applies_to_nationality_classes — a fact that cannot "
            "be scoped to a nationality class must not be guessed into one"
        )
    mapped = {NATIONALITY_BY_CLASS.get(str(c).strip().upper()) for c in classes}
    if None in mapped:
        raise ValueError(
            f"{rec.get('fact_uid')!r}: unrecognised nationality class in {classes!r}"
        )
    if len(mapped) != 1:
        raise ValueError(
            f"{rec.get('fact_uid')!r}: spans several nationality classes {classes!r}; the "
            "channel carries one value, so this needs splitting upstream, not collapsing here"
        )
    return mapped.pop()


def compose_fact_text(rec: Dict[str, Any]) -> str:
    """Keep the statement AND both halves of the divergence identifiable in one string.

    The channel carries a single `fact_text`. This batch carries a statement *and*, on the six
    non-obvious rows, a three-part note whose value is precisely the gap between what the
    official page says and what actually happens. Merging or dropping a half would destroy the
    only thing here that a government website does not already say.
    """
    parts: List[str] = [str(rec["fact_text"]).strip()]
    note = rec.get("non_obvious_note") or {}
    if note:
        parts.append(f"Commonly believed: {str(note['official_guidance']).strip()}")
        parts.append(f"Actually: {str(note['actual_reality']).strip()}")
        parts.append(f"Action required: {str(note['action_required']).strip()}")
    return "\n\n".join(parts)


def to_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    origin = str(rec["origin_country_code"]).strip().upper()
    dest = str(rec["destination_country_code"]).strip().upper()
    topic_key = str(rec["topic_key"]).strip()

    return {
        "destination_country": dest,
        # One entity per fact. The artifact's `topic_key` is unique across the batch and the
        # manifest asks for nine requirement_items, so a 1:1 entity:fact mapping is what
        # eventually promotes to the nine rows it names — collapsing them under one entity
        # would promote to a single merged requirement.
        "entity_topic_key": topic_key,
        # `dedupe_key` is destination|topic|fact_key. `topic_key` alone already makes it
        # unique, but the origin is carried here too so a later VE→IE batch arriving from a
        # different origin cannot land on an existing key. Derived from delivered fields.
        "fact_key": f"{origin.lower()}_{dest.lower()}_{topic_key}",
        "fact_text": compose_fact_text(rec),
        "source_url": str(rec["source_url"]).strip(),
        "entity_title": f"Ireland — {topic_key.replace('_', ' ')}",
        # Not carried by the artifact. `other` is the reader's honest default; picking
        # `document`/`step`/`eligibility` per row would be a guess presented as a reading.
        "fact_type": "other",
        "applies_to": {
            "corridor": f"{origin}->{dest}",
            "nationality": nationality_for(rec),
            # Everything below has no column in `immigration_fact_candidates`. It rides here
            # verbatim so a reviewer sees what the research actually said — in particular the
            # four rows counsel has to clear before anything is approved.
            "fact_uid": str(rec["fact_uid"]).strip(),
            "pillar": str(rec.get("pillar") or "").strip() or None,
            "non_obvious": bool(rec.get("non_obvious")),
            "needs_lawyer_review": bool(rec.get("needs_lawyer_review")),
            "quote_verbatim_confirmed": bool(rec.get("quote_verbatim_confirmed")),
            "source_name": str(rec.get("source_name") or "").strip() or None,
            "batch_id": BATCH_ID,
        },
        "evidence_quote": str(rec.get("evidence_quote") or "").strip() or None,
        # Not carried by the artifact. Recorded honestly rather than inflated; `grade()`
        # treats it as an input, never the last word.
        "confidence": "medium",
    }


def source_records() -> List[Dict[str, Any]]:
    return [json.loads(l) for l in SOURCE.read_text(encoding="utf-8").splitlines() if l.strip()]


def build() -> List[Dict[str, Any]]:
    return [to_record(r) for r in source_records()]


def check(records: List[Dict[str, Any]]) -> List[str]:
    """Every invariant that would otherwise cost a fact quietly."""
    problems: List[str] = []

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = int(manifest["record_count"])
    if len(records) != expected:
        problems.append(f"count {len(records)} != manifest record_count {expected}")

    keys = [(r["destination_country"], r["entity_topic_key"], r["fact_key"]) for r in records]
    if len(keys) != len(set(keys)):
        problems.append("duplicate dedupe_key — a collision is reported as a rejection, "
                        "so it would lose a fact without erroring")

    for rec, out in zip(source_records(), records):
        uid = rec["fact_uid"]
        if not out["source_url"]:
            problems.append(f"{uid}: empty source_url")
        if not out["evidence_quote"]:
            problems.append(f"{uid}: evidence_quote dropped in conversion")
        if out["applies_to"]["nationality"] != "non-EEA":
            problems.append(f"{uid}: nationality {out['applies_to']['nationality']!r} — this "
                            "batch is a third-country national, the free-mover track is wrong")
        note = rec.get("non_obvious_note") or {}
        for half in ("official_guidance", "actual_reality", "action_required"):
            if note and str(note[half]).strip() not in out["fact_text"]:
                problems.append(f"{uid}: {half} lost from fact_text")
        if str(rec["fact_text"]).strip() not in out["fact_text"]:
            problems.append(f"{uid}: statement lost from fact_text")

    lawyer = sum(1 for r in records if r["applies_to"]["needs_lawyer_review"])
    if lawyer != int(manifest["needs_lawyer_review_count"]):
        problems.append(
            f"needs_lawyer_review {lawyer} != manifest "
            f"{manifest['needs_lawyer_review_count']} — the counsel gate must not lose rows"
        )
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    args = ap.parse_args()

    records = build()
    problems = check(records)
    for p in problems:
        print(f"  ✖ {p}")
    if problems:
        print(f"\n✖ {len(problems)} problem(s) — nothing written")
        return 1

    lawyer = [r["applies_to"]["fact_uid"] for r in records if r["applies_to"]["needs_lawyer_review"]]
    print(f"✓ {len(records)} records, dedupe keys unique, counts reconcile against the manifest")
    print(f"  {len(lawyer)} row(s) flagged needs_lawyer_review — must not be approved:")
    for uid in lawyer:
        print(f"    - {uid}")

    if args.check:
        print("\n--check: nothing written")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"\n→ {OUT.relative_to(REPO_ROOT)}")
    print(f"  stage with: ./.venv311/bin/python scripts/import_otto_facts.py {BATCH_ID}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
