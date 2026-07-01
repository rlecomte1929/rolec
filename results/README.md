# ReloPass test-campaign results — canonical location

This directory is the **single source of truth** for ReloPass quality-campaign data.

## Files

| File | Tracked in git? | What it is |
| --- | --- | --- |
| `campaigns.json` | **Yes** (force-added) | Canonical machine-readable registry of every campaign (C1, C2, …). One entry per campaign, append-only. Consumed by `scripts/campaign_scorer.py`, `scripts/pre_campaign_check.py`, and the `relopass-test-campaign` skill. |
| `campaign_evidence_latest.json` | **Yes** (force-added) | Reproducible, sanitized evidence summary for the latest campaign — per-category PASS/FAIL/WARN/SKIP counts so a score can be re-derived from the repo, not just self-reported. Regenerate with `scripts/build_campaign_evidence.py`. |
| `README.md` | **Yes** | This file. |
| `test_results_*.json` | No (gitignored) | Raw per-run runner output. Large, machine-specific, may reference live data — kept local only. |
| `campaign_report_*.json` | No (gitignored) | Per-run scorer output. Local only. |

The whole `results/` directory is listed in the repo `.gitignore`; the tracked
files above are deliberately force-added (`git add -f`) so the registry and its
evidence survive in version control while the bulky raw runs stay out.

## Why there is no `campaigns.json` at the repo root

A stale `campaigns.json` once lived at the repository **root**. It contradicted
this file (it listed a different, older C3) and had **no consumers** — every
script and the skill resolve the registry via `RESULTS_DIR / "campaigns.json"`,
i.e. *this* directory. The root copy was removed (H4) so there is exactly one
canonical tracker. **Do not recreate a root-level `campaigns.json`.** Append new
campaigns to `results/campaigns.json` only.

## Regenerating the evidence summary

```bash
# From repo root, after a campaign report has been written to results/:
python scripts/build_campaign_evidence.py            # uses the latest report
python scripts/build_campaign_evidence.py --report results/campaign_report_<ts>.json
```

The evidence summary is derived from the scorer's `per_test` output. It contains
only test IDs, domains, priorities, and status counts — no tokens, no emails, no
case/person data. (These are API smoke tests on fake pre-launch data; the
generator additionally scrubs any stray `@`-addresses or bearer tokens as
defense-in-depth.)
