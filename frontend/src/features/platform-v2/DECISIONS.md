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

## Phase 0 · s9g Companies — port comparison (2026-05-20)

Step 1 of the per-screen recipe. Read both sides; capture the diff.

### Prototype side
`frontend/public/design-preview/platform-s9g-companies.jsx` — 1116 LOC.

Layout (top → bottom):
- Page header: eyebrow path + h1 + admin pill + Export CSV + Add tenant buttons + sub-line
- **KPI strip** (9 cards): Total / Active / Inactive / Archived / Premium / HR users / Employees / Open cases / Data issues
- **Filter bar**: search + 4 selects (status, plan, country, size) + "Issues only" toggle + "Clear" link
- **Table** with drag-reorderable columns: name (with logo + legal_name), plan, status, country, size, hr (with seat ratio + bar), emp (with seat ratio + bar), cases, contact (primary + sub-line), created (relative date), row actions menu
- **Bulk-select** with header checkbox (indeterminate state) + row checkboxes
- **Slide-out detail panel** triggered by row click — tabs: overview / hr_users / employees / assignments / policies — with fade-in placeholder while loading

### Legacy side
`frontend/src/pages/admin/AdminCompanies.tsx` — 841 LOC. Fed by `adminAPI.listCompanies(query)` → `AdminCompany[]` (typed in `frontend/src/types.ts:767`).

Layout:
- Top filter row (search + status + plan + country + size + HR-min + employees-min + cases-min + contact)
- Table with sortable headers
- **Inline row editing** (click edit → fields become inputs → save / cancel)
- **Add Company modal**
- **Bulk archive / delete** with feedback states
- Drill-in via `<Link to={/admin/companies/${id}}>` (separate `CountryDetailPage` / detail route)

### Field-by-field shape diff

`AdminCompany` (real) vs prototype's shape — the diff is small:

| Field | Real `AdminCompany` | Prototype | Action |
|---|---|---|---|
| `id`, `name`, `country`, `size_band`, `address`, `phone`, `hr_contact`, `support_email`, `created_at`, `updated_at`, `status`, `plan_tier`, `hr_seat_limit`, `employee_seat_limit`, `hr_users_count`, `employee_count`, `assignments_count`, `primary_contact_name`, `missing_from_registry`, `missing_from_companies_table` | ✓ | ✓ | Pass through |
| `legal_name` | — | "Aurora Energy AS" | Adapter substitutes `name` when missing |
| `industry` | — | "Energy" | Adapter returns `null`; column hidden for now |
| `website` | — | "aurora-energy.com" | Adapter returns `null`; not shown in v1 |
| `hq_city` | — | "Paris" | Adapter returns `null`; not shown in v1 |
| `tone` | — | 'a'..'f' | Adapter derives deterministically from `id` (hash → 6 buckets) |

**Endpoint mapping:**
- List → `GET /api/admin/companies` (existing — used by `adminAPI.listCompanies`)
- Detail → `GET /api/admin/companies/{company_id}` (existing — backs `AdminCompanyDetail*` types already in `types.ts`)

### What the V2 port WILL include (scope of Phase 0)

- KPI strip (9 cards, computed client-side from the list response)
- Filter bar — search + 4 selects + "issues only"
- Table — name/plan/status/country/size/hr-seat-progress/emp-seat-progress/cases/contact/created
- Slide-out detail panel — overview tab only for now (skipping hr_users / employees / assignments / policies sub-tabs in v1)
- Empty / loading / error states
- Read-only

### What the V2 port WILL NOT include (deferred)

- Drag-reorderable columns (cosmetic; deferred unless requested)
- Bulk-select + bulk actions (legacy has them; not in scope for read-only proof)
- Inline row editing (legacy has it; V2 detail panel becomes the edit surface later)
- Add Tenant modal (legacy has it; revisit when V2 takes over fully)
- Export CSV button (stub button, no handler in v1)
- HR Users / Employees / Assignments / Policies sub-tabs in detail panel (requires `/api/admin/companies/{id}` detail call; defer to v1.1)

### V1 sub-scope reasoning

This is **Phase 0 — recipe proof**. The goal is to land a working V2 screen, exercise the adapter pattern end-to-end, validate the flag gate, and produce a side-by-side comparison. Editing surfaces are deferred so the proof stays read-only (no data integrity risk). Once the read-only pattern is proven, editing and bulk actions get added in follow-up commits — same recipe, same flag.

### Side effects on the existing legacy page

None. Legacy `AdminCompanies.tsx` is untouched. V2 mounts at `/admin/companies-v2` (sibling route) until promotion. After promotion, the legacy route gates by `useV2Flag('companies')`; flag-off renders legacy, flag-on renders V2.

### Step 8 — Solo-mode QA checklist

Run with both tabs open side by side: `localhost:3000/admin/companies` (legacy) and `localhost:3000/admin/companies-v2` (V2).

**Smoke (must all pass before flipping the flag):**

- [ ] V2 route loads without console errors / red warnings
- [ ] Page shows the same number of company rows as legacy
- [ ] Each row shows the company name + the same plan, status, country, size as legacy
- [ ] Company logos render with stable colours (refresh → same colour for the same company)
- [ ] HR seat + Employee seat progress bars render and the % shape matches what you'd expect from the count/limit
- [ ] Clicking a row opens the slide-out detail panel
- [ ] Detail panel close button + backdrop click both dismiss
- [ ] Detail panel re-opens for a different company without ghost state
- [ ] Search filter shrinks the row count live
- [ ] Each select (status, plan, country, size) filters as expected
- [ ] "Issues only" checkbox filters to companies with `missing_from_registry` or orphan rows (if you have any in your dev DB; otherwise the list goes empty)
- [ ] "Clear filters" button resets all selects + search + checkbox
- [ ] Refresh link triggers a re-fetch (Network tab shows new request)
- [ ] Empty state ("No companies match your filters") shows when filters drop the list to zero
- [ ] Auth: log out → both routes redirect away. Log in as non-admin → 403 / redirect. Log in as admin → both routes render.

**Accepted scope differences vs legacy (already decided, no action):**

| Legacy has | V2 deliberately doesn't (yet) | Why |
|---|---|---|
| Per-column search inputs (HR-min, employees-min, cases-min, contact) | Single search bar + 4 selects | Prototype design; matrix-style column filtering deferred |
| Inline row editing | Read-only | Phase 0 = read-only proof |
| Add Company modal | "Add tenant" button is absent | Editing surface deferred |
| Bulk archive / delete | No bulk-select | Editing surface deferred |
| `<Link>` to `/admin/companies/:id` detail page | Slide-out detail panel only (no sub-tabs) | Sub-tabs deferred to v1.1 (require `/api/admin/companies/{id}` detail call) |
| Sortable column headers | No sort UI in V2 | Prototype's drag-to-reorder + sort deferred; default order is API order |

**Findings to log here when you run the QA:**

(Add a dated entry below with anything that surprised you. Format: `- 2026-MM-DD · <finding> · <action: fix / accept / defer>`.)

- 2026-05-20 · `/admin/companies-v2` rendered but visual fidelity vs prototype was low (flat Badge/Card primitives, default density) · **fix** in `2d670ff` — replaced antigravity primitives with Tailwind utilities + custom Pill component; KPI tone system, gradient logo chips, sticky+blurred filter bar, denser table.
- 2026-05-20 · One-click demo buttons in `/auth?mode=login` returned "Invalid username or email" — defaults were `demo-admin / demo123` which don't exist · **fix** in `bb7a7c8` — defaults now match `backend/scripts/seed_testingapril_accounts.py` (admin@relopass.com / hr@testingapril.com / employee@testingapril.com). Requires the seed script to have been run.

---

## Phase 1 · Screen 2 — Provider Grid (s7) — port complete (2026-05-20)

**Verdict applied: ADOPT** (per the classification table).

The existing `pages/HrProviderGrid.tsx` + `components/providers/ProviderStatusGrid.tsx` are already prototype-aligned in concept (Provider × Case matrix). No data-shape translation needed → **no adapter, no Vitest unit test for shape translation** — the existing typed `ProviderGridRow` IS the V2 shape.

### What landed (single commit, not 10)

`features/platform-v2/provider-grid/ProviderGridV2Page.tsx` — thin wrapper that:
  - Reuses `hrAPI.getProviderStatusGrid()` (existing endpoint, no API change)
  - Reuses the existing `<ProviderStatusGrid>` component as-is for the matrix
  - Adds prototype-style page header (eyebrow `RELOPASS · /hr/provider-grid` + h1 "Provider status" + `v2 preview` pill + Refresh + sub-line)
  - Adds a 6-card KPI strip computed locally from the same `rows` array (total / not-started / in-progress / at-risk / complete / blocked cells)
  - Reuses the `Pill` + `Kpi` idiom established in s9g Companies (gradient logos absent — N/A here since the matrix shows status cells, not company chips)

Mounted at sibling `/hr/provider-grid-v2` (always V2) and gated on legacy `/hr/provider-grid` via `V2Gate flag="mobility_control"` (default OFF).

### What this proves about the recipe

**ADOPT screens are roughly 3× faster than REWORK / new screens.** s9g Companies needed 10 commits (read-only port from scratch). s7 Provider Grid needed 1 — because the table component, the API call, the types, and the data already lived in real code. The recipe collapses to:
  1. Wrap existing component in prototype-styled page shell (header + KPIs).
  2. Sibling route + V2Gate the legacy.
  3. Validate.

For future ADOPT screens, skip steps 2-4 of the standard recipe (stub adapter, implement adapter, write adapter tests). Keep step 1 (comparison), step 5 (V2 component wrapper), step 7 (route + gate), step 8 (QA notes).

### Step 8 — Solo-mode QA checklist (Provider Grid)

Run with both tabs open: `localhost:3000/hr/provider-grid` (legacy, default) and `localhost:3000/hr/provider-grid-v2` (V2 always).

- [ ] V2 route loads without console errors specific to it
- [ ] Header eyebrow + h1 + v2 pill + Refresh button render
- [ ] KPI strip shows 6 cards; values match what you'd get summing the row list
- [ ] Existing ProviderStatusGrid renders below the strip (sortable headers, cell statuses, employee names)
- [ ] Refresh link triggers re-fetch (matches the inner grid's own Refresh button)
- [ ] Empty state still works when no rows
- [ ] Auth: HR or ADMIN access works; other roles blocked (same boundary as legacy route)

### Recipe lesson (carry forward)

**ADOPT verdict means single-commit port.** Don't fake the 10-step ritual when the underlying component is already correct — it's overhead with no protection added. The discipline that matters (tsc + build green, V2Gate, sibling route, written QA notes) still applies; the ceremony (multiple step commits, adapter + fixture + test trio) does not.

---

## Phase 0 follow-up · s9g Companies — write-surface parity (2026-05-20)

The first Phase 0 port (commits `fa04b4e`..`fdc29ca`) was deliberately read-only — Add / Edit / Archive / Delete were deferred per the step-1 scope decision. This block restores them.

Three commits, each adds one self-contained capability:

| Commit | What | Files added | Risk |
|---|---|---|---|
| `cc20f99` C1 | `CompanyFormModal` (Add + Edit) + "+ Add tenant" button in header | `CompanyFormModal.tsx` | 🟢 Non-destructive |
| `a9f6c91` C2 | `RowActionMenu` (⋯ dropdown) + Edit + Archive (soft, `window.confirm`) | `RowActionMenu.tsx` | 🟡 Soft delete |
| `d785e38` C3 | `DeleteCompanyDialog` (hard, type-name confirmation) | `DeleteCompanyDialog.tsx` | 🔴 Irreversible |

### UX guardrails by destruction level

| Action | Guardrail | Reversible? |
|---|---|---|
| Add tenant | None — fill form, submit | n/a |
| Edit | None — fill form, save | n/a |
| Archive | Single `window.confirm` | Yes — set `status='active'` to undo |
| Delete | Dedicated dialog. Operator must type the company name verbatim before the destructive button enables | No — orphans references |

This is a deliberate departure from the legacy which used a bulk-select mode for both Archive and Delete (cheaper per-action but easier to mis-target). V2's per-row pattern with progressively stronger gates trades throughput for safety — the right call for an admin surface used by the same person who owns the data.

### Where Add / Edit / Archive / Delete reach the backend

| V2 trigger | adminAPI method | Endpoint |
|---|---|---|
| Add tenant modal submit (mode=create) | `createCompany(payload)` | `POST /api/admin/companies` |
| Edit modal submit (mode=edit) | `updateCompany(id, payload)` | `PATCH /api/admin/companies/{id}` |
| Row menu → Archive | `archiveCompany(id)` | `POST /api/admin/companies/{id}/archive` |
| Row menu → Delete… (after type-name confirm) | `deleteCompany(id)` | `DELETE /api/admin/companies/{id}` |

All four go through the same `adminAPI.invalidateApiCachePrefix('admin:companies:')` cache-bust, so the V2 `useCompaniesV2.refresh()` returns fresh data on the next call.

### QA additions

- [ ] Add tenant: open modal, enter name only, submit → new row appears in the table.
- [ ] Add tenant: try to submit without a name → inline "Name is required" error.
- [ ] Edit: open row menu → Edit → form prefilled with current values → change country → save → row updates.
- [ ] Archive: open row menu → Archive → confirm dialog → row's status becomes `archived` (or row disappears if filtered).
- [ ] Archive of an already-archived company: the Archive menu item is hidden (`disableArchive` prop).
- [ ] Delete: open row menu → Delete… → dialog appears. Confirm button stays disabled until the typed name matches exactly. Type correctly → confirm → row removed from list.
- [ ] Delete escape paths: ESC key dismisses; outside-click dismisses (unless submitting).
- [ ] Error surfacing: kill the backend mid-action → `actionError` banner shows above the table with a Dismiss button.

---

## Phase 1 · Screen 3 — s7p Company Profile (HR) — port (2026-05-20)

Single-record edit page (different shape from s9g's list+modal). HR uses this to maintain their own company's profile.

### Prototype side
`frontend/public/design-preview/platform-s7p-profile.jsx` — 870 LOC. Four sections:
  - **A · Identity** — name, legal_name, industry, size_band, website
  - **B · Location & Contact** — country, hq_city, address, phone
  - **C · HR & Mobility Defaults** — hr_contact, support_email, default_destination_country, default_working_location
  - **D · Branding** — logo upload + brand_color picker

Variants: `filled` (canonical), `empty` (welcome), `wizard` (3-step).

### Legacy side
`frontend/src/pages/HrCompanyProfile.tsx` — 287 LOC. Flat single-column form (no section grouping). Same field set as prototype.

Data layer (reused as-is in V2):
  - `useHrCompanyContext()` → `{ company, loading, error, refresh }`
  - `hrAPI.getCompanyProfile()` → `GET /api/hr/company-profile`
  - `hrAPI.saveCompanyProfile(payload)` → `POST /api/hr/company-profile`
  - `hrAPI.uploadCompanyLogo(file)` → `POST /api/hr/company-profile/logo`
  - `hrAPI.removeCompanyLogo()` → `POST /api/hr/company-profile/remove-logo`

### Field shape: identical

Both sides consume `CompanyProfilePayload` (types.ts:86). **No adapter needed** — V2 component reads/writes the same fields the legacy already supports. One exception: `brand_color` is in the prototype + the DB schema (`database.py:9669`) but is NOT in `CompanyProfilePayload`. Deferred to follow-up.

### V2 scope (this port)

**In:**
  - Section-grouped layout matching the prototype (A / B / C / D)
  - Same field set as legacy (no new schema)
  - Sticky save bar at the bottom with "saved ✓" flash
  - Logo upload (reuse `hrAPI.uploadCompanyLogo` + `removeCompanyLogo`)
  - Country picker with flags (prototype-style)
  - Reuses `useHrCompanyContext` for the data path

**Out (deferred):**
  - Brand color picker (needs `brand_color` added to `CompanyProfilePayload` + API contract)
  - Empty + wizard variants (canonical filled only)
  - Completion scoring (`FIELD_WEIGHTS` strip in prototype)
  - Zoom-into-section UX (prototype's `profileZoom` tweak)

### Recipe profile

Closer to REWORK than ADOPT (visual layer redone, data layer untouched). About **3-4 commits**, not 10:
  1. Comparison + scope (this entry)
  2. CompanyProfileV2 component (visual + form state)
  3. Sibling route + V2Gate
  4. QA notes + tag

No `adapter.ts` because the input and output types are already aligned.

### Recipe lessons (carry forward to screen 2..N)

1. **Antigravity primitives are form-shaped, not table-shaped.** `Badge`, `Card`, `Input`, `Select`, `ProgressBar` have opinionated APIs (closed string callbacks, options arrays, fixed paddings). They work great in HrPolicy and the policy assistant. For prototype-style data screens (table headers, sticky filters, compact KPIs, dense pills) plain HTML + Tailwind utilities give better control. **Recipe addition:** for any ported screen, the first sub-decision is "form-style or data-style"; data-style screens skip antigravity in favour of Tailwind utilities.
2. **Visual fidelity needs an explicit pass.** First cut "works" but doesn't feel like the prototype. Bake a "polish pass" into step 8 (Solo-mode QA) — not as a separate phase but as expected work during QA.
3. **Defaults that fail silently are worse than defaults that fail loudly.** The `demo-admin / demo123` defaults looked plausible but referenced accounts that don't exist. Future env-var defaults should either match real seeds or surface a clear "configure VITE_DEMO_* first" message.

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
