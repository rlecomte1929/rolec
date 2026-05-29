# Eval — `employment_contract_fr_v1.txt`

**Cohort:** C1-05P-c · **Locale:** France · **Model under test:** `claude-3-7-sonnet`

This eval validates the FR prompt's extraction accuracy and FR-annualization
correctness. Run this manually (or as part of the C1-05c agent test suite)
before approving the prompt for production use.

---

## Acceptance bar (from Notion AIQ-524 validation criteria)

| Metric                                  | Bar       |
|-----------------------------------------|-----------|
| Field-level extraction accuracy         | ≥ 90 %    |
| Annualization correctness               | 100 %     |
| `gross_salary_guaranteed_fixed_only_bool` correctness | 100 % |
| Registry-ID format correctness          | 100 %     |

The eval set is small (2 FR fixtures here, 2 DE, 2 NO across the sibling
files = 6 contracts total) so a single wrong field on annualization or
the fixed-only bool is a hard fail.

---

## Methodology

1. For each fixture below, send the `INPUT` block as a single user
   message to `claude-3-7-sonnet` along with the contents of
   `employment_contract_fr_v1.txt` as the system prompt.
2. Enable the `extract_employment_contract` tool (schema in the prompt
   file).
3. Capture the tool call's input JSON as the actual output.
4. Diff against the `EXPECTED` block field-by-field.
5. Record results in the "Results" table at the bottom.

Scoring:
- **Field accuracy** = (#fields matching expected exactly) / (#fields in expected)
- Strings are compared case-sensitively. Decimal strings compared numerically.
- ISCO-08 codes: a `null` actual when expected is non-null counts as
  *partial* (acceptable — the prompt explicitly tells the model to
  return `null` when unsure), not a fail.
- `extraction_notes` is NOT scored — it's a free-text aid for the
  human reviewer. Read it qualitatively for sanity.

---

## Fixtures

### FR-1 — CDI fixed salary, no variable

(Identical to Exemplar 1 in the prompt — included here as an eval
fixture so we measure whether the model memorises the exemplar. A
"pass" here is necessary but not sufficient.)

**INPUT** — see `employment_contract_fr_v1.txt` Exemplar 1.

**Expected gold label:**
- `is_employment_contract`: `true`
- `contract_type`: `"CDI"`
- `employer_legal_name`: `"LUMIERE PRODUCTIONS SAS"`
- `employer_registry_id`: `"824657193"` (kind: `"SIREN"`)
- `position_title`: `"Cheffe de projet éditoriale"`
- `gross_salary_annual`: `"54000.00"` (EUR)
- `gross_salary_guaranteed_fixed_only_bool`: `true`
- `contract_start_date`: `"2026-09-01"`
- `contract_duration_months`: `null`
- `working_time_percent`: `100`

### FR-2 — CDD with variable + discretionary 13e mois

(Identical to Exemplar 2.)

**Expected gold label:**
- `is_employment_contract`: `true`
- `contract_type`: `"CDD"`
- `employer_legal_name`: `"NORDIC LOGISTICS FRANCE SARL"`
- `employer_registry_id`: `"51234567800027"` (kind: `"SIRET"`)
- `position_title`: `"Responsable commercial export"`
- `gross_salary_annual`: `"38400.00"` (EUR) — base only, 13e excluded as discretionary
- `gross_salary_guaranteed_fixed_only_bool`: `false`
- `contract_start_date`: `"2027-01-06"`
- `contract_duration_months`: `6`
- `working_time_percent`: `100`

---

## Held-out fixtures (NOT in the prompt)

These exist to measure generalisation. The model has not seen them as
exemplars. Author 2+ additional fixtures here before scoring acceptance;
the bar above applies to the held-out set only, NOT the in-prompt set.

> **TODO for reviewer / C1-05c executor:** add 2+ held-out FR contracts
> here (e.g. a CDI with guaranteed 13e mois that DOES count toward
> annualization; a CDD à temps partiel 50 %). Source from public
> templates on legifrance.gouv.fr or service-public.fr templates,
> anonymise, paste below.

---

## Results

| Run date   | Model        | Fixture | Field acc. | Annual. correct | Fixed-only bool correct | Registry-ID correct | Notes |
|------------|--------------|---------|-----------:|:---------------:|:-----------------------:|:-------------------:|-------|
| YYYY-MM-DD | sonnet-3-7   | FR-1    |        % |       ⬜        |           ⬜            |         ⬜          |       |
| YYYY-MM-DD | sonnet-3-7   | FR-2    |        % |       ⬜        |           ⬜            |         ⬜          |       |
| YYYY-MM-DD | sonnet-3-7   | FR-3 (held-out) | % |       ⬜        |           ⬜            |         ⬜          |       |

**Pass / Fail / Iterate:** ⬜

**Iteration notes:**
- (record any prompt-tuning rounds and what changed)

---

## What to do when a field fails

- **Annualization wrong** → the rule in the "Annualization (FR)" section
  needs sharper language or a counter-exemplar. Add a held-out fixture
  covering the failure mode and re-test.
- **Fixed-only bool wrong** → the exclusion-keyword list is incomplete
  or the prompt is interpreting "intéressement statutaire" too loosely.
  Edit the keyword list.
- **Registry-ID format wrong** → the model returned with separators or
  the wrong prefix. Reinforce the format rule with a held-out fixture
  containing both SIREN and SIRET (so the model has to pick).
- **`position_isco_2008` wrong** → acceptable if `null`. If the model is
  guessing, tighten the "Confidence ≥ medium required" guard.
