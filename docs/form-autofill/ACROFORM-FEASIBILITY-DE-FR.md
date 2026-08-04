# AcroForm prefill for DE/FR — feasibility check

**Date:** 2026-08-04 · **Task:** AIQ-1769 (subtask 1 of AIQ-1759)

## Summary

`FINDINGS.md` Appendix A.1 concluded: *"restrict any AcroForm-PDF prefill to corridors that
genuinely use fillable paper forms (DE/FR)."* The parenthetical `(DE/FR)` was never verified.
Field-testing every published candidate gives a **split** answer:

| corridor | verdict | file |
|---|---|---|
| **FR** | ✅ **viable** | `ls_14571-05_fr_09` on France-Visas — a genuine **172-field** AcroForm |
| **DE** | ❌ **not viable** | no blank PDF is published at all; VIDEX is an online app |

So A.1 is half right. FR can use AcroForm prefill. DE cannot, and belongs with NO on the
prefilled data-sheet model.

## France — one fillable file exists, and it is not the obvious one

Four candidates were field-tested with the task's own Test Command (`pypdf.get_fields()`):

| file | source | bytes | fields | verdict |
|---|---|---|---|---|
| `cerfa_14571.do` (**`*06`**) | service-public | 429,654 | **0** | flattened — *Print To PDF* from `LS_FR_v1.8.odt` |
| `cerfa_14571-05-long-sejour` | France-Visas | 248,160 | **0** | flattened |
| `cerfa_14571-05_long_sejour_en` | France-Visas | 34,164 | **0** | flattened |
| `cerfa_14571-05_long_sejour_es` | France-Visas | 65,147 | **0** | flattened |
| **`ls_14571-05_fr_09`** | France-Visas | 151,743 | **172** | ✅ genuine AcroForm |

`ls_14571-05_fr_09` metadata: `/Creator Writer`, `/Producer LibreOffice 7.1`,
created 2021-08-06, **modified 2024-03-26**. 3 pages. 134 text fields (`/Tx`) +
38 buttons (`/Btn`).

Field-name prefixes: `companion` (36), `applicant` (32), `resident` (17), `parental` (12),
`travel` (11), `purpose` (11), `previous` (11), `host` (9), `other` (9), `study` (7).

Full dump committed at `docs/form-autofill/fields_FR_cerfa_14571-05.txt` — this is the input
artifact AIQ-1759 subtask 2 needs.

### ⚠️ Provenance tension for Romain to resolve

The **fillable** file is edition **`*05`** (modified 2024-03-26). The edition currently published
on service-public is **`*06`** (created 2025-12-11) and is **flattened**. So prefilling means
filling a form one edition behind the current published one. That trade-off is a provenance
judgement, not an engineering one — per this task's human gate.

Note also that the task's "`*09`" was never a CERFA edition: it is the `_09` suffix in the
France-Visas **filename** `ls_14571-05_fr_09`, which is the `*05` form.

## Germany — no blank PDF exists

`videx.diplo.de/videx/visum-erfassung/de/videx-langfristiger-aufenthalt` is **VIDEX**, an
interactive web application (the page is a JS shell). VIDEX **generates** a completed PDF from
online entry — there is no blank fillable form to prefill. `digital.diplo.de/Blaue-Karte` is
likewise an online path.

The PDF is an **output** of the German process, not an input to it — structurally the same
mistake Appendix A.1 itself caught for Norway, where the EEA registration certificate turned out
to be "an output the police issue, not an input form".

## The seed script's core assumption is false

`backend/scripts/seed_immigration_form_templates.py` says the stand-ins are safe because
*"the AcroForm field NAMES match form_field_mappings.form_field_id, so swapping in the real
templates requires no code change."*

**There is zero overlap.** The real form uses English camelCase; the mappings use French
snake_case:

| real PDF (172) | DB mapping (12) |
|---|---|
| `applicantSurname` | `nom` |
| `applicantFirstname` | `prenoms` |
| `applicantDateOfBirth` | `date_naissance` |
| `applicantPlaceOfBirth` | `lieu_naissance` |
| `applicantNationality` | `nationalite` |
| `applicantOccupation` | `profession` |

Swapping in the real template therefore **does** require work. Worse, it is not a rename: the DB
models `sexe` and `situation_familiale` as single text fields, but the real form uses **checkbox
buttons** — `applicantGenderM` / `applicantGenderF`, and `applicantMaritalCEL` / `MAR` / `SEP` /
`DIV` / `VEU` / `AUT`. Subtask 2 needs a value→checkbox mapping layer, not a lookup table.

## Also corrected

`form_templates.original_pdf_url` is the **wrong target**. The prefill pipeline never reads
`form_templates`; it reads `form_field_mappings` keyed by `form_id` (`DE_blue_card_v2024`
15 fields, `FR_cerfa_14571_v2024` 12, `NO_datasheet_v2026` 9) plus bucket objects of the same
name. DE and FR both have `form_url` NULL, and there is **no FR row in `form_templates` at all**
(only `APOSTILLE-FR`) — which is why the task's verification query left `<fr code>` unfilled.
Prod also drifted from the task snapshot: 84 templates / 36 mappings, not 83 / 27.

## What remains

1. **Romain:** confirm the `*05` fillable file is acceptable given the `*06` is the current
   published edition (the provenance tension above).
2. Upload `ls_14571-05_fr_09.pdf` to the `form-templates` bucket as `FR_cerfa_14571_v2024.pdf`,
   set `form_field_mappings.form_url` + provenance.
3. Re-map the 12 FR mappings onto the real field names, including the checkbox layer (subtask 2).
4. Drop DE from the AcroForm branch; move it to the data-sheet model.
