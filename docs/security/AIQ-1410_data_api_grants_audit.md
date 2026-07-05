# AIQ-1410 — Supabase Data-API grant audit (Oct-30 2026 deadline)

**Status:** audit complete — draft grant migration pending human review.
**Prod project audited:** `nsvefcvpvwwwhuqyuqmp` (read-only). **Date:** 2026-07-05.
**Source:** Friday Digest 2026-07-03 · [Supabase June-2026 changelog](https://supabase.com/changelog/46689-developer-update-june-2026)

## Background
From **2026-10-30**, Supabase enforces that a table must have explicit Postgres GRANTs to the
`anon` / `authenticated` roles before the Data API (PostgREST + Realtime) can access it. The old
behaviour auto-granted these; new-project default flipped on 2026-05-30, and enforcement hits **all**
projects on Oct 30. A table the frontend reaches via the Supabase anon/authenticated key that lacks
grants will silently lose Data-API access.

## Method
1. `information_schema.role_table_grants` — grant status of every `public` base table for `anon` /
   `authenticated` / `PUBLIC`.
2. `pg_policies` — which tables carry RLS policies targeting `anon`/`authenticated`.
3. `grep supabase.from( / realtime .channel` in `frontend/src` — the tables the app **actually**
   reaches via the Data API (vs. the FastAPI backend, which uses `service_role` and is unaffected).
4. `pg_class.relrowsecurity` — RLS on/off for the candidate tables.

> Note: Postgres stores no table creation timestamp, so the "created after 2026-05-30" filter can't be
> computed reliably. The audit instead keys on the **decision-relevant** signal: does a table the
> frontend hits via the Data API have the grant it needs? That is what determines Oct-30 breakage.

## Findings

### Tier 1 — Unaffected by design (no action)
**320 public tables; 296 have no `anon`/`authenticated` grant.** This is expected: ReloPass routes
almost all data through the FastAPI backend (`service_role`, which bypasses Data-API grants), and the
SEC-002 remediation deliberately locked tables backend-only (`REVOKE ALL ... FROM anon`). These tables
do **not** use the Data API, so the Oct-30 change does not affect them. A vestigial `authenticated`
RLS policy without a grant is harmless when the app never reaches the table via the Data API.

### Tier 2 — Data-API tables already granted (safe)
Of the ~15 tables the frontend reaches directly, these already carry explicit grants — **no action**:
`feedback`, `pets`, `rp_debug_kv`, `ai_spend_requests`, `error_logs`, `error_tickets`.

### Tier 3 — Data-API tables with ZERO grants (review candidates)
These 9 are referenced by the frontend Supabase client but have **no** `anon`/`authenticated`/`PUBLIC`
grant today:

| Table | RLS | Frontend usage | Realtime | Grant if kept on Data API |
|---|---|---|---|---|
| `notifications` | on | realtime sub | ✅ | `SELECT` → authenticated |
| `case_forms` | on | realtime sub | ✅ | `SELECT` → authenticated |
| `provider_tasks` | on | realtime sub | ✅ | `SELECT` → authenticated |
| `profiles` | on | `.insert` + `.select` | – | `SELECT, INSERT` → authenticated |
| `notification_preferences` | on | `.select` | – | `SELECT` → authenticated |
| `policy_documents` | on | `.select` | – | `SELECT` → authenticated |
| `daily_summaries` | on | `.select` | – | `SELECT` → authenticated |
| `pet_import_rules` | on | `.select` | – | `SELECT` → authenticated |
| `supplier_stats` | **OFF** | `.select` | – | ⛔ do NOT grant until RLS is added |

## Interpretation & risk
Because these 9 **already have zero grants** and the app currently functions, ReloPass does **not**
meaningfully depend on the Data-API auto-grant — so **Oct-30 is close to a no-op for the platform**.
The residual, genuine questions are:
- **Realtime subscriptions** (`notifications`, `case_forms`, `provider_tasks`): Realtime needs `SELECT`
  to `authenticated` to deliver row changes under RLS. If these subs are live and relied upon, they
  need the grant; if they already silently no-op (the app tolerates it via backend polling), no action.
- **`profiles`** `.insert`/`.select`: verify whether these calls are live Data-API dependencies or
  legacy/fallback paths superseded by the backend.

**⚠️ Security caveat (important):** adding `anon`/`authenticated` grants **opens** Data-API access to a
table (gated only by its RLS) — the opposite direction from SEC-002. So grants must be added
**per-table**, only where the frontend genuinely needs Data-API access, and only after confirming the
table's RLS correctly scopes rows. Do not blanket-grant. `supplier_stats` has **RLS off** — granting it
would expose all rows to any logged-in user; add RLS first or leave it backend-only.

## Recommendation
1. Confirm (with Romain / a quick runtime check) which of the 9 the frontend truly needs via the Data
   API. Realtime `notifications`/`case_forms`/`provider_tasks` are the priority to verify.
2. For the confirmed subset, apply the reviewed grants from
   `supabase/migrations/20260826000000_data_api_grants_frontend_review.sql` — **dev branch first**, then
   prod, after RLS verification. Leave `supplier_stats` out until it has RLS.
3. Everything else (Tier 1/2) needs no action.

**Bottom line:** No blanket Oct-30 exposure — ReloPass is backend-routed and the Data-API tables that
matter are already granted. The draft migration covers the 9 edge tables for a deliberate, reviewed
decision, not an automatic apply.
