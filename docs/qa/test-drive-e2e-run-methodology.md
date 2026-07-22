# Test-Drive E2E run methodology — pin the corridor, log the run variables

**AIQ-1629 (TD-QA R2-10).** Regression comparison across test-drive QA runs is only
trustworthy when the runs are held to the same variables. This doc is the QA rule of
record; follow it for every verification / regression run.

## Why this exists

The test-drive corridor is **auto-assigned per session** (load-balanced across the five
locked corridors) unless an explicit `?corridor=` is supplied. That is correct for real
testers (the single-link model must stay), but it makes back-to-back QA runs
**non-comparable**:

- **RUN 001** landed on **IN_DE** (India → Munich) — a **Tier-A** corridor with real
  ingested immigration content.
- **RUN 002** landed on **NL_SG** (Amsterdam → Singapore) — a **Tier-B** corridor with
  **no ingested immigration content**.

A Tier-B corridor legitimately produces a thinner roadmap and "no policy rule" states —
which reads as a **phantom regression** when diffed against a Tier-A run. The corridor
confound must be removed before any run-to-run verdict is trusted.

## Rule 1 — Pin the corridor (Tier-A) on every QA run

Always supply an explicit corridor. The provisioning endpoint already honours
`?corridor=` (TD-13) and rejects anything outside the locked set, so **no product code
change is needed** — this is a methodology rule.

Use a **Tier-A** corridor (real ingested immigration/policy content):

| Corridor | Route | Tier |
|---|---|---|
| `FR_NO` | Paris → Oslo | **A** (preferred default for regression) |
| `IN_DE` | Mumbai → Munich | **A** |
| `GB_US` | London → New York | verify ingested content before relying on it |
| `NL_SG` | Amsterdam → Singapore | **B** — thin content expected; do NOT use for regression baselines |
| `ES_AE` | Madrid → Dubai | verify ingested content before relying on it |

**Default: `FR_NO`.** Keep the SAME corridor across the runs you intend to compare.

Provisioning links (both honour `?corridor=`):

```
# Standard self-serve test-drive, corridor pinned, QA campaign (never the live cohort):
https://relopass.com/test-drive?campaign=qa-<run-id>&corridor=FR_NO

# Staged fixture (AIQ-1656 / Task 4) — provision straight to a stage, corridor pinned:
POST /api/test-drive/provision-staged  { "first_name": "...", "campaign": "qa-<run-id>",
                                         "corridor_id": "FR_NO", "stage": "shortlist_ready" }
```

> `campaign` MUST be a `qa-*` value (never `insead-2026`) so the run doesn't contaminate
> the live cohort's metrics, and — for `provision-staged` — because the staged fixture is
> gated to `qa-*` campaigns. See the campaign-attribution rule in `test_drive.py`.

Do **not** remove auto-assignment for real testers — the single-link model stays; this
rule applies only to QA/regression runs, which always pass `?corridor=`.

## Rule 2 — Log a run-variable block in every QA report

Every QA run report must open with this block so any diff is attributable to a variable
rather than misread as a regression:

```
## Run variables
- Run ID:          qa-<run-id>
- Date (UTC):      YYYY-MM-DD
- Corridor:        FR_NO (Paris → Oslo, Tier-A)
- Seniority tier:  <e.g. L4 / senior>
- Policy baseline: <published default | company-specific | version id>
- Currency:        <e.g. EUR>
- HR case ID:      <relocation_cases id>
- Employee case:   <wizard_cases / assignment id>
- Build / commit:  <deployed SHA at run time>
```

Two consecutive runs are comparable **only** when their Run-variable blocks match on
corridor, seniority tier, policy baseline, and currency. If any of these differ, the
runs are not directly comparable and the report must say so.

## Checklist (per run)

- [ ] Corridor pinned with `?corridor=` (Tier-A; `FR_NO` unless a specific corridor is
      under test) — never rely on auto-assignment for a regression run.
- [ ] Campaign is `qa-<run-id>` (never `insead-2026`).
- [ ] Report opens with the Run-variable block above (both case IDs included).
- [ ] The comparison run used the **same** corridor + variables; any difference is called
      out explicitly.
