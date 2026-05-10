# ReloPass — Policy workflow (manual QA pack)

**Purpose:** Step-by-step manual checks for HR policy lifecycle and employee policy experience.  
**Audience:** Product, engineering, external testers.  
**Note:** Automated frontend tests cover core rendering and publish flow; this pack targets **end-to-end behavior**, copy, and edge cases in real environments.

**See also:** [Policy Assistant QA & red team](./policy-assistant-qa-pack.md) (bounded Q&A, jailbreak/mixed-scope, draft vs published).

**Before you start**

- Use a **dedicated test company** and named **test assignments** where possible.
- Record **environment** (URL, date, browser) on your run sheet.
- **Product rules**
  - **No policy** and **draft** are valid states — not failures by themselves.
  - Employees should see **published** entitlements and comparison tier — not HR drafts.
  - **Comparison readiness** (full / partial / informational) must be **explicit** in the UI.
- In bug reports, describe **screens and user-visible labels**; add IDs only if you have them.

---

## SECTION 1 — HR lifecycle scenarios

### 1. No policy → start from template

| | |
|---|--|
| **Setup** | Company (or program) has **no** company policy yet — HR policy workspace shows “no policy” / onboarding. |
| **Exact steps** | 1) Open HR Policy workspace. 2) Choose **start from template** (pick one standard baseline offered). 3) Wait for creation to finish. |
| **Expected result** | A company policy exists with a **draft** (or working version) derived from the template; workspace leaves “no policy” state. |
| **Verify visually** | Onboarding path visible first; after init, status badges/headlines reflect **draft / not live** (not “live for employees” until published). |
| **Verify functionally** | Template API/init completes without error; policy appears in policy list/selector; document/intake area consistent with a new baseline. |
| **Pass/Fail** | |

---

### 2. Publish starter template

| | |
|---|--|
| **Setup** | Template draft exists and workspace shows **ready to publish** (or equivalent) per ReloPass checks. |
| **Exact steps** | 1) Open **publish** (primary CTA or publish controls). 2) If shown, review **publish preflight** (current vs draft, comparison readiness). 3) **Confirm publish** once. 4) Wait for completion. |
| **Expected result** | Working version becomes **published / live**; HR sees active published policy. |
| **Verify visually** | Preflight shows **draft you are publishing** and **comparison after publish** in plain language; post-publish, **live** indicators and **replacement** messaging absent until a new draft exists. |
| **Verify functionally** | Single successful publish; workspace refresh shows **published** version; **current employee view** vs **if you publish** panels make sense (no “draft only” for live). |
| **Pass/Fail** | |

---

### 3. Upload weak policy summary while template is live

| | |
|---|--|
| **Setup** | **Published** template (or any live published policy) from scenario 2. |
| **Exact steps** | 1) Open document intake / upload. 2) Upload **weak / summary-only** test document. 3) Process / **normalize** per product flow. 4) Return to policy workspace. |
| **Expected result** | New **draft** from upload; **published template stays live**; HR sees **replacement** / “draft ahead of live” messaging. |
| **Verify visually** | Active policy (live) section still describes **current published**; uploaded draft appears as **under review / draft**; issues or blocked publish if document is incomplete. |
| **Verify functionally** | Employee-facing live policy **unchanged** until publish; no automatic switch of live version to the weak draft. |
| **Pass/Fail** | |

---

### 4. Review draft-only uploaded policy

| | |
|---|--|
| **Setup** | Uploaded draft exists (from scenario 3), **not publishable** or blocked by checklist/issues. |
| **Exact steps** | 1) Open **draft review** / detailed review / issues panel. 2) Read issues and readiness. 3) Optionally open benefit table for that draft. |
| **Expected result** | Clear list of **what blocks publish**; comparison/publish readiness badges match state (**not ready** where applicable). |
| **Verify visually** | Human-readable issues; **publish** not primary or disabled until ready; **current vs future employee** preview (if shown) does not claim draft is live. |
| **Verify functionally** | Navigating review does not change published version; saving draft status (if used) behaves as expected. |
| **Pass/Fail** | |

---

### 5. Apply HR overrides to a draft/policy

| | |
|---|--|
| **Setup** | Draft or version with **HR overrides** available (same policy as scenarios 3–4 or a fresh draft). |
| **Exact steps** | 1) Locate **HR overrides** (HR-only section). 2) Apply override (e.g. limit/cap change per test plan). 3) Save if required. 4) Observe **effective** / entitlement preview and readiness badges. |
| **Expected result** | **Effective preview** updates to reflect override; comparison readiness may change **only** if product rules say so. |
| **Verify visually** | Preview rows show baseline vs override vs effective consistently; no internal field names as primary copy. |
| **Verify functionally** | Override persists after refresh; publish (if you proceed) reflects overrides in preflight draft description. |
| **Pass/Fail** | |

---

### 6. Publish replacement policy

| | |
|---|--|
| **Setup** | Live published policy **and** a **ready-to-publish** replacement draft (improve draft until gates pass, or use prepared test data). |
| **Exact steps** | 1) Open **publish** from allowed entry point. 2) In **preflight**, confirm **current active** vs **draft being published** and **comparison today vs after publish**. 3) **Confirm publish** once. |
| **Expected result** | New version is **live**; old live version superseded in UI; replacement warning for that cycle cleared. |
| **Verify visually** | Preflight continuity message (employees see old until publish completes, if shown); post-publish **employee preview** matches new live policy. |
| **Verify functionally** | One publish request; normalized/workspace data matches **published**; no duplicate “live” conflict. |
| **Pass/Fail** | |

---

### 7. Upload another replacement policy after one is already live

| | |
|---|--|
| **Setup** | Scenario 6 complete — **one** published policy live (replacement already published once). |
| **Exact steps** | 1) Upload **another** policy document. 2) Normalize/build draft. 3) Review workspace status and messaging. |
| **Expected result** | **New draft** created; **current published remains active**; **replacement** flow messaging appears again as appropriate. |
| **Verify visually** | Same mental model as scenario 3/6: live row + draft row; badges for publish/comparison readiness on the **draft**. |
| **Verify functionally** | Employees still see **prior published** until a new publish; no silent swap. |
| **Pass/Fail** | |

---

## SECTION 2 — Employee scenarios

Use an **employee** session (or employee view) on an assignment under the test company.

### 1. No published policy

| | |
|---|--|
| **Setup** | HR side: **no** published policy for the program (no policy or draft only — align with test matrix). |
| **Steps** | Open employee policy / entitlements / services area for the assignment. |
| **Expected result** | **Neutral** messaging: policy not available or not yet published; **read-only** UI (no editing policy). |
| **What should not appear** | Published entitlement matrix as if live; **full/partial comparison** with dollar deltas implying a finalized published cap; backend error codes as user-facing text. |
| **Pass/Fail** | |

---

### 2. Published template policy

| | |
|---|--|
| **Setup** | **Published** starter/template policy live (after scenario 2). |
| **Steps** | Open employee policy/entitlements; scan benefits and any comparison UI. |
| **Expected result** | Entitlements (or benefit summary) reflect **published** template; messaging matches **comparison readiness** for that policy (informational/partial/full as applicable). |
| **What should not appear** | Wording that a **draft** is what employees see; editable policy fields; HR-only override controls. |
| **Pass/Fail** | |

---

### 3. Published policy with partial comparison readiness

| | |
|---|--|
| **Setup** | Published policy where product marks comparison as **partial** (test data / known company). |
| **Steps** | Open services or comparison surfaces; pick services with and without full numeric caps. |
| **Expected result** | **Partial** labeling; entitlements visible where designed; some lines informational only. |
| **What should not appear** | **Full** comparison label; fabricated **budget deltas** where caps/rules don’t support it; “exceeds policy” math without a defined cap. |
| **Pass/Fail** | |

---

### 4. Published policy with full comparison readiness

| | |
|---|--|
| **Setup** | Published policy with **full** comparison readiness and services with clear limits. |
| **Steps** | Compare quotes or estimates vs policy limits on covered services. |
| **Expected result** | **Within** vs **exceeds** (or product terminology) correct; **deltas** where allowed; **approval** flags when required. |
| **What should not appear** | Deltas on **excluded** or informational-only rows; inconsistent currency without explanation. |
| **Pass/Fail** | |

---

### 5. Policy replacement draft exists but is not yet live

| | |
|---|--|
| **Setup** | HR: **published** policy live **and** unpublished **replacement draft** (scenario 3/7 style). |
| **Steps** | As employee, open policy/entitlements/services. |
| **Expected result** | Employee experience matches **currently published** policy only; any messaging about “upcoming changes” is non-misleading if present. |
| **What should not appear** | Draft benefit values, draft-only overrides, or draft document title as the **live** policy; comparison based on **unpublished** draft limits. |
| **Pass/Fail** | |

---

## SECTION 3 — High-risk edge cases

Mark each **Pass / Fail / N/A** and note what you observed.

| # | Check | How to test (brief) | Pass/Fail |
|---|--------|---------------------|-----------|
| E1 | **Double publish clicks** | In preflight, rapidly click **Confirm publish** (or double-click). | Button busy/disabled; **one** publish; no duplicate live confusion. |
| E2 | **Stale draft after publish** | Publish, then immediately scan HR workspace for draft banners vs live. | UI shows **current published**; no stale “publish this draft” for already-published version without refresh glitches. |
| E3 | **Switch policy while review loading** | With multiple policies, switch selector while review/preview loading. | No mixed labels; final state consistent with selected policy. |
| E4 | **Draft must not replace live before publish** | Weak upload while live (scenario 3); check live row + employee. | Live unchanged pre-publish. |
| E5 | **Override saved but preview not refreshed** | Save override; observe effective preview without full page reload. | Preview updates; refresh matches. |
| E6 | **Comparison with missing cap** | Partial/informational service row. | No numeric delta; copy honest. |
| E7 | **Wrong messaging when only draft exists** | Employee session with draft-only company state. | No “published policy” pretense; informational/neutral only. |
| E8 | **Template live + uploaded draft coexistence** | After scenario 3/7. | HR UI shows **both** contexts clearly; employee still on live template until publish. |
| E9 | **Currency mismatch** | Quote currency ≠ policy currency in test data. | No misleading same-currency delta; explicit handling or safe fallback. |
| E10 | **Duration cap vs monetary estimate** | Policy limit in time/units vs money quote. | No bogus dollar comparison; informational or blocked as designed. |

---

## SECTION 4 — Pass/fail severity model

| Severity | Definition | Examples |
|----------|------------|----------|
| **Blocker** | Ship stopper: wrong legal/money UX, data safety, or core flow broken. | Employee sees **draft** as live; publish when **not ready**; incorrect **deltas**; blank/crash on open policy; **duplicate publish** corrupting live. |
| **Major** | Serious degradation: wrong state for many users; workaround painful or risky. | Wrong **comparison tier** label; preflight missing **current vs draft**; replacement warning missing; preview **never** updates after override; load errors with no recovery. |
| **Minor** | Incorrect but limited scope; workaround exists. | Single service mislabeled; edge viewport layout; rare race that self-heals on refresh. |
| **Cosmetic** | Visual/copy polish only; no behavior change. | Spacing, typos, icon alignment, non-critical tone. |

---

## SECTION 5 — Bug report template

Copy into your issue tracker.

```text
Title:
<Short, user-visible symptom — e.g. “Employee sees draft limits as published policy”>

Scenario:
<Section 1 # / Section 2 # / Edge case E# from this pack>

Setup:
<Test company, role HR vs employee, published vs draft state, browser>

Steps to reproduce:
1.
2.
3.

Expected:
<What this pack says should happen>

Actual:
<What happened>

Screenshot / video:
<Attach>

Request ID (if visible in UI or error):
<paste>

Policy ID / document ID / assignment ID (if known from support tools or URL):
<paste — optional, helps engineering>

Severity:
Blocker / Major / Minor / Cosmetic
```

---

## Ten highest-risk behaviors to watch

1. **Draft shown as live** to employees (entitlements or comparison).  
2. **Publish** succeeding or confirm enabled when **gates / preflight** say data incomplete.  
3. **Wrong comparison tier** (full vs partial vs informational) vs actual caps/rules.  
4. **Numeric deltas** when cap is missing, excluded, or informational-only.  
5. **Replacement draft** leaking into employee view before publish.  
6. **Preflight** missing or confusing **current vs draft** or **today vs after publish** comparison.  
7. **Double publish** or duplicate requests leaving **ambiguous live version**.  
8. **Overrides** saved but **effective / employee** preview stale.  
9. **Policy switch** during load producing **mixed** HR state.  
10. **Currency / unit mismatch** producing plausible-but-wrong savings.

---

## Related docs (optional)

- `docs/policy/published-policy-consumption-rules.md`  
- `docs/policy/comparison-readiness-and-fallback.md`  
- `docs/frontend/policy-workflow-copy-map.md`  
