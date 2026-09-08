# Feedback diagnostics context — design

**Date:** 2026-07-06
**Status:** Approved (design), pending implementation plan

## Context / problem

Bug reports filed through the in-app "Share feedback" widget currently carry only:
`category`, `message`, `page_url`, `report_id`, `screenshot_data`, `browser` (userAgent), and the
reporter's identity (`reporter_email/name/role`). Whoever triages a report in the admin
**Feedback & Work** tab has to guess *which function/endpoint actually failed* and then hunt through
backend logs by hand — as just happened with the "upload failed" (missing `company-logos` bucket) and
"Failed to send" (`feedback_user_id_fkey`) bugs.

**Goal:** auto-attach enough diagnostic context to each report that a triager can see, at a glance, the
page, the function that failed, the failed API call(s), and a correlation id that jumps straight to the
backend request log — without asking the reporter to provide any of it.

Chosen scope: **Rich** (page route + failing function + recent failed API calls + browser **plus**
navigation breadcrumb trail, viewport, app build SHA, and a correlation id). The widget UI is
**unchanged** — this is pure auto-capture.

## What already exists (reuse, don't rebuild)

- `frontend/src/lib/errorTracking.ts`: module-level **breadcrumb** ring buffer (last 10 nav/error
  events); `computeFingerprint(message, stack)` deriving the **first user-code stack frame** (= "the
  function that failed"); **PII scrubbing** `scrubPii()` / `redactUrl()` (emails, tokens/JWTs, UUIDs,
  query strings). Today it feeds the `capture-error` Edge Function only.
- Correlation id: backend sets `X-Request-ID` on every response and exposes it via CORS
  (`backend/main.py:566, 659, 697`); the client already generates/sends `X-Request-ID` on each request
  (`frontend/src/api/client.ts:167-176`, `getCurrentInteractionId()`, `apiGet/apiPost` at ~4152).
- Backend request logging already prints `request_id=<uuid>` per request (greppable in Render logs).
- `feedback.py` already stores structured columns and best-effort seeds `feedback_status`; the admin
  `components/admin/FeedbackTab.tsx` already renders expandable rows.

Only genuinely new plumbing: a build SHA exposed to the frontend, and two small ring buffers (recent
errors, recent failed requests).

## Architecture

A `client_context` JSON object is **collected at submit time** from module-level ring buffers,
PII-scrubbed **in the browser**, attached to the feedback POST, stored in one new `jsonb` column, and
rendered as a **Diagnostics** panel in the admin feedback row.

```
FeedbackWidget.submit()
  → collectDiagnostics()            // scrubbed snapshot (diagnostics.ts)
  → POST /api/feedback { ...body, client_context }
  → feedback.client_context (jsonb, size-capped server-side)
  → GET /api/admin/feedback         // returns client_context
  → FeedbackTab Diagnostics panel
```

## Components

### 1. `frontend/src/lib/diagnostics.ts` (new)
`collectDiagnostics(): ClientContext` returns a scrubbed snapshot:
```ts
interface ClientContext {
  route: string;              // location.pathname (redactUrl)
  appVersion: string;         // __APP_VERSION__ (build SHA)
  viewport: string;           // `${innerWidth}x${innerHeight}`
  userAgent: string;          // navigator.userAgent (already captured as `browser` too)
  interactionId: string | null;      // getCurrentInteractionId() — correlation id
  breadcrumbs: Breadcrumb[];          // from errorTracking (already scrubbed)
  recentErrors: { message: string; failingFrame: string; fingerprint: string; ts: string }[]; // last 5
  recentFailedRequests: { method: string; path: string; status: number; requestId: string | null; ts: string }[]; // last 5
}
```
All free-text passes through `scrubPii`. Buffers are bounded (last 5) and the whole object is JSON
size-capped (drop `breadcrumbs`/oldest entries if > ~16 KB) so the payload stays small.

### 2. `frontend/src/lib/errorTracking.ts` (extend)
Add a bounded `recentErrors` ring buffer (last 5) populated wherever an error is already captured
(`window.onerror`, `unhandledrejection`, `reportError`), storing `{ message, failingFrame, fingerprint,
ts }` (scrubbed). Export a `getRecentErrors()` reader. No change to the existing Edge-Function path.

### 3. `frontend/src/api/client.ts` (extend)
Add a bounded `recentFailedRequests` ring buffer (last 5). Record an entry in the error paths of
`apiGet/apiPost/apiPatch` (non-2xx via `buildApiError`, and fetch throws) and the axios response-error
interceptor: `{ method, path: redactUrl(path), status, requestId: response.headers.get('X-Request-ID')
?? sentXRequestId, ts }`. Export `getRecentFailedRequests()`.

### 4. Widget + API wrapper
- `frontend/src/components/FeedbackWidget.tsx`: add `client_context: collectDiagnostics()` to the
  `submitProductFeedback(...)` payload. No UI change.
- `frontend/src/api/productFeedback.ts`: add `client_context?: ClientContext` to `ProductFeedbackInput`.

### 5. Backend `backend/app/routers/feedback.py`
- `FeedbackBody.client_context: Optional[Dict[str, Any]] = None`.
- Serialize with `json.dumps`; if the serialized string exceeds a cap (~32 KB) drop it (like the
  oversized-screenshot rule) rather than fail the insert.
- Add `client_context` to the INSERT (bind `CAST(:ctx AS jsonb)` on Postgres; the SQLite test schema
  uses a TEXT column so the same param binds as text). Follow the existing dialect-aware pattern; the
  column is nullable so omitting it is safe.

### 6. Migration
`supabase/migrations/<ts>_feedback_client_context.sql`:
```sql
alter table public.feedback add column if not exists client_context jsonb;
```
ALTER on an existing table (no new table → the new-table RLS hard-gate does not apply). Idempotent.

### 7. Admin display `frontend/src/components/admin/FeedbackTab.tsx`
In the expandable row, add a **Diagnostics** section (only when `client_context` is present):
- **Page:** `route` · **App:** `appVersion` · **Browser/viewport**
- **Failed request(s):** `METHOD /path → 500` with the **request-id** (monospace, copyable) — the pivot
  to Render logs / the admin **Errors** tab.
- **Last error:** `message` + **failing function** (`failingFrame`) + `fingerprint`.
- **Recent activity:** breadcrumb trail (compact list).
`GET /api/admin/feedback` (`backend/app/routers/admin_feedback.py`) must select/return the new column in
the `product` stream (other streams return `null`).

### 8. Build SHA
`frontend/vite.config.ts`: `define: { __APP_VERSION__: JSON.stringify(process.env.RENDER_GIT_COMMIT?.slice(0,7) || <git rev-parse --short HEAD fallback> || 'dev') }`. Declare `__APP_VERSION__` in a global d.ts (or read via `config/env.ts`). Render sets `RENDER_GIT_COMMIT` at build.

## Privacy (GDPR)

Every string in `client_context` is scrubbed **client-side** via the existing `scrubPii`/`redactUrl`
before it leaves the browser (emails → `[email]`, tokens/JWTs → `[token]`, UUIDs → `[id]`, query
strings dropped). The backend additionally size-caps. This matches the posture already applied to the
`capture-error` pipeline, so no new sub-processor exposure. `client_context` holds diagnostics only —
never raw form fields or document contents.

## Testing

- **Backend** (`backend/tests/routers/test_feedback.py`, SQLite harness): a submit with a `client_context`
  dict persists it (TEXT column in the SQLite schema); a submit without it still succeeds (nullable);
  an oversized `client_context` is dropped but the row is still written (mirrors the screenshot test).
- **Frontend** (vitest): `collectDiagnostics()` returns scrubbed values (feed it an email/UUID → `[email]`/`[id]`);
  ring buffers cap at 5 and keep most-recent; `getRecentFailedRequests()` records a failed `apiPost`.
- **Type-check/build:** `tsc --noEmit` + `npm run build` (the `define`/global type must compile).
- **Live:** trigger a failing action (e.g., a 500), open the widget, submit; confirm the admin row's
  Diagnostics panel shows the route, the failed request + request-id, and the failing function; grep
  Render logs by that request-id to confirm the correlation.

## Out of scope (explicit)

- No widget UI changes (no "steps to reproduce" / severity fields).
- No new backend LLM processing of the context.
- No linking migration between `feedback` and the errors table — correlation is via the request-id/
  interaction-id string the triager can pivot on manually.
