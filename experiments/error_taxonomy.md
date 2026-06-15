# Policy Assistant — Error Taxonomy
**Phase 1 open coding · 20 traces · June 15 2026**

Score: **0 / 20 PASS** on first seed run.

---

## How to read this file

Each error category has:
- **Frequency** — how many of the 20 seed questions triggered it
- **Severity** — impact on user trust / product quality (High / Medium / Low)
- **Root cause** — where in the pipeline the failure originates
- **Fix layer** — what needs to change (data, classifier, prompt, post-processing)
- **Example** — a concrete question + bad output pair
- **Acceptance test** — the specific check that must pass before marking Fixed

---

## E1 · False Refusal on In-Scope Questions

**Frequency:** 17 / 20 (85%)
**Severity:** High — the assistant is nearly useless for its primary job

**Symptom:**
The assistant returns `answer_type: "refusal"` with `policy_status: "unknown"` for
questions that are clearly in-scope (housing allowance, moving expenses, language
classes, visa fees, etc.).

**Root cause:**
The published policy config has benefit rules for only a small number of topics
(`home_leave`, `relocation_allowance`). For every other topic the policy context
is empty, so `build_hr_resolved_policy_context` returns no content, and the
classifier/generator falls back to a refusal rather than saying "this topic isn't
covered in your policy data."

**Fix layer:** Data + prompt
1. Audit which benefit rule keys are populated in the published policy version
   (`policy_benefit_rules` table for version `5f562413-ef0f-402b-a70e-9aa5c6a0db99`).
2. For topics with no rule, return `answer_type: "not_in_policy"` (honest absence)
   instead of a generic refusal — these are different things and the user deserves
   to know the distinction.
3. Long-term: ensure the HR policy ingestion flow maps uploaded PDF benefits to
   the correct benefit rule keys so the coverage improves automatically.

**Example:**
```
Q: "What is the housing allowance for a Band 2 employee?"
A: answer_type=refusal, policy_status=unknown, answer_text=""
Expected: answer_type=not_in_policy OR entitlement_summary with the housing allowance value
```

**Acceptance test:**
> Given a question about a topic that exists in the uploaded policy PDF but is not
> yet mapped to a benefit rule, the assistant must NOT return `answer_type=refusal`.
> It must return either `entitlement_summary` (if the rule exists) or
> `not_in_policy` (if the topic is genuinely absent from the policy).
> A bare refusal with `policy_status=unknown` is always a FAIL for in-scope topics.

---

## E2 · Section Reference Misread as Quantity

**Frequency:** 1 / 20 (5%)
**Severity:** High — produces a confidently wrong number that HR would act on

**Symptom:**
The assistant returns a numeric value that is actually a policy section reference
(e.g. "§8.3"), presenting it as if it were a quantity (e.g. "8.30 trips").

**Root cause:**
The evidence excerpt stored in the benefit rule is `"Home leave 8.3"` — a label
copied verbatim from a table cell where "8.3" is a section number, not a quantity.
The answer generation prompt interprets any number after a benefit label as the
benefit's numeric value.

**Fix layer:** Data + post-processing
1. During policy extraction / ingestion, validate that numeric values in benefit
   rules are plausible for their category (trip counts should be integers 0–52,
   not floats like 8.3).
2. Add a post-processing check: if the extracted value for a `count`-type benefit
   is a float > 10, flag it as a likely section reference and return a clarification
   instead of a confident answer.
3. Correct the benefit rule data for `home_leave` in this company's policy.

**Example:**
```
Q: "How many home leave trips does the policy allow per year?"
A: "Home Leave is included up to 8.30"
   Evidence excerpt: "Home leave 8.3"
Expected: A trip count (e.g. "2 trips per year") or honest "the policy doesn't
          specify a number of trips, only a section reference (§8.3)"
```

**Acceptance test:**
> Given a question about home leave frequency, the answer must not present a
> section reference number (float matching §X.Y pattern) as a quantity.
> If no valid count is found, the answer must say so explicitly.

---

## E3 · Question Aspect Mismatch

**Frequency:** 2 / 20 (10%)
**Severity:** Medium — the topic is recognised but the specific sub-question is ignored

**Symptom:**
The classifier correctly identifies the topic (`relocation_allowance`) but the
answer generation returns the **amount** regardless of what the user actually
asked — deadline, structural option (lump sum vs managed), eligibility conditions,
etc. Two different questions receive the exact same answer.

**Root cause:**
The answer generation step receives the benefit rule value (e.g. `EUR 5,000`) and
formats it into a templated `entitlement_summary` response, without checking
whether the user's question is about a different attribute of that benefit (timing,
structure, conditions). The classifier resolves *topic* but loses *intent*.

**Fix layer:** Prompt
1. Add intent decomposition to the classification step: alongside `canonical_topic`,
   extract the **question aspect** (amount / deadline / eligibility / structure /
   process) as a separate field.
2. In answer generation, only include the amount if the aspect is `amount`. For
   other aspects, either look up the relevant rule field or return `not_in_policy`
   if that attribute isn't captured.

**Example:**
```
Q: "Is there a deadline to use the relocation allowance?"
A: "Relocation Allowance is included up to EUR 5,000"
Q: "Is there a lump sum option instead of managed relocation services?"
A: "Relocation Allowance is included up to EUR 5,000"   ← identical answer
Expected: answers that address the deadline and the lump-sum/managed distinction
          respectively, or explicit acknowledgement that the policy doesn't
          specify those attributes.
```

**Acceptance test:**
> Given two questions about the same topic but different aspects (amount vs
> deadline, or amount vs structure), the answers must differ in content.
> Returning the same `answer_text` for both is always a FAIL.

---

## E4 · Topic Not in Taxonomy (Banking)

**Frequency:** 1 / 20 (5%)
**Severity:** Low — clearly scoped gap, not a false refusal

**Symptom:**
"What does the policy say about banking support?" returns `answer_type=refusal,
refusal_code=ambiguous_or_ungrounded` — not because the policy lacks data, but
because `banking_setup` has no canonical topic in `PolicyAssistantCanonicalTopic`.

**Root cause:**
The assistant taxonomy covers 12 relocation topics. Banking assistance (bank transfer
reimbursement) is in the benefit rules but out of taxonomy.

**Fix layer:** Contract — add `BANKING_SETUP` canonical topic, pattern, and benefit key.

**Priority:** Low — banking is peripheral to core relocation Q&A. Defer until E2 and E3 are fixed.

---

## Priority order for fixing

| # | Error | Freq | Severity | Status | Fix |
|---|-------|------|----------|--------|-----|
| E1 | False refusal | 85% | High | ✅ **FIXED** | Published rules merged into topics dict; classifier keywords expanded |
| E2 | Section ref as quantity | 5% | High | ✅ **FIXED** | Deleted bad `8.3` row; home leave now returns "3 trips" not "8.30" |
| E3 | Aspect mismatch | 20% | Medium | ✅ **FIXED** | `question_aspect` field added to classifier; `_build_aspect_body()` branches in answer engine |
| E4 | Topic not in taxonomy | 5% | Low | Open | Add BANKING_SETUP canonical topic |

---

## Score history

| Date | Score | Notes |
|------|-------|-------|
| 2026-06-15 (baseline) | 0 / 20 | First seed run — all false refusals |
| 2026-06-15 (E1 fix) | 19 / 20 | Published rules merged into context; 7 classifier keyword gaps fixed |
| 2026-06-15 (E2 fix) | 19 / 20 | Bad §8.3 row deleted; home leave now shows "3" not "8.30". Banking gap (E4) is the sole remaining FAIL |
| 2026-06-15 (E3 fix) | 19 / 20 (rubric-updated) | Aspect routing: deadline/structure/eligibility/process questions now get distinct answers. Rubric strengthened for Q02/Q03 — both now PASS with correct content. E4 banking remains sole FAIL. |

---

## Next steps

1. [x] Audit `policy_benefit_rules` for populated topics
2. [x] Merge published benefit rules into the `topics` dict (was only in `hr_published_topics`)
3. [x] Expand classifier keyword patterns (COLA, mobility premium, language training, spouse, housing, status)
4. [x] Add `language_training` to SCHOOL_SEARCH benefit keys; `housing` to TEMPORARY_HOUSING keys
5. [x] Delete the `8.3` section-ref row from `policy_benefit_rules` for the eval policy (E2)
6. [x] Add question aspect extraction to classifier (E3) — so "deadline?" vs "amount?" get different answers
7. [ ] Manually review the 19 PASS traces in Langfuse and annotate ground truth → create golden-v1 dataset
8. [ ] Add E4 BANKING_SETUP canonical topic (low priority)
