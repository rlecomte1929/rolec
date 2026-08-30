#!/usr/bin/env python3
"""Preprocess a generator ledger so `import_otto_facts.py` can swallow it whole.

    python scripts/verify_ledger.py <ledger.ndjson>            # dry run — reports, writes nothing
    python scripts/verify_ledger.py <ledger.ndjson> --apply    # write clean.ndjson + worklist
    python scripts/verify_ledger.py <ledger.ndjson> --no-fetch # skip V2 liveness (offline/CI)

WHY THIS EXISTS
---------------
`parsers.read_jsonl` raises on the first malformed line and stops the batch, deliberately — a
half-imported batch that reports success is worse than no import. The cost is that one bad record
from the generator strands the other 199. This splits the file first: everything the importer
would choke on goes to a worklist with a reason, and what is left imports in one clean pass.

It also names the records that will import *fine* and then quietly never promote, because
`mappings.resolve()` refuses them. Those are the expensive ones — they look like success at import
time and produce nothing weeks later. See `verifier.py`'s module docstring for the two severities.

WHAT IT DOES NOT DO
-------------------
No database writes and no staging: the importer owns `otto_staging` and keeps owning it. No LLM.
No second evidence matcher — quote grounding is V3, which is the existing
`backend/scripts/backfill_fact_evidence.py` over `backend/app/services/fact_evidence.py`, run
after the import. This script prints that command rather than reimplementing it.

Exit codes
----------
  0  ran; the clean file is importable (rejections may still have been reported)
  1  nothing importable — every record was rejected, or the file was empty
  2  the run could not happen (missing file, unreadable config)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.imports.otto.verifier import (  # noqa: E402
    REJECT,
    Verdict,
    check_evidence_grounding,
    load_config,
    summarise,
    verify_lines,
)

_SAMPLE = 12

#: `backfill_fact_evidence.fetch_status_for` is three-valued and the middle value is not a
#: failure: `not_fetched` means robots.txt told us not to ask. Treating it as dead would report a
#: perfectly healthy source as unreachable — which this script did until it was measured against
#: skatteetaten.no and nav.no, both of which fetch fine.
OK = "fetched"
SKIPPED = "not_fetched"


def _fetch_liveness(verdicts: List[Verdict], timeout_s: float) -> Dict[str, Dict[str, Any]]:
    """Fetch the distinct URLs still in play, once, and KEEP the parsed text.

    Reuses `backfill_fact_evidence.fetch_and_parse`, which already honours robots.txt, rotates
    user agents, rate-limits per host, and distinguishes "every identity was refused" from "there
    is nothing there". Writing a second fetcher here would get that distinction wrong, and the
    distinction is the whole reason a dead-looking source is a warning rather than a rejection.

    Returns `{url: {"status", "text", "ok", "reason"}}`. It used to return just the status string
    and throw the page away, which meant V3 quote grounding would have had to fetch every source a
    second time. Keeping the text makes V3 free.

    ROBOTS. This passed `limiter=` but not `robots=`, so `fetch_and_parse`'s robots check —
    guarded by `robots is not None` — never ran, and the docstring above claimed otherwise.
    Observed fetching `lovdata.no`, which disallows crawlers. Now passes a policy. The effect is
    MORE `source_unreadable` warnings, which is correct: a source we are not allowed to read is a
    source we cannot verify a quote against, and saying so is the honest outcome.
    """
    try:
        from backend.scripts.backfill_fact_evidence import (  # noqa: WPS433
            HostRateLimiter,
            RobotsPolicy,
            fetch_and_parse,
            fetch_status_for,
        )
    except Exception as exc:  # pragma: no cover - exercised only on a broken checkout
        print(f"  ! liveness skipped: could not import the fetcher ({exc})")
        return {}

    urls = sorted({
        str(v.record.get("source_url") or "")
        for v in verdicts if v.record and not v.rejected and v.record.get("source_url")
    })
    if not urls:
        return {}

    limiter, robots = HostRateLimiter(), RobotsPolicy()
    out: Dict[str, Dict[str, Any]] = {}
    for url in urls:
        try:
            res = fetch_and_parse(url, robots=robots, limiter=limiter)
            out[url] = {
                "status": fetch_status_for(res),
                "text": res.get("text") or "",
                "ok": bool(res.get("ok")),
                "reason": str(res.get("reason") or ""),
            }
        except Exception as exc:  # noqa: BLE001 - a fetch failure is data, not a crash
            out[url] = {"status": f"error_{type(exc).__name__}", "text": "", "ok": False,
                        "reason": f"error_{type(exc).__name__}"}
    return out


def _apply_grounding(verdicts: List[Verdict], pages: Dict[str, Dict[str, Any]]) -> None:
    """V3: append quote-grounding findings, in place, using the pages already fetched.

    Skips rows already rejected by V0-V2 — a line that will not be imported does not need a
    fourth reason, and folding one in inflates every count in the report.
    """
    for v in verdicts:
        if v.record is None or v.rejected:
            continue
        url = str(v.record.get("source_url") or "")
        page = pages.get(url)
        if page is None:
            continue  # no fetch was attempted (no url, or liveness was skipped)
        findings, verified, offset = check_evidence_grounding(
            v.record, page["text"], fetch_ok=page["ok"], fetch_reason=page["reason"],
        )
        v.findings.extend(findings)
        v.evidence_verified = verified
        v.evidence_offset = offset


def _write(path: Path, lines: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(l if l.endswith("\n") else l + "\n" for l in lines), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ledger", help="path to the generator's NDJSON ledger")
    ap.add_argument("--apply", action="store_true",
                    help="write clean.ndjson + worklist.ndjson (default: dry run, report only)")
    ap.add_argument("--out", help="output directory (default: alongside the ledger)")
    ap.add_argument("--config", help=f"authority config (default: the one beside verifier.py)")
    ap.add_argument("--no-fetch", action="store_true",
                    help="skip V2 liveness. Recorded in the report — a run without liveness must "
                         "not be mistaken for one with it.")
    args = ap.parse_args(argv)

    ledger = Path(args.ledger)
    if not ledger.is_file():
        print(f"::error::{ledger} does not exist.")
        return 2
    try:
        cfg = load_config(Path(args.config) if args.config else None)
    except Exception as exc:  # noqa: BLE001
        print(f"::error::could not read the verifier config: {exc}")
        return 2

    started = datetime.now(timezone.utc)
    lines = ledger.read_text(encoding="utf-8").splitlines()
    verdicts = verify_lines(lines, cfg)

    if not verdicts:
        print(f"::error::{ledger} contains no records. An empty batch is not a clean batch.")
        return 1

    liveness: Dict[str, Dict[str, Any]] = {}
    if not args.no_fetch:
        print(f"V2 liveness: fetching distinct sources (timeout "
              f"{cfg['settings'].get('fetch_timeout_s', 20.0)}s) ...")
        liveness = _fetch_liveness(verdicts, cfg["settings"].get("fetch_timeout_s", 20.0))
        # V3 runs on the text that fetch just produced — no second request. It must happen
        # BEFORE summarise(), or its findings are not counted in the report they justify.
        _apply_grounding(verdicts, liveness)

    summary = summarise(verdicts)
    summary["liveness_checked"] = bool(liveness)
    if liveness:
        statuses = [p["status"] for p in liveness.values()]
        summary["sources_checked"] = len(statuses)
        summary["sources_fetched"] = sum(1 for s in statuses if s == OK)
        summary["sources_skipped"] = sum(1 for s in statuses if s == SKIPPED)
        summary["sources_failed"] = sum(1 for s in statuses if s not in (OK, SKIPPED))
        summary["quotes_verified"] = sum(1 for v in verdicts if v.evidence_verified is True)
        summary["quotes_not_on_page"] = sum(1 for v in verdicts if v.evidence_verified is False)

    # ---------------- report ----------------
    print(f"\nledger: {ledger}")
    print(f"lines {summary['lines']}   clean {summary['clean']}   "
          f"warned {summary['warned']}   rejected {summary['rejected']}")
    print(f"importable: {summary['lines'] - summary['rejected']}   "
          f"promotable: {summary['promotable']}   "
          f"stage-but-never-promote: {summary.get('promote_blocked', 0)}")

    if summary["findings_by_code"]:
        print("\nfindings:")
        for code, n in summary["findings_by_code"].items():
            print(f"  {n:4}  {code}")

    print("\nsource authority mix (importable rows):")
    for rank, n in summary["source_rank_mix"].items():
        print(f"  {n:4}  {rank}")

    if not liveness:
        print("\n  ! V2 LIVENESS NOT RUN (--no-fetch). Source reachability is unknown, not ok.")
    else:
        print(f"\nV2 liveness: {summary['sources_fetched']} fetched, "
              f"{summary['sources_skipped']} skipped by robots.txt, "
              f"{summary['sources_failed']} failed (of {summary['sources_checked']} distinct).")
        print(f"V3 evidence: {summary.get('quotes_verified', 0)} quote(s) confirmed on the cited "
              f"page, {summary.get('quotes_not_on_page', 0)} rejected as not on it.")
        if summary["sources_skipped"]:
            # `not_fetched` means we chose not to ask. Folding it in with real failures would
            # report a healthy source as dead, which is the mistake this line exists to avoid.
            for url in sorted(u for u, p in liveness.items() if p["status"] == SKIPPED)[:_SAMPLE]:
                print(f"      robots-skipped   {url[:96]}")
        if summary["sources_failed"]:
            print("  ! failures are reported, NOT rejected — a transient outage has faked a "
                  "dead source before (2026-08-22, a live HSE URL).")
            for url in sorted(u for u, p in liveness.items()
                              if p["status"] not in (OK, SKIPPED))[:_SAMPLE]:
                print(f"      {liveness[url]['status']:16} {url[:96]}")

    rejects = [v for v in verdicts if v.rejected]
    if rejects:
        print(f"\nrejected ({len(rejects)}) — kept out of the clean file. A bad_json or "
              "missing_required line would stop the importer mid-batch; the rest it drops:")
        for v in rejects[:_SAMPLE]:
            for f in v.findings:
                if f.severity == REJECT:
                    print(f"  line {v.lineno:4}  {f.check}/{f.code}: {f.detail}")
        if len(rejects) > _SAMPLE:
            print(f"  … and {len(rejects) - _SAMPLE} more")

    blocked = [v for v in verdicts if v.promote_blocked]
    if blocked:
        print(f"\nwill import but NOT promote ({len(blocked)}) — resolve() refuses these; "
              "silent unless read here:")
        for v in blocked[:_SAMPLE]:
            codes = ", ".join(f.code for f in v.findings if f.blocks_promote)
            print(f"  line {v.lineno:4}  {v.dedupe_key}  [{codes}]")
        if len(blocked) > _SAMPLE:
            print(f"  … and {len(blocked) - _SAMPLE} more")

    # Informational warnings are worth a count, but they do not gate the verdict.
    info = [v for v in verdicts if not v.rejected and v.warned and not v.promote_blocked]
    if info:
        print(f"\ninformational only ({len(info)} row(s)) — imports and promotes; a quality/"
              "tiering note, not a blocker. See findings above for the breakdown.")

    # ---------------- outputs ----------------
    out_dir = Path(args.out) if args.out else ledger.parent
    clean_path, work_path = out_dir / "clean.ndjson", out_dir / "worklist.ndjson"
    clean_lines = [json.dumps(v.record, ensure_ascii=False) for v in verdicts
                   if not v.rejected and v.record is not None]
    work_lines = [
        json.dumps({
            "lineno": v.lineno,
            "dedupe_key": v.dedupe_key,
            "findings": [{"severity": f.severity, "check": f.check, "code": f.code,
                          "detail": f.detail} for f in v.findings if f.severity == REJECT],
            "record": v.record,
        }, ensure_ascii=False) for v in rejects
    ]

    if args.apply:
        _write(clean_path, clean_lines)
        _write(work_path, work_lines)
        print(f"\nwrote {clean_path}  ({len(clean_lines)} record(s))")
        print(f"wrote {work_path}  ({len(work_lines)} rejection(s))")
        print("\nnext:")
        print(f"  python scripts/import_otto_facts.py {clean_path}            # dry run")
        print(f"  python scripts/import_otto_facts.py {clean_path} --apply")
        print("  python backend/scripts/backfill_fact_evidence.py --apply     # V3 quote grounding")
    else:
        print(f"\nDry run — nothing written. --apply would write {len(clean_lines)} clean "
              f"record(s) and {len(work_lines)} rejection(s) to {out_dir}/")

    print(f"\nelapsed {(datetime.now(timezone.utc) - started).total_seconds():.1f}s")
    if not clean_lines:
        print("::error::no importable records — the clean file would be empty.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
