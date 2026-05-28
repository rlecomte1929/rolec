# Eval — `payslip_v1.txt`

**Cohort:** C1-05P-d · **Locales:** FR / DE / NO
**Model under test:** `gpt-4o-mini` (default) and `claude-3-7-sonnet` (escalation)

This eval validates payslip extraction across three radically different
layouts (FR bulletin de paie, DE Lohnabrechnung, NO lønnsslipp) and —
critically — the anti-hallucination rule: when a field is ambiguous,
the model must emit `null` + finding rather than guess.

---

## Acceptance bar (from Notion AIQ-525 validation criteria)

Different bars per locale, reflecting OCR difficulty:

| Locale  | Field-level extraction accuracy | Notes                                       |
|---------|----------------------------------|---------------------------------------------|
| FR      | ≥ 90 %                          | DSN-2019 standardised layout — cleanest case |
| DE      | ≥ 90 %                          | Lohnabrechnung typically clean              |
| NO      | ≥ 70 %                          | Dense tables — Cohort 3 Reducto closes the gap |

Cross-locale invariants (all 100 %):

| Metric                                                | Bar       |
|-------------------------------------------------------|-----------|
| Locale detection correctness                          | 100 %     |
| Anti-hallucination compliance (no invented values when ambiguous) | 100 %     |
| Annualization correctness (derived_annual per locale rule)        | 100 %     |
| Currency identification (EUR for FR/DE, NOK for NO)   | 100 %     |
| Schema validation (every tool call deserialises against schema)   | 100 %     |

**Anti-hallucination compliance** is the cardinal metric. A model that
correctly emits `null` + AMBIGUOUS_CANDIDATES on a smudged OCR field
scores BETTER than one that confidently extracts a wrong value with no
finding. Score this binary: did the model invent a value where it
should have flagged? If yes, automatic fail for this metric on that
fixture regardless of how the rest scored.

---

## Methodology

1. For each fixture, send the `INPUT (OCR)` block as a single user
   message to the model along with `payslip_v1.txt` as the system
   prompt.
2. Enable the `extract_payslip` tool (schema in the prompt file).
3. Capture the tool call's input JSON as the actual output.
4. Diff against the `EXPECTED` block field-by-field.
5. Validate annualization: confirm `derived_annual` matches the
   per-locale formula given the values the model extracted (not the
   gold label — the model is consistent with itself).
6. Record results in the table.

Scoring rules:
- **String/decimal field match** = exact string equality (decimals are
  compared as 2-dp strings, so `"68000.00"` ≠ `"68000.0"`).
- **Date match** = exact ISO `YYYY-MM-DD`.
- **`employer_name_normalized` match** = string equality, but a
  near-miss that still drops the legal-form suffix correctly counts as
  passing — fuzzy matching is the downstream C1-07 resolver's job.
- **`findings[]` match** = (code, severity) tuple membership: the
  expected findings must all be present; extra INFO findings are OK;
  extra WARN/ERROR findings are NOT.
- **`consecutive_periods[]` match** = exact array of period objects,
  ignoring order.
- **`extraction_notes` is NOT scored** — read it qualitatively for
  sanity.

---

## Fixtures

### FR fixtures

#### FR-1 — Clean monthly, no bonuses
(Exemplar 1.) Gold label: `gross_monthly: "4500.00"`,
`derived_annual: "54000.00"` (× 12 because period is 03/2027 and 13e
mois evidence is not present), `consecutive_periods: []`.

#### FR-2 — Prime variable on T2 objectives
(Exemplar 2.) Gold label: `gross_monthly: "3200.00"` (the FIXED line,
NOT 4480 total brut), `derived_annual: "38400.00"` (3200 × 12, prime
excluded), VARIABLE_PAY_EXCLUDED finding required.

**Critical test:** if the model returns `gross_monthly: "4480.00"`
(total brut) instead of `"3200.00"` (base brut), the fixed-component-
only convention is broken and C1-08 false-positives downstream.

#### FR-3 — 3-month recap
(Exemplar 3.) Gold label: `consecutive_periods` array with 3 items
(Sept/Oct/Nov 2027), `derived_annual: "45600.00"`.

**Critical test:** the `consecutive_periods` array must have exactly 3
items, each with the correct `period_start`/`period_end` date pairs.
Missing the recap means C1-08 loses its strongest contradiction signal.

### DE fixtures

#### DE-1 — Clean Lohnabrechnung
(Exemplar 1.) Gold label: `gross_monthly: "5800.00"`,
`tax_withheld: "1190.97"` (Lohnsteuer + Soli + Kirchensteuer, NOT
including KV/RV/AV/PV), `derived_annual: "69600.00"`.

**Critical test:** if the model puts KV/RV/AV/PV (social) into
`tax_withheld`, it has confused income tax with social contributions.
This is the #1 DE failure mode.

#### DE-2 — Weihnachtsgeld vertraglich garantiert (× 13)
(Exemplar 2.) Gold label: `de_weihnachtsgeld_paid_this_period: true`,
`derived_annual: "75400.00"` (5800 × 13).

**Critical test:** the model must (a) set the bool to `true` AND (b)
compute × 13. Setting bool to `true` but computing × 12 is half-right
and breaks downstream.

#### DE-3 — Freiwilliges Weihnachtsgeld + Tantieme
(Exemplar 3.) Gold label: `de_weihnachtsgeld_paid_this_period:
false` (because freiwillig), `derived_annual: "110400.00"`
(9200 × 12, NOT × 13), DE_WEIHNACHTSGELD_FREIWILLIG_EXCLUDED
finding required.

**Critical test:** this is the inverse of DE-2 — the model must
correctly distinguish `"freiwillig, ohne Rechtsanspruch"` from
`"vertraglich garantiert"`. The same word "Weihnachtsgeld" appears in
both; only the qualifier changes the annualization. Mis-classification
here produces a 75 % overestimate of annual salary.

### NO fixtures (the hard set)

#### NO-1 — Clean lønnsslipp, 12 % feriepenger
(Exemplar 1.) Gold label: `gross_monthly: "68000.00"`,
`no_5_ferieuke_indicated: true`, `derived_annual: "878560.00"`
(68000 × 12.92).

**Critical test:** the model must recognise the
`"5. ferieuke tariffestet"` phrase as the × 12.92 trigger.

#### NO-2 — Table OCR misalignment
(Exemplar 2.) Gold label: `gross_monthly: "52000.00"` (Fastlønn line,
NOT 54658 Bruttolønn total), TABLE_OCR_MISALIGNMENT WARN finding
required, NO_FERIEPENGER_DEFAULT_ASSUMED INFO finding required
(because the lønnsslipp doesn't state feriepenger %).

**Critical test:** the model must (a) prefer Fastlønn over Bruttolønn
for `gross_monthly` and (b) NOT assume × 12.92 in the absence of
explicit 12 % / 5. ferieuke language. Going with the statutory 10.2 %
default (× 12) when no information is provided is the correct
conservative call.

#### NO-3 — 3-period recap + USD-quoted contract
(Exemplar 3.) Gold label: `gross_monthly: "137500.00"` (NOK-converted
fastlønn, NOT 962500 December-with-bonus total),
`consecutive_periods` with 3 items, `derived_annual: "1776500.00"`
(137500 × 12.92).

**Critical test:** the model must NOT include the December bonus in
`gross_monthly` even though it's the largest line on the page.
The bonus correctly inflates the December recap entry but the
fixed-component-only annualization uses Fastlønn.

---

## Anti-hallucination held-out fixtures (TODO)

> **TODO for reviewer / C1-05d executor:** the 9 in-prompt fixtures
> are clean enough that anti-hallucination doesn't bite hard. Add
> held-out fixtures specifically designed to test the refuse-pattern:
>
> - NO lønnsslipp with deliberately smudged "Bruttolønn" cell where
>   two plausible numbers appear. Expected: `gross_monthly: null` +
>   AMBIGUOUS_CANDIDATES finding listing both numbers.
> - DE Lohnabrechnung where the document is in DUTCH (not German). The
>   model should refuse — emit `locale_iso2: null` + LOCALE_UNDETERMINED.
> - FR bulletin where the OCR cuts off mid-page so "Net à payer" is
>   missing. Expected: `net_monthly: null` + OCR_UNREADABLE.
> - DE payslip with Weihnachtsgeld but the freiwillig/garantiert
>   qualifier is in a partly-truncated note. Expected: bool null +
>   AMBIGUOUS_CANDIDATES finding listing both interpretations.

These held-out fixtures are where the cardinal anti-hallucination rule
actually gets tested. The in-prompt fixtures only check that the
existing rules fire correctly on clean inputs.

---

## Results

| Run date   | Model        | Fixture | Locale | Field acc. | Annual. correct | Anti-halluc. compliance | Schema valid | Notes |
|------------|--------------|---------|--------|-----------:|:---------------:|:-----------------------:|:------------:|-------|
| YYYY-MM-DD | gpt-4o-mini  | FR-1    |   FR   |        % |       ⬜        |           ⬜            |      ⬜      |       |
| YYYY-MM-DD | gpt-4o-mini  | FR-2    |   FR   |        % |       ⬜        |           ⬜            |      ⬜      |       |
| YYYY-MM-DD | gpt-4o-mini  | FR-3    |   FR   |        % |       ⬜        |           ⬜            |      ⬜      |       |
| YYYY-MM-DD | gpt-4o-mini  | DE-1    |   DE   |        % |       ⬜        |           ⬜            |      ⬜      |       |
| YYYY-MM-DD | gpt-4o-mini  | DE-2    |   DE   |        % |       ⬜        |           ⬜            |      ⬜      |       |
| YYYY-MM-DD | gpt-4o-mini  | DE-3    |   DE   |        % |       ⬜        |           ⬜            |      ⬜      |       |
| YYYY-MM-DD | gpt-4o-mini  | NO-1    |   NO   |        % |       ⬜        |           ⬜            |      ⬜      |       |
| YYYY-MM-DD | gpt-4o-mini  | NO-2    |   NO   |        % |       ⬜        |           ⬜            |      ⬜      |       |
| YYYY-MM-DD | gpt-4o-mini  | NO-3    |   NO   |        % |       ⬜        |           ⬜            |      ⬜      |       |
| YYYY-MM-DD | sonnet-3-7   | NO-2 (escalation) | NO |   %  |       ⬜        |           ⬜            |      ⬜      |       |
| YYYY-MM-DD | sonnet-3-7   | held-out anti-halluc | * |  %  |       ⬜        |           ⬜            |      ⬜      |       |

**Per-locale rollup:**
- FR aggregate: ___ % field accuracy (bar: ≥ 90 %) ⬜
- DE aggregate: ___ % field accuracy (bar: ≥ 90 %) ⬜
- NO aggregate: ___ % field accuracy (bar: ≥ 70 %) ⬜

**Overall pass / fail / iterate:** ⬜

**Iteration notes:**
- (record any prompt-tuning rounds and what changed)

---

## What to do when a check fails

- **Locale detection wrong**: usually the model latched onto the
  currency symbol but missed the label vocabulary. Reinforce the
  priority order: vocabulary > format > symbol.
- **`gross_monthly` includes variable pay**: strengthen the
  fixed-component-only rule. Add a held-out fixture where the variable
  line is LARGER than the fixed line so the model can't just pick the
  bigger number.
- **`tax_withheld` includes social contributions (DE)**: add an
  explicit counter-exemplar where KV/RV/AV/PV is the largest line in
  the Abzüge column.
- **Weihnachtsgeld vertraglich-vs-freiwillig confusion**: this is
  high-stakes. Add 2+ held-out DE fixtures, one of each, with
  near-identical surface formatting so the only signal is the
  qualifier phrase.
- **NO Bruttolønn vs Fastlønn confusion**: the Fastlønn-preferred rule
  needs sharper language. Consider making the rule a top-level
  IMPORTANT block rather than a per-locale-guide bullet.
- **Anti-hallucination violation** (model invented a value when it
  should have flagged): this is the most serious failure. Walk through
  the prompt's anti-hallucination section with the failing fixture
  inline as a counter-example. Possibly add a synthetic exemplar that
  demonstrates the refuse pattern explicitly.
- **Annualization formula wrong**: the per-locale table needs sharper
  trigger language. NO is the most error-prone (12.92 trigger phrase
  must be exact).
- **Currency silently normalised**: especially USD-quoted contracts
  paid in NOK (NO-3 case). The currency_iso3 must reflect the payslip's
  currency, not the contract's.

---

## Cohort 3 outlook

Norwegian lønnsslipp accuracy is intentionally accepted to fall short
in Cohort 1 (acceptance bar = 70 %, not 90 %). The R-05 Reducto
fallback in Cohort 3 will close the gap by using a dedicated
table-aware extractor before this prompt sees the document. When that
lands, the NO bar should rise to ≥ 90 % matching FR/DE.

For Cohort 1, NO_FERIEPENGER_DEFAULT_ASSUMED + TABLE_OCR_MISALIGNMENT
findings effectively flag the cases the human reviewer should
double-check — the system fails LOUDLY rather than silently, which
preserves trust.
