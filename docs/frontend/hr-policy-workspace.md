# HR Policy workspace (frontend)

## Page flow (top → bottom)

HR-facing policy work is **one vertical story**:

1. **Documents & processing** (`HrPolicy.tsx` — `PolicyDocumentIntakeSection`) — upload, reprocess, build policy from file.
2. **Policy status at a glance** (`HrPolicyWorkspaceLayout`) — live vs draft vs employee comparison + **one primary CTA** (`deriveHrPolicyPrimaryAction`).
3. **Employee view: today vs if you publish** — side-by-side panels inside the status card (`data-testid` `hr-policy-employee-compare`): **Current employee view** (published policy + `published_comparison_readiness` only) vs **If you publish this draft** (working version + effective preview rows + `policy_readiness.comparison_readiness`). The future panel is hidden when there is no draft path; when `no_policy`, the whole block is omitted (parent passes `employeePreviewCompare: null`).
4. **Starter onboarding** (only `no_policy`) — `#hr-policy-starter-onboarding`.
5. **Active policy (live)** — published title, version, cost comparison tier.
6. **Working / replacement draft** — `#hr-policy-draft-panel` (compact; full detail in draft review).
7. **Replacement warning** — `Alert` when `hasUnpublishedDraftAhead && lifecycle.draftReplacement` (`data-testid` `hr-policy-replacement-warning`).
8. **More actions** — secondary outline buttons only.
9. **Detailed review** — `#hr-policy-detailed-review` → `HrPolicyDraftReviewPanel` (`#hr-policy-draft-review`).
10. **HR overrides** — `HrBenefitOverrideSection` (`#hr-policy-hr-overrides`).
11. **Benefit table & publish** — selector, matrix `#hr-policy-benefit-matrix`, publish controls. **Publish** opens **`PublishPreflightModal`** (preflight copy, then **Confirm publish** / **Cancel**). Parent (`HrPolicyReviewWorkspace`) runs `publishLatestVersion`, refreshes normalized with readiness, bumps review refresh, and closes the modal on success.

## Component ownership

| Concern | Owner |
|---------|--------|
| Phase + `hasUnpublishedDraftAhead` + issue merge | `resolveHrPolicyWorkspaceState` in `hrPolicyWorkspaceState.ts` |
| Primary CTA per phase | `deriveHrPolicyPrimaryAction` in `hrPolicyWorkspaceState.ts` |
| Live / draft / employee comparison copy in grid | `HrPolicyWorkspaceLayout` (uses `deriveHrPolicyLifecycleContext` for rules + replacement alert body) |
| Side-by-side employee today vs publish | `buildEmployeePreviewCompare` (`hrPolicyEmployeePreviewCompare.ts`) + `HrPolicyWorkspaceLayout` |
| Publish preflight | `PublishPreflightModal.tsx`; opened via `onRequestPublishPreflight` from layout / starter / bottom publish control |
| Replacement draft emphasis | Single `Alert` in layout when `hasUnpublishedDraftAhead && lifecycle.draftReplacement` |
| Document summary, readiness, publishable rules, employee visibility preview rows | `HrPolicyDraftReviewPanel` |
| Benefit edits, publish | `HrPolicyReviewWorkspace` |
| Pipeline / degraded states | `HrPolicyPipelineBanner` + `deriveHrPolicyPipelineState` |

## Resolver precedence

Documented in the module comment above `resolveHrPolicyWorkspaceState` in `hrPolicyWorkspaceState.ts`:

1. `no_policy` if no company policies.
2. `published` if `published_version` is published (even when a newer draft exists → then `hasUnpublishedDraftAhead`).
3. `ready_to_publish` if publish readiness is `ready` and latest version is not published.
4. Else `draft_not_publishable`.

**Note:** `ready_to_publish` does **not** require comparison readiness to be full; comparison affects employee UX copy, not phase.

## Primary CTA mapping

| `deriveHrPolicyPrimaryAction` | Button |
|------------------------------|--------|
| `start_baseline_or_upload` | Choose a standard baseline → scroll `#hr-policy-starter-onboarding` |
| `review_draft` | Review draft → benefit matrix |
| `publish` | Publish policy → opens preflight modal (confirm runs publish in parent) |
| `review_replacement_draft` | Review new draft → `#hr-policy-draft-panel` |
| `adjust_values` | Adjust policy values → benefit matrix |

## APIs used (existing contracts)

- `GET /api/company-policies` — policy list  
- `GET /api/hr/policy-documents` — uploads  
- `GET /api/company-policies/{id}/normalized?include_readiness=true` — matrix + `policy_readiness` + published comparison readiness  
- `GET /api/hr/policy-review?policy_id=…&document_id=…` — aggregate draft, issues, `entitlement_effective_preview`, `draft_rule_candidates`  
- `POST /api/hr/company-policy/initialize-from-template` — standard baseline (empty company only)  
- Publish / patch flows unchanged in review workspace  

Client: `companyPolicyAPI.initializeFromTemplate`, `hrPolicyReviewAPI.get` in `frontend/src/api/client.ts`.

## UX copy source of truth

- Phase headlines / sublines: `HR_POLICY_WORKSPACE_COPY` in `hrPolicyWorkspaceState.ts`  
- Comparison explainer: `COMPARISON_SUMMARY_COPY` + published comparison blockers (sanitized for display)  
- Readiness badges (publish / cost comparison API status → HR wording): `policyWorkflowCopy.ts`  
- Pipeline banner (secondary): `HR_POLICY_PIPELINE_COPY` in `hrPolicyDegradedState.ts`  
- Scenario map (HR + employee): `docs/frontend/policy-workflow-copy-map.md`  

## Scroll targets

- `#hr-policy-document-intake` — document upload / build from file (`HrPolicy.tsx`)  
- `#hr-policy-starter-onboarding` — standard baseline card (`HrPolicyWorkspaceLayout`)  
- `#hr-policy-draft-panel` — compact draft summary (`HrPolicyWorkspaceLayout`)  
- `#hr-policy-draft-review` — full draft review (`HrPolicyDraftReviewPanel`)  
- `hr-policy-employee-compare` / `hr-policy-panel-current-employee` / `hr-policy-panel-if-publish` — side-by-side employee preview in status card  
- `#hr-policy-hr-overrides` — override editor (`HrBenefitOverrideSection`)  
- `#hr-policy-benefit-matrix` — benefit matrix (`HrPolicyReviewWorkspace`)  
- `#hr-policy-detailed-review` — section heading before draft review panel  

## Removed / unused

- **`HrPolicyOverview.tsx`** — removed; was not referenced. Entry is document intake + `HrPolicyReviewWorkspace` only.  
- **`NormalizedPolicySectionLegacy`** — removed from `HrPolicy.tsx`; superseded by the review workspace.
