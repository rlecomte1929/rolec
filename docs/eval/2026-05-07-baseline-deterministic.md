# Eval verdict — 2026-05-07 — deterministic policy assistant

## Summary

The 12-question eval did not run. A single probe to
`POST /api/hr/policy-assistant/query` against `demo-hr-policy-001`
returned **HTTP 500 in 1.456s** before any refusal-quality
measurement was possible. Diagnosis (code-read, no further API
calls) confirms this is deterministic for the `policy_id` shape,
not a transient issue.

**This is the eval's verdict: HARD_FAIL by definition, generalised
across all questions that would have been asked.**

## What was tested

- **Endpoint:** `POST /api/hr/policy-assistant/query`
- **Auth:** HReval session token via `/api/auth/login` (PBKDF2 path,
  `public.users`)
- **Target policy:** `demo-hr-policy-001` (the only policy returned
  by `/api/hr/policies` for this account)
- **Probe question:** "What is the temporary housing allowance cap
  under the published policy?"
- **Result:** HTTP 500, body `"Internal server error"`, request_id
  `b583f63c-bfd4-497a-8e3c-ba45368b753e`

## Root cause

1. Code expects `policy_id: str` (no UUID cast in Python),
   parameterized as `:id` against `WHERE id = :id` at
   [`backend/database.py:11066`](backend/database.py#L11066) — but
   Postgres receives that param as text and the column is `uuid`,
   so the driver/server enforces UUID syntax at execution.
2. Schema stores `id uuid primary key default gen_random_uuid()`
   ([`supabase/migrations/20260301021000_company_policies_and_benefits.sql:4`](supabase/migrations/20260301021000_company_policies_and_benefits.sql#L4));
   every FK in subsequent migrations confirms `uuid`.
3. Yes — `'demo-hr-policy-001'` (19 chars, contains `-` but isn't
   UUID-shaped) **deterministically** raises `DataError: invalid
   input syntax for type uuid` and yields HTTP 500 with FastAPI's
   default body (matches the `"Internal server error"` observed,
   not the route's custom `"Policy assistant failed"`).
4. **Crash site:** [`backend/database.py:11068`](backend/database.py#L11068) —
   the `.fetchone()` of `SELECT * FROM company_policies WHERE id = :id`
   inside `Database.get_company_policy`, called from
   [`backend/main.py:7575`](backend/main.py#L7575) **before** the
   try/except at
   [`backend/main.py:7589-7602`](backend/main.py#L7589); that's
   why the catch-all message did not fire.
5. **No path.** Listing at `/api/hr/policies` returns the demo slug
   (likely from a JSON seed / demo registry, not from
   `company_policies`), but every deterministic-engine consumer
   (`get_company_policy`, `_require_policy_access`, audit writes)
   keys off the same uuid column — the 500 is universal for this
   `policy_id`.

## Why this matters more than a 12-question verdict

The `/api/hr/policies` endpoint advertises `demo-hr-policy-001` as
a valid policy to the HR UI. Every consumer endpoint of the
`policy_id` in the policy assistant flow will deterministically
500 against it. This is a contract violation between the listing
endpoint and the rest of the platform: the system advertises
something it cannot operate on. Any HR user who currently sees
this policy in their UI and asks the assistant a question about
it gets a 500.

The unknown — and now the most important open question for
ReloPass production readiness — is how many such mismatches exist
in the production index, and whether any real customer (not
synthetic, not demo) is currently exposed to them.

## Other findings surfaced today (not retested)

- `/api/hr/policy-documents` hangs >20s with zero bytes returned.
  Independent of `policy_id` shape. Likely Supabase RLS resolution
  failure due to dual-auth path mismatch — this account
  authenticates via `public.users` (PBKDF2) but RLS-protected
  reads expect `auth.users` session.
- Auth tokens are opaque session UUIDs, not JWTs. All identity
  context is server-resolved. Implications for audit and
  cross-context binding need mapping.
- The company-context shown in the React UI (`eval_synth_2026_05`)
  diverges from what the same token resolves to at the API layer
  (`NOR-INV-001` / demo policy). The UI's company switcher uses a
  mechanism we have not yet identified.
- `profiles.company_id` is NULL for at least 3 production user
  rows (Yves, Christopher, Mark Thompson). Several rows duplicate
  emails.

## Eval gating recommendation

No further engine evaluation should be attempted until:

1. The `policy_id` schema discrepancy is resolved, OR a UUID-shaped
   policy with content is confirmed queryable end-to-end via this
   token.
2. `/api/hr/policy-documents` responds within SLA, or its hang is
   diagnosed and the cause is understood.
3. The dual-context identity mismatch (UI vs token) is mapped —
   at minimum, we need to know which `company_id` any given API
   call actually scopes to, given a session token.

## Recommended priorities for the next dev session

**P0** — Audit the production `company_policies` table. List every
`policy_id`, group by id-shape (UUID vs string), identify which
the listing endpoint exposes vs which the consumer endpoints can
actually serve.

**P0** — Add a regression test that calls
`/api/hr/policy-assistant/query` against every policy returned by
`/api/hr/policies` for a given user and asserts no 500s. Today's
probe would have failed this test.

**P1** — Fix the listing endpoint to filter out non-queryable
policies, OR fix the consumer endpoints to handle string
`policy_id`s gracefully (validate-and-refuse rather than crash).

**P1** — Diagnose `/api/hr/policy-documents` 20s hang.

**P2** — Map the company-context resolution path between UI and
API.

**P2** — Audit the `auth.users` / `public.users` dual-auth
boundary.

## Methodology note

This session followed evaluation-driven-development discipline:
single probe before full eval; honest record of failure as data;
diagnosis via code-read rather than further production probes.
The result is a finding worth more than a clean verdict table on
a synthetic test would have been.

## Out of scope

Did **not** measure: refusal-quality, citation faithfulness,
retrieval recall, latency under load, behaviour against real
customer data, behaviour of the LLM-orchestrated
`/api/policy-assistant/rag-query` path. All deferred to a future
session, after engine reachability is restored.
