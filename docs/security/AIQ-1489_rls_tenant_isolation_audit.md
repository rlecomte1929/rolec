# AIQ-1489 — Supabase RLS Tenant-Isolation Audit

**Date:** 2026-07-13
**Project:** `nsvefcvpvwwwhuqyuqmp` (rolec-eu prod)
**Method:** Supabase RLS Tester is a dashboard-only feature preview (not automatable), so this
audit used the task's specified fallback — SQL-level policy inspection plus in-transaction
role impersonation (`SET LOCAL ROLE authenticated` + `request.jwt.claims`), all inside
`BEGIN … ROLLBACK` (read-only; nothing persisted).
**Verdict:** **PASS — no cross-tenant data leak found on any vector.** One functional defect
class found (RLS policies that error instead of filtering); fix built + validated + PR'd.

## Test tenants

| Label | company_id | Signal |
|---|---|---|
| Company A | `110854ad-3c85-4291-a484-0b43effb680e` | 243 relocation_cases; HR `hr_test@relopass.com` (`8f22ff4b…`, non-admin) |
| Company B | `c0000000-0000-0000-0000-000000000001` | 32 cases, 46 case_forms; HR `12b74a97…` |

## Structural coverage

| Check | Result |
|---|---|
| Public tables total | 324 |
| Tables with RLS **disabled** | **0** |
| Tables with RLS on but **zero policies** | **0** |
| Company-scoped tables (`company_id`/`hr_company_id`) | 53 |
| Company-scoped tables missing RLS | **0** |
| Tables `anon` can SELECT | 1 (`auth_page_config` — non-tenant UI config; intended) |
| `USING (true)` non-service policies | all on shared reference data (country/knowledge/form catalogs) or unreachable (no grant) |

`policy_calibration_alerts` has a permissive `WITH CHECK (true)` INSERT policy but **no table
grant** to anon/authenticated → unreachable. Defense-in-depth held.

## Cross-tenant probe (as Company-A HR, non-admin)

Only the 14 tenant/case-scoped tables that `authenticated` actually holds a SELECT grant on are
reachable from a client; `relocation_cases`, `cases`, `mobility_cases`, `hr_users`, etc. have **no
`authenticated` grant at all** (service-role-only) so a client cannot read them regardless of RLS.

| Vector | Result |
|---|---|
| SELECT other-tenant rows across all 14 reachable scoped tables | **0 rows** on every table |
| Positive control: `policy_documents` as Company-A HR | 14 rows, all Company A (proves impersonation live + RLS filtering) |
| Positive control: `case_forms` as Company-B HR | exactly 46 of 67 (own tenant only) |
| Cross-tenant INSERT (`company_preferred_suppliers` tagged to Company B) | BLOCKED (42501 WITH CHECK) |
| Cross-tenant UPDATE (`policy_documents` of Company B) | BLOCKED (0 rows) |
| Privilege escalation (self-INSERT into `admin_allowlist`) | BLOCKED (42501) |
| Non-admin write to reference data (`country_profiles`) | BLOCKED (0 rows / `is_admin()` gate) |

## Finding F1 — RLS policies that error instead of filtering (functional bug, not a leak)

Three tables' policies subquery a table the caller cannot SELECT. RLS subqueries run under the
caller's grants, so the read raises `42501 permission denied` for the **inner** table rather than
filtering — the request 500s. Fails **closed** (no data exposure) but breaks the feature.

| Table | Policy | Subqueries (ungranted) | Impact |
|---|---|---|---|
| `pets` | `pets_via_case` | `public.cases` | **User-facing** — `PetRequirementsSection.tsx` reads `pets` directly → pet-import section 500s for every user |
| `case_forms` | `case_forms_via_case` | `public.cases` | Direct-from-client case_forms reads 500 |
| `provider_tasks` | `provider_tasks_hr_all`, `provider_tasks_provider_select/update` | `hr_users`, `providers`, `vendor_users` | Direct authenticated reads 500 (backend uses service-role, so backend paths unaffected; JWT-claim policies were never broken) |

AIQ-1366 granted SELECT on `pets` believing that fixed it — necessary but not sufficient, because
the `pets_via_case` policy still subqueries `cases`.

**Fix (this PR):** move each cross-table lookup into a `SECURITY DEFINER` helper
(`user_owns_case_row`, `user_provider_ids`; HR path reuses existing `hr_company_ids()`) — the
same pattern already used by `user_has_case_access` / `my_company_id`. The tenant-scoping
predicate is copied verbatim, so isolation is unchanged; only the grant mechanism changes.
Migration `supabase/migrations/20260911000000_fix_case_scoped_rls_secdef.sql`.

**Validated (rollback tx):** post-fix, `pets`/`case_forms`/`provider_tasks` reads no longer error;
Company-B HR still sees exactly their 46 case_forms and zero cross-tenant; idempotent re-run clean.

> Migration is **not** applied here — per repo policy schema changes are applied out-of-band and
> the ledger reconciled after. Reviewer action below.

## Reviewer actions

1. Review the migration diff.
2. Apply out-of-band to prod (`nsvefcvpvwwwhuqyuqmp`), then reconcile the ledger at version `20260911000000`.
3. Smoke-test: open an employee case with the pet-import section → confirm it loads (no 500).
