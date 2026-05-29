# Eval — `employment_contract_no_v1.txt`

**Cohort:** C1-05P-c · **Locale:** Norway · **Model under test:** `claude-3-7-sonnet`

This eval validates the NO prompt's extraction accuracy and NO-annualization
correctness (feriepenger / 5. ferieuke rule).

---

## Acceptance bar (from Notion AIQ-524 validation criteria)

| Metric                                                | Bar       |
|-------------------------------------------------------|-----------|
| Field-level extraction accuracy                       | ≥ 90 %    |
| Annualization correctness (feriepenger × 12 vs × 12.92) | 100 %   |
| `gross_salary_guaranteed_fixed_only_bool` correctness | 100 %     |
| Organisasjonsnummer format (9 digits, no separators)  | 100 %     |

---

## Methodology

Identical to the FR/DE evals: system prompt = `employment_contract_no_v1.txt`,
user message = fixture `INPUT`, tool `extract_employment_contract`
enabled, diff against expected.

---

## Fixtures

### NO-1 — Fast stilling, 12 % feriepenger + 5. ferieuke explicit

(Identical to Exemplar 1 in the prompt.)

**Expected gold label:**
- `is_employment_contract`: `true`
- `contract_type`: `"FAST"`
- `employer_legal_name`: `"FJORDLYS ENERGI AS"`
- `employer_registry_id`: `"918542003"` (kind: `"ORGNR"`)
- `position_title`: `"Seniorrådgiver fornybar energi"`
- `gross_salary_annual`: `"878560.00"` (NOK) — `68000 × 12.92` because 5. ferieuke is explicitly granted with 12 % feriepenger
- `gross_salary_guaranteed_fixed_only_bool`: `true`
- `contract_start_date`: `"2027-08-02"`
- `contract_duration_months`: `null`
- `working_time_percent`: `100`

**Critical test:** if the model returns `gross_salary_annual = "816000.00"`
(`68000 × 12`), it has missed the 5. ferieuke / 12 % feriepenger
multiplier. The trigger phrases here are `"feriepenger utgjør 12 %"`
+ `"Ferieloven § 15 (tariffestet 5. ferieuke)"`.

### NO-2 — Midlertidig, USD-denominert, salgsprovisjon + opsjoner + tiltredelsesbonus

(Identical to Exemplar 2.)

**Expected gold label:**
- `is_employment_contract`: `true`
- `contract_type`: `"MIDLERTIDIG"`
- `employer_legal_name`: `"NORDLYS MARITIME ASA"`
- `employer_registry_id`: `"988011247"` (kind: `"ORGNR"`)
- `position_title`: `"Salgsdirektør Asia-Pacific"`
- `gross_salary_annual`: `"161500.00"` (USD) — `12500 × 12.92`, FIXED COMPONENT ONLY (provisjon, bonus, opsjoner, tiltredelsesbonus excluded per the guaranteed-fixed-only rule)
- `currency_iso3`: `"USD"` — unusual for a NO contract but explicit in source
- `gross_salary_guaranteed_fixed_only_bool`: `false`
- `contract_start_date`: `"2027-09-01"`
- `contract_duration_months`: `24`
- `working_time_percent`: `100`

**Critical tests:**
- If the model adds the salgsprovisjon, bonus, or tiltredelsesbonus to
  `gross_salary_annual`, the fixed-only convention is broken — the
  C1-09 downstream threshold check will produce false-positive Blue
  Card approvals.
- If the model normalises USD → NOK at some assumed rate, that is
  ALSO a fail. The prompt explicitly says "do not silently normalise"
  for currency.

---

## Held-out fixtures (NOT in the prompt)

> **TODO for reviewer / C1-05c executor:** add 2+ held-out NO contracts
> covering:
> - A fast stilling with ONLY statutory 10.2 % feriepenger (no 5.
>   ferieuke) — tests that the model does NOT spuriously apply × 12.92
> - A tilkalling / on-call contract with hourly rate (tests the hourly
>   annualization formula `hourly × 37.5 × 52`)
> - A 60 % deltidsstilling (tests `working_time_percent` non-100 case)

---

## Results

| Run date   | Model        | Fixture | Field acc. | Annual. correct | Fixed-only bool correct | Registry-ID correct | Notes |
|------------|--------------|---------|-----------:|:---------------:|:-----------------------:|:-------------------:|-------|
| YYYY-MM-DD | sonnet-3-7   | NO-1    |        % |       ⬜        |           ⬜            |         ⬜          |       |
| YYYY-MM-DD | sonnet-3-7   | NO-2    |        % |       ⬜        |           ⬜            |         ⬜          |       |
| YYYY-MM-DD | sonnet-3-7   | NO-3 (held-out) | % |       ⬜        |           ⬜            |         ⬜          |       |

**Pass / Fail / Iterate:** ⬜

**Iteration notes:**
- (record any prompt-tuning rounds and what changed)

---

## What to do when a field fails

- **Feriepenger × 12.92 misapplied to 10.2 % case** → the rule needs
  sharper language: "ONLY × 12.92 when the contract EXPLICITLY grants
  the 5. ferieuke OR states 12 % feriepenger; never apply on default
  Ferieloven mention alone."
- **Provisjon / bonus included in `gross_salary_annual`** → strengthen
  the IMPORTANT block at the top of the Annualization section. Add a
  held-out fixture with a single bonus to drive the point.
- **Organisasjonsnummer with separators** → the model returned
  `"918 542 003"` instead of `"918542003"`. Reinforce "digits only, no
  separators" with a counter-exemplar.
- **Currency silently normalised USD → NOK** → add an explicit
  failure-mode note in the Hard rules section.
