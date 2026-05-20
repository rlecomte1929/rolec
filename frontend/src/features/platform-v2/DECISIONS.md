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

## In-tree WIP classification (completed 2026-05-20)

Each WIP file committed in baseline `191ad2a` has been read and classified. Verdicts below.

**Verdict legend:**
- **ADOPT** — already prototype-aligned; use as the canonical V2 implementation for the matching prototype screen.
- **REWORK** — data layer and APIs are sound; UI does not match the prototype. Keep the data layer, replace the visualization.
- **REPLACE** — start fresh from the prototype design; the current implementation gets deleted once the V2 lands.
- **KEEP** — has nothing to do with prototype; standalone feature, leave it alone.

### Classification

| File / dir | Overlaps prototype | Verdict | Notes |
|---|---|---|---|
| `frontend/src/pages/HrPolicyBuilder.tsx` | s5b · Policy Builder | **REWORK** | 13-line page shell that mounts `PolicyBuilderWizard`. Keep the page entry; swap the wizard for the prototype's matrix UI when s5b is ported. |
| `frontend/src/pages/HrProviderGrid.tsx` | s7 · Mobility Control (provider view) | **ADOPT** | 60-line shell over `ProviderStatusGrid`. Aligned with the prototype's HR provider-status concept. Use as-is for s7's provider tab. |
| `frontend/src/pages/ProviderPortal.tsx` | (none) | **KEEP** | Public magic-link portal for *external* providers. The prototype has no equivalent persona. Self-contained, well-designed. |
| `frontend/src/pages/employee/EmployeeTaskPage.tsx` | (loose to s3) | **KEEP** | Standalone "my tasks" inbox over `servicesAPI.getTasks()`. The prototype roadmap (s3) has timeline steps but not a generic task list — distinct concept. |
| `frontend/src/features/policy-builder/` (6 files: wizard, 3 steps, indicator, draft hook) | s5b · Policy Builder | **REWORK** | 5-step linear wizard around tiers/budgets/documents/vendor-categories/approval. Prototype wants a 6-category × 31-benefit matrix instead. **Preserve** `usePolicyDraft.ts` (draft persistence + flash UX) and the API layer; **replace** the StepX components with a matrix UI. Schema extension required (see Schema gap below). |
| `frontend/src/features/timeline/RelocationTimeline.tsx` (+stories, a11y audit) | s3 · Roadmap | **REWORK** | Excellent vertical-timeline component with mobile bottom-sheet pattern and completed a11y audit. Prototype wants parallel tracks (immigration/housing/family/admin), not a single-axis timeline. Keep the data layer (`fetchRelocationPlanView`, status taxonomy, "mark done" PATCH); rework the visualization. The a11y audit work is reusable in the new component. |
| `frontend/src/components/providers/` (6 files: status grid, row, status cell, invite modal, assign-task modal, coordination panel) | s7 provider grid + tasks | **ADOPT** | Provider × case matrix with 4 categories (housing/immigration/shipping/other) and 4 coordination statuses. Sortable, auto-refresh, mobile-friendly. The invite + assign flows go deeper than the prototype — that's additive, not conflict. Use the whole dir as the canonical V2 for s7's provider tab. |
| `frontend/src/api/policyBuilder.ts` | s5b API | **REWORK** | Typed wrapper over `/api/hr/policies` CRUD. Sound, but contracts (`RelocationPolicyJson` shape) will evolve when s5b's canonical-benefits taxonomy lands. Extend rather than rewrite. |
| `frontend/src/api/providerPortal.ts` | (none) | **KEEP** | Separate axios instance + token management for the external provider portal. Parallel surface; prototype-agnostic. |
| `frontend/src/api/providers.ts` | s7 provider grid + tasks | **ADOPT** | Clean typed wrapper over `/api/hr/providers` and `/api/hr/provider-tasks`. Feeds the providers components. Use as-is. |
| `frontend/src/components/RequireEmployeeRoute.tsx` | (auth infra) | **KEEP** | Pure role-gate route guard (EMPLOYEE + ADMIN pass, HR redirected to command center, unauth redirected to landing). Infrastructure; orthogonal to the prototype. |
| `frontend/src/hooks/useProviderRealtime.ts` | s7 realtime | **KEEP** | Supabase realtime subscription for `provider_tasks` with exponential-backoff reconnect and 60s polling fallback. Well-engineered, generic. |
| `frontend/src/types/relocationPolicy.ts` | s5b types | **REWORK** | TypeScript shape for the existing 5-dim policy JSON. Will be extended (not replaced) when the canonical-benefits taxonomy is added — `benefits` becomes a new top-level dimension alongside `budgets`. |
| `backend/app/routers/hr_policies.py` | s5b backend | **REWORK** | 274-line CRUD router with org-scoping, audit log, and atomic activate. Schema lives in migration `20260513150000_relocation_policy_builder_schema.sql`. Will need a follow-up migration to add the canonical-benefits dimension; router stays. |
| `backend/app/routers/provider_portal.py` | (provider portal) | **KEEP** | 561-line router with provider-JWT auth, task CRUD, case summary, profile, and 30s-debounced Resend email notifications. Parallel surface; not in scope for prototype port. |

### Patterns observed

1. **Infrastructure files are universally KEEP.** `RequireEmployeeRoute`, `useProviderRealtime`, `providerPortal` API + backend router — all standalone plumbing that's orthogonal to which UI sits on top.
2. **Provider stack is ADOPT.** The existing provider grid + modals are a *superset* of what the prototype's s7 shows. The prototype is a sketch; this implementation is the real thing. Wire the prototype's s7 to *render* these components rather than trying to redesign them.
3. **Policy stack is REWORK with schema work.** The existing implementation is solid engineering against the wrong data shape. Schema needs to grow (not shrink) before the prototype's matrix view can sit on top.
4. **Timeline is REWORK.** Beautiful component, wrong visualization for the prototype. The a11y audit and mobile bottom-sheet pattern are transferable.

### Schema gap surfaced

**One follow-up migration needed before s5b can be ported:**

The existing `policy_versions.json_schema` has dimensions: `tiers`, `budgets`, `documents`, `vendor_categories`, `approval_workflow`. The prototype s5b expects a `benefits` dimension keyed by **31 canonical benefit IDs across 6 categories**, with per-cell `{ covered: 'covered' | 'partial' | 'excluded', cap_amount, cap_currency, cost_estimate }`.

**Decision deferred to the s5b porting session.** Two options to weigh then:
- **(A) Extend** `RelocationPolicyJson` with an optional `benefits` dimension; new code reads/writes both old and new; old policies remain valid.
- **(B) Replace** `json_schema` with a canonical-benefits-first shape; data migration converts existing tiers/budgets/documents into benefit cells.

Recommendation when we get there: (A) — additive change, no breaking migration, reversible.

### Next-session plan

With verdicts in hand, the porting order from the original phased plan is unchanged but more concrete:

1. **Phase 0 — `s9g Companies` proof.** Read-only, admin-only, no overlap with WIP. Pure adapter-pattern dry run.
2. **Phase 1 — HR command center surface.** First ADOPT screens land here:
   - s7 provider grid → wraps the existing `providers/` components into the prototype's s7 layout (mostly composition work, low risk).
   - s7p Company Profile (no overlap; clean port).
   - s10 Inbox (no overlap).
3. **Phase 2 — Policy stack (REWORK + schema migration).** Highest-risk phase. Schema decision + matrix UI + adapter on top of `policyBuilder.ts`.
4. **Phase 3 — Roadmap REWORK (s3 over RelocationTimeline data).**

The KEEP files (provider portal, EmployeeTaskPage, RequireEmployeeRoute, useProviderRealtime) are out of scope for platform-v2 and do not need any further attention.

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
