# UI text audit inventory (Phase 1)

Broad inventory of **meaningful** user-facing copy. **Phase 9:** items marked **Rewrite** were addressed in code where listed; a global em-dash purge and placeholder normalization covered additional admin/HR tables and pickers (see [final-copy-cleanup-report.md](./final-copy-cleanup-report.md)).

**Wave 2:** Marketing copy lives in `frontend/src/pages/landing/landingContent.ts` and `frontend/src/pages/public/*Content.ts` (fully tightened). HR and key employee/services `AppShell` subtitles were shortened in the page files listed in the final report’s Wave 2 section. Trivial repeats (e.g. generic **Save** / **Cancel** on standard forms) are omitted. Verdict: **OK** = acceptable as-is or after platform-wide punctuation pass; **Rewrite** = tightened in Phase 3–9.

**Wave 3:** `Resources.tsx` filters/empty states/CTAs; `HrPolicyManagement.tsx` list/upload/edit copy; default strings in `TrustBlock`, `TrustStrip`, `ProductDiagramBlock`. See [final-copy-cleanup-report.md](./final-copy-cleanup-report.md) Wave 3.

| Page / feature | File(s) | Sample or pattern | Type | Verdict |
|----------------|---------|-------------------|------|---------|
| Employee assignment hub | `pages/EmployeeJourney.tsx` | Manual claim instructions, Section A/B headers, status badges, reconciliation alerts | Title, helper, banner, badge | Rewrite (tone, length, em-dash removal) |
| Auth register (employee) | `pages/Auth.tsx` | HR email / case signup explainer | Alert | Rewrite |
| App shell / nav | `components/AppShell.tsx` | Admin tooltip, impersonation banner | Tooltip, status | Rewrite |
| HR case operational flow | `pages/HrCaseSummary.tsx` | Case essentials / readiness / plan subtitles, route reference note, compliance log | Subtitle, helper | Rewrite |
| Readiness core (employee/HR) | `features/readiness/CaseReadinessCore.tsx` | Immigration disclaimers, checklist labels | Warning, helper | Rewrite |
| Readiness + actions block | `features/cases/ReadinessAndActionsBlock.tsx` | Merged readiness explainer | Helper | Rewrite |
| HR dashboard | `pages/HrDashboard.tsx` | Post-create assignment alert | Alert | Rewrite |
| Services landing | `pages/ProvidersPage.tsx` | Multi-assignment picker subtitle, hero blurb, empty assignment | Subtitle, helper, empty | Rewrite |
| Services RFQ placeholder | `pages/services/ServicesRfqNew.tsx` | Loading / coming soon copy | Loading, body | Rewrite |
| Employee wizard | `pages/employee/CaseWizardPage.tsx` | Destination requirements banner | Banner | OK after punctuation |
| Step 5 review | `pages/employee/wizard/Step5ReviewCreate.tsx` | Cost estimate fallback, overview heading | Error, title | Rewrite |
| API transport errors | `utils/apiDetail.ts` | Timeout / network messages | Error | Rewrite |
| Assignment overview error | `contexts/EmployeeAssignmentContext.tsx` | Load failure message | Error | Rewrite |
| Admin layout subtitle | `pages/admin/AdminLayout.tsx` | Global admin explainer | Subtitle | Rewrite |
| Admin policies | `pages/admin/AdminPoliciesPage.tsx` | Page subtitle, how-to list | Subtitle, list | Rewrite |
| Admin suppliers / resources / companies / users / messages | Various `Admin*.tsx` | Page subtitles with long clauses | Subtitle | Rewrite |
| Internal collaboration thread | `components/admin/collaboration/InternalThreadPanel.tsx` | Closed thread note | Helper | Rewrite |
| Employee journey (legacy) | `pages/Journey.tsx` | Recommendation CTA line | Body | Rewrite |
| HR dashboard documents | `pages/Dashboard.tsx` | Core documents line | Body | Rewrite |
| Vendor inbox empty | `pages/vendor/VendorInbox.tsx` | No RFQs copy | Empty | Rewrite |
| Marketing / landing / public | `pages/Landing.tsx`, `public/*`, `landing/landingContent.ts` | Section comments only in some files; hero/body where visible | Marketing | Partial (comments dev-only; visible marketing not fully rewritten in this pass) |
| Table empty cells | Many admin + HR tables | `-` placeholder | Data | OK (standardized from em dash) |
| Policy workspace | `features/policy/HrPolicyReviewWorkspace.tsx` | Published banner, excerpt suffix | Status, inline | Minor rewrite |
| Debug / test accounts | `pages/DebugAuth.tsx`, `config/testAccounts.ts` | Labels | Dev | OK |

## Notes

- **Inventory is representative**, not exhaustive: any `AppShell title=` / `subtitle=` and `Alert` blocks are high-value follow-up targets.
- After the punctuation sweep, grep the repo for **curly apostrophes** in UI (`we’ll`, `you’re`) if you want strict ASCII in source strings.
