# pa-resource-2026-09-08 — re-source clearing a held fact

**Clears:** punch-list Tier-1 hold *"Panama — 5-year Panamanian-substitution duty (Labour Code
art. 18)"* (the full quoted phrasing was not an exact substring in the `cetippat.gob.pa` Labour
Code PDF; a 2-column layout + hyphenation broke the match).

**Landed:** PANAMA · EMPLOYMENT · 1 `requirement_item`, `review_status='pending'` (append-only).

## Fact
- key: `PA:employment:five_year_panamanian_substitution`
- title: Specialized foreign worker must be replaced by a Panamanian within 5 years
- pillar / nationality: EMPLOYMENT / non-EEA
- source: https://cetippat.gob.pa/wp-content/uploads/2021/06/codigo-detrabajo.pdf (Código de Trabajo)
- quote: "tendrán la obligación de sustituir al trabajador" (a clean contiguous verbatim fragment
  of art. 18, chosen to survive the PDF's 2-column interleaving + hyphenation)

## Verification
`confirm_quotes.py` → REVIEW_BROWSER (0.0 bigram — cetippat.gob.pa returned a blocked/stub
response; the server is intermittently unreachable). **Applier-verified via `pdfplumber`**:
extracted the Código de Trabajo PDF locally and confirmed the fragment is present verbatim, then
imported/promoted `--no-fetch`. Not a landing on a researcher's say-so — the applier read the
official PDF.

## Append-only
approved count unchanged (325), expert_verified 0, nationality scope guard green.
