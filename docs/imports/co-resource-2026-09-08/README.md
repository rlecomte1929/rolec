# co-resource-2026-09-08 — re-source clearing a held fact

**Clears:** punch-list Tier-1 hold *"Colombia — Cédula de Extranjería registration deadline"*
(the `migracioncolombia.gov.co` cédula page returned empty/redirect to both curl and browser).

**Landed:** COLOMBIA · IDENTITY · 1 `requirement_item`, `review_status='pending'` (append-only).

## Fact
- key: `CO:identity:cedula_deadline`
- title: Register the Cédula de Extranjería within the deadline
- pillar / nationality: IDENTITY / non-EEA
- source: https://www.cancilleria.gov.co/sites/default/files/Normograma/docs/decreto_1067_2015_pr005.htm
  (Decreto Único Reglamentario 1067/2015 del Sector Administrativo de Relaciones Exteriores)
- quote: "Tanto los titulares como los beneficiarios de visa, cuya vigencia sea superior a tres (3)
  meses, deberán inscribirse en el Registro de Extranjeros …"

## Verification
`confirm_quotes.py` → **CONFIRMED** (0.927 bigram overlap, utf-8). The governing decree on the
Cancillería normogram is reproducibly fetchable, unlike the Migración Colombia cédula page that
originally blocked this fact.

## Append-only
approved count unchanged (325), expert_verified 0, nationality scope guard green.
