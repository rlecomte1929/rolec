# NO→FR vendor audit — 2026-08-19

Audit of the Norway→France (Oslo→Paris) supplier layer.

> **Scope note.** The task brief for this audit described a `supabase/seed/vendors/` tree
> (`_SCHEMA.md`, `index.json`, per-country flat JSON, a `vendor_providers` table, `vendor_key` /
> `country_coverage` / `corridors_served` / `priority_at_hub` / `regulatory_gate` columns, a
> `wave2-import-pipeline.mjs` loader and a `curated-import` hook). **None of that exists in this
> repository or in production** — see §6. This audit was therefore run against the supplier layer
> that does exist. No files were invented to make the brief's plan executable.

## 1. What was audited

| | |
|---|---|
| Tables | `suppliers`, `supplier_service_capabilities`, `supplier_service_categories`, `vendor_candidates` |
| Scope | `based_in_country`/`incorporation_country` ∈ (NO, FR) |
| Rows | **57** (NO 29, FR 28) |
| Method | read-only SQL against production; nothing written |

## 2. Coverage per category

`supplier_service_categories.compliance_critical` is this schema's equivalent of the brief's
CRITICAL categories. Only two categories are marked critical, and **both clear the ≥3 bar on both
sides of the corridor**.

| category | critical | NO | FR | verdict |
|---|---|---|---|---|
| `legal_admin` | ✅ | 7 | 4 | pass |
| `tax_finance` | ✅ | 5 | 3 | pass (FR exactly at the floor) |
| `housing_agencies` | — | 8 | 4 | pass |
| `movers` | — | 6 | 13 | pass |
| `banks` | — | 3 | **0** | **open gap** |
| `schools` | — | 3 | **0** | **open gap** |

### Open gaps — stated, not filled

Both gaps are on the **destination** side, which is where the corridor's own risk sits.

- **`banks` FR = 0.** The brief flags expat-banking depth as a known NO→FR gap, and the data
  confirms it: the corridor can currently offer a returning employee no French banking option at
  all. This matters more here than it would elsewhere — `justificatif de domicile` gates CPAM,
  banking and vehicle registration, so a missing banking option blocks a chain, not one task.
- **`schools` FR = 0.** Including the Lycée International de Saint-Germain-en-Laye, which the
  brief identifies as the only school in France continuing the Norwegian curriculum. It is named
  in the brief but **not present in the data**, and it is not added here: adding it from a task
  brief rather than from sourced research is exactly the fabrication this audit is meant to catch.

`tax_finance` FR sits at exactly 3 — it passes, but any single removal drops a compliance-critical
category below the floor. Worth watching rather than acting on.

## 3. Duplicates

**Zero duplicates.** Checked three ways across all 57 rows — normalised name, website domain, and
`legal_registration_number`. No entity appears twice under divergent keys.

Nothing is flagged for founder merge confirmation.

## 4. Competitor (RMC) check

The brief requires that enterprise RMCs — ReloPass competitors — are not corridor-listed, while
operational moving brands legitimately stay.

| entity | present | verdict |
|---|---|---|
| Cartus | absent | ✅ rule holds |
| Crown World Mobility | absent | ✅ rule holds |
| Crown Relocations (Norway) | present, NO, `movers` | ✅ correct — operational brand |
| **SIRVA Worldwide** | **present, `verified: true`, country `NULL`** | ⚠️ **see below** |
| Santa Fe Relocation — Paris | present, FR, `movers` | flag only |

**⚠️ `SIRVA Worldwide` is the finding.** SIRVA is a relocation-management company of the same
class as Cartus and Crown World Mobility — the brief simply did not name it. Two things make it
worse than a naming oversight:

1. it is `verified: true`, one of only three verified rows in this corridor; and
2. its country is **NULL**, so it is not scoped to any corridor and can surface anywhere.

It is the only verified supplier in the entire table with no country. **Recommended: flag for
founder decision** — this audit does not remove or reclassify a verified row.

*Santa Fe Relocation — Paris* is flagged for information only. Santa Fe runs both an RMC line and
a genuine moving operation, so by the brief's own Crown Relocations logic the Paris `movers` entry
is legitimate. No action proposed.

## 5. Traceability

The trust architecture requires every row to be traceable. Against 57 rows:

| check | rows failing | share |
|---|---|---|
| no `source_url` | 17 | 30% |
| no `website` | 44 | 77% |
| no `legal_registration_number` | 38 | 67% |
| no `source` tag | 0 | 0% |
| `entity_verified_at` unset | 0 | 0% |
| `status` not active | 0 | 0% |

Every row carries a `source` tag and an entity-verification timestamp, so provenance exists at the
row level. But **30% cannot be traced to a source document**, and 77% have no website — a shortlist
entry an HR generalist cannot look up is not usable, whatever its confidence label says.

**3 of 57 rows are `verified`** (all NO). That is correct and expected: nothing is customer-visible
until the founder flips it, and this audit changes no verification state.

## 6. The brief's infrastructure does not exist

Recorded because two separate task briefs this week have cited some of these paths.

Absent from the repo **and** from `audos-workspace-776786/`: `supabase/seed/vendors/` (entire
directory), `_SCHEMA.md`, `index.json`, `ireland.json`, `spain.json`, `france.json`, `norway.json`,
`tools/wave2-import-pipeline.mjs`, `apps/case-command/vendor-corridor-backfill.ts`, both corridor
supplier dossiers, `docs/es-ie-corridor-qa-report.md`,
`docs/nofr-corridor-gap-remediation-2026-08-14.md`, and
`docs/relopass-destination-priority-map.md`.

Absent from production: the `vendor_providers` table, and **all six** of the brief's key columns
(`vendor_key`, `country_coverage`, `corridors_served`, `priority_at_hub`, `regulatory_gate`,
`service_type`) on any supplier table.

What exists instead: `suppliers` (116 rows), `vendor_candidates` (534), 
`supplier_service_capabilities` (118), plus qualification, accreditation, red-flag and
service-area tables. In the repo, vendor seed data is `backend/app/recommendations/datasets/*.json`
— **12 files keyed by category, not by country**. `vendors` has been renamed `vendors_legacy`.

Consequently the brief's dedup/rejection list, its `curated-import` hook payload, and its
`backfill.ts` doc-inconsistency item are all **not applicable** to this repository. None were
actioned. Nothing was created to make them applicable.

## 7. Recommended next actions

1. **Decide on `SIRVA Worldwide`** — verified, uncountried, RMC class. Founder call.
2. **Close `banks` FR and `schools` FR** from sourced research, not from a brief.
3. **Backfill `source_url` for the 17 untraceable rows** before any of them is considered for
   verification; a row that cannot be checked cannot be verified.
4. Treat `tax_finance` FR = 3 as a watch item.

Nothing in this audit was written to the database or to any seed file. It is a read-only finding.
