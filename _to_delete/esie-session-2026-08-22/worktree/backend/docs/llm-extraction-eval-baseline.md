# LLM Policy Extraction — Eval Baseline

**Captured:** 2026-05-27  
**Script:** `backend/scripts/eval_llm_policy_extraction.py`  
**Fixture set:** `backend/tests/fixtures/policy_eval_set/` (5 fixtures, 30 gold benefit-keys)  
**Model under test:** `claude-sonnet-4-6` (env: `RELOPASS_LLM_POLICY_MODEL`)

---

## How to re-run

```bash
# Regex baseline only (no API key needed):
python backend/scripts/eval_llm_policy_extraction.py --skip-llm

# Regex + LLM side-by-side:
ANTHROPIC_API_KEY=sk-... python backend/scripts/eval_llm_policy_extraction.py

# Machine-readable JSON (for dashboards / CI):
python backend/scripts/eval_llm_policy_extraction.py --json
```

Pass `F1 ≥ 0.75` as the minimum acceptable bar. Any run where F1 drops below 0.75
for either extractor should trigger a prompt audit before deploying.

---

## Fixture set summary

| # | File | Description | Gold benefit-keys |
|---|------|-------------|-------------------|
| 1 | `01-comprehensive` | Full policy, all 11 standard benefits stated explicitly | 11 |
| 2 | `02-minimal` | Thin policy — only 2 benefits (visa, travel) | 2 |
| 3 | `03-ambiguous-housing` | Multi-currency housing caps (NOK/GBP/USD/SGD); amounts not in a single number | 3 |
| 4 | `04-no-eligibility` | 5 benefits stated, zero eligibility / band / assignment-type info | 5 |
| 5 | `05-table-heavy` | Table-formatted policy; labels in column headers rather than prose | 9 |

Edge cases exercised: missing fields (04), ambiguous/multi-currency amounts (03),
table-heavy formatting (05), minimal policy (02).

---

## Baseline numbers — 2026-05-27

### Regex extractor (`extracted_by: regex`)

| Fixture | Gold | Pred | TP | FP | FN | P | R | F1 |
|---------|------|------|----|----|----|---|---|----|
| 01-comprehensive | 11 | 11 | 11 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| 02-minimal | 2 | 2 | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| 03-ambiguous-housing | 3 | 3 | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| 04-no-eligibility | 5 | 5 | 5 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| 05-table-heavy | 9 | 9 | 9 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| **OVERALL** | **30** | **30** | **30** | **0** | **0** | **1.00** | **1.00** | **1.00** |

> **Why 1.00 across the board?** The eval fixtures were built using the same benefit-key
> vocabulary (`BENEFIT_KEYS` in `policy_extractor.py`) that the regex layer scans for.
> The regex extractor will score perfectly on any fixture whose policy text contains the
> exact trigger keywords. This is expected and correct for a baseline — it confirms the
> fixture harness wires up properly. The interesting signal appears when the LLM extractor
> is run and compared: the LLM should catch benefits that are paraphrased or implied
> without the exact regex keywords, while the regex extractor will miss those and score
> lower on harder, real-world fixtures added in future iterations.

### LLM extractor (`extracted_by: ai`) — pending

LLM baseline not yet captured — requires `ANTHROPIC_API_KEY` to be set in the run
environment. Run the following to update this doc:

```bash
ANTHROPIC_API_KEY=sk-... python backend/scripts/eval_llm_policy_extraction.py --json \
  | python -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d['llm'], indent=2))"
```

Copy the `overall` block here once captured. Expected outcome: LLM F1 ≥ regex F1 on
fixtures 03 and 05 (the ambiguous and table-heavy cases where regex keyword matching
is weakest).

---

## Interpreting results

| Signal | Meaning | Action |
|--------|---------|--------|
| Regex F1 drops on existing fixtures | A BENEFIT_KEYS keyword was removed or fixture text changed | Check git diff on `policy_extractor.py` or fixture files |
| LLM F1 < Regex F1 on comprehensive fixture | Model regression or prompt change degraded extraction | Roll back last prompt / model change |
| LLM F1 > Regex F1 on fixtures 03 / 05 | LLM handling ambiguous language better than regex | Good — expected. Consider raising the pass bar |
| Both extractors have FP > 0 | Extractor is hallucinating benefit-keys not in gold | Review prompt or regex keyword list |

---

## Adding new fixtures

1. Create `backend/tests/fixtures/policy_eval_set/NN-<slug>.txt` — anonymised policy text.
2. Create `backend/tests/fixtures/policy_eval_set/NN-<slug>.gold.json` — see existing gold files for schema.
   The `benefits` array should contain only `benefit_key` strings.
3. Run `python backend/scripts/eval_llm_policy_extraction.py --skip-llm` — confirm regex scores
   match your expectations, then update this doc with the new baseline row.

Real-world fixture guidelines:
- Strip all identifying information: company names → `Acme Corp`, amounts ≥ industry norm → keep, amounts that could identify a client → round to nearest 500.
- One fixture per document type you want to protect against regression.
- Aim for ≥ 10 fixtures (currently 5) before enabling the nightly CI gate.
