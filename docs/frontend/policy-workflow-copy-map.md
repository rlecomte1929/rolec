# Policy workflow — HR & employee copy map

Operational wording used in the ReloPass frontend policy surfaces. Internal API field names are not shown to users; readiness **status** values are passed through a small label formatter when we do not have a mapped phrase.

## Scenarios → primary message

| # | Scenario | Where it appears | Intent |
|---|----------|------------------|--------|
| 1 | Draft created from uploaded document | Workspace phase `draft_not_publishable`, pipeline `normalized_partial`, draft panel | We extracted and saved a working copy; it is not live until HR publishes. |
| 2 | Document analyzed but not publishable | Same phase, readiness issues, draft review “what to fix” | Explain gaps and point to the checklist + benefit table. |
| 3 | Publishable policy ready for activation | Phase `ready_to_publish`, review banner, starter guidance | Checks passed; next step is explicit publish action. |
| 4 | Active policy published | Phase `published`, lifecycle active source, pipeline `published_*` | This is what employees see (within eligibility). |
| 5 | Template started because no company policy | `no_policy` onboarding, starter card | Offer baseline as a fast start; clarify upload remains an option. |
| 6 | Employee sees informational only | Employee panel + messages when comparison is not fully available | Benefits may show; side-by-side cost comparison is limited until limits are complete. |
| 7 | Employee sees comparison-ready policy | Employee panel “full” path, review visibility | Published policy has enough structure for automated comparison where supported. |
| 8 | Uploaded draft does not replace active policy yet | Lifecycle card, draft replacement alert, draft panel note | Published version stays live; new upload is draft until publish. |

### One-line wording anchors (for design / QA)

1. **Upload → draft:** “ReloPass turned your file into an editable draft—it is not the live employee policy yet.”
2. **Analyzed, blocked:** “Work through the checklist and benefit table; publish when this page shows ready.”
3. **Ready to activate:** “Ready to go live—publishing puts these benefits on assignments (within eligibility).”
4. **Live:** “Live for employees—this published version drives what they see today.”
5. **No policy / template path:** “Start with a standard baseline or upload your company policy; employees only see benefits after you publish.”
6. **Employee informational:** “Overview-style view—automated cost comparison waits on clearer caps.”
7. **Employee comparison on:** “Cost comparison is on—ReloPass can compare costs to published limits where supported.”
8. **Safe replacement:** “Your current published policy stays active until you publish the new draft.”

## Phase headlines (HR workspace)

| Phase | Headline | Subline (summary) |
|-------|----------|-------------------|
| `no_policy` | Get your relocation policy in place | No policy is live yet. Start from a standard baseline or upload your own file—employees only see benefits after you publish. |
| `draft_not_publishable` | Draft saved—finish review before it goes live | ReloPass pulled benefit rules from your file (or baseline). Fix the items below, then publish when the workspace says you can. |
| `ready_to_publish` | Ready to go live | This version passed ReloPass checks. Publish when you want employees to see these benefits on their assignments. |
| `published` | Live for employees | This published version drives what relocating employees see (by eligibility). You can upload a newer file or edit values anytime. |

## Pipeline banner states (HR)

| State | Title | Body (gist) |
|-------|-------|-------------|
| `workspace_empty` | No policy to work with yet | Add a policy by uploading a file or creating a baseline, then turn it into a published version. |
| `uploaded_not_normalized` | File received—still processing | Text extraction or policy build may still be running, or you have not finished “build policy from document” yet. |
| `normalized_failed` | We could not finish processing this file | Fix the file or re-run processing, then try building the policy again. |
| `normalized_partial` | Policy draft exists—not live yet | Review the benefit table and publish when checks pass. |
| `published_not_comparison_ready` | Live policy—cost comparison not fully on | Employees see benefits; comparison bars need clearer limits in a few places. |
| `published_comparison_ready` | Live policy—cost comparison available | Employees can use policy-backed comparison on supported services where limits are defined. |

## Comparison summary (published policy card)

| Key | Employee-facing meaning (HR preview copy) |
|-----|------------------------------------------|
| `full` | Cost comparison is on for services where your policy states clear dollar (or unit) limits. |
| `partial` | Some services support full comparison; others show coverage or text until limits are filled in. |
| `informational` | Employees can read benefits; automated comparison stays limited until required caps and categories exist. |

## Employee panel variants

| Variant | Role |
|---------|------|
| No policy | HR has not published yet; page explains what will appear later. |
| Under review / partial structure | Policy is published but not every limit is ready for automated comparison. |
| Partial automation | Mix of clear limits and “orientation only” rows. |
| Full | Benefits and comparisons from the published policy where limits allow. |

## Code locations

- Phase + comparison copy: `frontend/src/features/policy/hrPolicyWorkspaceState.ts`
- Readiness badge labels (publish / cost comparison API status → HR badge text): `frontend/src/features/policy/policyWorkflowCopy.ts`
- Pipeline banner: `frontend/src/features/policy/hrPolicyDegradedState.ts`, `HrPolicyPipelineBanner.tsx`
- Lifecycle: `frontend/src/features/policy/hrPolicyLifecycle.ts`
- Draft review banners & issue hints: `frontend/src/features/policy/hrPolicyReviewFormatters.ts`
- Starter onboarding: `starterPolicyCopy.ts`, `StarterPolicyOnboardingCard.tsx`, `StarterPolicyDraftGuidance.tsx`
- Employee: `employeePolicyPanelCopy.ts`, `employeePolicyMessages.ts`
