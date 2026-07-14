# AIQ-1528 — `init_db()` runtime DDL against production Postgres

**Date:** 2026-07-14 · **Status:** fixed (Postgres now skips boot DDL by default)

## The finding

`Database.init_db()` (`backend/db/misc.py`, lines 391–3073) executed **248 unguarded DDL
statements** against **production Postgres on every boot**, written in SQLite shape.

Structural audit of the function (guard determined by enclosing indentation, not by a nearby
mention of `_is_sqlite`):

| | count |
|---|---|
| DDL statements inside `init_db()` | **303** |
| …inside an `if _is_sqlite:` block (safe) | 55 |
| …inside an `if not _is_sqlite:` block (deliberate Postgres DDL) | **0** |
| …**unguarded** — reached Postgres | **248** |

They cover **125 tables**, including core ones: `profiles`, `companies`, `relocation_cases`,
`users`, `audit_logs`, `sessions`, `quotes`, `rfqs`, and the whole `policy_*` family.

`exception_requests` — the table that tripped the CI gate — was never an outlier. It was the one
that happened to get caught.

## Why it mostly looked fine

Of the 125 tables, **123 already exist in prod** (created properly, by migrations). For those,
`CREATE TABLE IF NOT EXISTS` is a silent no-op. The system appeared healthy.

The damage was the exception: **a table that a migration had NOT created got conjured by the app
instead** — with `text` ids, `text` timestamps, and, because an app-issued `CREATE TABLE` grants
nothing, **no RLS and no policies**.

That is precisely `public.exception_requests`:

- its migration (`20260503100000`) declares `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
- prod actually had `id: text, created_at: text` — the SQLite shape
- it had **RLS disabled and 0 policies**

And it is why its RLS was **lost twice in a single day**: the symptom kept being `ALTER`ed back
while the boot code kept re-asserting the cause.

### The 2 tables that don't exist in prod

`employee_cap_overrides` and `audit_log` are in `init_db` but absent from prod — the app's DDL for
them fails silently and is swallowed. They were already missing; the guard changes nothing for
them. If they are needed, they need a **migration**.

### Tables carrying the SQLite fingerprint (`created_at: text`)

18 tables, including `users`, `employees`, `hr_users`, `hr_policies`, `relocation_cases`,
`sessions`, `support_cases`, `compliance_*`. **All currently have RLS enabled and ≥1 policy**, so
this is legacy type debt, not an open door. Worth a separate cleanup; not urgent.

## The fix

The escape hatch **already existed and was already correct**. `init_db()` opens with:

> *"In production (Render), avoid runtime DDL. Supabase migrations are the source of truth."*

…followed by an early return that still runs the healthcheck and every seed. It was simply gated
on an env var — `DISABLE_RUNTIME_DDL` — that **nobody had set in production**. Prod logs contain
no "Runtime DDL disabled" line; the DDL ran on every boot.

**Postgres now skips the boot DDL by default.** Opting back in is possible (`ALLOW_RUNTIME_DDL=1`)
but must be a deliberate act.

> A default that depends on someone remembering an env var is not a guard. It is a coin toss.

`DISABLE_RUNTIME_DDL` is retained for back-compat and is now redundant.

## Safety

- **123 / 125** tables already exist → the skipped DDL was a no-op for them.
- **2** missing tables were already failing to be created → nothing regresses.
- The skip path still runs `_db_healthcheck`, `seed_readiness_templates_if_empty`,
  `ensure_missing_readiness_templates`, `seed_dossier_questions_if_missing`, and
  `_backfill_employee_contacts` — pinned by test.
- **SQLite is unaffected.** Local dev and the test suite have no migrations and still build their
  schema from `init_db`.

## Tests

`backend/tests/test_init_db_no_runtime_ddl.py` pins the guard by observing whether execution
passes the early return (`_maybe_ensure_postgres_missing_schemas` is the first statement after it).
Mutation-checked: restoring the old env-gated condition fails the test.

## Follow-ups (not done here)

1. **Reconcile the 18 text-timestamp tables** to `timestamptz` — legacy debt, has live rows, needs
   its own migration and care.
2. **Decide on `employee_cap_overrides` / `audit_log`** — currently referenced by code but absent
   from prod. Either migrate them in or remove the dead references.
3. **Consider deleting the DDL from `init_db` entirely** and giving SQLite a schema fixture. The
   guard makes it inert on Postgres, but 2,700 lines of duplicated schema will drift from the
   migrations sooner or later.
