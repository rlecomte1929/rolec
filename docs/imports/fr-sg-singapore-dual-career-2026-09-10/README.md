# AD-P7 · Singapore spouse/partner career-transition vendors (FR->SG corridor)

**batch_id:** `fr-sg-singapore-dual-career-2026-09-10`
**corridor:** `XX-SG` (career services — not corridor-specific)
**service_category:** `spouse`
**persona:** Adrien relocating to Singapore on an Employment Pass; accompanying partner on a Dependant's Pass who wants to continue/transition their career.

> Regulatory context only (NOT a service in this file): a Dependant's Pass holder needs a **Letter of Consent (LOC)** or their **own work pass** to take up employment in Singapore. This file lists **career-services vendors only**.

## Deliverables
| file | rows | sha256 |
|---|---|---|
| `fr-sg-singapore-dual-career-2026-09-10.providers.csv` | 5 | `e657816d06edbbbfb27adf14b1cd97b764f0582575f5501d7b6caa9133f56617` |
| `fr-sg-singapore-dual-career-2026-09-10.rejects.csv` | 3 | `c15aeafd3bb4adf6d6aca348bdfb58be116c6d00c2fd1ff9e283e4ac9ea1a39f` |

All rows are candidate-only: review_status=`pending`, verification_status=`representative`, status=`draft`, platform_vetting_status=`pending`.

## Official register used (provenance)
**Accounting and Corporate Regulatory Authority (ACRA) — Information on Corporate Entities**, published as open data on **data.gov.sg** (collection id 2 — 27 alphabetically-partitioned CSV files, updated monthly). Each accepted vendor was matched by **exact `entity_name`** with **`entity_status`='Live'** in the current (Aug 2026) partition. Appearing on the ACRA register as a Live entity IS the accreditation.

| company_name | UEN (accreditation_number) | status | primary SSIC / activity |
|---|---|---|---|
| Executive Coach International Pte. Ltd. | 200414184R | Live Company | 70201 (management consultancy) |
| Right Management Singapore Pte. Ltd. | 199308166C | Live Company | 70201 / 82301 (career transition / outplacement — ManpowerGroup) |
| Avodah People Solutions Pte. Ltd. | 201811519K | Live Company | 70204 — "corporate consultancy services for talent career development management" |
| Career Navigators SG LLP | T16LL1455L | Live | 85509 — "providing career and motivational courses" |
| Randstad Pte. Limited | 199304055W | Live Company | 78104 / 70201 — operates RiseSmart outplacement / career-transition |

## 9-column CSV schema (exact order)
`corridor, service_category, company_name, website_url, source_name, source_url, accreditation_body, accreditation_number, accreditation_expiry`

- `accreditation_body` = **ACRA** for every accepted provider.
- `accreditation_number` = the entity's **UEN**.
- `accreditation_expiry` is **left blank** — ACRA registration carries a live/inactive status, not an expiry date. **None was invented.**
- `website_url` is the operator's own brand domain (informational only). It is **left blank for Career Navigators SG LLP** because no website could be reliably tied to that exact legal entity without assumption.

## ICF note (honesty)
The **ICF Credentialed Coach Finder** and **"Verify a Coach"** directories (`apps.coachingfederation.org`) were the intended coach-credential source, but both are **JS-gated dynamic pages** that could not be enumerated from this egress (search results render as a `[NumberOfResults]` placeholder). Individual ICF credential status was therefore **NOT asserted per-vendor**; provenance falls back entirely to the official **ACRA company register**. (Executive Coach International's founder being an ICF Master Certified Coach is recorded as context only, not a verified per-record accreditation.)

## GDPR note
No personal data captured. All accepted records are **business entities** identified by ACRA legal name and UEN — no named individuals, personal emails or personal phone numbers.

## Rejects (tier-3, own-site only / not matched on ACRA)
- **NetExpat** — global (Belgium-HQ) dual-career provider; no SG-registered entity located on the ACRA register. Own website only.
- **Coach4Expats** — EU-based expat/partner career service; no SG-registered entity on the ACRA register. Own website only.
- **CNavigators** — trading name not matched on ACRA letter 'C' under this spelling; only the provider's own website found. May be registered under a different legal name — re-check ACRA/BizFile before accepting.

## Source access issues (honest log)
- ACRA data retrieved via the official **data.gov.sg api-open poll-download** endpoint (→ signed AWS S3 URL) and parsed locally; matched by exact `entity_name` + `entity_status='Live'`.
- The data.gov.sg **dataset-metadata JSON endpoint** returns HTTP 403 without a `User-Agent` header (worked once a browser UA was sent).
- The **ICF CCF / Verify-a-Coach** directories and **ACRA BizFile+** interactive search are JS-gated and could not be scraped; the ACRA open dataset was used as the equivalent official register.
- **No provider was accepted without an exact ACRA register match.** Firms' own sites are recorded only in rejects, never as the source of accreditation.
