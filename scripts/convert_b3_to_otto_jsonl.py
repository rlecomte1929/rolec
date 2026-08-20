#!/usr/bin/env python3
"""Convert the B3 research batch into the JSONL `scripts/import_otto_facts.py` reads.

B3 (`docs/imports/B3-facts-enrichment.md`) is a set of *divergence flags*: each record pairs
what official guidance says with what actually happens. That pair is the payload — it is the
only thing in the batch an HR generalist could not have got from the government website.

Otto's fact channel carries a single `fact_text`, so the pair is composed into a labelled
block rather than flattened into one narrative sentence. A reviewer's question is "is this
true, and is it actually surprising?", which needs both halves visible and separable; merged
into prose they read as one claim and the misconception half stops being identifiable. The
structured original stays in `docs/imports/data/B3/corridor_facts.ndjson`, which remains the
queryable copy — this file is the import-shaped view of it, not a replacement.

Derives, never invents. Every output field traces to an input field or to a rule stated below.

Run from the repo root:

    python scripts/convert_b3_to_otto_jsonl.py            # write the JSONL
    python scripts/convert_b3_to_otto_jsonl.py --check    # verify the committed file matches

Then import with the usual CLI, which dry-runs by default:

    python scripts/import_otto_facts.py B3-corridor-facts-2026-08-18
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "docs" / "imports" / "data" / "B3" / "corridor_facts.ndjson"
BATCH_ID = "B3-corridor-facts-2026-08-18"
OUT = REPO_ROOT / "audos-workspace-776786" / "data" / f"{BATCH_ID}.jsonl"

#: B3 `category` -> the closest member of `parsers.KNOWN_FACT_TYPES`. A category with no
#: honest match falls to "other" rather than being forced into a neighbouring bucket.
FACT_TYPE_BY_CATEGORY = {
    "immigration_work_authorization": "eligibility",
    "immigration_registration": "step",
    "registration_anmeldung": "step",
    "registration_cpr": "step",
    "identity_number": "step",
    "payroll_id": "step",
    "tax_id_payroll": "step",
    "banking_digital_id": "step",
    "social_security": "eligibility",
    "social_security_offshore": "eligibility",
    "tax_expat_scheme": "eligibility",
    "tax_payroll": "other",
    "healthcare_cost": "fee",
    "broadcasting_fee": "fee",
}


def split_corridor(corridor: str) -> tuple[str, str]:
    """`"NO->GB"` -> `("NO", "GB")`. The destination is where the requirement applies."""
    origin, _, dest = corridor.partition("->")
    origin, dest = origin.strip().upper(), dest.strip().upper()
    if len(origin) != 2 or len(dest) != 2:
        raise ValueError(f"unparseable corridor {corridor!r}")
    return origin, dest


def compose_fact_text(rec: dict) -> str:
    return (
        f"Commonly believed: {rec['official_guidance'].strip()}\n\n"
        f"Actually: {rec['actual_reality'].strip()}\n\n"
        f"Action required: {rec['action_required'].strip()}"
    )


def to_record(rec: dict, seq: int) -> dict:
    origin, dest = split_corridor(rec["corridor"])
    category = rec["category"].strip()

    out = {
        "destination_country": dest,
        "entity_topic_key": category,
        # `dedupe_key` is destination|topic|fact_key, and B3 carries several ORIGINS into the
        # same destination and category — DK->DE and a later FR->DE would collide on
        # `DE|tax_payroll|…` without the origin here. `seq` keeps it unique and stable.
        "fact_key": f"b3_{origin.lower()}_{dest.lower()}_{category}_{seq:02d}",
        "fact_text": compose_fact_text(rec),
        "source_url": rec["source_url"].strip(),
        "entity_title": f"{dest} {category.replace('_', ' ')}",
        "fact_type": FACT_TYPE_BY_CATEGORY.get(category, "other"),
        # B3's `employee_type` is the literal "all" — a wildcard, not an employee type.
        # `backend/imports/otto/mappings.py` is explicit that NULL nationality means
        # *applies to everyone* and that "any" is deliberately not a value, so the
        # nationality key is OMITTED rather than filled. Corridor is kept because it is
        # real scoping information the flat fact would otherwise lose.
        "applies_to": {"corridor": f"{origin}->{dest}"},
        # B3 carries no verbatim source quotes, so `grade()` pins every row to
        # needs_review. That is the intended outcome for unreviewed research, not a gap.
        "evidence_quote": None,
        # Single-pass Otto research, not a multi-pass beam. Recorded honestly rather than
        # inflated to match a default.
        "confidence": "medium",
    }
    if rec.get("source_missing"):
        # Nothing in this batch sets it. If a later re-run does, the row must not silently
        # acquire a citation it never had — an empty source_url is rejected by the reader,
        # which is the correct outcome.
        out["source_url"] = ""
    return out


def build() -> list[dict]:
    rows = [json.loads(line) for line in SOURCE.read_text().splitlines() if line.strip()]
    return [to_record(r, i) for i, r in enumerate(rows, start=1)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify the committed JSONL matches what this script would emit")
    args = ap.parse_args()

    records = build()
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)

    if args.check:
        if not OUT.exists():
            print(f"FAIL {OUT} does not exist", file=sys.stderr)
            return 1
        if OUT.read_text() != body:
            print(f"FAIL {OUT} is stale — re-run without --check", file=sys.stderr)
            return 1
        print(f"OK   {OUT.relative_to(REPO_ROOT)} matches ({len(records)} records)")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(body)

    dests: dict[str, int] = {}
    for r in records:
        dests[r["destination_country"]] = dests.get(r["destination_country"], 0) + 1
    keys = {(r["destination_country"], r["entity_topic_key"], r["fact_key"]) for r in records}

    print(f"wrote {OUT.relative_to(REPO_ROOT)}")
    print(f"  records          {len(records)}")
    print(f"  unique dedupe    {len(keys)}  (collision-free: {len(keys) == len(records)})")
    print(f"  by destination   {dict(sorted(dests.items()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
