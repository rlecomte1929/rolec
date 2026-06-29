#!/usr/bin/env python3
"""
Ingest Playwright results into the campaign-scorer schema.

The browser layer (tests/e2e) emits a Playwright JSON report (`_results.json`);
the API layer (relopass_api_runner_patched.js) emits `test_results.json`. This
adapter converts the Playwright report into the same `results[]` shape the scorer
reads (id + status), MERGES it with the API layer, and writes a single
`results/test_results_<ts>.json` for `campaign_scorer.py` to pick up.

Each test ID comes from the leading `[TAG]` in the Playwright spec title
(e.g. "[CORE-RLS] ..." -> "CORE-RLS"; "[VND-05/MSG-05] ..." -> "VND-05").
Only IDs present in scoring_map.json are scored, so keep the two in sync.

Usage:
    python3 scripts/ingest_playwright_results.py \
        --pw tests/e2e/test-artifacts/<RUNID>/_results.json \
        [--api test_results.json] [--out results/test_results_<ts>.json]
"""
import argparse
import glob
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"

# Playwright status -> scorer status
PW_STATUS = {
    "passed": "PASS",
    "failed": "FAIL",
    "timedOut": "FAIL",
    "interrupted": "FAIL",
    "skipped": "SKIP",
}
# worst-wins ranking when an ID appears more than once
# worst-wins ranking when an ID appears more than once. PASS must rank ABOVE SKIP:
# parse_playwright seeds status to SKIP, so if PASS ranked below it a passing spec
# would never overwrite the seed and would be silently dropped from the score.
RANK = {"FAIL": 3, "WARN": 2, "PARTIAL": 2, "PASS": 1, "SKIP": 0}

TAG_RE = re.compile(r"^\s*\[([^\]]+)\]")


def tag_of(title: str):
    m = TAG_RE.match(title or "")
    if not m:
        return None
    # "VND-05/MSG-05" -> "VND-05"; "CORE-HR-dashboard" -> as-is
    return re.split(r"[\s/]+", m.group(1).strip())[0]


def walk_specs(node):
    """Yield every spec dict from a Playwright JSON report (recursive suites)."""
    if isinstance(node, dict):
        for spec in node.get("specs", []) or []:
            yield spec
        for child in node.get("suites", []) or []:
            yield from walk_specs(child)
    elif isinstance(node, list):
        for item in node:
            yield from walk_specs(item)


def parse_playwright(pw_path: Path):
    data = json.loads(pw_path.read_text(encoding="utf-8"))
    rows = {}
    roots = data.get("suites", data)
    for spec in walk_specs({"suites": roots} if isinstance(roots, list) else data):
        title = spec.get("title", "")
        tid = tag_of(title)
        if not tid:
            continue
        # worst status across this spec's tests/projects
        status = "SKIP"
        for t in spec.get("tests", []) or []:
            res = (t.get("results") or [{}])
            pw = res[-1].get("status", "skipped")
            s = PW_STATUS.get(pw, "FAIL")
            if RANK[s] >= RANK[status]:
                status = s
        prev = rows.get(tid)
        if prev is None or RANK[status] >= RANK[prev["status"]]:
            rows[tid] = {"id": tid, "title": title.strip(), "status": status, "source": "browser"}
    return list(rows.values())


def summarize(results):
    c = {"total": len(results), "pass": 0, "fail": 0, "warn": 0, "skip": 0}
    for r in results:
        s = r.get("status")
        if s == "PASS":
            c["pass"] += 1
        elif s in ("FAIL", "BLOCKED"):
            c["fail"] += 1
        elif s in ("WARN", "PARTIAL"):
            c["warn"] += 1
        else:
            c["skip"] += 1
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pw", required=True, help="Playwright _results.json path")
    ap.add_argument("--api", default=None, help="API runner test_results.json (optional)")
    ap.add_argument("--out", default=None, help="output path (default results/test_results_<ts>.json)")
    args = ap.parse_args()

    browser = parse_playwright(Path(args.pw))

    merged = {}  # id -> row ; API layer first, browser overrides/adds
    api_meta = {}
    api_path = args.api or (str(REPO_ROOT / "test_results.json") if (REPO_ROOT / "test_results.json").exists() else None)
    if api_path and os.path.exists(api_path):
        api = json.loads(Path(api_path).read_text(encoding="utf-8"))
        api_meta = {k: api.get(k) for k in ("bugs_regression", "scenario_statuses", "performance_snapshot")}
        for r in api.get("results", []) or []:
            if r.get("id"):
                merged[r["id"]] = {**r, "source": r.get("source", "api")}
    for r in browser:
        merged[r["id"]] = r

    results = list(merged.values())
    ts = datetime.now(timezone.utc)
    out = {
        "run_date": ts.strftime("%Y-%m-%d"),
        "run_ts": ts.isoformat(),
        "runner_version": "e2e-sentinel-1.0",
        "mode": "API+Browser (E2E Sentinel)",
        "summary": summarize(results),
        "results": results,
        **{k: v for k, v in api_meta.items() if v},
    }
    out["score_pct"] = round(100 * out["summary"]["pass"] / max(1, out["summary"]["total"] - out["summary"]["skip"]))

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = Path(args.out) if args.out else RESULTS_DIR / f"test_results_{ts.strftime('%Y-%m-%dT%H-%M')}.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"✔ merged {len(browser)} browser + {len(merged) - len(browser)} api → {out_path}")
    print(f"  summary: {out['summary']}")


if __name__ == "__main__":
    main()
