# Execution Prompt — SEC-RLSd · RLS for Catalog / Seed Tables

**Notion:** AIQ-661 — `https://www.notion.so/370887c64d488182b78cc3d99d600b4c`
**Parent sprint:** AIQ-649. Parallel with SEC-RLSa/b/c/e; SEC-RLSf closes.
**Priority:** **P0** · **Complexity:** Medium · **Branch:** `audit/stage-1-rls-d-catalog`

## Role
Backend engineer. You give public-read seed tables an explicit RLS policy (SELECT for everyone; writes locked down) instead of leaving them naked behind the anon key. This is the lowest-effort subtask in the sprint, but it has to be exact.

## Read first
- `supabase/rls_allowlist.txt` — pick the catalog/seed tables (list below).
- `scripts/check_rls_coverage.py` — CI gate.
- `supabase/migrations/20260302000000_country_resources.sql` and the `_seed*` migrations — to confirm what's data-only vs. user-input.

## Tables in scope (verify; some are gray-area and may belong to SEC-RLSe)
Public-read catalog / seed data:
- `country_events`, `country_profiles`, `country_resource_items`, `country_resource_sections`
- `requirements_catalog`, `requirement_items`
- `default_policy_templates`
- `compliance_reference_sources` (could belong to SEC-RLSb if HR-uploads — verify)
- `catalog_employee_demand`, `catalog_scrape_quota` (likely server-only — triage; may move to SEC-RLSe)
- `relocation_sources` (verify — could be cases-domain SEC-RLSa)

Triage rule: if it's pure reference data the frontend reads anonymously to render dropdowns / lookups, it belongs here. If it's user-input or per-tenant, it belongs in a/b. If it's only written by background jobs and never read by clients, it belongs in e.

## Migration shape
`supabase/migrations/<NEW-TS>_rls_catalog_seed.sql` (timestamp > `20260531000000`):

```sql
ALTER TABLE public.<table> ENABLE ROW LEVEL SECURITY;

-- Anyone (including anon) may read.
CREATE POLICY "<table>_public_select" ON public.<table>
  FOR SELECT TO anon, authenticated
  USING (true);

-- Writes locked to admin / service_role only.
CREATE POLICY "<table>_admin_write" ON public.<table>
  FOR ALL TO authenticated
  USING (
    auth.uid() IN (SELECT user_id FROM public.admin_allowlist)
  ) WITH CHECK (
    auth.uid() IN (SELECT user_id FROM public.admin_allowlist)
  );

-- Defense in depth — anon explicitly stripped of write privileges.
REVOKE INSERT, UPDATE, DELETE ON public.<table> FROM anon;
```

Note: we **don't** `REVOKE SELECT FROM anon` here — these tables are public-read by design.

## Allowlist update
Remove every triaged table from `supabase/rls_allowlist.txt`. For any catalog table you decide to leave on the allowlist (e.g. you triage it server-only after all), keep the entry and add a `# reason` comment — that comment is what SEC-RLSf will validate.

## Tests
`backend/tests/integration/test_rls_catalog_seed.py`:
1. Anon GET `/rest/v1/country_profiles?select=*` → returns rows (still public-readable).
2. Anon POST `/rest/v1/country_profiles` → 401 / 403.
3. HR Admin user GET → returns rows.
4. Admin allowlisted user POST → 201.
5. Non-admin authenticated user POST → 401 / 403.

## Frontend regression check
Before merging, run a smoke pass against the parts of the SPA that hit these tables anonymously (country pickers, requirements catalog dropdowns, public marketing pages). Open DevTools Network and confirm 200s for all `GET /rest/v1/country_*` calls under the anon key.

## Constraints
- Do not break anonymous public reads — these tables are intentionally exposed.
- Lock writes to admin / service_role via `admin_allowlist` — match the existing `is_admin()` semantics in the backend.
- If a table currently has no writers from the frontend, prefer keeping the allowlist entry with a `# server-write only` comment over adding a policy.

## Test commands
```
python scripts/check_rls_coverage.py --allowlist supabase/rls_allowlist.txt
cd backend && pytest backend/tests/integration/test_rls_catalog_seed.py -v
# Smoke against staging:
curl "https://<project>.supabase.co/rest/v1/country_profiles?select=code,name&limit=3" -H "apikey: <anon>"
```

## Definition of done
- Single migration applies cleanly.
- Catalog tables have public-read + admin-write policies; allowlist drained for triaged entries.
- Frontend public lookups still work.
- Tests green; CI rls-coverage green.
- Notion AIQ-661 → Human Review with allowlist delta + sample anon-read response.
- Commit per CLAUDE.md Build Hygiene rules.
