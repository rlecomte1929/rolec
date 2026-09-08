# ReloPass — Phase A Execution Pack: Close the ES→IE Loop

**Date:** 2026-08-22 · **Author:** Claude (Cowork) · **Owner:** Romain
**Direction chosen:** depth-first — drive ONE corridor to correctly-served + eval-green + gated, before scaling arming.
**Anchor:** AIQ-1984 (prove the full loop on Andrea's ES→IE). Retiring it drags **AIQ-1938 / 1969 / 1971 / 1972** with it.
**Companions:** `ReloPass_Theory_to_Product_Engineering_Plan_2026-08-22.md` · `ReloPass_ThemeDigest_Architecture_2026-08-22.md`.

---

## 0. The plan on a page

**Goal:** persona *Andrea — Spanish (EEA) national, Madrid→Dublin, professional/direct employee* gets a served roadmap that is **correct**, proven by a green golden-fixture eval, behind the human gate.

**What I found reading the live serving path (this changes the plan):**
- `applies_to_matcher.py` (**shipped today**) already gates applicability correctly: `audience_scope` rules reach everyone on the corridor (incl. EEA), `nationality_determined` rules gate by CLASS via `nationality_class.classify_best`, and it **fails open** on unknowns (the anti-silence contract). → *The "EEA mover told she needs a work permit" mis-serve is already prevented at the applicability layer.*
- `requirements_sufficiency.compute_requirements_sufficiency` (**shipped today**) already carries `assertion_mode`, `conditional_on`, `non_obvious` out to the caller — and its own comment says *"it is the rendering layer's job to present it conditionally."* → **The remaining mis-serve (Emergency-Tax "you're exempt" stated flatly) is a RENDERING gap, not a data gap.**
- `roadmap_confidence_gate.py` gates the *AI* roadmap fail-closed (HIGH only); the deterministic path fails open. → **1938's job is to unify these into one visible "outside my verified zone" degrade**, so an OOD tuple neither fabricates nor silently empties.

**Build order (🟡 builds now, 🔴 waits for your gate):**

| # | Card | What's actually left | Tier |
|---|---|---|---|
| 1 | **1984.1** freeze the Andrea fixture | create the fixture doc + pytest (neither exists yet) | 🟡 now |
| 2 | **1969** render conditionals | frontend renders `conditional`/`non_obvious`; never a flat assertion | 🔴 |
| 3 | **1938** OOD visible degrade | unified in-distribution check + "outside verified zone" state | 🔴 |
| 4 | **1971** employee-type tree | populate snapshot fields + scope facts + explicit tree | 🟡→🔴 |
| 5 | **1972** dated actions | "within 90 days" → a real date from the move date | 🟡 |
| 6 | **1984.4** = the above, green on the fixture | integration — no new logic, just proof | 🔴 |
| 7 | **1984.2 / .3 / .5** generator · verify · eval | stage candidate; verifier gate; record recall + relief | 🟡/🔴 |

**The efficiency:** 1984.4 is not separate work — it is cards 2–5 validated on Andrea. One PR retires five cards.

---

## 1. The four armed serving-correctness cards

### AIQ-1969 — Tag/condition every requirement (render the conditional) — **the live gap**
- **Claim provenance:** "tag what each requirement is conditioned on — kill shortcut assumptions" (inspires).
- **Layer / entry points:** *data layer DONE.* Gap = rendering. `requirements_sufficiency.py` emits `assertion_mode`/`conditional_on`/`non_obvious` in `supporting_requirements`; the frontend consumer + `roadmap_requirement_copy.py` must render them. 
- **Acceptance:** for Andrea, a `conditional` fact (e.g. Emergency-Tax exemption *conditioned on* PPS number + correct employer registration) renders **with its condition** and is **never** shown as "you are exempt"; `non_obvious=true` facts get an "easy-to-miss" treatment.
- **Eval metric:** golden-fixture assertion — `conditional facts rendered conditionally / total = 100%`; `0` conditionals rendered as flat assertions.
- **Test sketch:** `tests/e2e/test_andrea_esie_fixture.py::test_conditional_facts_render_conditionally` + unit test on the serializer.
- **Tier:** 🔴 (served-content correctness). **Decomp:** (a) serializer carries the 3 fields to FE, (b) FE renders conditional + trap, (c) fixture assertion. **Routing:** Cursor generates FE + tests → Claude Code branch+PR.

### AIQ-1938 — OOD gate + visible degrade
- **Claim provenance:** "verify corridor/nationality/employee-type in-distribution; degrade visibly" (inspires). `[needs Tier-1]` for the exact user-facing "outside my verified zone" copy.
- **Layer / entry points:** extend `roadmap_confidence_gate.py`; add an in-distribution check over the approved/compiled set callable from `requirements_sufficiency.py`. Unify the fail-closed (AI) / fail-open (deterministic) split into one **visible degrade**.
- **Acceptance:** an unsupported (corridor, nationality-class, employee-type) tuple returns a visible "outside my verified zone" state — never a fabricated timeline, never a silent empty; Andrea (in-distribution) returns the full roadmap.
- **Eval metric:** pytest OOD tuple → degraded state; PostHog logs OOD-hit rate.
- **Test sketch:** `tests/unit/test_ood_gate_degrades.py`. **Tier:** 🔴. **Decomp:** (a) in-distribution check, (b) degraded payload, (c) UI surface (pairs AIQ-1939). **Routing:** Cursor → Claude Code.

### AIQ-1971 — Employee-type branching as an explicit, lawyer-verifiable tree
- **Claim provenance:** "encode employee-type branching as an explicit decision tree" (inspires).
- **Layer / entry points:** `apply_applies_to` already lists `status`/`employee_profile` as targeting keys but they're **no-ops until the snapshot carries them**. Gap: (a) populate `employee_profile`/`status` in `build_profile_snapshot` (`guidance_pack_service.py`), (b) scope ES→IE facts by employee-type where the law differs (CSEP vs General Employment Permit vs intra-company), (c) make the branching an enumerable structure, not scattered conditionals.
- **Acceptance:** Andrea (professional/direct) sees the professional branch; a different employee-type sees a different, correct branch; the tree is enumerable for lawyer review.
- **Eval metric:** pytest across 2–3 employee-types on the ES→IE fixture; each gets the lawyer-confirmed rule set.
- **Test sketch:** `tests/unit/test_employee_type_tree_esie.py`. **Tier:** 🟡 (structure) → 🔴 (the ES→IE scoping content). **Decomp:** (a) snapshot fields, (b) tree structure, (c) fact scoping — **needs Otto Tier-1**. **Routing:** Cursor builds tree+test; Otto relays employee-type scoping; Claude Code applies.

### AIQ-1972 — Literal rule → pragmatic, dated action
- **Claim provenance:** "translate 'within 3 months' → a concrete deadline" (inspires).
- **Layer / entry points:** `roadmap_builder.py` / `timeline_service.py` / `roadmap_lead_times.py`; consume `conditional_on` + the move date.
- **Acceptance:** for Andrea with a move date D, a "register within 90 days" rule renders as a dated action ("by <D+90d>"), not the literal text.
- **Eval metric:** pytest — given D, action date == D + offset; `0` literal-only deadlines in the served roadmap.
- **Test sketch:** `tests/unit/test_dated_actions_esie.py`. **Tier:** 🟡 (deterministic date math). **Decomp:** (a) offset extraction, (b) date computation, (c) render. **Routing:** Cursor → Claude Code.

---

## 2. AIQ-1984.1 — the fixture (create it; it does not exist yet)

`docs/esie-andrea-golden-fixture.md` is **absent** — so 1984.1 creates both the human-readable spec and the pytest.

- **Spec (`docs/esie-andrea-golden-fixture.md`):** persona Andrea; `expected_served_rules` = the ES→IE `audience_scope` rule set `[needs Tier-1 list from Otto]`; `must_not_assert` = { "needs an employment permit / work visa", "unconditionally exempt from Irish Emergency Tax", "any `nationality_determined` non-EEA rule leaking to an EEA mover" }.
- **Test (`tests/e2e/test_andrea_esie_fixture.py`):** loads the spec, xfail until cards 2–5 land. **No serving/DB change in 1984.1.**

---

## 3. PROMPT O — paste into a NEW Otto chat

```
ROLE — You are Otto: Researcher + Bridge Originator + Progress Keeper for ReloPass Phase A
(close the ES→IE serving loop, depth-first). You never touch rolec or the ReloPass DB — Claude
Code does. You relay Tier-1 facts + context onto the otto-claude-bridge, pull Claude Code's
receipts, and keep the progress board.

BRIDGE (secret in the x-hook-secret header on every call; never print it):
- Execute URL: https://audos.com/api/hooks/execute/workspace-776786/otto-claude-bridge
- push {direction, kind, payload, source:"otto"} -> {ok,id}; pull {direction, sinceId?, limit?}
  -> {ok,rows} (pending, id>sinceId); ack {ids:[…]} -> {ok,updated}
- directions: otto_to_claude (you send), claude_to_otto (you read Claude Code)
- kind enum ["message","record","manifest"] — "record" for structured, "manifest" for fact
  batches, "message" for status. "receipt" is rejected 400.

TASK 1 — Relay the ES→IE Tier-1 rule set for the golden fixture (kind record, subtype
"fixture_facts"): the exact list of ES→IE audience_scope rules that apply to any mover on the
corridor, AND, for AIQ-1971, the employee-type scoping (which facts differ for professional /
CSEP vs General Employment Permit vs intra-company). Use your VERIFIED ES→IE batch — do not
re-generate. Each rule: {fact_key, fact_text, applies_to{nationality_scope_basis, assertion_mode,
conditional_on?, non_obvious}, source_url, evidence_quote, employee_type_scope?}. correlation_id
you generate; governance "staging_only".

TASK 2 — Stand by for WORKLISTs from Claude Code (claude_to_otto): any fact needing re-sourcing,
a needs_lawyer_review item, or an employee-type scoping gap for 1971. Re-research and reply
(kind record, echo correlation_id + in_reply_to).

PROGRESS BOARD (required): one row per task_id [task_id | phase | status | PUSH_ID | receipt |
key_result | gate], status queued→pushed→awaiting_receipt→received→blocked→done. Persist to
otto.md → "My Plan" → "ES-IE Phase A". Post a one-line STATUS (kind message) at each milestone.
Report the board to Romain at each phase boundary.

GOVERNANCE: staging_only; you never request promotion; nothing serves unreviewed. START: run
TASK 1 now, report PUSH_IDs + board to Romain, then poll claude_to_otto.
```

## 4. PROMPT C — paste into Claude Code (rolec session)

```
ROLE — You are Claude Code, the runner for ReloPass ES→IE Phase A: close the serving loop
(AIQ-1984), depth-first. Otto relays Tier-1 facts + context on the otto-claude-bridge; you build,
test, and stage. Use relopass-dev-queue for the serving code and relopass-corridor-transfer for any
staging. The bridge is the intake, not a replacement for the skills.

BRIDGE: secret in ~/.otto-bridge-secret (chmod 600) -> x-hook-secret header; never print. Execute
URL https://audos.com/api/hooks/execute/workspace-776786/otto-claude-bridge. push/pull/ack as
usual. READ otto_to_claude; REPLY on claude_to_otto (kind "record", echo correlation_id +
in_reply_to). ReloPass Supabase project: nsvefcvpvwwwhuqyuqmp.

BUILD SEQUENCE (one branch: audit/stage-esie-serving-loop; 🔴 = do NOT merge, hand Romain the diff):
1. AIQ-1984.1 — create docs/esie-andrea-golden-fixture.md (persona Andrea; expected_served_rules
   from Otto's fixture_facts relay; must_not_assert: needs work permit / unconditionally exempt
   from Emergency Tax / any nationality_determined non-EEA rule reaching an EEA mover) + a pytest
   tests/e2e/test_andrea_esie_fixture.py (xfail until step 6). NO serving/DB change here.
2. AIQ-1969 — render conditionals: the serializer already emits assertion_mode/conditional_on/
   non_obvious from requirements_sufficiency.py; make the frontend + roadmap_requirement_copy.py
   render a conditional fact WITH its condition (never "you are exempt") and flag non_obvious as an
   easy-to-miss trap. TDD against the fixture.
3. AIQ-1938 — OOD gate: extend roadmap_confidence_gate.py + add an in-distribution check over the
   approved set callable from requirements_sufficiency.py; an unsupported (corridor, nationality-
   class, employee-type) tuple returns a visible "outside my verified zone" state, never a fabricated
   timeline nor a silent empty. Andrea stays in-distribution.
4. AIQ-1971 — employee-type tree: populate employee_profile/status in build_profile_snapshot
   (guidance_pack_service.py); scope ES→IE facts by employee-type per Otto's relay; make the
   branching enumerable. If scoping is missing, push a WORKLIST to Otto and continue.
5. AIQ-1972 — dated actions: in roadmap_builder.py/timeline_service.py, turn "within N days"
   (conditional_on / rule text) into a real date from the move date.
6. AIQ-1984.4 — flip the fixture from xfail to green: Andrea shows the audience_scope rules,
   conditionals render conditionally, non_obvious flagged, deadlines dated, and NONE of the
   must_not_assert items appear. Keep check_serving_llm_isolation AND check_route_auth green.
7. AIQ-1984.2/.3/.5 — stage the Andrea candidate to otto_staging (never served); prove the verifier
   gate blocks an unverified/human-flip-required fact (AIQ-1983 guardrail); record loop PASS +
   non_obvious_recall(ES-IE, professional) in rag_eval_reports.py; wire the PostHog relief signal.

For each step push an apply_report (kind record) with the branch/commit SHA + test results; ack the
row. GOVERNANCE: branch+PR only (no direct main merge); write only otto_staging for data; promotion
to public.requirement_facts and the representative→verified flip are Romain/lawyer gates — never
auto-fire. START: pull otto_to_claude for Otto's fixture_facts, build step 1, report to Romain.
```

---

## 5. What only you (Romain) unblock in Phase A

- **The Tier-1 `audience_scope` rule list** for the fixture (Otto relays it, but confirm it's the verified ES→IE set) — the fixture's `must_not_assert` is only as good as the real rule set behind it.
- **Merge the serving-correctness PR** (🔴) once the fixture is green and you've read the diff.
- **The lawyer/promote gate** for any ES→IE fact that must flip `representative → approved` to serve.
- **Optional ride-along:** AIQ-1940 (P0, "Needs Human Clarification") — a two-line answer on the `requirement_fact` schema frees the Data-Quality lane to move next to this.

## 6. Definition of done — Phase A

- `tests/e2e/test_andrea_esie_fixture.py` **green**.
- Andrea's served roadmap: shows the `audience_scope` rules, renders conditionals *conditionally*, flags `non_obvious` traps, **dates** the deadlines, and **never** asserts she needs a visa or is unconditionally tax-exempt.
- `non_obvious_recall(ES-IE, professional)` computed + stored in `rag_eval_reports.py`.
- `check_serving_llm_isolation` + `check_route_auth` green (no LLM in the serving path).
- AIQ-1984 **and** 1938 / 1969 / 1971 / 1972 → **Human Review**, artifact = the PR + the green fixture. **Five cards retired in one loop.**

Then, and only then, Phase B: scale arming across the remaining themes with this battle-tested template.
