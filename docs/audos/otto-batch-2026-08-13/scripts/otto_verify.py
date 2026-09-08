#!/usr/bin/env python3
"""otto_verify.py — quality gates for Otto (Audos) card output.

A card is not complete when the agent reports writing a file. It is not complete when the
file is found in git either. It is complete when the CONTENT survives the gates below.

Every gate here traces to a measured failure in this project, not to a preference:

  * 38 registry-evidenced rows were reported into being for a file that was never written.
  * 4 accreditations named a bar association while carrying a 9-digit company registration
    number and evidence pointing at a commercial directory.
  * A "convert-only, change not a single value" second pass visibly re-queried business
    registers and compiled fresh entries.
  * `registry_lookup` is not a legal verification_method and violates a CHECK constraint.

Stdlib only. Uses `jsonschema` if it happens to be installed; otherwise a built-in
validator covering the subset the schemas use. No network unless --check-urls.

  usage:
    python3 scripts/otto_verify.py --batch otto-batch.json
    python3 scripts/otto_verify.py --batch otto-batch.json --card OTTO-G --check-urls
    python3 scripts/otto_verify.py --batch otto-batch.json --json > report.json

  exit: 0 all gates passed · 1 a gate failed · 2 bad invocation
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from urllib.parse import urlparse

# --------------------------------------------------------------------------- constants

# Never acceptable as accreditation evidence. A supplier's own site is fine in
# website_url; it can never be the value of source_url.
DENY_HOSTS = (
    "google.com", "google.co", "goo.gl", "maps.app.goo.gl", "yelp.com", "yelp.",
    "trustpilot.com", "linkedin.com", "facebook.com", "instagram.com", "x.com",
    "twitter.com", "pagesjaunes.fr", "societe.com", "verif.com", "infogreffe.fr",
    "wikipedia.org", "medium.com", "reddit.com", "quora.com", "tripadvisor.",
    "clutch.co", "g2.com", "capterra.com", "glassdoor.",
)

# Aggregator shapes that pass a host check but are still not registers.
DENY_PATH_HINTS = ("top-10", "top10", "best-", "-best", "/blog/", "/blogs/", "listicle")

# Official / statutory domains for corridor and lead-time cards.
OFFICIAL_HINTS = (
    ".gov", ".gov.uk", ".gouv.fr", "gov.ie", ".govt.", "europa.eu", "europarl.europa.eu",
    "udi.no", "skatteetaten.no", "politiet.no", "nav.no", "brreg.no", "tilsynsradet.no",
    "revenue.ie", "enterprise.gov.ie", "irishimmigration.ie", "welfare.ie",
    "citizensinformation.ie", "centralbank.ie", "psr.ie", "dsp.gov.ie",
    "uscis.gov", "travel.state.gov", "dol.gov", "legislation.gov.uk",
    "service-public.fr", "legifrance.gouv.fr", "insee.fr", "urssaf.fr",
    "bamf.de", "auswaertiges-amt.de", "cleiss.fr", "mohre.gov.ae", "mofa.go.jp",
)

BANNED_MARKETING = (
    "revolutionary", "game-changing", "game changing", "seamless", "supercharge",
    "best-in-class", "best in class", "exciting chapter", "unlock the", "end-to-end",
)

# Hard gate in CLAUDE.md. A false or premature compliance claim is itself a legal liability.
BANNED_COMPLIANCE = (
    "eu ai act ready", "ai act ready", "ai act compliant", "eu ai act compliant",
    "ai act certified", "ai act conformant", "high-risk ai system", "high risk ai system",
    "gdpr certified", "gdpr compliant badge", "iso 27001 certified",
)

BODY_IS_PROFESSIONAL = re.compile(
    r"advokatforening|advokat|bar association|barreau|law society|solicitor|notaire|"
    r"chamber|kammer|ordre des|institute|chartered|psra|eura|fidi|iam\b|tilsyn",
    re.I,
)

# Norwegian organisation numbers and French SIREN are both 9 digits.
NINE_DIGIT = re.compile(r"^\s*\d{3}[\s.]?\d{3}[\s.]?\d{3}\s*$")

SEARCH_FORM = re.compile(
    r"/(search|search-for-members|find-a-[a-z]+|finn|sok|s%C3%B8k|recherche|annuaire|"
    r"member-search|directory)/?$",
    re.I,
)

NUMERIC_KEYS = (
    "expected_duration_days", "published_current_days", "statutory_days",
    "cost_amount", "amount", "fee_amount", "salary_threshold_amount",
)

CSV_ROW_KEYS_FOR_DIFF = ("company_name", "service_category", "source_url")


# ----------------------------------------------------------------- tiny schema validator

class SchemaError(Exception):
    pass


def _resolve(ref: str, root: dict):
    if not ref.startswith("#/"):
        raise SchemaError(f"only local $ref supported, got {ref!r}")
    node = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        node = node[part]
    return node


def _validate(inst, schema: dict, root: dict, path: str = "$") -> list[str]:
    """Minimal JSON Schema subset: the keywords otto-outputs.schema.json actually uses."""
    errs: list[str] = []

    if "$ref" in schema:
        return _validate(inst, _resolve(schema["$ref"], root), root, path)

    t = schema.get("type")
    if t:
        types = t if isinstance(t, list) else [t]
        ok = False
        for tt in types:
            if tt == "object":
                ok |= isinstance(inst, dict)
            elif tt == "array":
                ok |= isinstance(inst, list)
            elif tt == "string":
                ok |= isinstance(inst, str)
            elif tt == "integer":
                ok |= isinstance(inst, int) and not isinstance(inst, bool)
            elif tt == "number":
                ok |= isinstance(inst, (int, float)) and not isinstance(inst, bool)
            elif tt == "boolean":
                ok |= isinstance(inst, bool)
            elif tt == "null":
                ok |= inst is None
        if not ok:
            return [f"{path}: expected {t}, got {type(inst).__name__}"]

    if "const" in schema and inst != schema["const"]:
        errs.append(f"{path}: must be {schema['const']!r}, got {inst!r}")

    if "enum" in schema and inst not in schema["enum"]:
        errs.append(f"{path}: {inst!r} not in {schema['enum']}")

    if isinstance(inst, str):
        if "minLength" in schema and len(inst) < schema["minLength"]:
            errs.append(f"{path}: shorter than {schema['minLength']}")
        pat = schema.get("pattern")
        if pat and not re.search(pat, inst):
            errs.append(f"{path}: {inst!r} does not match /{pat}/")

    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "minimum" in schema and inst < schema["minimum"]:
            errs.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and inst > schema["maximum"]:
            errs.append(f"{path}: above maximum {schema['maximum']}")

    if isinstance(inst, list):
        if "minItems" in schema and len(inst) < schema["minItems"]:
            errs.append(f"{path}: {len(inst)} items, need >= {schema['minItems']}")
        if "maxItems" in schema and len(inst) > schema["maxItems"]:
            errs.append(f"{path}: {len(inst)} items, need <= {schema['maxItems']}")
        if "items" in schema:
            for i, v in enumerate(inst):
                errs += _validate(v, schema["items"], root, f"{path}[{i}]")

    if isinstance(inst, dict):
        for req in schema.get("required", []):
            if req not in inst:
                errs.append(f"{path}: missing required key {req!r}")
        props = schema.get("properties", {})
        for k, v in inst.items():
            if k in props:
                errs += _validate(v, props[k], root, f"{path}.{k}")
            else:
                matched = False
                for pat, sub in schema.get("patternProperties", {}).items():
                    if re.search(pat, k):
                        errs += _validate(v, sub, root, f"{path}.{k}")
                        matched = True
                if not matched and schema.get("additionalProperties") is False:
                    errs.append(f"{path}: unexpected key {k!r}")

    return errs


def validate_records(records, schema_ptr: str, base_dir: str) -> list[str]:
    fname, _, frag = schema_ptr.partition("#")
    with open(os.path.join(base_dir, fname), encoding="utf-8") as fh:
        root = json.load(fh)
    sub = _resolve("#" + frag, root) if frag else root
    out: list[str] = []
    for i, rec in enumerate(records):
        out += _validate(rec, sub, root, f"record[{i}]")
    return out


# ------------------------------------------------------------------------------ helpers

def walk_dicts(obj, path="$"):
    if isinstance(obj, dict):
        yield path, obj
        for k, v in obj.items():
            yield from walk_dicts(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_dicts(v, f"{path}[{i}]")


def walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_strings(v)


def host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def load_output(repo_root: str, rel_path: str):
    """Return (actual_path, records, raw_text) checking BOTH the un-doubled and doubled path."""
    candidates = [
        os.path.join(repo_root, rel_path),
        os.path.join(repo_root, "audos-workspace-776786", rel_path),
    ]
    actual = next((p for p in candidates if os.path.isfile(p)), None)
    if actual is None:
        return None, None, None

    with open(actual, encoding="utf-8-sig") as fh:
        raw = fh.read()

    if actual.endswith(".csv"):
        rows = list(csv.DictReader(raw.splitlines()))
        return actual, rows, raw
    if actual.endswith(".json"):
        data = json.loads(raw)
        return actual, (data if isinstance(data, list) else [data]), raw
    return actual, [], raw


def parse_thread_capture(text: str, fb: dict):
    """Extract records from an in-thread fallback block."""
    blocks = fb.get("blocks") or [{"begin": fb.get("begin"), "end": fb.get("end"),
                                   "format": fb.get("format")}]
    out = []
    for b in blocks:
        if not b.get("begin"):
            continue
        m = re.search(re.escape(b["begin"]) + r"(.*?)" + re.escape(b["end"]), text, re.S)
        if not m:
            continue
        body = m.group(1).strip()
        if b.get("format") == "json":
            try:
                data = json.loads(body)
                out += data if isinstance(data, list) else [data]
            except json.JSONDecodeError:
                pass
        else:  # pipe-separated, header line first
            lines = [ln for ln in body.splitlines() if ln.strip()]
            if len(lines) >= 2:
                hdr = [h.strip() for h in lines[0].split("|")]
                for ln in lines[1:]:
                    vals = [v.strip() for v in ln.split("|")]
                    out.append(dict(zip(hdr, vals)))
    return out


# -------------------------------------------------------------------------------- gates

def gate_non_empty(recs, spec):
    n = len(recs)
    lo, hi = spec.get("min_records"), spec.get("max_records")
    if n == 0 and not spec.get("may_be_header_only"):
        return [f"0 records — a file that exists but holds no data is the failure this "
                f"workflow exists to catch"]
    if lo is not None and n < lo and not (n == 0 and spec.get("may_be_header_only")):
        return [f"{n} records, manifest requires >= {lo}"]
    if hi is not None and n > hi:
        return [f"{n} records, manifest allows <= {hi} — suspect padding"]
    return []


def gate_enum_discipline(recs):
    errs = []
    legal_vm = {"public_registry", "supplier_document", "manual_email", "directory_listing"}
    legal_cat = {"housing_agencies", "movers", "banks", "legal_admin", "tax_finance"}
    for _, d in walk_dicts(recs):
        vm = (d.get("verification_method") or "").strip()
        if vm and vm not in legal_vm:
            extra = " — this is the exact value that violates our CHECK constraint" \
                if vm == "registry_lookup" else ""
            errs.append(f"verification_method={vm!r} is not legal{extra}")
        cat = (d.get("service_category") or "").strip()
        if cat and cat not in legal_cat:
            errs.append(f"service_category={cat!r} is not a database enum value")
    return errs


def gate_sourcing_rule(recs):
    errs = []
    for _, d in walk_dicts(recs):
        for key in ("source_url", "evidence_url", "real_entity_evidence_url"):
            u = (d.get(key) or "").strip()
            if not u:
                continue
            h = host_of(u)
            if any(bad in h for bad in DENY_HOSTS):
                errs.append(f"{key} host {h!r} is not a register "
                            f"({d.get('company_name') or d.get('supplier_name') or '?'})")
            low = u.lower()
            if any(hint in low for hint in DENY_PATH_HINTS):
                errs.append(f"{key} looks like an aggregator/listicle: {u}")
    return errs


def gate_source_not_own_site(recs):
    errs = []
    for _, d in walk_dicts(recs):
        s, w = (d.get("source_url") or "").strip(), (d.get("website_url") or "").strip()
        if s and w and host_of(s) and host_of(s) == host_of(w):
            errs.append(f"source_url and website_url share host {host_of(s)!r} — a "
                        f"supplier's own site cannot be its accreditation evidence "
                        f"({d.get('company_name', '?')})")
    return errs


def gate_no_org_number(recs):
    errs = []
    for _, d in walk_dicts(recs):
        body = (d.get("accreditation_body") or d.get("body")
                or d.get("recommended_body") or "")
        num = (d.get("accreditation_number") or d.get("membership_number")
               or d.get("real_membership_number") or "")
        if num and NINE_DIGIT.match(str(num)) and BODY_IS_PROFESSIONAL.search(body):
            errs.append(
                f"{str(num).strip()!r} is a 9-digit company/organisation number but "
                f"accreditation_body is {body!r}. A company register confirms a company "
                f"exists; it does not evidence membership. This is exactly AIQ-1828."
            )
    return errs


def gate_evidence_not_search_form(recs):
    errs = []
    for _, d in walk_dicts(recs):
        for key in ("evidence_url", "source_url", "real_entity_evidence_url",
                    "example_entity_url", "member_url"):
            u = (d.get(key) or "").strip()
            if u and SEARCH_FORM.search(urlparse(u).path or ""):
                errs.append(f"{key} is a bare search/landing page with no entity: {u}")
    return errs


def gate_label_discipline(recs):
    errs = []
    for p, d in walk_dicts(recs):
        if "label" in d and d["label"] not in ("VERIFIED", "CLAIM"):
            errs.append(f"{p}.label={d['label']!r} — must be VERIFIED or CLAIM")
    labelled = sum(1 for _, d in walk_dicts(recs) if "label" in d)
    if labelled == 0:
        errs.append("no [VERIFIED]/[CLAIM] labels anywhere — Otto cannot see our repo, "
                    "database or CDN, and unlabelled claims about them have been wrong before")
    return errs


def gate_checked_date(recs):
    errs = []
    for p, d in walk_dicts(recs):
        has_src = any((d.get(k) or "").strip() for k in ("source_url", "dpa_url", "url"))
        has_date = any((str(d.get(k) or "")).strip()
                       for k in ("checked_date", "published_from_date", "date"))
        if has_src and not has_date:
            errs.append(f"{p}: sourced but carries no checked_date — legal and government "
                        f"pages change")
    return errs


def gate_official_domains(recs):
    errs = []
    for p, d in walk_dicts(recs):
        for key in ("source_url", "duration_source_url", "cost_source_url", "url"):
            u = (d.get(key) or "").strip()
            if not u:
                continue
            h = host_of(u)
            if not any(hint in h for hint in OFFICIAL_HINTS):
                errs.append(f"{p}.{key} host {h!r} is not an official/statutory domain")
    return errs


def gate_number_requires_source(recs):
    errs = []
    for p, d in walk_dicts(recs):
        vals = [k for k in NUMERIC_KEYS
                if d.get(k) not in (None, "", [], {})]
        if not vals:
            continue
        srcs = [k for k in d if k.endswith("source_url") and (d.get(k) or "").strip()]
        if not srcs:
            errs.append(f"{p}: has {vals} but no source_url — an authoritative-sounding "
                        f"wrong number is the failure we cannot ship")
    return errs


def gate_provenance(recs):
    return [f"{p}.provenance={d['provenance']!r} — must be 'representative'; an "
            f"agent-authored 'verified' is a fabricated SME sign-off"
            for p, d in walk_dicts(recs)
            if "provenance" in d and d["provenance"] != "representative"]


def _scan_strings(recs, needles, why):
    errs, seen = [], set()
    for s in walk_strings(recs):
        low = s.lower()
        for n in needles:
            if n in low and n not in seen:
                seen.add(n)
                errs.append(f"{why}: {n!r} appears in the output")
    return errs


def gate_no_marketing(recs):
    return _scan_strings(recs, BANNED_MARKETING, "banned marketing register")


def gate_no_compliance_claim(recs):
    return _scan_strings(recs, BANNED_COMPLIANCE,
                         "PROHIBITED COMPLIANCE CLAIM (CLAUDE.md hard gate)")


def gate_thread_diff(recs, card, repo_root):
    fb = card.get("thread_fallback") or {}
    cap = fb.get("capture_as")
    if not cap:
        return ["SKIP: card declares no thread fallback"]
    path = os.path.join(repo_root, cap)
    if not os.path.isfile(path):
        return [f"SKIP: no thread capture at {cap} — paste Otto's in-thread block there "
                f"BEFORE authorising a write task. A measured 'convert-only' pass drifted "
                f"into fresh research; without the capture there is nothing to diff against."]
    with open(path, encoding="utf-8") as fh:
        thread = parse_thread_capture(fh.read(), fb)
    if not thread:
        return [f"SKIP: could not parse a block out of {cap}"]

    errs = []
    if len(thread) != len(recs):
        errs.append(f"thread block has {len(thread)} records, synced file has {len(recs)} "
                    f"— the write task was supposed to convert, not re-research")

    def key(d):
        return tuple((d.get(k) or "").strip().lower() for k in CSV_ROW_KEYS_FOR_DIFF)

    if all(isinstance(r, dict) for r in recs + thread):
        t, f = {key(r) for r in thread}, {key(r) for r in recs}
        if t and f and t != {("", "", "")}:
            for extra in sorted(f - t)[:5]:
                errs.append(f"in file but NOT in thread (invented on the second pass): {extra}")
            for missing in sorted(t - f)[:5]:
                errs.append(f"in thread but NOT in file (dropped on the second pass): {missing}")
    return errs


def gate_url_resolves(recs, timeout=8):
    """Check every evidence link resolves.

    Distinguishes a dead link from a dead network. If EVERY url fails at the connection
    layer, the machine has no egress (the desktop Cowork VM does not) and the gate reports
    a SKIP rather than damning good data. A gate that cries wolf is a gate people learn to
    ignore, which is worse than not having it.
    """
    import urllib.error
    import urllib.request
    errs, conn_fail, checked, seen = [], 0, 0, set()
    for _, d in walk_dicts(recs):
        for key in ("source_url", "evidence_url", "dpa_url", "url", "egqs_url",
                    "real_entity_evidence_url", "member_url", "example_member_url",
                    "duration_source_url", "cost_source_url", "dpf_listing_url"):
            u = (d.get(key) or "").strip()
            if not u or u in seen:
                continue
            seen.add(u)
            checked += 1
            req = urllib.request.Request(u, method="GET", headers={
                "User-Agent": "ReloPass-otto-verify/1.0 (link check)"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    if r.status >= 400:
                        errs.append(f"HTTP {r.status}: {u}")
            except urllib.error.HTTPError as e:
                if e.code not in (403, 405, 429):  # bot-walls, not dead links
                    errs.append(f"HTTP {e.code}: {u}")
            except Exception as e:
                conn_fail += 1
                errs.append(f"unreachable ({type(e).__name__}): {u}")

    if checked and conn_fail == checked:
        return [f"SKIP: all {checked} URLs failed at the connection layer — this machine "
                f"has no network egress, so the result says nothing about the links. "
                f"Re-run --check-urls from a shell that can reach the internet."]
    return errs


def gate_min_bytes(raw, spec):
    """Prose deliverables (the gaps files) are judged by substance, not record count."""
    n = len(raw or "")
    need = spec.get("min_bytes", 40)
    if n < need:
        return [f"{n} bytes, need >= {need} — a gaps file is not optional. "
                f"'NONE' and 'this register is login-gated' are answers; an empty file is not."]
    return []


GATES = {
    "min_bytes": lambda ctx: gate_min_bytes(ctx["raw"], ctx["spec"]),
    "non_empty": lambda ctx: gate_non_empty(ctx["recs"], ctx["spec"]),
    "schema": lambda ctx: (validate_records(ctx["recs"], ctx["spec"]["schema"], ctx["base"])
                           if ctx["spec"].get("schema") else ["SKIP: no schema declared"]),
    "enum_discipline": lambda ctx: gate_enum_discipline(ctx["recs"]),
    "sourcing_rule": lambda ctx: gate_sourcing_rule(ctx["recs"]),
    "source_not_own_site": lambda ctx: gate_source_not_own_site(ctx["recs"]),
    "no_org_number_as_accreditation": lambda ctx: gate_no_org_number(ctx["recs"]),
    "evidence_url_not_search_form": lambda ctx: gate_evidence_not_search_form(ctx["recs"]),
    "label_discipline": lambda ctx: gate_label_discipline(ctx["recs"]),
    "checked_date_present": lambda ctx: gate_checked_date(ctx["recs"]),
    "official_source_domains": lambda ctx: gate_official_domains(ctx["recs"]),
    "number_requires_source": lambda ctx: gate_number_requires_source(ctx["recs"]),
    "provenance_representative": lambda ctx: gate_provenance(ctx["recs"]),
    "no_marketing_copy": lambda ctx: gate_no_marketing(ctx["recs"]),
    "no_compliance_claim": lambda ctx: gate_no_compliance_claim(ctx["recs"]),
    "thread_diff": lambda ctx: gate_thread_diff(ctx["recs"], ctx["card"], ctx["repo"]),
    "url_resolves": lambda ctx: (gate_url_resolves(ctx["recs"]) if ctx["check_urls"]
                                 else ["SKIP: pass --check-urls to run this"]),
}


# --------------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch", default="otto-batch.json")
    ap.add_argument("--card", default="all")
    ap.add_argument("--repo-root", default=None)
    ap.add_argument("--check-urls", action="store_true")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args()

    if not os.path.isfile(args.batch):
        print(f"FAIL  no batch manifest at {args.batch}", file=sys.stderr)
        return 2
    base = os.path.dirname(os.path.abspath(args.batch)) or "."
    with open(args.batch, encoding="utf-8") as fh:
        batch = json.load(fh)

    repo = args.repo_root or os.environ.get("RELOPASS_REPO") or os.getcwd()
    want = args.card.upper()
    cards = [c for c in batch["cards"] if want in ("ALL", c["card_id"].upper())]
    if not cards:
        print(f"FAIL  no such card: {args.card}", file=sys.stderr)
        return 2

    report, failed = [], False

    for card in cards:
        cid = card["card_id"]
        for spec in card["outputs"]:
            entry = {"card": cid, "path": spec["path"], "gates": {}}
            actual, recs, raw = load_output(repo, spec["path"])

            if actual is None:
                if spec.get("required"):
                    entry["gates"]["file_present"] = {
                        "ok": False,
                        "detail": [
                            "not found at the expected path, and not at the DOUBLED path "
                            "either — run " + os.path.join(
                                os.path.relpath(base, repo), "scripts/otto_recover.sh")
                            + f" {cid} first"]}
                    failed = True
                else:
                    entry["gates"]["file_present"] = {"ok": True, "detail": ["optional, absent"]}
                report.append(entry)
                continue

            entry["actual_path"] = os.path.relpath(actual, repo)
            entry["records"] = len(recs)
            entry["gates"]["file_present"] = {"ok": True, "detail": [f"{len(recs)} records"]}

            # Prose outputs (the gaps/notes files) carry no records, so the structured
            # gates are meaningless on them. Judge them on substance instead.
            applicable = (["min_bytes"] if spec["format"] == "md"
                          else card["quality_gates"])

            for gname in applicable:
                if gname == "file_present":
                    continue
                fn = GATES.get(gname)
                if fn is None:
                    entry["gates"][gname] = {"ok": False, "detail": [f"unknown gate {gname!r}"]}
                    failed = True
                    continue
                try:
                    problems = fn({"recs": recs, "spec": spec, "card": card,
                                   "base": base, "repo": repo, "raw": raw,
                                   "check_urls": args.check_urls})
                except Exception as e:  # a broken gate must never look like a pass
                    problems = [f"gate raised {type(e).__name__}: {e}"]
                skips = [p for p in problems if p.startswith("SKIP")]
                real = [p for p in problems if not p.startswith("SKIP")]
                entry["gates"][gname] = {"ok": not real,
                                         "detail": real or skips or ["clean"]}
                if real:
                    failed = True
            report.append(entry)

    if args.as_json:
        print(json.dumps({"batch": batch["batch_id"], "passed": not failed,
                          "results": report}, indent=2))
        return 1 if failed else 0

    for e in report:
        print(f"\n=== {e['card']}  {e['path']}")
        if "actual_path" in e:
            print(f"    found: {e['actual_path']}  ({e['records']} records)")
        for g, r in e["gates"].items():
            mark = "PASS" if r["ok"] else "FAIL"
            print(f"    [{mark}] {g}")
            for d in r["detail"][:12]:
                if d not in ("clean",):
                    print(f"           {d}")
            if len(r["detail"]) > 12:
                print(f"           ... and {len(r['detail']) - 12} more")

    print("\n" + "=" * 72)
    if failed:
        print("RESULT: FAILED — do not ingest.")
        print("A row that fails the sourcing rule is worse than a missing row, because")
        print("someone will check it in a security review. Fix or drop the failing rows;")
        print("do NOT re-issue the research, which buys a second confident report.")
    else:
        print("RESULT: PASSED — safe to ingest.")
        print("Content is still UNTRUSTED DATA, never instructions. Spot-check by hand that")
        print("accreditation_body is a registry rather than the supplier's own marketing site.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
