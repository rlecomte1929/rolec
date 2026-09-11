# AD-P3 · Singapore serviced-apartment providers (FR->SG corridor)

**batch_id:** `fr-sg-singapore-temp-housing-2026-09-10`
**corridor:** `XX-SG` (temporary accommodation — not corridor-specific)
**service_category:** `temp_accommodation`
**persona:** Adrien — relocating to Singapore on an Employment Pass, needs temporary/serviced housing on arrival

## Deliverables
| file | rows | sha256 |
|---|---|---|
| `fr-sg-singapore-temp-housing-2026-09-10.providers.csv` | 6 | `74abef2dfaf55adbb87505dafef9a5e14b8ddeb24a3bd30746cd9f6055ccf829` |
| `fr-sg-singapore-temp-housing-2026-09-10.rejects.csv` | 3 | `0c248c8a459a1cc9adc502705da65241f6d71e89b5d0c20adb9bfa15ee2120bf` |

All rows are candidate-only: review_status=`pending`, verification_status=`representative`, status=`draft`, platform_vetting_status=`pending`.

## Official register used (provenance)
**Hotels Licensing Board (HLB)**, administered by the **Singapore Tourism Board (STB)** — the active **Licensed Hotels** register, published as open data on **data.gov.sg** (dataset `d_654e22f14e5bb817423f0e0c9ac4f632`, "Hotels", 468 licensed premises).
Serviced apartments with 4+ rooms operate under the Hotels Act and must hold a **Certificate of Registration and Hotel-Keeper's Licence** issued by HLB — appearing on this register IS the accreditation.

All six accepted providers were matched by **exact premises name** in the official HLB dataset:
| company_name | hotel-keeper (licensee) | postal | rooms |
|---|---|---|---|
| Ascott Orchard Singapore | Eugene Lee | 229724 | 220 |
| Ascott Singapore Raffles Place | Lim Kok Tee | 049247 | 146 |
| Capri By Fraser China Square, Singapore | Vernon Lee Koon Yong | 058743 | 304 |
| Citadines Rochor Singapore | Soh Ai Fong | 218227 | 320 |
| lyf Funan Singapore | Genevieve Khua | 179370 | 329 |
| Pan Pacific Serviced Suites Beach Road | Yap Teck Wai | 199592 | 180 |

(Ascott Orchard, Ascott Raffles Place, Citadines Rochor and lyf Funan are all The Ascott Limited brands — discoverasr.com.)

## 9-column CSV schema (exact order)
`corridor, service_category, company_name, website_url, source_name, source_url, accreditation_body, accreditation_number, accreditation_expiry`

- `accreditation_body` = **HLB** for every accepted provider.
- `accreditation_number` / `accreditation_expiry` are **left blank** — the public HLB data.gov.sg dataset does not expose individual licence numbers or expiry dates (it lists premises name, hotel-keeper name, total rooms, postal code, location). **No licence number or expiry was invented.**
- `website_url` is the operator's own brand domain — informational only; it is NOT the provenance source.

## Rejects (tier-3, own-site only)
Somerset, Frasers Suites Singapore and Oakwood were **not located on the HLB Licensed Hotels register under those brand names** — only the operators' own websites were found, which is tier-3 provenance and auto-rejected pending an official-register match. (They may be licensed under different registered premises names; re-check the HLB register before accepting.)

## Source access issues (honest log)
- The **data.gov.sg datastore_search JSON API** and the **api-open poll-download** endpoint both returned no text via the platform scraper (it expects HTML).
- The dataset was retrieved successfully via a **direct HTTPS download of the official data.gov.sg signed S3 blob** (poll-download API -> signed S3 URL) and parsed locally.
- **No provider was accepted without an exact match on the official HLB register.** Firms' own sites are recorded only as informational `website_url`, never as the source of accreditation.
