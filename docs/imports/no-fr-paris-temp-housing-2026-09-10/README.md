# D-P3 - Paris serviced-apartment / extended-stay providers (`no-fr-paris-temp-housing-2026-09-10`)

**Package type:** vendor CSV
**Corridor:** NO -> FR | **Use case:** 1-3 month corporate relocation temp housing in Paris
**Persona:** Denis - Norwegian national, Oslo -> Paris

## Files
- `no-fr-paris-temp-housing-2026-09-10-providers.csv` - 4 accepted, SIRENE-verified providers
- `no-fr-paris-temp-housing-2026-09-10-rejects.csv` - 2 rejected (SIREN not verifiable this run)

## Status flags (per hard constraints)
- `platform_vetting_status`: `pending` (all rows)
- No DB writes, no webhook calls - files only.

## Columns
`provider_name`, `siren`, `address_paris`, `arrondissement`, `website`, `min_stay_nights`, `corporate_booking`, `sirene_verified`, `platform_vetting_status`, `rejection_reason`.

## Accepted providers (SIREN verified against annuaire-entreprises.data.gouv.fr, 2026-09-11)
| Provider | SIREN | Paris presence |
|---|---|---|
| Citadines (The Ascott) | 311127278 | HQ Levallois-Perret (92); operates multiple Paris serviced-apartment residences |
| Aparthotel Adagio | 503938110 | Registered 75019 Paris |
| Reside Etudes Apparthotels (Residhome / Sejours & Affaires) | 488885732 | 75017 Paris |
| Appart'City | 490176120 | Paris estab. 75008; HQ Montpellier (34) |

## Verification method / caveats
- SIREN numbers confirmed via the official French register (annuaire-entreprises.data.gouv.fr) on 2026-09-11. These are **operating-entity** SIRENs, not per-residence SIRETs.
- `min_stay_nights` = 1 reflects flexible nightly booking; all four offer dedicated **corporate long-stay** rates suitable for 1-3 month relocations (`corporate_booking = yes`). Exact 30/90-day corporate terms to be confirmed at platform vetting.
- Citadines HQ is in Levallois-Perret (92), so `arrondissement` is left blank; it nonetheless operates numerous residences inside Paris intramuros.

## Rejected / unverified this run
- **Edgar Suites** and **Fraser Suites Le Claridge** could not have their operating-entity SIREN confirmed this run (the `recherche-entreprises` JSON API returned no text through the scraper and an annuaire search timed out). Excluded pending verification - see rejects CSV.
