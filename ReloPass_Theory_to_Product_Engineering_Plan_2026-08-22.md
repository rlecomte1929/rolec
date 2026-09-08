# ReloPass — Theory→Product Engineering Plan (continuing Otto's ticket #115842)

**Date:** 2026-08-22 · **Author:** Claude (Cowork) · **Owner:** Romain
**Continues:** Otto ticket #115842 → cards **T1** (AIQ-2083, re-materialize 37 course analyses) and **T2** (AIQ-2084, 7 theme digests arming AIQ-1936–1985 / 2018–2022).
**Built on:** the proven `otto-claude-bridge` (self-test PASSED 2026-08-22) and the `ReloPass_Otto_Claude_Tandem_Execution_Plan`.
**Scope chosen with Romain:** *full theory→product pipeline* — carry the 47 learnings all the way to shipped ReloPass behaviour, not another shelf of markdown.

---

## 0. TL;DR

Otto has built a **large, high-quality theory corpus** (47 analyses: 37 courses + 10 books) and pre-wired it to **~55 engineering cards** (AIQ-1936–1985, 2018–2022). But look at the board: **39 of the 50 cards in the 1936–1985 family are `Parked`.** The theory landed; the product didn't. That is the same failure the bridge self-test named for corridors — *"research piles up as files and stalls before it becomes served product behaviour"* — now repeating one layer up, for *learnings*.

T1 and T2 as written produce **more documents**. The higher-value move is to treat the corpus as **source code for the product** and stand up a **Learning Compiler**: a pipeline that takes an analysis and emits, at the far end, a *merged PR + a promoted-to-pending DB change + a green eval*, through the Generator–Relay–Applier loop you already proved. T2 stops being "a digest" and becomes "**a spec that compiles to a `relopass-dev-queue` task**."

This plan (a) re-specs T2's output as an **Armed Card** contract, (b) lays out the 5-stage pipeline with the right agent on each leg, (c) gives the three-hats engineering substance (full-stack / AI / CS) the armed cards must carry, (d) sequences it so the first shipped card lands this week, and (e) ships **one proof slice now** — the whole **Architecture** theme, armed, with the P0 card **AIQ-1984** decomposed into buildable subtasks. See the companion file `ReloPass_ThemeDigest_Architecture_2026-08-22.md`.

---

## 1. Where Otto left it — and the honest diagnosis

**What Otto did (well):** created T1 + T2, set them to *Otto ready · P1 · Yellow*, assigned *Claude Cowork*, recorded the workspace-UUID auth quirk and the board schema quirks (title property is `fable`; Status/Priority are `select`) in `otto.md`. Both cards carry complete execution prompts and validation criteria. Clean intake.

**Three problems the intake surfaces — each is an opportunity:**

**(P1) The corpus is parked, not producing.** Of AIQ-1936–1985 (50 cards): `Parked` ×39, `Done` ×3 (1949, 1976, 1979), `Human Review` ×2 (1950, 1953), `Ready for AI` ×1 (1956), `Otto ready` ×2 (1981, 1984), `Needs Human Clarification` ×1 (1940), `Rejected` ×1 (1948), `Archived` ×1 (1983). The 2018–2022 authoring family is healthier (`Ready for AI` ×4, `Needs Decomposition` ×1). **Diagnosis:** we have been *accumulating* theory-backed cards faster than we *retire* them. Value = retired cards that changed served behaviour, not cards created.

**(P2) The T1/T2 assignee/author seam is crossed.** Both cards are assigned to *Claude Cowork*, but their execution prompts are written to **Otto** — *"You authored these analyses — retrieve them from your GCS bundles/ZIPs."* Cowork cannot read Otto's GCS. As written, **neither card is executable by its assignee.** This is not a mistake to paper over — it is *exactly* the credential-silo the bridge exists to cross. §7 fixes it with the bridge, not with a re-assignment.

**(P3) T1/T2 risk multiplying markdown.** Both are "Type-5 deliverable = markdown." If we execute them literally we get 37 + 7 new `.md` files and the board still shows ~39 Parked cards. The corpus was always a *means*; the *end* is served product. This plan keeps T1/T2 (the corpus must be in-repo and addressable) but subordinates them to the compile step that actually retires cards.

---

## 2. The reframe — the corpus is source code; build a Learning Compiler

A learning is only worth the extraction cost if it changes a decision. In ReloPass, decisions live in code and data: what the serving layer asserts, how corridors compile, what the verifier gates, which eval must pass. So the corpus should be compiled the way source is compiled — deterministically, in stages, with a gate at each boundary.

```
   ANALYSIS  →  CLAIM  →  ARMED CARD  →  ARTIFACT  →  MERGED/PROMOTED  →  EVAL GREEN
  (Tier-1/2)  (cited)   (spec+tests)   (diff/SQL)   (human-gated)      (proof)
     T1          T2          T2+          GRA loop     lawyer/Romain     harness
```

Two design commitments make this real rather than a metaphor:

1. **A claim may *inspire* engineering freely, but may only *ground* a served product fact if it is Tier-1 (verbatim).** T1 already encodes this (CS229/CS230 are Tier-2 → inspire, never ground). Engineering artifacts — acceptance criteria, tests, indexes, decompositions — are **not product claims about the world**, so they can be authored from a Tier-2 analysis or even from the card text itself. Served *relocation facts* cannot. This single rule lets us move fast on code while staying honest on content.

2. **The compiler never auto-serves.** Every stage is append-only and reversible until a human gate. Code lands as a branch+PR (Romain merges); data lands `review_status='pending'` (lawyer flips at `/admin/countries`); `representative → verified` is a human-only transition (already card AIQ-1983's guardrail). The compiler's job is to make the human gate a *5-minute approval of a green, tested artifact*, not a research project.

---

## 3. Pipeline architecture — 5 stages, right agent per leg

The capability split is real (it's what forced the bridge). Each stage goes to the agent that *can* do it, and the bridge moves the artifact across the silo.

| # | Stage | Input → Output | Owner (does the work) | Governance | Bridge `kind` |
|---|---|---|---|---|---|
| **S1** | **Extract** | source (course/book) → analysis `.md` (Tier-1/2 tagged) | **Otto** (authored them; has GCS) | none (docs) | `manifest` (T1 delivery) |
| **S2** | **Materialize** | analyses → in-repo `corpus/theory/**` + index + `manifest.json` (sha256) | **Claude Code** applies; **Otto** relays the bundle | none (docs, in git) | `record: context_bundle` |
| **S3** | **Arm** | claims → **Armed Card** per AIQ id (accept. criteria + eval metric + test sketch + decomposition) | **Cowork** (I read repo+prod, know the services) with Otto's claims | Cowork self-validates | `record` |
| **S4** | **Generate** | Armed Card → unified diff / transactional SQL / tests **+ prediction** | **Cursor** (fleet, read-only bundle) | sandboxed, no prod | `record: artifact` |
| **S5** | **Apply+Verify** | artifact → dry-run → apply → prod/eval check | **Claude Code** applies; **Cowork** verifies independently | 🔴 human/lawyer gate | `record: apply_report` |

**Why this is the correct division of labour**

- **Otto extracts and researches** — it is the only agent with the source bundles and the research muscle (Denis). It should *not* write code or DB; it relays.
- **Cowork arms** — arming needs someone who can read both the repo (device bridge) *and* prod (Supabase MCP) to write acceptance criteria and test sketches that reference *real* services (`requirements_builder.py`, `factual_verifier.py`, …) and *real* rows. That's me. I cannot reach the bus, so Otto/Claude Code relay my armed cards.
- **Cursor generates** — generation is a pure read-only function `(bundle) → (artifact + prediction)`; give Cursor's fleet the bulk codegen and it never touches prod. This is where spare capacity goes.
- **Claude Code applies** — the one wired agent: rolec checkout + service-role key + `gh`. It dry-runs against Cursor's prediction, applies on match, and owns the id/mapping derivation Cowork can't compute reliably.
- **Human gates** — merge to `main`, promote to served, flip to verified. Nothing 🔴 auto-fires.

**Where it pays / doesn't** (same discipline as the bridge doc): route a theme's worth of cards — bulk, parallel codegen with tests — through the loop. Do **not** route a one-line change through four hops; the wired agent just does it. Use the loop where scale justifies the relay.

---

## 4. The Armed Card contract — T2's real output

This is the plan's core artifact. Today an AIQ card is a title + a status. An **Armed Card** is a card upgraded until a `relopass-dev-queue` (code) or `notion-task-executor` (non-code) agent can execute it **with zero follow-up questions**. T2 should emit *this*, per card, not a prose digest.

**Every Armed Card carries:**

1. **Claim provenance** — the corpus claim(s) that motivate it, each with source + tier. Tier-2 marked "inspires, not grounds."
2. **Layer + entry points** — `UI | API | Isolation | Feature | Data | AI/ML` and the *named* files/services it touches (e.g. `backend/app/services/requirements_builder.py`). Lets `relopass-fix-*` route it.
3. **Acceptance criteria** — behavioural, testable, binary. "Given persona X, the served output asserts Y and never asserts Z."
4. **Eval metric** — the *number* that must move, and its instrument (PostHog event, pytest assertion, a report in `rag_eval_reports.py`). No card ships without a metric — this is the whole Evaluation theme, applied to itself.
5. **Test sketch** — the pytest (or golden-fixture) that encodes the acceptance criteria, named and located. TDD: the test is the spec.
6. **Autonomy Tier** — 🟢/🟡/🔴 per the `relopass-autopilot` rubric (immigration/tax/legal correctness ⇒ 🔴).
7. **Decomposition** — if the card is compound, the atomic subtasks (each one Layer-typed, each independently testable), so it leaves `Needs Decomposition`.
8. **Bridge routing** — who generates (Cursor?), who applies (Claude Code / Cowork), what the dry-run predicts.

An Armed Card is *executable intent*. The moment it exists, the card moves `Parked → Ready for AI` and the compiler's back half (S4/S5) can run unattended for 🟢/🟡, gated for 🔴.

---

## 5. The engineering substance — the three hats

The corpus's 7 themes are not evenly "product." Read as an engineer, they cluster into three disciplines. Here is the concrete work each implies, tied to the real services in `rolec`. (Full per-card arming for Architecture ships now; the rest follow the same shape.)

### 5a. Full-stack engineer — the correctness surface that reaches a mover

The serving path is the product. Today it runs through `requirements_builder.py` (serves **approved only**), `requirements_sufficiency.py`, `applies_to_matcher.py` (both touched 2026-08-22 — the CT-4 work), `roadmap_builder.py` / `roadmap_corridor_overlay.py` / `timeline_service.py`, exposed by routers `requirement_facts.py` and `public_corridor.py`.

- **The S1 audit risk is a full-stack bug, not a content bug.** An EEA mover told they're exempt from Irish Emergency Tax is a *serving* defect: `applies_to.nationality_scope_basis` (`audience_scope` vs `nationality_determined`) and `assertion_mode=conditional` must gate rendering. Cards **1938** (OOD gate — extend the existing `roadmap_confidence_gate.py`), **1969** (tag what each requirement is conditioned on), **1971** (employee-type decision tree), **1972** (literal rule → dated action) live here. **Ship these before promoting any corridor** (CT-4 before CT-5), or you promote a mis-served correctness bug.
- **Compile & cache the corridor** (1937, 1954, 1955): a *compile/validate build step* over `corridor_registry.py` that only emits lawyer-verified corridors, a compiled-corridor cache with explicit invalidation on rule change, and an O(1) served view behind a compound index. This is the difference between "we have facts" and "we serve them in <50 ms, correctly, every time."
- **Delta-metrics & the arc** (1968, 1974): the fear→relief arc is a *layout + instrumentation* job — the timeline must visibly fill in above the fold, and the funnel `activations→verified→relief-yes→paid` must be measured, not the day.

### 5b. AI expert — generator/verifier as the architecture, not a feature

ReloPass already has the pieces: `immigration_answer_engine.py` (generator), `factual_verifier.py` + `immigration_answer_verifier.py` (verifier), `immigration_contradiction_detector.py`, `staging_review_service.py` → `review_queue_service.py` (the human gate), `source_reliability_service.py`, `embeddings.py`. The theory says: **make the separation a hard invariant, and build the eval before the model.**

- **Generator–verifier gate as an invariant** (1936, 1983): *no LLM candidate ships without lawyer/user verification*, and *only a human flips `representative → verified`*. This is a guardrail in the write path (`staging_review_service.py`) + a test, not a vibe.
- **Eval harness before any model** (1945, 1981, 1946, 1966, 1967): build the relief-moment eval and the **non-obvious-requirement recall** metric (sliced by corridor × employee-type, vs a lawyer HLP baseline) *first*, wire it into `rag_eval_reports.py` + PostHog. 1981 is Otto-ready P0 — it's the card that tells you whether anything else worked.
- **Corridor transfer = fine-tuning discipline** (1963, 1977, 1943, 1960): freeze the verified backbone, re-verify the head, never transfer volatile facts; a hard-negative registry (Norway EEA-not-EU vs Ireland non-Schengen) forces apart the look-alikes; cosine dedup into a *human* review queue, never auto-merge.
- **Distill only from the verified engine** (1978): the v1 employee chatbot's teacher is the verified engine, never raw LLM output. Distillation compounds the moat; distilling from raw LLM output launders hallucination into the product.

### 5c. Computer scientist — the data structures and complexity that make it defensible

- **Model the knowledge graph as a typed graph** (1953, in Human Review): typed nodes/edges, **topological sort + cycle detection** on `depends_on`, over `policy_context_graph_service.py`. A relocation roadmap *is* a DAG; treat it as one and infeasible/circular dependencies become detectable, not latent.
- **CSP feasibility** (1947): "flag infeasible move dates in week one" is a constraint-satisfaction check over the compiled corridor DAG + lead times (`roadmap_lead_times.py`). This is a CS problem with a clean formulation.
- **O(1) serving + invalidation** (1955, 1954): compound index `(corridor_id, entity_id, fact_key, employee_type)` + a denormalized served view + a scale audit; cache the compiled corridor with correctness-preserving invalidation. Complexity is a feature customers feel as latency.
- **Idempotency as a tested invariant** (1982, 1958): double-import regression test with a row-count assertion; UNIQUE composite key + transactional corridor writes. The bridge self-test already leaned on `ON CONFLICT (dedupe_key) DO NOTHING` — make it a *test*, not a habit.
- **Freshness as a decaying signal** (1985, 1973): `verified_at` + `days_since_last_verified` + a staleness queue that visibly downgrades decaying nodes, plus the continuous re-verification engine (`change_detection_service.py`, `source_change_classifier.py`, `freshness_service.py` already exist to build on).

---

## 6. Sequencing — the critical path to a retired card

The goal is **retired cards that changed served behaviour**, fastest. Sequenced so the first ships this week and each phase de-risks the next.

**Phase 0 — Proof slice (this session).** Arm the entire **Architecture** theme; decompose the P0 spearhead **AIQ-1984** ("prove the full LLM→verify→serve→eval loop on ONE case, Andrea's ES→IE") into buildable subtasks; hand Claude Code the first bridge-ready context-bundle. Ships as `ReloPass_ThemeDigest_Architecture_2026-08-22.md`. **Why 1984 first:** it's Andrew Ng's "overfit one batch" — get *one* corridor correct end-to-end (generate→verify→serve→eval) before scaling. It reuses the ES→IE work already in flight (self-test, tandem plan) and turns three P0 cards green at once.

**Phase 1 — Arm the 7 themes (T2, upgraded).** Cowork arms every card in AIQ-1936–1985 / 2018–2022 to the §4 contract. Output is not 7 prose digests but **~55 Armed Cards** + a theme index. Every `Needs Decomposition` card (2019, and any compound 1936/1944/1945/1947/1963/1973/1978) gets an atomic breakdown. **This is the single highest-leverage step** — it converts the whole parked backlog into executable intent. Batchable across a Cursor fleet for the codegen-heavy cards.

**Phase 2 — Compile the Green/Yellow lane.** Run S4/S5 (Generate→Apply+Verify) on every 🟢/🟡 Armed Card via `relopass-autopilot`. 🔴 cards (all immigration/tax/legal correctness, all serving merges, all promotions) stage a tested artifact and wait for Romain/lawyer. Target: the 1938/1969/1971/1972 serving-correctness cards land *before* the next corridor promotion.

**Phase 3 — The standing factory (T1 institutionalised).** Materialise the corpus into `corpus/theory/**` (T1, done properly via §7), and wire the `relopass-content-extraction` skill so a *new* course/book flows S1→S5 with no manual relay: extract → materialize → auto-arm draft → Cursor generates → Claude Code applies → eval. Every future learning arrives as a candidate PR, not a candidate document.

**Critical-path picture:**
```
Phase 0 (Architecture armed + 1984 decomposed)         ← now
   └─► Phase 1 (all 7 themes armed → ~55 Armed Cards)   ← the leverage step
          └─► Phase 2 (autopilot compiles 🟢/🟡; 🔴 staged+gated)
                 └─► Phase 3 (content-extraction skill = the standing compiler)
```

---

## 7. Fixing the T1/T2 handoff seam (the bridge, used for real)

The seam (P2) is the bridge's home turf. Resolution, per card:

- **T1 (materialize 37 analyses).** *Otto* holds the analyses in GCS; *Claude Code* owns the repo write. So: **Otto pushes the 37 analyses as `manifest` chunks → Claude Code writes them to `corpus/theory/<source>/<item>.md`, builds the index + `manifest.json` (sha256, count==37), commits on a branch → Cowork verifies count/sha/section-completeness against prod-of-record.** Cowork's role on T1 is *verifier*, not author — which is correct, and matches the card's Yellow tier (self-validate + sample). The assignee stays "Claude Cowork" for tracking; the *work* is Otto-origin + Claude-Code-apply + Cowork-verify. No re-assignment needed once the flow is on the wire.
- **T2 (7 digests → Armed Cards).** *Cowork* is the right author here (needs repo+prod read to arm against real services), so this card's assignee is correct. Otto relays the corpus claims (S1 output) over the bridge; Cowork arms; Claude Code/Cursor pick up S4/S5. **Upgrade the acceptance criteria** from "7 digest files" to "~55 Armed Cards each satisfying the §4 contract; every AIQ id appears in exactly one theme; every Needs-Decomposition card has an atomic breakdown."

Concretely, add the three `record` subtypes from the Generator–Relay–Applier doc to the bus — `context_bundle`, `artifact`, `apply_report` — and T1/T2 ride the existing infra with no new endpoints.

---

## 8. Governance & guardrails (unchanged, restated because they're load-bearing)

- **Append-only; promote-to-pending only.** Data lands `review_status='pending'`; `requirements_builder` serves approved only. The flip to served on immigration/tax/legal content is the **human lawyer gate at `/admin/countries`** — never auto-serve.
- **`representative → verified` is human-only** (AIQ-1983). The compiler may propose; only a person promotes.
- **Tier-2 inspires, never grounds** a product fact (T1's rule). Engineering artifacts are exempt (they assert nothing about the world).
- **Every 🔴 waits for Romain:** code merge to `main`, promotion to served, lawyer review. The compiler *prepares* 🔴s as green, tested, dry-run-verified artifacts; it never fires them.
- **Files-first, reversible:** staging is `REVOKE`d from app roles; branches aren't `main`; dry-run precedes every apply; Cowork verifies independently of the applier.

---

## 9. Metrics — how we know the compiler works

Measure the compiler the way we'll measure the product (dogfood the Evaluation theme):

| Metric | Instrument | Target |
|---|---|---|
| **Cards retired / week** (Parked→Done, attributable to a claim) | Notion `notion_work_queue.py` + this plan's provenance links | ≥ 5/wk once Phase 1 lands |
| **Arm→ship lead time** (Armed Card → merged/promoted) | Notion timestamps | ↓ toward < 3 days for 🟡 |
| **Non-obvious-requirement recall** (the product metric, 1981) | `rag_eval_reports.py` + lawyer HLP baseline | defined + baselined before scaling corridors |
| **Serving-correctness regressions** (S1-class) | golden-fixture pytest (`docs/esie-andrea-golden-fixture.md`) | 0 promoted while red |
| **Corpus→code traceability** | every merged PR links the AIQ id + claim | 100% |

The last row is the moat metric: a served fact you can trace back through card → claim → Tier-1 source is defensible in a way a ChatGPT answer never is (the Trust theme, cards 1970/1969, made literal).

---

## 10. What ships in this session

1. **This plan** — `ReloPass_Theory_to_Product_Engineering_Plan_2026-08-22.md` (repo root, beside your other 2026-08-22 artifacts).
2. **Proof slice** — `ReloPass_ThemeDigest_Architecture_2026-08-22.md`: the Architecture theme fully armed (8 cards), **AIQ-1984 decomposed** into 5 atomic subtasks, and a **bridge-ready context-bundle** for the first buildable one.
3. **Visual** — a shareable pipeline/architecture diagram (the 5 stages × agents × gates).

**Immediate next actions (proposed):**
- **Romain:** approve upgrading T2's acceptance criteria to the Armed-Card contract (§4); pick whether Phase 1 arms all 7 themes in one Cowork pass or fans the codegen-heavy ones across a Cursor fleet.
- **Otto:** relay the Architecture-theme corpus claims (and the T1 analyses) over the bridge as `manifest`, so the arming's provenance is Tier-1 where it must be.
- **Claude Code:** take the Phase-0 context bundle (in the proof-slice file) and run S5 dry-run for AIQ-1984 subtask 1 against the ES→IE Andrea fixture.

The line to hold: **stop counting cards created; start counting cards retired that changed what a mover is told.** Everything above is in service of that one number.
