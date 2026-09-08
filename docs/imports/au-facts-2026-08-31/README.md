# Australia destination facts (2026-08-31)

Australia opened as a destination (coverage-master rank 6, Sydney hub), greenfield. Browser-grounded
against **gov.au** (immi.homeaffairs.gov.au, ato.gov.au, servicesaustralia/homeaffairs health,
fairwork.gov.au) by a Claude Code research subagent.

## What landed (15 facts → 10 requirement_items, all `pending` / `representative`)
| requirement_item (topic) | pillar | facts |
|---|---|---|
| Skills in Demand visa (subclass 482) | RESIDENCE | 2 |
| Employer Nomination Scheme visa (subclass 186) | RESIDENCE | 1 |
| Skilled Employer Sponsored Regional visa (subclass 494) | RESIDENCE | 2 |
| Right to work in Australia | EMPLOYMENT | 1 |
| Tax File Number (TFN) | EMPLOYMENT | 2 |
| Australian tax residency | EMPLOYMENT | 2 |
| Superannuation (Super Guarantee, 12%) | EMPLOYMENT | 1 |
| Medicare eligibility (RHCA) | HEALTHCARE | 2 |
| Private health insurance (condition 8501) | HEALTHCARE | 1 |
| Workplace rights | EMPLOYMENT | 1 |

All `applies_to.nationality = non-EEA` → THIRD_COUNTRY (Australia is non-EEA). Scope guard exit 0.
1 fact `needs_lawyer_review` (tax-residency-vs-immigration determination). The 494 "Sydney is NOT a
designated regional area" trap is captured.

## ⚠️ Referee caveat (honest)
`verify_ledger` re-fetch reached only **1 of 9** gov.au pages — immi.homeaffairs.gov.au and ato.gov.au
blocked its fetcher, so 3/15 quotes were referee-confirmed and the other 12 are `fetch_failed`
(**reported, not rejected** — the known "a transient outage faked a dead source" pattern, so the batch
stays importable). The research subagent browser-confirmed all 15 verbatim. They land `representative`;
**re-run `verify_ledger` (or `backfill_fact_evidence`) to re-confirm the 12 before approval.**

## Code this batch required
- `requirements_country_key.py`: `"AU": "AUSTRALIA"` (+ `test_australia_is_covered`). gov.au already
  allowlisted in the otto parser, so no allowlist change needed.

## Load record (Runbook A)
```
verify_ledger.py facts.ndjson --apply   -> clean 15, importable 15, promotable 15; 8/9 fetch_failed
import_otto_facts.py clean.ndjson --apply --batch-id au-facts-2026-08-31   -> staged 15 (new)
park AU-immig-2026-08-12 (8 'ready') -> flip mine -> promote(country='AU') -> restore
  -> 10 requirement_items; verify AUSTRALIA 0->10, expert_verified=0
```

**Gate remaining (human):** approve at `/admin/countries` (AUSTRALIA); serving needs `"AU":"AUSTRALIA"`
merged (PR #2138). Re-confirm the 12 fetch-blocked quotes first.
