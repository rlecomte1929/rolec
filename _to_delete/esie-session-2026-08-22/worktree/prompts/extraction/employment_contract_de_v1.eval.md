# Eval — `employment_contract_de_v1.txt`

**Cohort:** C1-05P-c · **Locale:** Germany · **Model under test:** `claude-3-7-sonnet`

This eval validates the DE prompt's extraction accuracy and DE-annualization
correctness (Weihnachtsgeld guaranteed-vs-freiwillig rule).

---

## Acceptance bar (from Notion AIQ-524 validation criteria)

| Metric                                                | Bar       |
|-------------------------------------------------------|-----------|
| Field-level extraction accuracy                       | ≥ 90 %    |
| Annualization correctness (Weihnachtsgeld rule)       | 100 %     |
| `gross_salary_guaranteed_fixed_only_bool` correctness | 100 %     |
| Registry-ID format (`HRB <digits>` / `HRA <digits>`)  | 100 %     |

---

## Methodology

Identical to the FR eval: system prompt = `employment_contract_de_v1.txt`,
user message = fixture `INPUT`, tool `extract_employment_contract`
enabled, diff against expected.

---

## Fixtures

### DE-1 — Arbeitsvertrag unbefristet, 13. Monatsgehalt vertraglich garantiert

(Identical to Exemplar 1 in the prompt.)

**Expected gold label:**
- `is_employment_contract`: `true`
- `contract_type`: `"UNBEFRISTET"`
- `employer_legal_name`: `"WALDSTERN GMBH"`
- `employer_registry_id`: `"HRB 248915"` (kind: `"HRB"`)
- `position_title`: `"Senior Datenanalystin"`
- `gross_salary_annual`: `"75400.00"` (EUR) — `5800 × 13` because Weihnachtsgeld is contractually guaranteed
- `gross_salary_guaranteed_fixed_only_bool`: `true`
- `contract_start_date`: `"2027-03-15"`
- `contract_duration_months`: `null`
- `working_time_percent`: `100`

**Critical test:** if the model returns `gross_salary_annual = "69600.00"`
(i.e. `5800 × 12`, ignoring the guaranteed 13.), this is an annualization
failure — the language `"vertraglich garantiertes"` + `"Anspruch besteht"`
is the exact phrasing that flips ×12 → ×13.

### DE-2 — Arbeitsvertrag befristet, Tantieme + Aktienoptionen + freiwilliges Weihnachtsgeld

(Identical to Exemplar 2.)

**Expected gold label:**
- `is_employment_contract`: `true`
- `contract_type`: `"BEFRISTET"`
- `employer_legal_name`: `"NORDKAP BIOTECH AG"`
- `employer_registry_id`: `"HRB 174326"` (kind: `"HRB"`)
- `position_title`: `"Leiter klinische Studien"`
- `gross_salary_annual`: `"110400.00"` (EUR) — `9200 × 12` because Weihnachtsgeld is freiwillig
- `gross_salary_guaranteed_fixed_only_bool`: `false`
- `contract_start_date`: `"2027-06-01"`
- `contract_duration_months`: `24`
- `working_time_percent`: `100`

**Critical test:** if the model returns `gross_salary_annual = "119600.00"`
(`9200 × 13`), it has ignored `"kann gewährt werden"` + `"Rechtsanspruch
besteht nicht"` — the exact phrasing for German freiwillige Sonderzahlungen.
This is the high-stakes failure mode for the DE prompt.

---

## Held-out fixtures (NOT in the prompt)

> **TODO for reviewer / C1-05c executor:** add 2+ held-out DE contracts
> covering:
> - A GmbH & Co. KG with HRA registry-ID (tests the HRA-vs-HRB pattern)
> - A Werkstudentenvertrag with explicit 20 Wochenstunden (tests
>   `working_time_percent` partial calculation)
> - A Minijob with monthly < 538 € (tests the low-end working-time edge)

---

## Results

| Run date   | Model        | Fixture | Field acc. | Annual. correct | Fixed-only bool correct | Registry-ID correct | Notes |
|------------|--------------|---------|-----------:|:---------------:|:-----------------------:|:-------------------:|-------|
| YYYY-MM-DD | sonnet-3-7   | DE-1    |        % |       ⬜        |           ⬜            |         ⬜          |       |
| YYYY-MM-DD | sonnet-3-7   | DE-2    |        % |       ⬜        |           ⬜            |         ⬜          |       |
| YYYY-MM-DD | sonnet-3-7   | DE-3 (held-out) | % |       ⬜        |           ⬜            |         ⬜          |       |

**Pass / Fail / Iterate:** ⬜

**Iteration notes:**
- (record any prompt-tuning rounds and what changed)

---

## What to do when a field fails

- **Weihnachtsgeld misclassification** → strengthen the "freiwillig"
  keyword list. Add the exact phrasing from the failed fixture as a
  counter-exemplar.
- **HRB / HRA confusion** → the format-rule paragraph needs a concrete
  HRA example. The current prompt only shows HRB in exemplars.
- **Steuernummer leaking into `employer_registry_id`** → add explicit
  guard ("Do NOT use Steuernummer or USt-IdNr") even more prominently.
