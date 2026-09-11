# AcroForm prefill for DE/FR — feasibility check

**Date:** 2026-08-04 · **Task:** AIQ-1769 (subtask 1 of AIQ-1759) · **Outcome:** premise refuted, no code shipped

> ## ⚠️ 2026-08-10 — THE FRANCE HALF OF THIS DOCUMENT IS WRONG
>
> The "Not verified" section below flagged that the France-Visas `cerfa_14571-05` FR/EN/ES variants
> were never downloaded, and said: *"If one of them is a genuine AcroForm the FR half becomes
> viable, so that is worth one check before the branch is abandoned."*
>
> **That check has now been run, and one of them is.**
> **`ls_14571-05_fr_09` is a genuine AcroForm with 172 named fields.** France is viable.
>
> The 2026-08-04 conclusion was reached on the **service-public `*06`**, a genuinely flattened
> file — not on the France-Visas `*05`, which is a different document from a different portal.
> Read **§ Correction (2026-08-10)** at the end before acting on anything above. Germany is
> unaffected and remains unsalvageable.

## Summary

`FINDINGS.md` Appendix A.1 concludes: *"restrict any AcroForm-PDF prefill to corridors that
genuinely use fillable paper forms (DE/FR)."* The parenthetical `(DE/FR)` was an **assumption**
— nobody had checked whether the DE and FR forms are actually fillable AcroForms.

~~They are not. **Neither corridor publishes a blank fillable AcroForm.**~~ **Germany does not.
France does** — see the correction above. The AcroForm-prefill branch of AIQ-1759 holds for FR.

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

---

# Correction (2026-08-10) — France IS viable

The one outstanding check above was run. **It reverses the France conclusion.**

## Results — all three France-Visas variants plus the service-public file

| file | portal | PDF | pages | `/AcroForm` | named fields | verdict |
|---|---|---|---|---|---|---|
| `ls_14571-05_fr_09` | France-Visas | 1.6 | 3 | **yes** | **172** (131 `/Tx`, 38 `/Btn`, 3 unresolved) | **FILLABLE** |
| `cerfa_14571-05_long_sejour_en` | France-Visas | 1.4 | 3 | no | 0 | flattened |
| `cerfa_14571-05_long_sejour_es` | France-Visas | 1.4 | 4 | no | 0 | flattened |
| `cerfa_14571.do` (`*06`) | service-public | 1.7 | 3 | no | 0 | flattened |

The `*06` result independently reproduces the 2026-08-04 finding (`pypdf.get_fields()` → 0, no
XFA). **The original check was not wrong about the file it examined — it examined the wrong file.**
The FR-language France-Visas `*05` is a different document from a different portal, and it is the
fillable one.

Extracted field list committed at
`docs/form-autofill/artifacts/fr_cerfa_14571-05_acroform_fields.json` (name, `/FT`, `/MaxLen`).

## Method, and why it took three attempts

France-Visas answers **HTTP 403 to `curl`** regardless of user-agent, `Referer`, `Sec-Fetch-*`
headers, or a full cookie jar lifted from a live browser session — it fingerprints beyond cookies.
The file had to be fetched from **inside a real browser session**.

Two earlier passes reported "NO FILLABLE FIELDS" and **both were false negatives.** Worth recording,
because the same two traps will catch the next person:

1. **A raw byte scan cannot see into object streams.** The FR catalogue is
   `<</AcroForm 263 0 R …>>` — an *indirect* reference. Object 263 lives inside one of 8
   `/ObjStm` compressed streams, so `/FT` and `/Widget` counts over the raw bytes were 0 while the
   fields existed all along. PDF 1.4 files (the EN/ES variants) have no object streams, which is
   why the negative result *is* trustworthy for those two.
2. **`'endstream'` contains `'stream'`.** Scanning for the `stream` keyword with a naive
   `indexOf`/regex matches inside `endstream` too, which shifts every subsequent offset and made all
   281 candidate slices fail to inflate — reported as `inflated: 0`, which looked like "not
   compressed" rather than "my scan is broken". Skipping matches preceded by `end` inflated 70 of
   141 streams and the fields appeared immediately.

Anyone re-checking a government PDF for fillability: resolve indirect references, or use a real
parser. A zero from a byte grep means nothing.

## Consequences

1. **The FR AcroForm path is not retired.** `form_prefill_service.fill_acroform()` has a genuine
   target for the first time.
2. **`FR_cerfa_14571_v2024`'s 12 seeded field ids are entirely fictional.** Zero of them
   (`nom`, `prenoms`, `date_naissance`, `lieu_naissance`, `nationalite`, `sexe`,
   `numero_passeport`, `date_delivrance`, `date_expiration`, `situation_familiale`, `profession`,
   `employeur`) appear in the real form, which uses semantic English names — `applicantSurname`,
   `applicantFirstname`, `applicantDateOfBirth`, `travelDocNumber`, `travelDocValidUntil`,
   `applicantEmail`, `applicantOccupation`, `purposeTRAV`/`ETUD`/`STAG`/…
   `backend/tests/test_imm11_form_prefill.py:170` already recorded this exact mismatch —
   *"The real CERFA calls it `applicantSurname`; our mapping says `nom`. Zero overlap."* — so the
   fact was known and never acted on. Re-seeding the mapping against the real names is now
   unblocked; that is its own task.
3. **This does NOT apply to the DE→FR corridor.** CERFA 14571 is a **long-stay visa application**,
   and a German citizen exercising free movement needs no long-stay visa. The form serves
   **third-country nationals** applying to enter France. So the AcroForm path and the data-sheet
   path are not competing models of the same thing — they serve different populations, and both
   are correct:
   - **non-EEA → FR** → prefill the real CERFA AcroForm.
   - **EEA → FR** (incl. DE→FR) → the data sheet; there is no visa form to fill.
4. **Germany is unchanged.** VIDEX generates a completed PDF as *output*; there is no blank input
   form. `DE_blue_card_v2024` remains a synthetic stand-in with no authentic equivalent.
5. **The `*05` vs `*06` edition question is still open and still Romain's call.** service-public
   publishes `*06` (flattened); France-Visas publishes `*05` (fillable). Prefilling `*05` means
   prefilling an edition the other government portal has superseded. That is a content-accuracy
   decision, not a technical one — do not resolve it by picking whichever file happens to be
   fillable.

---

# Follow-up (2026-09-11) — mapping re-seeded against the real field names

Consequence 2 above ("Re-seeding the mapping against the real names is now unblocked; that is its
own task") is **done**. `supabase/migrations/20261135000000_fr_cerfa_14571_real_acroform_fields.sql`
replaces the 12 fictional French ids with the real France-Visas `*05` AcroForm field names
(`applicantSurname`, `travelDocNumber`, …), mapped to the vault columns the Build B fact dictionary
governs. Only the **9 plain-text (`/Tx`) fields** that map to a governed vault path are seeded; the
gender and marital-status **radio-button (`/Btn`) groups** need a value→export-value layer the fill
pipeline does not yet have and are a deliberate follow-up. `backend/tests/test_fr_cerfa_real_acroform.py`
locks every seeded `form_field_id` to the committed artifact and proves a fill lands all nine.

Still open (needs the browser, France-Visas 403s non-browser fetchers): upload the real `*05` PDF to
the `form-templates` bucket as `FR_cerfa_14571_v2024.pdf`. The edition caveat (5) is unchanged and
still Romain's call.
