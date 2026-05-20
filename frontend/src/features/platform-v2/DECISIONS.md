# platform-v2 decisions log

Append-only log of architectural and product decisions made during the platform-v2 port. Newest entries on top. Each entry: date, what, why, alternative considered.

---

## 2026-05-20 · Safety-net committed before any porting

**Decision:** Land a 6-commit "safety net" (cruft cleanup, design-preview sandbox, this scaffold, flags module, V2Gate, WIP log) before touching any screen.

**Why:** The team wants to migrate without ever breaking the live app. Safety net puts the infrastructure (flags, gate, adapter location, decision log) in place ahead of any product work, so every later screen ports against a stable platform.

**Alternative considered:** Start with screen 1 directly. Rejected because the first screen would have invented the recipe ad-hoc; codifying the recipe first means screens 2..N are mechanical.

---

## 2026-05-20 · Adapter pattern, not direct API consumption

**Decision:** Components in `platform-v2/` will never call APIs directly or read raw API response shapes. Each screen has an `adapter.ts` that converts real-API shape → prototype shape, and a hook that wires the query to the adapter.

**Why:** The prototype was designed against a mock schema (`{from, to, stage, cap}`). The real API uses different field names (`origin_country`, `destination_country`, `assignment_status`, `entitlement.max_amount`). Either we rename one side or we translate. Translation lets both sides evolve independently and gives us one fixed point per screen to test.

**Alternative considered:** Rename real-API fields to match the prototype. Rejected — would require 400+ endpoint changes across a 13.7k-line monolith and break every existing consumer.

---

## 2026-05-20 · Feature flags via a new platform-v2 namespace, NOT extending featureFlags.ts

**Decision:** Add `frontend/src/features/platform-v2/flags.ts` rather than modifying the existing `frontend/src/featureFlags.ts`.

**Why:** Two reasons. (1) `featureFlags.ts` is already modified in the user's uncommitted WIP — touching it would couple the platform-v2 scaffold to unfinished work. (2) Keeping all V2 plumbing inside `features/platform-v2/` makes the boundary explicit and the eventual cleanup (when all screens have shipped and flags are deleted) is a single directory.

**Alternative considered:** Extend the existing `featureFlags.ts`. Defer to a later commit once user WIP lands.

---

## OPEN — Uncommitted WIP overlapping prototype screens

The following are present in the working tree (untracked or modified) and overlap conceptually with platform-v2 screens. **Decision pending — to be analysed methodically in a follow-up session.**

| File / dir | Overlaps prototype screen | Status |
|---|---|---|
| `frontend/src/pages/HrPolicyBuilder.tsx` | s5b · Policy Builder (HR) | Untracked |
| `frontend/src/pages/HrProviderGrid.tsx` | s7 · Mobility Control provider view | Untracked |
| `frontend/src/pages/ProviderPortal.tsx` | (separate but related) | Untracked |
| `frontend/src/pages/EmployeeTaskPage.tsx` | s3 · Roadmap task drawer | Untracked |
| `frontend/src/features/policy-builder/` | s5b · Policy Builder | Untracked |
| `frontend/src/features/timeline/RelocationTimeline.tsx` | s3 · Roadmap | Untracked |
| `frontend/src/components/providers/` | s6 · Marketplace / s7 provider grid | Untracked |
| `frontend/src/api/policyBuilder.ts` | s5b backend wiring | Untracked |
| `frontend/src/api/providerPortal.ts` | provider portal backend wiring | Untracked |
| `frontend/src/api/providers.ts` | provider list backend wiring | Untracked |
| `frontend/src/components/RequireEmployeeRoute.tsx` | (auth guard) | Untracked |
| Several `M` files in `frontend/src/` and `backend/` | (in-flight backend + nav changes) | Modified |

**Plan:** In the next working session we read each file, classify it as:
- **Keep + adopt** — already prototype-aligned; integrate as the V2 implementation
- **Keep but rework** — useful logic but UI doesn't match prototype; harvest the data hooks
- **Replace** — start fresh from the prototype design

Until classified, none of these are touched by platform-v2 commits.

---

## Validation gates (canonical)

### Tier A — every commit
- [ ] `cd frontend && npx tsc --noEmit` exit 0
- [ ] `npm run build` exit 0
- [ ] Commit message: imperative, scoped, names the screen + step number

### Tier B — before flipping the flag in your own session
- [ ] `npx vitest run` all green
- [ ] Manual smoke: golden path on V2 works end-to-end (steps recorded here)
- [ ] Auth boundaries: log out → blocked. Wrong role → blocked. Right role → works.
- [ ] Network throttled to "Slow 3G" once; loading states visible and real
- [ ] Console: zero red errors, zero new warnings
- [ ] Rate limit: 5 quick page reloads doesn't trigger 429s

### Tier C — before flipping for any user other than you
- [ ] Dogfood for 3–5 working days with no manual rollback
- [ ] Side-by-side diff with legacy captured and accepted here
- [ ] One teammate or beta user clicks through it on real data
- [ ] You've watched it work on real (not test) data
