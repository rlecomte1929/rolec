# platform-v2 decisions log

Append-only log of architectural and product decisions made during the platform-v2 port. Newest entries on top. Each entry: date, what, why, alternative considered.

---

## 2026-05-20 · Solo, pre-customer operating mode

**Decision:** The repo runs in "solo mode" until first real customer is using the platform. Solo mode relaxes the production-grade safety rules. The matrix in [`README.md`](./README.md#operating-rules) is the source of truth.

**What gets dropped:**
- 3–5 day soak periods → ~10 minutes of clicking around
- "Teammate clicks through it" (Tier C) → not applicable
- Strict "never commit speculative WIP" → committing WIP is *safer* than untracked
- Schema migration via Supabase branch first → can apply directly

**What stays in BOTH modes:**
- `tsc --noEmit` + `npm run build` clean before every commit
- Atomic, revertable commits
- Adapter pattern (real API ↔ V2 shape)
- Flag-gated screens (still useful for one-click V2/legacy toggle in *your* browser)
- DECISIONS.md as memory across sessions

**Trigger to flip to production mode:** first customer/user on real data, OR the codebase gains a second active developer. Whichever comes first. When that happens, this entry gets a follow-up "flipped" annotation and the rules tighten back to the right column of the README matrix.

**Why:** The production-mode rules were borrowed from a different operating context. Applying them to a solo, pre-customer codebase wastes calendar time on coordination ceremony that has no audience. The boundary is real and named so we don't forget to tighten back when it matters.

**Alternative considered:** Stay in production mode "to build good habits." Rejected — the habits that matter (type-check, atomic commits, adapter pattern, decision log) are kept; the ones that don't (multi-day soaks, teammate sign-off) just slow the only developer down.

---

## 2026-05-20 · Baseline checkpoint commit, untracked WIP captured into git

**Decision:** Land one big "chore: baseline checkpoint" commit (`191ad2a`) that captures the entire working tree as of 2026-05-20 — 41 files, +8.4k lines — before starting any platform-v2 analysis or porting work.

**Why:** The working tree had ~30 modified or untracked files from previous in-flight work (HrPolicyBuilder, HrProviderGrid, ProviderPortal, EmployeeTaskPage, policy-builder feature dir, timeline feature dir, providers component dir, plus their backend routers + API wrappers). Leaving these uncommitted meant:
  - Not in git history → losing files by accident was possible
  - No stable baseline to diff "new" changes against during analysis
  - Every git operation had to dodge a grey zone

In solo, pre-customer mode the cost of committing speculative work is near zero (revert is one command) and the cost of NOT committing is real (lost work, ambiguous diffs). So we committed.

**Three backup layers were created first** in case anything goes wrong:
1. `~/relopass-backups/relopass-20260520-103213.bundle` — full git bundle (all branches, tags, history)
2. `~/relopass-backups/relopass-worktree-20260520-103213.tar.gz` — entire working tree (incl. untracked) as a tarball
3. In-repo tag `pre-baseline-20260520-103213` + branch `backup/pre-baseline-20260520-103213` for instant in-repo restore

**Alternative considered:** Surgically extract only the `/design-preview` route from App.tsx and leave everything else uncommitted (the original "Option 1a" plan). Rejected once we learned the project is solo + pre-customer — the surgical extraction is process overhead built for a context that doesn't apply.

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

## OPEN — In-tree WIP overlapping prototype screens (now committed in baseline `191ad2a`)

The following files were committed to the baseline (`191ad2a`) on 2026-05-20 and overlap conceptually with platform-v2 screens. **Each one needs a verdict — to be filled in during the WIP classification session.**

| File / dir | Overlaps prototype screen | Verdict | Notes |
|---|---|---|---|
| `frontend/src/pages/HrPolicyBuilder.tsx` | s5b · Policy Builder (HR) | TBD | |
| `frontend/src/pages/HrProviderGrid.tsx` | s7 · Mobility Control provider view | TBD | |
| `frontend/src/pages/ProviderPortal.tsx` | (separate but related) | TBD | |
| `frontend/src/pages/employee/EmployeeTaskPage.tsx` | s3 · Roadmap task drawer | TBD | |
| `frontend/src/features/policy-builder/` (6 files) | s5b · Policy Builder | TBD | |
| `frontend/src/features/timeline/RelocationTimeline.tsx` (+stories, a11y audit) | s3 · Roadmap | TBD | |
| `frontend/src/components/providers/` (6 files) | s6 · Marketplace / s7 provider grid | TBD | |
| `frontend/src/api/policyBuilder.ts` | s5b backend wiring | TBD | |
| `frontend/src/api/providerPortal.ts` | provider portal backend wiring | TBD | |
| `frontend/src/api/providers.ts` | provider list backend wiring | TBD | |
| `frontend/src/components/RequireEmployeeRoute.tsx` | (auth guard) | TBD | |
| `frontend/src/hooks/useProviderRealtime.ts` | s7 realtime updates | TBD | |
| `frontend/src/types/relocationPolicy.ts` | s5b types | TBD | |
| `backend/app/routers/hr_policies.py` | s5b backend | TBD | |
| `backend/app/routers/provider_portal.py` | provider portal backend | TBD | |

**Verdict legend:**
- **ADOPT** — already prototype-aligned; integrate as the V2 implementation. Becomes the canonical V2 for that screen.
- **REWORK** — useful logic but UI doesn't match prototype; harvest the data hooks / API wrappers, replace the UI.
- **REPLACE** — start fresh from the prototype design. The current implementation gets deleted (or kept temporarily behind a flag).
- **KEEP** — has nothing to do with prototype; leave alone, don't classify against platform-v2.

**Process for filling this in:** WIP classification session — for each file, read it, compare to the corresponding prototype JSX (`platform-s*.jsx`), write the verdict + a 1-line reason in the Notes column. No code changes during classification. Code changes come in the next session, one screen at a time, following the per-screen recipe.

---

## Validation gates (canonical)

### Tier A — every commit (kept in both modes)
- [ ] `cd frontend && npx tsc --noEmit` exit 0
- [ ] `npm run build` exit 0
- [ ] Commit message: imperative, scoped, names the screen + step number

### Tier B — before flipping the flag in your own browser (kept in both modes)
- [ ] `npx vitest run` all green (if tests exist for the screen)
- [ ] Click the golden path of the V2 screen end-to-end
- [ ] Console: zero red errors, zero new warnings
- [ ] Auth boundaries: log out → blocked. Wrong role → blocked. Right role → works.

### Tier C — before declaring a screen "done"

**Solo mode (current):**
- [ ] ~10 minutes of clicking through V2 on real data
- [ ] Discrepancies vs legacy captured here (fix or explicitly accept)

**Production mode (future, when first customer lands):**
- [ ] Dogfood for 3–5 working days with no manual rollback
- [ ] Side-by-side diff with legacy captured and accepted here
- [ ] One teammate or beta user clicks through it on real data
- [ ] You've watched it work on real (not test) data
- [ ] Network throttled to "Slow 3G" once; loading states visible and real
- [ ] Rate limit: 5 quick page reloads doesn't trigger 429s
