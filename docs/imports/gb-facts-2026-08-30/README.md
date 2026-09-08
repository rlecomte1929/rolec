# UK destination facts — the 4 remaining settling-in gaps (2026-08-30/31)

Completes the **United Kingdom** destination. The 12 substantive immigration/tax/NI/GP facts landed
2026-08-30 (direct-insert). This batch fills the settling-in gaps identified in the handoff:
**council tax · state-school admissions · driving-licence exchange · opening a UK bank account.**

Research: browser-grounded against **GOV.UK** by a Claude Code research subagent (Otto-first was
attempted via the bus, id 15; the reliable engine carried it). Referee: `scripts/verify_ledger.py`
re-fetched all 7 gov.uk pages and confirmed **11/11 evidence quotes verbatim, 0 rejected**.

## What landed (11 facts → 3 requirement_items, all `pending` / `representative`)

| requirement_item (topic) | purpose | pillar | facts | what it establishes |
|---|---|---|---|---|
| Council tax | employment | HOUSING | 3 | liable if 18+; single-person 25% discount (must apply); all-student household exempt |
| State school admissions | family | HOUSING | 4 | state school free 5–16; apply via the **local council** (incl. from abroad), not the school; in-year applications for mid-year arrivals; primary window opens Sept, closes 15 Jan |
| Driving licence exchange | employment | IDENTITY | 4 | non-designated licence: drive 12 months then GB tests; designated-country list; designated 5-year exchange window; EU-licence-until-70 rule |

All scoped `applies_to.nationality = non-EEA` → `THIRD_COUNTRY` (the UK is non-EEA; post-Brexit every
foreign national classifies third-country). Scope guard `check_nationality_scope.py --db`: **exit 0**.

## Source list (all official GOV.UK)
- `gov.uk/council-tax/who-has-to-pay`, `gov.uk/council-tax/discounts-for-full-time-students`
- `gov.uk/types-of-school`, `gov.uk/schools-admissions/how-to-apply`
- `gov.uk/driving-nongb-licence/...` (three smart-answer leaves: any-other-country, full list, EU/EEA)

## Deliberate reject (never invent)
- **Opening a UK bank account** — dropped. No official national gov.uk page carries a verbatim rule;
  the substantive content lives on individual council sites and MoneyHelper (`moneyhelper.org.uk`,
  not gov.uk). Per the honesty rule this is a documented reject, not a fabricated fact. If wanted, it
  belongs in the **settling-in resources** pipeline (`import_resources.py`), not `requirement_items`.

## Load record (Runbook A)
```
verify_ledger.py facts.ndjson --apply     -> clean 11, importable 11, promotable 11, 0 rejected
import_otto_facts.py clean.ndjson --apply --batch-id gb-facts-2026-08-30   -> staged 11 (status=new)
UPDATE otto_staging ... SET status='ready' WHERE batch_id='gb-facts-2026-08-30'   -> 11 (new->ready gate)
executor.promote(country='GB', dry_run=False)   -> 3 requirement_items, 0 unmapped, 0 skipped
verify: UK 22->25 (+3); 0 pre-existing rows changed; expert_verified=0; staged 11 -> promoted
```

**Gate remaining (human):** approve the 3 rows at `/admin/countries` (UNITED KINGDOM). Nothing is
served until approved — `requirements_builder` returns `approved` only.
