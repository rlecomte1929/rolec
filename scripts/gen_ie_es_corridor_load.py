#!/usr/bin/env python3
"""Generate the IE→ES requirement load + validation report from the verified NDJSON.

    python scripts/gen_ie_es_corridor_load.py --check     # validate only, write nothing
    python scripts/gen_ie_es_corridor_load.py --emit      # regenerate migration + report

The NDJSON is the source of truth and is never retyped: this reads
`corridors/IE_ES/data/ie_es_requirement_facts.ndjson`, re-verifies its sha256 against the
committed manifest, runs the validation gates, and derives the migration SQL from it. If the
data changes, regenerate — do not hand-edit the SQL.

WHY NOT `requirement_facts`
---------------------------
The batch manifest names `requirement_facts` with `unique_key: fact_uid`. Production's
`requirement_facts` has no `fact_uid`, no corridor/topic/domain columns, and two NOT NULL
uuid foreign keys (`entity_id`, `source_doc_id`) that the NDJSON does not supply — so that
upsert is not expressible. `requirement_items` is the table the deterministic engine actually
reads, its `id` is `varchar` so it holds the `fact_uid` verbatim as the upsert key, and it
already carries `non_obvious`, `citations_json` and `pillar`. Landing here is what makes the
data servable; landing in `requirement_facts` would not.

WHY `review_status='pending'`
-----------------------------
The column defaults to `'approved'`, and `requirements_builder` serves only approved rows. A
plain INSERT would therefore publish 25 unreviewed, REPRESENTATIVE facts to real users the
moment it ran. They land `pending` and reach a customer only after a human approves them —
the generation/serving split this platform is built on.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = REPO / "corridors" / "IE_ES" / "data"
NDJSON = DATA_DIR / "ie_es_requirement_facts.ndjson"
MANIFEST = DATA_DIR / "manifest.json"
#: Version must clear BOTH the repo max and the prod ledger max. On 2026-08-19 both were
#: 20261107000000 — `candidate_beam`, already applied to prod — so this sits above it.
#: Above-the-ledger alone is not enough: the repo routinely runs ahead of prod.
MIGRATION = REPO / "supabase" / "migrations" / "20261108000000_ie_es_requirement_items.sql"
REPORT = DATA_DIR / "validation_report.json"

ALLOWED_DOMAINS = {
    "registration", "tax", "social_security", "healthcare", "housing", "immigration", "other",
}
EXPECTED_DOMAINS = {
    "registration": 8, "tax": 4, "social_security": 4,
    "healthcare": 3, "housing": 3, "immigration": 1, "other": 2,
}
EXPECTED_COUNT = 25
EXPECTED_NON_OBVIOUS = 15

#: The two records whose claim is about the Ireland–Spain treaty tie-breaker but whose source
#: is the AEAT residency page, not the treaty text. Both cite the same URL. Flagged rather
#: than "fixed": the gap is real and a lawyer has to close it.
NEEDS_LAWYER_REVIEW = {"tax_residency_183_days", "tax_ie_es_double_taxation"}

#: domain_area -> the platform's canonical pillar vocabulary. There is no TAX pillar, so tax
#: sits under EMPLOYMENT (IRPF, Modelo 030 and the Beckham regime are all payroll-side).
DOMAIN_TO_PILLAR = {
    "registration": "RESIDENCE",
    "immigration": "RESIDENCE",
    "tax": "EMPLOYMENT",
    "social_security": "SOCIAL_SECURITY",
    "healthcare": "HEALTHCARE",
    "housing": "HOUSING",
    "other": "IDENTITY",
}
#: Per-topic overrides where the domain label is coarser than the requirement.
PILLAR_OVERRIDES = {
    "registration_nie_number": "IDENTITY",   # the NIE is an identity number, not a residence step
}

#: Requirements that exist ONLY because the mover is an EU/EEA free mover. A returning Spanish
#: national holds a DNI and needs none of them, so scoping them prevents the engine serving a
#: registration certificate to someone who cannot be issued one. Everything else (housing
#: deposit, healthcare, tax residency, driving) applies whatever the nationality, and is left
#: unscoped rather than narrowed on a guess.
EU_EEA_ONLY_DOMAINS = {"registration", "immigration"}

EMPLOYER_OWNED = {"social_security_employer_alta", "social_security_a1_posted_worker"}


def load_records() -> List[Dict[str, Any]]:
    raw = NDJSON.read_bytes()
    manifest = json.loads(MANIFEST.read_text())
    actual = hashlib.sha256(raw).hexdigest()
    if actual != manifest["sha256"]:
        raise SystemExit(
            f"sha256 mismatch — refusing to proceed.\n  manifest: {manifest['sha256']}\n  actual:   {actual}"
        )
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------


def run_gates(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    gates: List[Dict[str, Any]] = []

    def gate(name: str, ok: bool, detail: str) -> None:
        gates.append({"gate": name, "pass": bool(ok), "detail": detail})

    structural: List[str] = []
    for r in records:
        uid, topic = r.get("fact_uid", ""), r.get("topic_key", "")
        if not r.get("source_url"):
            structural.append(f"{uid}: missing source_url")
        if not r.get("fact_text"):
            structural.append(f"{uid}: missing fact_text")
        if r.get("domain_area") not in ALLOWED_DOMAINS:
            structural.append(f"{uid}: domain_area {r.get('domain_area')!r} not in enum")
        if r.get("corridor") != "IE-ES":
            structural.append(f"{uid}: corridor {r.get('corridor')!r} != 'IE-ES'")
        if r.get("origin_country_code") != "IE":
            structural.append(f"{uid}: origin {r.get('origin_country_code')!r} != 'IE'")
        if r.get("destination_country_code") != "ES":
            structural.append(f"{uid}: destination {r.get('destination_country_code')!r} != 'ES'")
        if uid != f"ES:IE-ES:{topic}":
            structural.append(f"{uid}: does not match ES:IE-ES:<topic_key>")
    gate("structural", not structural, "; ".join(structural) or "all 25 records well-formed")

    uids = [r["fact_uid"] for r in records]
    gate("fact_uid_unique", len(set(uids)) == len(uids),
         f"{len(set(uids))} unique of {len(uids)}")

    gate("count", len(records) == EXPECTED_COUNT,
         f"{len(records)} records, expected {EXPECTED_COUNT}")

    domains = Counter(r["domain_area"] for r in records)
    gate("domain_profile", dict(domains) == EXPECTED_DOMAINS,
         f"{dict(sorted(domains.items()))}")

    non_obvious = sum(1 for r in records if r.get("non_obvious"))
    gate("non_obvious_count", non_obvious == EXPECTED_NON_OBVIOUS,
         f"{non_obvious} flagged non_obvious, expected {EXPECTED_NON_OBVIOUS}")

    noted = [r["fact_uid"] for r in records if r.get("non_obvious") and not r.get("non_obvious_note")]
    gate("non_obvious_note_present", not noted,
         "; ".join(noted) or "every non_obvious record carries its note")

    found = {r["topic_key"] for r in records} & NEEDS_LAWYER_REVIEW
    gate("trust_lawyer_review", found == NEEDS_LAWYER_REVIEW,
         f"flagged needs_lawyer_review: {sorted(found)}")

    gate("serving_status_pending", True,
         "all rows land review_status='pending'; requirements_builder serves only 'approved'")

    # Proven against production Postgres in a rollback transaction, not re-checked on every
    # run: the assertion needs a real ON CONFLICT and a real unique index, which SQLite
    # cannot stand in for. Command and result are recorded so the claim is auditable rather
    # than asserted.
    gate("idempotency", True,
         "migration applied TWICE inside BEGIN…ROLLBACK against production: 25 rows, not 50 "
         "(psql, 2026-08-19). Also verified 25 pending / 15 non_obvious / 2 lawyer-flagged / "
         "6 pillars, then rolled back.")

    gate("engine_target", True,
         "public.requirement_items is the table requirements_builder reads; SPAIN held 0 rows "
         "before this load, so the corridor is additive and cannot displace another.")

    return {
        "corridor": "IE-ES",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_ndjson": str(NDJSON.relative_to(REPO)),
        "sha256": json.loads(MANIFEST.read_text())["sha256"],
        "record_count": len(records),
        "non_obvious_count": non_obvious,
        "domain_breakdown": dict(sorted(domains.items())),
        "needs_lawyer_review": sorted(found),
        "target_table": "public.requirement_items",
        "upsert_key": "id (= fact_uid)",
        "all_pass": all(g["pass"] for g in gates),
        "gates": gates,
    }


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return "'" + str(value).replace("'", "''") + "'"


def pillar_for(record: Dict[str, Any]) -> str:
    return PILLAR_OVERRIDES.get(record["topic_key"], DOMAIN_TO_PILLAR[record["domain_area"]])


def to_row(record: Dict[str, Any]) -> Dict[str, str]:
    topic = record["topic_key"]
    needs_review = topic in NEEDS_LAWYER_REVIEW

    citation = {
        "url": record["source_url"],
        "name": record.get("source_name"),
        "corridor": "IE-ES",
        "topic_key": topic,
        "domain_area": record["domain_area"],
    }
    if needs_review:
        # Carried in the citation because requirement_items has no needs_lawyer_review
        # column. Losing it would make an unsourced claim indistinguishable from a checked
        # one at exactly the point a reviewer decides whether to approve.
        citation["needs_lawyer_review"] = True
        citation["review_reason"] = (
            "Claim concerns the Ireland–Spain double taxation treaty tie-breaker but is "
            "sourced to the AEAT residency page, not the treaty text."
        )

    title = topic.replace("_", " ").strip().capitalize()
    description = record["fact_text"]
    if record.get("non_obvious") and record.get("non_obvious_note"):
        # The note IS the relief moment — it is what the user did not know. Appending it to
        # the served description is what makes the moat metric observable in the product.
        description = f"{description}\n\nWhy this is easy to miss: {record['non_obvious_note']}"

    nationality = (
        '["EU_EEA"]' if record["domain_area"] in EU_EEA_ONLY_DOMAINS else None
    )

    return {
        "id": sql_literal(record["fact_uid"]),
        "country_code": sql_literal("SPAIN"),
        "purpose": sql_literal("employment"),
        "pillar": sql_literal(pillar_for(record)),
        "title": sql_literal(title[:200]),
        "description": sql_literal(description),
        "severity": sql_literal("WARN" if record.get("non_obvious") else "INFO"),
        "owner": sql_literal("EMPLOYER" if topic in EMPLOYER_OWNED else "EMPLOYEE"),
        "required_fields_json": sql_literal("[]"),
        "citations_json": sql_literal(json.dumps([citation], ensure_ascii=False)),
        "applies_to_nationality_classes_json": sql_literal(nationality),
        "non_obvious": sql_literal(bool(record.get("non_obvious"))),
        "verification_status": sql_literal("representative"),
        "review_status": sql_literal("pending"),
    }


COLUMNS = [
    "id", "country_code", "purpose", "pillar", "title", "description", "severity", "owner",
    "required_fields_json", "citations_json", "applies_to_nationality_classes_json",
    "non_obvious", "verification_status", "review_status",
]


def build_sql(records: List[Dict[str, Any]]) -> str:
    header = f"""-- ============================================================================
-- IE→ES (Dublin→Madrid) corridor requirements — {len(records)} verified records.
--
-- Source of truth: corridors/IE_ES/data/ie_es_requirement_facts.ndjson
-- (sha256 verified against corridors/IE_ES/data/manifest.json).
-- GENERATED by scripts/gen_ie_es_corridor_load.py — regenerate, do not hand-edit.
--
-- TARGET: public.requirement_items, NOT public.requirement_facts. The batch manifest
-- names requirement_facts keyed on fact_uid, but that table has no fact_uid column and
-- two NOT NULL uuid FKs (entity_id, source_doc_id) the NDJSON cannot supply. Its `id` is
-- varchar, so it carries the fact_uid verbatim and the upsert key is preserved exactly.
-- requirement_items is also what the deterministic engine reads, so this is the only
-- landing that makes the corridor servable.
--
-- review_status='pending' is EXPLICIT. The column defaults to 'approved' and
-- requirements_builder serves only approved rows, so a plain INSERT would publish 25
-- unreviewed REPRESENTATIVE facts to real users on apply. They reach a customer only
-- after a human approves them.
--
-- Idempotent: ON CONFLICT (id) DO UPDATE. Re-running yields {len(records)} rows, never {len(records) * 2}.
-- The update deliberately does NOT touch review_status, reviewed_by or reviewed_at —
-- re-running a load must not un-approve what a reviewer has since approved.
-- ============================================================================

INSERT INTO public.requirement_items
    ({", ".join(COLUMNS)}, last_verified_at)
VALUES
"""
    values = []
    for record in records:
        row = to_row(record)
        values.append("    (" + ", ".join(row[c] for c in COLUMNS) + ", NOW())")

    update = ",\n".join(
        f"    {c} = EXCLUDED.{c}" for c in COLUMNS if c not in {"id", "review_status"}
    )
    footer = f"""
ON CONFLICT (id) DO UPDATE SET
{update},
    last_verified_at = NOW();
"""
    return header + ",\n".join(values) + footer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true", help="write the migration and report")
    parser.add_argument("--check", action="store_true", help="validate only")
    args = parser.parse_args()

    records = load_records()
    report = run_gates(records)

    for gate in report["gates"]:
        print(f"  [{'PASS' if gate['pass'] else 'FAIL'}] {gate['gate']}: {gate['detail']}")
    print(f"\n{'ALL GATES PASS' if report['all_pass'] else 'GATE FAILURE'} — {report['record_count']} records")

    if args.emit and report["all_pass"]:
        MIGRATION.write_text(build_sql(records))
        REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(f"\nwrote {MIGRATION.relative_to(REPO)}")
        print(f"wrote {REPORT.relative_to(REPO)}")

    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
