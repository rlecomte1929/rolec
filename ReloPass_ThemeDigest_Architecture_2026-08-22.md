# Theme Digest — Architecture (PROOF SLICE for T2 / AIQ-2084)

**Date:** 2026-08-22 · **Author:** Claude (Cowork) · **Owner:** Romain
**Theme 1 of 7** (per T2): *generator–verifier separation, deterministic serving, LLM-vs-rule-engine.*
**Purpose:** demonstrate the **Armed Card** contract from `ReloPass_Theory_to_Product_Engineering_Plan_2026-08-22.md` §4 on a real theme — turning parked, theory-backed cards into executable intent a `relopass-dev-queue` / `relopass-fix-*` agent can build with no follow-up questions.

> **Provenance note (honest).** The *engineering artifacts* below (acceptance criteria, eval metrics, test sketches, decompositions) are authored by Cowork from (a) the AIQ card text, (b) the real `rolec` services I inspected, and (c) well-established systems/ML/CS theory the named courses teach. Per T1's rule, engineering artifacts assert nothing about the world, so this is sound. **Where a card would change a *served relocation fact*, the grounding claim must still be Tier-1 (verbatim) — flagged inline as `[needs Tier-1]`.** Otto should relay the verbatim corpus claims over the bridge to fill those.

---

## Theme overview — the claims that ground this theme

| Claim (theme spine) | Typical source | Tier | Grounds / inspires |
|---|---|---|---|
| Separate a **generator** (proposes) from a **verifier** (gates); never ship generator output unverified | ML systems design; MLOps spec | inspires code | inspires |
| **Build the eval/overfit one example** before scaling the system ("overfit a single batch") | Ng, deep-learning practice | inspires code | inspires |
| **Deterministic serving** beats an LLM in the hot path for correctness-critical output | MLOps; systems | inspires code | inspires |
| A dependency structure is a **DAG** → topological order + cycle detection | CS50 / algorithms | inspires code | inspires |
| **Distillation** copies the teacher's behaviour — so the teacher must be trustworthy | 6.7960 / DL | inspires code | inspires |

None of these ground a *served relocation fact*, so all are safe to compile from now. The corridor facts they help serve (Andrea's ES→IE case) are separately Tier-1 and already verified in the ES→IE batch.

## Theme → card map (8 cards, all AIQ-1936–1985)

| AIQ | Title (short) | Status now | Tier | Layer | Retires to |
|---|---|---|---|---|---|
| **1984** | Prove full LLM→verify→serve→eval loop on ONE case (Andrea ES→IE) | Otto ready · **P0** | 🔴* | AI/ML | **spearhead** |
| 1936 | Generator–verifier gate: no LLM candidate ships unverified | Parked · P2 | 🔴 | AI/ML+API | invariant |
| 1937 | Corridor compile/validate build step — only verified corridors serve | Parked · P2 | 🔴 | Feature | build step |
| 1938 | OOD gate before a timeline — verify corridor/nationality/employee-type; degrade visibly | Parked · P2 | 🔴 | API | serving gate |
| 1953 | Typed knowledge graph + topological sort + cycle detection | Human Review · P1 | 🟡 | Backend | graph model |
| 1954 | Cache compiled corridor + explicit invalidation on rule change | Parked · P2 | 🟡 | Perf | cache |
| 1955 | O(1) serving: compound index + denormalized view + scale audit | Parked · P2 | 🟡 | Perf | index |
| 1978 | Distill v1 chatbot only from the verified engine (teacher) | Parked · P2 | 🔴 | AI/ML | distillation |

*1984 decomposes into 🟡 and 🔴 subtasks (below); the card as a whole is gated by its 🔴 legs.

---

## Armed cards

### AIQ-1984 — Prove the full loop on ONE case (Andrea ES→IE) — **P0 spearhead**

- **Claim provenance:** "overfit one example before scaling" (inspires). The Andrea corridor facts are Tier-1 (ES→IE verified batch).
- **Layer / entry points:** end-to-end. `immigration_answer_engine.py` (generate) → `factual_verifier.py` + `staging_review_service.py` → `review_queue_service.py` (verify/gate) → `requirements_builder.py` + `requirements_sufficiency.py` + `applies_to_matcher.py` (serve) → `rag_eval_reports.py` + PostHog (eval). Fixture: `docs/esie-andrea-golden-fixture.md`.
- **Acceptance criteria:** For persona *Andrea — Spanish (EEA) national, Madrid→Dublin, professional*: (1) a candidate fact is *generated* and lands in `otto_staging` only; (2) it cannot reach serving without passing the verifier + a human flip; (3) once approved, the served roadmap asserts the 17 `audience_scope` rules for an EEA mover and **never** asserts she needs a work visa / is exempt from Emergency Tax; (4) the eval harness records this exact case as PASS and computes non-obvious recall for ES→IE.
- **Eval metric:** golden-fixture pytest = green; `non_obvious_recall(ES-IE, professional)` computed and stored in `rag_eval_reports.py`; PostHog `relief_moment_response` fires for the Andrea walk.
- **Test sketch:** `tests/e2e/test_andrea_esie_full_loop.py` — one test per leg (generate→stage, verify-gate blocks unverified, serve-correctness on the fixture, eval-records-pass).
- **Autonomy tier:** 🔴 overall (serving + verify legs); 🟡 for the fixture/eval legs.
- **Decomposition:** 5 atomic subtasks below.
- **Bridge routing:** Cursor generates the pytest + serving assertions from the context bundle; Claude Code applies + dry-runs against prod ES→IE rows; Cowork verifies the served output independently.

**Decomposition of 1984 → 5 atomic, independently-testable subtasks**

| # | Subtask | Layer | Tier | Depends on | Acceptance (binary) |
|---|---|---|---|---|---|
| **1984.1** | Freeze the Andrea ES→IE golden fixture as an executable pytest (the eval target) | AI/ML · test | 🟡 | — | `pytest tests/e2e/test_andrea_esie_fixture.py` runs; encodes persona + `expected_served_rules` + `must_not_assert`; currently xfail (nothing wired yet) |
| **1984.2** | Generator leg: Andrea candidate produced by `immigration_answer_engine`, staged to `otto_staging`, never served | AI/ML | 🟡 | 1984.1 | candidate row exists in `otto_staging`; `requirements_builder` returns 0 unverified for Andrea |
| **1984.3** | Verifier gate: `factual_verifier` + human flip required; reject any fact missing `source_url`/`evidence_quote` | API · Data | 🔴 | 1984.2 | an unverified candidate cannot become `verified` except via the human transition (AIQ-1983 guardrail); test proves the block |
| **1984.4** | Serving leg: served roadmap correct for an EEA mover (`audience_scope` shown; `conditional`/nationality never mis-asserted) | API | 🔴 | 1984.3 | fixture assertions (3) pass; `check_serving_llm_isolation` stays green (no LLM in serving path) |
| **1984.5** | Eval leg: record loop PASS + compute `non_obvious_recall(ES-IE)`; wire PostHog relief signal | AI/ML | 🟡 | 1984.4 | `rag_eval_reports` row written; recall number present; PostHog event on the Andrea walk |

Ship order: **1984.1 → 1984.2 → 1984.5 (harness) can proceed while 1984.3/1984.4 (🔴, gated) wait for review.** The harness is buildable now with zero serving risk — which is why it's the Phase-0 bundle below.

### AIQ-1936 — Generator–verifier gate (invariant)
- **Claim:** never ship generator output unverified (inspires). **Layer:** AI/ML+API, `staging_review_service.py`, `factual_verifier.py`, write path into `requirement_facts`.
- **Acceptance:** any code path that writes `verification_status='verified'` without a recorded human action fails a guard + a test. **Eval:** a `pytest` asserting the guard rejects a synthetic auto-verify. **Test sketch:** `tests/unit/test_no_autoverify_guardrail.py`. **Tier:** 🔴. **Decomp:** atomic. **Routing:** Cursor generates guard+test; Claude Code applies. Overlaps AIQ-1983 (make it one guardrail, two tests).

### AIQ-1937 — Corridor compile/validate build step
- **Claim:** only lawyer-verified corridors serve (inspires). **Layer:** Feature, `corridor_registry.py` + `corridor_persistence.py`; a new `compile_corridor()` producing a validated, immutable served artifact.
- **Acceptance:** a corridor with any `review_status != approved` fact cannot be compiled into the served set; compile emits a manifest (fact ids + versions). **Eval:** pytest — a corridor with 1 pending fact fails compile. **Test sketch:** `tests/unit/test_corridor_compile_gate.py`. **Tier:** 🔴. **Decomp:** (a) compile function, (b) validation gate, (c) served-set swap. **Routing:** Cursor generates; Claude Code applies; pairs with 1954/1955.

### AIQ-1938 — OOD gate before a timeline
- **Claim:** verify corridor/nationality/employee-type is in-distribution; degrade visibly if not (inspires). **Layer:** API, extend the **existing** `roadmap_confidence_gate.py` + `requirements_sufficiency.py`. **`[needs Tier-1]`** for the exact "outside verified zone" copy shown to a mover.
- **Acceptance:** for an unsupported (corridor, nationality, employee_type) tuple, the API returns a visible "outside my verified zone" state, never a fabricated timeline. **Eval:** pytest on an OOD tuple returns the degraded state; PostHog logs OOD hits. **Test sketch:** `tests/unit/test_ood_gate_degrades.py`. **Tier:** 🔴. **Decomp:** (a) in-distribution check over the compiled set, (b) degraded response, (c) UI surface (pairs 1939). **Routing:** Cursor generates the gate + test; Claude Code applies.

### AIQ-1953 — Typed knowledge graph + topological sort + cycle detection (in Human Review)
- **Claim:** a roadmap is a DAG; type it, sort it, detect cycles (inspires). **Layer:** Backend, `policy_context_graph_service.py`, consumed by `roadmap_builder.py`.
- **Acceptance:** `depends_on` edges form a typed graph; a topological order is produced; an injected cycle raises a detectable error (not a silent bad roadmap). **Eval:** pytest — a 3-node cycle is detected; a valid DAG yields a stable topo order. **Test sketch:** `tests/unit/test_corridor_dag_toposort.py`. **Tier:** 🟡. **Decomp:** atomic (it's already in Human Review — likely needs the test + cycle case to close). **Routing:** Cursor generates toposort+cycle test; Claude Code applies. **Fast win — closest to Done.**

### AIQ-1954 — Cache compiled corridor + invalidation
- **Claim:** deterministic served artifacts should be cached with correct invalidation (inspires). **Layer:** Perf, cache layer over `requirements_builder.py`/`corridor_registry.py`; invalidate on rule/version change (`plan_versions_service.py`, `rule_change_notifier.py` exist).
- **Acceptance:** repeated serve of an unchanged corridor hits cache; any fact/version change invalidates before next serve (no stale served fact ever). **Eval:** pytest — change a fact → next serve reflects it; cache-hit metric present. **Test sketch:** `tests/unit/test_corridor_cache_invalidation.py`. **Tier:** 🟡. **Decomp:** (a) cache key = compile manifest hash, (b) invalidation hook. **Routing:** Cursor; Claude Code applies. Depends on 1937.

### AIQ-1955 — O(1) serving: compound index + denormalized view
- **Claim:** correctness-critical serving must be O(1) and audited at scale (inspires). **Layer:** Perf + DB migration: compound index `(corridor_id, entity_id, fact_key, employee_type)` + a denormalized served view; `requirements_builder.py` reads the view.
- **Acceptance:** the hot serve query uses the index (EXPLAIN shows index scan, no seq scan); p95 serve latency < 50 ms at 10× current row count. **Eval:** a scale-audit script + an EXPLAIN assertion test. **Test sketch:** `tests/perf/test_serving_index_plan.py` + `scripts/scale_audit_serving.py`. **Tier:** 🟡 (additive migration; append-only). **Decomp:** (a) migration, (b) view, (c) builder read-path swap, (d) scale audit. **Routing:** Cursor generates migration+view+audit; Claude Code applies via `apply_migration` dry-run.

### AIQ-1978 — Distill v1 chatbot only from the verified engine
- **Claim:** distillation copies the teacher — so the teacher must be the verified engine, never raw LLM (inspires). **Layer:** AI/ML, `immigration_answer_engine.py` as teacher; a distillation dataset built only from verified served outputs.
- **Acceptance:** the distillation dataset builder rejects any example whose source is not a `verified`+`approved` served fact. **Eval:** pytest — a raw-LLM example is excluded from the training set. **Test sketch:** `tests/unit/test_distill_teacher_verified_only.py`. **Tier:** 🔴 (defines what trains a shipped model). **Decomp:** (a) dataset builder from served-verified only, (b) exclusion guard+test. **Routing:** Cursor generates; Claude Code applies. Gated — deferred until 1984 proves the loop.

---

## Phase-0 bridge-ready CONTEXT BUNDLE — subtask 1984.1 (freeze the fixture)

The safest first buildable unit: test-only, 🟡, zero serving risk, and it's the eval the whole loop is measured against ("build the eval first").

```json
{
  "direction": "otto_to_claude",
  "kind": "record",
  "source": "cowork_via_relay",
  "payload": {
    "subtype": "context_bundle",
    "task_id": "1984.1:ES-IE:2026-08-22",
    "correlation_id": "arm-arch-1984-1-2026-08-22",
    "corridor": "ES-IE",
    "schema_version": "1.0",
    "governance": "test_only_no_serving_change",
    "goal": "Freeze the Andrea ES->IE golden fixture as an executable pytest that encodes persona + expected_served_rules + must_not_assert; land it xfail until legs 1984.2-1984.4 wire it.",
    "entry_points": [
      "docs/esie-andrea-golden-fixture.md",
      "tests/e2e/ (new: test_andrea_esie_fixture.py)",
      "backend/app/services/requirements_builder.py (read-only ref: serves approved only)",
      "backend/app/services/applies_to_matcher.py (read-only ref: nationality_scope_basis / audience_scope)"
    ],
    "fixture": {
      "persona": "Andrea — Spanish (EEA) national, Madrid -> Dublin, professional, direct employee",
      "expected_served_rules": ["the 17 ES->IE audience_scope rules that apply to any mover on this corridor [needs Tier-1: exact list from Otto's ES-IE verified batch]"],
      "must_not_assert": [
        "Andrea (EEA) needs an employment permit / work visa",
        "Andrea is exempt from Irish Emergency Tax because she is EEA",
        "any nationality_determined rule mis-applied to an EEA mover"
      ]
    },
    "acceptance": "pytest collects and runs test_andrea_esie_fixture.py; assertions reference the fixture file; test is xfail/skip with a clear reason until 1984.4 lands; NO change to any serving or DB code in this subtask.",
    "output_contract": "unified diff adding tests/e2e/test_andrea_esie_fixture.py + a prediction {files_touched:[that one test file], serving_changed:false, db_changed:false, expected_pytest: '1 xfailed'}",
    "reply_with": ["diff", "prediction"]
  }
}
```

**Loop for this bundle:** Otto relays it → Cursor generates the test diff + prediction → Claude Code dry-runs (`pytest --collect-only`, confirms `serving_changed:false`, `db_changed:false`) → applies on a branch → Cowork confirms the fixture's `must_not_assert` list matches the live ES→IE `audience_scope` reality. Then 1984.2 unblocks.

---

## Manifest (this proof slice)

- Files: `ReloPass_ThemeDigest_Architecture_2026-08-22.md` (this file), companion `ReloPass_Theory_to_Product_Engineering_Plan_2026-08-22.md`.
- Cards armed: **8** (AIQ-1936, 1937, 1938, 1953, 1954, 1955, 1978, 1984).
- Decompositions: **1** (AIQ-1984 → 5 atomic subtasks).
- Bridge bundles: **1** (subtask 1984.1, test-only).
- Themes remaining for Phase 1: **6** (Transfer Learning, Data Quality, Human-in-Loop, Scaling Laws, Trust Architecture, Relief Moment).
