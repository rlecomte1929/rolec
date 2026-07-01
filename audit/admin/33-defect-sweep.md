# Real-defect sweep — origin/main @ 0f14c760 (2026-06-30)

Read-only sweep for CONFIRMED broken-on-main bugs (not style/features). Route list dumped from the real prod app (`backend.main:app`, 678 routes). Both repo guards (`check_route_auth.py`, `check_router_registrations.py`) currently pass.

## Findings

### P1 — Provider Portal data endpoints 404 in prod (live page, broken) — *fix held in #1216*
`backend/app/routers/provider_portal.py` (`GET /api/provider/tasks`, `PATCH .../tasks/{id}`, `GET .../case-summary`, `PATCH .../profile`) is registered in **neither** `backend/main.py` nor `backend/app/main.py` on current main → every call 404s. `frontend/src/pages/ProviderPortal.tsx` (live at `/provider/portal`) calls them on mount. Provider auth works (`providers.py`), so a provider signs in then hits 404s.
- **Status:** the dual-registration fix is in **held PR #1216** (not yet on main). No new fix needed — it lands July 1.

### P2 — Support triage `_TRIAGE_SYSTEM.format()` KeyError — *fix held in #1228*
`backend/app/routers/support.py:463` `.format()` on a template with unescaped literal JSON braces → `KeyError` (confirmed by execution). Currently masked (support router grandfathered-unregistered → 405; and a `try/except` → 502), so latent, but total breakage of AI triage the moment support is wired.
- **Status:** the brace-escape fix is in **held PR #1228**. No new fix needed.

### P3 — `ab_tests` router modular-only → 405 in prod (known/grandfathered)
`backend/app/routers/ab_tests.py` registered only in `app/main.py`; admin-internal; documented in `router_registration_allowlist.txt`. Low priority.

## NEW actionable finding (not covered by any held PR)

### Guard blind spot — `scripts/check_router_registrations.py` can't see a router registered in NEITHER entrypoint
The guard only diffs `app/main.py` vs `backend/main.py` for *modular-only* routers. A router registered in **neither** file (exactly the provider_portal case) is invisible — which is why CI passed despite the live 404. **Recommended fix:** widen the guard to flag any `routers/*.py` defining an `APIRouter` with routes that is registered in neither entrypoint and not explicitly allowlisted. This is a "fix the guard that should have caught the bug" improvement: low-risk, prevents a whole class of silent 404s, and would have caught provider_portal before it shipped.

## Negative results (checked, nothing found)
- `.format()` brace bugs: ONLY support triage. `dossier_notifications`, `hr_mobility_briefing_service`, `prescreening_notification`, `nlg/frame_based` templates all clean; the two data-driven `.format` callers are guarded/seed-driven.
- Unguarded routes: `check_route_auth.py` passes.
- Frontend→backend 404s: swept 524 FE `/api/...` strings vs 678 prod routes — only live mismatch is the Provider Portal cluster (others latent/unwired: `AIPanel.tsx`→`/api/ai/chat`, `policyBuilderPipeline.ts`→`/api/hr/policy-builder/*`, both with no live importer; `hr_policies.py` modular routes superseded by legacy `@app` routes).

## Not exhaustively swept
- KeyError/IndexError on request data (class 4): spot-checked only.
- Unawaited coroutines / async bugs (class 6): no high-confidence finding, but not deeply swept — treat as "no finding," not "clean."

## Bottom line
The two real prod bugs already have held fixes (#1216, #1228). The one new actionable item is the **router-registration guard blind spot** — a small, high-leverage hardening that closes the gap which let provider_portal's 404 reach prod.
