# RPX-05 consensus research pipeline

*Book → infrastructure. This is the first executable artifact distilled from the reading set:
Berryman & Ziegler, *Prompt Engineering for LLMs* (O'Reilly 2025) and Chip Huyen, *AI
Engineering* (O'Reilly 2024). It turns the "Ziegler 5-pass" research technique into a
deterministic, testable pipeline that feeds the corridor knowledge base as candidates only.*

## Why this is the moat

ReloPass's defensible advantage is not the corridor data — it is **the machine that produces
and refreshes that data accurately, at scale, without hard-coding**. Two failure modes make the
naive approaches unusable for a compliance product:

- **One LLM pass is confidently wrong often enough to be dangerous.** Huyen's compound-error
  arithmetic (95%/step → 60% over 10 steps) and Ziegler's "hallucinations cannot be instructed
  away" both say the same thing: a single generation cannot be trusted as fact.
- **Hand-coded data does not scale and goes stale.** New countries/cities/services and changing
  rules make a static table a liability.

The answer is an **ensemble with a citation gate**: run N independent research passes and keep a
fact only in proportion to how many passes independently found it, *and* whether it is cited to a
statutory source with a verbatim quote. Ziegler's epistemic rule — **"trust but verify, minus the
trust"** — encoded as code, not as a prompt instruction.

## Architecture (authoring layer — never serves, never calls a model here)

```
N research workers          passes/*.jsonl          consensus.jsonl  ─► import_otto_facts.py
(Otto / LLM, one small  ──► (one file per pass,  ──► needs_review.jsonl   --apply --promote
 single-corridor task,       JSONL of FactRow    ──► gaps.jsonl        ─► requirement_items
 files to GCS)               objects)            ──► run-report.md         (review_status='pending')
                                    │
                                    ▼
                     backend/imports/otto/consensus.py   ← the deterministic merge + eval
                     scripts/rpx_consensus.py            ← CLI
```

This respects the repo's **generation/serving split** (CI: `check_serving_llm_isolation.py`):
research and the model live in authoring; the serving path only ever reads reviewed data. Huyen:
"retrieve from the verified graph, not the open web at answer time." Ziegler ch. 9: **prefer a
workflow to an agent for a known task** — corridor research *is* a known task, so it is an explicit
pipeline of narrow steps, not one long agent chat (which is exactly what failed in Otto — it hit
Ziegler/Huyen's context "dumb zone" and errored out).

## Entity resolution before voting (learned from the first real run)

Independent passes drift **both** the topic key and the fact key for the same fact
(`right_of_residence` / `eu_right_of_residence` / `…_worker`; and a unique `fact_key` every time),
so naive exact-key voting collapses consensus to noise — the first live NO→FR run (5 passes, 71
statutory-cited facts) scored **0 consensus** for that reason alone. The merge therefore resolves
facts before voting, deterministically and LLM-free:

1. **Canonical topic** — `CANONICAL_TOPICS` maps known aliases to one form (explicit, no silent
   structural merges).
2. **Text clustering within a topic** — facts are grouped by content-token Jaccard on `fact_text`
   (same fact → near-identical text; different sub-facts → different text), so drifted `fact_key`s
   for the same fact vote together while distinct sub-facts stay separate.

Re-running the same 5 passes with this step yields **3 consensus (5/5) + 4/5 + 3/5, 0 gaps**. The
threshold is deliberately conservative (a false merge of two distinct compliance facts is worse
than an under-count); **semantic/embedding clustering is the next enhancement** to lift the facts
that vary in phrasing beyond lexical overlap.

## The consensus bands (RPX-05 card, made executable)

`merge_passes()` groups every candidate by `destination_country | entity_topic_key | fact_key`,
counts how many **distinct passes** produced it (`pass_count`), and routes it:

| Condition | Outcome |
|---|---|
| unofficial source (blog / vendor / law-firm), any pass_count | **gap** (hard rule) |
| `pass_count == N` **and** official source **and** verbatim quote | **consensus** |
| `pass_count ≥ ceil(0.6·N)` (incl. full-count that is only semi-official or unquoted) | **needs_review** (lawyer) |
| below that, but official + verbatim | **needs_review** (lawyer) — low-band rescue |
| below that, otherwise | **gap** |

Source tier reuses the existing `classify_source()` (OFFICIAL / SEMI_OFFICIAL / UNOFFICIAL), so
the sourcing gate and the consensus gate compose. **Nothing is ever fabricated to fill a gap** —
gaps are the re-sourcing worklist. Output rows carry `applies_to.pass_count` and
`needs_lawyer_review`; everything lands `review_status='pending'` downstream (human/lawyer gate at
`/admin/countries` is unchanged).

## Evaluation-driven development (Huyen ch. 4; Ziegler ch. 10)

`evaluate_consensus()` is the guardrail. It **verifies the merge's own invariant** — every
consensus row is official + verbatim-cited — so a regression in the merge FAILs the eval instead
of shipping a wrong fact, and reports quality metrics (citation coverage, statutory ratio, gap
ratio, pass-count histogram). This is Huyen's "define evaluation criteria before building," and it
is asymmetric by design: a missing mandatory requirement is catastrophic, a spurious one is merely
annoying.

**Roadmap (next slices), straight from the summaries:**
1. **SOMA rubric** (Ziegler ch. 10 — Specific, Ordinal, Multi-Aspect): grade each candidate per
   aspect on an ordinal scale (source-cited yes/partial/no; legal-advice phrasing none/borderline/
   present; completeness vs golden list; tone) with an AI judge — a screen, never proof.
2. **Mandatory-recall against a golden set** (Huyen ch. 4): freeze lawyer-confirmed cases per
   corridor; report weekly mandatory-requirement recall as the headline metric.
3. **Freshness / staleness signal** (Huyen ch. 4 step 4): re-run the passes on a cadence; a fact
   that falls out of consensus (5/5 → 3/5) is the drift alarm. This is the auto-refresh that
   replaces hand-maintenance.
4. **Flywheel** (Huyen ch. 8): case-close capture writes structured outcomes back as new pass
   evidence, so accuracy compounds with usage.

## Usage

```bash
# one JSONL file per research pass, all in a directory (or pass a glob)
python scripts/rpx_consensus.py <passes_dir> --batch-id RPX-05-fr-no-2026-09-12 --out-dir <dir>
# → <batch>.consensus.jsonl, <batch>.needs_review.jsonl, <batch>.gaps.jsonl, <batch>.run-report.md
# then, after reviewing the report:
python scripts/import_otto_facts.py <batch>.consensus.jsonl --apply --promote   # candidates, pending
```

A runnable 3-pass sample lives in `backend/imports/otto/fixtures/rpx_sample/`; the merge + eval are
unit-tested in `backend/tests/test_rpx_consensus.py`.

## The worker contract (what produces a "pass")

Each pass is one research worker's output for a corridor, as FactRow JSONL (`destination_country,
entity_topic_key, fact_key, fact_text, source_url`, plus `evidence_quote`, `fact_type`,
`applies_to`, `confidence`).

`applies_to.status` must use the **serving-purpose vocabulary**, not free text: `professional` /
`worker` / `employee` / `salaried` → `employment`; `student` → `study`; `family` → `family`;
`any` → `other`. A status outside this set is *refused* at promote time (it would land
`purpose='other'` and be invisible to the corridor reader), so the worker must emit one of these.

After staging, facts sit at `status='new'` and reach `public.requirement_items` only through two
human gates, neither of which the pipeline bypasses: a reviewer approves `new → ready` at
`/admin/requirement-facts` (which is when `promote()` writes the row, at `review_status='pending'`),
then the lawyer gate at `/admin/countries` approves it for serving.

Keep each worker task **small and single-corridor** and deliver a file
(Otto's proven mode) — never a long interactive chat. The passes must be **independent** (do not
seed pass 2 with pass 1's output) or the consensus signal is worthless. Claude Code is the wired
applier that pulls the pass files, runs this merge, and loads the result; the Audos→GitHub sync
lane does not propagate on its own.

## Provenance of the technique

- Berryman & Ziegler, *Prompt Engineering for LLMs*: ch. 2 (hallucinations, truth bias,
  specificity/checkability), ch. 9 (workflow over agent), ch. 10 (offline suites, SOMA).
  Summary: `Downloads/Books analysis/03-prompt-engineering-ziegler.md`.
- Chip Huyen, *AI Engineering*: ch. 3–4 (evaluation-driven development, AI-as-judge limits), ch. 6
  (RAG vs agents, compound error), ch. 8 (data flywheel), ch. 10 (guardrails, freshness).
  Summary: `Downloads/Books analysis/02-ai-engineering-huyen.md`.
