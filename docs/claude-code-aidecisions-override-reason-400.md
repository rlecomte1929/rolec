# Claude Code — stop "Add to package" from 400-ing the AI-decision audit write

Paste from repo root. Base off current `main`. **Own branch off `main`: `fix/aidecision-override-reason`. Do NOT use `fix/td-qa-services-batch-0719`.** Read `CLAUDE.md`.

## What's proven (Cowork captured it live on prod `1ca6061f` — do not re-investigate the endpoint)

The recurring "Add to package fires an HTTP 400" is **NOT** the services-state save. That endpoint is robust — 8/8 rapid browser-origin writes returned 200 and the shortlist persists 6/6 (no data loss).

The failing request is the **fire-and-forget `createAIDecision`** fired on "Add to package" in `frontend/src/features/recommendations/RecommendationResults.tsx` (~line 536 → `POST /api/ai/decisions`).

Captured against prod, exact responses:
- `decision:'accept'` (no reason) → **201**
- `decision:'override'` (no reason) → **400** `{"detail":"Reason is required for decision 'override'."}`
- `decision:'reject'` (no reason) → **400** `{"detail":"Reason is required for decision 'reject'."}`
- `decision:'override'` **with** reason → **201**

The backend contract is intentional (`backend/app/routers/ai_decisions.py` ~line 140 requires a reason for `override`/`reject`). **Do not weaken that contract.**

### Why the "first-per-category clean, rest 400" signature happens
The **first** pick in a category is the top-ranked recommendation → recorded as `accept` (no reason needed) → 201. **Subsequent picks are non-top → recorded as `override`, but the quick "Add to package" path sends no `reason` → 400.**

### Two impacts
1. Console-noise 400s, masked by the optimistic UI (button flips to "In package" regardless).
2. **The one that actually matters:** because the call is fire-and-forget and the error is swallowed, **every override/reject AI-decision is silently dropped from the audit trail** (`ai_decisions`). That trail is a deliberate compliance control (AIQ-1694) — and overrides are exactly the decisions most worth logging.

---

## The fix (decide the semantics, then make the write always valid)

1. **Never send `override`/`reject` without a `reason`.** On the "Add to package" path, either:
   - **(preferred) reclassify a plain in-list add as `accept`.** Adding a vetted, recommended vendor to the package isn't really *overriding* the AI — reserve `override` for picking something the AI did **not** recommend, and `reject` for explicitly dismissing a recommendation. If a simple add is `accept`, no reason is required and the audit row is still written. Confirm this matches how `decision` is currently derived in `RecommendationResults.tsx`.
   - **or**, if a non-top add genuinely is an `override`, supply a `reason` — reuse the existing override-reason capture on the card (the `onConfirmPick(overrideReason)` flow) or default to a clear system reason like `"Employee added a non-top recommendation to their package"`.
2. **Make the fire-and-forget write observable.** It must not block the pick (keep it async), but a non-2xx must be **logged** (console/telemetry), not silently swallowed — otherwise future audit-trail drops are invisible again.
3. **Do not change** the backend reason requirement, the services-state path (it's fine), or the shortlist persistence.

## Reproduce first (fast, no UI needed)
From the app origin (or with a fixture token): `POST /api/ai/decisions` with `{feature, recommendation_id, ai_output:{}, decision:'override'}` and no reason → observe the 400. Add a `reason` → 201. Then exercise the real "Add to package" on 6 vendors (mix of top + non-top) and confirm the network tab shows **zero** 400s on `/api/ai/decisions` after the fix.

## Acceptance
1. 6 rapid "Add to package" picks (top + non-top, across 2 categories) → **zero 400s** on `/api/ai/decisions`.
2. `ai_decisions` has **one row per pick** (overrides/rejects included) with a non-null `reason` where the contract requires it.
3. The pick UI is unchanged and never blocks; a failed decision write is logged, not swallowed.
4. Services-state persistence and the reason requirement are untouched.
5. `cd frontend && npx tsc --noEmit` + `npm run build` clean; add a test around the decision-classification / reason logic.

## Hard rules
- Branch `fix/aidecision-override-reason` off `main`, own PR. Never `fix/td-qa-services-batch-0719`, never push `main`.
- Frontend-first. If you touch a backend router, register in BOTH `backend/main.py` and `backend/app/main.py` (per `CLAUDE.md`) — but the fix should not need a backend change.

## Report
branch · SHA · PR · the decision-classification change (accept vs override) · how reason is now always supplied when required · zero 400s captured · ai_decisions rows written for overrides · tsc/build/test output.
