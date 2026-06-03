# Execution Prompt — SEC-004 · Rate Limiting Coverage

**Notion:** AIQ-476 — `https://www.notion.so/36d887c64d4881e9bc7fc4e13c9e20ce`
**Priority:** P1 · **Complexity:** Low → **Medium** (more nuanced than a fresh install).
**Branch:** `feature/sec-004-rate-limit-coverage`

## Role
Backend security engineer. You close the abuse surface on unlimited API endpoints. **slowapi is already wired**; your job is to bring coverage from ~6 endpoints to the full surface and harden the 429 response.

## ⚠️ Audit drift — slowapi already installed
The Notion task implies installing slowapi. **It's already there.** Don't re-install.
- `backend/requirements.txt` pins `slowapi==0.1.9`.
- `backend/rate_limit.py` exports the shared `limiter` (with `_real_remote_address` honoring `X-Forwarded-For` for Render's proxy).
- `backend/main.py` registers `app.state.limiter` + `RateLimitExceeded` handler.
- 6 endpoints already use `@limiter.limit(...)` (e.g. `backend/app/routers/auth.py:180,371` and `backend/main.py:4738,4853`).
- Tests bypass via `RELOPASS_DISABLE_RATE_LIMITS=1` (set in conftest).

CLAUDE.md `## Commands` references the bypass — don't break that contract.

## What ships
1. **Coverage expansion** — apply `@limiter.limit(...)` to every route in scope per the table below. Use a single source of truth: a small module `backend/app/rate_limits.py` defining named constants:
   ```python
   AUTH_LIMIT     = "5/minute"
   STANDARD_LIMIT = "100/minute"
   UPLOAD_LIMIT   = "10/minute"
   ADMIN_LIMIT    = "20/minute"
   AI_LIMIT       = "20/minute"
   ```
   Then import + apply per endpoint. Don't sprinkle bare strings.

2. **429 response shape** — confirm the existing `RateLimitExceeded` handler returns JSON + `Retry-After` header. If not, replace the default handler with:
   ```python
   @app.exception_handler(RateLimitExceeded)
   async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
       retry = int(exc.detail.split()[0]) if False else 60  # parse from exc; fallback 60s
       return JSONResponse(
           status_code=429,
           content={"error": "rate_limit_exceeded",
                    "message": f"Too many requests. Retry after {retry}s.",
                    "retry_after": retry},
           headers={"Retry-After": str(retry)},
       )
   ```
   Verify by inspecting slowapi's `RateLimitExceeded.detail` field on the installed version.

3. **Structured log on limit hit** — add a `logger.warning("rate_limit_hit", extra={"ip": ip, "path": path, "limit": limit})` inside the handler. Standard `logging` module per CLAUDE.md backend conventions.

4. **AI cost-control endpoints** — keying on authenticated user (not IP). For routes that hit OpenAI / Mistral, use `@limiter.limit(AI_LIMIT, key_func=user_key_func)` where `user_key_func(request)` returns the JWT sub (fall back to IP if unauth).

## Endpoint inventory (target after this PR)

| Group | Limit | Routes (verify with grep) |
|---|---|---|
| Auth | `5/minute` | `/api/auth/login`, `/api/auth/register`, `/api/auth/password-reset`, `/api/auth/refresh` |
| Standard API | `100/minute` | All `/api/cases/*`, `/api/employees/*`, `/api/hr/*` GETs/POSTs not in another bucket |
| File uploads | `10/minute` | `/api/hr/policies/upload` (main.py:10556), `/api/hr/policy-documents/upload` (10778), `/api/admin/policies/upload` (11816), any `/api/tasks/*/upload` |
| Admin endpoints | `20/minute` | `/api/admin/*` GETs/POSTs (excluding uploads, which use UPLOAD_LIMIT) |
| AI inference | `20/minute` (per user) | Any route calling OpenAI/Mistral/Anthropic — grep `openai_client\|llm_policy_extractor\|policy_assistant_answer_engine` for call sites |

Build this table for real before applying — the inventory above is the audit baseline; verify each row with `grep -n "@app.get\|@app.post" backend/main.py backend/app/routers/*.py`.

## Tests
`backend/tests/test_rate_limit_coverage.py`:
1. With `RELOPASS_DISABLE_RATE_LIMITS` **unset**, hit `/api/auth/login` 6 times → request 6 returns 429 with `Retry-After` header and the documented JSON shape.
2. Same for a standard API endpoint at the 101st request.
3. Hit upload endpoint 11 times → 11th returns 429.
4. AI endpoint: simulate same user (same JWT) 21 times → 21st returns 429; second user not affected.
5. Existing test suite still green with the bypass env var set (CLAUDE.md contract).

## Constraints
- Do not change `backend/rate_limit.py`'s key function — the `X-Forwarded-For` parsing is correct for Render.
- Test bypass env var (`RELOPASS_DISABLE_RATE_LIMITS=1`) must continue to disable limits — don't add a new bypass mechanism.
- Supabase internal service-role calls (server-to-server) must not be rate-limited — if any backend route is invoked from a Supabase Edge Function, document and exempt it.

## Test commands
```
cd backend && pytest backend/tests/test_rate_limit_coverage.py -v
cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest -q   # full suite still green
```

## Definition of done
- `backend/app/rate_limits.py` exists with the 5 named constants.
- Every route in the inventory has a `@limiter.limit(...)` decorator referencing a constant.
- 429 response includes `Retry-After` header + documented JSON body.
- Rate-limit hits log as `rate_limit_hit` with IP + path + limit.
- Tests prove 429 fires on each of the 5 endpoint groups.
- Notion AIQ-476 → Human Review with inventory table + sample 429 response in Execution Notes.
- Commit per CLAUDE.md Build Hygiene rules.
