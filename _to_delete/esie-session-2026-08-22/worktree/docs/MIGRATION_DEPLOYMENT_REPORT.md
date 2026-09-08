# Policy Migration Deployment Report

## 1. Migration file responsible for `policy_documents`

**Primary:** `supabase/migrations/20260329000000_policy_documents.sql`  
**Reconciliation (idempotent):** `supabase/migrations/20260403000000_policy_engine_reconciliation.sql`  
**Catch-up (new):** `supabase/migrations/20260404000000_production_policy_catchup.sql`

All three create `public.policy_documents`; the reconciliation and catch-up use `CREATE TABLE IF NOT EXISTS` and also create the other policy tables.

---

## 2. Tables created by reconciliation / catch-up

| Table | Created by reconciliation (20260403) | Created by catch-up (20260404) |
|-------|--------------------------------------|--------------------------------|
| policy_documents | ✓ | ✓ |
| policy_document_clauses | ✓ | ✓ |
| policy_versions | ✓ | ✓ |
| policy_benefit_rules | ✓ | ✓ |
| policy_rule_conditions | ✓ | ✓ |
| policy_exclusions | ✓ | ✓ |
| policy_evidence_requirements | ✓ | ✓ |
| policy_assignment_type_applicability | ✓ | ✓ |
| policy_family_status_applicability | ✓ | ✓ |
| policy_tier_overrides | ✓ | ✓ |
| policy_source_links | ✓ | ✓ |
| resolved_assignment_policies | ✓ | ✓ |
| resolved_assignment_policy_benefits | ✓ | ✓ |
| resolved_assignment_policy_exclusions | ✓ | ✓ |
| assignment_policy_service_comparisons | ✓ | ✓ |

---

## 3. Why production still does not have the table

**Most likely:**

1. **`supabase db push` never completed** – You must confirm with `Y` at the prompt. If you don’t, migrations are not applied.
2. **CLI not linked / configured for production** – `supabase link` must point to the same project as your app. Project ref in config is `rolec`; the linked project ID is shown when you run `supabase link --project-ref <id>`.
3. **Missing `SUPABASE_DB_PASSWORD`** – `supabase migration list` and `db push` need the DB password. Set it as an env var or pass it when prompted.
4. **Earlier migration failure** – If any migration before `20260329` fails, later ones (including `20260329` and `20260403`) never run.
5. **Duplicate timestamps** – These timestamps are shared: `20260304` (policy_version_status, rkg_resources), `20260305` (resolved_assignment_policies, resources_cms_workflow), `20260312` (review_queue, supplier_registry). That can cause `schema_migrations_pkey` conflicts in some setups.

---

## 4. Exact terminal commands to run now

### Option A: Push via CLI (preferred)

```bash
# 1. Ensure you're linked to the production project
cd /Users/Rom/Documents/GitHub/rolec
supabase link --project-ref <YOUR_PRODUCTION_PROJECT_REF>

# 2. Set DB password (required for push)
export SUPABASE_DB_PASSWORD='<your-database-password>'

# 3. Push all pending migrations (confirm with Y)
supabase db push --include-all

# 4. Check status
supabase migration list
```

### Option B: Manual run in Supabase SQL Editor (if CLI push fails)

1. In Supabase Dashboard: **Project → SQL Editor**
2. Copy the contents of `supabase/migrations/20260404000000_production_policy_catchup.sql`
3. Paste into the editor and run
4. Tables will be created; `schema_migrations` will not be updated
5. Later, run `supabase db push` so migrations are recorded (idempotent `IF NOT EXISTS` will succeed)

---

## 5. Whether a new catch-up migration was created

**Yes.** Created: `supabase/migrations/20260404000000_production_policy_catchup.sql`

It creates all policy tables idempotently. Use it either via `supabase db push` or by running its SQL in the Supabase SQL Editor.

---

## 6. Exact SQL checks to run after migration

Run in **Supabase SQL Editor**:

```sql
-- 1. Table existence (should return 16 rows)
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'policy_documents',
    'policy_document_clauses',
    'policy_versions',
    'policy_benefit_rules',
    'policy_rule_conditions',
    'policy_exclusions',
    'policy_evidence_requirements',
    'policy_assignment_type_applicability',
    'policy_family_status_applicability',
    'policy_tier_overrides',
    'policy_source_links',
    'resolved_assignment_policies',
    'resolved_assignment_policy_benefits',
    'resolved_assignment_policy_exclusions',
    'assignment_policy_service_comparisons',
    'company_policies'
  )
ORDER BY tablename;

-- 2. Quick smoke test: policy_documents exists and is queryable
SELECT COUNT(*) AS policy_docs_count FROM public.policy_documents;

-- 3. Migration history (optional: see which migrations were applied)
SELECT version, name FROM supabase_migrations.schema_migrations
WHERE version LIKE '202603%' OR version LIKE '202604%'
ORDER BY version;
```

Expected for (1): 16 rows.  
Expected for (2): 0 initially.  
If (1) returns 0 rows for `policy_documents`, the migration did not run successfully.
