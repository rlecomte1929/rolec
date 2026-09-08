# CL facts — third-country professional relocated to Chile (Santiago)

Batch: `cl-facts-2026-08-31` · corridor `CL` · perspective nationality `non-EEA`, status `professional`.
11 facts in `facts.ndjson`. Every `evidence_quote` was confirmed as a **verbatim substring** of the
fetched official government text (raw HTML rendered faithfully, or PDF text extraction). All quotes < 200 chars.
No blogs / relocation-firm / news sources used. Nothing invented — no fabricated numbers, fees, or citations.

## Pillar / type spread
- Pillars: RESIDENCE 3, EMPLOYMENT 4, TIMELINE 2, IDENTITY 2 (all within the allowed 7).
- fact_type: eligibility 4, obligation 3, deadline 2, process 1, document 1.

## Sources (all official Chilean government) — verbatim confirmed = YES for all

| fact_key | source_url | lang | verbatim? |
|---|---|---|---|
| CL:residence:work_permit_applied_from_abroad | https://serviciomigraciones.cl/en/residencia-temporal-permit/subcategories/remunerated-activities/ | EN | YES |
| CL:employment:subordinate_relationship_employer | https://serviciomigraciones.cl/en/residencia-temporal-permit/subcategories/remunerated-activities/ | EN | YES |
| CL:timeline:work_permit_90_45_contract | https://serviciomigraciones.cl/en/residencia-temporal-permit/subcategories/remunerated-activities/ | EN | YES |
| CL:employment:transitoria_no_remunerated_work | https://serviciomigraciones.cl/en/permanencia-transitoria-permit/work-authorization/ | EN | YES |
| CL:residence:temporal_valid_up_to_2_years | https://serviciomigraciones.cl/en/residencia-temporal-permit/ | EN | YES |
| CL:residence:definitiva_24_months | https://serviciomigraciones.cl/en/residencia-definitiva-permit/ | EN | YES |
| CL:identity:cedula_requires_residence_permit | https://www.chileatiende.gob.cl/fichas/3337-cedula-de-identidad-para-extranjeros-obtencion-y-renovacion | ES | YES |
| CL:identity:rut_requires_cedula | https://www.sii.cl/contribuyentes/contribuyentes_individuales/chilenos_extranjero/rol_unico_tributario.htm | ES | YES |
| CL:timeline:cedula_within_30_days | https://www.chileatiende.gob.cl/fichas/3337-cedula-de-identidad-para-extranjeros-obtencion-y-renovacion | ES | YES |
| CL:employment:tax_first_3_years_chilean_source | https://www.sii.cl/preguntas_frecuentes/declaracion_renta/001_140_1219.htm | ES | YES |
| CL:employment:tax_residency_183_days | https://www.sii.cl/normativa_legislacion/circulares/2021/circu63.pdf | ES | YES |

## Verification method
- SERMIG (serviciomigraciones.cl) + ChileAtiende + SII HTML pages: fetched raw HTML with a browser
  User-Agent (all HTTP 200), rendered to visible text (inline `<em>/<strong>/<a>` tags stripped without
  inserting spaces so wording matches the page exactly), then asserted each quote is a literal substring.
  The SII RUT page is latin-1 encoded and was decoded accordingly to preserve accents.
- 183-day tax-residency definition (Código Tributario Art. 8 N°8): taken verbatim from SII **Circular 63
  de 2021** PDF via text extraction (`pypdf`). This is the operative SII instruction restating the statute.

## Unverifiable / dropped
- **None dropped for lack of a quote.** No SOCIAL_SECURITY (AFP/isapre), HEALTHCARE, or HOUSING fact is
  included: no verbatim official-government quote was located within this batch's source set, and inventing
  one is out of scope. These pillars are gaps for a follow-up batch.
- SII FAQ URL `.../preguntas_frecuentes/renta/001_002_1219.htm` returned HTTP 404; not used. The 183-day
  rule is instead sourced from Circular 63/2021 (above).

## Non-obvious themes covered
1. Work-based Residencia Temporal must be applied for **from outside Chile** — cannot convert tourist → work inside the country.
2. Permit is **tied to a subordinate relationship with a Chile-domiciled employer** / formal job offer.
3. Job-offer route grants only **90 days**; the signed contract must be filed **within 45 days** of entry to extend to 1 year.
4. **Tourist (Permanencia Transitoria) holders cannot do paid work** (rare special authorisation aside).
5. Residencia Temporal capped at **up to 2 years**; Residencia Definitiva needs **≥ 24 months** of temporary residence.
6. **Cédula de Identidad para Extranjeros** issued only after a SERMIG residence permit; **RUT registration requires the cédula** — sequence: residence permit → cédula → RUT.
7. Cédula must be obtained **within 30 days** of the residence permit taking effect, or a fine applies.
8. **Tax**: first 3 years taxed only on Chilean-source income; **tax residency triggered by > 183 days** presence in any 12-month window, regardless of visa/intent.
