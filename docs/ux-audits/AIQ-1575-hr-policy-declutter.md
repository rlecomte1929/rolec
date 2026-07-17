# AIQ-1575 — `/hr/policy` (Published policy tab) declutter audit

Source: Maya feedback `BUG-260717-724E` on `/hr/policy`. Scope: remove duplicate/premature
UI on the Published-policy tab; guide first-time HR without repeating the same CTA.

## Block inventory (top → bottom) and decision

The tab is rendered by three stacked files: `pages/HrPolicy.tsx` (banner) →
`features/policy/HrPolicyPageV2.tsx` (blocks 2–5) →
`features/policy/HrPolicyReviewWorkspace.tsx` + `HrPolicyWorkspaceLayout.tsx` (blocks 6–8).

| # | Block | Component / location | Decision |
|---|---|---|---|
| 1 | "Next step: This is your live, published policy…" banner | `PolicyNextStepCta` (`HrPolicy.tsx:303-350`), rendered `:184` | **BUG (flag)** — copy is hard-coded and shows even with no policy. Should vary on policy existence. Deferred. |
| 2 | "Ask about this policy" button + hint | `HrPolicyPageV2.tsx:639-657` | **DONE** — hidden until a policy is live (was visible-but-disabled). |
| 3 | Status chips + "Publish draft" | `StatusStrip` (`HrPolicyPageV2.tsx:90-160`) | Keep. |
| 4 | "Preview & compare" | `PreviewCompareSection` (`HrPolicyPageV2.tsx:176-277`) | Keep. |
| 5 | "Start your policy" (template / import) | `BuildNextVersionSection` (`HrPolicyPageV2.tsx:281-367`) | **CONSOLIDATE** — redundant with block 7 (see below). Deferred (needs decision). |
| 6 | "What this means for employees" (Choose a standard baseline / Upload) | `HrPolicyWorkspaceLayout.tsx:252-375` | **CONSOLIDATE** — its "Choose a standard baseline" button is a pure scroll-shim to block 7. Deferred. |
| 7 | "Start with a standard baseline" (Conservative/Standard/Premium) | `StarterPolicyOnboardingCard` (rendered `HrPolicyWorkspaceLayout.tsx:380-389`) | **KEEP as the single first-time entry point** (Maya's preferred block). Move higher — deferred with consolidation. |
| 8 | "Policy & version" (Select-policy dropdown + version metadata) | `HrPolicyReviewWorkspace.tsx:752-823` | **DONE (partial)** — hidden for first-time HR (empty dropdown = clutter); kept for returning HR (it holds the version switcher, metadata, and source download — deleting it outright, as literally requested, would break multi-policy switching). |

## Shipped in this PR (safe, isolated)

1. **Block 2** — "Ask about this policy" is now hidden entirely until `hasLivePolicy`
   (a published policy exists), instead of rendered greyed-out. The Q&A only answers
   from a published policy, so it's a premature control before then.
2. **Block 8** — the "Policy & version" card renders only when
   `policies.length > 0 || normalized?.version` (there is a policy/version to act on).
   First-time HR no longer see an empty "Select policy" dropdown; returning HR keep the
   switcher/metadata/download.

## Correction to Maya's premises (verified against code)

- "Ask about this policy" was **already gated** (disabled + a "Publish your policy to ask
  questions about it" hint) when no policy is live — it was visible-but-disabled, not
  ungated. Now hidden.
- "Remove the Policy & version block" — taken as *hide when empty* rather than *delete*,
  because it is functional for returning HR (version switcher + metadata + source download).

## The real duplication ("double-dipping") — DEFERRED, needs a decision

Blocks 5, 6, 7 all offer "pick a baseline / upload a policy", but **blocks 5 and 7 seed two
different backend subsystems**:

- Block 5 "Start from a template" → `policyConfigMatrixAPI.hrApplyTemplate` (the **config-matrix** / caps system).
- Block 7 "Create X baseline" → `companyPolicyAPI.initializeFromTemplate` (the **company_policies** / canonical system).
- Block 6 "Choose a standard baseline" is a scroll-shim to block 7; its "Upload" duplicates block 7's upload.

So "just delete the duplicates" is **not safe** without deciding which baseline subsystem is
canonical. Baseline/template selection also exists a **third** time in the dedicated **Policy
Builder** tab (`HrPolicyBuilderV2Page` `applyTemplate`), and block 1's banner already tells HR
to use the builder to make changes.

**Recommendation (pending owner decision):** make block 7 (`StarterPolicyOnboardingCard`) the
single first-time baseline entry point on the landing page and remove blocks 5 and 6's baseline
CTAs — but only after confirming which subsystem (`config-matrix` vs `company_policies`) is the
one new HR should seed. If the Policy Builder tab is meant to own baseline creation entirely,
the landing page should link to it rather than duplicate it a fourth time.

First-time predicate to reuse when moving block 7 up: `phase === 'no_policy' && !hasPublishedMatrix`.
