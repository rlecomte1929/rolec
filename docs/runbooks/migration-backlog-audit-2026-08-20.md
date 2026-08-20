# Migration backlog audit — 2026-08-20

**What this answers:** the prod default branch sits at `MIGRATIONS_FAILED`, and the standing
advice is that the failed state is *load-bearing* — it is what stops a backlog of unapplied
migrations from running. That advice was recorded with a specific fear attached: a
`DELETE FROM public.supplier_service_capabilities` against **118 live rows**.

**Measured today, that fear is stale.** Every destructive statement in the backlog would delete
**zero** rows of live data. The reason to leave `MIGRATIONS_FAILED` alone is still good, but it
is schema resurrection, not data loss.

## The backlog

`scripts/check_migration_drift.py --json` against prod, 2026-08-20:

| | |
|---|---|
| repo migration versions | 615 |
| prod ledger rows | 467 (max `20261108000000`) |
| **dead** — repo file at/below ledger max with no prod row | **148** |
| ledger rows with no repo file (true drift) | **0** |

"Dead" means `db push` would skip them: they sort below the ledger max, so the applier has
already moved past. They are not queued to run — they are stranded.

## Classification of the 148

| | count |
|---|---|
| additive only (CREATE / ALTER … ADD / INSERT / policy + grant) | **136** |
| contains a destructive statement | **12** |

### The 12, and what each would actually destroy

| version | file | destructive statements |
|---|---|---|
| `20260507100000` | `exception_requests_hardening.sql` | 1× ALTER…DROP |
| `20260513280000` | `employee_tasks_quote_requests.sql` | 1× ALTER…DROP |
| `20260521020000` | `case_forms_add_dependent_id.sql` | 1× ALTER…DROP |
| `20260522130000` | `policy_cap_exceptions.sql` | 1× ALTER…DROP |
| `20260523020000` | `friction_analysis_summary_type.sql` | 1× ALTER…DROP |
| `20260528000000` | `policy_cap_requests_exception_type.sql` | 1× ALTER…DROP |
| `20260609100000` | `immigration_corpus_chunks.sql` | 1× ALTER…DROP |
| `20260605800000` | `imm11_form_field_mappings_seed.sql` | 1× DELETE |
| `20260606100000` | `imm18_retention_automation.sql` | 1× DELETE |
| `20260925000000` | `dedupe_service_catalog_items.sql` | 2× DELETE |
| `20261001000000` | `cleanup_la_supplier_shells.sql` | 3× DELETE |
| `20261004000001` | `cleanup_living_areas_supplier_shells.sql` | 1× DELETE |

**Every DELETE measured against live data, 2026-08-20:**

| migration | target | rows it would delete |
|---|---|---|
| `20261004000001` | `supplier_service_capabilities WHERE service_category='living_areas'` | **0** |
| `20261001000000` | `service_catalog_items WHERE category='living_areas' AND external_id LIKE 'la-%'` | **0** |
| `20261001000000` | `company_vendor_selections` on those items | **0** |
| `20260925000000` | duplicate `service_catalog_items` by `(category, lower(name))` | **0** — 0 duplicate groups remain of 1014 items |
| `20260606100000` | `imm_employee_profiles` past retention + 30d | **0** |
| `20260605800000` | `form_field_mappings` for `DE_blue_card_v2024`, `FR_cerfa_14571_v2024` | 27, **then re-inserted by the same file** |

### Correcting the record on `supplier_service_capabilities`

The table does hold **118 rows** — the number in the original warning. But they are
`movers` 42, `schools` 33, `housing_agencies` 16, `legal_admin` 13, `tax_finance` 9, `banks` 5.
**`living_areas` holds 0.** The DELETE is category-scoped, so it matches nothing. The warning
conflated the table's size with the statement's blast radius.

The `living_areas` cleanups are no-ops because the cleanup they describe already happened
out-of-band. `dedupe_service_catalog_items` is a no-op for the same reason.
`imm11_form_field_mappings_seed` is an idempotent re-seed — the file's own comment says
"form_ids are removed before re-insert", and it carries the two matching INSERTs.

## The hazard that IS real: schema resurrection

`20260605950000_rfq_requests.sql` is in the dead set and creates `public.rfq_requests`.

Prod deliberately renamed that table to `rfq_requests_legacy`; the live RFQ system is
`rfqs` / `rfq_items` / `rfq_recipients`, currently holding **30 live RFQs**. Verified today:
`to_regclass('public.rfq_requests')` is NULL, `rfq_requests_legacy` exists.

Applying it would stand a superseded, empty `rfq_requests` next to the live tables — under the
name the old code used. That is not data loss; it is a table a future query can bind to by
mistake, which is worse than an obviously-absent one.

## Verdict

- **Do not "repair" the branch to make migrations succeed.** Still correct — but the reason is
  schema drift and resurrection, not a 118-row deletion.
- **The remedy is to remove the auto-apply path**, by disconnecting the Supabase↔GitHub
  integration in the dashboard. That is account-level; MCP cannot do it.
- **A full triage remains worthwhile** but is no longer urgent on data-safety grounds. The
  136 additive migrations are the real question: each is either already-applied-out-of-band
  (most likely, given the ledger is chronically behind) or genuinely missing schema.
- **Re-run this audit before acting.** Every "0 rows" here is a measurement of today's data,
  not a property of the migration. A future seed that repopulates `living_areas` would arm
  `20261004000001` again.

## Reproducing it

```bash
DATABASE_URL=... python scripts/check_migration_drift.py --json > drift.json
# then, per dead version, scan its file for DELETE/DROP/TRUNCATE and measure the predicate
```
