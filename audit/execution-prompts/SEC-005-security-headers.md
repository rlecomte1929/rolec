# Execution Prompt — SEC-005 · Security Headers (CSP, HSTS, X-Frame-Options)

**Notion:** AIQ-477 — `https://www.notion.so/36d887c64d488116bacfde3ec7018e1d`
**Priority:** P1 · **Complexity:** Low · **Estimated effort:** ~1 hr backend + ~1 hr CSP audit + ~30 min frontend config.
**Branch:** `feature/sec-005-security-headers`

## Role
Backend + infra engineer. You close the easy-but-visible web-security gap that every buyer security review surfaces in the first 30 seconds.

## ⚠️ Hosting drift — frontend is on Render, not Vercel
The Notion task references `vercel.json`. **There is no Vercel deployment.** Per `CLAUDE.md` §Deployment, the frontend is a **Render Static Site** at `relopass.com`. Pick one of these two paths for the frontend headers, in order of preference:

1. **`frontend/public/_headers`** (Netlify-style header file; Render Static Sites honor it). Single file in repo, ships in `frontend/dist/`. **Use this.**
2. `render.yaml` `headers:` block — repo-rooted; requires Render to read it on deploy. More moving parts than `_headers`. Fallback only.

## What ships

### Backend — FastAPI middleware in `backend/main.py`
Add a security-headers middleware **before** the CORS middleware registration (per the comment block at backend/main.py:482-487 — middleware registered last runs first). Six headers:

```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # CSP on API responses kept minimal — API serves JSON, not pages.
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response
```

### Frontend — `frontend/public/_headers`
```
/*
  Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://*.supabase.co wss://*.supabase.co https://api.relopass.com; font-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'
```

### CSP audit — MANDATORY before shipping the frontend policy
A strict CSP that breaks the SPA is worse than no CSP. Before merging:
1. Build: `cd frontend && npm run build`.
2. Grep the dist bundle for inline scripts/styles: `grep -rn "javascript:\|onerror=\|onclick=" frontend/dist/index.html` — should return nothing.
3. Open the deployed site with DevTools Console; navigate every route tier (Employee, HR, Admin) and watch for CSP violations.
4. If the build relies on inline styles (Tailwind JIT doesn't, but check), keep `'unsafe-inline'` for `style-src` — but **never** for `script-src`.
5. If Supabase realtime uses additional WebSocket origins, add them to `connect-src`.

If any tier breaks, **fix the source** (move inline scripts out, swap `style=` to classNames) rather than relax the policy.

## Validation
- `curl -I https://api.relopass.com/health` returns all 6 headers.
- `curl -I https://relopass.com` returns all 6 headers.
- `securityheaders.com` scan on both domains → **A or A+**.
- Full SPA route tour with DevTools open → zero CSP violations.
- No `'unsafe-inline'` or `'unsafe-eval'` in `script-src` (style-src may keep `'unsafe-inline'` if documented).
- Existing CORS behavior unchanged (`OPTIONS` preflights still return `Access-Control-Allow-*`).

## Constraints
- Order matters: HTTP middleware registered **before** CORS middleware so it runs **after** CORS. Match the existing pattern at `backend/main.py:482-487`.
- Render Static Sites do not strip `_headers` files — verify the deployed asset list includes `_headers` (`curl -I https://relopass.com/_headers` should return 200 or 404 of a path not exposed by the static server; the headers themselves apply via the proxy).
- Do not introduce `'unsafe-inline'` for `script-src` to make the SPA "just work" — fix the inline script instead.

## Test commands
```
cd frontend && npm run build && grep -E "javascript:|onerror=|onclick=" frontend/dist/**/*.html || echo "no inline JS"
cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest -q
curl -sI https://api.relopass.com/health | grep -iE "strict|frame|content-type-options|referrer|permissions|csp"
```

## Definition of done
- Backend middleware adds 6 headers to every API response.
- `frontend/public/_headers` ships in the static build.
- `securityheaders.com` shows A or A+ on both domains.
- DevTools Console shows zero CSP violations across all three persona route trees.
- CSP directives commented inline in `_headers` with rationale per directive.
- Notion AIQ-477 → Human Review with `securityheaders.com` screenshot or text result in Execution Notes.
- Commit per CLAUDE.md Build Hygiene rules.
