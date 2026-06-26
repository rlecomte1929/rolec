# AIQ-1223 — Inference-based HR-admin onboarding (research + spec)

**Status:** Spec / PR-A (research + instrumentation). Implementation lands in PR-B (1223c–e).
**Owner:** Growth / Onboarding
**Related:** `frontend/src/lib/feature-flags.tsx`, `frontend/src/perf/hrOnboardingInstrumentation.ts`, `AdminAbTestsPage`, Supabase `get-feature-flags` edge function.

---

## 1. Premise

Most B2B onboarding asks the admin a wall of setup questions before they get any
value ("How big is your company? How many moves a year? What's your policy
structure?"). ReloPass already captures most of those answers **implicitly** the
moment HR starts using the product — they fill in a company profile, open the
policy builder, create a case. AIQ-1223 proposes we **read first-session
behaviour and auto-configure the workspace** instead of front-loading a wizard.

There is **no existing HR setup wizard** today. HR lands on `HrDashboard` with a
`CasesEmptyState` and is left to discover the surfaces on their own. That makes
this a greenfield onboarding bet rather than a rewrite — we can layer inference
on top of the surfaces that already exist, behind an A/B flag, with the manual
forms staying as the fallback / control.

---

## 2. Current-state map — HR entry surfaces

| Surface | Component / route | What it writes | First-run signal today |
| --- | --- | --- | --- |
| **Dashboard** | `frontend/src/pages/HrDashboard.tsx` | — (reads `/api/hr/assignments`) | `CasesEmptyState` renders when there are zero assignments → the single clearest "brand-new workspace" signal. |
| **Company profile** | `frontend/src/features/platform-v2/company-profile/CompanyProfileV2Page.tsx` (+ shared `CompanyProfileForm`) | `companies` table via `hrAPI.saveCompanyProfile` (autosave + manual save) | Captures `size_band`, `default_destination_country`, `default_working_location`, `country`. |
| **Policy Builder** | `/hr/policy?tab=builder` → `HrPolicy.tsx` → `HrPolicyBuilderV2Page` | `policy_configs` / `policy_config_versions` / `policy_config_benefits` (config-matrix system) via `policyConfigMatrixAPI.hrPutDraft` + `hrPublish` | Opening the builder = intent to define policy; publishing = tier structure exists. |
| **Discovery** | `HrDiscoveryPage` | **MOCK data** — not yet wired to a backend | Not a reliable signal source until it is backed by real data. Excluded from v1 inference. |

Notes / gotchas baked into the design:
- The company profile uses a **shared** `CompanyProfileForm` with debounced
  autosave (1.5 s). Instrumentation fires in the HR page handler
  (`CompanyProfileV2Page.handleSave`) so it is HR-scoped and not double-counted
  from the admin editing path.
- ReloPass runs **two parallel policy systems**. The Builder writes the
  **config-matrix** system (`policy_config*`), which is the live one for HR. The
  legacy `relocation_policies` / `hr_policies` tables are orphaned — inference
  must read `policy_config_versions` + `policy_config_benefits`, not the legacy
  tables.
- HR↔company resolution goes through `hr_users` (the `profiles` path is dead for
  legacy text ids). Any backend inference engine must resolve `company_id` the
  same way the policy resolver does, or it will 400 on no-company HR.

---

## 3. The three inferred signals → source action → inference

| # | Signal | Source field / table | First-session action that reveals it | Inference |
| --- | --- | --- | --- | --- |
| 1 | **Company size** | `companies.size_band` (enum band, e.g. `51–200`) | HR saves the company profile (`company_profile_saved`) | Larger bands → more tiers + heavier volume defaults; smaller bands → single-tier scaffold. |
| 2 | **Policy tier count** | `policy_config_versions` + `policy_config_benefits` (count of distinct tiers / benefit rows) | HR opens the builder (`policy_builder_opened`) then publishes (`policy_published`, carries `tier_count`) | Number of tiers tells us how granular their policy is → seeds the tier scaffold + comparison defaults. |
| 3 | **Mobility volume** | count of `relocation_cases` for the company | HR creates the first case (`first_case_created`) | Presence + growth of cases distinguishes a one-off mover from a high-volume program → sets dashboard density + nudges. |

All three signals are **observable from instrumentation we ship in this PR**
(1223b) before any inference engine is built, so we can validate that the signals
actually fire in real sessions before investing in PR-B.

---

## 4. Auto-config rules (deterministic-first)

The inference engine maps signals → a **proposed** workspace config. Rules are
deterministic table lookups wherever possible (no model needed); the proposal is
always **suggested, never silently applied** — HR sees and can override it.

| Inputs | Proposed config |
| --- | --- |
| `size_band ∈ {1–10, 11–50}` | Single policy tier ("All employees"); compact dashboard; skip volume nudges. |
| `size_band ∈ {51–200, 201–500}` | Two-tier scaffold (Standard / Senior); default destination pre-filled from `companies.default_destination_country`. |
| `size_band ∈ {501–1000, 1001–5000, 5000+}` | Three-tier scaffold (Standard / Senior / Executive); enable bulk-assign affordances. |
| `default_destination_country` set | Pre-select it as the case destination default and seed supplier/resource recs. |
| `default_working_location` set | Inject into the policy evaluation engine default. |
| `tier_count` observed at publish | Reconcile the scaffold to the real published tier count (real data wins over the size-band guess). |
| `relocation_cases` count `> 0` | Switch dashboard from empty-state to active-program layout; surface staleness/alerts. |

Determinism note: size-band → tier-scaffold and destination pre-fill are pure
lookups. The only "soft" step is initial tier-count *before* a publish exists,
which is a guess from size_band that gets overwritten by the real `tier_count`
the moment HR publishes.

---

## 5. Manual fallback (always reachable)

Inference is **additive**. The existing manual surfaces stay fully reachable and
authoritative:
- `CompanyProfileV2Page` (company profile form) — unchanged.
- `/hr/policy?tab=builder` (Policy Builder) — unchanged.
- Every auto-proposed value is editable in those same forms. A proposed config
  is a pre-fill, not a lock. The **control** arm of the A/B test *is* the manual
  experience, so the fallback is literally what 50% of users get.

---

## 6. A/B plan — reuse the existing flag framework

Reuse `frontend/src/lib/feature-flags.tsx` as-is. No new framework.

- **Flag:** `hr_inference_onboarding`, registered via the Supabase
  `get-feature-flags` edge function and managed in `AdminAbTestsPage`.
- **Resolution:** `useVariant('hr_inference_onboarding')` in the HR shell.
  - `control` → today's manual experience (empty-state + forms).
  - `variant` (`inferred`) → inference engine proposes config from the signals.
- Bucketing is deterministic (SHA-256 `hashUserBucket(userId, flagName)` against
  `traffic_split`), so an HR user's arm is stable across sessions — essential for
  an onboarding experiment that spans more than one visit.
- Safe by construction: any error / missing flag / disabled flag →
  `control`, i.e. the manual experience.

**Activation metric.** Primary: *time-to-first-published-policy* (signup →
`hr_onboarding.policy_published`). Secondary: *first-session activation rate* =
share of new HR workspaces that reach all three signals
(`company_profile_saved` ∧ `policy_published` ∧ `first_case_created`) within the
first session. Both are computed in PostHog from the events shipped in 1223b,
split by the `hr_inference_onboarding` variant property. Guardrail: company
profile / policy edit rate must not spike in the variant (would mean the
inference is wrong and HR is correcting it).

---

## 7. Build breakdown — follow-up PR-B

| Sub-task | What it does | Key files |
| --- | --- | --- |
| **1223c — inference engine** | Backend/service that reads the three signals for a company and returns a proposed config (deterministic rules from §4). Resolves `company_id` via `hr_users`; reads `companies.size_band`, `policy_config_versions`/`policy_config_benefits`, `relocation_cases` count. | new `backend/app/services/hr_onboarding_inference.py` (+ router registered in **both** `backend/app/main.py` and `backend/main.py` per CLAUDE.md), reads existing policy/company tables. |
| **1223d — UI** | HR-facing "Suggested setup" surface that renders the proposed config as editable pre-fills on the dashboard / company profile / builder; every value remains overrideable. Empty-state replaced by an inference-driven first-run panel. | `HrDashboard.tsx` (`CasesEmptyState` → inferred first-run panel), `CompanyProfileV2Page`, `HrPolicyBuilderV2Page`. |
| **1223e — A/B wiring** | Register `hr_inference_onboarding` in `get-feature-flags`; gate 1223d behind `useVariant`; attach the variant as a PostHog super-property so all 1223b events are split by arm; wire activation-metric dashboards. | `feature-flags.tsx` (consume), `AdminAbTestsPage` (manage), `analytics.ts` (register super-property), Supabase `get-feature-flags`. |

Dependency order: 1223b (this PR, instrumentation) → 1223c (engine) → 1223d (UI)
→ 1223e (A/B). 1223b can ship and gather baseline signal data before the engine
exists, de-risking the rest.

---

## 8. Instrumentation shipped in this PR (1223b)

Event constants live in `frontend/src/perf/hrOnboardingInstrumentation.ts`
(`HR_ONBOARDING_EVENTS`), mirroring `assignmentLinkingInstrumentation.ts`. They
fire through `track()` (`analytics.ts`), a no-op without `VITE_POSTHOG_KEY`.

| Event | Fired at | Props (PII-free) |
| --- | --- | --- |
| `hr_onboarding.company_profile_saved` | `CompanyProfileV2Page.handleSave` (after a successful save) | `has_size_band`, `has_default_destination_country`, `has_default_working_location`, `size_band` (enum band) |
| `hr_onboarding.policy_builder_opened` | `HrPolicy.tsx` effect when `?tab=builder` becomes active | — |
| `hr_onboarding.policy_published` | `HrPolicyBuilderV2Page.handlePublish` (after publish succeeds) | `tier_count`, `benefit_row_count` |
| `hr_onboarding.first_case_created` | `HrDashboard.handleAssign` (only when there were zero prior assignments) | `prior_case_count` |

**Privacy:** no names, emails, addresses, or free text in any property — counts,
booleans, ids, and coarse enum bands only, per the GDPR data-minimisation rule
in CLAUDE.md.
