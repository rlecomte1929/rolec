# Eval — `roadmap_generator_v1.txt`

**Cohort:** AIQ-627 (P1-01b) · **Stage:** RAG roadmap generator · **Model under test:** `claude-sonnet-4-6`

This eval validates that the generator prompt (a) produces a schema-valid
`CaseRoadmap` for a covered corridor with every step grounded in a supplied
chunk, and (b) refuses with the `RULE_NOT_FOUND` sentinel — emitting zero
steps — for an uncovered corridor.

Run this manually (or wire it into the P1-01d orchestrator test suite) before
approving the prompt for production use.

---

## Acceptance bar (from Notion AIQ-627 validation criteria)

| Metric | Bar |
|--------|-----|
| FR→NO runs producing schema-valid `CaseRoadmap` JSON | 5 / 5 |
| Every emitted step has a non-null `source_url` copied from a supplied chunk | 100 % |
| Zero steps cite a `source_url` not present in the CONTEXT | 100 % |
| JP→NO (uncovered) run returns `result=RULE_NOT_FOUND` with `steps=[]` | 1 / 1 |
| JP→NO run hallucinates zero steps | 100 % |

A single fabricated `source_url`, or any non-empty `steps` array on the JP→NO
run, is a hard fail.

---

## Methodology

1. For each fixture below, send the `SUBJECT` + `CONTEXT` block as a single
   user message to `claude-sonnet-4-6`, with the contents of
   `roadmap_generator_v1.txt` as the system prompt and temperature=0.
2. Enable the `emit_case_roadmap` tool (schema in the prompt file).
3. Capture the tool call's input JSON as the actual output.
4. Validate the output:
   - `result` ∈ {`OK`, `RULE_NOT_FOUND`}.
   - When `result=OK`: every step's `source_url` and `source_chunk_id` appear
     on a CONTEXT chunk; `steps` is non-empty; `corridor` matches the subject.
   - When `result=RULE_NOT_FOUND`: `steps == []` and `refusal_reason` is set.
5. Record results in the "Results" table at the bottom.

`summary` and `description` free text are NOT scored field-by-field — read
them qualitatively for grounding. The scored invariants are the schema shape,
the citation grounding, and the refusal behaviour.

---

## Live-corpus dependency (READ THIS)

The real FR→NO immigration corpus does **not** exist in the repo yet — it is
blocked on **P0-05** (corridor ingestion). Until P0-05 lands,
`immigration_retriever.retrieve_for_profile()` cannot return real FR→NO chunks,
so the **5 FR→NO live runs in the table below are a reviewer step**, not
something the AI executor could run.

What the AI executor DID validate, deterministically and offline, is the
prompt's *control logic* — that an empty CONTEXT triggers RULE_NOT_FOUND with
zero steps, and that a populated CONTEXT yields a schema-shaped roadmap whose
citations all trace back to supplied chunks. See
`backend/tests/test_roadmap_generator_prompt.py`. This mirrors how P1-01a
(`test_immigration_retriever.py`) validated against deterministic fixtures
rather than the absent live corpus.

**Reviewer:** once P0-05 has ingested FR→NO, run the 5 live FR→NO fixtures and
the 1 JP→NO fixture below against `claude-sonnet-4-6` and fill in the table.

---

## Fixtures

### FR-NO-1 — EEA free movement (covered)

(Identical to Exemplar 1 in the prompt — a "pass" here is necessary but not
sufficient; it only proves the model can reproduce the in-prompt exemplar.)

**Expected:** `result=OK`, 3 steps, all `source_url`s from the 3 supplied
chunks, all `confidence=high`, all `requires_expert_review=false`.

### FR-NO-2 — non-EEA skilled worker, partial coverage

(Identical to Exemplar 3.)

**Expected:** `result=OK`, 2 steps; step 2 (family immigration) is
`confidence=low` and `requires_expert_review=true`.

### FR-NO-3, 4, 5 — held-out (NOT in the prompt)

> **TODO for reviewer / P1-01d executor:** author 3 held-out FR→NO CONTEXT
> blocks from the real P0-05 corpus (e.g. tax registration, bank-account /
> D-number, health-service registration). The model has not seen these as
> exemplars, so they measure generalisation. The acceptance bar applies to the
> held-out set.

### JP-NO-1 — uncovered corridor (refusal)

(Identical to Exemplar 2.) Empty CONTEXT.

**Expected:** `result=RULE_NOT_FOUND`, `steps=[]`, `refusal_reason` set,
`corridor="JP→NO"`. ZERO fabricated steps.

---

## Results

| Run date | Model | Fixture | result | #steps | All source_url grounded | requires_expert_review correct | Pass |
|----------|-------|---------|--------|-------:|:-----------------------:|:------------------------------:|:----:|
| YYYY-MM-DD | sonnet-4-6 | FR-NO-1 | | | ⬜ | ⬜ | ⬜ |
| YYYY-MM-DD | sonnet-4-6 | FR-NO-2 | | | ⬜ | ⬜ | ⬜ |
| YYYY-MM-DD | sonnet-4-6 | FR-NO-3 (held-out) | | | ⬜ | ⬜ | ⬜ |
| YYYY-MM-DD | sonnet-4-6 | FR-NO-4 (held-out) | | | ⬜ | ⬜ | ⬜ |
| YYYY-MM-DD | sonnet-4-6 | FR-NO-5 (held-out) | | | ⬜ | ⬜ | ⬜ |
| YYYY-MM-DD | sonnet-4-6 | JP-NO-1 | | | n/a | n/a | ⬜ |

**Pass / Fail / Iterate:** ⬜

**Iteration notes:**
- (record any prompt-tuning rounds and what changed)

---

## What to do when a fixture fails

- **A `source_url` is fabricated** → strengthen Hard rule 2 / Anti-hallucination
  with a counter-exemplar showing the chunk set and the (wrong) invented URL.
- **JP→NO returns steps** → the RULE_NOT_FOUND guard is being overridden by the
  model's prior knowledge. Sharpen "The RULE_NOT_FOUND guard" section and add a
  near-miss held-out fixture (a corridor that *looks* like FR→NO but is not
  covered) to make the refusal robust.
- **Steps over-confident** (`requires_expert_review=false` on a conditional
  step) → tighten Hard rule 7 or add a low-confidence counter-exemplar.
- **Schema-invalid output** → confirm the tool schema is being passed to the
  model and `tool_choice` forces `emit_case_roadmap`.
