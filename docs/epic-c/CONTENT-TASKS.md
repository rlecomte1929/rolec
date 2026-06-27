# Epic C — CONTENT TASKS (7, all parallel-safe)

> **Before doing anything, read `docs/epic-c/SHARED.md` in full.** It has the Definition of Done, setup,
> hard rules, and fix patterns. Each task below is the SCOPE for one Conductor agent. Re-measure live at
> the start of your task (counts here are a 2026-06-27 snapshot and shift as PRs merge).

---

## TASK ENT — drain `react/no-unescaped-entities` to 0
- **Objective:** zero `react/no-unescaped-entities` across `frontend/src` (~62 occurrences, 43 files,
  heaviest in `features/platform-v2`). Pure cosmetic; rendered output is identical.
- **Method:** use the entities script in SHARED.md; loop until 0; build; fix any straggler by hand.
- **SUCCESS:**
  ```
  npx eslint src --rule '{"react/no-unescaped-entities":"error"}' --format json > /tmp/e.json 2>/dev/null
  node -e "console.log(require('/tmp/e.json').flatMap(f=>f.messages).filter(m=>m.ruleId==='react/no-unescaped-entities').length)"   # must print 0
  ```
  + SHARED Definition of Done 2–6. Commit `fix(a11y): escape JSX entities to 0 (Epic C / entities)`. **May auto-merge on green.**
- **GUARDRAIL:** only touch `' " > }` at eslint-flagged JSX-text positions (never apostrophes inside JS
  strings/attributes). Use `&quot;`/`&apos;`, not curly quotes (a test asserts straight quotes). Re-run `vitest`.

---

## TASK CLK-1 — clickable sweep: `features/platform-v2/**` (~22 elements, ~18 files)
- **Scope (re-measure; EXCLUDE the deferred `policy-builder/HrPolicyBuilderV2Page.tsx` — that is DEF-3):**
  `intake/RelocatePlanIntakePage`(3), `intake/EmployeeIntakePage`(2), `policy-reality/HrPolicyRealityPage`(2),
  `shared/index`(2), and 1 each in `admin/AdminCompanies`, `admin/AdminExceptions`, `admin/AdminUsers`,
  `admin/form-templates/PdfCoordinateMapper`, `dashboard/DashboardScreen`, `discovery/DiscoveryScreen`,
  `discovery/HrDiscoveryPage`, `dossier/OriginalPdfDrawer`, `hr-control/HRControlPanel`,
  `marketplace/MarketplaceScreen`, `mobility-control/MobilityControlCenterV2Page`, `policy/PolicyBuilder`,
  `settings/SettingsScreen`.
- **Method:** apply the SHARED fix patterns per element; ONE PR for all; spot-check rows/lists for behavior.
- **SUCCESS:** `npx eslint src/features/platform-v2 --rule '{"local/no-clickable-div":"error"}' --format json`
  → 0 violations on your files (HrPolicyBuilderV2Page may still show — it's DEF-3) + SHARED DoD 2–6.
  Commit `fix(a11y): keyboard-accessible clickable elements in platform-v2 (Epic C / T2)`. **May auto-merge.**

---

## TASK CLK-2 — clickable sweep: `pages/admin/**` + `features/admin/**` + `features/policy*/**` (~11 elements, ~9 files)
- **Scope:** `features/admin/policy-workspace/PolicyWorkspacePage`(4), `pages/admin/AdminAssignments`(3),
  `pages/admin/AdminMessages`(2 — a clickable LIST), `pages/admin/AdminSuppliers`(2 — has a `<td>`
  stopPropagation guard → use the guard pattern), `features/policy/HrPolicyReviewWorkspace`(1),
  `features/policy-config/CountryMultiSelect`(1).
- **SUCCESS:** those files' `local/no-clickable-div` = 0 + SHARED DoD. Commit
  `fix(a11y): keyboard-accessible clickable elements in admin pages (Epic C / T2)`. **May auto-merge.**

---

## TASK CLK-3 — clickable sweep: components + HR-pages tail (~9 elements, ~9 files)
- **Scope:** `components/ProviderCoordinationPanel`, `components/antigravity/Card`,
  `components/case/VendorBrowsePanel`, `features/immigration/PassportOCRFlow`, `pages/HrCommandCenter`,
  `pages/HrDashboard`, `pages/HrVendorCuration` (1 each). **`antigravity/Card` is a SHARED primitive** — fix
  once, it cascades; verify a couple of its consumers still render.
- **SUCCESS:** those files' `local/no-clickable-div` = 0 + SHARED DoD. Commit
  `fix(a11y): keyboard-accessible clickable elements in shared components + HR pages (Epic C / T2)`. **May auto-merge.**

---

## TASK DEF-1 — `features/hr/HrTeamList.tsx` (30 clickable + the last `no-autofocus`). ⚠️ BROWSER-VERIFIED — DO NOT AUTO-MERGE
- The hard one: clickable `<tr>` + **5 stopPropagation `<td>` guards** + a resize handle + 1 `autoFocus`.
- **Method:** replace the per-cell `<td>` guards with **row-level target delegation** —
  `onClick={(e)=>{ if((e.target as HTMLElement).closest('button,a,input,select,label,[role="button"]')) return; toggle(); }}`
  + `role="button"`/`tabIndex={0}`/`onKeyDown(Enter/Space)` on the row. FIRST confirm `InlineSelect`/`Checkbox`
  render real interactive DOM the selector catches. Resize handle: `role="button"` `tabIndex={-1}` + onKeyDown,
  keep its onMouseDown. Remove or justify the `autoFocus`.
- **SUCCESS:** `HrTeamList.tsx` `local/no-clickable-div` = 0 AND `jsx-a11y/no-autofocus` = 0 + SHARED DoD 2–5.
  **DO NOT AUTO-MERGE.** Open the PR; then a human (or Playwright MCP if available) MUST verify in a browser:
  keyboard expand/collapse, inline-edit, and column resize all still work, with no layout shift. Merge only after that.

---

## TASK DEF-2 — `components/AppShell.tsx` (mobile drawer). ⚠️ BROWSER-VERIFIED — DO NOT AUTO-MERGE
- aria-hidden backdrop + the drawer container's "tap-inside-closes" onClick. Move close-on-nav to the
  nav-link onClick or a route-change `useEffect`; treat the backdrop as presentational (scoped disable or
  role/tabIndex/onKeyDown). **CRITICAL NAVIGATION COMPONENT.**
- **SUCCESS:** `AppShell.tsx` `local/no-clickable-div` = 0 + SHARED DoD 2–5. **DO NOT AUTO-MERGE** — human/
  Playwright verify: mobile drawer opens/closes, nav links navigate and dismiss the drawer.

---

## TASK DEF-3 — `features/platform-v2/policy-builder/HrPolicyBuilderV2Page.tsx` (30, builder canvas). ⚠️ BROWSER-VERIFIED — DO NOT AUTO-MERGE
- Inspect each clickable element individually; apply the matching SHARED pattern.
- **SUCCESS:** that file's `local/no-clickable-div` = 0 + SHARED DoD 2–5. **DO NOT AUTO-MERGE** — human/
  Playwright verify the policy builder still works (add/edit/drag tiers, save).
