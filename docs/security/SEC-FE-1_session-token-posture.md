# Session-token posture — Option A (accepted risk)

**Status:** accepted, pre-launch · **Task:** SEC-FE-1 (AIQ-1168) · **Source:** AP-02 security-audit

## The finding
The ReloPass Bearer token **and** the Supabase JWT are stored in `localStorage`,
which is JavaScript-readable. An XSS foothold could exfiltrate either. This is the
one genuine "security violation" the audit flagged.

Separately, the ReloPass session token had **no expiry at all**: `public.sessions`
stored only `(token, user_id, created_at)` and the validation path checked only the
token — a stolen token was usable **forever**.

## Decision: Option A (keep in localStorage, harden in place)
Moving the token to an `HttpOnly` cookie (Option B) is deliberately **deferred**.
Rationale, pre-launch:
- The Supabase JWT would remain in `localStorage` regardless (the Supabase JS
  client manages its own session there), so a cookie only half-solves it.
- A cross-origin `HttpOnly` cookie (frontend ↔ api.relopass.com) needs
  `SameSite=None; Secure` **plus** CSRF protection — a non-trivial change best
  scoped together with the Supabase session migration.
- No real customer PII exists yet (platform is pre-launch with test data).

## Mitigations in place (reduce blast radius under Option A)
1. **Strict CSP, committed & live** (SEC-FE-2): `script-src 'self'` (no
   `unsafe-inline`) in `render.yaml`, verified live via `curl -I https://relopass.com`.
   Shrinks the XSS surface that could read the token.
2. **Dependency hygiene**: DEP-1/DEP-2 patched bundle-facing vulns; gitleaks
   secret-scanning (SEC-FE-7) gates new leaks.
3. **Bounded session TTL** (this task): sessions now expire `created_at + 14 days`
   (`SESSION_TTL_DAYS` in `backend/db/auth.py`), checked on every token
   validation. A stolen token is now usable for **≤14 days**, not forever. An
   expired token returns 401 and the existing `client.ts` interceptor routes the
   user to login.

## Revisit trigger
**Before the first real customer PII** lands, implement Option B (HttpOnly cookie
for the ReloPass token, `SameSite=None; Secure` + CSRF), scoped together with the
Supabase session. Re-open the cookie-migration decision then.

## Known follow-up
- TTL is **absolute** (from `created_at`), so an active user re-logs-in every 14
  days. A seamless **sliding/refresh-token** mechanism (extend on activity, or a
  `/auth/refresh` endpoint) is a follow-up — deliberately not added here to avoid
  a per-request write on the hot auth path and to keep this change small.
