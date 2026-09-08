# RLS second barrier for `policy_assistant_chunks` (F3 / AIQ-834)

## What & why

Tenant isolation for the policy-assistant vector store used to rest entirely on a
single application-layer `WHERE company_id = :co` clause. RLS was *enabled* on
`policy_assistant_chunks` but **inert**, because the backend connects as the
Postgres role `postgres`, which has `BYPASSRLS` and ignores policies.

Isolation was correct *today* (the predicate is server-derived and null-guarded),
but the blast radius of any future regression — a new query omitting the
predicate, or `company_id` ever flowing from user input — was complete
cross-tenant policy-PII exposure with **no second line of defense**.

This change adds that second line:

1. A dedicated **least-privilege role `relopass_api`** (no `BYPASSRLS`).
2. A request-scoped **RLS policy** on `policy_assistant_chunks` keyed on a
   transaction-local GUC `app.current_company_id`.
3. The retriever sets that GUC (`set_config('app.current_company_id', <uuid>,
   true)`) in the same transaction as the similarity query.

With the backend connected as `relopass_api`, a query that omits the WHERE clause
**still** returns only the current company's rows — Postgres enforces it.

## What shipped (this PR)

- `supabase/migrations/20260611000000_relopass_api_rls_barrier.sql` — creates the
  role (`NOLOGIN`), grants, and the `pac_select_relopass_api` policy. Additive; no
  data change; no existing policy dropped.
- `backend/app/services/policy_chunk_retriever.py` — sets the GUC in the same
  transaction (`db.request_engine.begin()`), via `set_config(..., is_local=true)`
  which survives the Supabase transaction-mode pooler (a session-level `SET ROLE`
  would not).
- `backend/db_config.py` + `backend/database.py` — an optional dedicated request
  engine (`db.request_engine`) driven by `RELOPASS_API_DATABASE_URL`. **Falls back
  to the existing superuser engine when unset**, so this is a no-op until the role
  is provisioned (safe dark-ship).
- `backend/tests/test_rls_second_barrier.py` — the isolation regression test
  (session-mode Postgres; skips otherwise).

## Validation already performed

- The migration DDL was applied in a **rolled-back** transaction against the
  production database (Supabase) — valid, no residue.
- The policy predicate semantics were proven live: company-A row visible to A,
  company-B row blocked for A, and an unset/blank GUC **fails closed** (zero
  rows, never "all rows").
- **RLS enforcement proven live (rolled back) against the production database:**
  a non-`BYPASSRLS` role with the GUC policy, querying with **no WHERE clause**,
  returned only company A's rows (2), and zero rows when the GUC was unset, while
  the bypass path saw all 4. Reproduce with `python scripts/verify_rls_guc_barrier.py`
  or `RELOPASS_RLS_TEST_DB_URL=<session-url> pytest backend/tests/test_rls_second_barrier.py`.

### Connection notes (why the proof uses `authenticated`, not `relopass_api`)

The Supabase **transaction-mode** pooler (port 6543, used by the app and the MCP)
rejects session commands like `SET ROLE`. The **session-mode** pooler (same host,
**port 5432**) supports them. But the pooler also rejects granting role membership
to its own login user (`GRANT <role> TO current_user` drops the connection), so
`relopass_api` cannot be entered via `SET ROLE` over the pooler, and the direct
(non-pooler) endpoint is not DNS-resolvable for this project.

The barrier is a property of the RLS machinery on **any** non-`BYPASSRLS` role +
the GUC policy, so the live proof exercises it via the built-in `authenticated`
role using the **identical** USING expression. The `relopass_api` policy is the
same expression bound to the production role (its predicate is separately proven,
and the migration DDL validated). On a true direct/CI Postgres (superuser), the
same test can target `relopass_api` directly.

## Activation runbook (human — required to make the barrier load-bearing)

Until these steps are done, the policy + GUC are in place but inert (the backend
still connects as the bypass-RLS superuser). Nothing breaks in the meantime.

1. **Set the role password** (out-of-band — secrets never live in a migration):
   ```sql
   ALTER ROLE relopass_api WITH LOGIN PASSWORD '<generated-strong-password>';
   ```
2. **Confirm grants** match the request path's needs (this PR grants on
   `policy_assistant_chunks` only — extend when the role is adopted more widely).
3. **Set `RELOPASS_API_DATABASE_URL`** in Render (backend service) to the
   `relopass_api` connection string, pooler-qualified username:
   `postgresql://relopass_api.<project_ref>:<password>@<pooler-host>:6543/postgres`
4. **Verify enforcement** against a session-mode (direct, port 5432) connection:
   ```bash
   RELOPASS_RLS_TEST_DB_URL='postgresql://postgres:<pw>@<direct-host>:5432/postgres' \
     python -m pytest backend/tests/test_rls_second_barrier.py -v
   ```
5. Confirm in prod that `SELECT current_user` during a request returns
   `relopass_api` (not `postgres`).

## Rollback

Unset `RELOPASS_API_DATABASE_URL` (request path reverts to the superuser engine).
The role/policy can remain — they are inert without the dedicated connection.
