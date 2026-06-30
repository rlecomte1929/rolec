# Eval fixture curation

The Phase-1/2 eval build-out seeded **synthetic golden sets** so the gates are
non-vacuous and catch regressions immediately. Synthetic data is honest about
itself — every seeded fixture carries `verification_status: "representative"` (per
the content-provenance model). **Representative ≠ authoritative.** These fixtures
prove the *pipeline* works and trip on regressions, but they are NOT a substitute
for expert-labeled ground truth, and metric values computed against them measure
self-consistency, not real-world correctness.

This doc is the workflow to promote them to authoritative.

## Find them

```bash
python -m backend.scripts.list_representative_fixtures        # human list
python -m backend.scripts.list_representative_fixtures --json # machine list
```

## Promotion workflow (per fixture)

1. **Source real ground truth.** Replace synthetic content with expert/authoritative
   data (immigration rule text + the actual permit outcome for a corridor; real HR
   policy chunks; a real "best supplier" judgement for a case).
2. **Re-derive expected values** against the real content (expected chunk ids,
   eligibility `outcome_set` + citations, ideal ranking + graded relevance).
3. **Flip the marker** from `verification_status: "representative"` to `"verified"`
   (or remove it) once a human owner signs off.
4. **Re-run the relevant gate** and re-tune the threshold to a meaningful level
   (synthetic thresholds were set to "non-zero + regression-catching", not to a
   real quality bar). Then the gate measures real quality.
5. **Record the owner + date** in the fixture's `_meta`.

## Per-fixture notes

| Fixture | Gate it feeds | Known gap to fix when curating |
|---|---|---|
| `tests/fixtures/eligibility/<corridor>/ground_truth.json` | `run_eligibility_eval` | All 5 corridors now carry citations. US_FR & BR_PT use **representative** FR/PT rule versions (`FR_CESEDA_L421:2024`, `PT_LEI_23_2007_ART88:2007`) added to `backend/eval/rule_registry.py` — illustrative pointers, not authoritative legal cites. Promote to verified against live French/Portuguese immigration law. |
| `tests/fixtures/eval/outcome_accuracy/us_l1b_gold.json` | `run_outcome_accuracy` | Single corridor; expand to the 5 seeded corridors with real roadmaps. |
| `tests/fixtures/rag_eval/hr_policy/{queries,chunks}.jsonl` | `eval_hr_policy_context_precision`, reranker | Bodies are hand-authored for deterministic lexical overlap; replace with real policy text + real expected chunks. |
| `tests/fixtures/rag_eval/triad_cases.json` | `run_rag_triad` | Replace mock-judge-friendly cases with real (answer, chunks, gold-label) triples. |
| `tests/fixtures/rag_eval/judge_calibration_cases.json` | `run_judge_calibration` | These ARE the expert labels the judge is measured against — needs a real SME pass (Hamel "validate the judge"). Highest-leverage to curate. |
| `tests/fixtures/ranking/golden_rankings.json` | `run_ranking_eval`, preference learning | Ordering was **seeded from the static engine** → it's a regression guard, not preference ground truth. Replace `ideal_order`/`relevance` with real user-preference judgements before trusting NDCG as a quality signal. |

## Why this matters

Off-the-shelf / synthetic evals rarely transfer; accuracy against a self-seeded
set is too coarse (Eugene Yan). The labeling discipline matters more than the tool
— promote these as real usage data and SME time become available, starting with
`judge_calibration_cases.json` (it gates whether every LLM-judge score is trustworthy).
