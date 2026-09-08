# ReloPass Case Command v2 — Phase 2 PLAN (Model A), 2026-08-22

Follows the approved Phase 1 reconciliation. **Decision locked: Model A** — the shipped
`rule-engine.ts` feasibility calculator + `CorridorCheck.tsx`, **no** obligations engine / DAG /
`case_obligations` renderer is built. Outbound delivery: **pattern (a)** — I produce reviewed
patches + passing tests; Otto (or the in-space Cursor agent) lands them in the live Audos space;
`[audos-sync]` mirrors them back. Persistence: **Spend → the provisioned `case_spend` table via an
Otto hook; Review → a `review_status` flag** on the case row. Still no code — this is the plan, and
it ends at a STOP.

## What Model A already satisfies (no packet — do not rebuild)

| v2 Gap | Status in Model A | Evidence |
|---|---|---|
| **Gap 3** — retrospective + `nothing_to_do` | **DONE** | `red` = "Window passed" for wholly-elapsed windows; `confirmed`/`confirmedClear` positive, counted separately; past anchors first-class (`rule-engine.ts:113-118, 831-835`; `CorridorCheck.tsx:116-117`; NO→FR tests). |
| **Gap 4** — `employer_absent` | **DONE** | `Owner` includes `'Employer (not engaged)'`, authored on `b2-urssaf`/`b3-PE`, tested not-moved-to-employee (`rule-engine.ts:23, 693, 704`; `rule-engine.norway-france.test.ts:79-86`). |

Model-A translation of the v2 vocabulary (used throughout below): "obligation" → roadmap
**requirement**; "`case_obligations` id" → requirement `id`; "`red_late`" → `red` "Window passed";
"`nothing_to_do`" → `confirmed`; "DAG Waiting-on" → the existing free-text `dependencyNote`
(Model A has no computed blocking DAG — that is a Model-B construct and is out of scope).

## The case anchor (shared by W3 + W4)

The real per-case row in Model A is created by **`CaseGate`** and read back via the **`case-access`
server hook** (`CorridorCheck.tsx:216`, `POST /api/workspaces/{space}/hooks/case-access/execute`,
numeric `caseId`, tied to the Stripe unlock and the verified `__spaceSessionId`). Spend and Review
attach to **that** `caseId` — the same `cases` table whose `review_status`/`case_spend` columns are
provisioned. No new case abstraction is invented.

---

## Work packets

Ordered so dependencies come first. W3 and W4 are independent of each other (either order).
Every packet lands via pattern (a). "Gate: vitest" = the case-command harness must stay green;
these are Audos-space TS files, so the repo's Python/migration/serving/PII gates do **not** apply
(none of these packets touch `backend/`, `frontend/`, or `supabase/`).

### W1 — Determinism verification harness (Gap 7) · depends on: none · **do first**

- **Closes:** Gap 7 AC1-3, tests T7.1/T7.2/T7.3.
- **What:** extend the existing vitest suite with a 10×-run byte-stability assertion across all three
  corridors × employee types, pinned to a committed golden. Locks determinism *before* any change.
- **Files (1):** `apps/case-command/rule-engine.determinism.test.ts` (new) — reason: isolate the
  10×/golden harness from the per-corridor behaviour suites.
- **Tests:** T7.1 FR→NO 10 runs identical (6-obligation claim reinterpreted: assert the real authored
  count, stable); T7.2 NO→FR 10 runs identical, includes a `red`, a `confirmed`, an
  `Employer (not engaged)`; T7.3 perturb one input → output changes and is stable across 10 runs.
- **Gate:** vitest green (currently 37 tests; this adds ~3-5).
- **Blast radius:** test-only — cannot affect the running app; a reviewer sees a failing test if the
  engine is not actually deterministic.
- **Otto dependency:** none. Pure test file — could even be verified in the cloud harness before it
  lands. Zero-risk first step.

### W2 — NO→FR acceptance verification (Gap 1) · depends on: W1

- **Closes:** Gap 1 AC1/AC3 (satisfied), and *documents* AC2/AC4 as Model-B constructs represented in
  Model A by `dependencyNote` (not a blocking DAG).
- **What:** no engine/UI code. Add assertions that NO→FR covers all four phases (exit / employment /
  establishment / customs) and that the Phase-D customs items (`d1`/`d2`) carry a `dependencyNote`
  pointing at the Phase-A exit-evidence item (`a10`). Confirm the corridor renders in `CorridorCheck`.
- **Files (1):** extend `apps/case-command/rule-engine.norway-france.test.ts`.
- **Tests:** phase-coverage assertion; customs→exit `dependencyNote` linkage assertion.
- **Gate:** vitest green.
- **Blast radius:** test-only.
- **Otto dependency:** none for code. **Flag (not a code task):** the NO→FR content is an *authoring
  draft* — counsel assurance is a **separate gate** and blocks sellability; W2 does not clear it.

### W3 — Estimate Review (Gap 5) · depends on: W1 + Otto review hook · independent of W4

- **Closes:** Gap 5 AC1-3, tests T5.1/T5.2/T5.3.
- **What:** a Review view in Case Command that presents the active case's `runCaseCheck` roadmap as a
  reviewable estimate (reusing `FullRoadmap` rendering: feasibility, non-obvious flags,
  responsible-party split incl. `Employer (not engaged)`, `confirmed` positives, the milestone price
  reference from `lib/pricing.ts`) + a `review_status` (`draft`|`reviewed`) persisted on the case row.
  Reads exclusively from the case inputs + engine output — no duplicate estimate store.
- **Files (~2-3):** new `apps/case-command/EstimateReview.tsx`; wire a view into `App.tsx` (or a tab in
  `CorridorCheck.tsx`); a thin client call to the review hook. Reuse `FullRoadmap` (do not fork it).
- **Tests:** T5.1 review lists all requirements + `review_status=draft`; T5.2 confirm → `reviewed`,
  roadmap unchanged (determinism untouched); T5.3 a case with a `red` and a `confirmed` shows both.
- **Gate:** vitest green; visual check against `--space-*` tokens (no new palette).
- **Blast radius:** additive view; risk is only if it re-computes/mutates the roadmap — tests guard
  that it does not.
- **Otto dependency:** a hook action to **get/set `cases.review_status` for a caseId** — extend
  `case-access` or a small `case-review` action. I deliver the exact contract; Otto implements +
  enables. Execution also needs the current `case-access` hook schema + `CaseGate.tsx` (read at W3
  start).

### W4 — Spend tracking (Gap 2) · depends on: W1 + Otto spend hook · independent of W3

- **Closes:** Gap 2 AC1-3, tests T2.1/T2.2/T2.3.
- **What:** a Spend surface in Case Command — add/list spend for the active case (`amount`, `currency`
  EUR/NOK, `category`, `incurred_on`, `responsible_party`, `note`, optional link to a roadmap
  requirement id), **per-currency** totals (no FX conversion invented), read-only rollup. Zero coupling
  to engine determinism — spend never alters feasibility/dates.
- **Files (~2-3):** new `apps/case-command/SpendTab.tsx`; wire into `App.tsx`/`CorridorCheck.tsx`; a thin
  hook client.
- **Tests:** T2.1 spend linked to case → rollup; T2.2 spend linked to a requirement id → under it +
  rollup; T2.3 mixed EUR+NOK → per-currency totals, never summed across currencies.
- **Gate:** vitest green; `--space-*` tokens.
- **Blast radius:** additive; the determinism-isolation is the thing a reviewer checks.
- **Otto dependency:** a **new `case-spend` server hook** (create + list spend for a caseId), authored
  and enabled by Otto. I deliver the contract (actions, payloads, responses). **Open design point
  prompt #6 flagged:** `case_spend` write policy is `requireVerifiedOwner:true`,
  `allowSharedWrites:false`, owner = `session_id` → spend rows are owned by the writing session. If HR
  needs team-wide spend visibility, that is a **design decision for the hook** (e.g. a case-scoped
  read that the hook authorises), **not** something to solve by loosening the policy or writing shared
  rows. Recommended: session-owned writes + a case-scoped read action on the hook; confirm at W4 start.

### Gap 6 — data hygiene / seed · **minimised, folded into W1/W2**

Model A has no DB seed (corridors are hardcoded arrays), so the v2 seed/idempotency criteria are
largely N/A. The only useful remnant — internal consistency (unique ids, resolvable `dependencyNote`
references, valid `appliesTo`/offsets) — is already covered by the existing "corridor isolation"
tests and the W1/W2 additions. No standalone packet. If you want it explicit, I add one consistency
test to W1.

---

## Deliberately NOT doing

- **No Model-B build:** no `case_obligations` engine, no `obligation_dependencies` blocking DAG, no
  "Obligations tab", no re-wiring the dead `case-obligations.ts`. (Model A decision.)
- **No Gap 3 / Gap 4 packets** — already satisfied in Model A (table above). These are the packets the
  spec asks for that the evidence says are unnecessary.
- **No edits treated as shipping via the repo mirror** — `audos-workspace-776786/` is a snapshot;
  all code lands in the live space via Otto (pattern a).
- **No `frontend/` `backend/` `supabase/` changes** — nothing here touches Render-served rolec, so no
  migration/RLS, serving-isolation, PII, or compliance-copy gate is engaged.
- **Not touching** the candidate-beam lane, the LinkedIn lane, or the Supabase migration-hygiene items
  the ledger lists as open founder decisions.
- **Not clearing counsel assurance** — NO→FR stays an authoring draft; assurance is a separate gate.

## Prerequisites before execution (Phase 3)

1. A **fresh `CorridorCheck.tsx`** (and, at W3/W4 start, `CaseGate.tsx` + the current `case-access`
   hook schema) — my mirror is 2026-08-11 and this is the file the 2026-08-20 regression churned.
   `rule-engine.ts` is confirmed untouched (ledger), so W1/W2 can proceed on the current copy now.
2. Otto hooks for **W3** (`review_status` get/set) and **W4** (`case-spend` create/list) — I hand over
   the contracts; Otto implements + enables during the packet's window.
3. Confirm the **HR-wide vs session-owned** spend-visibility choice for W4 (recommendation above).

## Recommended sequence (step by step, a STOP + your approval at each)

**W1 → W2 → (W3 or W4).** W1 is zero-risk and pure-test — the right first move; it locks determinism
before anything changes. W2 is small verification. W3 and W4 are the two real UI builds, each gated on
its Otto hook, and can go in either order — I'd suggest **W3 (Review)** next since it needs no new
table (just the provisioned `review_status`), then **W4 (Spend)** once the `case-spend` hook is agreed.

**STOP — awaiting approval of this plan (and of the W1-first sequence).** No branch, no code until you approve.
