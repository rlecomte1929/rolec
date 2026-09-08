# Vendor Phase 0 — corrected handoff prompt

**Context date:** 2026-07-19 · **Repo:** `rlecomte1929/rolec` · **Supabase:** `nsvefcvpvwwwhuqyuqmp`
**Replaces** the Phase 0 prompt drafted by Otto. Sections on store topology, Option A ratification and the 8-row archive decision are **kept as written** — they were correct. Four things are changed; each is flagged inline.

---

## CONTEXT — ReloPass vendor Phase 0

### Store topology (confirmed — do not re-litigate)

- **Canonical vendor store = Supabase `public.suppliers`** + satellites (`supplier_service_capabilities`, `supplier_scoring_metadata`, `supplier_cluster_cache`, `company_preferred_suppliers`, `hr_supplier_submissions`, `supplier_ranking_weights`). 17 prod rows, 89 code refs. RFQ/recommendation/scoring code already queries it.
- **The deployed system already co-locates in Supabase:** `relocation_cases` (496 live), RFQs (9 live), `suppliers` (17). **Option A is RATIFIED — this is NOT a migration.** Nothing to move, no cross-store FK, no bridge, no sync. The tables already live together.

### Hard operating rule (silent-failure guard)

All new vendor/RFQ/policy/budget tables **must** be created in **Supabase**, never Audos WorkspaceDB. If they land in WorkspaceDB nothing errors — the deployed app simply never reads them, and it surfaces weeks later as an empty vendor list. Otto's DB tools reach only WorkspaceDB and **cannot verify Supabase**; the Cowork/Cursor side is the source of truth there.

### Deprecation — all THREE names across BOTH stores

Do all three, or the trap relocates.

1. **Supabase `vendors`** — 0 rows, already carries a DEPRECATED comment → **DROP** (via committed migration).
2. **WorkspaceDB `relopass_vendors`** — 0 rows, 22 cols (task #83885), no code reads it → **DROP**. This is the "third name" trap: it exists in WorkspaceDB even though it never existed in Supabase.
3. **WorkspaceDB `vendors`** — 8 legacy GlobeIQ demo rows → **ARCHIVE & DROP, do NOT migrate.** All one demo batch (created 2026-06-30, `session_id` NULL, blanket `country_coverage` arrays). None cover Norway except Fragomen, which is already in Supabase `suppliers`. Export the 8 rows to `data/archive/workspacedb-vendors-legacy-20260719.json` for audit, then drop. The 5 FR-touching names (Fragomen, Crown, Dwellworks, Bright Horizons, HSBC) are a **re-authoring shortlist only** — they re-enter through the verify pipeline per corridor if needed, never as a raw copy.

**Never create a table named `relopass_vendors` in Supabase.** The name is retired.

---

## SEQUENCE

### A. SEED GAP FIRST *(unchanged — this was right)*

Seed files hold **80** suppliers (movers 10, living_areas 38, schools 32); prod `suppliers` = **17 rows** (~21% loaded). Establish, before any other work:

- why only 17 of 80 landed — partial run, failure, or filtering by design;
- whether `seed_suppliers.py` is **idempotent-safe** to re-run against production;
- the **true verified count per service category** today.

Do not author new categories on a 21%-loaded seed. The "5 verified per category" deliverable depends on this number and is currently unknown.

### B. APPROVAL GATE — ⚠️ CHANGED

The 9 pending Norway suppliers (`no-leg-1/2`, `no-mv-1/2`, `no-bk-1/2/3`, `no-tf-1/2`) and 3 Oslo schools (`s-o1/2/3`) are **presented to Romain for review — not approved by any agent.**

The prior draft said "flip verified ones to approved". That converts a human gate into an agent action. **Do not flip any record to approved.**

Produce a review table, one row per supplier: name · service category · corridor · source of the record · what was verified and how · what remains unverified. Romain decides. Supplier records are the product's credibility surface; an agent-approved supplier that turns out to be wrong is a customer-facing failure.

### C. AUDIT BEFORE CREATE — ⚠️ SUBSTANTIALLY CHANGED

**The prior draft proposed creating `rfq_requests`, `rfq_recipients`, `quotes`, `quote_line_items`, `policy_profiles`, `policy_caps`, `budget_estimates`. Every one of those already exists in Supabase, several with live data.** Creating them would add a fourth parallel model to a layer that already has three.

Current state, verified 2026-07-19:

| Table | Rows | Cols | RLS |
|---|---|---|---|
| `rfq_requests` | 25 | 19 | ✅ |
| `quote_requests` | 21 | 11 | ✅ |
| `rfq_recipients` | 17 | 12 | ✅ |
| `quote_lines` | 10 | 4 | ✅ |
| `quote_conversations` | 9 | 5 | ✅ |
| `rfq_items` | 9 | 5 | ✅ |
| `rfqs` | 9 | 17 | ✅ |
| `quotes` | 6 | 9 | ✅ |
| `policy_cap_requests` | 1 | 16 | ✅ |
| `quote_participants` | 0 | 4 | ✅ |
| `case_budget_lines` | 0 | 5 | ✅ |
| `quote_messages` | 0 | 5 | ✅ |

There are **three overlapping RFQ/quote models** already live:

1. `rfqs` + `rfq_items` + `rfq_recipients` — 9 / 9 / 17
2. `rfq_requests` — 25
3. `quote_requests` + `quotes` + `quote_lines` + `quote_conversations` — 21 / 6 / 10 / 9

**Deliverable for C is an audit, not a schema.** Produce:

- which model each is written and read by — cite router and service file paths (`hr_rfq.py`, `supplier_rfq.py`, `employee_quotes.py`, `rfq_brief.py`, `rfq_evaluation_service.py`, `rfq_recipient_mapping.py`);
- which is **canonical**, and which are legacy or abandoned;
- what the live rows in the non-canonical models represent — real usage or test residue;
- a consolidation recommendation, with what gets deprecated.

**Then stop.** No new RFQ/quote/budget table is created until the canonical model is agreed. This is the same defect pattern currently being arbitrated in the policy layer (four overlapping attempts at AIQ-1631/1635/1636 + `fix/f14-shared-taxonomy`) — do not reproduce it here.

Extending Supabase `suppliers` with `rfq_channel`, `response_sla_days`, `quality_signal`, `reverify_due` is **in scope after A and B**, since `suppliers` is confirmed canonical. That is additive to an agreed table and carries no fragmentation risk.

---

## HARD GATES — ⚠️ ADDED (missing from the prior draft)

### Any new `public` table in Supabase requires all three

```sql
ALTER TABLE public.<t> ENABLE ROW LEVEL SECURITY;
CREATE POLICY "<descriptive name>" ON public.<t> FOR SELECT USING (/* tenant scoping */);
REVOKE ALL ON public.<t> FROM anon;
```

The anon key ships in the frontend bundle and Supabase exposes `public` via PostgREST — a table without RLS is readable by any unauthenticated visitor. This caused **SEC-002** (8 tables, GDPR-scope PII exposure). Canonical pattern: the `case_milestones` policies. Note every existing RFQ/quote table already meets this standard; do not be the exception.

### Migration discipline

Commit `supabase/migrations/<timestamp>_<name>.sql` with **idempotent** DDL. **Never apply to production**, never write to `supabase_migrations.schema_migrations`. The operator applies out-of-band and reconciles the ledger. Any migration — including the `vendors` DROP — is 🔴 **Red, human-gated**.

### Router registration (if any endpoint is added)

Register in **both** `backend/app/main.py` **and** `backend/main.py`. Render boots `uvicorn backend.main:app`; registering only in the modular app returns **405 in production**. This has caused three incidents. Verify:

```bash
python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if '<prefix>' in r.path))"
```

---

## BRANCH DISCIPLINE — ⚠️ CHANGED

Cut a **dedicated branch off `main`**: `feat/vendor-phase-0`.

The prior draft targeted `fix/td-qa-services-batch-0719`. That branch already carries the Stripe spec docs and 2 migrations from #84567, plus the TD-QA services batch. Adding vendor Phase 0 produces a PR mixing three unrelated concerns, which cannot be reviewed or reverted cleanly.

---

## REPORT BACK

```
A. SEED GAP
   True verified supplier count PER category after load: ____
   Why only 17 of 80 landed: ____
   seed_suppliers.py idempotent-safe to re-run? ____

B. APPROVAL GATE
   Review table for the 9 Norway + 3 Oslo school records: [attach]
   Records flipped to approved by an agent: MUST BE ZERO ____

C. RFQ/QUOTE AUDIT
   Canonical model: ____
   Legacy/abandoned: ____
   What the non-canonical live rows represent: ____
   Consolidation recommendation: ____
   [STOPPED — no new tables created]

DEPRECATION
   Supabase vendors: ____ | WorkspaceDB relopass_vendors: ____ | WorkspaceDB vendors archived+dropped: ____
   Archive JSON path: ____

BRANCH: feat/vendor-phase-0 (off main) ____
No table created in WorkspaceDB: ____
```

**DO NOT:** create `relopass_vendors` anywhere · put any new table in WorkspaceDB · migrate the 8 legacy rows · author new service categories before the seed count is known · **create any RFQ/quote/budget table before the §C audit is agreed** · **approve any supplier record without Romain**.
