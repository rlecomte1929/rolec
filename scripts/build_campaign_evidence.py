#!/usr/bin/env python3
"""
ReloPass Campaign Evidence Builder  (H4)
========================================
Distils a campaign_report_*.json (the output of campaign_scorer.py) into a small,
sanitized, **committable** evidence summary so a campaign's headline score is
*reproducible from the repo* — not merely self-reported in campaigns.json.

The raw test_results_*.json / campaign_report_*.json files are gitignored (large,
machine-specific, may reference live data). This script extracts only:
  - per-category (domain) PASS / FAIL / WARN / PARTIAL / BLOCKED / SKIP counts
  - the runner summary (total / pass / fail / warn / skip)
  - the recomputed overall score, derived from the per-category counts, alongside
    the score the scorer reported — so the two can be cross-checked.

It carries **no** PII: only test IDs, domains, priorities and status counts. As
defense-in-depth it still scrubs any stray e-mail address or bearer token that
might appear in a test title.

Usage:
    python scripts/build_campaign_evidence.py                       # latest report in results/
    python scripts/build_campaign_evidence.py --report results/campaign_report_<ts>.json
    python scripts/build_campaign_evidence.py --out results/campaign_evidence_latest.json

Output (default): results/campaign_evidence_latest.json
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import re
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
RESULTS_DIR = REPO_ROOT / "results"

# Status point values — must match campaign_scorer.POINTS so the recomputed score
# agrees with the scorer. SKIP is excluded from the denominator.
POINTS = {"PASS": 1.0, "WARN": 0.5, "PARTIAL": 0.5, "FAIL": 0.0, "BLOCKED": 0.0, "SKIP": None}
COUNT_STATUSES = ["PASS", "WARN", "PARTIAL", "FAIL", "BLOCKED", "SKIP"]

# Domain weights — must match campaign_scorer.DOMAIN_WEIGHTS.
DOMAIN_WEIGHTS = {
    "Authentication": 4, "Case Management": 4, "Employee Journey": 4,
    "Policy Management": 3, "Forms & Dossiers": 3, "Immigration": 2,
    "Suppliers & Vendors": 2, "Resources": 2, "Admin Console": 1,
    "Notifications": 1, "Collaboration": 1, "Coordination": 1,
    "Exception Requests": 1, "Integrations": 1,
    "Security & RLS": 4, "Performance": 2, "End-to-End Flows": 3,
}

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_TOKEN_RE = re.compile(r"(?i)\b(bearer\s+)?[A-Za-z0-9_-]{24,}\.[A-Za-z0-9_-]{6,}\b")


def _scrub(text: str) -> str:
    """Defense-in-depth: redact any stray e-mail or token-shaped string."""
    if not text:
        return text
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _TOKEN_RE.sub("[redacted-token]", text)
    return text


def _latest_report() -> Path | None:
    files = sorted(glob.glob(str(RESULTS_DIR / "campaign_report_*.json")))
    return Path(files[-1]) if files else None


def build_evidence(report: dict) -> dict:
    """Build the sanitized evidence summary from a scorer report dict."""
    per_test = report.get("per_test", {}) or {}

    # Group statuses by domain (category).
    categories: "OrderedDict[str, dict]" = OrderedDict()
    for meta in per_test.values():
        if not isinstance(meta, dict):
            continue
        domain = meta.get("domain", "Uncategorised")
        status = meta.get("status", "SKIP")
        cat = categories.setdefault(
            domain,
            {"weight": DOMAIN_WEIGHTS.get(domain, 1),
             **{s: 0 for s in COUNT_STATUSES}},
        )
        cat[status] = cat.get(status, 0) + 1

    # Per-category score + weighted overall, recomputed from the counts.
    weighted_sum = 0.0
    weight_total = 0.0
    category_out: "OrderedDict[str, dict]" = OrderedDict()
    for domain, c in categories.items():
        scored = 0
        points = 0.0
        for status in COUNT_STATUSES:
            pv = POINTS.get(status)
            if pv is None:  # SKIP — excluded from denominator
                continue
            scored += c[status]
            points += pv * c[status]
        pct = round((points / scored) * 100, 1) if scored else None
        category_out[domain] = {
            "weight": c["weight"],
            "counts": {s: c[s] for s in COUNT_STATUSES},
            "scored": scored,
            "score_pct": pct,
        }
        if pct is not None:
            weighted_sum += pct * c["weight"]
            weight_total += c["weight"]

    recomputed_overall = round(weighted_sum / weight_total, 1) if weight_total else None
    reported_overall = report.get("overall_score")

    # Aggregate runner-level totals across categories.
    totals = {s: sum(c["counts"][s] for c in category_out.values()) for s in COUNT_STATUSES}

    evidence = {
        "schema": "relopass.campaign_evidence/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_report": _scrub(str(report.get("current_file") or "")),
        "scorer_version": report.get("scorer_version"),
        "health_band": report.get("health_band"),
        "overall_score_reported": reported_overall,
        "overall_score_recomputed": recomputed_overall,
        "overall_score_matches": (reported_overall == recomputed_overall),
        "runner_summary": report.get("current_summary", {}),
        "test_totals_by_status": totals,
        "categories": category_out,
        "regressions": report.get("regressions", []),
        "fixed": report.get("fixed", []),
        "new_failures": report.get("new_failures", []),
    }
    # Tamper-evident digest of the category counts.
    digest_payload = json.dumps(
        {"categories": category_out, "totals": totals}, sort_keys=True
    ).encode("utf-8")
    evidence["evidence_sha256"] = hashlib.sha256(digest_payload).hexdigest()
    return evidence


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ReloPass campaign evidence builder")
    parser.add_argument("--report", help="campaign_report_*.json to summarise (default: latest in results/)")
    parser.add_argument("--out", help="output path (default: results/campaign_evidence_latest.json)")
    args = parser.parse_args(argv)

    report_path = Path(args.report) if args.report else _latest_report()
    if not report_path or not report_path.exists():
        print("ERROR: no campaign_report_*.json found. Run campaign_scorer.py first.", file=sys.stderr)
        return 1

    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    evidence = build_evidence(report)

    out_path = Path(args.out) if args.out else (RESULTS_DIR / "campaign_evidence_latest.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, ensure_ascii=False)
        f.write("\n")

    match = "✓ matches" if evidence["overall_score_matches"] else "✗ MISMATCH"
    print(f"  Evidence written → {out_path}")
    print(f"  Band {evidence['health_band']}  "
          f"reported={evidence['overall_score_reported']}  "
          f"recomputed={evidence['overall_score_recomputed']}  ({match})")
    print(f"  Categories: {len(evidence['categories'])}  "
          f"totals={evidence['test_totals_by_status']}")
    print(f"  sha256={evidence['evidence_sha256'][:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
