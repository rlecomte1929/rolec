# Employee Journey — UI Redesign Brief (design-input artifact)

> Generated 2026-06-11. Purpose: a backend-grounded brief that feeds the engineered design prompt.
> Each screen lists the user's goal, the **live** endpoints behind it (verified against the booted
> prod app, not the router files), the data shape, and — critically — the **prod-reality state**
> (what a real employee actually sees today, which is often the *empty* state, not the rich happy path).
>
> Design rule that falls out of this: **empty/onboarding states are the common case here, not edge
> cases.** A redesign that only renders the rich happy-path will look broken for most real users.
> Design within the existing `frontend/src/components/antigravity/` system — extend it, don't replace it.

---

## Scope

**Pass 1 — core spine (this brief):** the 5 screens a real employee walks in order.
1. Dashboard / Hub
2. Intake Wizard
3. Roadmap
4. Dossier & Forms
5. Benefits & Policy

**Pass 2 — secondary flows (listed, not detailed yet):** Immigration sub-flow (consent → passport OCR →
interview → checklist → my-data/GDPR), Task Portal, Quote Request, Rich Profile, Form Editor.

---

## 1. Dashboard / Hub — `/employee/dashboard`

- **Component:** `pages/EmployeeJourney.tsx`
- **User goal:** Land after login, claim/link my relocation assignment, see where I am.
- **Live endpoints:**
  - `GET /api/employee/assignments/overview` — linked + pending assignments
  - `GET /api/employee/assignments/current` — current assignment (client-cached 30s)
  - `POST /api/employee/assignments/{id}/claim` — claim by id + email
  - `POST /api/employee/assignments/claim-by-token` — magic-link claim
  - `POST /api/employee/assignments/{id}/link-pending` — link a pending assignment
  - `GET /api/employee/messages` — message feed
- **Prod-reality state:** Demo employees are typically `awaiting_intake` with nothing claimed yet
  (per E2E notes). **The first-run state is "no assignment claimed."** This screen's empty/claim
  state is the *primary* experience, not a fallback.
- **Antigravity in use:** Alert, Badge, Button, Card, Input, LoadingButton.
- **States today:** loading / error / empty / linked-rows. (Reasonable coverage already.)

## 2. Intake Wizard — `/employee/case/:caseId/intake`  (legacy alias `/wizard`)

- **Component:** `pages/employee/CaseWizardPage.tsx` (v2 Pathway). Legacy `CaseWizardPage` v1 still
  mounted alongside — **do not redesign the v1 flow**; target v2 only.
- **User goal:** Tell the platform my move context (household, commute, preferences) so it can build a plan.
- **Live endpoints:**
  - `GET /api/employee/assignments/{id}/intake` — last saved intake state
  - `PATCH /api/employee/assignments/{id}/intake-draft` — autosave draft
  - `POST /api/employee/assignments/{id}/intake-progress` — persist step counter
  - (legacy Q&A flow `POST /api/employee/journey/answer`, `GET .../next-question` — **legacy, ignore**)
- **Prod-reality state:** Works; autosave round-trips (B17 PASS in E2E). This is the most reliable
  data-capture surface. Strong candidate to anchor the visual language (progress, autosave affordance).
- **States today:** loading / error / step N-of-M / "draft saved" indicator.

## 3. Roadmap — `/employee/case/:caseId/roadmap`

- **Component:** `pages/employee/EmployeeCaseRoadmapPage.tsx` → platform-v2 `RoadmapScreen`
- **User goal:** See my relocation as a timeline of steps with progress + confidence.
- **Live endpoint:** `GET /api/cases/{caseId}/roadmap/tracks` — tracks → steps, doc-count chips, confidence.
- **⚠️ Prod-reality state (IMPORTANT):** the persisted `roadmap_steps`/`tracks` table is **empty —
  nothing writes it yet** (the ephemeral `derive_roadmap` builder is orphaned; materialization is
  AIQ-800). So today this screen renders its **"roadmap being set up" empty state for real cases.**
  Per-step confidence exists only on the AI/RAG roadmap path, **not** the employee feed.
  **Design the empty/"being set up" state as a first-class screen, not an afterthought.**
- **States today:** loading / error (= "being set up") / tracks.

## 4. Dossier & Forms — `/employee/case/:caseId/dossier`

- **Component:** `pages/employee/EmployeeDossierPage.tsx` (+ `CaseFormCard`)
- **User goal:** See the official forms I must complete, their status, and act on them.
- **Live endpoints:**
  - `GET /api/cases/{caseId}/forms` — list of case forms (served by `cases_read`, the live path)
  - Realtime: `useCaseFormsRealtime(caseId)` — Supabase subscription for new forms
  - Per-form (Form Editor, pass 2): `GET/PATCH /api/cases/{caseId}/forms/{formId}`, `.../fields`,
    `.../documents`, `.../submit`, `.../flag`
- **Prod-reality state:** Forms are auto-triggered by the roadmap; with the roadmap writer empty (see
  #3), the forms list is **often empty too.** Content honesty: form templates are all
  `verification_status='representative'` (none `'verified'`) → UI must show the
  **"Indicative — confirm with {authority}"** disclaimer. The one known dead bit is the roadmap-step
  label on each card.
- **States today:** loading / error / empty / tabbed (All, Action needed, Blocked, Ready, Submitted).

## 5. Benefits & Policy — `/employee/benefits` + `/employee/policy`

Two related screens; treat as one design problem (what's covered + how my picks compare).

### 5a. Compensation & Allowance Policy — `/employee/policy`
- **Component:** `pages/employee/EmployeePolicyPage.tsx` → `EmployeePolicyView` (matrix). NB
  `EmployeePolicyPanel` is **dead** — ignore it.
- **User goal:** Read what my company's policy covers for my assignment type + family status.
- **Live endpoints (the CORRECT ones):**
  - `GET /api/employee/policy/caps` — resolved caps (matrix bridge, reads `policy_config` v4) ✅ LIVE
  - `GET /api/employee/policy/applicable` — applicable policy for this employee ✅ LIVE
  - `GET /api/employee/policy-config` — employee-scoped config
- **States today:** loading / error / empty ("no published policy yet") / category blocks.

### 5b. Benefit Comparison Dashboard — `/employee/benefits`
- **Component:** `pages/employee/EmployeeBenefitComparisonPage.tsx`
- **User goal:** Compare the services I selected against my resolved policy (cap vs estimate per category).
- **Endpoint it currently calls:** `GET /api/employee/assignments/{id}/policy-service-comparison`
- **⚠️ Prod-reality state (IMPORTANT — known schism AIQ-908/AIQ-240):** that comparison endpoint reads
  the **OLD/dead** `company_policies`/`policy_versions` system, which is **empty for any company
  published via the config matrix** — i.e. **empty for real employees, not just demo data.** The live
  cap data lives at `GET /api/employee/policy/caps`. Until the config→comparison bridge (AIQ-240) lands,
  this dashboard is **structurally empty in prod.** Design the empty state honestly, and prefer wiring
  the redesign to `/api/employee/policy/caps` for the cap side.
- **Cross-cutting:** Policy Assistant FAB/docked panel (`PolicyAssistantFab`, `EmployeePolicyAssistantPanel`)
  appears across the policy surfaces — `POST /api/employee/policy-assistant/query` is **live and GREEN**
  (returns answer + citations). This is a genuinely working, differentiated feature — feature it.

---

## Cross-cutting design facts (apply to every screen)

- **Design system:** extend `frontend/src/components/antigravity/` (AppShell, Button/LoadingButton,
  Card, Input/Textarea, Alert, Badge, Container). No greenfield component library.
- **Empty-first:** Roadmap (#3), Forms (#4), Benefit Comparison (#5b) are empty in prod *today* for
  real employees. Empty/onboarding states are the default surface — design them as primary screens.
- **Content honesty:** representative (not verified) content must carry the "Indicative — confirm with
  {authority}" treatment; don't design UI that implies authoritative/verified data.
- **The working, demo-able wins to lean into:** Intake autosave (#2), Policy Assistant Q&A (live, cited),
  and the Policy caps view (#5a). Anchor the redesign's "wow" on what actually works.

---

---

## Approved design direction — "E / ReloPass Native" (2026-06-11)

Explored 5 directions for the Intake Wizard; **E is approved** as the design language for the
whole employee journey. Mockups + screenshots live in
`~/.gstack/projects/rlecomte1929-rolec/designs/intake-wizard-20260611/` (variant-E.html = wizard,
dashboard-E.html = journey home; `journey-board.html` opens both).

**Design-system principles (apply to every employee page):**
- **Navy/teal only.** Brand tokens, nothing invented: navy `#0b2b43` (structure, primary buttons,
  completed/progress fills), navy mids `#133456`/`#1f4870`, navy tints `#f0f5fa`/`#d6e4f0`, teal
  `#1f8e8b` used *sparingly* as the "current / active / in-progress" accent + links only. No purple,
  coral, or cream.
- **Single content column; never a second sidebar.** The app's foldable nav owns the left edge — a
  page-level stepper sidebar would collide with it. Put flow context in a **horizontal bar at the top**.
- **antigravity primitives.** `Card` (rounded-xl, border `#e2e8f0`, shadow-sm), navy primary button,
  Inter typography. The mock is built to port straight onto antigravity.
- **Empty-first.** Roadmap and Benefit Comparison are empty in prod today — design their empty states
  as first-class screens (the "What needs you" near-empty pattern on the dashboard is the template).
- **Clarity touches:** per-field/section helper subtext, a persistent autosave/status chip wherever
  data is captured, and content honesty ("Indicative — confirm with {authority}") on representative data.
- **Country flags:** whenever a nationality or country is shown (nationality fields, origin→destination
  corridor chips, address country, passport country), render the country's flag next to the name for a
  quick visual cue. Mocks use flag emoji (e.g. 🇮🇳 Indian, 🇮🇳 Bangalore → 🇩🇪 Berlin — see
  `immigration-confirm-E.html`); **implementation should use a flag-icon SVG library keyed on ISO 3166-1
  alpha-2** (e.g. `flag-icons`/Twemoji), not raw emoji, for consistent cross-platform rendering. Flag is
  decorative (`aria-hidden`) — the country name remains the accessible label.

**Screens & states mocked so far (all in the E language, in the designs/ dir above):**
- Spine: `dashboard-E` (journey home) · `variant-E` (intake wizard) · `services-policy-E` · `roadmap-E` (populated) · `roadmap-empty-E` (prod default).
- States: `dashboard-claim-E` (no-assignment/claim — prod-primary first run) · `services-policy-empty-E` (no policy published — prod default).
- Case sub-surfaces (use a breadcrumb, NOT the 3-phase bar): `dossier-E` (forms list) · `form-editor-E` (Anmeldung, AI-prefilled review) · `immigration-checklist-E` (EU Blue Card docs) · `rich-profile-E` (built WITH the household dedup fix — roster read-only from intake, enrichments only).
- Boards: `journey-board.html` (spine) · `states-board.html` (states + sub-surfaces).
- Not yet built: a `/employee/tasks` page (see to-do aggregator note below), Messages, mobile/responsive, then React implementation.

**To-do aggregator model (avoid a third to-do surface):** the Dashboard's "What needs you" is the
AGGREGATOR; Dossier/Forms, Tasks, and Immigration are the underlying sources it links into. Do not
build `/employee/tasks` as a standalone parallel to-do list — surface its items through the aggregator.

**The 3-phase journey model (the unifying "where am I"):**
The journey is **Intake → Services & Policy → Roadmap**. The Dashboard ("journey home") is the only
place that shows all three phases; each downstream page shows only *its* phase's context bar. This
replaces the old confusing setup where three different "step" systems competed (see findings below).
The Intake wizard's top rail is the *intake* sub-progress (phase 1), NOT a journey-wide counter.

## Double-dipping cross-check (verified in code, 2026-06-11)

| Overlap | Verdict | Action |
|---|---|---|
| Service selection: wizard "Assignment Context" step vs `/employee/quote-request` | DISTINCT | None — wizard step 4 is job/salary; services live in the Quote Request flow. |
| Budget (wizard salary input) vs `/employee/benefits` (read-only comparison) | DISTINCT | None — input vs output. |
| **Household/family: wizard Step 3 (`familyMembers`) vs Rich Profile (`EmployeeRichProfilePage`)** | **DUPLICATE** | Rich Profile (not live yet — seeded demo, TODO) must **reuse** the wizard roster and only add *enrichments* (spouse employment, kids' schooling, pets), never re-ask names/DOB. Fix before it ships. |
| **3 competing step systems: wizard 5-step rail / Dashboard 5-pill flow / Roadmap milestones** | **UX confusion** | Resolved by the 3-phase model above; the Dashboard redesign drops the 5-pill flow. |
| Progress source of truth: `assignment.intake_step` (DB) vs wizard client-computed | CONSISTENCY RISK | Decide canonical writer; wizard is the only writer of `intake_step` today. |

**Implementation note:** the *real* wizard steps are **Relocation Basics → Employee Profile →
Family Members → Assignment Context → Review** (not the friendly Move/Household/Services/Budget/Review
labels used in the mock). Align to the real sequence — or deliberately re-sequence — when building.

## Ask-once / single source of truth (hard design rule, verified 2026-06-11)

A field the user has given is **never requested again as a blank input** — it is shown pre-filled and
**confirmed**, or carried silently. Verified violation in the current backend: name, DOB, nationality,
passport number/expiry, and spouse name/DOB/nationality are each collected in **4–5 places** (intake
draft → `prefill_engine` → immigration interview `interview_questions.json` → `EmployeeProfileUpdate`),
because there are 3 parallel data inlets (intake draft, immigration "vault" `employee_immigration_profiles`,
profile update) with no reconciliation. Design pattern that fixes it (see `immigration-confirm-E.html`
and `rich-profile-E.html`): a "From your intake — please confirm" card with read-only "On file" rows +
"Confirm all", then ask ONLY the net-new fields. Backend fix needed: interview/profile must read the
canonical store and skip already-confirmed fields.

## Dynamic, requirements-driven plan (verified 2026-06-11)

The journey must get **shorter when fewer requirements apply** and longer when more do — never a rigid
fixed script. Driving inputs: nationality/EU-status, origin+destination corridor, contract type, family.
- ✅ `immigration_regime.py` already detects this: EU national + EU destination → `eu_free_movement`
  ("no work permit required", 0 lead time); domestic move → no visa; non-EU → work-permit/visa regime.
- ✅ Intake question flow is conditional (`question_engine.py` `applies_if`).
- ❌ **GAP to fix:** `roadmap_builder.derive_roadmap()` is hardcoded — it always builds the same 4 tracks
  *including "Visa & Permit"* and never reads the regime result, and `requirement_evaluation_service.py`
  doesn't gate on free-movement. So today an EU citizen would still get a visa track they don't need.
  **Backend fix: wire `immigration_regime` → `roadmap_builder` (and the requirements eval) so tracks/steps
  are added only when the regime requires them.** (`_REGIME_TASK_CODES` already exists but is unused.)
- Design proof: `roadmap-light-E.html` (EU intra-EU move = 7 steps, NO visa/immigration track, "your move
  is straightforward" callout) vs `roadmap-E.html` (non-EU = 16 steps + visa track). The Immigration
  checklist sub-surface only exists when immigration applies. (Correction: a French citizen → Germany
  needs NO EU Blue Card — free movement; only non-EU nationals get the visa track.)

## `/employee/tasks` — DECISION: no standalone page (aggregator model)

Do **not** build `/employee/tasks` as a separate to-do list. The Dashboard's "What needs you" is the
single aggregator; it pulls action items from all sources (Forms, HR-assigned tasks, Immigration docs),
each item tagged by source and linking into its source surface. This prevents a third competing to-do
surface and keeps "what do I do next" in one place. (`/employee/tasks` data still exists server-side; it
feeds the aggregator rather than its own screen.)

---

## What this brief is NOT

It does not specify visual direction (color, type, layout, motion) — that's the design prompt's job.
This is the *grounding contract*: what each screen is for, what data it can truly show, and which
states are real. Feed it to `design-shotgun` / `frontend-design` as the factual substrate.
