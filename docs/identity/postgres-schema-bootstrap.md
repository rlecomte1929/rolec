# Postgres: `employee_contacts` and canonical identity tables

## Symptom

- HR “Assign” fails with `relation "employee_contacts" does not exist`.
- Usually means **Supabase SQL migrations were not applied** to the linked database, while the app is deployed with **`DISABLE_RUNTIME_DDL=1`** (Render), so the Python runtime does not run the full SQLite-style `init_db` DDL.

## Fix (preferred)

Apply migrations from the repo on your Supabase project (CLI or Dashboard), especially:

- `supabase/migrations/20260320120000_canonical_identity_employee_contacts.sql`
- `supabase/migrations/20260321120000_employee_contacts_unique_email_per_company.sql`
- `supabase/migrations/20260410120000_identity_link_guardrails.sql`

## Automatic bootstrap (app)

On startup, if the DB is **Postgres** and **`public.employee_contacts` is missing**, `Database._maybe_ensure_postgres_canonical_identity_schema()` runs **idempotent** DDL aligned with those migrations (tables, `case_assignments.employee_contact_id`, indexes, RLS policies for `service_role`).

After deploy, **restart the Render service** once so the API runs this step; then retry HR assign.

**Note:** Prefer migrations for long-term consistency; the bootstrap is a safety net for drift between app and DB.
