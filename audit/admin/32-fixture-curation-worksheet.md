# Fixture Curation Worksheet — `verification_status: "representative"` eval fixtures

**Status:** DRAFT for Romain's review. Read-only prep — no fixture was modified.
**Prepared:** 2026-06-30. **Scope:** turn the synthetic eval fixtures flagged
`verification_status: "representative"` into authoritative ground truth.

## How to use this doc
- Each fixture set has: what it labels, which eval gate consumes it, a sample,
  my **Proposed label / verdict** (with a confidence), and a **NEEDS ROMAIN**
  flag where I genuinely cannot decide without domain/legal/product knowledge.
- Edit inline. For draftable items, change the **Verdict** column to `OK` /
  `FIX→<value>`. For "needs me" items, fill the blank decision column.
- I (Claude) did **not** invent any immigration/legal facts. Where a label
  depends on real law, a real policy document, or a true user preference, it is
  flagged NEEDS ROMAIN, not guessed.

## Inventory at a glance

| # | Fixture set | Items | Consumed by (gate) | I can draft | Needs Romain |
|---|-------------|-------|--------------------|-------------|--------------|
| 1 | `feedback_triage/cases.jsonl` *(branch `feat/admin-bug-routine`)* | 24 cases | `run_feedback_triage_eval.py` — **hard CI gate** area_acc ≥ 0.83 | **24/24** (high) | 0 (product-judgment only, confirm) |
| 2 | `rag_eval/judge_calibration_cases.json` | 25 cases | `run_judge_calibration.py` — warn-only (Cohen κ < 0.6) | **25/25** (high) | 0–2 borderline |
| 3 | `rag_eval/triad_cases.json` | 8 cases | `run_rag_triad.py` — hard gate (3 ratios) | **8/8** verdicts (high) | gate thresholds (product) |
| 4 | `eligibility/<corridor>/ground_truth.json` | 5 corridors | `run_eligibility_eval.py` — **hard CI gate** outcome=1.0 + citation_effective=1.0 | outcomes **5/5** (med-high) | **citations 5/5 (legal)** |
| 5 | `rag_eval/hr_policy/{queries,chunks}.jsonl` | 18 queries / 57 chunks | `eval_hr_policy_context_precision.py`, rerank tests | mappings **18/18** (high) | chunk **bodies** = representative-enough? (product, low risk) |
| 6 | `ranking/golden_rankings.json` | 3 cases (30 placements) | `run_ranking_eval.py` — hard gate NDCG ≥ 0.90 | 0 | **ideal_order = true preference? 3/3 (product)** |
| (adj.) | `rag_eval/queries.jsonl` + `chunks.jsonl` + `corpus/*` (immigration) | 51 q / 76 chunks | `eval_context_precision.py` | mappings only | **corpus = real immigration facts (legal)** |

**Totals:** ~83 discrete labeled units across 6 in-scope sets.
- **Draftable by me (review-only for Romain):** sets 1, 2, 3 fully (57 cases);
  set 4 outcomes (5); set 5 query→chunk mappings (18). ≈ 80 units.
- **Genuinely needs Romain:** set 4 citations (legal, 7 distinct statute IDs),
  set 6 ranking order (product preference, 3 cases), set 5/immigration chunk
  *bodies* (product/legal sign-off, lower per-item risk).

**Recommended first target:** `judge_calibration_cases.json` (set 2). It gates
whether *every* LLM-judge groundedness score downstream is trustworthy — and it
is 100% draftable here, so curation collapses to Romain skimming 25 yes/no
verdicts. Pair it with `feedback_triage/cases.jsonl` (set 1), which is the
evidence base for the LLM-triage flag-flip decision and is already a clean CI
gate. Both are pure "confirm my drafts" passes — fastest path to retiring two
`representative` flags.

---

## 1. `feedback_triage/cases.jsonl`  *(branch: `feat/admin-bug-routine`)*

**Labels:** per support-feedback message → `gold_severity` ∈
{low, medium, high, critical} and `gold_area` ∈ {ui, api, isolation, feature, other}.
**Used by:** `backend/eval/run_feedback_triage_eval.py`. `--ci` **hard-gates** the
deterministic classifier at `area_accuracy ≥ 0.83`. The LLM classifier number is
report-only (it's the evidence for flipping the `feedback_llm_triage` flag).
**Classifier rules:** `backend/app/services/feedback_triage.py` — keyword scan,
area precedence isolation→ui→feature→api→other; severity critical(isolation) /
high(crash words) / medium(category=bug) / low.

**Verification run (deterministic classifier vs current gold):**
severity_acc = **23/24 (0.958)**, area_acc = **20/24 (0.833)** — exactly on the
CI gate. The 4 area misses are the 4 cases carrying a `known_failure` note, i.e.
deliberate documented classifier blind spots, NOT label errors.

**My read:** support severity/area is a product-triage judgment I can make
confidently from the text + the enum definitions. All 24 current gold labels are
defensible. Below: my independent verdict per case. "Conf" = my confidence the
gold label is the right authoritative label.

| id | text (abbrev) | gold sev/area | classifier pred | my verdict | conf | Romain |
|----|---------------|---------------|-----------------|-----------|------|--------|
| tc-01 | tenant data leak in reporting | critical/isolation | =gold | OK | high | |
| tc-02 | cross-company data visible after transfer | critical/isolation | =gold | OK | high | |
| tc-03 | submit button broken, nothing loads | high/ui | =gold | OK | high | |
| tc-04 | modal overlaps header, can't close | high/ui | =gold | OK | high | |
| tc-05 | spinner never stops after save | medium/ui | =gold | OK | high | |
| tc-06 | layout misaligned on mobile | low/ui | =gold | OK | high | |
| tc-07 | 500 error loading dashboard | high/api | =gold | OK | high | |
| tc-08 | auth endpoint 403 intermittently | medium/api | =gold | OK | med (403→medium defensible; could argue high) | |
| tc-09 | API list endpoint a bit slow | low/api | =gold | OK | high | |
| tc-10 | want CSV export | low/feature | =gold | OK | high | |
| tc-11 | feature request: multi-language | low/feature | =gold | OK | high | |
| tc-12 | "search enhancement filed as bug" not working | medium/feature | =gold | OK | med (area=feature vs ui/api ambiguous) | |
| tc-13 | slow loading page sometimes | low/other | =gold | OK | med (could be api) | |
| tc-14 | general onboarding feedback | low/other | =gold | OK | high | |
| tc-15 | "something seems off" | medium/other | =gold | OK | high | |
| tc-16 | crashes on document upload | high/other | =gold | OK | med (area=other; arguably api) | |
| tc-17 | API request 500 ISE | high/**api** | high/feature ✗ | OK (gold right; classifier 'request'→feature misfire) | high | |
| tc-18 | UI looks broken after update | high/**ui** | high/other ✗ | OK (gold right; 'interface/looks' not in ui list) | high | |
| tc-19 | request to update profile throws exception | high/**api** | high/feature ✗ | OK (gold right; 'request' misfire) | high | |
| tc-20 | wishlist: sort table by column | low/feature | =gold | OK | high | |
| tc-21 | auth token expiring too quickly | low/api | =gold | OK | med (severity low vs medium debatable) | |
| tc-22 | isolation breach, tenant sees other reports | critical/isolation | =gold | OK | high | |
| tc-23 | dark-mode toggle CSS not rendering | low/ui | =gold | OK | high | |
| tc-24 | company A data in company B dashboard | critical/**isolation** | medium/other ✗ | OK (gold right; no isolation keyword → classifier misses) | high | |

**Effort:** ~20 min for Romain to confirm (mostly a skim; ~5 "med" rows worth a
second look: tc-08, tc-12, tc-13, tc-16, tc-21).
**Curation action:** if all OK, replace `_meta.note` and drop the
`verification_status:"representative"` line → `"curated"`. The 4 `known_failure`
notes should stay (they document classifier gaps, not label doubt).

---

## 2. `rag_eval/judge_calibration_cases.json`  *(origin/main)* — **RECOMMENDED FIRST**

**Labels:** 25 cases, each `{answer, chunks, gold}` where `gold` ∈
{grounded, partially_grounded, ungrounded}.
**Used by:** `backend/eval/run_judge_calibration.py` — measures the grounding
judge (same judge that powers `immigration_answer_verifier.verify_grounding` and
the live HR Policy answer path) against this gold set; reports agreement +
Cohen's κ. **Warn-only** (κ < 0.6 prints WARNING, exits 0) — but it is the
*calibration anchor* for trusting every groundedness verdict in the system.

**Sample:**
- C-03 grounded: answer "tuition covered up to EUR 20,000/child/yr" vs chunk
  saying exactly that → entailed.
- C-12 partially_grounded: answer adds "university fees also reimbursed" not in
  chunk → one supported claim + one unsupported.
- C-20 ungrounded: answer "all children attend Harvard, full scholarships" vs
  EUR 20,000 tuition chunk → contradicted/unsupported.

**My read:** this is textual entailment (answer vs chunk text), fully
determinable from the fixture itself — **no domain knowledge required**. I
reviewed all 25. The label schema is internally consistent: C-01..C-09
grounded, C-10..C-17 partially_grounded (each adds exactly one fabricated rider
to a true core), C-18..C-25 ungrounded (each is absurd vs the chunk). **All 25
gold verdicts are correct.**

Two worth a glance (both defensible as-is):
- **C-10..C-17** are labelled `partially_grounded` because the core claim *is*
  grounded and only the appended clause is invented. If Romain's product
  definition is "any unsupported claim ⇒ ungrounded," these flip to ungrounded.
  This is a **labeling-policy choice**, not a factual error → see decision box.
- **C-19** chunk text ("two home-leave trips ... economy class") slightly
  differs from the matching chunk elsewhere; answer "lifetime first-class for
  entire extended family" is clearly ungrounded regardless. OK.

> **NEEDS ROMAIN (policy choice, not fact):** Confirm the 3-class boundary —
> does "true core + one fabricated rider" = `partially_grounded` (current) or
> `ungrounded`? Your call sets the standard the live judge is held to.
> Decision: ________________

**Verdict table (fill only if you disagree):**

| band | ids | gold | my verdict |
|------|-----|------|-----------|
| grounded | C-01…C-09 | grounded | all OK (high) |
| partially | C-10…C-17 | partially_grounded | all OK *given* current 3-class policy (high) |
| ungrounded | C-18…C-25 | ungrounded | all OK (high) |

**Effort:** ~15 min (one policy decision + a skim).

---

## 3. `rag_eval/triad_cases.json`  *(origin/main)*

**Labels:** 8 cases `{query, retrieved_chunks, answer, notes}`. Every case is
authored to be "grounded and relevant." No explicit per-case gold *score* — the
gold is the implicit assertion that each answer is context-relevant, grounded,
and answer-relevant.
**Used by:** `backend/eval/run_rag_triad.py` — **hard gate** at
context_relevance ≥ 0.15, groundedness ≥ 0.40, answer_relevance ≥ 0.15.

**My read:** I verified each answer is fully supported by its two chunks and
answers the query (e.g. T-01 housing cap EUR 2,500 + tier-1 EUR 3,200 — both in
chunks h1/h2). All 8 are correctly "grounded and relevant." **Draftable: 8/8
verdicts OK (high).**

> **NEEDS ROMAIN (product, not fact):** the three **gate thresholds**
> (0.15 / 0.40 / 0.15) are low and were set so synthetic content passes. Once
> the corpus is real, confirm the thresholds reflect the quality bar you want
> to enforce. Decision: ________________

**Effort:** ~10 min (threshold sanity-check; the 8 verdicts are confirm-only).

---

## 4. `eligibility/<corridor>/ground_truth.json`  *(origin/main, 5 corridors)*

**Labels:** per synthetic dossier → `eligibility_verdict.outcome_set` +
`eligibility_verdict.citations` (statute version IDs).
**Used by:** `backend/eval/run_eligibility_eval.py` — **hard CI gate**:
`outcome_accuracy = 1.0` AND `citation_effective_ratio = 1.0` (every cited rule
must be in force on the eval date 2026-07-01, per
`backend/eval/rule_registry.py`).

**Two separable parts:**

### 4a. Outcomes — I can draft (med-high)
The regime mapping is mechanical and I can reason about it from the profile:

| corridor | profile | outcome_set | my verdict | conf |
|----------|---------|-------------|-----------|------|
| BR_PT | Brazilian → Portugal, LTA | ELIGIBLE_WORK_PERMIT | plausible (non-EU → PT work/residence permit) | high |
| FR_NO | France(EU) → Norway(EEA), LTA | ELIGIBLE_EU_FREE_MOVEMENT | correct (EEA free movement) | high |
| IN_DE | Indian → Germany, LTA | ELIGIBLE_WORK_PERMIT | plausible (could be Blue Card §18g — see note) | med |
| UK_DE | British(post-Brexit) → Germany, LTA | ELIGIBLE_WORK_PERMIT | plausible (UK now third-country) | high |
| US_FR | American → France, LTA | ELIGIBLE_WORK_PERMIT | plausible (non-EU → FR salarié permit) | high |

*Note IN_DE:* fixture itself flags a future Blue Card (`AufenthG §18g`) regime
could refine §18b. Whether the *correct* authoritative outcome for a given
salary/qualification is skilled-worker (§18b) vs EU Blue Card (§18g) is a real
distinction — flagged below.

### 4b. Citations — **NEEDS ROMAIN (legal)**
These are the load-bearing legal cites and the eval gates on them being
"effective." Two are explicitly synthetic (`FR_CESEDA_L421:2024`,
`PT_LEI_23_2007_ART88:2007`) per the content-provenance model; the others look
real but I cannot legally verify them. **I will not assert these — they need a
human (you / immigration counsel) to confirm the statute, article, and version.**

| corridor | citations | status | NEEDS ROMAIN: confirm/correct |
|----------|-----------|--------|-------------------------------|
| BR_PT | `PT_LEI_23_2007_ART88:2007` | explicitly representative | art. 88 Lei 23/2007 = subordinate-work residence permit? still in force? ____ |
| FR_NO | `EU_DIR_2004_38_ART7:2004`, `NO_EOS_UTLENDINGS:2010` | look real | Dir 2004/38 art.7 + NO EEA reg correct? ____ |
| IN_DE | `DE_AUFENTHG_18B:2020` | look real | §18b vs §18g (Blue Card) for this profile? ____ |
| UK_DE | `DE_AUFENTHG_18B:2020` | look real | same §18b — right post-Brexit cite? ____ |
| US_FR | `FR_CESEDA_L421:2024` | explicitly representative | CESEDA L.421 "salarié" — correct article/year? ____ |

**Effort:** outcomes ~15 min (confirm my table, decide IN_DE §18b vs §18g);
citations = real legal-review work, 1–2 h or a counsel check. **This is the
highest-legal-risk set** — do not retire its `representative` flag without a
genuine legal sign-off.

---

## 5. `rag_eval/hr_policy/{queries,chunks}.jsonl`  *(origin/main)*

**Labels:** 18 queries, each with `expected_chunk_ids` (≥3), `intent_category`,
`difficulty`, `persona`, over a 57-chunk synthetic company-policy corpus for 3
fake companies (acme_standard, acme_executive, globex_standard).
**Used by:** `backend/scripts/eval_hr_policy_context_precision.py` + rerank tests
(`test_hr_policy_context_precision.py`, `test_hr_policy_rerank_precision.py`) —
lexical context-precision; bodies are deliberately authored so the offline eval
is deterministic.

**My read — two layers:**
- **Query → expected_chunk_id mappings (18/18 draftable, high):** these are
  internally consistent — e.g. Q-HRP-001 (housing cap) → the three
  `housing_cap.{monthly_cap,city_tier,eligibility}` chunks, which exist and are
  on-topic. The mapping is verifiable from the corpus itself; I confirmed
  spot-checks across housing, tax-equalization, schooling, intern. No mapping
  errors found.
- **Chunk *bodies* (NEEDS ROMAIN, product — low per-item risk):** the bodies are
  invented "representative" policy text (EUR 2,500 cap, 2 home-leave trips,
  etc.). They are *plausible* relocation-policy terms but are not any real
  ReloPass demo-company policy. Whether they're "representative enough" to
  retire the flag is a **product call**, not a fact I can settle. Low risk
  because no legal/PII exposure — it's demo policy text.

> **NEEDS ROMAIN (product):** Are these synthetic company-policy bodies an
> acceptable stand-in for the eval, or should they be replaced with the actual
> demo-company policy text used elsewhere in the product? Decision: __________

**Effort:** mappings ~20 min confirm; bodies = a single product decision
(accept-as-representative vs swap for real demo policy).

---

## 6. `ranking/golden_rankings.json`  *(origin/main)* — **mostly NEEDS ROMAIN**

**Labels:** 3 cases — `(category, corridor, criteria)` → `ideal_order` (full
ranking of ~10 supplier ids) + graded `relevance` {0,1,2,3}.
- banks / SG-SG / expat+digital priority 9
- insurance / SG-SG / health+travel, family
- movers / SG-JP / Singapore→Tokyo, 2-bed apartment, 2 people
**Used by:** `backend/eval/run_ranking_eval.py` — **hard gate** mean NDCG@5 ≥ 0.90.
The eval runs the live recommendation engine and scores its output against this
order. Per the fixture's own note, the engine "reproduces the golden ordering it
was seeded from," so a healthy run is ~1.0 — meaning **this gold currently just
mirrors the engine, it does not independently encode a human preference.**

**My read:** I **cannot** draft this responsibly.
1. Supplier ids (`b-1`…`b-10`, `i-*`, `m-*`) are opaque — I have not mapped them
   to real suppliers/attributes, so I can't judge whether `b-1 > b-9 > b-10` is
   the *right* order for an expat-friendly, digital-first SG banking customer.
2. The whole point of a golden ranking is to encode the **true user preference**;
   if it's seeded from engine output it's circular and proves nothing. Deciding
   the genuinely-correct order is exactly the domain/product judgment that needs
   a human.

> **NEEDS ROMAIN (product/domain):** For each of the 3 cases, is the
> `ideal_order` the order a real customer with those criteria *should* see, or
> is it just the engine's current output? If the latter, the gate is vacuous and
> the order needs to be set independently (ideally by you / a mobility SME)
> before it means anything.
> - banks SG-SG ideal_order correct? ____
> - insurance SG-SG ideal_order correct? ____
> - movers SG-JP ideal_order correct? ____

**Effort:** real product work — needs the supplier catalog mapping +
preference judgment. Lower urgency than sets 1/2/4 (gate is currently
self-fulfilling, so no false failures), but it provides little assurance until
curated.

---

## (Adjacent) Immigration `rag_eval/queries.jsonl` + `chunks.jsonl` + `corpus/*`

Not in the explicit task list, but the immigration sibling of set 5: 51 queries
/ 76 chunks across the 5 corridors, consumed by `eval_context_precision.py`.
Query→chunk **mappings** are draftable/verifiable like set 5; the **corpus
bodies are immigration facts** → same legal-review bucket as set 4b citations.
Flagging for completeness — recommend curating alongside set 4 (same SME).

---

## Bottom line

- **Fully draftable here (Romain = confirm only):** sets 1, 2, 3 (57 cases) +
  set 4 outcomes (5) + set 5 mappings (18) ≈ **80 units**.
- **Genuinely needs Romain's judgment:** set 4 **citations** (legal, 7 IDs —
  highest risk), set 6 **ranking order** (3 product calls), set 5 / immigration
  **chunk bodies** (product/legal sign-off).
- **Curate first:** `judge_calibration_cases.json` (anchors trust in every
  LLM-judge score; 25 confirm-only verdicts + 1 policy decision), then
  `feedback_triage/cases.jsonl` (LLM-triage flip decision; 24 confirm-only, on
  the CI gate). Both retire a `representative` flag in well under an hour.
