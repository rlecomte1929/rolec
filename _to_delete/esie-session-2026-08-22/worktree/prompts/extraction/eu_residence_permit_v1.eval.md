# Eval — `eu_residence_permit_v1.txt`

**Cohort:** C1-05P-f · **Coverage:** DE / FR / NO / ES residence permits
(Regulation (EC) 1030/2002 uniform format)
**Model under test:** `gpt-4o-mini` (default) and `claude-3-7-sonnet` (escalation)

This eval validates the EU residence permit prompt across four issuing
states. Three things matter most: (a) NOT re-extracting MRZ fields,
(b) correctly mapping the on-card residence-purpose text to the
controlled vocabulary code, and (c) ALWAYS emitting the expired-permit
finding when `mrz_parse.expiry_date < current_date`.

---

## Acceptance bar (from Notion AIQ-527 validation criteria)

| Metric                                                              | Bar       |
|---------------------------------------------------------------------|-----------|
| Field-level extraction accuracy                                     | ≥ 90 %    |
| `residence_purpose_code` mapping correctness                        | ≥ 95 %    |
| MRZ-field-leakage rate                                              | 0 %       |
| Expired-permit finding emission (when applicable)                   | 100 %     |
| Schema validation                                                   | 100 %     |

The expired-permit finding at 100 % is non-negotiable: missing it
silently allows expired residents to pass the C1-08 eligibility check,
which is exactly the cascade Cohort 1 is designed to prevent.

`residence_purpose_code` at 95 % allows a small tolerance for ambiguous
on-card phrasings that legitimately map to OTHER — but never below.

---

## Methodology

Same as the passport eval: system prompt = `eu_residence_permit_v1.txt`,
user message = fixture body text + MRZ_PARSE + CURRENT_DATE, tool
`extract_eu_residence_permit_non_mrz` enabled, diff actual against
expected.

Special note on `current_date`: the runtime injects this so the prompt
can detect expiry without baking in a "today" assumption. When running
the eval, use the exact `CURRENT_DATE` value listed in each fixture so
the expected expiry findings match.

---

## Fixtures

### TD1-DE — Aufenthaltstitel, Blaue Karte EU, valid

(Identical to Exemplar 1.) **CURRENT_DATE:** 2027-05-28

**Expected gold label:**
- `residence_purpose_code`: `"BLUE_CARD"`
- `residence_purpose_text_verbatim`: `"Blaue Karte EU"`
- `validity_start`: `"2027-04-15"`
- `issuing_authority`: `"Landeshauptstadt München, KVR"` (Ü preserved)
- `mrz_body_discrepancies`: `[]`
- `findings`: `[]` (valid until 2031-04-14 — no expiry finding)
- `agent_confidence`: `"high"`

**Critical test:** the model must NOT emit `surname: "PATEL"`,
`document_number: "T01548299"`, or `expiry_date: "2031-04-14"` anywhere
— those come from the MRZ parser.

### TD1-FR — Titre de séjour, Vie privée et familiale, expires in 54 days

(Identical to Exemplar 2.) **CURRENT_DATE:** 2027-05-28

**Expected gold label:**
- `residence_purpose_code`: `"FAMILY_MEMBER"`
- `residence_purpose_text_verbatim`: `"Vie privée et familiale"`
- `validity_start`: `"2024-07-22"`
- `issuing_authority`: `"Préfecture de la Loire-Atlantique"`
- `findings`: 1 × `PERMIT_EXPIRES_SOON` (INFO) — 54 days remaining

**Critical test:** the model must emit PERMIT_EXPIRES_SOON when expiry
is within 90 days. Missing this loses the renewal-required signal.

### TD1-NO — Oppholdstillatelse, Forsker, Ö↔OE transliteration

(Identical to Exemplar 3.) **CURRENT_DATE:** 2027-05-28

**Expected gold label:**
- `residence_purpose_code`: `"RESEARCHER"`
- `residence_purpose_text_verbatim`: `"Oppholdstillatelse for forskning (Forsker)"`
- `validity_start`: `"2027-02-03"`
- `issuing_authority`: `"Utlendingsdirektoratet (UDI)"`
- `mrz_body_discrepancies`: 1 INFO (`surname`, Ö↔UE — German national in Norway)
- `findings`: `[]`

**Critical test:** SCHRÖDER↔Schroeder must be classified as INFO
(legitimate Umlaut). The transliteration rule applies based on
*holder nationality* not *issuing state*: a German national resident
in Norway still has Umlauts in their name that the MRZ encoding will
have stripped.

### TD1-ES — TIE, Reagrupación familiar, EXPIRED 78 days ago

(Identical to Exemplar 4.) **CURRENT_DATE:** 2027-05-28

**Expected gold label:**
- `residence_purpose_code`: `"FAMILY_MEMBER"`
- `residence_purpose_text_verbatim`: `"Reagrupación familiar — Familiar de español"`
- `validity_start`: `"2024-03-12"`
- `issuing_authority`: `"Comisaría General de Extranjería y Fronteras — Madrid"`
- `findings`: 1 × `PERMIT_EXPIRED` (WARN) — 78 days past expiry

**Critical test (most important in the suite):** the PERMIT_EXPIRED
WARN finding MUST be emitted. If missing, the model silently passed
an expired permit as valid — a Cohort 1 false-negative.

---

## Held-out fixtures (NOT in the prompt)

> **TODO for reviewer / C1-05f executor:** add held-out fixtures
> covering:
> - DE Aufenthaltstitel with "Forscher" → maps to RESEARCHER (different
>   from the in-prompt FR "Chercheur" exemplar)
> - FR titre de séjour with "Passeport Talent — Salarié en mission ICT"
>   → maps to ICT
> - ES TIE with "Residente de larga duración — UE" → maps to
>   EU_LONG_TERM_RESIDENT
> - DE Aufenthaltstitel with "§25 Abs. 2 AufenthG (Anerkennung als
>   Flüchtling)" → maps to PROTECTION_REFUGEE
> - A card with on-card text that does NOT match any controlled-vocab
>   code → must map to OTHER + PURPOSE_CODE_FALLBACK_OTHER finding
> - DE Aufenthaltstitel that is EXPIRED (mirrors the ES exemplar's
>   PERMIT_EXPIRED finding pattern but in a different language context
>   so the model can't pattern-match)
> - A card where the visual side date format is ambiguous (e.g. "03/04/2027"
>   — could be 3 April US-style or 3 April EU-style, both work, but
>   when the format is genuinely ambiguous use
>   VISUAL_DATE_FORMAT_AMBIGUOUS)
>
> Source from public templates (EU Commission's specimen card library)
> or anonymise real samples. NO real PII.

---

## Results

| Run date   | Model        | Fixture | Field acc. | Purpose code | MRZ leak? | Expiry finding correct | Schema valid | Notes |
|------------|--------------|---------|-----------:|:------------:|:---------:|:----------------------:|:------------:|-------|
| YYYY-MM-DD | gpt-4o-mini  | TD1-DE  |        % |      ⬜      |    ⬜     |          ⬜            |      ⬜      |       |
| YYYY-MM-DD | gpt-4o-mini  | TD1-FR  |        % |      ⬜      |    ⬜     |          ⬜            |      ⬜      |       |
| YYYY-MM-DD | gpt-4o-mini  | TD1-NO  |        % |      ⬜      |    ⬜     |          ⬜            |      ⬜      |       |
| YYYY-MM-DD | gpt-4o-mini  | TD1-ES  |        % |      ⬜      |    ⬜     |          ⬜            |      ⬜      |       |
| YYYY-MM-DD | gpt-4o-mini  | held-out-1 |     % |      ⬜      |    ⬜     |          ⬜            |      ⬜      |       |

**Overall pass / fail / iterate:** ⬜

**Iteration notes:**
- (record any prompt-tuning rounds and what changed)

---

## What to do when a check fails

- **MRZ field leakage**: same remediation as the passport eval —
  reinforce the "What you NEVER extract" section.
- **Wrong `residence_purpose_code`**: extend the mapping table with
  the specific on-card phrasing that was missed. Each row in the
  table acts as a few-shot signal; add the failing example as a row.
- **Missing expired-permit finding**: this is the most serious failure.
  Make the rule a top-level IMPORTANT block (already is — bump it
  further if needed). Consider a synthetic counter-exemplar where the
  model refuses to skip the finding even though all other fields
  parse cleanly.
- **Wrong validity_start**: usually a date-format misinterpretation
  (DD.MM.YYYY vs MM/DD/YYYY). Add a held-out fixture with an ambiguous
  date format that requires the model to use VISUAL_DATE_FORMAT_AMBIGUOUS.
- **`residence_purpose_text_verbatim` doesn't match card**: the model
  paraphrased instead of copying. Reinforce "verbatim — preserve
  capitalisation and diacritics".
- **Transliteration over-escalated to WARN**: same remediation as the
  passport eval — strengthen the §6 transliteration rule section.
- **`agent_confidence` too high on expired permits**: confidence
  reflects *extraction quality*, not *eligibility outcome*. A cleanly
  extracted expired permit should still be `agent_confidence: "high"`
  with the PERMIT_EXPIRED finding doing the alarm-raising. Reinforce
  this if conflated.
