# AD-P1 · France-departure requirement facts (FR->SG corridor)

**batch_id:** `fr-departure-2026-09-10`
**corridor:** FR-SG (Paris -> Singapore) · **origin side (France exit)**
**persona:** Adrien, French national, moving on a Singapore Employment Pass
**artifact:** `fr-departure-2026-09-10.ndjson` · **records:** 8 · **sha256:** `ccff444dcb6c828aa5565309195467336a3d2943bdf1eef2d9d3339e72210eb0`

## Status (all records)
- review_status: `pending`
- verification_status: `representative`
- status: `draft`
- platform_vetting_status: `pending`
- quote_verbatim_confirmed: `false` (every record — awaiting human/lawyer verification)

## Scope
Net-new **origin-side** facts for the FR->SG corridor (this corridor had no France-exit facts). Each record is a discrete obligation the departing French resident (or their employer) must handle, phrased in the mover's terms, with a verbatim official-source quote.

## Coverage (fact_key -> pillar)
| fact_key | pillar | type | non_obvious | lawyer |
|---|---|---|---|---|
| fr_sg_dep_tax_address_declaration | EMPLOYMENT | where_to_apply | no | no |
| fr_sg_dep_tax_sip_nr_transfer | EMPLOYMENT | where_to_apply | no | no |
| fr_sg_dep_tax_2042nr_form | EMPLOYMENT | document | yes | no |
| fr_sg_dep_health_expat_no_french_coverage | HEALTHCARE | eligibility | yes | no |
| fr_sg_dep_health_cfe_optional | HEALTHCARE | other | yes | no |
| fr_sg_dep_social_security_a1_scope | SOCIAL_SECURITY | eligibility | yes | **yes** |
| fr_sg_dep_unemployment_expat_affiliation_8days | SOCIAL_SECURITY | deadline | yes | no |
| fr_sg_dep_caf_family_benefits_stop | SOCIAL_SECURITY | eligibility | yes | no |

## Sources (official only)
- **impots.gouv.fr** — "Je pars vivre a l'etranger, quelles demarches dois-je accomplir ?"
- **service-public.gouv.fr F55** — "Salarie expatrie a l'etranger"
- **service-public.gouv.fr F3155** — "Salarie detache a l'etranger"
- **caf.fr** — "Je pars vivre a l'etranger"

## Key judgement calls
- **FR-SG totalization / A1:** There is **no** EU-style totalization for FR->SG and **no** bilateral social security convention between France and Singapore (corroborated by French Senate written question n.00126, réponse publiée 29/09/2022). The A1 scope fact is sourced to the whitelisted service-public F3155 page and flagged `needs_lawyer_review: true`. **No coverage position was invented.**
- **ameli.fr was not scrapable** from this egress (HTTP 403 / empty body). The loss-of-French-coverage fact was sourced from the whitelisted service-public.gouv.fr F55 page instead of ameli.fr.

## Loader notes
- destination_country = `FR` for every record (origin-side obligations governed by French law).
- nationality = `EEA` (a departing French resident's own obligations), never null.
- Tax obligations mapped to the `EMPLOYMENT` pillar per loader convention.
