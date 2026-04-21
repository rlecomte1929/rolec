# Dual auth consolidation plan

ReloPass currently runs two authentication systems side by side:

1. **Legacy**: `public.users` table + PBKDF2 hashes (`passlib`) + opaque UUID session tokens stored in a `sessions` table. Issued by `POST /api/auth/login`.
2. **Supabase Auth**: a mirrored user in `auth.users`, created by `backend/services/supabase_auth_sync.sync_relopass_user_to_supabase_auth`. Used by the frontend Supabase JS client for RLS-enforced DB access and realtime subscriptions.

Both are live at the same time. The legacy token gates every FastAPI endpoint; the Supabase JWT gates the RLS-backed Postgres access the frontend does directly. Logout historically only killed the legacy side — the Supabase JWT stayed valid for its TTL (up to 1 hour).

This document is the roadmap to merge them.

## What's already been fixed (as of the work tracked in this repo)

- **Logout revokes both tokens** — `POST /api/auth/logout` now accepts an optional `supabase_access_token` in the request body and calls `revoke_supabase_session` (wrapping Supabase Admin API's `sign_out`). The frontend can forward both tokens on logout; the backend handles revocation server-side so a leaked JWT cannot be replayed.
- **Rate limits applied identically** to both login and register paths ([backend/app/routers/auth.py](../../backend/app/routers/auth.py)).
- **Supabase anon key rotation** — the original exposure in `frontend/.env.development` has been addressed (see commit `8084286`).

## Why we can't just rip out the legacy side today

1. **`supabase-py` doesn't yet support the new `sb_secret_...` / `sb_publishable_...` keys.** The backend relies on the legacy service-role JWT for admin operations (user creation, storage writes, admin client). Pulling the plug on legacy JWT signing breaks `backend/services/supabase_client.py`.
2. **Password verification lives on `public.users.password_hash`.** The legacy login path verifies PBKDF2 there. Moving password verification to Supabase means either re-hashing (impossible — we don't have plaintext), or forcing every user through a password reset. We need Supabase Auth's `migrate_password` flow or a bulk re-issue.
3. **Backend middleware / dependencies expect the legacy session shape.** `backend/app/auth_deps.get_current_user` looks up the user by the legacy token. Switching to Supabase JWT verification touches every protected route.

## The plan

### Phase 1 — Prepare (completed)
- [x] Logout revokes both tokens.
- [x] Rate limit login/register.
- [x] Supabase key rotation documented.
- [x] Anon key removed from git-tracked files.

### Phase 2 — Freeze legacy register path (next)

1. Add a feature flag `DISABLE_LEGACY_REGISTER=1` that flips `/api/auth/register` to a 410 Gone.
2. Frontend registration calls `supabase.auth.signUp()` directly and only hits the backend `/api/auth/login` path (with Supabase access token forwarded) to mint the legacy session token for backward compat with the rest of the API.
3. New users never get a `password_hash` in `public.users` after Phase 2 — their row is created empty and the legacy-login path for them fails with a clear "sign in via Supabase" error.

### Phase 3 — Migrate existing users (30-day window)

1. On successful legacy login, emit a password-reset email via `supabase.auth.admin.generate_link(type='recovery', email=…)`. Users reset their password through Supabase; their Supabase account acquires a password; legacy `password_hash` is retired after N logins via Supabase.
2. Instrument: Sentry counters for legacy-login vs Supabase-login. When the ratio crosses 95% Supabase, move to Phase 4.

### Phase 4 — Read-only legacy tokens

1. `/api/auth/login` no longer creates new `sessions` rows for users whose Supabase account is active.
2. Instead, the endpoint validates the Supabase access token supplied by the frontend (via JWK verification against Supabase's public keys) and returns a short-lived equivalent legacy-format token derived from the Supabase JWT.
3. `backend/app/auth_deps.get_current_user` accepts either a legacy token OR a Supabase JWT. Prefers Supabase JWT when both are present.

### Phase 5 — Remove legacy

1. Drop `public.users.password_hash` column (Alembic + Supabase migration).
2. Delete `POST /api/auth/register` and legacy session cleanup paths.
3. Switch `backend/app/auth_deps.get_current_user` to Supabase JWT verification only.
4. Remove `passlib` from `backend/requirements.txt`.

Estimated timeline: Phase 2 is one PR. Phase 3 is a 30-day live window (traffic-dependent). Phase 4 is one PR. Phase 5 is one cleanup PR plus the schema migration.

## Known risks and mitigations

- **`supabase-py` lagging the new key format.** Track [github.com/supabase/supabase-py](https://github.com/supabase/supabase-py) releases. If they ship `sb_secret_` key support before Phase 5, plan to migrate backend env vars simultaneously.
- **JWK verification overhead per request.** Mitigate with in-memory JWK cache keyed on `kid`, refreshed on miss. Supabase rotates keys rarely; 5-minute cache is safe.
- **Active user sessions at Phase 4 cutover.** Send a coordinated re-authentication prompt. Legacy tokens that haven't expired will continue to work during a 24-hour grace window after Phase 4 ships.

## Audit trail expectations

Every phase should emit identity events (see `backend/identity_observability.py`) so we can see the ratio shift:

- `identity.auth.signin.legacy_ok`
- `identity.auth.signin.supabase_ok`
- `identity.auth.legacy_password_reset_sent`
- `identity.auth.legacy_session_created_in_readonly_mode` (Phase 4)

These feed back into the Sentry dashboards once Phase 2 ships.
