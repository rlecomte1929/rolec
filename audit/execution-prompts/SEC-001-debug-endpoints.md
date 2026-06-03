# Execution Prompt — SEC-001 · Gate `/debug/*` Endpoints

**Notion:** AIQ-466 — `https://www.notion.so/36d887c64d4881f0bce2ead875d93262`
**Priority:** **P0** · **Complexity:** Low · **Estimated effort:** ~45 min (was 30 min — more endpoints than the audit found).
**Branch:** `feature/sec-001-debug-gate`

## Role
Backend security engineer. You close live unauthenticated attack surface on `api.relopass.com`. Done right, this disappears from production with zero side effects.

## ⚠️ Audit drift — scope expanded
The Notion task cites `backend/main.py:731-753`, but a fresh grep on 2026-05-30 found those routes have shifted **and additional debug endpoints exist that were not in the audit**. **You must gate all 8**, not just the original 3.

Authoritative list (grep `grep -n "/debug" backend/main.py`):

| Line | Route |
|---|---|
| 755 | `GET /debug/db` |
| 766 | `POST /debug/kv` |
| 776 | `GET /debug/kv/{key}` |
| 2664 | `GET /api/admin/debug/runtime-database` |
| 2690 | `GET /api/admin/debug/test-company-graph` |
| 5716 | `GET /api/debug/supabase` |
| 10353 | `GET /api/debug/cases/{case_id}/events` |
| 10363 | `GET /api/debug/assignment-check` |

Re-grep before editing — line numbers will drift as you work.

## What ships
Wrap every `/debug` route definition in an env-var guard. **Use a helper, not 8 copies of the same `if` block.**

```python
# Near the top of backend/main.py
DEBUG_ENDPOINTS_ENABLED = os.environ.get("ENABLE_DEBUG_ENDPOINTS") == "1"

def debug_route(method: str, path: str, **kwargs):
    """Register a debug route only when ENABLE_DEBUG_ENDPOINTS=1; else no-op."""
    def decorator(fn):
        if DEBUG_ENDPOINTS_ENABLED:
            getattr(app, method)(path, **kwargs)(fn)
        return fn
    return decorator
```

Then replace each `@app.get("/debug/...")` / `@app.post("/debug/...")` with `@debug_route("get", "/debug/...")`. The function body is unchanged; routes simply don't register when the env var is unset.

**Do NOT** set `ENABLE_DEBUG_ENDPOINTS=1` in any production env. Document the flag in `README.md` (or `.env.example` if it exists) as **local development only**.

## Tests
Add `backend/tests/test_debug_endpoints_gated.py`:
1. Default (no env var) → all 8 routes return 404.
2. With `ENABLE_DEBUG_ENDPOINTS=1` set before app construction → all 8 return 200/expected behavior.

Test the route table directly via `app.router.routes` filtering — don't depend on the actual SQL the endpoints would run.

## Validation (production probe — after deploy)
```bash
for path in \
  /debug/db /debug/kv/x \
  /api/admin/debug/runtime-database \
  /api/admin/debug/test-company-graph \
  /api/debug/supabase \
  /api/debug/cases/00000000-0000-0000-0000-000000000000/events \
  /api/debug/assignment-check
do
  curl -s -o /dev/null -w "%{http_code} $path\n" "https://api.relopass.com$path"
done
# Expected: 404 for all 7 GETs; 405 for /debug/kv (because it's POST-only)
```

## Constraints
- One file touched: `backend/main.py` (+ tests + README). No new routes, no behavior change beyond gating.
- Helper must be defined **before** any `@debug_route(...)` decorator references it.
- Keep existing test suite green — `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest -q`.

## Definition of done
- All 8 debug routes gated behind `ENABLE_DEBUG_ENDPOINTS=1`.
- New test file passes both modes.
- 7 production curls return 404 / POST returns 405.
- `README.md` (or `.env.example`) documents the flag with the warning **"local development only — never set in production."**
- Notion AIQ-466 → Human Review with the production probe output in Execution Notes.
- Commit per CLAUDE.md Build Hygiene rules.
