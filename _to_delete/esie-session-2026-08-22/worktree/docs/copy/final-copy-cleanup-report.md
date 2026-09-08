# Final copy cleanup report (Phase 10)

## Summary

Pass focused on **user-visible** strings in `frontend/src` (TS/TSX). Developer comments were only changed when the global punctuation pass touched them.

## Main categories of change

1. **Em dash removal**  
   All Unicode em dashes (`U+2014`) were removed from `.ts` / `.tsx` under `frontend/src`.  
   - Table and empty-value placeholders that used `'—'` now use `'-'`.  
   - Prose that used em dashes was rewritten or replaced with periods, colons, or middle dots (`·`) for separators in compact UI (e.g. impersonation banner).

2. **Mechanical cleanup after replacement**  
   Sequences like `  -  ` (artifact of em-dash substitution) were normalized to `:` or `·` via a follow-up pass.

3. **Employee hub (`EmployeeJourney.tsx`)**  
   Shorter subtitles, badges, banners, manual-claim copy, section intros, and CTAs (`Link case`, `Linking…`). Less “assistant” explanation, same rules.

4. **HR / admin shells**  
   Tighter `AdminLayout` explainer, admin page subtitles (Policies, Suppliers, People, Messages, Resources, Assignments, Ops, review queue, mobility inspect), and policy workspace published line.

5. **Services / RFQ / pickers**  
   Picker subtitles for multi-assignment flows, Providers hero line, RFQ placeholder page tightened.

6. **Readiness / case summary**  
   `ReadinessAndActionsBlock` and `HrCaseSummary` subtitles and reference note; `CaseReadinessCore` immigration disclaimers shortened.

7. **Auth / dashboard / vendor**  
   Employee register alert, Journey completion state, document checklist alert, vendor inbox empty state.

8. **Errors / loading**  
   `EmployeeAssignmentContext` overview error, `apiDetail` timeout message, Step 5 review sufficiency error.

## Patterns removed or reduced

- Long em-dash clauses in marketing-style sentences.  
- Repeated “we / you can now” framing.  
- Multi-sentence empty reassurance where one sentence + action suffices.  
- Over-explained admin subtitles (“unified operations…”) → noun phrases.

## Wording standards adopted

- **Hyphen `-`** for missing field/table cells in dense tables.  
- **Colon `:`** for label: value and some former dash constructions.  
- **Middle dot `·`** only where a tiny separator is needed in one-line UI (e.g. impersonation).  
- **Assignment / case / link / claim** kept where they match the product model.

## Still worth manual review (not fully rewritten)

- **Marketing / public pages** (`Landing`, `public/*`, `landingContent`, `platformContent`): mostly section comments; hero/body copy was not exhaustively rewritten.  
- **Backend-driven strings** returned in API `message` / `detail` fields: not in this repo pass.  
- **Supabase / email templates** outside `frontend/src`.  
- **E2E or storybook** strings if added later.

## Verification

- Grep `U+2014` in `frontend/src`: **no matches**.  
- `npx tsc --noEmit` in `frontend/` should pass after edits (run in CI).

## Wave 2 (marketing + HR + services shells)

**Marketing (max ROI):** Rewrote copy in `landing/landingContent.ts`, `public/platformContent.ts`, `public/accessContent.ts`, `public/trustContent.ts`, `public/whyReloPassContent.ts` (shorter lines, less filler, same structure).

**HR `AppShell` subtitles:** `HrDashboard`, `HrCommandCenter`, `HrCaseSummary`, `HrAssignmentReview`, `HrReviewDashboard`, `HrCaseReview`, `HrEmployees`, `HrEmployeeDetail`, `HrCompanyProfile`, `HrAssignmentPackageReview`, `HrPolicyManagement`, `HrPolicy`, `HrComplianceCheck`.

**Employee / services shells:** `ProvidersPage`, `ServicesQuestions`, `ServicesRecommendations`, `ServicesEstimate`, `ServicesRfqNew`, `ServicesConclusion`, `QuotesInbox`, `Resources` (subtitle + hero line), `Journey`, `CaseWizardPage`, `EmployeeCaseSummary`, `Messages`, `NotificationSettings`, `VendorInbox`.

## Wave 3 (Resources, HR policy list, marketing defaults)

**Resources (`Resources.tsx`):** Multi-assignment picker title/subtitle, empty states (no assignment, no destination), hero hints (“Suggested next”), section titles (“Suggested for you”, “This week (…)”), filter labels (Price / When), search placeholder, events empty + country-wide notice, overview empty line, external link CTA **Open** (including event cards).

**HR policy management (`HrPolicyManagement.tsx`):** Load/save/publish/upload errors, loading line, AppShell subtitle, list/upload CTAs, upload blurb, benefit-matrix helper, **Publish for employees**, ellipsis on **Uploading…**, back link without arrow.

**Marketing components:** `TrustBlock` (shorter trust bullets), `TrustStrip` (default eyebrow + single **Logo slots** fallback), `ProductDiagramBlock` (diagram slot label **Diagram**).

## Related docs

- [ui-text-audit-inventory.md](./ui-text-audit-inventory.md)  
- [ui-copy-style-guide.md](./ui-copy-style-guide.md)
