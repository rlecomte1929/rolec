# ReloPass Case Command v2 — Phase 0 + Phase 1 (reconciliation), 2026-08-22

Execution of `claude_code_prompt_6_case_command_v2_spec_execution.md`, reconciliation-first.
Run from a Cowork session with the local `rolec` clone bridged (read/write) plus `~/Downloads`
granted. **Analysis only — no code was written, no branch created, no commit made.** Ends at the
Phase 1 STOP, awaiting approval.

---

## PHASE 0 — INVENTORY

### inputs (all 5 present + byte-exact, but SPLIT across two locations, not all in SOURCE_DIR)

| Input | Expected | Found | Location | Verdict |
|---|---|---|---|---|
| `ReloPass_Gap_Analysis_and_Build_Spec_v2_codebase_aware.md` | 23,098 B | 23,098 B | `rolec/audos-workspace-776786/` | OK (content) |
| `ReloPass_Gap_Analysis_Build_Spec.md` (v1) | 35,933 B | 35,933 B | `rolec/audos-workspace-776786/` | OK |
| `APP_INTEGRATION_MANIFEST.md` | 30,390 B | 30,390 B | `rolec/audos-workspace-776786/` | OK |
| `LinkedIn_Outreach_Build_Spec.md` | 7,261 B | 7,261 B | `rolec/audos-workspace-776786/` | OK |
| `relopass_state_ledger.md` | 24,661 B | 24,661 B | `~/Downloads/` | OK |

Deviation (reported, not worked around): `SOURCE_DIR: ~/Downloads` does **not** hold the 4 spec files —
they live in the repo mirror; only the ledger is in Downloads. All five are byte-exact against the
prompt's manifest, so content authority is satisfied; the channel is just different from what the
prompt states.

### branch

- On `feat/enrich-curated-batches-non-obvious`, up to date with origin. **Not `main`** (good).
- **Tree is DIRTY.** Modified: `.githooks/pre-commit`, `supabase/config.toml`. Untracked incl.
  `.architect-audits/`, `.gstack/`, stray `200` / `200,` / `404`, and several dated `.md`/`.html`.
- Not a Phase 0/1 blocker (read-only), but a **Phase 3 blocker**: any packet work must start from a
  clean base off the intended base branch.

### code source — **case (c): a PARTIAL 2026-08-11 Audos export, NOT the stale mirror the prompt describes**

The prompt's ground-truth table (mirror = "3 files", `rule-engine.ts` ABSENT, "frozen 2026-07-16")
is **STALE / WRONG as of now**. Actual `audos-workspace-776786/apps/case-command/`:

- **17 entries**, last `[audos-sync]` push **2026-08-11** (`git log`: `f613923f`, `85d69890`).
- `rule-engine.ts` **PRESENT at 46,058 B** — exactly the prompt's "live" size.
- `App.tsx` **31,207 B** — the live size (not the mirror's claimed 29,168).
- `case-obligations.ts`, `datasheet-seed.ts`, `CaseGate.tsx`, `CorridorCheck.tsx`,
  `PersonalRelocationDataSheet.tsx`, and 3 corridor test suites all present at live sizes.

But it is **incomplete** vs the prompt's 2026-08-22 live manifest. **Absent from this export:**

- case-command: `requirement-blocks.ts` (63,045 B), `ood-gate.ts`, `corridor-step-provenance.ts`,
  `vendor-corridor-backfill.ts`, `freshness.test.ts`, `ood-gate.test.ts`, and **7 of 10** corridor
  `rule-engine.*.test.ts` suites (only france-norway / norway-france / spain-ireland present).
- lib: `corridorContract.ts` (19,349 B), `freshness.ts`, `vendorCatalog.ts`, `corridorCoverage.ts`,
  `vendorTaxonomy.ts` (present: `dataSheetBuilder.ts`, `datasheet-types.ts`).

Consequence: the core engine is reconcilable **now** (and 37 tests run green — below), but any spec
claim whose evidence would live in a missing file cannot be closed from here. A complete current
export is needed to finish (Question 2).

### ledger state (Case Command lane)

1. **This task is the resumption of a PAUSED lane.** Ledger: *"Case Command gaps build (prompts
   #3/#3a): PAUSED, awaiting the delta-list reply from the mirror size-diff. Do not interleave with
   the beam lane. WorkspaceDB schema for it is already provisioned (`cases.employer_engaged`,
   `cases.review_status`, `case_obligations.resolution_state/resolution_note/flag_severity`,
   `case_spend` table)."* → the Gap 2–5 schema is attested provisioned; this Phase 1 delta list is
   the awaited reply.
2. **Active workspace source regression (2026-08-20).** Ledger: a process *"bulk-rewrote the
   workspace file tree with a MUCH older snapshot and then PUBLISHED it"* — twice (~08:08 and
   ~21:40 UTC), *"existing files reverted, new files kept"*, `CorridorCheck.tsx` lost its freshness
   badges + the ReliefMomentPrompt re-mount, and *"IT RECURRED, and it is STILL RUNNING."* Directive:
   *"treat every file-tree claim in this ledger dated before 2026-08-20 08:07 as unverified."* This
   bears directly on whether the 2026-08-22 live capture is a good snapshot (Question 3).
3. Standing protocol reaffirmed: verify-first per premise, channel rule, single-authorship,
   explicit-ordering, cite-the-ledger.

### blockers (Phase 0 → Phase 1)

- **None that stop Phase 1** — I have the core engine + all 5 inputs and ran the live tests.
- **Two that gate a faithful Phase 2/3:** (a) incomplete export (missing engine-adjacent files +
  WorkspaceDB has no read path from here — the case_* schema claims are attested, not verified);
  (b) dirty tree / unconfirmed base branch. Both surfaced as questions below.

---

## PHASE 1 — RECONCILIATION

### The headline finding: the spec conflates two different data models, and describes the wrong one as "ALREADY BUILT"

There are **two parallel Case Command models**, and v2's *"What already exists (do not rebuild)"*
section attributes Model-B behaviour to Model-A files that don't implement it.

- **Model A — shipped, live, tested.** `rule-engine.ts` is a **pure, stateless timeline/feasibility
  calculator** over **hardcoded** corridor requirement arrays, rendered by `CorridorCheck.tsx`.
  Signature `runCaseCheck(employeeType, anchorDate, today, corridorId)` → `requirements[]` each with
  a `feasibility ∈ {green, amber, red, confirmed}`. Three corridors authored (FR→NO 19 rules, NO→FR
  23, ES→IE 13). **37/37 tests pass.**
- **Model B — WorkspaceDB UIM/EAV.** `cases` / `case_facts` / `pathway_eligibility_rules` /
  `obligations` / `obligation_dependencies` / `case_obligations` tables (attested to exist by
  prompt #6 row-counts + the ledger; **not verifiable from here**). `case-obligations.ts` holds a
  row-joiner with `blocked`/`blockedBy`/`flag_message` — but it is **imported by nothing** and fed a
  **hardcoded Sarah-Chen (Singapore→London) snapshot.** There is **no engine** that turns
  `case_facts` into `case_obligations`, and **no App.tsx tab** that renders them, anywhere in this
  export.

v2 says Model B's engine/UI are done. **They are not.** And the behaviours v2's Gaps 1/3/4 ask to
add already exist in **Model A**. Building "as specced" therefore risks standing up a *second*
obligations engine + renderer that duplicates the shipped calculator — a single-authorship
violation, and exactly the "rebuilding what exists" failure mode the prompt warns about.

### evidence table (v2 "already exists" claims vs real code)

Citations are `apps/case-command/…` unless noted. `re` = `rule-engine.ts`, `co` = `case-obligations.ts`.

| Spec claim | v2 class | Verdict | Evidence |
|---|---|---|---|
| Engine "accepts a Case ID; loads `case_facts` + `condition_tree`" | ALREADY BUILT | **CONTRADICTED** | `runCaseCheck(employeeType, anchorDate, today, corridorId)` `re:931`. No case id, no DB, no `case_facts`/`condition_tree` in the file (token scan: 0 hits). |
| "Evaluates the condition tree to confirm pathway match" | ALREADY BUILT | **NOT FOUND** | Corridor chosen by `CORRIDORS[corridorId]` `re:937`; requirements filtered by `appliesTo` `re:943`. No pathway/condition-tree logic. |
| "Instantiates `case_obligations` respecting `obligation_dependencies` DAG; blocked start `'blocked'`" | ALREADY BUILT | **CONTRADICTED** | No `case_obligations`, no `obligation_dependencies`, no `'blocked'` status. `Feasibility` = green/amber/red/confirmed `re:25`,`re:831`. `dependencyNote` is free text `re:53`, drives nothing. |
| "Computes `due_date` from a 3-tuple `anchor_type`+`offset_days` vs `absolute_date`, anchored to `move_date`/`arrival_date` CaseFact" | ALREADY BUILT | **CONTRADICTED** | `actionByDate = anchorDays + offsetWeeks*7` `re:945`; single int `offsetWeeks` `re:46`. No `anchor_type`/`offset_days`/`absolute_date`; no `arrival_date` fact. |
| "Resolves `case.*` / `facts.*` / `destination.*` / `nationality.*` paths" | ALREADY BUILT | **NOT FOUND** | No path resolver anywhere; inputs are `(employeeType, date)`. |
| "Idempotent — re-runs preserve completed history" | ALREADY BUILT | **PARTIAL / N-A** | Pure function, deterministic (tests assert `toEqual`, `rule-engine.norway-france.test.ts:31`). But there is no persisted `case_obligations` history to preserve — nothing is stored. |
| "Stress-tested vs `GIQ-2024-FR-NO-00001` → 6 `case_obligations`" | ALREADY BUILT | **NOT FOUND** | No such case in code. FR→NO = **19** hardcoded rules `re:137-336` → feasibility items, not 6 obligations. Test suites are the 3 corridor files (37 tests), none referencing that id. |
| "App.tsx + case-obligations.ts Obligations tab: status pills pending/in progress/blocked/completed" | ALREADY BUILT | **CONTRADICTED (as wired)** | App.tsx views are `'cases'`/`'check'` `App.tsx:436,527`; **no** import of `case-obligations.ts` (grep: 0). ObligationStatus pills exist only in `co:15` — a module imported by nothing. |
| "Due date with red 'Xd overdue'" | ALREADY BUILT | **PARTIAL** | "Xd overdue" in App.tsx `DaysRemaining` `App.tsx:82`, but over `sample-data.deadlineDate`, not obligations. CorridorCheck shows "Window passed" red for elapsed windows `CorridorCheck.tsx:116`. |
| "`flag_message` highlighted in teal" | ALREADY BUILT | **NOT FOUND (as wired)** | `flagMessage` lives in `co:88` (unwired). CorridorCheck renders `nonObvious` flags `CorridorCheck.tsx:134`, not an obligations `flag_message`. |
| "Full DAG 'Waiting on: [upstream]' with upstream live status" | ALREADY BUILT | **NOT FOUND** | Literal "Waiting on" appears **nowhere** in the workspace (grep: 0). `blockedBy` logic exists in `co:92,169` but unwired. |
| "Theme tokens `#0b1620/#142430/#2a93e0/#38c6de`" | (constraint) | **PARTIAL** | App themes via CSS custom properties `--space-*` + `lib/colors.ts` `tw` (`App.tsx:29`, `CorridorCheck.tsx:117`), not hardcoded hex. Follow the token system, not literal hex. |
| WorkspaceDB `cases`/`case_facts`/`pathway_eligibility_rules`/`obligations`/`obligation_types`/`obligation_dependencies`/`case_obligations` + Gap 2–5 columns | (given) | **UNVERIFIABLE HERE — ATTESTED** | No WorkspaceDB read path in this environment. Attested by prompt #6 (row counts) + ledger (Gap 2–5 provisioned). Code refs: only `due_date` + one `obligation_dependencies` comment `co:6`; **none** of `employer_engaged`/`review_status`/`case_spend`/`resolution_state`/`red_late`/`nothing_to_do` appear in this export's code. |

### test baseline (real output)

Mac `node_modules` can't run in the device's Linux VM (`Cannot find module @rollup/rollup-linux-arm64-gnu`
— cross-platform install), so I copied `rule-engine.ts` + the 3 test files into the cloud container,
installed vitest 2.1.9, and ran:

```
 Test Files  3 passed (3)
      Tests  37 passed (37)   Duration 934ms
```

- `rule-engine.france-norway.test.ts` — 12 tests, all green ("behaviour must not change" regression;
  derived-runway 42→112-day band; determinism).
- `rule-engine.norway-france.test.ts` — 13 tests, all green (retrospective red for elapsed windows;
  `confirmed`-clear positives counted separately (Gap 3); `Employer (not engaged)` owner not moved to
  employee (Gap 4); corridor isolation).
- `rule-engine.spain-ireland.test.ts` — 12 tests, all green (contract-signed anchor; banner measures
  time SINCE signature; employer-owned permit).

These 37 tests exercise **Model A only**. No test in this export touches `case_obligations`,
`obligation_dependencies`, `condition_tree`, or a Case ID — corroborating the table above.

### delta list — what is genuinely left, per gap (both readings shown)

| Gap | v2 class | Reality in Model A (shipped) | Genuinely left |
|---|---|---|---|
| **1 — NO→FR corridor** | net-new content | **Largely DONE:** `NORWAY_FRANCE_REQUIREMENTS` (23 rules) authored + rendered by CorridorCheck; 13 NO→FR tests green incl. retrospective + confirmed + employer-not-engaged. | If Model A is the target: **author polish + source verification only** (content marked DRAFT/needs-source). If Model B: **everything** — seed `GIQ-2024-NO-FR-00001`, `pathway_eligibility_rules.condition_tree`, `obligations`+`obligation_dependencies` (customs-import blocked-until-export), and an engine+tab to render them (none exist). |
| **3 — retrospective + `nothing_to_do`** | partially built (extend) | **DONE in Model A:** `red` = "Window passed" for wholly-elapsed windows; `confirmed`/`confirmedClear` positive, counted separately; past anchors first-class (`pastAnchorText`). | Nothing, if Model A. If Model B: add `resolution_state`/`flag_severity` handling to a `case_obligations` engine that doesn't exist yet. |
| **4 — `employer_absent`** | net-new small | **DONE in Model A:** `Owner` includes `'Employer (not engaged)'`, used on `b2-urssaf`/`b3-PE`, tested (not reassigned to employee). | Nothing, if Model A. If Model B: `cases.employer_engaged` gating `case_obligations.responsible_party=employer_absent` — needs the Model-B engine. |
| **2 — Spend tracking** | net-new | No spend surface. CorridorCheck is **stateless** (no per-case persistence). | Genuinely new — but **where it attaches depends on the model.** Spec targets `case_spend`→`cases`/`case_obligations` (Model B). Model A has no persistent case to hang spend on. |
| **5 — Estimate Review** | net-new | No review state; no per-case store. | Genuinely new — same model dependency. Spec targets `cases.review_status` over `case_obligations`. |
| **6 — Data hygiene / seed** | net-new | Model A "seed" = the hardcoded arrays (no DB seed). | Genuinely new **only in Model B** (idempotent seed of both corridors' rows + cases). Meaningless for Model A. |
| **7 — E2E verification** | net-new | Model A determinism is **already** locked by the 37 vitest tests (10-run stability is implied by pure-function `toEqual`). | If Model A: extend existing vitest to an explicit 10× byte-stable harness across corridors (small). If Model B: net-new against an engine that doesn't exist. |

### contradictions (spec says X, code shows Y)

1. **Engine identity.** Spec: `rule-engine.ts` is a DB-backed Rule DSL engine (Case ID → `case_facts`
   + `condition_tree` → instantiate `case_obligations` with DAG blocking + 3-tuple due dates). Code:
   it is a stateless hardcoded-corridor feasibility calculator (`re:931`), no DB, no DAG, no 3-tuple.
2. **Obligations UI.** Spec: App.tsx renders an Obligations tab (pills, "Waiting on:", teal
   `flag_message`) via `case-obligations.ts`. Code: App.tsx imports `sample-data`, not
   `case-obligations.ts` (grep 0); the shipped engine UI is `CorridorCheck.tsx`; `case-obligations.ts`
   is **dead code** fed a hardcoded snapshot; "Waiting on" exists nowhere.
3. **Gaps 1/3/4 already exist in Model A**, so "extend the Model-B engine" would duplicate shipped,
   tested functionality — a single-authorship violation.
4. **Prompt #6's mirror ground-truth is stale** — the mirror already contains `rule-engine.ts`
   (46,058 B) and 16 more entries at live sizes; it is a 2026-08-11 partial export, not the "3-file,
   frozen 2026-07-16" snapshot described.
5. **Source stability.** The ledger records an active file-tree regression (2026-08-20, "still
   running") that reverts the workspace to a July snapshot and republishes — so the 2026-08-22 live
   capture's integrity needs confirming before anything is built on it.

### questions (each with a recommended answer) — STOP here

1. **Which model is Case Command's target — Model A (shipped `rule-engine.ts` + `CorridorCheck`) or
   Model B (`case_obligations` UIM)?** *Recommended:* confirm Model A is the live product surface and
   that v2's "ALREADY BUILT" Model-B engine/UI **do not exist in code**; do **not** build a second
   obligations engine/renderer. Re-map Gaps 2/5/6/7 onto whichever single model you choose. This is
   the decision the rest of the plan hangs on.
2. **Provide a COMPLETE current Audos export** (`apps/case-command/` all ~40 entries incl.
   `requirement-blocks.ts`, `ood-gate.ts`, `corridor-step-provenance.ts`, `vendor-corridor-backfill.ts`,
   all 10 tests; `lib/` incl. `corridorContract.ts`, `freshness.ts`, `vendorCatalog.ts`; `tools/`).
   *Recommended:* yes — my copy is the 2026-08-11 partial mirror; needed to rule out that a Model-B
   engine hides in a missing file and to reconcile the freshness/ReliefMoment UI.
3. **Confirm the 2026-08-22 live capture is a good, post-repair snapshot** (the ledger's rewriter was
   "still running" on 2026-08-20). *Recommended:* Otto confirms the rewriter is stopped before build.
4. **WorkspaceDB read (or an Otto row-dump)** for `cases`/`case_obligations`/`obligations`/
   `obligation_dependencies` + the Gap 2–5 columns, so the schema is verified, not just attested.
   *Recommended:* Otto provides a read-only export.
5. **Clean base for Phase 3.** Currently on `feat/enrich-curated-batches-non-obvious` with a dirty
   tree. *Recommended:* confirm the intended base (main?), clean/stash, branch fresh before any packet.
6. **Theme:** follow the `--space-*` CSS-var token system the app actually uses, not the literal hex
   in the spec. *Recommended:* yes.

**STOP — awaiting approval. No Phase 2 plan, no branch, no code until the model question (1) is answered.**
