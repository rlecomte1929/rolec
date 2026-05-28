# Eval — `passport_td3_v1.txt`

**Cohort:** C1-05P-b · **Coverage:** FR / DE / NO / IN / US TD3 passports
**Model under test:** `gpt-4o-mini` (default) and `claude-3-7-sonnet` (escalation)

This eval validates the PASSPORT_TD3 non-MRZ prompt across five issuing
states. The hardest things to get right are (a) NOT re-extracting MRZ
fields, (b) classifying body↔MRZ discrepancies correctly as INFO
(legitimate transliteration) vs WARN (substantive disagreement), and
(c) capturing the consequential per-state endorsements (ECNR/ECR for
IN; PT.5 for DE; diplomatic markers everywhere).

---

## Acceptance bar (from Notion AIQ-523 validation criteria)

| Metric                                                       | Bar       |
|--------------------------------------------------------------|-----------|
| Field-level extraction accuracy (issuing_authority + endorsements) | ≥ 90 %    |
| MRZ-field-leakage rate (model outputting MRZ values)         | 0 %       |
| Discrepancy severity classification correctness              | ≥ 95 %    |
| ECNR/ECR endorsement recall on IN fixtures                   | 100 %     |
| Schema validation (every tool call deserialises against schema) | 100 %     |

MRZ-field-leakage = 0 % is the hardest constraint and the one that
matters most: a single leaked value lets the LLM silently override the
deterministic MRZ parser, which is exactly what the architecture
forbids.

---

## Methodology

1. For each fixture below, send the `BODY TEXT (OCR)` block + the
   `MRZ_PARSE` JSON block as a single user message to the model along
   with the contents of `passport_td3_v1.txt` as the system prompt.
2. Enable the `extract_passport_td3_non_mrz` tool (schema in the prompt
   file).
3. Capture the tool call's input JSON as the actual output.
4. Diff against the `EXPECTED` block field-by-field.
5. Verify NO MRZ-derived field (`surname`, `given_names`,
   `document_number`, `nationality_iso3`, `issuing_state_iso3`,
   `date_of_birth`, `sex`, `expiry_date`, `personal_number`) appears
   as a value anywhere in the output payload. The schema does not
   contain these keys, so this should be impossible by construction —
   but if the model puts an MRZ value inside an `endorsements[].text`
   or `extraction_notes`, that's a leak.
6. Record results in the "Results" table.

Scoring:
- **issuing_authority match** — string equality (case-sensitive,
  diacritic-preserving).
- **endorsements match** — set-equality on `(type, text)` tuples;
  ordering doesn't matter.
- **mrz_body_discrepancies match** — set-equality on
  `(field, severity)` tuples. The `reason` text is qualitative —
  read it but don't score it strictly.
- **Schema validation** — tool call MUST satisfy the input_schema in
  the prompt. Any field outside the schema = automatic fail for this
  metric.

---

## Fixtures

### TD3-FR — French passport, clean

(Identical to Exemplar 1 in the prompt.)

**Expected gold label:**
- `issuing_authority`: `"Préfecture de Police de Paris 75-101"`
- `endorsements`: `[]`
- `mrz_body_discrepancies`: 1 INFO (`surname`, Latin diacritic fold LAFORÊT↔Laforet)
- `agent_confidence`: `"high"`

**Critical test:** the model must NOT emit `surname: "LAFORÊT"` or
`given_names: "Théo Marc"` anywhere — those go through the MRZ parser.

### TD3-DE — German Reisepass, Umlaut + PT.5

(Identical to Exemplar 2.)

**Expected gold label:**
- `issuing_authority`: `"Stadt München"` (with Umlaut preserved)
- `endorsements`: 1 × `DUAL_NATIONALITY` with verbatim PT.5 text
- `mrz_body_discrepancies`: 1 INFO (`surname`, Ü↔UE)
- `agent_confidence`: `"high"`

**Critical test:** if the model classifies GRÜNEWALD↔Gruenewald as
WARN instead of INFO, it has missed the DEU Umlaut reverse rule. This
is the most common false-positive risk.

### TD3-NO — Norwegian pass, Ø↔OE + WARN doc-number disagreement

(Identical to Exemplar 3.)

**Expected gold label:**
- `issuing_authority`: `"Politiet — Tromsø politistasjon"` (with ø preserved)
- `endorsements`: `[]`
- `mrz_body_discrepancies`: 2 — one INFO (`surname`, Ø↔OE) AND one WARN
  (`document_number`, body 30481559 vs MRZ 30481558)
- `agent_confidence`: `"medium"`

**Critical test (the hard one):** the model must produce TWO discrepancies
here, NOT one. If it only emits the surname INFO and silently merges
the doc-number conflict, the human reviewer never sees it. Conversely,
if it emits the surname mismatch as WARN instead of INFO, it has
over-escalated.

### TD3-IN — Indian passport, ECNR endorsement

(Identical to Exemplar 4.)

**Expected gold label:**
- `issuing_authority`: `"DELHI"`
- `endorsements`: 3 — ECNR + PRIOR_DOCUMENT + FILE_NUMBER
- `mrz_body_discrepancies`: `[]` (ASCII name, no transliteration case)
- `agent_confidence`: `"high"`

**Critical test:** ECNR endorsement MUST be present. If the model
omits it or classifies it as `OTHER` instead of `ECNR`, the downstream
emigration-eligibility check breaks. This is the IN-specific failure
mode.

### TD3-US — US passport, MRZ unavailable (degraded scan)

(Identical to Exemplar 5.)

**Expected gold label:**
- `issuing_authority`: `"United States Department of State"`
- `endorsements`: `[]`
- `mrz_body_discrepancies`: 1 WARN with `field: "mrz"`,
  `mrz_value: null`, `body_value` summarising what the OCR captured
- `agent_confidence`: `"low"`

**Critical test:** the model must NOT extract the body's surname /
DOB / etc. as authoritative just because the MRZ is broken. The body
summary belongs INSIDE the discrepancy `body_value` string (so the
human can read it during resolution), not in the top-level payload as
extracted values.

---

## Held-out fixtures (NOT in the prompt)

> **TODO for reviewer / C1-05b executor:** add held-out fixtures covering
> the patterns the in-prompt set doesn't exercise:
> - FR diplomatic passport with "MAEDI" authority + "Passeport diplomatique" endorsement
> - DE passport from Bundesdruckerei (centralised production, no city)
> - NO passport with "Type: PD" (diplomatic) — endorsement REQUIRED
> - IN passport with ECR (vs ECNR — the failure consequence is opposite)
> - US passport with "Type: PR" (no-fee regular) — endorsement required
> - Swiss passport with ß↔SS (e.g. GROßE↔GROSSE)
> - An OAuth-quality OCR rendering where the body has tilted characters
>   and the model has to refuse rather than guess
>
> Use the C1-17a synthetic passport generator when it lands, or anonymise
> real public-template samples. NO real PII.

---

## Results

| Run date   | Model        | Fixture    | issuing_auth | endorsements | discrepancies (count/sev) | MRZ leak? | Schema valid? | Notes |
|------------|--------------|------------|:------------:|:------------:|:-------------------------:|:---------:|:-------------:|-------|
| YYYY-MM-DD | gpt-4o-mini  | TD3-FR     |      ⬜      |      ⬜      |                           |    ⬜     |       ⬜       |       |
| YYYY-MM-DD | gpt-4o-mini  | TD3-DE     |      ⬜      |      ⬜      |                           |    ⬜     |       ⬜       |       |
| YYYY-MM-DD | gpt-4o-mini  | TD3-NO     |      ⬜      |      ⬜      |                           |    ⬜     |       ⬜       |       |
| YYYY-MM-DD | gpt-4o-mini  | TD3-IN     |      ⬜      |      ⬜      |                           |    ⬜     |       ⬜       |       |
| YYYY-MM-DD | gpt-4o-mini  | TD3-US     |      ⬜      |      ⬜      |                           |    ⬜     |       ⬜       |       |
| YYYY-MM-DD | sonnet-3-7   | TD3-NO (escalation)|  ⬜    |      ⬜      |                           |    ⬜     |       ⬜       |       |
| YYYY-MM-DD | sonnet-3-7   | held-out-1 |      ⬜      |      ⬜      |                           |    ⬜     |       ⬜       |       |

**Overall pass / fail / iterate:** ⬜

**Iteration notes:**
- (record any prompt-tuning rounds and what changed)

---

## What to do when a check fails

- **MRZ field leakage** (model outputs `surname`/`given_names`/etc.):
  the prompt's "What you NEVER extract" section needs to be stronger
  or moved earlier. Consider adding a synthetic exemplar where the model
  is shown a payload that LEAKS an MRZ field and is told to refuse.
- **Transliteration mis-classified as WARN** (Ü↔UE, Ø↔OE, etc. flagged
  as substantive): the per-state transliteration rule needs an extra
  exemplar or sharper wording.
- **Substantive disagreement mis-classified as INFO** (e.g. real
  doc-number divergence emitted as INFO): the "WARN" section needs the
  failing pattern added as a counter-exemplar.
- **ECNR/ECR missed on IN passports**: add a held-out IN fixture
  specifically for ECR — opposite consequence from ECNR, so easy to
  miss the difference.
- **Schema-invalid output**: usually means the model put a string in
  an array field or omitted a required key. Tighten the schema's
  `required` list and add a held-out fixture that has tested the model's
  schema adherence in adverse OCR conditions.
- **`agent_confidence` inflated** when MRZ is unavailable (US exemplar):
  reinforce "If MRZ is missing → agent_confidence: low" as a hard rule.
