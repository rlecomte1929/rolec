# Database layer — payment/access state

## Why a sidecar table instead of `ALTER TABLE relocation_cases`

The original Node/Postgres spec added `access_tier`, `payment_status`, and
Stripe columns directly to `relocation_cases`. On Audos, WorkspaceDB tables
are created via the `workspace_db_create_table` tool and there is **no
column-add tool** — DDL through server functions or raw SQL is read-only and
silently fails. Payment state therefore lives in a dedicated sidecar table,
**`case_access`**, with an optional FK back to `relocation_cases.id`
(`ON DELETE SET NULL`).

One `case_access` row exists per corridor-check case. Case identity is the
deterministic **`case_key`** (unique):

```
frno|<sessionId>|<employeeType>|<moveDate>
```

so the same HR user re-running the same check reuses the same row (and its
paid unlock) across reloads and sessions on the same browser.

## Tables

- **`case_access`** (SQL name `app_case_access`) — live schema exported in
  [`case_access.table.json`](./case_access.table.json). State machine:
  - `access_tier`: `'free' | 'roadmap' | 'essentials'` (default `'free'`)
  - `payment_status`: `'unpaid' | 'pending' | 'paid' | 'refunded'` (default `'unpaid'`)
  - Stripe linkage: `stripe_session_id`, `stripe_payment_intent_id`,
    `amount_cents`, `currency` (default `'eur'`), `paid_at`
  - Receipt fields collected pre-checkout: `billing_company`, `billing_vat`,
    `customer_email`
- **`case_addons`** (SQL name `app_case_addons`) — v1 scaffold, exported in
  [`case_addons.table.json`](./case_addons.table.json). Empty, no logic
  wired. `addon_type`: `'movers' | 'immigration_lawyers' | 'tax_advisors' |
  'schools' | 'pets'`. FKs to both `relocation_cases.id` and
  `case_access.id`.

## Write discipline

`case_access` and `case_addons` are written **only** by the three server
functions (`case-checkout`, `case-access`, `stripe-case-webhook`). App/browser
code must treat them as read-only — the unlock decision is always the
server's, derived from Stripe's own status API, never from client input.

## How the tables were created

Via the Audos MCP `workspace_db_create_table` tool (the only supported DDL
path), on 2026-07-18 by `audos-code`. The JSON exports in this folder are the
live `workspace_db_describe_table` output at package-creation time and can be
used to re-create the tables if ever needed.
