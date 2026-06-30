# ReloPass — Platform-wide UI Consistency Audit

**Date:** 2026-06-30 · **Scope:** `frontend/src` (773 non-test `.tsx/.ts`) · **Rubric:** `DESIGN.md`
(navy `#0b2b43` + teal `#1f8e8b`, Inter + JetBrains Mono, 8px grid, antigravity component library) ·
**Method:** static analysis (grep/counts across the whole tree) — no app run required.

---

## Executive summary

ReloPass has a **mature, well-engineered frontend** (strict TS, error-gating ESLint with jsx-a11y, a
real in-house component library, near-total `<Button>` adoption). The problem is **not quality, it's
consistency** — the app was built across several eras (`pages/*` legacy, `features/*`, `platform-v2/*`)
and those eras never converged. The result:

> **Navigation is the one truly unified layer. Almost everything wrapping it — component libraries,
> page shells, headers, typography, container widths, color tokens — has drifted into 2–3 parallel
> ways of doing the same thing.**

The single highest-leverage theme is **consolidation**: collapse the duplicate component libraries and
shells into one canonical system, and the typography/color/spacing inconsistencies largely fix
themselves because there's finally one place to enforce them.

### Scorecard

| Dimension | Verdict | Headline numbers |
|---|---|---|
| Navigation (sidebar) | 🟢 **Strong** | One role-ranked `PlatformShellSidebar`; identical active-state/icons across personas |
| Button adoption | 🟢 **Strong** | 1,269 `<Button>` vs ~40 raw `<button>` (~97%) |
| Tailwind spacing grid | 🟢 **Good** | Only 2 arbitrary `p-[..px]` values; grid leak is in inline styles |
| Component system | 🔴 **Severe** | **3 overlapping libraries**; 177 raw `<select>` vs 68; 74 raw `<textarea>` (no shared); 81 raw `<table>`; 16+ Badge impls; 18+ bespoke Modals |
| Typography | 🔴 **Severe** | ~732 arbitrary `text-[..px]` (21 sizes incl. fractional); no shared Heading/Text; **`font-mono` renders the wrong font (bug)** |
| Page shell / layout | 🟠 **Drifted** | 2 shells (`AppShell` vs `AdminLayout`); ~58 pages bypass the shared header; container-width anarchy |
| Color / tokens | 🟠 **Drifted** | ~5,014 hardcoded hex; 1,379 raw brand-color literals that should be tokens; live shells use 0 CSS vars |
| Forms | 🟠 **Drifted** | `react-hook-form` + `zod` installed but unused; 115 files hand-roll `useState` forms |
| Dark mode / theming | ⚪ **Dead** | Full token system exists but `ThemeProvider` is wired to nothing live |
| Accessibility | 🟢 **Mature** (1 epic) | jsx-a11y at `error`; 537 muted-text contrast instances remain (WCAG-AA epic) |

---

## 1. Components — the structural root cause (🔴 severe)

**There are three overlapping component libraries:**
1. `src/components/antigravity/` — the canonical design system (26 components).
2. `src/features/platform-v2/shared/index.tsx` — a 768-line *parallel* library (re-implements
   Badge/ProgressBar/CountryFlag; owns Avatar/EmptyState/LoadingSpinner/ConfirmDialog/StatCard).
3. `src/components/admin/overview/` — a third mini-set (StatCard, Skeleton, ModuleCard).

So the same screen can import `Badge` from two places, and `StatCard`/`Avatar`/`ProgressBar`/
`CountryFlag` each exist 2–3×.

**Raw-HTML vs component adoption:**

| Primitive | Shared component | Raw HTML | Verdict |
|---|---|---|---|
| Button | 1,269 | ~40 | 🟢 ~97% migrated |
| Input | 365 | 21 | 🟢 strong |
| Card | 432 | — | 🟢 strong |
| Alert | 141 | — | 🟢 strong |
| **Select** | 68 | **177** | 🔴 inverted 2.6:1 — `antigravity/Select` exists |
| **Textarea** | **0 (none exists)** | **74** | 🔴 100% gap |
| **Table** | siloed `DataTable` (~9 uses) | **81** | 🔴 mostly raw |
| Badge | 151 | 16+ competing impls | 🟠 fragmented |
| Modal | ~29 | 18+ bespoke + inline `fixed inset-0` | 🟠 under-enforced |

**Worst raw-HTML offenders:** `AdminResourceEditor.tsx` (raw selects + textareas), `ResourcesPageContent.tsx`
(9 selects), `EmployeeIntakePage.tsx` (7 selects), the `pages/admin/*` cluster, `AdminCompanyDetail.tsx`
(4 tables).

**Missing best-practice primitives** (what a B2B SaaS / HR platform should have a shared component for):

| Component | Status | Notes |
|---|---|---|
| Data Table (sort/paginate) | Partial (siloed) | `platform-v2/data-table/DataTable.tsx` bypassed by 81 raw tables |
| Tabs | ❌ absent (shared) | hand-rolled `activeTab` in ≥9 files |
| Toast / Snackbar | ❌ absent | substituted by page banners |
| Tooltip | ad-hoc | `title` attrs + one-offs |
| Pagination | ❌ absent (shared) | only inside DataTable |
| Switch / Toggle | ❌ absent | none found |
| Date picker | ❌ absent | 36 raw `type="date"` inputs |
| Drawer | ad-hoc | 3 one-off drawers |
| Accordion | ad-hoc | 1 one-off |
| Skeleton | ad-hoc | `admin/overview/Skeleton` + scattered `animate-pulse` |
| Empty-state | shared in platform-v2 only | legacy pages inline "No X found" |
| Textarea | ❌ absent | 74 raw |
| Avatar | ad-hoc (not in antigravity) | 2 impls |

**States:** 34 distinct raw `animate-spin` spinners + 1 shared `LoadingSpinner` (platform-v2 only) +
skeletons — at least 3 loading patterns. Empty/error states largely copy-pasted.

**Forms:** `react-hook-form@7.80` + `zod@4.4` are in `package.json` but **effectively unused** for forms
(`useForm(` ≈ 0 component files); 115 feature files hand-roll per-field `useState` + inline validation.

---

## 2. Typography (🔴 severe) — includes a real bug

- **`font-mono` does not render JetBrains Mono.** `tailwind.config.js` defines only `sans` (no `mono`
  key), so all **115 `font-mono` usages** fall back to the default `ui-monospace/SFMono` stack — the
  brand mono font is essentially never rendering where it's used. `index.css:78` also sets the
  `code/pre` fallback to `source-code-pro`, contradicting DESIGN.md. **This is a fixable bug, not just
  drift.**
- **Type-scale epidemic:** ~732 arbitrary `text-[..px]` across **21 distinct sizes**, including
  fractional `12.5px / 11.5px / 10.5px / 13.5px / 9.5px`. Combined with named classes, ~31 distinct
  text sizes are in use; inline `fontSize:13` is the single most common size and isn't in the
  documented scale at all. Worst files: `HrPolicyBuilderV2Page.tsx` (122), `VendorPerformancePage.tsx`
  (59), `MobilityControlCenterV2Page.tsx` (34), `RoadmapTemplate.tsx` (32).
- **No shared typography primitive.** 469 hand-rolled `<h1–h4>` with ad-hoc classes; the same heading
  level renders at 8–9 different sizes and 2–3 different weights (h1: 34 semibold vs 12 bold; etc.).
  There is no `Heading`/`Text` component to enforce hierarchy — this is the structural cause of the
  size sprawl.
- **Good:** Inter is correctly applied at the base layer (self-hosted, `body` font-family, tailwind
  `sans`).

---

## 3. Color / tokens (🟠 drifted)

- ~5,014 hardcoded hex literals in `frontend/src`; **1,379 are raw brand colors** (`#0b2b43` / `#1f8e8b`)
  that should be `navy-*` / `accent-*` Tailwind classes or `--rp-*` vars per DESIGN.md.
- Live shells (`AppShell`, `AdminLayout`, `PlatformShellSidebar`) use **0 CSS variables** — every color
  is a hardcoded class/hex, so the token system can't theme them.
- ✅ The 4 purple/violet/indigo **brand violations** (DESIGN.md says zero purple) are already fixed in
  **PR #1207** (indigo/violet → slate/teal/sky/amber).

---

## 4. Spacing / sizing (🟢 grid good, 🟠 sizing drifted)

- **8px grid:** Tailwind spacing is clean (only 2 arbitrary `p-[..px]`). The grid leak is in **inline
  `style={{}}`** objects (heavy in `platform-v2`): off-grid `padding: 9px/5px/14px/11px/7px`,
  `gap: 10/6/3`.
- **Control heights not standardized:** `h-7/h-8/h-9/h-10/h-11/h-12` + arbitrary `h-[40/41/44px]` all
  used for similar controls. The (otherwise excellent) antigravity `Button` defines size via padding
  only and pins **no canonical height**.
- **Radius / shadow:** `rounded-lg` is a healthy de-facto standard (878 uses) but undercut by 11
  arbitrary radii + 12 bespoke `shadow-[rgba…]` elevations + a non-standard `shadow-4`.
- **Container width anarchy:** the documented page width `max-w-7xl` is used **only 7×**, drowned out
  by 20+ competing widths (`max-w-3xl/2xl/5xl` + arbitrary pixel caps), often **double-nested** inside
  the shell's already-capped container.

---

## 5. Page shell / layout / nav (🟢 nav / 🟠 shell)

- **Navigation is the best-unified layer:** one role-ranked `PlatformShellSidebar` (`ROLE_RANK`
  Employee<HR<Admin, cumulative sections), identical active-state tokens, lucide icons, grouping,
  collapse — the same for every persona.
- **But there are TWO shells:** `AppShell` (Employee + HR, ~47 pages) vs a separate hand-maintained
  `AdminLayout` (Admin, ~48 pages). They've diverged:
  - **Header:** AppShell = `<Breadcrumb>` + `text-2xl` h1 + subtitle. AdminLayout = uppercase eyebrow
    "Internal Superuser Console", **no breadcrumb component**, different crumb.
  - **Container:** AppShell = `max-w-7xl mx-auto` (centered, 1280px). AdminLayout = `px-8 py-7`
    (**full-bleed, no max-width, no mobile padding step**).
  - **Topbar:** AppShell = functional (RoleSwitcher, NotificationsBell, Logout, mobile drawer).
    AdminLayout = **decorative/non-functional** (a bell with no handler, an "Ask ReloPass AI" button
    with a **hard-coded `3` badge**, no mobile drawer → Admin is desktop-only).
- **~58 pages bypass the shared header** and hand-roll their own `<h1>` (the entire `platform-v2/*`
  tree + assorted first-party pages).
- **5 dead decoy shells** exist (`platform-v2/shell/{Sidebar,TopBar,AIPanel}.tsx`,
  `platform-v2/sidebar/PlatformSidebar.tsx`, `components/ProfileSidebar.tsx`) — zero or orphan importers.

---

## 6. Dark mode / theming (⚪ dead code)

`platform.css` fully defines `[data-theme='light']`, `[data-theme='dark']`, and a `prefers-color-scheme`
fallback. **But the controller is dead:** `ThemeProvider.tsx` is imported only by a dead decoy
(`platform-v2/shell/TopBar.tsx`), **not** by `main.tsx`/`App.tsx`; nothing sets `data-theme` at runtime;
the live shells have **0 `var(--…)`** and **0 `dark:`** variants. Dark mode would currently apply to no
page. → Decide: **wire it up** or **formally delete** the dead token system.

---

## 7. Accessibility (🟢 mature, 1 epic)

`eslint-plugin-jsx-a11y` is configured with rules promoted to `error` + a custom `local/no-clickable-div`
rule; `<img>` alt coverage is 100%; most clickable-divs are justified `aria-hidden` overlays. Remaining:
**537 muted-text instances** (`text-slate-400/gray-400/*-300`) for the WCAG-AA contrast epic (needs
surface-aware judgment, not a blind swap) + 2 genuine clickable-div comboboxes in `EmployeeIntakePage`.

---

## Proposed modification menu — decide to implement or not

Each item ships as its own **locally-verified** PR (tsc + eslint + vite build + vitest) and will **not**
be merged to `main` until you have Render credit (merge = Render deploy). IDs are referenced in the
decision request.

### P0 — quick, deterministic, low-risk (hours each)
| ID | Change | Why | Risk |
|---|---|---|---|
| **TYPE-1** | Fix the `font-mono` bug: add `mono: ['JetBrains Mono', …]` to `tailwind.config.js` + fix `index.css:78` code fallback | 115 usages instantly render the correct brand font; it's a bug, not a preference | 🟢 very low |
| **DEAD-1** | Delete the 5 dead decoy shells + orphaned `ProfileSidebar`/`Journey` (confirm 0 importers first) | Removes ~80KB of confusing dead code; smaller bundle | 🟢 low (dead code) |
| **TOKEN-1** | Verify/define `navy-*` + `accent-*` Tailwind tokens so they map to `#0b2b43`/`#1f8e8b` | Prerequisite that unlocks the hex→token migration | 🟢 low |

### P1 — structural consolidation (the high-value core; days each)
| ID | Change | Why | Risk |
|---|---|---|---|
| **COMP-1** | Collapse the 3 component libraries → one canonical antigravity (start Badge → StatCard → ProgressBar → Avatar) | Removes the root cause of most inconsistency | 🟠 medium (touch many imports) |
| **COMP-2** | Build the absent primitives: **Textarea, Tabs, Tooltip, Switch, Pagination, Skeleton, Toast** | Closes the best-practice component gaps | 🟢 additive |
| **COMP-3** | Migrate raw `<select>` (177) / `<textarea>` (74) / `<table>` (81) → shared components, page-cluster by cluster | Fixes the inverted adoption; consistent form/table UX | 🟠 medium (volume) |
| **SHELL-1** | Converge `AppShell` + `AdminLayout` into one shell (shared header/container/topbar; fix Admin's fake topbar + add mobile) | The biggest look-and-feel divergence across personas | 🟠 medium |
| **HEADER-1** | Add a shared `PageHeader`; make the ~58 bypassing pages adopt the shell title/breadcrumb | Uniform page headers everywhere | 🟠 medium |
| **TYPE-2** | Add shared `Heading`/`Text` primitives + drain `text-[..px]` to the scale | Enforces type hierarchy; kills the 732-occurrence sprawl | 🟠 medium |

### P2 — strategic (larger initiatives)
| ID | Change | Why | Risk |
|---|---|---|---|
| **TOKEN-2** | hex→token migration: 1,379 brand-color literals → `navy-*`/`accent-*` | Single source of color truth; enables theming | 🟠 high-volume churn |
| **A11Y-1** | Muted-text contrast epic (537, surface-aware) | WCAG-AA compliance | 🟠 needs per-instance judgment |
| **THEME-1** | Either **wire** dark mode (ThemeProvider→main + shells consume vars) or **formally delete** the dead token system | Stop shipping dead code; decide the product stance | 🟠 medium |
| **FORM-1** | Adopt the already-installed `react-hook-form` + `zod` for forms | Replace 115 files of hand-rolled state; consistent validation | 🟠 large |

### Recommended sequence
1. **P0 bundle first** (TYPE-1 + DEAD-1 + TOKEN-1) — one small PR, immediate wins, unblocks the rest.
2. **COMP-2** (build the missing primitives) before **COMP-1/COMP-3** (so migrations have targets).
3. **SHELL-1 + HEADER-1** together (they touch the same surface).
4. **TYPE-2** + **TOKEN-2** once the primitives/tokens exist.
5. P2 epics (A11Y-1, THEME-1, FORM-1) as deliberate, separately-scoped initiatives.

---

## Appendix — dead code to remove (DEAD-1)
- `frontend/src/features/platform-v2/shell/Sidebar.tsx` (zero importers)
- `frontend/src/features/platform-v2/shell/TopBar.tsx` (zero importers)
- `frontend/src/features/platform-v2/shell/AIPanel.tsx` (zero importers)
- `frontend/src/features/platform-v2/sidebar/PlatformSidebar.tsx` ("retired" per code comment)
- `frontend/src/components/ProfileSidebar.tsx` (only used by legacy `pages/Journey.tsx`)
- ⚠️ Keep `features/platform-v2/sidebar/navIcons.tsx` — it IS live (imported by `PlatformShellSidebar`).
- `ThemeProvider.tsx` — keep only if THEME-1 wires it; otherwise delete with the dead token system.
