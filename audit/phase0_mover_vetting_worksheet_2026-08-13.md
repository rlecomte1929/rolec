# Phase 0 — Mover vetting worksheet (FR / DE)

**Addendum A · Vendor Sourcing Sides & HR Catchment Override**
Measured against production `nsvefcvpvwwwhuqyuqmp` on 2026-08-13. **No rows were changed.**

Phase 0 says: report the 15 rows, do not self-approve, produce a worksheet, stop. This is that
worksheet. It ends with two blockers that need a decision before Phase 1 is worth starting.

---

## The 15 rows

All 15 are `platform_vetting_status = 'pending'`, all `coverage_scope_type = 'country'`,
all `source = 'directory_import'`. The prompt's count is exact: **11 DE + 4 FR**.

The right-hand column applies Addendum A §S2 `vendor_reaches('NO')`, which is satisfied by ANY of:
(1) `coverage_scope_type='global'`, (2) a `supplier_service_area_coverage` row for NO or a
containing region, (3) a **verified** `FIDI FAIM` / `IAM` / `OMNI` accreditation.

### DE-registered capabilities (11)

| # | supplier | accreditation | NO reach evidenced? |
|---|---|---|---|
| 1 | AGS France (SOFDI – Société Française de Déménagement International) | FIDI FAIM Plus — **verified** | ✅ rule 3 |
| 2 | Grospiron International | FIDI FAIM Plus — **verified** | ✅ rule 3 |
| 3 | AGS Global Solutions GmbH — Berlin | FIDI FAIM Plus — claimed | ❌ |
| 4 | AGS Global Solutions GmbH — Koblenz | FIDI FAIM — claimed | ❌ |
| 5 | All World Transport | FIDI FAIM — claimed | ❌ |
| 6 | Hasenkamp Relocation Services GmbH | FIDI FAIM Plus — claimed | ❌ |
| 7 | Hertling GmbH & Co. KG | FIDI FAIM Plus — claimed | ❌ |
| 8 | Intermove GmbH | FIDI FAIM Plus — claimed | ❌ |
| 9 | Neer Service | FIDI FAIM — claimed | ❌ |
| 10 | Paul v. Maur GmbH | FIDI FAIM Plus — claimed | ❌ |
| 11 | Sterling Relocation S.A.R.L (trading as Sterling Lexicon) | FIDI FAIM — claimed | ❌ |

### FR-registered capabilities (4) — all created 2026-08-13

| # | supplier | accreditation | NO reach evidenced? |
|---|---|---|---|
| 12 | AMT TRANSFERT | INSEE SIRENE — claimed | ❌ |
| 13 | D-MAX | INSEE SIRENE — claimed | ❌ |
| 14 | SARL ORGANIDEM | INSEE SIRENE — claimed | ❌ |
| 15 | VASSE TRANSFERT | INSEE SIRENE — claimed | ❌ |

**Aggregate reach evidence across all 15:** `global` scope **0** · area-coverage rows **0** ·
verified FIDI/IAM/OMNI **2**.

---

## BLOCKER 1 — the Phase 0 gate cannot be met by current supply

> Gate as written: *"≥3 FR-based movers approved with verified NO reach."*

**FR-based movers that can evidence NO reach today: 0.**

The four FR rows came from the INSEE SIRENE import (AIQ-1827, PR #1846) and are **tier 2 by
construction** — SIRENE proves a company is registered in France and self-declared NAF 49.42Z
(déménagement). It evidences no network membership whatsoever. They are local Paris removals
firms; nothing suggests any of them can handle a Paris→Oslo international household-goods move.

Approving them would assert reach that no evidence supports — the precise failure Addendum A
line 34 warns about: *"a Paris mover with no Nordic network cannot quote Paris→Oslo."*

**Three ways forward. This is a human decision.**

1. **Source FR movers from FIDI/IAM/OMNI directly** (recommended). FIDI's per-affiliate pages
   resolve individually and were used to verify 4 movers on 2026-08-12; only its `find-mover`
   index is 404. A France-scoped FIDI harvest would produce genuinely tier-1 origin supply.
2. **Accept the two verified FIDI firms as the FR origin supply.** AGS France (SOFDI) and
   Grospiron International are **French companies** — see Blocker 2 — currently carrying a
   `country_code='DE'` capability. If `country_code` means *served*, they may already be the
   right answer for FR-origin and simply need an FR capability row. That is 2, not 3.
3. **Lower the Phase 0 gate to 2** and proceed, accepting thinner origin supply for the beta.

---

## BLOCKER 2 — there is no column for "where a vendor is based"

Addendum A §S2 makes eligibility `vendor.based_in ∈ catchment.all`. Measured:

| candidate source | state |
|---|---|
| `suppliers.incorporation_country` | **0 of 108 populated** |
| `supplier_service_capabilities.country_code` | means the country **served**, not the base |
| `supplier_service_area_coverage` | **8 rows total**, all Oslo living areas (`la-o1`…`la-o5`) |
| `service_catalog_items.city, country` | populated — this is what `item_country()` reads |

The evidence that `country_code` is the *served* country, not the base: **AGS France (SOFDI –
Société Française de Déménagement International)** and **Grospiron International** are French
firms whose capability rows are `country_code='DE'` and `'NO'`. Under a "based_in" reading, the
data says two French movers are German.

**Consequence:** the spec is implementable on the **curation** side (C1/C5/C6 resolve vendor
country through `item_country(master_item_id)` → `service_catalog_items.country`), but **not on
the recommendation-engine side** (C7, B1), which reads `suppliers` / `supplier_service_capabilities`
and has no base-country field to filter on.

Addendum A §A.5 does not add one. Something must, before Phase 2 can implement
`search_by_service_corridor(origin_country, …)` as anything other than a no-op.

**Options:** add `suppliers.based_in_country char(2)` and backfill it (SIREN prefixes give FR for
the four new rows; FIDI affiliate pages give the rest); or redefine eligibility in terms of an
existing field and amend the spec. Either changes §A.5, so it is a spec decision, not an
implementation detail.

---

## Not done, deliberately

- **No supplier was approved.** Vetting is a trust boundary and the prompt says so explicitly.
- **No schema, no code, no migration.** Phase 0 is data-only.

## One precondition to flag

Precondition #4 says the five reference documents are *committed*. They are **present but
untracked** — `audit/ReloPass_Vendor_Sourcing_Addendum_2026-08-13.md`,
`audit/ReloPass_HR_Catchment_UX_Proposal.md`,
`audit/ReloPass_Data_Integration_Audit_2026-08-13.md`,
`design/relopass-hr-catchment-mockup.html`, `evals/relopass_integration_evals.py`.

They are readable, so this did not block Phase 0. But CI cannot see them, no other agent or
worktree has them, and a stray `git checkout` loses the spec this whole workstream depends on.
Worth committing before Phase 1.
