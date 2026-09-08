#!/usr/bin/env python3
"""Closure gate for AIQ-2027: prove the VE→IE batch landed as reviewable candidates.

    ./.venv311/bin/python scripts/verify_aiq_2027_ve_ie_load.py            # artifact + derivation
    ./.venv311/bin/python scripts/verify_aiq_2027_ve_ie_load.py --db-url … # + live reconciliation

Exits non-zero on any failure. Every query it runs is a SELECT; it writes nothing and applies
nothing, so it is safe in CI and safe to re-run against production.

`check_ve_ie_batch.py` already gates the *artifact* — hash, counts, conversion, reader. This
gates the *landing*: that the nine facts reached `public.requirement_items` as candidates and
that re-running the load cannot duplicate or un-approve them.

Why this exists rather than a hand-written INSERT migration
-----------------------------------------------------------
AIQ-2027's card asked for a migration of nine `INSERT`s keyed on the artifact's `fact_uid`
with `ON CONFLICT (id) DO NOTHING`. That contract does not hold against this table. The load
path is `promote()`, which writes through `crud.create_requirement_item` — an upsert on the
natural key `(country_code, purpose, title)` whose primary key is
`uuid5(_SEED_NS, "country|purpose|title")`, the same namespace `seed_requirements.py` uses so
a promoted row and a later YAML re-seed converge on one row. A row keyed on `fact_uid`
therefore collides with nothing: `ON CONFLICT (id) DO NOTHING` would fire zero times and
insert nine duplicates beside the nine that are already live.

So the idempotency claim is checked where it actually lives: check 7 re-derives all nine ids
through the real converter → reader → mappings path and asserts they equal the ids prod
holds. Equal ids mean a re-run upserts the same nine rows. That is the same guarantee
`ON CONFLICT (id) DO NOTHING` was meant to give, evidenced rather than asserted.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

BATCH_ID = "ve-ie-entry-family-2026-08-20"
BATCH_DIR = REPO_ROOT / "docs" / "imports" / BATCH_ID
NDJSON = BATCH_DIR / "ve_ie_entry_family_requirement_facts.ndjson"
MANIFEST = BATCH_DIR / "manifest.json"

# Pinned independently of manifest.json. If both the artifact and the manifest were edited in
# one commit, reconciling them against each other would still pass.
EXPECTED_SHA256 = "2186f59ae0cb06bb7403ef4bed2f291ff1ad4313bc270fb0051883f7e63a46d6"
EXPECTED_COUNT = 9

# The four rows counsel must clear before they can be approved at all. Named, not counted:
# a count still passes if a flag moved from one fact to another, and these four are the ones
# whose content is legally load-bearing.
EXPECTED_LAWYER_REVIEW = {
    "spanish_residence_does_not_grant_irish_entry",
    "csep_immediate_family_reunification",
    "spouse_stamp_1g_right_to_work",
    "dependant_join_family_d_visa_required",
}

# Fixed corridor values every row must carry. The nationality is the reason the batch exists:
# ES→IE would derive EEA, but the subject is a Venezuelan national resident in Spain and that
# residence does not carry over. An EEA row would serve the free-mover track to a
# visa-required national.
FIXED_CORRIDOR = {
    "corridor": "ES-IE",
    "origin_country_code": "ES",
    "destination_country_code": "IE",
    "country_code": "IRELAND",
    "verification_status": "representative",
}
EXPECTED_NATIONALITY = ["THIRD_COUNTRY"]

# `domain_area` is NOT fixed: three of the nine are authored as 'family'. They only promote
# because staging normalises every row to 'immigration' — `mappings.resolve` returns Unmapped
# for any other value, so were that normalisation to stop, these three would silently fail to
# promote while the other six succeeded, and nobody would be told. Check 7 is what catches it:
# it drives the real mappings path and raises on Unmapped.
ARTIFACT_DOMAIN_AREAS = {"immigration", "family"}
FAMILY_DOMAIN_TOPICS = {
    "csep_immediate_family_reunification",
    "spouse_stamp_1g_right_to_work",
    "dependant_join_family_d_visa_required",
}

REQUIRED_KEYS = [
    "fact_uid", "topic_key", "domain_area", "pillar", "corridor", "origin_country_code",
    "destination_country_code", "country_code", "applies_to_nationality_classes", "fact_text",
    "non_obvious", "source_url", "source_name", "evidence_quote", "verification_status",
    "review_status", "needs_lawyer_review", "quote_verbatim_confirmed", "batch_id",
]

# Any state that would publish unreviewed immigration content the moment something served it.
FORBIDDEN_REVIEW_STATES = {"approved", "verified", "lawyer_verified", "live", "expert_verified"}


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive_ids(records: List[Dict[str, Any]]) -> Dict[str, str]:
    """Re-derive the primary key `promote()` writes, per topic_key, via the real code path.

    Deliberately drives the shipped converter, the shipped reader and the shipped mappings
    rather than reimplementing the title rule — a local copy of that rule would keep agreeing
    with itself after the real one changed.
    """
    convert = _load_module(
        "convert_ve_ie_to_otto_jsonl", REPO_ROOT / "scripts" / "convert_ve_ie_to_otto_jsonl.py"
    )
    from backend.imports.otto import mappings
    from backend.imports.otto.parsers import read_jsonl
    from backend.scripts.seed_requirements import _SEED_NS

    tmp = Path(tempfile.mkdtemp()) / f"{BATCH_ID}.jsonl"
    tmp.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in convert.build()) + "\n",
        encoding="utf-8",
    )
    rows, rejections = read_jsonl(tmp, batch_id=BATCH_ID)
    if rejections:
        raise RuntimeError(f"reader rejected {len(rejections)} row(s): {rejections[:2]}")

    groups: Dict[Any, List[Any]] = {}
    entities: Dict[Any, Any] = {}
    for idx, row in enumerate(rows):
        key = (row.destination_country, row.entity_topic_key)
        groups.setdefault(key, []).append(
            SimpleNamespace(
                fact_text=row.fact_text, fact_type=row.fact_type, fact_key=row.fact_key,
                applies_to=row.applies_to, source_url=row.source_url,
                evidence_quote=row.evidence_quote, accuracy_tier=row.accuracy_tier, id=idx,
            )
        )
        entities[key] = SimpleNamespace(
            destination_country=row.destination_country, topic_key=row.entity_topic_key,
            title=row.entity_title, domain_area="immigration",
        )

    derived: Dict[str, str] = {}
    for key, facts in groups.items():
        draft = mappings.resolve(entities[key], facts)
        if isinstance(draft, mappings.Unmapped):
            raise RuntimeError(f"{key[1]}: unmapped — {draft.reason}")
        derived[key[1]] = str(
            uuid.uuid5(_SEED_NS, f"{draft.country_code}|{draft.purpose}|{draft.title}")
        )
    return derived


def check_live(db_url: str, records, derived, failures: List[str]) -> None:
    """Reconcile the nine landed rows. SELECT only — this function writes nothing."""
    from sqlalchemy import create_engine, text

    engine = create_engine(db_url)
    topic_keys = [r["topic_key"] for r in records]
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, country_code, purpose, title, review_status, verification_status,"
                "       non_obvious, citations_json"
                "  FROM public.requirement_items"
                " WHERE country_code = :cc AND id = ANY(:ids)"
            ),
            {"cc": FIXED_CORRIDOR["country_code"], "ids": list(derived.values())},
        ).mappings().all()

        by_id = {r["id"]: r for r in rows}
        missing = [tk for tk in topic_keys if derived[tk] not in by_id]
        if missing:
            failures.append(f"not landed in requirement_items: {missing}")
        else:
            print(f"  ✓ all {len(topic_keys)} rows present in public.requirement_items")

        for tk in topic_keys:
            row = by_id.get(derived[tk])
            if row is None:
                continue
            if row["review_status"] != "pending":
                failures.append(f"{tk}: landed review_status={row['review_status']!r}, not 'pending'")
            if row["purpose"] != "employment":
                failures.append(
                    f"{tk}: purpose={row['purpose']!r} — a row at 'other' is unreachable from "
                    "the purpose=employment corridor call even after counsel approves it"
                )
            cites = row["citations_json"] or ""
            flagged = '"needs_lawyer_review": true' in cites
            if flagged != (tk in EXPECTED_LAWYER_REVIEW):
                failures.append(
                    f"{tk}: landed needs_lawyer_review={flagged}, expected "
                    f"{tk in EXPECTED_LAWYER_REVIEW}"
                )
            if f'"topic_key": "{tk}"' not in cites:
                failures.append(f"{tk}: landed citations_json carries no topic_key back-reference")

        if not any(f.startswith(tuple(topic_keys)) for f in failures):
            print("  ✓ every landed row: review_status='pending', purpose='employment', "
                  "counsel flag and topic_key intact")

        # A duplicate would defeat the whole idempotency claim, and would not show up above:
        # the id lookup finds the canonical row and never sees its twin. Matched on topic_key,
        # which `citations_json` genuinely carries — an earlier revision of this check scanned
        # for a `batch_id` marker that is nowhere in the column, so it reported "no duplicates"
        # against a table it had not actually interrogated.
        for tk in topic_keys:
            extra = conn.execute(
                text(
                    "SELECT count(*) FROM public.requirement_items"
                    " WHERE country_code = :cc AND id <> :canonical"
                    "   AND citations_json LIKE :pattern"
                ),
                {"cc": FIXED_CORRIDOR["country_code"], "canonical": derived[tk],
                 "pattern": '%"topic_key": "' + tk + '"%'},
            ).scalar()
            if extra:
                failures.append(
                    f"{tk}: {extra} row(s) beside the canonical id {derived[tk]} — the load "
                    "duplicated instead of upserting"
                )
        if not any("duplicated instead of upserting" in f for f in failures):
            print(f"  \u2713 no duplicate row for any of the {len(topic_keys)} topic keys")

        total = conn.execute(
            text("SELECT count(*) FROM public.requirement_items WHERE country_code = :cc"),
            {"cc": FIXED_CORRIDOR["country_code"]},
        ).scalar()
        pending = conn.execute(
            text("SELECT count(*) FROM public.requirement_items"
                 " WHERE country_code = :cc AND review_status = 'pending'"),
            {"cc": FIXED_CORRIDOR["country_code"]},
        ).scalar()
        print(f"  \u2139 IRELAND now holds {total} requirement_items, {pending} pending review")
        if pending != EXPECTED_COUNT:
            failures.append(
                f"IRELAND has {pending} pending rows, expected {EXPECTED_COUNT} — either the "
                "batch was reviewed, or another batch is also awaiting review"
            )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db-url", default=None,
                    help="read-only reconciliation against a live database (SELECT only). "
                         "Deliberately explicit: DATABASE_URL in a shell points at production.")
    args = ap.parse_args()

    failures: List[str] = []

    for path in (NDJSON, MANIFEST):
        if not path.is_file():
            print(f"✖ missing artifact: {path.relative_to(REPO_ROOT)}")
            return 1

    # 1. source integrity
    actual = sha256(NDJSON)
    manifest_sha = str(json.loads(MANIFEST.read_text(encoding="utf-8"))["sha256"]).strip()
    if actual == EXPECTED_SHA256 and manifest_sha == EXPECTED_SHA256:
        print(f"✓ source sha256 reconciles (artifact = manifest = pinned): {actual}")
    else:
        failures.append(
            f"sha256 mismatch — artifact {actual}, manifest {manifest_sha}, pinned {EXPECTED_SHA256}"
        )

    records = [json.loads(l) for l in NDJSON.read_text(encoding="utf-8").splitlines() if l.strip()]

    # 2. staged row count
    if len(records) == EXPECTED_COUNT:
        print(f"✓ {len(records)} staged rows")
    else:
        failures.append(f"expected exactly {EXPECTED_COUNT} facts, parsed {len(records)}")

    # 3. shape
    shape_errors: List[str] = []
    for idx, rec in enumerate(records, 1):
        uid = rec.get("fact_uid", f"line {idx}")
        for key in REQUIRED_KEYS:
            if key not in rec:
                shape_errors.append(f"{uid}: missing {key!r}")
        for key, want in FIXED_CORRIDOR.items():
            if key in rec and rec[key] != want:
                shape_errors.append(f"{uid}: {key}={rec[key]!r}, expected {want!r}")
        if rec.get("domain_area") not in ARTIFACT_DOMAIN_AREAS:
            shape_errors.append(
                f"{uid}: domain_area={rec.get('domain_area')!r}, expected one of "
                f"{sorted(ARTIFACT_DOMAIN_AREAS)}"
            )
        if rec.get("applies_to_nationality_classes") != EXPECTED_NATIONALITY:
            shape_errors.append(
                f"{uid}: nationality {rec.get('applies_to_nationality_classes')!r}, "
                f"expected {EXPECTED_NATIONALITY!r}"
            )
        if not str(rec.get("evidence_quote") or "").strip():
            shape_errors.append(f"{uid}: empty evidence_quote")
        if not str(rec.get("source_url") or "").startswith("https://"):
            shape_errors.append(f"{uid}: source_url is not an https URL")
    if shape_errors:
        failures.extend(shape_errors)
    else:
        print(f"✓ 0 shape errors across {len(records)} facts")

    # 4. candidates only
    states = {str(r.get("review_status", "")).lower() for r in records}
    if states == {"pending"}:
        print("✓ all review_status values are 'pending'")
    else:
        failures.append(f"review_status values {sorted(states)} — must all be 'pending'")
        for bad in sorted(states & FORBIDDEN_REVIEW_STATES):
            failures.append(f"'{bad}' would publish unreviewed immigration content on promotion")

    # 5. no quote confirmed yet
    confirmed = {r.get("quote_verbatim_confirmed") for r in records}
    if confirmed == {False}:
        print("✓ all quote_verbatim_confirmed values are false")
    else:
        failures.append(f"quote_verbatim_confirmed values {confirmed} — must all be false")

    # 6. the counsel-flagged four, by name
    flagged = {r["topic_key"] for r in records if r.get("needs_lawyer_review")}
    if flagged == EXPECTED_LAWYER_REVIEW:
        print(f"✓ exactly the 4 expected needs_lawyer_review topic keys")
        for tk in sorted(EXPECTED_LAWYER_REVIEW):
            print(f"      · {tk}")
    else:
        failures.append(
            f"needs_lawyer_review mismatch — unexpected {sorted(flagged - EXPECTED_LAWYER_REVIEW)}, "
            f"missing {sorted(EXPECTED_LAWYER_REVIEW - flagged)}"
        )

    # 6b. the family-domain rows are still the ones we think they are
    family_rows = {r["topic_key"] for r in records if r.get("domain_area") == "family"}
    if family_rows == FAMILY_DOMAIN_TOPICS:
        print(f"✓ {len(family_rows)} rows authored domain_area='family' — promote only because "
              "staging normalises them to 'immigration'")
    else:
        failures.append(
            f"domain_area='family' set changed — unexpected {sorted(family_rows - FAMILY_DOMAIN_TOPICS)}, "
            f"missing {sorted(FAMILY_DOMAIN_TOPICS - family_rows)}"
        )

    # 7. idempotency, through the real load path
    derived: Dict[str, str] = {}
    try:
        derived = derive_ids(records)
        if len(set(derived.values())) == EXPECTED_COUNT:
            print(f"✓ idempotent: {EXPECTED_COUNT} distinct ids re-derived through the real "
                  "converter → reader → mappings path")
            for tk in (r["topic_key"] for r in records):
                print(f"      {derived.get(tk, '—')}  {tk}")
        else:
            failures.append(
                f"derived {len(set(derived.values()))} distinct ids for {EXPECTED_COUNT} facts — "
                "two facts collide on the natural key and would overwrite each other"
            )
    except Exception as exc:  # noqa: BLE001
        failures.append(f"id derivation failed: {exc}")

    # 8. live reconciliation
    if args.db_url and derived:
        print("\n— live reconciliation (read-only) —")
        try:
            check_live(args.db_url, records, derived, failures)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"live reconciliation failed: {exc}")
    elif args.db_url:
        failures.append("skipped live reconciliation: id derivation did not complete")
    else:
        print("\n(no --db-url: live reconciliation skipped)")

    if failures:
        print(f"\n✖ AIQ-2027 FAIL — {len(failures)} failure(s):")
        for f in failures:
            print(f"    - {f}")
        return 1
    print(f"\n✔ AIQ-2027 PASS — batch {BATCH_ID} landed as reviewable candidates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
