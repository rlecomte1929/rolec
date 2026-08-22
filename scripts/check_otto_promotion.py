#!/usr/bin/env python3
"""Pre-promotion collision check for Otto import batches (the online half of the gate).

``scripts/check_otto_batches.py`` is the *offline* delivery gate: by design it touches no
network or database, so it can prove a batch is internally well-formed and would route,
but it cannot tell whether the batch's keys already exist in the target tables. A batch
that passes the gate can still be a no-op (or a partial duplicate) on load.

This tool closes that gap without needing live DB access, by simulating otto-loader v6's
routing and de-duplication against a **workspace DB export**
(``data/workspace-db-export/<date>/requirement_facts.json`` +
``requirement_entities.json``). It reimplements the promotion-relevant branch of
``supabase/functions/otto-loader/index.ts`` — verified byte-identical to the deployed
loader on every routing/dedup path as of 2026-08-22:

  * routing:            target_table contains "requirement_fact"
  * destination:        entity.destination_country || destination_country || <corridor tail>
  * topic:              topic_key || entity.topic_key || domain_area
  * existing-fact key:  dest | entity.topic_key | fact_key   (facts joined to entities)
  * existing-entity key: dest | topic_key
  * in-batch key:       dest | topic | fact_key | applies_to

Usage::

    python scripts/check_otto_promotion.py <batch-id> --export data/workspace-db-export/<date>/
    python scripts/check_otto_promotion.py --all    --export data/workspace-db-export/<date>/

Exit 0 when every batch would promote cleanly (0 unrouted and, unless --allow-existing,
0 dup_existing); 1 otherwise; 2 on usage error.

WARNING: a DB export is a point-in-time snapshot. Re-export immediately before a real
loader run — a stale export can miss keys loaded since it was taken, turning a real
collision into a false "clean".
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMPORTS_DIR = os.path.join(PROJECT_ROOT, "docs", "imports")
EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2

# Mirrors supabase/functions/otto-loader/index.ts. Kept honest by
# scripts/check_gate_loader_sync.py (which compares the gate's copies to the loader).
ALLOWED_DOMAINS = {
    "immigration", "registration", "tax", "social_security", "healthcare", "housing",
    "other", "vehicle", "vehicle_import", "domestic_move", "financial", "employer_compliance", "pet",
}
FACT_TYPES = {
    "eligibility", "document", "step", "deadline", "fee", "where_to_apply", "account", "other",
}
_CN = {"spain": "ES", "ireland": "IE"}


# ---- faithful reimplementation of the loader's helper functions --------------------
def _clean_code(s: str) -> str:
    return "".join(ch for ch in s if ch.isalpha())


def iso2(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if len(s) == 2:
        return s.upper()
    if s.lower() in _CN:
        return _CN[s.lower()]
    c = _clean_code(s)
    if len(c) in (2, 3):
        return c.upper()
    return None


def _entity(r: Dict[str, Any]) -> Dict[str, Any]:
    e = r.get("entity")
    return e if isinstance(e, dict) else {}


def fact_text(r: Dict[str, Any]):
    return r.get("fact_text") or r.get("body") or r.get("requirement") or r.get("text") or r.get("fact_value")


def map_domain(v: Any) -> str:
    s = str(v if v is not None else "immigration").lower()
    return s if s in ALLOWED_DOMAINS else "other"


def fact_domain(r: Dict[str, Any]) -> str:
    return map_domain(_entity(r).get("domain_area") or r.get("domain_area") or r.get("domain") or "immigration")


def fact_topic(r: Dict[str, Any]):
    return r.get("topic_key") or _entity(r).get("topic_key") or fact_domain(r)


def fact_key(r: Dict[str, Any]):
    if r.get("fact_key"):
        return r["fact_key"]
    if r.get("dedupe_key"):
        return str(r["dedupe_key"]).split("|")[-1]
    return str(r["fact_type"]) if r.get("fact_type") else "fact"


def fact_type(v: Any) -> str:
    s = str(v or "").lower()
    if s in FACT_TYPES:
        return s
    if s == "timeline":
        return "deadline"
    return "other"


def _corridor_tail(v: Any) -> Optional[str]:
    corr = str(v or "")
    if not corr:
        return None
    seg = corr.split("-")[-1] if "-" in corr else corr
    return iso2(seg)


def fact_dest(r: Dict[str, Any]) -> Optional[str]:
    e = _entity(r)
    c = iso2(e.get("destination_country")) or iso2(r.get("destination_country")) or iso2(r.get("destination_country_code"))
    if c:
        return c
    dk = str(r.get("dedupe_key") or "")
    if dk:
        head = dk.split("|")[0]
        c = iso2(head.split("-")[-1] if "-" in head else head)
        if c:
            return c
    return _corridor_tail(r.get("corridor"))


# ---- I/O ---------------------------------------------------------------------------
def load_stream(path: str) -> List[Dict[str, Any]]:
    recs = []
    for i, line in enumerate((l for l in open(path, encoding="utf-8").read().splitlines() if l.strip()), 1):
        try:
            recs.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise ValueError("line %d is not valid JSON: %s" % (i, e))
    return recs


def find_stream(batch_dir: str) -> Optional[str]:
    manifest_path = os.path.join(batch_dir, "manifest.json")
    if os.path.isfile(manifest_path):
        try:
            manifest = json.load(open(manifest_path, encoding="utf-8"))
            for entry in manifest.get("files", []) or []:
                if isinstance(entry, dict) and (
                    entry.get("role") == "fact_stream" or str(entry.get("format", "")).lower() == "ndjson"
                ):
                    cand = os.path.join(batch_dir, entry.get("path", ""))
                    if os.path.isfile(cand):
                        return cand
        except json.JSONDecodeError:
            pass
    found = sorted(f for f in os.listdir(batch_dir) if f.endswith(".ndjson"))
    return os.path.join(batch_dir, found[0]) if len(found) == 1 else None


def load_export_list(path: str) -> List[Dict[str, Any]]:
    d = json.load(open(path, encoding="utf-8"))
    if isinstance(d, list):
        return d
    for k in ("data", "rows", "records"):
        if isinstance(d.get(k), list):
            return d[k]
    for v in d.values():
        if isinstance(v, list):
            return v
    return []


def _entity_dest(e: Dict[str, Any]) -> Optional[str]:
    c = iso2(e.get("destination_country")) if e.get("destination_country") else None
    return c or _corridor_tail(e.get("corridor"))


def build_existing_sets(export_dir: str) -> Tuple[set, set]:
    """Rebuild the loader's existing-key sets from a workspace DB export."""
    ents = load_export_list(os.path.join(export_dir, "requirement_entities.json"))
    facts = load_export_list(os.path.join(export_dir, "requirement_facts.json"))
    ent_keys, by_id = set(), {}
    for e in ents:
        dd, tk = _entity_dest(e), e.get("topic_key")
        if dd and tk:
            ent_keys.add("%s|%s" % (dd, tk))
        for idk in ("id", "entity_id"):
            if e.get(idk) is not None:
                by_id.setdefault(e[idk], e)
    fact_keys = set()
    for f in facts:
        e = by_id.get(f.get("entity_id"))
        if e:
            dd, tk = _entity_dest(e), e.get("topic_key")
        else:  # fall back to the fact's own corridor/topic if the join is missing
            dd, tk = _corridor_tail(f.get("corridor")), f.get("topic_key")
        fk = f.get("fact_key")
        if dd and tk and fk:
            fact_keys.add("%s|%s|%s" % (dd, tk, fk))
    return ent_keys, fact_keys


# ---- simulation --------------------------------------------------------------------
def simulate(records, ent_keys, fact_keys):
    r = {"routed": 0, "unrouted": 0, "mapped_new": 0, "dup_in_batch": 0, "dup_existing": 0,
         "skip_no_source": 0, "skip_no_dest": 0, "skip_no_text": 0,
         "domain_downgraded": [], "fact_type_coerced": [],
         "entities_new": set(), "entities_existing": set(), "dup_existing_keys": []}
    seen = set()
    for rec in records:
        tt = str(rec.get("target_table") or "").lower()
        if "requirement_fact" not in tt:
            r["unrouted"] += 1
            continue
        r["routed"] += 1
        cc, txt = fact_dest(rec), fact_text(rec)
        if not rec.get("source_url"):
            r["skip_no_source"] += 1; continue
        if not cc:
            r["skip_no_dest"] += 1; continue
        if not txt:
            r["skip_no_text"] += 1; continue
        topic, fk, dom = fact_topic(rec), fact_key(rec), fact_domain(rec)
        raw_dom = str(_entity(rec).get("domain_area") or rec.get("domain_area") or rec.get("domain") or "immigration").lower()
        if raw_dom not in ALLOWED_DOMAINS:
            r["domain_downgraded"].append((fk, raw_dom))
        raw_ft = str(rec.get("fact_type") or "").lower()
        if raw_ft and raw_ft not in FACT_TYPES and raw_ft != "timeline":
            r["fact_type_coerced"].append((fk, raw_ft))
        bkey = "%s|%s|%s|%s" % (cc, topic, fk, json.dumps(rec.get("applies_to") or {}, sort_keys=True))
        if bkey in seen:
            r["dup_in_batch"] += 1; continue
        seen.add(bkey)
        ek = "%s|%s" % (cc, topic)
        (r["entities_existing"] if ek in ent_keys else r["entities_new"]).add(ek)
        if ("%s|%s|%s" % (cc, topic, fk)) in fact_keys:
            r["dup_existing"] += 1
            r["dup_existing_keys"].append("%s|%s|%s" % (cc, topic, fk))
            continue
        r["mapped_new"] += 1
    return r


def check_batch(batch_id: str, export_dir: str, allow_existing: bool) -> Tuple[bool, str]:
    lines, failed = [], 0

    def emit(ok, label, detail=""):
        nonlocal failed
        lines.append("  [%s] %s%s" % ("PASS" if ok else "FAIL", label, (" - " + detail) if detail else ""))
        if not ok:
            failed += 1

    batch_dir = os.path.join(IMPORTS_DIR, batch_id)
    header = ["=" * 78, "BATCH: %s   (export: %s)" % (batch_id, os.path.relpath(export_dir, PROJECT_ROOT)), "=" * 78]
    if not os.path.isdir(batch_dir):
        return False, "\n".join(header + ["  [FAIL] batch directory exists - %s" % batch_id])
    stream = find_stream(batch_dir)
    if not stream:
        return True, "\n".join(header + ["  [SKIP] no NDJSON fact stream (reference batch) — nothing to promote"])
    try:
        records = load_stream(stream)
    except ValueError as e:
        return False, "\n".join(header + ["  [FAIL] fact stream is valid NDJSON - %s" % e])

    ent_keys, fact_keys = build_existing_sets(export_dir)
    s = simulate(records, ent_keys, fact_keys)
    n = len(records)

    notes = [
        "  loaded export: %d existing entity keys, %d existing fact keys" % (len(ent_keys), len(fact_keys)),
        "  records routed to requirement_facts : %d" % s["routed"],
        "  UNMAPPED (loader 'unrouted' bucket) : %d" % s["unrouted"],
        "  mapped_new (would insert)           : %d" % s["mapped_new"],
        "  dup_in_batch                        : %d" % s["dup_in_batch"],
        "  dup_existing (already in target)    : %d" % s["dup_existing"],
        "  skip no_source / no_dest / no_text  : %d / %d / %d" % (s["skip_no_source"], s["skip_no_dest"], s["skip_no_text"]),
        "  requirement_entities new / existing : %d / %d" % (len(s["entities_new"]), len(s["entities_existing"])),
    ]
    emit(s["unrouted"] == 0, "0 unmapped (every record routes to requirement_facts)", str(s["unrouted"]))
    emit(s["skip_no_source"] == s["skip_no_dest"] == s["skip_no_text"] == 0,
         "no record skipped for missing source_url / destination / fact_text")
    emit(not s["domain_downgraded"], "no domain_area silently downgraded to 'other'",
         str(s["domain_downgraded"][:5]) if s["domain_downgraded"] else "")
    emit(not s["fact_type_coerced"], "no fact_type silently coerced to 'other'",
         str(s["fact_type_coerced"][:5]) if s["fact_type_coerced"] else "")
    emit(s["dup_in_batch"] == 0, "no duplicate (dest|topic|fact_key|applies_to) inside the batch", str(s["dup_in_batch"]))
    ok_existing = s["dup_existing"] == 0 or allow_existing
    emit(ok_existing, "no collision with keys already in the export%s"
         % (" (allowed)" if allow_existing and s["dup_existing"] else ""),
         "" if s["dup_existing"] == 0 else "%d: %s" % (s["dup_existing"], s["dup_existing_keys"][:3]))
    emit(s["mapped_new"] + s["dup_existing"] + s["dup_in_batch"] == n,
         "every routed record accounted for (new+dup==total)",
         "%d/%d" % (s["mapped_new"] + s["dup_existing"] + s["dup_in_batch"], n))
    lines = notes + [""] + lines  # export notes first, then the PASS/FAIL checks
    verdict = "PASS" if failed == 0 else "FAIL"
    tail = ["", "VERDICT: %s - %d mapped_new, %d dup_existing, %d unmapped, %d entities to create"
            % (verdict, s["mapped_new"], s["dup_existing"], s["unrouted"], len(s["entities_new"]))]
    return failed == 0, "\n".join(header + lines + tail)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Pre-promotion collision check for Otto batches (offline, vs a DB export).")
    p.add_argument("batch", nargs="*", help="batch id(s) under docs/imports/")
    p.add_argument("--all", action="store_true", help="check every batch under docs/imports/")
    p.add_argument("--export", required=True, help="path to a data/workspace-db-export/<date>/ directory")
    p.add_argument("--allow-existing", action="store_true", help="do not fail when a key already exists in the export")
    args = p.parse_args(argv)

    export_dir = os.path.abspath(args.export)
    for req in ("requirement_entities.json", "requirement_facts.json"):
        if not os.path.isfile(os.path.join(export_dir, req)):
            sys.stderr.write("export missing %s under %s\n" % (req, export_dir))
            return EXIT_USAGE

    if args.all:
        if not os.path.isdir(IMPORTS_DIR):
            sys.stderr.write("no docs/imports/ under %s\n" % PROJECT_ROOT)
            return EXIT_USAGE
        batches = sorted(d for d in os.listdir(IMPORTS_DIR) if os.path.isdir(os.path.join(IMPORTS_DIR, d)))
    else:
        batches = args.batch
    if not batches:
        p.print_usage(sys.stderr)
        sys.stderr.write("give at least one batch id, or --all\n")
        return EXIT_USAGE

    failed_any = False
    for b in batches:
        ok, text = check_batch(b, export_dir, args.allow_existing)
        print(text)
        failed_any = failed_any or not ok
    return EXIT_FAILED if failed_any else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
