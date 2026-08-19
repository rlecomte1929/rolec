#!/usr/bin/env python3
"""Corridor fact-pack gate — provenance as a build-failing invariant.

WHY THIS EXISTS

ReloPass serves relocation obligations as fact, so every served fact must be traceable to an
official page, with the date that page publishes about itself and the sentence it actually
says. Twice now that evidence has been gathered by a human and then LOST at the loading
boundary:

  * backend/seeds/requirements/norway.yaml's own header records that its source report
    checked nine items "each with an exact official quote and URL". The file's `citations:`
    key is a bare list of URLs. seed_requirements.py passes those into `citations_json`,
    requirements_builder resolves each citation against a source_records map, and silently
    drops whatever does not resolve.
  * 20261032000000_remove_fake_evidence.sql found the downstream state: 27 rows whose
    visible "evidence" read `Stub content for <url>`, and 6 pointing at example.com.
    20261031000000_frno_source_records.sql measured 90 items carrying citations, of which
    27 resolved, and repaired four by hand.

Neither loss was caught by review, because in both cases the data looked complete. This
guard makes the four checks the 2026-08-19 provenance pass applied by hand into something
CI re-applies on every PR.

THE FOUR CHECKS

  (a)  official source      — the publisher is an authority, via classify_source()
  (a2) jurisdiction match   — the publisher's country IS the pack's jurisdiction
  (a3) binding direction    — a destination binding cites the destination's own authority
  (b)  freshness            — the page's OWN publication date is within --max-age-days
  (c)  completeness         — url + date + verbatim quote, and the quote is not a stub
  (d)  consistency          — dependencies resolve, are acyclic, and never point at staged

(a2) is what makes the origin/destination split enforceable rather than conventional: it is
structurally impossible to file a gov.uk obligation in the Norway pack.

TWO DECISIONS THAT MUST NOT BE RELITIGATED BY EDITING A CONSTANT

  * A NULL publication date on a promoted fact is a FAILURE, not a skip. The original
    TypeScript gate skipped nulls, which meant a pack carrying no dates at all reported
    PASS. See docs/runbooks/corridor-facts/source-verification-2026-08-15.md.
  * The freshness rule is NOT loosened for authorities that publish no date (udi.no,
    skatteetaten.no, politiet.no). The 2026-08-16 decision was to cite a dated official
    restatement instead. Weakening the rule here would silently re-admit undated pages
    across every corridor.

There is no "skip" path and no way to pass by deleting a dependency. The allowlist below is
the only tolerance surface, and it is verified rather than trusted: an entry whose violation
no longer reproduces FAILS, so the file drains instead of becoming a blindfold.

DEPENDENCY NOTE. Unlike check_serving_llm_isolation.py this guard is not stdlib-only: it
needs a real YAML parser, because the evidence it protects is multi-line prose with
significant punctuation. PyYAML is already a pinned backend dependency (backend/
requirements.txt), so the CI job installs one package.

EXIT CODES
  0  every promoted fact passes, or its violation is allowlisted AND still reproduces
  1  a violation; or an allowlist entry that no longer reproduces
  2  bad invocation, unreadable/unparseable pack, or ZERO facts examined

Exit 2 on zero facts is deliberate: "0 violations" and "I found nothing to look at" print
identically, and a guard that silently examines nothing is the shape of a green check that
proves nothing.

USAGE
    python3 scripts/check_corridor_facts.py --root . --run-date 2026-08-19
    python3 scripts/check_corridor_facts.py --json report.json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit

FACTS_DIR = Path("backend/seeds/facts")
CORRIDORS_DIR = Path("corridors")
ALLOWLIST = Path("scripts/corridor_facts_allowlist.txt")

#: Statuses that make a fact CUSTOMER-VISIBLE and therefore gate-bearing.
PROMOTED = ("active", "representative")
#: Staged. Not rendered, not seeded, not gate-bearing — and nothing promoted may depend on it.
STAGED = ("staged",)
VALID_STATUS = PROMOTED + STAGED
VALID_KIND = ("obligation", "preparation_item")

#: `active` demands a primary authority. `representative` also accepts a statutory body that
#: restates a rule published elsewhere (revenue.ie, citizensinformation.ie) — which is
#: exactly the distinction that keeps those Irish facts out of `active`.
ALLOWED_CLASS = {"active": ("official",), "representative": ("official", "semi_official")}

#: Publisher host -> the jurisdiction whose authority it is. Longest suffix wins. Kept in
#: step with parsers._OFFICIAL_* by _selftest_hosts() below, which fails the run if this
#: table ever claims a host classify_source does not recognise.
HOST_JURISDICTION: Dict[str, str] = {
    "gov.uk": "GB", "legislation.gov.uk": "GB",
    "gouv.fr": "FR", "service-public.fr": "FR", "impots.gouv.fr": "FR",
    "legifrance.gouv.fr": "FR", "urssaf.fr": "FR", "ameli.fr": "FR",
    "france-visas.gouv.fr": "FR", "ofii.fr": "FR",
    "gov.ie": "IE", "revenue.ie": "IE", "citizensinformation.ie": "IE",
    "irishimmigration.ie": "IE",
    # rtb.ie (Residential Tenancies Board) is listed as a reviewed trust root in the
    # 2026-08-19 runbook, but parsers.py does not know it and no fact here cites it. It is
    # left OUT rather than added on both sides: widening the importer's trust surface is a
    # decision that should ride with the fact that needs it, not with unused config. The
    # self-test below is what forced this to be a decision instead of a silent mismatch.
    "lovdata.no": "NO", "udi.no": "NO", "skatteetaten.no": "NO", "politiet.no": "NO",
    "nav.no": "NO", "altinn.no": "NO", "helsenorge.no": "NO", "brreg.no": "NO",
    "folkeregisteret.no": "NO", "workinnorway.no": "NO",
    "gob.es": "ES",
    "europa.eu": "EU", "eur-lex.europa.eu": "EU", "ec.europa.eu": "EU",
    "youreurope.europa.eu": "EU", "efta.int": "EU",
}

#: Evidence shapes that LOOK like a capture and are not. Each was found in production.
STUB_QUOTE_PREFIXES = ("stub content for", "placeholder", "tbd", "todo")
STUB_URL_MARKERS = ("example.com", "example.org", "localhost")


class GateError(Exception):
    """A condition that makes the run itself invalid — reported as exit 2, never as a pass."""


# ── loading ───────────────────────────────────────────────────────────────────────────────

def _yaml():
    try:
        import yaml  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover - environment
        raise GateError(
            "PyYAML is required (it is already in backend/requirements.txt): "
            f"pip install pyyaml — {exc}"
        )
    return yaml


def _classify_source(root: Path):
    """The repo's own host classifier. Imported, never restated.

    Two allowlists of official hosts would drift, and the drift would be silent: a host the
    Otto importer trusts but this gate does not would reject a fact that is genuinely fine,
    and the reverse would admit one that is not.
    """
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from backend.imports.otto.parsers import classify_source  # noqa: WPS433
    except Exception as exc:  # pragma: no cover - environment
        raise GateError(f"cannot import classify_source from backend/imports/otto/parsers.py: {exc}")
    return classify_source


def _as_date(value: Any, where: str) -> Optional[_dt.date]:
    if value is None or value == "":
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    try:
        return _dt.date.fromisoformat(str(value).strip())
    except ValueError:
        raise GateError(f"{where}: unparseable date {value!r} (want YYYY-MM-DD)")


def load_packs(root: Path) -> Dict[str, Dict[str, Any]]:
    """canonical key -> fact, with pack context folded in. Raises GateError on bad shape."""
    yaml = _yaml()
    facts: Dict[str, Dict[str, Any]] = {}
    directory = root / FACTS_DIR
    if not directory.is_dir():
        raise GateError(f"missing fact-pack directory {FACTS_DIR}/ under {root}")
    for path in sorted(directory.glob("*.yaml")):
        try:
            pack = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            raise GateError(f"{path}: unparseable YAML — {exc}")
        jurisdiction = pack.get("jurisdiction")
        if not jurisdiction:
            raise GateError(f"{path}: missing top-level `jurisdiction`")
        for index, fact in enumerate(pack.get("facts") or []):
            for required in ("fact_key", "topic", "kind", "status"):
                if not fact.get(required):
                    raise GateError(f"{path} fact #{index + 1}: missing `{required}`")
            if fact["status"] not in VALID_STATUS:
                raise GateError(
                    f"{path}: fact {fact['fact_key']} has status {fact['status']!r}; "
                    f"expected one of {VALID_STATUS}"
                )
            if fact["kind"] not in VALID_KIND:
                raise GateError(
                    f"{path}: fact {fact['fact_key']} has kind {fact['kind']!r}; "
                    f"expected one of {VALID_KIND}"
                )
            key = f"{jurisdiction}:{fact['topic']}:{fact['fact_key']}"
            if key in facts:
                raise GateError(f"duplicate canonical key {key} (second in {path})")
            fact["_key"] = key
            fact["_jurisdiction"] = jurisdiction
            fact["_path"] = str(path.relative_to(root))
            fact["_pack_defaults"] = {
                "purposes": pack.get("default_purposes"),
                "owner": pack.get("default_owner"),
                "severity": pack.get("default_severity"),
            }
            facts[key] = fact
    return facts


def load_bindings(root: Path) -> List[Dict[str, Any]]:
    yaml = _yaml()
    bindings: List[Dict[str, Any]] = []
    for path in sorted((root / CORRIDORS_DIR).glob("*/facts.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            raise GateError(f"{path}: unparseable YAML — {exc}")
        for required in ("corridor_id", "origin_iso", "destination_iso"):
            if not doc.get(required):
                raise GateError(f"{path}: missing top-level `{required}`")
        doc["_path"] = str(path.relative_to(root))
        doc["_dir"] = path.parent
        bindings.append(doc)
    return bindings


def load_allowlist(root: Path) -> Tuple[Dict[Tuple[str, str], str], List[str]]:
    """(key, check_id) -> reason. Missing file is fine; an empty allowlist is the goal."""
    path = root / ALLOWLIST
    entries: Dict[Tuple[str, str], str] = {}
    problems: List[str] = []
    if not path.is_file():
        return entries, problems
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            problems.append(f"{ALLOWLIST}:{lineno}: expected `<key> <check-id>`, got {raw.strip()!r}")
            continue
        entries[(parts[0], parts[1])] = raw.split("#", 1)[1].strip() if "#" in raw else ""
    return entries, problems


# ── the checks ────────────────────────────────────────────────────────────────────────────

def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().lstrip(".")


def _jurisdiction_of(url: str) -> Optional[str]:
    host = _host(url)
    if not host:
        return None
    best: Optional[str] = None
    best_len = -1
    for suffix, iso in HOST_JURISDICTION.items():
        if (host == suffix or host.endswith("." + suffix)) and len(suffix) > best_len:
            best, best_len = iso, len(suffix)
    return best


def _selftest_hosts(classify_source) -> List[str]:
    """Every host this gate claims is an authority must also be one to classify_source.

    Without this the two tables drift apart silently, and a jurisdiction mapping for a host
    the importer rejects would be dead configuration that nothing exercises.
    """
    problems = []
    for suffix in sorted(HOST_JURISDICTION):
        if classify_source(f"https://{suffix}/") == "unofficial":
            problems.append(
                f"HOST_JURISDICTION claims {suffix!r} but classify_source() grades it "
                "unofficial — the tables have drifted; fix parsers.py or this table"
            )
    return problems


def _quote_of(fact: Dict[str, Any]) -> str:
    return ((fact.get("source") or {}).get("evidence_quote") or "")


def _norm(text: str) -> str:
    return " ".join((text or "").split())


def check_fact(fact, *, classify_source, run_date, max_age_days) -> List[Dict[str, str]]:
    key = fact["_key"]
    status = fact["status"]
    out: List[Dict[str, str]] = []
    add = lambda cid, msg: out.append({"check": cid, "key": key, "path": fact["_path"], "message": msg})

    source = fact.get("source") or {}

    # Preparation items are the INVERSE case: no authority publishes them, so they must carry
    # no provenance at all. One that grows a source is a defect, not an improvement — it means
    # someone attached a page to a claim that page does not make.
    if fact["kind"] == "preparation_item":
        if status != "staged":
            add("c-completeness", f"preparation_item must be staged, is {status!r}")
        if source:
            add("c-completeness",
                "preparation_item carries a `source:` block; no authority publishes these, "
                "so provenance must be ABSENT (not nulled)")
        if fact.get("last_verified_date"):
            add("c-completeness", "preparation_item carries last_verified_date")
        return out

    if status not in PROMOTED:
        return out  # staged obligations are not gate-bearing

    url = source.get("url")
    quote = _quote_of(fact)
    published = _as_date(source.get("published_date"), f"{key}.source.published_date")
    retrieved = _as_date(source.get("retrieved_at"), f"{key}.source.retrieved_at")

    # ── (c) completeness ──────────────────────────────────────────────────────────────
    for field, value in (("url", url), ("evidence_quote", quote), ("title", fact.get("title")),
                         ("fact_text", fact.get("fact_text")),
                         ("last_verified_date", fact.get("last_verified_date"))):
        if not value:
            add("c-completeness", f"promoted fact is missing `{field}`")
    if not fact.get("pillar"):
        add("c-completeness", "promoted fact is missing `pillar`")

    lowered = _norm(quote).lower()
    if quote and any(lowered.startswith(p) for p in STUB_QUOTE_PREFIXES):
        add("c-completeness", f"evidence_quote is a placeholder, not a capture: {quote[:60]!r}")
    if url and any(marker in url.lower() for marker in STUB_URL_MARKERS):
        add("c-completeness", f"source url is a placeholder host: {url}")
    # A quote that is really our own summary. Caught by containment either way round, since
    # a paraphrase is usually a near-copy of one or the other.
    if quote and fact.get("fact_text"):
        body = _norm(fact["fact_text"]).lower()
        if lowered and (lowered in body or body in lowered):
            add("c-completeness",
                "evidence_quote duplicates fact_text — a paraphrase presented as a capture")
    declared = source.get("quote_sha256")
    if quote and declared:
        actual = hashlib.sha256(_norm(quote).encode("utf-8")).hexdigest()
        if actual != declared:
            add("c-completeness",
                f"quote_sha256 mismatch: the quote was edited after capture "
                f"(declared {declared[:12]}…, actual {actual[:12]}…)")
    elif quote and not declared:
        add("c-completeness", "promoted fact is missing `quote_sha256`")

    # ── (a) official source, (a2) jurisdiction ────────────────────────────────────────
    if url:
        source_class = classify_source(url)
        allowed = ALLOWED_CLASS[status]
        if source_class not in allowed:
            add("a-official-source",
                f"{_host(url)} grades {source_class!r}; status {status!r} allows {allowed}")
        mapped = _jurisdiction_of(url)
        if mapped is None:
            add("a2-jurisdiction-match",
                f"{_host(url)} is not in HOST_JURISDICTION, so its jurisdiction cannot be "
                "verified — add it there (and to parsers.py if needed) rather than skipping")
        elif mapped != fact["_jurisdiction"]:
            add("a2-jurisdiction-match",
                f"published by {_host(url)} ({mapped}) but filed in the {fact['_jurisdiction']} "
                "pack — a fact belongs to the authority that publishes it")

    # ── (b) freshness ────────────────────────────────────────────────────────────────
    if published is None:
        add("b-freshness",
            "promoted fact has no source publication date. This is a FAILURE, not a skip: "
            "an undated page cannot be shown to be current. Cite a dated official "
            "restatement instead (decision of 2026-08-16).")
    else:
        age = (run_date - published).days
        if age > max_age_days:
            add("b-freshness",
                f"source published {published} is {age} days old (limit {max_age_days}) "
                f"as of run-date {run_date}")
        if published > run_date:
            add("b-freshness", f"source publication date {published} is in the future")
        if retrieved:
            if retrieved > run_date:
                add("b-freshness", f"retrieved_at {retrieved} is in the future")
            if retrieved < published:
                add("b-freshness", f"retrieved_at {retrieved} precedes published {published}")
    return out


def check_graph(facts: Dict[str, Dict[str, Any]]) -> List[Dict[str, str]]:
    """(d) dependency closure, acyclicity, and evidence de-duplication."""
    out: List[Dict[str, str]] = []
    add = lambda key, msg, path="": out.append(
        {"check": "d-consistency", "key": key, "path": path, "message": msg})

    for key, fact in facts.items():
        for dep in fact.get("depends_on") or []:
            target = facts.get(dep)
            if target is None:
                add(key, f"depends_on {dep} which is not a canonical key in any pack", fact["_path"])
            elif fact["status"] in PROMOTED and target["status"] not in PROMOTED:
                add(key,
                    f"promoted fact depends on {dep}, which is {target['status']!r}. A visible "
                    "obligation cannot rest on one nobody has verified.", fact["_path"])

    # cycles
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {k: WHITE for k in facts}

    def walk(node: str, trail: List[str]) -> None:
        colour[node] = GREY
        for dep in facts[node].get("depends_on") or []:
            if dep not in facts:
                continue
            if colour[dep] == GREY:
                add(node, f"dependency cycle: {' -> '.join(trail + [node, dep])}",
                    facts[node]["_path"])
            elif colour[dep] == WHITE:
                walk(dep, trail + [node])
        colour[node] = BLACK

    for key in facts:
        if colour[key] == WHITE:
            walk(key, [])

    # Two canonical facts capturing the SAME sentence from the SAME page are one fact filed
    # twice — the duplication jurisdiction-keying exists to prevent. Same page with DIFFERENT
    # quotes is normal and expected (one gov.ie page backs both PPS facts).
    seen: Dict[Tuple[str, str], str] = {}
    for key, fact in sorted(facts.items()):
        source = fact.get("source") or {}
        quote = _norm(_quote_of(fact))
        if not (source.get("url") and quote):
            continue
        fingerprint = (source["url"], hashlib.sha256(quote.encode("utf-8")).hexdigest())
        if fingerprint in seen:
            add(key, f"identical url AND evidence quote as {seen[fingerprint]} — these are one "
                     "fact filed twice; collapse them and list both pack_keys", fact["_path"])
        else:
            seen[fingerprint] = key

    # pack_keys must be globally unique: one Audos key cannot claim two canonical facts.
    claimed: Dict[str, str] = {}
    for key, fact in sorted(facts.items()):
        for pack_key in fact.get("pack_keys") or []:
            if pack_key in claimed:
                add(key, f"pack_key {pack_key} is already claimed by {claimed[pack_key]}",
                    fact["_path"])
            else:
                claimed[pack_key] = key
    return out


def check_bindings(bindings, facts, root) -> List[Dict[str, str]]:
    """(a3) binding direction, plus referential integrity of refs and step ids."""
    import re
    out: List[Dict[str, str]] = []
    add = lambda cid, key, msg, path: out.append(
        {"check": cid, "key": key, "path": path, "message": msg})

    for binding in bindings:
        corridor = binding["corridor_id"]
        path = binding["_path"]
        steps = set()
        for pathway in sorted(binding["_dir"].glob("pathways/*/v1.yaml")):
            steps |= set(re.findall(r"^\s*-\s*step_id:\s*([A-Za-z0-9_]+)",
                                    pathway.read_text(encoding="utf-8"), re.M))
        for side, expected in (("origin_facts", binding["origin_iso"]),
                               ("destination_facts", binding["destination_iso"])):
            for entry in binding.get(side) or []:
                ref = entry.get("ref") if isinstance(entry, dict) else entry
                fact = facts.get(ref)
                if fact is None:
                    add("d-consistency", f"{corridor}/{ref}",
                        f"{side} references {ref}, which is not a canonical key", path)
                    continue
                actual = fact["_jurisdiction"]
                # EU instruments are union-level and legitimately bound origin-side by any
                # member-state corridor; they are never a destination's own authority.
                ok = (actual == expected) or (side == "origin_facts" and actual == "EU")
                if not ok:
                    add("a3-binding-direction", f"{corridor}/{ref}",
                        f"{side} of {corridor} (expects {expected}) cites a {actual} fact. A "
                        "destination requirement must come from the destination's own "
                        "authority; an origin obligation from the origin's.", path)
                step = entry.get("step_id") if isinstance(entry, dict) else None
                if step and step not in steps:
                    add("d-consistency", f"{corridor}/{ref}",
                        f"step_id {step!r} is not a step in any {corridor} pathway "
                        f"({len(steps)} known)", path)
    return out


# ── driver ────────────────────────────────────────────────────────────────────────────────

def check(root: Path, run_date: _dt.date, max_age_days: int) -> Tuple[int, Dict[str, Any], str]:
    classify_source = _classify_source(root)
    facts = load_packs(root)
    bindings = load_bindings(root)
    allowlist, allowlist_problems = load_allowlist(root)

    findings: List[Dict[str, str]] = []
    findings += [{"check": "config", "key": "-", "path": str(ALLOWLIST), "message": m}
                 for m in allowlist_problems]
    findings += [{"check": "config", "key": "-", "path": __file__, "message": m}
                 for m in _selftest_hosts(classify_source)]

    examined = 0
    for key in sorted(facts):
        fact = facts[key]
        if fact["status"] in PROMOTED and fact["kind"] == "obligation":
            examined += 1
        findings += check_fact(fact, classify_source=classify_source,
                               run_date=run_date, max_age_days=max_age_days)
    findings += check_graph(facts)
    findings += check_bindings(bindings, facts, root)

    if examined == 0:
        raise GateError(
            "zero promoted facts examined. That is reported as a broken run, not a pass: "
            "'no violations' and 'nothing was looked at' are indistinguishable otherwise."
        )

    # Apply the allowlist, and hold it to account.
    suppressed, live = [], []
    for finding in findings:
        entry = (finding["key"], finding["check"])
        if entry in allowlist:
            finding["allowlisted_reason"] = allowlist[entry]
            suppressed.append(finding)
        else:
            live.append(finding)
    stale = [f"{k}  {c}" for (k, c) in sorted(allowlist)
             if not any(f["key"] == k and f["check"] == c for f in findings)]

    lines: List[str] = []
    lines.append(f"Corridor fact-pack gate — run-date {run_date}, max age {max_age_days} days")
    counts: Dict[str, int] = {}
    for fact in facts.values():
        counts[fact["status"]] = counts.get(fact["status"], 0) + 1
    lines.append(
        f"  {len(facts)} canonical facts across {len(list((root / FACTS_DIR).glob('*.yaml')))} packs "
        f"({', '.join(f'{v} {k}' for k, v in sorted(counts.items()))}); "
        f"{examined} gate-bearing; {len(bindings)} corridor bindings"
    )
    if suppressed:
        lines.append(f"  {len(suppressed)} finding(s) suppressed by {ALLOWLIST}")
    if live:
        lines.append("")
        lines.append(f"FAIL — {len(live)} violation(s):")
        for finding in sorted(live, key=lambda f: (f["check"], f["key"])):
            lines.append(f"  [{finding['check']}] {finding['key']}")
            lines.append(f"      {finding['message']}")
            if finding.get("path"):
                lines.append(f"      in {finding['path']}")
    if stale:
        lines.append("")
        lines.append(f"FAIL — {len(stale)} allowlist entr(ies) no longer reproduce; delete them:")
        lines += [f"  {s}" for s in stale]
    if not live and not stale:
        lines.append("")
        lines.append("PASS — every promoted fact carries an official, dated, quoted source.")

    report = {
        "run_date": run_date.isoformat(),
        "max_age_days": max_age_days,
        "canonical_facts": len(facts),
        "gate_bearing": examined,
        "status_counts": counts,
        "bindings": len(bindings),
        "violations": live,
        "suppressed": suppressed,
        "stale_allowlist": stale,
        "verdict": "PASS" if not live and not stale else "FAIL",
    }
    return (1 if (live or stale) else 0), report, "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assert every customer-visible corridor fact has official, dated, quoted provenance.",
    )
    parser.add_argument("--root", default=".", help="repository root (default: cwd)")
    parser.add_argument("--run-date", default=None,
                        help="date freshness is measured against, YYYY-MM-DD (default: today "
                             "UTC). CI passes it explicitly so a run is reproducible.")
    parser.add_argument("--max-age-days", type=int, default=365,
                        help="freshness window in days (default: 365)")
    parser.add_argument("--json", dest="json_path", default=None, help="write the report here")
    args = parser.parse_args(argv)

    try:
        run_date = (_dt.date.fromisoformat(args.run_date) if args.run_date
                    else _dt.datetime.now(_dt.timezone.utc).date())
    except ValueError:
        print(f"error: --run-date {args.run_date!r} is not YYYY-MM-DD", file=sys.stderr)
        return 2
    if args.max_age_days <= 0:
        print("error: --max-age-days must be positive", file=sys.stderr)
        return 2

    try:
        exit_code, report, text = check(Path(args.root).resolve(), run_date, args.max_age_days)
    except GateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(text)
    if args.json_path:
        target = Path(args.json_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nreport written to {target}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
