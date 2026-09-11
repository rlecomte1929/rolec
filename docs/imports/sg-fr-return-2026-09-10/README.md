# AD-P10 · SG->FR return / repatriation skeleton (FR->SG corridor, reverse leg)

**batch_id:** `sg-fr-return-2026-09-10`
**corridor:** SG-FR (Singapore -> Paris) · **reverse leg / repatriation**
**persona:** Adrien — French national repatriating from a Singapore Employment Pass back to France
**artifact:** `sg-fr-return-2026-09-10.ndjson` · **records:** 7 · **sha256:** `b5cd04a6cc219130934879d6a69c578c579f3511fe5e7575b7c7c7f7ad8b77ad`

## Status (all records)
- review_status: `pending`
- verification_status: `representative`
- status: `draft` (candidate-only)
- platform_vetting_status: `pending`
- quote_verbatim_confirmed: `false` (every record — awaiting human/lawyer verification)

## Scope — MIXED AUDIENCE
A repatriation skeleton of the highest-value facts, split across two jurisdictions:
- **Host-exit (Singapore)** — Adrien as a `non-EEA` EP holder. destination_country = `SG`.
- **Home-re-entry (France)** — Adrien as an `EEA` national. destination_country = `FR`.

`destination_country` is set to the ISO-2 country where each obligation applies. Nationality is set per audience (SG-exit `non-EEA`, FR-re-entry `EEA`) — never null. Tax facts map to the `EMPLOYMENT` pillar per loader convention.

## Coverage (fact_key -> side -> pillar -> flags)
| fact_key | side | pillar | non_obvious | lawyer |
|---|---|---|---|---|
| sg_fr_ret_ir21_tax_clearance | SG exit | EMPLOYMENT | yes | no |
| sg_fr_ret_ep_cancellation | SG exit | RESIDENCE | yes | no |
| sg_fr_ret_no_cpf | SG exit | SOCIAL_SECURITY | yes | no |
| sg_fr_ret_fr_tax_residence_notify | FR re-entry | EMPLOYMENT | no | no |
| sg_fr_ret_fr_pas_rate | FR re-entry | EMPLOYMENT | yes | no |
| sg_fr_ret_fr_declaration_split | FR re-entry | EMPLOYMENT | yes | no |
| sg_fr_ret_fr_health_puma | FR re-entry | HEALTHCARE | yes | no |

non_obvious_count = 6 · needs_lawyer_review_count = 0

## Sources (official only)
- **iras.gov.sg** — Tax clearance for non-Singapore Citizen employees (Form IR21)
- **mom.gov.sg** — Cancel an Employment Pass; Who is entitled to CPF contributions
- **service-public.gouv.fr** — F31443 (Impôt sur le revenu · retour d'expatriation); F32824 (assurance maladie au retour d'expatriation)
- **impots.gouv.fr** — Je reviens en France après un séjour à l'étranger (corroboration)

## Key judgement calls
- **EP cancellation cascades to the family:** the MOM quote makes explicit that cancelling the EP also cancels all related passes (the family's Dependant's Passes) — surfaced as the non-obvious flag.
- **No CPF to unwind:** sourced to the MOM CPF-eligibility page; combined with the known absence of a France-Singapore social security totalization agreement (noted, not over-claimed).
- **French PAS default rate** and the **return-year 2042-NR + 2042 split** are both taken verbatim from service-public F31443.
- **Health re-affiliation** sourced to service-public F32824 (ameli.fr not scrapable). The verbatim S1106/first-hour-worked procedure is published for EEE/EU/CH/UK returns; the note flags that Adrien returns from a non-EEA country and that the non-working PUMa 3-month-residence rule / 'autre pays' specifics should be confirmed.

## Source access issues (honest log)
- **IRAS JavaScript-rendered** — IR21 quote captured from an official iras.gov.sg search excerpt; re-confirm on the live page. `quote_verbatim_confirmed=false` on all records.
- **ameli.fr not scrapable** from this egress — health fact sourced to whitelisted service-public.gouv.fr instead.
- MOM and service-public pages scraped cleanly; their quotes are verbatim from the live pages.
- **No fee, rate, deadline or coverage position was invented.**

## Loader notes
- destination_country = `SG` for host-exit records, `FR` for home-re-entry records.
- nationality = `non-EEA` (SG-exit audience) or `EEA` (FR-re-entry audience), never null.
- Tax obligations mapped to the `EMPLOYMENT` pillar per loader convention.
