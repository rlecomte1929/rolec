# AcroForm prefill for DE/FR — feasibility check

**Date:** 2026-08-04 · **Task:** AIQ-1769 (subtask 1 of AIQ-1759) · **Outcome:** premise refuted, no code shipped

## Summary

`FINDINGS.md` Appendix A.1 concludes: *"restrict any AcroForm-PDF prefill to corridors that
genuinely use fillable paper forms (DE/FR)."* The parenthetical `(DE/FR)` was an **assumption**
— nobody had checked whether the DE and FR forms are actually fillable AcroForms.

They are not. **Neither corridor publishes a blank fillable AcroForm.** The AcroForm-prefill
branch of AIQ-1759 rests on a premise that does not hold.

## Evidence

### France — CERFA 14571*06: authentic, but flattened

Source supplied by Romain, the official government forms portal:
`https://www.formulaires.service-public.gouv.fr/gf/cerfa_14571.do`

Verified it is genuinely the long-stay visa application — page 1 carries the photo box,
"Je sollicite un visa pour le motif suivant", "DÉCISION DU POSTE", and the numbered items
17–23. The version marker in the document text is **`N°14571*06`**.

Ran the task's own Test Command:

```
pages: 3   size: 429,654 bytes
ACROFORM FIELD COUNT: 0
/Producer:     Microsoft: Print To PDF
/Title:        LS_FR_v1.8.odt
/CreationDate: D:20251211174832+01'00'
```

Zero form fields. The metadata explains why: it was **printed to PDF from an ODT**, which
flattens any interactive fields. Per the task's own Technical Constraints — *"a flattened or
scanned form cannot be prefilled and silently produces an empty fill report... Verify by
enumerating fields before accepting"* — this file must be **rejected**.

France-Visas corroborates: its forms are described as print-and-complete, and the applicant is
told to "print and come with your CERFA in final paper version".

### Germany — no blank PDF exists at all

Source supplied by Romain: `https://videx.diplo.de/videx/visum-erfassung/de/videx-langfristiger-aufenthalt`

This is **VIDEX**, an interactive web application (the page is a JS shell — "Daten werden
laden ..."), not a form download. VIDEX is the Federal Foreign Office's online capture tool: the
applicant enters data online and VIDEX **generates** a completed PDF at the end. There is no
blank fillable AcroForm to prefill. `digital.diplo.de/Blaue-Karte` is likewise an online
application path.

The PDF is an **output** of the German process, not an input to it — structurally the same
mistake Appendix A.1 itself identified for Norway, where the EEA registration certificate turned
out to be "an output the police issue, not an input form".

## Consequence

- Validation criterion 1 of AIQ-1769 ("Both templates resolve to a downloadable PDF whose
  AcroForm field names can be enumerated") is **unsatisfiable** with the official sources.
- The synthetic stand-ins in `backend/scripts/seed_immigration_form_templates.py` cannot be
  replaced by real fillable equivalents, because none are published.
- AIQ-1759 subtasks 2 and 5 (field mappings, golden cases) are blocked on an artifact that does
  not exist — not on effort.

By Appendix A.1's own logic, DE and FR belong in the same bucket as NO: the correct production
model is the **prefilled data-sheet** (the `NO_datasheet_v2026` pattern already shipped), not
AcroForm PDF prefill.

## Two further corrections to the task record

1. **The FR version is `*06`, not `*09`.** The `*09` in the task most likely came from the
   France-Visas filename `ls_14571-05_fr_09`, where `09` is a filename suffix on a `*05` form,
   not a CERFA edition.
2. **`form_templates.original_pdf_url` is the wrong target.** The prefill pipeline never reads
   `form_templates`; it reads `form_field_mappings` keyed by `form_id`
   (`DE_blue_card_v2024` 15 fields, `FR_cerfa_14571_v2024` 12 fields, `NO_datasheet_v2026`
   9 fields), and storage objects of the same name in the `form-templates` bucket. Both DE and FR
   have `form_url` NULL. There is also **no FR row in `form_templates` at all** — only
   `APOSTILLE-FR` — which is why the task's verification query left `<fr code>` unfilled.

## Not verified

France-Visas hosts other variants (`cerfa_14571-05` in FR/EN/ES). These were **not** downloaded
or field-tested — only the service-public `*06` was. If one of them is a genuine AcroForm the
FR half becomes viable, so that is worth one check before the branch is abandoned. Deciding
which file is the authentic current edition remains Romain's call, per AIQ-1769.
