# AD-P4 · Singapore GP / family medical clinics (FR->SG corridor)

**batch_id:** `fr-sg-singapore-medical-2026-09-10`
**corridor:** `XX-SG` (primary care — not corridor-specific)
**service_category:** `medical`
**persona:** Adrien — relocating to Singapore on an Employment Pass, needs a GP / family clinic on arrival

## Deliverables
| file | rows | sha256 |
|---|---|---|
| `fr-sg-singapore-medical-2026-09-10.providers.csv` | 6 | `fe41c432181bd74828cfea7af0d439dba330dc7051497a42136cf43343c8a7c1` |
| `fr-sg-singapore-medical-2026-09-10.rejects.csv` | 3 | `78d0753fd79843730b68d9de897ca8cca6b3564130ae9f2ba4390c28e952fecc` |

All rows are candidate-only: review_status=`pending`, verification_status=`representative`, status=`draft`, platform_vetting_status=`pending`.

## Official register used (provenance)
**Ministry of Health (MOH) — CHAS Clinics register**, the list of clinics participating in the Community Health Assist Scheme, published as open data on **data.gov.sg** (dataset `d_548c33ea2d99e29ec63a7cc9edcccedc`, "CHAS Clinics" — 1,193 records, of which 1,053 carry `LICENCE_TYPE=MC` (Medical Clinic)).

Each accepted clinic was matched on **HCI_CODE** (the MOH Healthcare Institution licence code) with `LICENCE_TYPE=MC`. Appearing on the MOH register with a valid MC licence IS the accreditation.

| company_name | HCI_CODE (accreditation_number) |
|---|---|
| Asia HealthPartners (304 Orchard Road, Lucky Plaza #05-06) | 9404842 |
| ACMS Medical Clinic (1 Grange Road, Orchard Building #06-06) | 16M0198 |
| Duxton Medical Clinic (7 Tanjong Pagar Plaza #01-106) | 16M0035 |
| Cross Street Medical Clinic (531 Upper Cross Street, Hong Lim Complex #01-35) | 18M0076 |
| Chua & Partners Family Clinic (18 Jalan Membina #02-05) | 9403452 |
| B T Goh Family Clinic & Surgery (194 Kim Keat Ave #01-406) | 9400089 |

## 9-column CSV schema (exact order)
`corridor, service_category, company_name, website_url, source_name, source_url, accreditation_body, accreditation_number, accreditation_expiry`

- `accreditation_body` = **MOH** for every accepted clinic.
- `accreditation_number` = the clinic's **HCI_CODE** from the MOH register.
- `accreditation_expiry` is **left blank** — the CHAS open dataset does not publish licence expiry dates. **None was invented.**
- `website_url` is **left blank** — the dataset does not publish clinic websites and none were invented. (The register carries an official general telephone `HCI_TEL`, but it was intentionally NOT carried into this file to avoid propagating unverified contact data.)
- The clinic's location is embedded in `company_name` for disambiguation.

## New-patient / expat-friendly flags (honesty note)
Singapore private GP clinics operate on a **walk-in basis and accept new patients by default** — there is no NHS-style panel-registration or "accepting new patients" flag in any official register, so acceptance is **NOT asserted per-clinic** (it is the sector norm). "Expat-friendly" is likewise **not an official register attribute** and was **NOT asserted per-clinic** to avoid fabrication. Asia HealthPartners and ACMS (both on Orchard Road) are commonly used by international residents, but that is context, not an official accreditation.

## GDPR note
No personal data captured. Clinics are business entities; **no named individual doctors, personal emails or personal phone numbers** are included. Only the official register's business-level identifiers are used.

## Rejects (tier-3, own-site only)
Osler Health International, International Medical Clinic (IMC) and Raffles Medical (Orchard) were **not located on the MOH CHAS open-data register** under those names — only the providers' own websites were found, which is tier-3 provenance and auto-rejected pending an official-register match. They may be licensed HCIs verifiable on the **HealthHub directory** (the full list of licensed healthcare service providers), which is JS-gated and could not be scraped; re-check there before accepting.

## Source access issues (honest log)
- The **data.gov.sg datastore_search JSON endpoint** returned no text via the platform scraper.
- The dataset was retrieved via a **direct HTTPS download of the official data.gov.sg signed S3 blob** (poll-download API -> signed S3 URL; GeoJSON with HTML-encoded attribute tables) and parsed locally.
- The MOH aggregate "Health Facilities (Primary Care...)" dataset (`d_e4663ad3f088a46dabd3972dc166402d`) was inspected first but contains only **yearly counts**, not named clinics, so the named CHAS register was used instead.
- The **HealthHub Directory** (full list of licensed healthcare service providers) is **JS-gated** and could not be scraped; expat clinics absent from CHAS are recorded in `rejects.csv` for re-check there.
- **No clinic was accepted without an exact match on the official MOH CHAS register.** Firms' own sites are recorded only in rejects, never as the source of accreditation.
