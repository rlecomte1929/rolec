# ReloPass AI/ML Learning Playbook v2 — Execution Roadmap

*Generated 2026-08-19 from the Notion AI Work Queue (`collection://4e2887c6-4d48-82c1-931e-87b09fb5c4ed`). 49 tasks derived from the playbook's 58 recommendations. Each task's `AIQ-####` is its live Notion ID — the source of truth. This file is a committable snapshot for a Claude Code / Conductor session.*

---

## How to use this file

Two ways to execute, both keyed on the `AIQ-####` id:

1. **Notion-native (preferred).** In a Claude Code session with the repo mounted and the Notion connector on, run `relopass-autopilot` (Green/Yellow lane) or `relopass-dev-queue` / `pick up AIQ-1940`. The skill pulls the live brief, runs the `Test Command`, commits, and writes status back to Notion. Nothing goes stale.
2. **File-native (offline).** If Notion isn't wired into that session, copy the fenced **AI Brief** under any task straight into Claude Code. It's self-contained (context, files, approach, test, snapshot).

### Lanes (autonomy tier)

- 🟢 **Green → Ready for AI** — reversible, no prod-data/security surface, concrete test. Autopilot auto-executes + auto-Dones.
- 🟡 **Yellow → Ready for AI** — ships code but test-covered, low blast radius. Autopilot executes + self-validates; ~15% human audit sample.
- 🔴 **Red → Needs Decomposition** — expensive/irreversible/foundational. Run `notion-decomposition` first, then dev-queue. Never auto-advanced.

### Routing (`FIX SKILL`)

`relopass-fix-ui-bug` (Layer UI) · `relopass-fix-api-bug` (Layer API) · `notion-decomposition` → `relopass-dev-queue` (Layer Feature / Red).

### Snapshot caveat

File paths are directory-level with a "grep for X" hint; dev-queue's recon resolves exact files. All briefs stamped 2026-08-19 — re-verify if >14 days old. Foundational architecture tasks are 🔴 Red on purpose: decompose before one-shot execution.

---

## Priority legend

`P0` = before the next paying customer · `P1` = next 90 days · `P2` = plan for v1.

Counts: **P0 = 18 · P1 = 23 · P2 = 4 · New authoring-pipeline gaps (P1) = 4.** Lanes: 🔴 12 · 🟡 32 · 🟢 5.

---

# P0 — Before the next paying customer

### AIQ-1935 · [Architecture] LLM authors, deterministic engine serves
**P0 · 🔴 Red → Needs Decomposition · Layer API · AI/ML Implementation · Route: `notion-decomposition`**

```text
## AI Brief — Playbook v2 rec #1

Task: LLM authors, deterministic engine serves — never serve compliance from the probabilistic layer
Layer: API · Tier: 🔴 Red · Route: notion-decomposition

Context: 755 authored facts serve via the compliance engine. The catastrophic failure mode is a runtime path that lets an LLM output reach an HR user as a 'requirement' without lawyer verification. The playbook (Theme 1, CS50 AI + MIT Lec 21) makes this the load-bearing invariant.

Goal: Prove and enforce that the runtime serving path performs zero LLM inference; every served requirement comes from the deterministic engine over lawyer-verified, source-attributed facts.

Files to touch:
- backend/app/routers/ — map every serving endpoint's call graph
- backend/app/services/ — the rule/compliance engine that emits timelines
- backend LLM client module — grep anthropic|openai|llm; confirm it is import-unreachable from serving
- CI (.github/workflows/ or .githooks/) — add a guard

Approach: (a) map the serving call graph; (b) locate all LLM client usages, confirm they live only in authoring; (c) add a CI/lint guard + unit test that fails if an LLM client is reachable from a serving endpoint; (d) write the ARCHITECTURE.md boundary section. Coordinate with the absorbed #1986 runtime block.

Test command: cd backend && pytest -q + a guard test asserting no LLM client import is reachable from the serving path.
Schema: No DB changes.
```

- **Validation:** Runtime path contains zero LLM inference; every served requirement is produced by the deterministic engine from lawyer-verified facts with a source_url. Architecture doc + code review confirm the split.
- **Deps:** Absorbed #1986 (code-level invariant; sources: MIT 6.7960 Lec 8, MIT 15.773 Lec 7, AI Dev 26 Andrew Ng). Related #1936.

### AIQ-1936 · [Architecture] Generator–verifier gate
**P0 · 🔴 Red → Needs Decomposition · Layer API · Backend Implementation · Route: `notion-decomposition`**

```text
## AI Brief — Playbook v2 Theme 4 (recs #20/#23)

Task: Generator–verifier gate — no LLM candidate ships without lawyer/user verification
Layer: API · Tier: 🔴 Red · Route: notion-decomposition

Context: LLMs propose candidate requirements; the risk (MIT Lec 21 — 'four of five cited papers don't exist') is a plausible, confident, false requirement reaching an HR user. Today there is no enforced state machine separating candidates from servable facts.

Goal: Enforce a state machine — candidate → (human/lawyer verify) → servable — at the schema + write-path level so an unverified candidate is structurally unservable.

Files to touch:
- schema / supabase/migrations/ — additive lifecycle state on requirement_fact (candidate|representative|verified)
- backend/app/services/ — the only promotion path (representative→verified requires a recorded verifier)
- backend/app/routers/ — serving query filters to verified only

Approach: Add a lifecycle-state column (additive). Route all writes through a single promotion function that records verifier identity + timestamp. Serving selects only verified. Reuse the absorbed #1983 guardrail. Decompose into: migration, write-path guard, serving filter, regression tests.

Test command: cd backend && pytest -q (candidate-cannot-serve, promotion-requires-verifier, serving-excludes-unverified).
Schema: Additive migration (lifecycle state column).
```

- **Validation:** No requirement_fact reaches 'servable' without a recorded verifier sign-off; unverified LLM candidates sit in a review queue and are unservable. Only a human flips representative→verified (hard-fail programmatic attempts; audit-log every flip).
- **Deps:** Absorbed #1983 (verified-write guardrail; sources: AI Dev 26 Adit Abraham, MLOps #25, CS329A). Related #1935, #1998.

### AIQ-1937 · [Architecture] Corridor compile/validate build step
**P0 · 🔴 Red → Needs Decomposition · Layer API · Backend Implementation · Route: `notion-decomposition`**

```text
## AI Brief — Playbook v2 rec #17

Task: Corridor compile/validate build step — only lawyer-verified corridors serve
Layer: API · Tier: 🔴 Red · Route: notion-decomposition

Context: Corridors publish without a compile-style gate, so an unverified or malformed corridor can reach serving. Playbook (CS50x Lec 1/2): publishing = compiling; it only 'compiles' if every requirement has a live source, a valid employee-type profile, and a valid deadline.

Goal: Add a 4-stage build (resolve templates → validate types+sources → compute deadlines → link timeline). Stamp a build status; only status-0 (lawyer-verified & servable) returns compliance output.

Files to touch:
- backend/app/services/ — new build/compile module (4 stages, each gating the next)
- backend/app/routers/ — serve only status-0 corridors
- supabase/migrations/ — additive build_status on corridor

Approach: Stages as pure functions returning pass/fail + diagnostics; a corridor advances only if all pass. Persist build_status (0 servable / 1 representative). Shadow-run before flipping serving. Decompose into: stage functions, status persistence, serving filter, tests.

Test command: cd backend && pytest -q.
Schema: Additive migration (build_status).
```

- **Validation:** Corridors carry a build status (0 = verified & servable, 1 = representative/unverified behind CaseGate). Only status-0 serves; failed builds cannot publish.
- **Deps:** —

### AIQ-1938 · [Trust/Compliance] OOD gate before emitting a timeline
**P0 · 🔴 Red → Needs Decomposition · Layer API · Backend Implementation · Route: `notion-decomposition`**

```text
## AI Brief — Playbook v2 recs #4/#5

Task: OOD gate before emitting a timeline — verify corridor, nationality, employee-type; degrade visibly
Layer: API · Tier: 🔴 Red · Route: notion-decomposition

Context: Case Command can render a clean, authoritative-looking timeline for a case outside the verified graph (MIT Lec 17: a brittle model is most confident exactly where it is most wrong — pig→airliner at 99%). For compliance that means silently omitting a week-seven requirement.

Goal: Classify every case against the verified graph on 3 axes before emitting output; any unverified axis → OOD → force a visibly degraded, caveated response and log an OOD-distance signal.

Files to touch:
- backend/app/services/ — OOD classifier (3-axis coverage check + distance)
- backend/app/routers/ — call the gate before timeline emission
- backend/app/models/ — verified-coverage lookups (corridor/nationality/employee-type)

Approach: Coverage lookups per axis → boolean in-distribution + a scalar distance. Serving refuses a confident timeline when OOD. Emit verdict+distance to the UI (#1939) and the verification backlog (#1966). Decompose into: coverage lookups, distance metric, serving integration, tests.

Test command: cd backend && pytest -q.
Schema: No DB changes (reads coverage).
```

- **Validation:** Each case classified on 3 axes (corridor verified? nationality/passport class seen? employee type covered?). Any unverified axis flips to OOD and forces a degraded, caveated output.
- **Deps:** — (pairs with UI #1939)

### AIQ-1939 · [Trust/Compliance] Show the OOD boundary as a trust feature
**P0 · 🟡 Yellow → Ready for AI · Layer UI · Frontend Implementation · Route: `relopass-fix-ui-bug`**

```text
## AI Brief — Playbook v2 rec #6

Task: Show the OOD boundary as a trust feature — 'outside my verified zone'
Layer: UI · Tier: 🟡 Yellow · Route: relopass-fix-ui-bug

Context: When a case is OOD (see API #1938), the product should not render a normal timeline. The playbook (MIT Lec 17 + Kissinger): the honest boundary is more trustworthy than confident coverage — the 'this thing knows things I don't' promise.

Goal: Render an explicit OOD panel: what I'm confident about / what I can't yet vouch for / how to get it verified — plus a CTA to request verification.

Files to touch:
- frontend/src/ timeline/dossier component — branch on the API OOD verdict
- frontend/src/ API types — add the OOD verdict + distance shape

Approach: Consume the verdict from #1938 (do not compute client-side). When OOD, swap the timeline for the 3-part panel with a 'request verification' CTA that files into the backlog. Keep the in-distribution path unchanged. Ship behind a flag; A/B the tone.

Test command: cd frontend && npx tsc --noEmit.
UX: Tailwind + shadcn/ui; WCAG 2.1 AA; reassuring not alarming; responsive 1280/1440.
Schema: No DB changes.
```

- **Validation:** OOD cases display the 'confident / can't-vouch / get-verified' panel; an OOD-distance signal is logged per case and routes high-distance cases to the verification backlog.
- **Deps:** Depends on #1938.

### AIQ-1940 · [Data Quality] Enforce requirement_fact schema
**P0 · 🟡 Yellow → Ready for AI · Layer API · Backend Implementation · Route: `relopass-fix-api-bug`**

```text
## AI Brief — Playbook v2 rec #3

Task: Enforce requirement_fact schema (types + pydantic, mandatory source_url + evidence_quote)
Layer: API · Tier: 🟡 Yellow · Route: relopass-fix-api-bug

Context: The moat is 755 facts, 70% source-linked — meaning ~30% are not. MIT Lec 21 + CS50x Lec 1/6: grounding is absent, so the citation IS the grounding — no source, no fact, enforced at the schema level.

Goal: A typed model that validates every requirement_fact at ingest and rejects null fact_type / null source_url / null evidence_quote; one canonical schema across all corridors.

Files to touch:
- backend/app/models/ — pydantic model (fact_text, source_url, evidence_quote, deadline_offset:int)
- backend/app/services/ ingest path — route all writes through it
- tests/ — rejection + acceptance cases

Approach: Define the model as the single ingest gate; add a backfill report flagging existing rows that would fail (feed #1941). Enforce on new ingest now; enforce on existing after the report is cleared.

Test command: cd backend && pytest -q.
Schema: No new columns (validation only); may add NOT NULL later after backfill.
```

- **Validation:** A typed model rejects any row with null fact_type/source_url/evidence_quote; one canonical schema enforced across corridors, diffable across LLM passes.
- **Deps:** Pairs with #1941.

### AIQ-1941 · [Data Quality] Segregate 134 null-source datasheet rows
**P0 · 🟡 Yellow → Ready for AI · Layer API · Backend Implementation · Route: `relopass-fix-api-bug`**

```text
## AI Brief — Playbook v2 rec #15

Task: Segregate 134 null-source datasheet rows from the 17 compliance facts
Layer: API · Tier: 🟡 Yellow · Route: relopass-fix-api-bug

Context: The fact table mixes 134 datasheet/field-definition rows (null source_url) with ~17 lawyer-relevant compliance facts. Nothing untyped/unsourced must leak into served output (CS50x Lec 1).

Goal: Tag or move the datasheet rows so the serving path can only read sourced compliance facts — without deleting anything.

Files to touch:
- supabase/migrations/ — additive is_compliance_fact flag (default false)
- backend/app/services|routers/ — serving filter (is_compliance_fact AND source_url NOT NULL)
- scripts/ — one-off tagging script that emits a before/after report

Approach: Add the flag; set is_compliance_fact=true only on the confirmed 17; produce a report for human sign-off before the serving filter goes live. No deletes. Coordinate with #1940.

Test command: cd backend && pytest -q.
Schema: Additive migration (is_compliance_fact flag).
```

- **Validation:** The 134 datasheet rows are flagged separately from the 17 compliance facts; the serving path reads only sourced compliance facts.
- **Deps:** Depends on schema #1940.

### AIQ-1942 · [Data Quality] Format CVRs consistently = training-data readiness
**P0 · 🟡 Yellow → Ready for AI · Layer API · Backend Implementation · Route: `relopass-fix-api-bug`**

```text
## AI Brief — Playbook v2 rec #29

Task: Format Case Verification Reports consistently from day one = v1 training-data readiness
Layer: API · Tier: 🟡 Yellow · Route: relopass-fix-api-bug

Context: CVRs are the transfer points (MIT Lec 19): each lawyer-verified case is simultaneously the validation artifact and a future fine-tuning example. Ad-hoc formats now make the corpus untrainable later.

Goal: Enforce one fixed CVR schema (official_guidance, actual_reality, action_required, source, corridor, created_at); support clean train/validation splits by corridor; an export path emitting CVRs as fine-tuning records. Backfill out of scope.

Files to touch:
- backend/app/models/ — CVR schema
- backend/app/services/ — CVR write/read + corridor-split helper + export
- tests/

Approach: One CVR model; a split helper (held-out set feeds #1945); reject ad-hoc CVR writes; keep an open_notes field.

Test command: cd backend && pytest -q.
Schema: Additive (CVR schema/table).
```

- **Validation:** A fixed CVR schema is enforced; supports train/validation splits by corridor; corpus batchable; a sample round-trips into a fine-tuning export. No ad-hoc formats.
- **Deps:** Absorbed #1997. Feeds eval harness #1945.

### AIQ-1943 · [Corridor Knowledge] Hard-negative registry
**P0 · 🟡 Yellow → Ready for AI · Layer API · Backend Implementation · Route: `relopass-fix-api-bug`**

```text
## AI Brief — Playbook v2 rec #35

Task: Hard-negative registry — force apart Norway EEA-not-EU and Ireland non-Schengen look-alikes
Layer: API · Tier: 🟡 Yellow · Route: relopass-fix-api-bug

Context: Requirements that read almost identically to an EU-corridor requirement can be silently copied across the EEA/Schengen boundary (MIT Lec 12: hard negatives carry the signal). Norway is EEA-not-EU; Ireland is EU-but-non-Schengen.

Goal: A registry of look-alike pairs that must never be auto-merged or cross-copied, consulted by every transfer and dedup path.

Files to touch:
- backend/app/models/ — hard_negative table (pair + reason)
- backend/app/services/ — transfer/copy (#1963) and cosine dedup (#1960) consult it
- tests/

Approach: Additive table seeded with the two canonical pairs; expose is_hard_negative(a,b); wire into copy + dedup so a match is blocked and surfaced for human review.

Test command: cd backend && pytest -q.
Schema: Additive (hard_negative table).
```

- **Validation:** An explicit hard-negative registry exists; flagged pairs are blocked from cross-corridor copy and forced apart in similarity/dedup; seeded with ≥2 pairs.
- **Deps:** Consumed by #1960, #1963.

### AIQ-1944 · [Corridor Knowledge] Demand-pull gate (no corridor without an anchoring case)
**P0 · 🔴 Red → Needs Decomposition · Layer Feature · Backend Implementation · Route: `notion-decomposition`**

```text
## AI Brief — Playbook v2 rec #56

Task: No corridor/requirement without a real anchoring case — grow the graph dynamically (demand-pull gate)
Layer: Feature · Tier: 🔴 Red · Route: notion-decomposition

Context: Verified representative cases — not corridor count — are the growth metric. The failure mode is pre-allocating empty requirement rows or inferring an unverified corridor from an adjacent one.

Goal: Enforce that a corridor/requirement only becomes servable when a real HR-anchored case pulls it; the OOD flag (#1938) triggers real verification, not inference.

Files to touch:
- backend/app/services/ — authoring/expansion gate
- backend/app/routers/ — admin create paths
- admin UI — surface the demand-pull decision + backlog

Approach: Allow candidate authoring but block promotion-to-servable unless an anchoring case exists. Wire OOD trips into a verification backlog. Feed the expansion score (#1961). Decompose into: gate rule, admin surface, backlog wiring, tests.

Test command: cd backend && pytest -q.
Schema: Possibly additive (anchoring-case link).
```

- **Validation:** No empty/pre-allocated requirement rows for corridors lacking a verified anchoring case; the OOD flag triggers real verification rather than inference.
- **Deps:** Ties to #1938, #1961.

### AIQ-1945 · [Evaluation/Metrics] Build the relief-moment eval harness BEFORE any model
**P0 · 🔴 Red → Needs Decomposition · Layer Feature · AI/ML Implementation · Route: `notion-decomposition`**

```text
## AI Brief — Playbook v2 recs #7/#8

Task: Build the relief-moment eval harness BEFORE any model
Layer: Feature · Tier: 🔴 Red · Route: notion-decomposition

Context: The 10-Book Gap Report rates the relief-moment eval 🔴 MISSING — the single biggest measurement gap. PyTorch discipline: build the eval harness before the model; keep a fixed versioned test set; never train on the test set.

Goal: A harness that scores corridor cases against a frozen held-out CVR set and computes non-obvious-flag recall (fraction of lawyer-confirmed non-obvious items the roadmap surfaces), with authoring and scoring strictly separated.

Files to touch:
- backend/app/eval/ — harness (load fixtures → run pipeline → compute recall)
- versioned fixtures dir — the held-out CVR set
- tests/eval/

Approach: Freeze/version a held-out CVR set (from #1942). Compute non-obvious-flag recall as the one scalar. Assert zero overlap between authoring and scoring cases. Decompose into: fixtures, recall metric, split guard, CLI/report. This is the target every future model aims at.

Test command: cd backend && pytest -q.
Schema: No DB changes (reads CVRs).
```

- **Validation:** A held-out CVR test set exists; the pipeline computes non-obvious-flag recall; authoring and scoring strictly separated (no train-on-test).
- **Deps:** Depends on CVR schema #1942; feeds #1946, #1984.

### AIQ-1946 · [Evaluation/Metrics] Lock PostHog relief-moment logging
**P0 · 🟡 Yellow → Ready for AI · Layer UI · Frontend Implementation · Route: `relopass-fix-ui-bug`**

```text
## AI Brief — Playbook v2 recs #7/#57

Task: Lock PostHog relief-moment logging as the production eval signal
Layer: UI · Tier: 🟡 Yellow · Route: relopass-fix-ui-bug

Context: The metric is the objective function; instrument it first. The binary relief prompt at the bottom of each roadmap is the standing production signal for corridor accuracy — today it is not captured.

Goal: Fire relief_moment_response(corridor, employee_type, response, open_text, case_id, timestamp) at the end of every roadmap and expose a yes-rate-per-corridor read.

Files to touch:
- frontend/src/ roadmap/timeline component — mount the prompt + fire the event
- frontend/src/ PostHog wrapper

Approach: Add the binary prompt at roadmap end; fire the typed event via the existing PostHog client (debounce one per case; scrub PII). Confirm events land; wire a yes-rate-per-corridor view (feeds #1968). Ship behind a flag.

Test command: cd frontend && npx tsc --noEmit.
Schema: No DB changes (analytics).
```

- **Validation:** relief_moment_response events fire with the full property set at the bottom of every roadmap; dashboard shows yes-rate per corridor.
- **Deps:** Production counterpart to #1945; related #1968.

### AIQ-1947 · [Architecture] CSP feasibility check (flag infeasible move dates)
**P0 · 🔴 Red → Needs Decomposition · Layer API · Backend Implementation · Route: `notion-decomposition`**

```text
## AI Brief — Playbook v2 (CS50 AI — CSP/A*)

Task: CSP feasibility check — flag infeasible move dates in week one
Layer: API · Tier: 🔴 Red · Route: notion-decomposition

Context: The relief moment is 'the week-seven ambush, computed in week one'. Today there is no planner that detects when a requirement dependency chain is infeasible for a given move date.

Goal: A deterministic planner that orders requirements by dependency, flags infeasible move dates, and returns the critical path.

Files to touch:
- backend/app/services/ — planner (arc-consistency/backtracking or A*) over the typed graph (#1953)
- backend/app/routers/ — expose feasibility verdict + critical path

Approach: Build on the directed dependency graph (#1953). CSP/backtracking for a feasible ordering, A*/heuristic for the lowest-risk timeline. Flag infeasible dates with the blocking requirement named. No LLM in the planner. Decompose into: graph adapter, solver, critical-path extraction, API, tests.

Test command: cd backend && pytest -q.
Schema: No DB changes.
```

- **Validation:** A CSP/A* planner produces a feasible ordering, flags infeasible move dates, and highlights the critical path.
- **Deps:** Depends on #1953.

### AIQ-1949 · [Product UX] Clear the '2 Outstanding' badge after upload
**P0 · 🟢 Green → Ready for AI · Layer UI · Frontend Implementation · Route: `relopass-fix-ui-bug`**

```text
## AI Brief — Playbook v2 rec #14

Task: Clear the '2 Outstanding' badge via live DOM update after upload
Layer: UI · Tier: 🟢 Green · Route: relopass-fix-ui-bug

Context: After a successful document upload, the 'N Outstanding' badge stays stale until a full reload — a live P0 conversion irritant.

Goal: Decrement/remove the badge client-side from the upload success response, no reload.

Files to touch:
- frontend/src/ document-vault/dossier component — grep for the 'Outstanding' badge and the upload success handler

Approach: On upload success, read the returned outstanding count and update badge state directly (optimistic then reconcile). Ensure it reaches zero when all docs are in. Single-component, reversible.

Test command: cd frontend && npx tsc --noEmit.
Schema: No DB changes.
```

- **Validation:** Badge decrements/removes client-side from the JSON response; no stale '2 Outstanding' after all docs uploaded.
- **Deps:** —

### AIQ-1950 · [Product UX] Fix broken links + 'Start' routing
**P0 · 🟡 Yellow → Ready for AI · Layer UI · Frontend Implementation · Route: `relopass-fix-ui-bug`**

```text
## AI Brief — Playbook v2 rec #14

Task: Fix broken links + 'Start routes to dossier' — route-table + hook-verb audit
Layer: UI · Tier: 🟡 Yellow · Route: relopass-fix-ui-bug

Context: Several links are broken and 'Start' routes to the dossier instead of case intake — a live P0 navigation defect. CS50x Lec 9: one route per handler, deliberate GET/POST.

Goal: Every anchor maps to exactly one intended handler; 'Start' → intake; create/checkout are POST, access is read; no broken links remain.

Files to touch:
- frontend/src/navigation/ — nav/route config
- frontend/src/ router + components with hard-coded hrefs (grep the broken targets and 'Start')

Approach: Extract the actual route/hook table first; diff every anchor against it; fix only the mismatches; verify each route resolves. Human reviews the diff.

Test command: cd frontend && npx tsc --noEmit.
Schema: No DB changes.
```

- **Validation:** All anchors audited against the real route/hook table; 'Start' → intake; hooks single-purpose; no broken links remain.
- **Deps:** —

### AIQ-1951 · [Product UX] Rewrite the CaseGate paywall value statement
**P0 · 🟢 Green → Ready for AI · Layer UI · Frontend Implementation · Route: `relopass-fix-ui-bug`**

```text
## AI Brief — Playbook v2 rec #9

Task: Rewrite the CaseGate paywall value statement (styled benefits, before/after)
Layer: UI · Tier: 🟢 Green · Route: relopass-fix-ui-bug

Context: Live P0 feedback: 'Prepay — it's not clear what benefits I get.' CS50x Lec 8: structure=HTML, emphasis=CSS — communicate value visually at the paywall.

Goal: Make prepay value legible at a glance — checkmark benefits, contrasting card, before/after — leading with the fear, then the relief.

Files to touch:
- frontend/src/ CaseGate/paywall component (grep 'Prepay' / CaseGate)

Approach: Replace prose with a styled benefits list + before/after framing; run the copy through relopass-brand-voice. Keep distinct from the roadmap paywall (#1999). Copy/CSS only, reversible; A/B behind a flag.

Test command: cd frontend && npx tsc --noEmit.
Schema: No DB changes.
```

- **Validation:** CaseGate shows a styled benefits list (checkmark ul, contrasting card, before/after); value visible without reading prose; leads fear→relief.
- **Deps:** Distinct surface from #1999 (do not merge).

### AIQ-1952 · [Product UX] Confirm the OTP three-call auth chain completes
**P0 · 🔴 Red → Needs Decomposition · Layer API · Backend Implementation · Route: `notion-decomposition`**

```text
## AI Brief — Product hardening (auth)

Task: Confirm the OTP three-call auth chain actually completes (a CRM row is not a session)
Layer: API · Tier: 🔴 Red · Route: notion-decomposition

Context: Open uncertainty on whether EmailGate.tsx completes register→verify→sign-in, and whether a CRM row is being mistaken for an authenticated session/grant. This underpins the whole trust architecture.

Goal: Verify (and fix if needed) that only a fully verified, server-authoritative session authenticates; access_tier resolves in WorkspaceDB, never from a CRM row alone.

Files to touch:
- frontend/src/EmailGate.tsx — the POST /api/space/{spaceId}/register → verify → sign-in chain
- backend/app/routers/ — space register/verify endpoints
- backend WorkspaceDB — access_tier resolution

Approach: Characterization tests for the current flow; prove where a CRM row leaks access; fix so access_tier is server-authoritative and requires a verified session. Auth = always Red: full human gate + staged rollout behind a flag.

Test command: cd backend && pytest -q && cd ../frontend && npx tsc --noEmit.
Schema: No DB changes expected.
```

- **Validation:** A CRM row alone does not count as a signed-in user or grant; access_tier is server-authoritative in WorkspaceDB; the full register→verify→sign-in chain grants access.
- **Deps:** —

### AIQ-1973 · [Trust/Compliance] Continuous re-verification engine + weekly ritual
**P0 · 🔴 Red → Needs Decomposition · Layer Feature · Backend Implementation · Route: `notion-decomposition`**

```text
## AI Brief — Playbook v2 Theme 3 (temporal grounding)

Task: Stand up the continuous re-verification engine + weekly verification ritual
Layer: Feature · Tier: 🔴 Red · Route: notion-decomposition

Context: Models are frozen at a training snapshot; regulatory rules change constantly. Continuous re-verification is precisely the temporal grounding LLMs lack — the un-fakeable moat. Today there is no standing re-verification loop.

Goal: An engine + ritual where every requirement carries freshness, a contrastive drift signal prioritizes what to re-verify, and each real case refines the spec and becomes v1 training data.

Files to touch:
- backend/app/services/ — drift signal + re-verification scheduler
- backend/app/models/ — freshness fields (reuse #1985)
- ops runbook — the weekly ritual

Approach: Build on #1985's verified_at/days_since_last_verified. Rank decaying rules by a contrastive drift signal. Engine proposes re-verifications; a human/lawyer confirms (#1936). Every case updates the spec + CVR corpus (#1942).

Test command: cd backend && pytest -q.
Schema: Additive (freshness fields via #1985).
```

- **Validation:** A standing weekly verification ritual exists; every real case refines the spec and becomes v1 training data; a drift signal prioritizes what to re-verify as rules decay.
- **Deps:** Reuses #1985; feeds #1942, #1936.

# P1 — Next 90 days

### AIQ-1953 · [Architecture] Typed graph + topological sort + cycle detection
**P1 · 🟡 Yellow → Ready for AI · Layer API · Backend Implementation · Route: `relopass-fix-api-bug`**

```text
Task: Model the knowledge graph as a typed graph; topological sort + cycle detection for depends_on
Context: Requirements have dependencies but aren't stored as a typed graph, so implied (non-obvious) requirements can't be inferred and circular deps aren't caught.
Goal: Store corridors as nodes with typed edges (requires/precedes/source-attributed-by); emit timelines via topological sort; catch cycles at build; enable entailment of implied requirements.
Files: backend/app/models/ (graph model); backend/app/services/ (topological sort + cycle detection); tests/
Approach: Add the graph model; snapshot current timeline orderings as golden tests; implement topological emission + build-time cycle detection. Substrate for planner (#1947) and caching (#1954).
Test command: cd backend && pytest -q. Schema: Additive (graph/edge model).
```

- **Validation:** depends_on chains stored as directed edges; timeline emission uses topological sort; circular deps caught at build; entailment surfaces implied requirements.
- **Deps:** Foundation for #1947, #1954.

### AIQ-1954 · [Architecture] Cache compiled corridor requirements + invalidation
**P1 · 🟡 Yellow → Ready for AI · Layer API · Performance Optimization · Route: `relopass-fix-api-bug`**

```text
Task: Cache compiled corridor requirements + explicit invalidation on rule change
Context: Verified facts change monthly, not per request — but a cached timeline must never outlive the fact it was built from (CS50x Lec 4: decay as a memory leak; every entry needs an owner + lifetime).
Goal: Cache the compiled requirement set per (corridor_id, employee_type); invalidate + recompile on any re-verification or representative→verified flip.
Files: backend/app/services/ (cache layer + invalidation hooks on verify/promote); tests/
Approach: Key by (corridor_id, employee_type); populate on first serve; hook the promote/verify path (#1936) to drop + recompile; TTL backstop. Reversible — disable to serve direct.
Test command: cd backend && pytest -q. Schema: No DB changes (in-app/edge cache).
```

- **Validation:** Compiled set cached per corridor_id + employee_type; a re-verify/flip invalidates and recompiles all cached timelines for that corridor; no stale serve.
- **Deps:** Depends on graph #1953.

### AIQ-1955 · [Architecture] O(1) serving: compound index + denormalized served view
**P1 · 🟡 Yellow → Ready for AI · Layer API · Performance Optimization · Route: `relopass-fix-api-bug`**

```text
Task: O(1) serving: compound index + denormalized served view; scale audit
Context: An O(n^2) employee-type × requirement join fine at 3 corridors will choke at the Stage-3 DE hub (~120 pairs). Design for the scaled case now.
Goal: Constant-time retrieval via a composite index + a denormalized served-timeline view, plus a trie for corridor-prefix lookup; audit hot queries for growth order.
Files: supabase/migrations/ (composite index (corridor_id, entity_id, fact_key) + served view); backend/app/services/ (read from view; trie); tests/
Approach: Add index + read-only served view (rebuilt on invalidation from #1954); confirm via EXPLAIN; remove any O(n^2) hot-path join; add trie. Additive/reversible.
Test command: cd backend && pytest -q. Schema: Additive migration (index + view).
```

- **Validation:** Composite index exists; denormalized served view per corridor gives fast reads; no O(n^2) hot-path join; trie handles corridor-prefix lookup toward ~120 pairs.
- **Deps:** Depends on graph #1953.

### AIQ-1956 · [Data Quality] Reject truncated/corrupted evidence_quote
**P1 · 🟢 Green → Ready for AI · Layer API · Backend Implementation · Route: `relopass-fix-api-bug`**

```text
Task: Reject truncated/corrupted evidence_quote (length/checksum, preserve UTF-8)
Context: A verbatim legal quote silently cut off is data corruption that reads as authoritative (CS50x Lec 4: buffer-overflow-class). We just fixed a mojibake-corrupted document — same failure class in data.
Goal: Validate evidence_quote/fact_text at ingest; reject truncated quotes; store multilingual text as UTF-8; normalized comparison on legal text.
Files: backend/app/models|services/ (ingest validator, extends #1940); tests/
Approach: Checksum + min-length heuristic (not a hard cap); UTF-8-safe (no byte truncation); replace raw string-== with normalized compare.
Test command: cd backend && pytest -q. Schema: No DB changes (validation).
```

- **Validation:** Length/checksum validation rejects truncated quotes; multilingual quotes preserved as UTF-8; no raw string-== on legal text.
- **Deps:** Extends schema #1940.

### AIQ-1957 · [Data Quality] Resilient source fetching
**P1 · 🟡 Yellow → Ready for AI · Layer API · Backend Implementation · Route: `relopass-fix-api-bug`**

```text
Task: Resilient source fetching (httpx timeouts/retries, per-fact try/except, abort partial corridor)
Context: A slow/failed government source can silently produce an empty fact or a partial corridor — poisoning the moat.
Goal: Resilient authoring fetches: timeouts/retries, per-fact isolation, empty/failed = NULL that aborts that fact's promotion (never persist an empty source_url).
Files: backend/app/services/ authoring fetch/parse path (httpx timeouts + backoff; per-fact try/except; NULL-on-failure); tests/
Approach: httpx with sane timeouts/retries; isolate each fact's parse; on failure log the source, skip that fact, never promote it; emit a fetch-health report. Pairs with #1940.
Test command: cd backend && pytest -q. Schema: No DB changes.
```

- **Validation:** Timeouts retried then skipped; empty fetch aborts promotion; no partial corridor persisted; never persist an empty source_url.
- **Deps:** Pairs with #1940.

### AIQ-1958 · [Data Quality] UNIQUE key + transactional writes + parameterized queries
**P1 · 🟡 Yellow → Ready for AI · Layer API · Backend Implementation · Route: `relopass-fix-api-bug`**

```text
Task: UNIQUE composite key + transactional corridor writes + parameterized queries
Context: A corridor can hold two conflicting versions of the same fact, and a promotion can partially apply. Raw string SQL is an injection + corruption risk (CS50x Lec 7).
Goal: Enforce UNIQUE(corridor:entity_id:fact_key) (re-verify = UPDATE); wrap batch promotions in BEGIN/COMMIT with locking; parameterized queries everywhere.
Files: supabase/migrations/ (UNIQUE constraint, after a dupe report); backend/app/services/ (transactional promote); backend/app/database.py (parameterized); tests/
Approach: Run a duplicate report first (human-reviewed dedupe) so UNIQUE applies cleanly; atomic transactions with row locking; replace string-concat SQL with parameters.
Test command: cd backend && pytest -q. Schema: Additive UNIQUE (needs pre-dedupe pass).
```

- **Validation:** Duplicate fact rejected by constraint; concurrent promote doesn't clobber; no raw string SQL remains.
- **Deps:** Pairs with versioning #1959.

### AIQ-1959 · [Data Quality] Version corridor specs with a changelog
**P1 · 🟡 Yellow → Ready for AI · Layer API · Backend Implementation · Route: `relopass-fix-api-bug`**

```text
Task: Version corridor specs with a changelog (rule change = new version + diff, not in-place edit)
Context: Rules change over time; HR directors need an audit trail. Today a rule change is an in-place edit with no diff/history.
Goal: Version each corridor spec like source — a rule change creates a new version + diff; prior versions stay inspectable.
Files: supabase/migrations/ (version + changelog table); backend/app/services/ (version-on-change + diff); tests/
Approach: Version table keyed by corridor + version_no; on any rule change write a new version + stored diff instead of overwriting; expose a history read. Coordinate with #1958, #1973.
Test command: cd backend && pytest -q. Schema: Additive (version/changelog table).
```

- **Validation:** Rule change yields a new version + diff; prior versions readable; no in-place overwrite.
- **Deps:** Pairs with #1958, #1973.

### AIQ-1960 · [Corridor Knowledge] Requirement embedding + cosine dedup to a review queue
**P1 · 🟡 Yellow → Ready for AI · Layer API · AI/ML Implementation · Route: `relopass-fix-api-bug`**

```text
Task: Requirement embedding + cosine dedup into a human review queue (never auto-merge)
Context: Build the graph on learned distances, not string matches — but similarity is not equivalence (MIT Lec 12), so nothing may auto-merge.
Goal: Embed each verified requirement; surface pairs above a cosine threshold as candidate duplicates into an authoring-review queue; never auto-merge; respect hard negatives.
Files: backend/app/services/ (embedding + cosine dedup pass); backend/app/models/ (vector store/column + review queue); tests/
Approach: Embed; pairwise cosine; above ~0.92 create a review-queue item; consult the hard-negative registry (#1943). Output feeds est_reuse_pct (#1961).
Test command: cd backend && pytest -q. Schema: Additive (vector store + review queue).
```

- **Validation:** Each verified requirement embedded; pairs above threshold surface as candidate duplicates to a review queue; hard-negatives excluded; nothing auto-merges.
- **Deps:** Uses #1943; feeds #1961.

### AIQ-1961 · [Corridor Knowledge] Measured corridor-reuse score (est_reuse_pct)
**P1 · 🟡 Yellow → Ready for AI · Layer API · AI/ML Implementation · Route: `relopass-fix-api-bug`**

```text
Task: Compute a measured corridor-reuse score (est_reuse_pct) feeding the demand-pull gate
Context: The '40–60% reuse' claim is qualitative. MIT Lec 12 makes reuse measurable via requirement-level distances.
Goal: est_reuse_pct per corridor pair from requirement overlap (shared-vs-total, mean cosine) + a similarity score (legal system, EEA membership, language, tax-treaty family); drive expansion sequencing; feed the demand-pull gate.
Files: backend/app/services/ (reuse-score, uses #1960 embeddings); backend/app/models/ (per-pair score); tests/
Approach: Combine embedding overlap + feature-similarity; expose components for human sanity-check; write est_reuse_pct per pair; demand-pull gate (#1944) reads it. Civil↔common-law pairs score low.
Test command: cd backend && pytest -q. Schema: Additive (per-pair score).
```

- **Validation:** est_reuse_pct computed per pair; adjacent > distant; the demand-pull gate consumes it.
- **Deps:** Uses #1960; feeds #1944.

### AIQ-1962 · [Corridor Knowledge] Reusable requirement-templates library
**P1 · 🟡 Yellow → Ready for AI · Layer API · Backend Implementation · Route: `relopass-fix-api-bug`**

```text
Task: Build a reusable requirement-templates/primitives library
Context: New corridors are largely rebuilt from scratch, forfeiting 40–60% structural reuse. The backbone (case skeleton, requirement categories) is corridor-invariant and should be shared.
Goal: A shared library of verified requirement templates corridors import by reference (one source of truth), with volatile facts kept corridor-specific.
Files: backend/app/models/ (template/primitive table + reference); backend/app/services/ (resolve references at build); tests/
Approach: Extract corridor-invariant primitives (EEA residence registration, totalization, D-number); store once; reference them; editing a template triggers sibling regression (#1963). Volatile facts never in the template.
Test command: cd backend && pytest -q. Schema: Additive (template table + references).
```

- **Validation:** A shared template library exists; corridors import by reference (not copied text); a template edit propagates + triggers regression.
- **Deps:** Ties to #1963, #1961.

### AIQ-1963 · [Corridor Knowledge] Transfer as finetuning (freeze backbone, re-verify head)
**P1 · 🔴 Red → Needs Decomposition · Layer Feature · AI/ML Implementation · Route: `notion-decomposition`**

```text
Task: Treat corridor transfer as finetuning: freeze backbone, re-verify head, never transfer volatile facts
Context: Transfer = pretraining → adaptation (MIT Lec 18). Shared representation transfers cheaply; the task-specific head must be re-learned. Silently copying volatile facts is catastrophic forgetting — a wrong answer that looks right.
Goal: Encode the discipline: reuse backbone; always re-verify head; hard-gate volatile facts (threshold/deadline/official/fee) behind lawyer verification; flag civil↔common-law transitions low-transfer; regression-check siblings on a shared-node edit.
Files: backend/app/services/ (transfer/adaptation policy); backend/app/models/ (backbone-vs-head tagging); tests/
Approach: Tag each requirement backbone|head; allow backbone reuse; block head/volatile transfer without re-verification (#1936, #1943, #1962); flag ES→IE/GB/DE low-transfer. Decompose: tagging, transfer gate, domain-shift flag, sibling regression.
Test command: cd backend && pytest -q. Schema: Additive (backbone/head tag).
```

- **Validation:** Backbone reused; head always re-verified; volatile facts hard-gated + never silently transferred; civil↔common-law flagged; shared-node edit triggers sibling regression.
- **Deps:** Uses #1943, #1962; related #1936.

### AIQ-1964 · [Corridor Knowledge] Decompose compound requirements into atomic facts
**P1 · 🟡 Yellow → Ready for AI · Layer API · Backend Implementation · Route: `relopass-fix-api-bug`**

```text
Task: Decompose compound requirements into atomic, individually-sourced facts
Context: A compound requirement stored as one blob makes verification coarse and errors hard to isolate (MIT Lec 21 compositionality).
Goal: Split compound requirements into atomic facts, each with its own source_url and deadline — the smallest unit a lawyer can sign off.
Files: backend/app/services/ (decomposition at authoring); backend/app/models/ (atomic fact + parent/depends_on link #1953); tests/
Approach: Detect conjunctions/sequencing; split into atomic facts, each independently sourced + dated; preserve relationships via depends_on edges (#1953). Pairs with #1940.
Test command: cd backend && pytest -q. Schema: Additive (atomic fact rows + links).
```

- **Validation:** Compound requirements decomposed into atomic facts; each has its own source + deadline; relationships preserved.
- **Deps:** Uses #1940, #1953.

### AIQ-1965 · [Evaluation/Metrics] Bayesian completeness + graph-health dashboard
**P1 · 🟡 Yellow → Ready for AI · Layer API · AI/ML Implementation · Route: `relopass-fix-api-bug`**

```text
Task: Bayesian corridor-completeness score + alignment/uniformity graph-health dashboard
Context: We can't yet answer 'have we captured every requirement for this corridor?' and have no graph-health monitoring to prioritize verification.
Goal: A per-corridor completeness/confidence score (Bayes-updated by verified cases + sign-offs) + an internal dashboard tracking alignment (equivalent requirements close in embedding space) and uniformity (coverage spread).
Files: backend/app/services/ (Bayesian score + alignment/uniformity, uses #1960 embeddings); frontend/src/ admin (dashboard read); tests/
Approach: Update the score as verification accumulates; compute alignment/uniformity from embeddings; surface internally to sequence verification. Internal prior, distinct from the customer relief metric (#1946).
Test command: cd backend && pytest -q. Schema: Additive (score store).
```

- **Validation:** Score rises with verified cases + sign-offs; alignment/uniformity computed from embeddings; used internally to prioritize.
- **Deps:** Uses #1960; distinct from #1946.

### AIQ-1966 · [Evaluation/Metrics] Per-subpopulation accuracy (DRO)
**P1 · 🟡 Yellow → Ready for AI · Layer API · AI/ML Implementation · Route: `relopass-fix-api-bug`**

```text
Task: Track accuracy per employee-type subpopulation (DRO), prioritize the worst-served
Context: Aggregate accuracy hides rare-but-high-stakes profiles (third-country nationals, dual citizens, stateless) being silently under-served (MIT Lec 17 subpopulation shift).
Goal: Track accuracy per employee-type subpopulation; prioritize verification toward the worst-served; log a per-case OOD-distance that turns edge cases into a prioritized backlog.
Files: backend/app/services/ (per-subpop accuracy + worst-served ranking; consume OOD-distance from #1938); tests/
Approach: Slice accuracy by employee type; rank subgroups worst-first (with sample sizes + shrinkage); route high OOD-distance cases into the backlog. Additive reporting.
Test command: cd backend && pytest -q. Schema: No DB changes (reporting).
```

- **Validation:** Per-subpop accuracy computed; worst-served ranked first; OOD-distance logged per case.
- **Deps:** Consumes #1938.

### AIQ-1967 · [Evaluation/Metrics] Attribute failed CVRs ('manual backprop')
**P1 · 🟡 Yellow → Ready for AI · Layer API · AI/ML Implementation · Route: `relopass-fix-api-bug`**

```text
Task: Attribute failed CVRs ('manual backprop') and instrument every authoring stage
Context: When a case fails verification there's no way to trace it to the stage that caused it, so fixes are vague re-runs (PyTorch: manually backprop the error).
Goal: Attribute each failure to a stage (which LLM pass, prompt framing, source); instrument every authoring stage so a wrong deadline is traceable to the rule that produced it.
Files: backend/app/services/ (per-stage trace records + attribution); backend/app/eval/ (attribution report, ties to #1945); tests/
Approach: Emit a structured trace record per stage keyed by case; on a failed CVR walk back the trace to the responsible stage/source; produce an attribution report. Sampled logging to control noise.
Test command: cd backend && pytest -q. Schema: No DB changes (tracing).
```

- **Validation:** A seeded failure attributes to the correct stage; every stage emits a trace record.
- **Deps:** Complements #1945, #1936.

### AIQ-1968 · [Evaluation/Metrics] Delta-metrics dashboard (measure the arc)
**P1 · 🟡 Yellow → Ready for AI · Layer UI · Frontend Implementation · Route: `relopass-fix-ui-bug`**

```text
Task: Delta-metrics dashboard — measure the arc, not the day (activations→verified→relief-yes→paid)
Context: The moment is 14 activations / 0 paid. CS50x Lec 10: measure the delta, not the day.
Goal: A dashboard tracking week-over-week deltas across activations → verified cases → relief-moment yes-rate → first paid.
Files: frontend/src/ admin (new delta view); analytics/funnel endpoints (read counts + relief events #1946)
Approach: Build the funnel with WoW deltas (not just absolutes); pull relief yes-rate from #1946; follow the dataviz skill for palette + chart specs. Keep the 0-paid column visible.
Test command: cd frontend && npx tsc --noEmit. Schema: No DB changes.
```

- **Validation:** Dashboard shows all four funnel stages with WoW deltas; relief yes-rate wired.
- **Deps:** Reads #1946; related #1968.

### AIQ-1969 · [Trust/Compliance] Tag conditioned-on (kill shortcut assumptions)
**P1 · 🟡 Yellow → Ready for AI · Layer API · Backend Implementation · Route: `relopass-fix-api-bug`**

```text
Task: Tag what each LLM-proposed requirement is conditioned on — kill shortcut assumptions
Context: A rule learned only from EU-passport cases (e.g. Madrid→Dublin) can masquerade as a general rule (MIT Lec 17 shortcut learning).
Goal: Tag each proposed requirement with its conditioning (nationality, employer type, city); block promotion-to-general until re-verified against a case lacking that condition.
Files: backend/app/models/ (conditioned-on tags); backend/app/services/ (promotion guard); tests/
Approach: Capture conditioning at authoring; at promotion, if tagged conditioned-on X, require a counter-case (lacking X) before it becomes general. Ties into #1936, #1938.
Test command: cd backend && pytest -q. Schema: Additive (conditioned-on tags).
```

- **Validation:** Every proposed requirement tagged with its conditioning; a copied assumption cannot become general without re-verification against a counter-case.
- **Deps:** Ties to #1936, #1938.

### AIQ-1970 · [Trust/Compliance] 'Why not ChatGPT?' trust explainer
**P1 · 🟢 Green → Ready for AI · Layer UI · Frontend Implementation · Route: `relopass-fix-ui-bug`**

```text
Task: Write the 'Why not just use ChatGPT?' trust explainer on CaseGate (AI-literacy grounded)
Context: 'Why not just use ChatGPT?' becomes a technically credible, lecturer-stated trust argument (MIT Lec 21: LLMs fall short exactly on factual-accuracy-critical applications).
Goal: A CaseGate explainer built on learning != logic, the grounding gap, factual-accuracy-critical apps, temporal snapshot rot — with deterministic engine + source attribution + lawyer sign-off as the traceable answer.
Files: frontend/src/ CaseGate component (add the explainer section)
Approach: Draft copy with relopass-brand-voice (lead with the limitation, not the brag); implement as a scannable section (headline + 3–4 points). Copy/section only, reversible.
Test command: cd frontend && npx tsc --noEmit. Schema: No DB changes.
```

- **Validation:** CaseGate carries the explainer built on the four LLM limitations with the traceable answer.
- **Deps:** —

### AIQ-1971 · [Trust/Compliance] Employee-type decision tree
**P1 · 🟡 Yellow → Ready for AI · Layer API · Backend Implementation · Route: `relopass-fix-api-bug`**

```text
Task: Encode employee-type branching as an explicit lawyer-verifiable decision tree
Context: Branch logic (EU citizen vs non-EU passport → work permit + PPS) buried in nested if/else can't be verified by a lawyer (CS50x Lec 5).
Goal: Encode branch logic as an explicit, data-driven decision tree, each path lawyer-verifiable, resolving to the correct requirement set.
Files: backend/app/models/ (decision-tree representation); backend/app/services/ (tree evaluation); tests/
Approach: Represent branches as data (not code); evaluate the tree to select the requirement set; golden tests per branch for lawyer review; keep alongside current logic until verified. Feeds #1947.
Test command: cd backend && pytest -q. Schema: Additive (decision-tree data).
```

- **Validation:** Branch logic encoded as a lawyer-verifiable decision tree; each branch resolves correctly; data-driven, not nested if/else.
- **Deps:** Feeds #1947; pairs with #1964.

### AIQ-1972 · [Trust/Compliance] Pragmatic dated actions
**P1 · 🟡 Yellow → Ready for AI · Layer API · Backend Implementation · Route: `relopass-fix-api-bug`**

```text
Task: Translate literal rules into pragmatic, dated actions ('within 3 months' → concrete deadline)
Context: The relief moment depends on concrete dates (MIT Lec 21 pragmatics): 'register within 3 months' → 'for a May 1 move, the folkeregister deadline is Aug 8'.
Goal: Compile each relative rule to a concrete date + action for the given move date; the timeline shows dated, ordered actions.
Files: backend/app/services/ (deadline resolver: deadline_offset → concrete date); tests/
Approach: Use the structured deadline_offset from #1940; compute concrete dates at serve time via a tested date utility (timezones/business days); output dated, ordered actions feeding #1976.
Test command: cd backend && pytest -q. Schema: No DB changes (uses existing offset).
```

- **Validation:** Each relative rule compiled to a concrete date + action; timeline actions dated and ordered.
- **Deps:** Uses #1940; feeds #1976.

### AIQ-1974 · [Product UX] Stage the fear→relief narrative in layout
**P1 · 🟡 Yellow → Ready for AI · Layer UI · UX Redesign · Route: `relopass-fix-ui-bug`**

```text
Task: Stage the fear→relief narrative in layout — timeline visibly fills in above the fold
Context: Relief is asserted in copy, not shown. CS50x Lec 8: make the fear→relief arc a layout — lead with the fear above the fold, resolve it visually as the timeline fills in.
Goal: A layout that names the fear above the fold, then resolves it with a timeline that fills in with flagged items; onboarding copy names the fear then reassures.
Files: frontend/src/ landing + dashboard components; frontend/src/ timeline component
Approach: Restructure heading hierarchy + CSS to stage the narrative top-to-bottom; populate the timeline with flagged items; onboarding copy via relopass-brand-voice. Keep paywall surfaces (#1951/#1999) distinct. Ship behind a flag; A/B.
Test command: cd frontend && npx tsc --noEmit. Schema: No DB changes.
```

- **Validation:** Fear above the fold; relief shown via a filling timeline; heading hierarchy + CSS stage the narrative; onboarding names the fear then reassures.
- **Deps:** Distinct from #1951/#1999.

### AIQ-1975 · [Product UX] Redesign the case-intake form
**P1 · 🟡 Yellow → Ready for AI · Layer UI · Frontend Implementation · Route: `relopass-fix-ui-bug`**

```text
Task: Redesign the case-intake form (semantic form, labeled inputs, inline validation, POST)
Context: Employee type + move date unlock the corridor, but the intake form lacks clean semantics/validation and correct verb discipline.
Goal: A clean, validated intake form: proper <form> semantics, labeled inputs, required-field + inline validation, POST for create, sensible server-side defaults.
Files: frontend/src/ case-intake form component; backend/app/routers/ intake POST handler (confirm POST + request.form.get defaults)
Approach: Rebuild with semantic form + accessible labels; inline JS validation on change/submit; ensure create is POST; graceful server-side defaults. Test all field paths.
Test command: cd frontend && npx tsc --noEmit. Schema: No DB changes.
```

- **Validation:** Proper form semantics, labeled inputs, required-field + inline validation, POST for create, server-side defaults.
- **Deps:** —

### AIQ-1976 · [Product UX] Dynamic timeline from versioned JSON  ⚠️ largely resolved
**P1 · 🟡 Yellow · Layer UI · Frontend Implementation · Route: `relopass-fix-ui-bug`**

> ⚠️ **Resolved 2026-08-19 (PR #1890).** Claims 1–2 already met in `main` — the corridor JSON resource exists (`GET /api/public/corridor-requirements`, 14/14 items sourced on ES→IE) and both timeline components have zero hardcoded corridor markup. Residual (source link per timeline item) split into a follow-up task: *"Carry requirement provenance onto relocation-plan timeline items."* Finding: `docs/findings/AIQ-1976-timeline-already-dynamic.md`.

```text
Task: Render the compliance timeline dynamically from versioned JSON corridor endpoints
Goal: Corridor requirements as versioned, cacheable JSON (corridor × employee-type → requirements[]); front end maps each to a timeline item with status + source link, server-rendered from verified facts.
Files: backend/app/routers/ (corridor JSON resource); frontend/src/ timeline component (map JSON → items); shared types
Approach: Typed JSON contract (+ backend contract test); render from it (no hand-written markup); each item shows status + source link. Consumes #1959, #1972.
Test command: cd frontend && npx tsc --noEmit + backend contract test.
```

- **Validation:** Versioned JSON resource; timeline items map from it with status + source link; server-rendered from verified facts.
- **Deps:** Follow-up: provenance/source-link per timeline item.

---

# P2 — Plan for v1 (deferred until the data threshold is real)

### AIQ-1977 · [Corridor Knowledge] Augment rare employee types around the anchor
**P2 · 🟡 Yellow → Ready for AI · Layer API · AI/ML Implementation · Route: `relopass-fix-api-bug`**

```text
Task: Augment rare employee types around the single anchor case (re-verify every variant)
Context: Thin corridors like ES→IE have one verified case (Andrea). MIT Lec 19: augment around the anchor — but every augmented variant must be re-verified before entering the graph.
Goal: Enumerate variants around the anchor (EU vs non-EU passport, dependents/pets, move-date timing); route every augmented variant AND every synthetic LLM candidate through the generator-verifier gate before it joins the graph.
Files: backend/app/services/ (anchor augmentation + candidate synthesis, candidates only); tests/
Approach: Generate variants as candidates; synthesize candidate requirements for thin corridors only; force everything through #1936's gate; nothing serves until re-verified. Andrea's ES→IE is the reference anchor.
Test command: cd backend && pytest -q. Schema: Additive (candidate variants).
```

- **Validation:** Variants enumerated around the anchor; every augmented variant + synthetic candidate re-enters the generator-verifier gate before joining the graph.
- **Deps:** Uses #1936.

### AIQ-1978 · [Architecture] Distill the v1 chatbot from the verified engine  🔒 deferred
**P2 · 🔴 Red → Needs Decomposition · Layer Feature · AI/ML Implementation · Route: `notion-decomposition`**

> 🔒 **Deferred (v1).** Do not start until: relief-moment eval harness #1945 is live, CVR corpus #1942 is accumulating, and the CVR-count threshold #1979 says a fine-tuned model beats the engine.

```text
Task: Distill the v1 employee chatbot only from the verified engine (teacher), never raw LLM output
Goal (when un-deferred): Train/distill a v1 chatbot (student) only from the deterministic engine + lawyer-verified facts + CVRs (teacher); never learn from unverified LLM output; keep the LLM-authors/engine-serves invariant (#1935) intact.
Files (future): backend/app/ml/ (distillation pipeline); eval harness #1945; CVR corpus #1942
Approach: Start only after #1979 crossover + #1945/#1942 in place. PyTorch discipline: versioned datasets, fixed seeds, one primary metric (non-obvious-flag recall vs the engine), small runnable experiments. Decompose before any code.
Test command: cd backend && pytest -q (when built).
```

- **Validation:** Student trained/distilled only from the verified engine + CVRs; never from unverified LLM output; PyTorch prototyping discipline.
- **Deps:** Gated by #1979, #1945, #1942.

### AIQ-1979 · [Evaluation/Metrics] Defensibility curve + fine-tune threshold  ✅ executed
**P2 · 🟢 Green · Task Type Research · Route: `notion-task-executor` (Cowork)**

> ✅ **Executed 2026-08-19 by autopilot (Human Review, Passed).** Deliverable: `AIQ-1979_Defensibility_Curve_Framework.md`. Framework + decision rules complete; the quantitative `N*` threshold is parameterised pending CVR data (compute method included).

```text
Task: Define the coverage×case-volume defensibility curve + fine-tune threshold + compute-optimal authoring spend
Goal: Doc that (1) defines moat = (verified corridors) × (verified cases per corridor); (2) estimates the CVR threshold where fine-tuning beats the engine; (3) recommends a breadth/depth split; (4) states the emergent-capability v1 launch gate (#1978); (5) packages the investor argument; and flags that compliance may NOT scale like language.
Approach: Reason from current numbers (3 corridors, thin CVR count); present a curve + explicit assumptions, not a false-precise number; refine as CVRs accumulate. Cowork deliverable — no repo.
Acceptance: the doc answers all 5 points with explicit assumptions.
```

- **Validation:** A power-law curve for moat strength; the fine-tune crossover estimated (engine wins until then); breadth/depth split; v1 launch gate; investor packaging.
- **Deps:** Gates #1978.

### AIQ-1980 · [Product UX] Mobile-first + accessibility polish
**P2 · 🟡 Yellow → Ready for AI · Layer UI · UX Redesign · Route: `relopass-fix-ui-bug`**

```text
Task: UX polish: mobile-first responsive dossier + compliance-grade accessibility
Context: HR generalists check status on a phone between meetings; the dossier must be legible under pressure and accessible.
Goal: Responsive single-column reflow (no horizontal scroll on mobile) for timeline/badges/CTAs; semantic HTML + AA contrast meeting WCAG 2.1 AA.
Files: frontend/src/ case dossier + timeline components; shared layout/CSS
Approach: Reflow to single column at mobile widths; semantic landmarks + alt text; contrast to AA; test at 375/768/1280/1440 with a visual diff. Run design:accessibility-review before handoff.
Test command: cd frontend && npx tsc --noEmit + accessibility-review.
```

- **Validation:** Single-column reflow, no horizontal scroll on mobile; semantic HTML + AA contrast meet WCAG 2.1 AA.
- **Deps:** —

---

# New — Authoring-pipeline gaps (P1, created 2026-08-19)

*The playbook flagged the Ziegler 5-pass and 4-Check gate as "NOT IMPLEMENTED." These four fill the authoring-machinery gap and depend on each other: schema (2020) → extraction (2022) → 5-pass (2019) → 4-Check (2021) → lawyer sign-off (#1998).*

### AIQ-2019 · [AI/ML] Ziegler 5-pass consensus authoring pipeline
**P1 · 🔴 Red → Needs Decomposition · Layer Feature · AI/ML Implementation · Route: `notion-decomposition`**

```text
Task: Ziegler 5-pass consensus authoring pipeline
Context: The playbook flags this as NOT IMPLEMENTED — the top authoring-machinery gap. Authoring is single-pass today, so candidate recall is unmeasured and lower than it should be.
Goal: Run 5 LLM passes from different framings, diff them, take the union as the candidate set, frequency-tag each item (n/5), and route the union to a lawyer-review queue. NLP/LLM accelerates authoring; a human is the only publisher.
Files: backend/app/services/ (the 5-pass runner + union/frequency logic); lawyer-review queue model + admin surface
Approach: Reuse the structured pass schema (#2020); union with frequency tags; file to the review queue (#1936). Decompose: pass runner, union/tag, review queue, admin surface, tests.
Test command: cd backend && pytest -q. Schema: Additive (candidate + review-queue tables).
```

- **Validation:** 5 framings run; outputs diffed + unioned; each candidate carries a frequency tag (n/5); every pass emits the structured schema; the union lands in the lawyer-review queue; 0 auto-publish.
- **Deps:** Depends on #2020; feeds #2021 and #1936.

### AIQ-2020 · [Data Quality] Structured authoring-pass output schema
**P1 · 🟡 Yellow → Ready for AI · Layer API · Backend Implementation · Route: `relopass-fix-api-bug`**

```text
Task: Structured authoring-pass output schema (official_guidance/actual_reality/action_required/source)
Context: Authoring passes emit unstructured text, so they can't be diffed for consensus or cleanly handed to a lawyer.
Goal: Define + enforce the structured pass schema so passes are diffable and lawyer-reviewable; reject free-form output.
Files: backend/app/models/ (pass-output schema, pydantic); backend/app/services/ (enforce on every pass result); tests/
Approach: Define the 4-field schema (+ optional notes); validate every pass output; add a field-by-field diff helper the 5-pass pipeline (#2019) uses; version the schema. Align with #1940.
Test command: cd backend && pytest -q. Schema: Additive (pass-output schema).
```

- **Validation:** Every pass output conforms to {official_guidance, actual_reality, action_required, source}; free-form rejected; two passes diffable field-by-field; schema versioned.
- **Deps:** Consumed by #2019 and #2021; aligns with #1940.

### AIQ-2021 · [Data Quality] 4-Check pre-verification gate
**P1 · 🟡 Yellow → Ready for AI · Layer API · Backend Implementation · Route: `relopass-fix-api-bug`**

```text
Task: 4-Check pre-verification gate (scoped to fact_text IS NOT NULL)
Context: NOT IMPLEMENTED. Lawyer time is scarce; candidates should pass 4 automated checks first. Scope must be fact_text IS NOT NULL (the clean authored population), not the 217 datasheet field-definition rows.
Goal: A pre-lawyer gate running 4 checks (source present+reachable; evidence_quote present+untruncated; deadline parses; schema-valid), scoped correctly, forwarding only passing candidates.
Files: backend/app/services/ (the 4-check gate: scoped query + checks); tests/
Approach: Implement the 4 checks reusing #1940 + evidence checks #1956; scope to fact_text IS NOT NULL; label failures by check; forward passers to the lawyer queue (#1998). Assert the 217 datasheet rows are excluded.
Test command: cd backend && pytest -q. Schema: No DB changes (gate logic).
```

- **Validation:** Gate runs 4 checks; scoped to fact_text IS NOT NULL, excludes the 217 datasheet rows; only passers reach the lawyer queue; failures labeled by check.
- **Deps:** Consumes #2020 + #1940 + #1956; feeds #1998.

### AIQ-2022 · [AI/ML] NLP candidate extraction from official sources
**P1 · 🟡 Yellow → Ready for AI · Layer API · AI/ML Implementation · Route: `relopass-fix-api-bug`**

```text
Task: NLP candidate extraction from official sources (lovdata/CLEISS/NAV) — never auto-publish
Context: Authoring pulls candidates from official sources by hand. CS50 AI: NLP/tokenization/attention extraction should accelerate authoring — but it never auto-publishes; every candidate routes through lawyer verification.
Goal: An extraction step that produces candidate requirements + verbatim quotes from lovdata/CLEISS/NAV.no and files them as candidates into the generator-verifier gate.
Files: backend/app/services/ (extraction: fetch via #1957 → extract → candidate + verbatim quote); tests/
Approach: Use resilient fetching (#1957); extract candidates with a required verbatim source quote (UTF-8, untruncated — #1956); file as candidates only (unservable) into the gate (#1936); log + skip failures. Feeds the 5-pass pipeline (#2019).
Test command: cd backend && pytest -q. Schema: Additive (candidate rows).
```

- **Validation:** Extraction yields candidates each with a verbatim quote + source_url; every candidate enters the gate (#1936) as unservable; nothing auto-publishes; failures logged + skipped.
- **Deps:** Uses #1957, #1956; feeds #2019 / #1936.

---

## Appendix A — Related playbook tasks already executor-ready in Notion

These were already well-formed before this pass — pull them by ID in Claude Code (they carry their own briefs). Not reproduced above to avoid drift.

| ID | Title | Priority · Tier · Status |
|---|---|---|
| AIQ-1981 | [AI/ML] Non-obvious-requirement recall vs a lawyer HLP baseline | P0 · Otto ready |
| AIQ-1982 | [AI/ML] Corridor-import idempotency (double-import regression test) | P0 · Otto ready |
| AIQ-1984 | [AI/ML] Prove the full LLM→verify→serve→eval loop on ONE case (Andrea ES→IE) | P0 · Otto ready |
| AIQ-1985 | [AI/ML] Per-requirement verified_at + freshness metric + staleness queue | P0 · Otto ready |
| AIQ-1996 | relief_moment_response eval gate | P0 · 🔴 Red · Ready for AI |
| AIQ-1998 | Enforce the lawyer sign-off gate on every corridor fact before it serves | P0 · 🔴 Red · Ready for AI |
| AIQ-1999 | Rewrite the roadmap paywall value statement (fear→relief) | P1 · 🟡 Yellow · Ready for AI |

## Appendix B — Merged / archived duplicates (2026-08-19)

Consolidated to remove overlap; content folded into the survivor. Un-archive in Notion to restore.

| Archived | → Merged into | What was folded in |
|---|---|---|
| AIQ-1986 | AIQ-1935 | Code-level "fail the build if any serving path reaches an LLM" enforcement + MIT/AI-Dev-26 sources |
| AIQ-1983 | AIQ-1936 | Verified-write guardrail (only a human flips representative→verified; hard-fail programmatic attempts; audit-log the flip) |
| AIQ-1997 | AIQ-1942 | Exact CVR field set + the fine-tuning export path |

*Distinct, both kept: AIQ-1951 (CaseGate paywall) vs AIQ-1999 (roadmap paywall) — different surfaces, not merged.*

---

*Snapshot generated 2026-08-19 from the ReloPass AI Work Queue. The `AIQ-####` ids are the live source of truth — prefer running `relopass-autopilot` / `relopass-dev-queue` in Claude Code so status and results sync back to Notion. Re-generate this file if the queue drifts.*

