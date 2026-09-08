# P9 Policy Consolidation Spec

**Task:** AIQ P9-1 — Audit Policy + Policy Builder pages; produce consolidation spec  
**Date:** 2026-05-26  
**Author:** Claude Cowork (notion-task-executor)  
**Status:** Spec complete — ready for P9-2 implementation

---

## 1. Current State

### Navigation (PlatformShellSidebar.tsx, lines 70–80)

The HR Operations sidebar currently exposes two separate entries pointing at the same general domain:

| Sidebar item ID | Label | Route | Notes |
|---|---|---|---|
| `requirements-discovery` | Requirements | `/hr/policy` | LIVE badge — separate feature, do NOT touch |
| `policy-builder` | Policy builder | `/hr/settings/policy` | Standalone page, full AppShell |
| `policy-benefits` | Mobility policy | `/hr/policy` | Same route as Requirements — confusing duplication |

Result: two items resolve to the same URL (`/hr/policy`), and "Policy builder" silently lives under `/hr/settings/policy` with no visual relationship to "Mobility policy". Users clicking around see three entries where the mental model is two: requirements discovery and policy management.

### Page inventory

**`HrPolicy.tsx`** (`/hr/policy`)  
- Branches on user role (`HR` vs `EMPLOYEE`).  
- HR branch: renders `<AppShell section="HR Operations" title="Mobility policy">` wrapping `<HrPolicyPageV2>`.  
- `useSearchParams` already imported and active (reads `adminCompanyId`).  
- No tab logic yet — entire HR branch is a single view.

**`HrPolicyBuilderV2Page.tsx`** (`/hr/settings/policy`)  
- Standalone page with its own `<AppShell wide>` wrapper.  
- Contains: `<Breadcrumb section="HR Operations" title="Policy builder" />`, sticky header with `<h1>Policy Builder</h1>`, mode tabs (template / document), currency selector, Save draft / Preview / Publish buttons.  
- Self-contained — nothing in `HrPolicy.tsx` is aware of it.

**`App.tsx`** (routing)  
- Line 269: `<Route path={ROUTE_DEFS.hrPolicyBuilder.path} element={<HrPolicyBuilder />} />`  
- Lines 305–306: existing `<Navigate>` pattern for route aliasing already in place.

---

## 2. Approach Decision

### Options considered

| Option | Description | Verdict |
|---|---|---|
| **A — Tabs** | Merge both pages into `/hr/policy` with `?tab=policy` (default) and `?tab=builder`. Redirect old builder route. | **Chosen** |
| B — Sub-nav | Add a second level of sidebar items under a "Policy" parent. | Rejected — over-engineering; two items don't warrant a sub-nav. |
| C — Inline | Replace the builder modal/page with an inline section below the policy view. | Rejected — builder is complex (mode tabs, currency, publish workflow); embedding inline collapses two different workflows into a single scroll. |

### Why tabs

- `HrPolicy.tsx` already imports `useSearchParams` — adding a `tab` param is two lines.
- App.tsx has precedent for `<Navigate replace>` aliasing (lines 305–306). The pattern is established.
- The Stripe/Linear brand register (our reference bar) uses tabs for same-feature/different-mode UX (e.g., Stripe Dashboard: Overview / Activity; Linear: Issues / Cycles / Backlog). Policy view vs. policy builder is exactly that pattern.
- Sidebar goes from 3 ambiguous items to 1 clean "Policy" entry. Cognitive load reduction is significant.

---

## 3. Routing Plan

### After P9-2 is deployed

| URL | Behaviour |
|---|---|
| `/hr/policy` | Renders `HrPolicy.tsx` HR branch with active tab = `policy` (default) |
| `/hr/policy?tab=policy` | Same as above (explicit) |
| `/hr/policy?tab=builder` | Renders `HrPolicy.tsx` HR branch with active tab = `builder` |
| `/hr/settings/policy` | `<Navigate to="/hr/policy?tab=builder" replace />` — old builder URL redirects cleanly |

### Tab state wiring (HrPolicy.tsx)

```tsx
// Add after existing searchParams destructure (line 60 area)
const activeTab = (searchParams.get('tab') ?? 'policy') as 'policy' | 'builder';

const setTab = (tab: 'policy' | 'builder') => {
  const next = new URLSearchParams(searchParams);
  next.set('tab', tab);
  setSearchParams(next, { replace: true });
};
```

Tab switcher UI sits inside the AppShell, above the current `<HrPolicyPageV2>` render. When `activeTab === 'builder'`, render `<HrPolicyBuilderV2Content>` (the extracted inner content of `HrPolicyBuilderV2Page`, without the AppShell wrapper — see §5).

---

## 4. Sidebar Diff

File: `frontend/src/components/PlatformShellSidebar.tsx`

### Before (lines 78–80, approximate)

```ts
{ id: 'policy-builder',  label: 'Policy builder',  to: ROUTE_DEFS.hrPolicyBuilder.path },
{ id: 'policy-benefits', label: 'Mobility policy',  to: ROUTE_DEFS.hrPolicy.path },
```

### After

```ts
{ id: 'policy-benefits', label: 'Policy', to: ROUTE_DEFS.hrPolicy.path },
```

Changes:
- **Delete** the `policy-builder` entry entirely.
- **Rename** `policy-benefits` label from `'Mobility policy'` to `'Policy'`.
- Leave `id: 'policy-benefits'` unchanged (avoids churn in any analytics keyed on sidebar item IDs).
- **Do not touch** `requirements-discovery` (Requirements, LIVE badge) — that is a separate feature.

---

## 5. File + Line Change List for P9-2

### File 1: `frontend/src/App.tsx`

**Line 269** — replace the standalone builder route with a redirect:

```tsx
// Before
<Route path={ROUTE_DEFS.hrPolicyBuilder.path} element={<HrPolicyBuilder />} />

// After
<Route
  path={ROUTE_DEFS.hrPolicyBuilder.path}
  element={<Navigate to={`${ROUTE_DEFS.hrPolicy.path}?tab=builder`} replace />}
/>
```

Remove the `HrPolicyBuilder` lazy import (search for `HrPolicyBuilder` in the lazy-import block near the top of App.tsx) once it is no longer used as a route element. If `HrPolicyBuilderV2Page` is imported elsewhere, keep the import — only remove the lazy route import.

---

### File 2: `frontend/src/components/PlatformShellSidebar.tsx`

Apply the sidebar diff from §4.

---

### File 3: `frontend/src/pages/HrPolicy.tsx`

Add tab state and switcher to the HR branch:

1. After the `adminCompanyId` line (~line 60), add:
   ```tsx
   const activeTab = (searchParams.get('tab') ?? 'policy') as 'policy' | 'builder';
   const setTab = (tab: 'policy' | 'builder') => {
     const next = new URLSearchParams(searchParams);
     next.set('tab', tab);
     setSearchParams(next, { replace: true });
   };
   ```

2. Inside the HR branch `<AppShell>` render, add a tab switcher bar above `<HrPolicyPageV2>`:
   ```tsx
   <div className="flex gap-1 mb-4 border-b border-slate-200">
     <TabButton active={activeTab === 'policy'} onClick={() => setTab('policy')}>
       Policy
     </TabButton>
     <TabButton active={activeTab === 'builder'} onClick={() => setTab('builder')}>
       Builder
     </TabButton>
   </div>

   {activeTab === 'policy' && <HrPolicyPageV2 adminCompanyId={adminCompanyId ?? undefined} />}
   {activeTab === 'builder' && <HrPolicyBuilderEmbedded />}
   ```

3. Add a local `TabButton` primitive (or reuse an existing one if present in antigravity):
   ```tsx
   function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
     return (
       <button
         type="button"
         onClick={onClick}
         className={[
           'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
           active
             ? 'border-indigo-600 text-indigo-700'
             : 'border-transparent text-slate-500 hover:text-slate-700',
         ].join(' ')}
       >
         {children}
       </button>
     );
   }
   ```

---

### File 4: `frontend/src/features/platform-v2/policy-builder/HrPolicyBuilderV2Page.tsx`

**Critical constraint: AppShell suppression.**

`HrPolicyBuilderV2Page` currently starts its render with `<AppShell wide>`. When it is embedded as a tab inside `HrPolicy.tsx` (which already has its own `<AppShell>`), nesting two AppShells will break layout.

**Approach:** Extract the inner content into a sibling component and export it.

```tsx
// Add at the bottom of HrPolicyBuilderV2Page.tsx (or as a separate file)

/**
 * HrPolicyBuilderEmbedded — the Policy Builder page content without its own
 * AppShell wrapper. Used when the builder is embedded as a tab inside another
 * AppShell page (e.g., HrPolicy.tsx). The outer AppShell is provided by the
 * host page.
 */
export function HrPolicyBuilderEmbedded() {
  // Same hooks and logic as HrPolicyBuilderV2Page — either duplicate the
  // relevant state/handlers or extract a shared hook (useHrPolicyBuilder)
  // that both the standalone page and the embedded version can use.
  //
  // The render return is everything currently inside <AppShell wide>...</AppShell>
  // in HrPolicyBuilderV2Page, minus the AppShell and Breadcrumb wrappers.
  // The sticky header, mode tabs, currency selector, and action buttons are
  // all retained.
  return (
    <div>
      {/* Contents of HrPolicyBuilderV2Page minus <AppShell> and <Breadcrumb> */}
    </div>
  );
}
```

The simplest extraction path: move all state declarations and event handlers into a `useHrPolicyBuilder()` hook co-located in the same file or in `hooks/useHrPolicyBuilder.ts`. Both `HrPolicyBuilderV2Page` and `HrPolicyBuilderEmbedded` call the hook and render the same JSX — the only difference is whether `<AppShell>` and `<Breadcrumb>` are present.

The standalone `/hr/settings/policy` route now redirects (App.tsx change above), so `HrPolicyBuilderV2Page` as a standalone entry point is no longer needed — but keep the component in place until the redirect has been verified in production (it can be deleted in a later cleanup PR).

---

## 6. Acceptance Tests

Perform these steps in the browser after P9-2 is deployed to staging:

1. **Default route renders policy tab**  
   Navigate to `/hr/policy`. Confirm the "Policy" tab is active (indigo underline), `<HrPolicyPageV2>` renders, no double AppShell / double sidebar.

2. **Builder tab renders builder content**  
   On `/hr/policy`, click "Builder". Confirm URL updates to `/hr/policy?tab=builder`, the builder sticky header appears, mode tabs (template / document) are visible, currency selector is present. No duplicate AppShell / sidebar.

3. **Old builder URL redirects**  
   Navigate directly to `/hr/settings/policy`. Confirm the browser redirects to `/hr/policy?tab=builder` and renders the builder tab.

4. **Back button works correctly**  
   From `/hr/policy?tab=builder`, press Back. Should return to the previous history entry (not loop between tabs), because `setSearchParams` uses `replace: true`.

5. **Sidebar shows one Policy entry**  
   Confirm sidebar HR Operations section shows: Requirements (LIVE badge), Policy — and does NOT show "Policy builder" or "Mobility policy" as separate items.

6. **Requirements link unchanged**  
   Click "Requirements" in sidebar. Confirm it still navigates to `/hr/policy` (policy tab default) and loads requirements discovery content correctly — the LIVE badge is present.

7. **TypeScript check passes**  
   Run `cd frontend && ./node_modules/.bin/tsc --noEmit`. Zero errors.

8. **No broken imports**  
   The lazy import for `HrPolicyBuilder` in `App.tsx` must be removed or remain used. Confirm no "imported but never used" TypeScript error and no dead import warnings.

---

## 7. Known Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Double AppShell nesting breaks layout | Extract `HrPolicyBuilderEmbedded` per §5 File 4 — tested in acceptance step 2. |
| `useSearchParams` setter with `replace: true` breaks browser history | Deliberate: tab switches shouldn't stack history entries. Deep-link to `/hr/policy?tab=builder` from elsewhere (e.g., sidebar or email) still works as a normal history entry. |
| Supabase RLS on builder API calls — builder may call routes that check for `hrPolicyBuilder` role guard | `ROUTE_DEFS.hrPolicyBuilder.roles = ['HR', 'ADMIN']`. The `/hr/policy` route has the same roles. No RLS change needed. |
| Analytics keyed on the removed sidebar item ID `policy-builder` | Sidebar item deletion is acceptable; any events on `policy-builder` naturally stop. The `policy-benefits` id is retained so existing analytics on that item are unaffected. |
