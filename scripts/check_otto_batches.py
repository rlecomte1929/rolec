#!/usr/bin/env python3
"""Delivery gate for Otto research import batches under ``docs/imports/``.

An Otto batch is a directory ``docs/imports/<batch-id>/`` holding a ``manifest.json``,
one NDJSON fact stream, and a ``README.md``. This script is the gate that decides
whether such a batch may be handed over: it enforces the delivery contract every
batch is written to, and it reconciles the manifest against the bytes on disk so a
manifest cannot claim counts the stream does not contain.

Run from the project root::

    python scripts/check_otto_batches.py es-departure-2026-08-22
    python scripts/check_otto_batches.py --all
    python scripts/check_otto_batches.py <batch-id> --json report.json

It needs nothing outside the standard library and touches no network or database,
so it runs in any checkout and in CI.

What is checked, in three sections:

1. DELIVERY CONTRACT, per record.
   ``applies_to.nationality`` present and drawn from {EEA, EU, non-EEA, non-EU} --
   never null; ``applies_to.status`` present; no ``fact_type: "step"`` anywhere in the
   stream (process steps belong to ``requirement_entities``); an absolute https
   ``source_url`` on an official publisher host; a non-empty, substantive
   ``evidence_quote``; ``review_status`` and ``verification_status`` on every record
   matching what the manifest declares for the whole batch; unique ``fact_key``; and
   the loader-facing fields (``target_table``, ``topic_key``, ``fact_type``,
   ``domain_area``, ``confidence_score``) in the shapes ``tools/otto-loader-index.ts``
   actually reads, so nothing is silently coerced on load.

2. MANIFEST RECONCILIATION.
   Record total, line count, every histogram, every declared source's citation count,
   and the fact stream's own size and SHA-256 must agree with the file on disk, and
   every ``*_balanced`` flag the manifest asserts must be true.

3. PROMOTION SIMULATION.
   Re-implements the routing and de-duplication branch of otto-loader v6 so
   "0 unmapped, everything promotes" is measured rather than asserted.

Checks that depend on optional conventions (a nationality-scoping self-audit, an
assertion-mode marker) run only when the batch actually carries those fields, so a
batch is never failed for not using a convention it never claimed.

Exit codes: 0 all batches pass, 1 at least one check failed, 2 usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMPORTS_DIR = os.path.join(PROJECT_ROOT, "docs", "imports")

EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2

#: The contract's closed vocabulary. `null` is the failure this list exists to catch.
ALLOWED_NATIONALITY = {"EEA", "EU", "non-EEA", "non-EU"}

#: Mirrors tools/otto-loader-index.ts. A value outside these sets is not rejected by
#: the loader, it is silently rewritten ("other"), which is worse: the batch loads
#: and the taxonomy is wrong. So the gate rejects it here.
LOADER_FACT_TYPES = {
    "eligibility", "document", "step", "deadline", "fee", "where_to_apply", "account", "other",
}
LOADER_DOMAIN_AREAS = {
    "immigration", "registration", "tax", "social_security", "healthcare", "housing", "other",
    "vehicle", "vehicle_import", "domestic_move", "financial", "employer_compliance", "pet",
}

#: A source is official when its host is a state/government host or a named public
#: authority. Suffix rules cover the general case; the explicit set covers authorities
#: on their own domains (an ayuntamiento, a social-security body, a revenue office).
OFFICIAL_HOST_SUFFIXES = (
    ".gob.es", ".gov.ie", ".gov.uk", ".europa.eu", ".gouv.fr", ".bund.de", ".gc.ca", ".gov",
)
OFFICIAL_HOSTS = {
    # Spain
    "sede.agenciatributaria.gob.es", "www.agenciatributaria.gob.es", "www3.agenciatributaria.gob.es",
    "agenciatributaria.gob.es", "www.seg-social.es", "seg-social.es", "sede.seg-social.gob.es",
    "www.boe.es", "boe.es", "www.ine.es", "ine.es", "sede.madrid.es", "www.madrid.es",
    "seuelectronica.ajuntament.barcelona.cat", "www.valencia.es", "sede.valencia.es",
    "extranjeros.inclusion.gob.es", "www.inclusion.gob.es",
    # Ireland
    "www.irishimmigration.ie", "irishimmigration.ie", "enterprise.gov.ie", "www.enterprise.gov.ie",
    "www.revenue.ie", "revenue.ie", "www.gov.ie", "gov.ie", "services.mywelfare.ie",
    "www.mywelfare.ie", "www2.healthservice.hse.ie", "www.hse.ie", "www.citizensinformation.ie",
    "citizensinformation.ie", "www.welfare.ie",
}

MIN_QUOTE_CHARS = 25


class Result:
    """Collects PASS/FAIL/SKIP lines for one batch and remembers whether it failed."""

    def __init__(self, batch_id: str) -> None:
        self.batch_id = batch_id
        self.lines: List[Tuple[str, str, str]] = []
        self.failed = 0
        self.passed = 0
        self.skipped = 0

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        self.lines.append(("PASS" if ok else "FAIL", label, detail))
        if ok:
            self.passed += 1
        else:
            self.failed += 1
        return ok

    def skip(self, label: str, detail: str = "") -> None:
        self.lines.append(("SKIP", label, detail))
        self.skipped += 1

    def note(self, text: str) -> None:
        self.lines.append(("NOTE", text, ""))

    def section(self, title: str) -> None:
        self.lines.append(("SECTION", title, ""))

    def render(self) -> str:
        out = []
        for kind, label, detail in self.lines:
            if kind == "SECTION":
                out.append("\n--- %s ---" % label)
            elif kind == "NOTE":
                out.append("  %s" % label)
            else:
                out.append("  [%s] %s%s" % (kind, label, (" - " + detail) if detail else ""))
        return "\n".join(out)


def host_of(url: str) -> str:
    m = re.match(r"^https?://([^/?#]+)", url or "")
    return m.group(1).lower() if m else ""


def is_official(url: str) -> bool:
    host = host_of(url)
    if not host:
        return False
    if host in OFFICIAL_HOSTS:
        return True
    return any(host == s.lstrip(".") or host.endswith(s) for s in OFFICIAL_HOST_SUFFIXES)


def load_stream(path: str) -> Tuple[List[Dict[str, Any]], int, bytes]:
    raw = open(path, "rb").read()
    text = raw.decode("utf-8")
    lines = [l for l in text.splitlines() if l.strip()]
    records = []
    for i, line in enumerate(lines, 1):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise ValueError("line %d is not valid JSON: %s" % (i, e))
    return records, len(lines), raw


def find_stream(batch_dir: str, manifest: Dict[str, Any]) -> Optional[str]:
    """Prefer the file the manifest declares; fall back to a lone .ndjson."""
    for entry in manifest.get("files", []) or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("role") == "fact_stream" or str(entry.get("format", "")).lower() == "ndjson":
            candidate = os.path.join(batch_dir, entry.get("path", ""))
            if os.path.isfile(candidate):
                return candidate
    found = sorted(f for f in os.listdir(batch_dir) if f.endswith(".ndjson"))
    return os.path.join(batch_dir, found[0]) if len(found) == 1 else None


def histogram(values) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for v in values:
        key = str(v)
        out[key] = out.get(key, 0) + 1
    return out


def check_contract(r: Result, records: List[Dict[str, Any]], manifest: Dict[str, Any]) -> None:
    r.section("SECTION 1: DELIVERY CONTRACT")
    n = len(records)

    bad = [rec.get("fact_key") for rec in records
           if (rec.get("applies_to") or {}).get("nationality") not in ALLOWED_NATIONALITY]
    r.check(not bad, "every record has applies_to.nationality from %s, never null"
            % sorted(ALLOWED_NATIONALITY), "%d/%d ok" % (n - len(bad), n) + (" first: %s" % bad[:3] if bad else ""))

    bad = [rec.get("fact_key") for rec in records if not (rec.get("applies_to") or {}).get("status")]
    r.check(not bad, "every record has a non-empty applies_to.status", "%d/%d ok" % (n - len(bad), n))

    declared_status = {str((rec.get("applies_to") or {}).get("status")) for rec in records}
    r.check(len(declared_status) == 1, "applies_to.status is uniform across the stream",
            "values: %s" % sorted(declared_status))

    steps = [rec.get("fact_key") for rec in records if rec.get("fact_type") == "step"]
    r.check(not steps, "no fact_type='step' record in the fact stream", "%d found" % len(steps))

    bad = [rec.get("fact_key") for rec in records
           if not str(rec.get("source_url", "")).startswith("https://")]
    r.check(not bad, "every source_url is an absolute https URL", "%d/%d ok" % (n - len(bad), n))

    bad = [(rec.get("fact_key"), host_of(rec.get("source_url", ""))) for rec in records
           if not is_official(rec.get("source_url", ""))]
    r.check(not bad, "every source_url is on an official publisher host",
            "hosts: %s" % sorted({h for _, h in bad}) if bad else
            "hosts: %s" % sorted({host_of(rec["source_url"]) for rec in records}))

    bad = [rec.get("fact_key") for rec in records if not str(rec.get("evidence_quote") or "").strip()]
    r.check(not bad, "every record carries a non-empty evidence_quote", "%d/%d ok" % (n - len(bad), n))

    lengths = [len(str(rec.get("evidence_quote") or "")) for rec in records]
    short = [rec.get("fact_key") for rec in records
             if len(str(rec.get("evidence_quote") or "")) < MIN_QUOTE_CHARS]
    r.check(not short, "every evidence_quote is a substantive quotation (>= %d chars)" % MIN_QUOTE_CHARS,
            "shortest %d chars" % (min(lengths) if lengths else 0))

    bad = [rec.get("fact_key") for rec in records if not str(rec.get("fact_text") or "").strip()]
    r.check(not bad, "every record carries non-empty fact_text", "%d/%d ok" % (n - len(bad), n))

    expected_review = manifest.get("review_status_all")
    r.check(expected_review is not None, "manifest declares review_status_all", str(expected_review))
    if expected_review is not None:
        bad = [rec.get("fact_key") for rec in records
               if (rec.get("applies_to") or {}).get("review_status") != expected_review]
        r.check(not bad, "every record's review_status matches manifest review_status_all",
                "%d/%d are %r" % (n - len(bad), n, expected_review))

    expected_verif = manifest.get("verification_status_all")
    r.check(expected_verif is not None, "manifest declares verification_status_all", str(expected_verif))
    if expected_verif is not None:
        bad = [rec.get("fact_key") for rec in records
               if (rec.get("applies_to") or {}).get("verification_status") != expected_verif]
        r.check(not bad, "every record's verification_status matches manifest verification_status_all",
                "%d/%d are %r" % (n - len(bad), n, expected_verif))

    keys = [rec.get("fact_key") for rec in records]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    r.check(not dupes, "fact_key is unique across the stream", "%d duplicates %s" % (len(dupes), dupes[:3]))

    bad = [rec.get("fact_key") for rec in records
           if "requirement_fact" not in str(rec.get("target_table", "")).lower()]
    r.check(not bad, "every record declares target_table=requirement_facts at record level",
            "%d/%d ok" % (n - len(bad), n))

    bad = [rec.get("fact_key") for rec in records
           if not rec.get("topic_key")
           or rec.get("topic_key") != (rec.get("entity") or {}).get("topic_key")]
    r.check(not bad, "topic_key is present at record level and identical inside entity",
            "%d/%d ok" % (n - len(bad), n))

    bad = sorted({str(rec.get("fact_type")) for rec in records
                  if rec.get("fact_type") not in LOADER_FACT_TYPES})
    r.check(not bad, "every fact_type is in the loader's own set (nothing silently coerced)",
            "offending: %s" % bad if bad else "%d distinct" % len({rec["fact_type"] for rec in records}))

    bad = sorted({str(rec.get("domain_area")) for rec in records
                  if rec.get("domain_area") not in LOADER_DOMAIN_AREAS})
    r.check(not bad, "every domain_area is in the loader's allow-list (nothing downgraded to 'other')",
            "offending: %s" % bad if bad else "%d distinct" % len({rec["domain_area"] for rec in records}))

    bad = [rec.get("fact_key") for rec in records
           if not isinstance(rec.get("confidence_score"), (int, float))
           or not 0 <= float(rec["confidence_score"]) <= 1]
    r.check(not bad, "confidence_score is numeric in [0,1] (the field the loader reads)",
            "%d/%d ok" % (n - len(bad), n))

    # Optional convention: a nationality-scoping self-audit.
    if any("nationality_scope_basis" in (rec.get("applies_to") or {}) for rec in records):
        r.section("SECTION 1a: NATIONALITY-SCOPING SELF-AUDIT")
        bad = [rec.get("fact_key") for rec in records
               if not (rec.get("applies_to") or {}).get("nationality_scope_basis")]
        r.check(not bad, "every record declares applies_to.nationality_scope_basis",
                "%d/%d classified" % (n - len(bad), n))
        audit = ((manifest.get("dependencies") or {}).get("S1_nationality_scoping_self_audit") or {})
        defs = audit.get("basis_definitions") or {}
        r.check(bool(defs), "manifest defines the bases under S1_nationality_scoping_self_audit.basis_definitions",
                "%d definitions" % len(defs))
        used = histogram((rec.get("applies_to") or {}).get("nationality_scope_basis") for rec in records)
        for basis in sorted(used):
            r.check(basis in defs, "basis %r resolves to a manifest definition" % basis)
        declared = audit.get("bases") or {}
        r.check({k: int(v) for k, v in declared.items()} == used,
                "manifest S1 basis counts match the stream", "manifest %s vs stream %s" % (declared, used))
        r.check(sum(used.values()) == n, "the bases sum to the record total",
                "%d vs %d" % (sum(used.values()), n))
        if any("nationality_scope_axis" in (rec.get("applies_to") or {}) for rec in records):
            axis_defs = audit.get("axis_definitions") or {}
            axes = histogram((rec.get("applies_to") or {}).get("nationality_scope_axis") for rec in records)
            r.check(bool(axis_defs), "manifest defines the axes under axis_definitions",
                    "%d definitions" % len(axis_defs))
            for axis in sorted(axes):
                r.check(axis in axis_defs, "axis %r resolves to a manifest definition" % axis)
            r.check(sum(axes.values()) == n, "the axes sum to the record total",
                    "%d vs %d" % (sum(axes.values()), n))
            neutral = axes.get("nationality_neutral", 0)
            r.check(neutral == used.get("audience_scope", 0),
                    "axis 'nationality_neutral' agrees with basis 'audience_scope'",
                    "%d vs %d" % (neutral, used.get("audience_scope", 0)))

    # Optional convention: conditional assertions must say what they are conditional on.
    conditional = [rec for rec in records
                   if (rec.get("applies_to") or {}).get("assertion_mode") == "conditional"]
    if conditional:
        bad = [rec.get("fact_key") for rec in conditional
               if not str((rec.get("applies_to") or {}).get("conditional_on") or "").strip()]
        r.check(not bad, "every conditional record states applies_to.conditional_on",
                "%d conditional records" % len(conditional))


def check_manifest(r: Result, records: List[Dict[str, Any]], line_count: int,
                   raw: bytes, stream_path: str, manifest: Dict[str, Any]) -> None:
    r.section("SECTION 2: MANIFEST RECONCILIATION")
    n = len(records)
    counts = manifest.get("counts") or {}

    r.check(counts.get("records_total") == n, "counts.records_total == records in the stream",
            "%s vs %d" % (counts.get("records_total"), n))
    r.check(counts.get("ndjson_lines") == line_count, "counts.ndjson_lines == non-empty lines in the stream",
            "%s vs %d" % (counts.get("ndjson_lines"), line_count))
    if "fact_type_step" in counts:
        r.check(counts["fact_type_step"] == 0, "counts.fact_type_step == 0", str(counts["fact_type_step"]))
    if "nationality_null_or_missing" in counts:
        r.check(counts["nationality_null_or_missing"] == 0, "counts.nationality_null_or_missing == 0",
                str(counts["nationality_null_or_missing"]))

    for field, getter in (
        ("by_topic", lambda rec: (rec.get("applies_to") or {}).get("topic")),
        ("by_fact_type", lambda rec: rec.get("fact_type")),
        ("by_domain_area", lambda rec: rec.get("domain_area")),
    ):
        declared = counts.get(field)
        if declared is None:
            r.skip("counts.%s not declared" % field)
            continue
        actual = histogram(getter(rec) for rec in records)
        r.check(sum(declared.values()) == n, "sum(counts.%s) == records_total" % field,
                "%d vs %d" % (sum(declared.values()), n))
        r.check({k: int(v) for k, v in declared.items()} == actual,
                "counts.%s histogram matches the stream" % field,
                "" if {k: int(v) for k, v in declared.items()} == actual
                else "manifest %s vs stream %s" % (declared, actual))

    sources = manifest.get("sources") or []
    if sources:
        total_citing = sum(int(s.get("records_citing", 0)) for s in sources)
        r.check(total_citing == n, "sum(sources[].records_citing) == records_total", "%d vs %d" % (total_citing, n))
        actual = histogram(rec.get("source_url") for rec in records)
        mismatched = [s.get("source_url") for s in sources
                      if int(s.get("records_citing", 0)) != actual.get(s.get("source_url"), 0)]
        r.check(not mismatched, "every source's records_citing matches the stream",
                "%d distinct source URLs" % len(actual) if not mismatched else "off: %s" % mismatched[:2])
        undeclared = sorted(set(actual) - {s.get("source_url") for s in sources})
        r.check(not undeclared, "every source_url used in the stream is declared in the manifest",
                "undeclared: %s" % undeclared[:2] if undeclared else "%d declared" % len(sources))
    else:
        r.skip("manifest declares no sources[] block")

    entry = None
    for candidate in manifest.get("files", []) or []:
        if isinstance(candidate, dict) and candidate.get("path") == os.path.basename(stream_path):
            entry = candidate
            break
    if entry is None:
        r.check(False, "manifest files[] declares the fact stream", os.path.basename(stream_path))
    else:
        if "bytes" in entry:
            r.check(int(entry["bytes"]) == len(raw), "manifest files[].bytes matches the file on disk",
                    "%s vs %d" % (entry["bytes"], len(raw)))
        if "sha256" in entry:
            digest = hashlib.sha256(raw).hexdigest()
            r.check(str(entry["sha256"]).lower() == digest, "manifest files[].sha256 matches the file on disk",
                    "" if str(entry["sha256"]).lower() == digest else "manifest %s vs actual %s"
                    % (entry["sha256"], digest))
        if "records" in entry:
            r.check(int(entry["records"]) == n, "manifest files[].records matches the stream",
                    "%s vs %d" % (entry["records"], n))

    recon = manifest.get("reconciliation") or {}
    flags = {k: v for k, v in recon.items() if isinstance(v, bool)}
    false_flags = sorted(k for k, v in flags.items() if not v)
    if flags:
        r.check(not false_flags, "every boolean reconciliation flag the manifest asserts is true",
                "%d flags" % len(flags) if not false_flags else "false: %s" % false_flags)
    else:
        r.skip("manifest declares no reconciliation flags")


def check_promotion(r: Result, records: List[Dict[str, Any]]) -> None:
    """Re-implement the routing/dedupe branch of tools/otto-loader-index.ts."""
    r.section("SECTION 3: PROMOTION SIMULATION (otto-loader v6)")
    unrouted = mapped_new = dup_in_batch = skip_no_source = skip_no_dest = skip_no_text = 0
    seen = set()
    entities = set()
    for rec in records:
        table = str(rec.get("target_table") or "").lower()
        if "requirement_fact" not in table:
            unrouted += 1
            continue
        dest = (rec.get("entity") or {}).get("destination_country") or rec.get("destination_country")
        text = (rec.get("fact_text") or rec.get("body") or rec.get("requirement")
                or rec.get("text") or rec.get("fact_value"))
        if not rec.get("source_url"):
            skip_no_source += 1
            continue
        if not dest:
            skip_no_dest += 1
            continue
        if not text:
            skip_no_text += 1
            continue
        topic = rec.get("topic_key") or (rec.get("entity") or {}).get("topic_key") or rec.get("domain_area")
        bkey = "%s|%s|%s|%s" % (dest, topic, rec.get("fact_key"),
                               json.dumps(rec.get("applies_to") or {}, sort_keys=True))
        if bkey in seen:
            dup_in_batch += 1
            continue
        seen.add(bkey)
        entities.add((dest, topic))
        mapped_new += 1

    r.note("records routed to requirement_facts : %d" % (len(records) - unrouted))
    r.note("UNMAPPED (loader 'unrouted' bucket) : %d" % unrouted)
    r.note("mapped_new (would promote)          : %d" % mapped_new)
    r.note("dup_in_batch                        : %d" % dup_in_batch)
    r.note("skip_no_source / no_dest / no_text  : %d / %d / %d"
           % (skip_no_source, skip_no_dest, skip_no_text))
    r.note("requirement_entities auto-created   : %d" % len(entities))
    r.check(unrouted == 0, "0 unmapped (every record routes to requirement_facts)", str(unrouted))
    r.check(mapped_new == len(records), "every record promotes",
            "%d/%d" % (mapped_new, len(records)))
    r.check(dup_in_batch == 0, "no duplicate (dest|topic|fact_key|applies_to) inside the batch",
            str(dup_in_batch))
    r.check(skip_no_source == skip_no_dest == skip_no_text == 0,
            "no record skipped for missing source_url / destination / fact_text")


def check_batch(batch_id: str) -> Result:
    r = Result(batch_id)
    batch_dir = os.path.join(IMPORTS_DIR, batch_id)
    if not os.path.isdir(batch_dir):
        r.check(False, "batch directory exists", os.path.relpath(batch_dir, PROJECT_ROOT))
        return r
    r.check(True, "batch directory exists", os.path.relpath(batch_dir, PROJECT_ROOT))

    manifest_path = os.path.join(batch_dir, "manifest.json")
    if not r.check(os.path.isfile(manifest_path), "manifest.json is present"):
        return r
    try:
        manifest = json.load(open(manifest_path, encoding="utf-8"))
    except json.JSONDecodeError as e:
        r.check(False, "manifest.json parses as JSON", str(e))
        return r
    r.check(True, "manifest.json parses as JSON")
    r.check(os.path.isfile(os.path.join(batch_dir, "README.md")), "README.md is present")
    r.check(manifest.get("batch_id") == batch_id, "manifest batch_id matches the directory name",
            "%r vs %r" % (manifest.get("batch_id"), batch_id))

    stream_path = find_stream(batch_dir, manifest)
    if stream_path is None:
        r.skip("no NDJSON fact stream in this batch",
               "manifest declares none and the directory holds no single .ndjson; "
               "record-level checks do not apply to a reference batch")
        return r
    try:
        records, line_count, raw = load_stream(stream_path)
    except ValueError as e:
        r.check(False, "fact stream is valid NDJSON", str(e))
        return r
    r.check(True, "fact stream is valid NDJSON",
            "%s, %d records" % (os.path.basename(stream_path), len(records)))
    if not r.check(bool(records), "fact stream is not empty"):
        return r

    # Sections 1-3 grade a batch against the otto-loader v6 delivery contract: record-level
    # `target_table`, `applies_to.nationality`, `fact_type` from the loader's set,
    # `confidence_score`, the by_* count histograms, the promotion simulation. A batch that
    # never claimed that contract must not be graded by it.
    #
    # `ve-ie-entry-family-2026-08-20` is the case. It predates this gate, carries a different
    # and legitimate shape (`fact_uid`, `applies_to_nationality_classes`, no `fact_type` or
    # `confidence_score`), targets `public.requirement_items` rather than the loader's
    # `requirement_facts`, and is validated by its own `scripts/verify_aiq_2027_ve_ie_load.py`,
    # which passes. Graded here it scored 18 PASS / 15 FAIL — every failure being "you are not
    # the other batch's schema".
    #
    # It landed anyway because CI gates only CHANGED batches and #1971 did not touch it, so the
    # false universality stayed invisible until the first edit to that batch. Dispatch on what
    # the manifest actually declares, and say plainly what was not checked — a silent skip and a
    # false failure are both worse than a stated one.
    if not manifest.get("loader"):
        r.skip("batch does not declare the otto-loader contract",
               "no manifest 'loader' block, so the v6 record contract, the by_* count "
               "histograms and the promotion simulation do not apply; NDJSON validity, "
               "README, batch_id and manifest parsing were still checked")
        return r

    check_contract(r, records, manifest)
    check_manifest(r, records, line_count, raw, stream_path, manifest)
    check_promotion(r, records)
    return r


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Gate Otto research import batches in docs/imports/.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("batch", nargs="*", help="batch id(s), i.e. directory name(s) under docs/imports/")
    p.add_argument("--all", action="store_true", help="check every batch under docs/imports/")
    p.add_argument("--json", help="also write the structured result to this path")
    p.add_argument("--min-records", type=int, default=1,
                   help="fail a batch with fewer than this many records (default: 1)")
    args = p.parse_args(argv)

    if args.all:
        if not os.path.isdir(IMPORTS_DIR):
            sys.stderr.write("no docs/imports/ directory under %s\n" % PROJECT_ROOT)
            return EXIT_USAGE
        batches = sorted(d for d in os.listdir(IMPORTS_DIR)
                         if os.path.isdir(os.path.join(IMPORTS_DIR, d)))
    else:
        batches = args.batch
    if not batches:
        p.print_usage(sys.stderr)
        sys.stderr.write("give at least one batch id, or --all\n")
        return EXIT_USAGE

    report = {"project_root": PROJECT_ROOT, "batches": []}
    failed_any = False
    for batch_id in batches:
        r = check_batch(batch_id)
        stream = find_stream(os.path.join(IMPORTS_DIR, batch_id), {}) \
            if os.path.isdir(os.path.join(IMPORTS_DIR, batch_id)) else None
        if stream:
            try:
                records, _, _ = load_stream(stream)
                if len(records) < args.min_records:
                    r.check(False, "batch has at least %d records" % args.min_records, str(len(records)))
            except ValueError:
                pass
        print("=" * 78)
        print("BATCH: %s" % batch_id)
        print("=" * 78)
        print(r.render())
        verdict = "PASS" if r.failed == 0 else "FAIL"
        print("\nVERDICT: %s - %d checks passed, %d failed, %d skipped"
              % (verdict, r.passed, r.failed, r.skipped))
        report["batches"].append({
            "batch_id": batch_id, "verdict": verdict,
            "passed": r.passed, "failed": r.failed, "skipped": r.skipped,
            "checks": [{"kind": k, "label": l, "detail": d} for k, l, d in r.lines
                       if k in ("PASS", "FAIL", "SKIP")],
        })
        failed_any = failed_any or r.failed > 0

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print("\nreport written to %s" % args.json)
    return EXIT_FAILED if failed_any else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
