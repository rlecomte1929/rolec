# Ho Chi Minh City provider harvest — 2026-08-31 (wave 9, XX-VN)

Relocation-service providers in **Ho Chi Minh City, Vietnam**, each sourced from an official
statutory register. Landed to **pending** in the admin vetting queue; nothing served. Append-only:
approved capabilities held at 130, fingerprint unchanged.

## Landed (promoted=16 → suppliers +10, pending capabilities +16)
| category | rows | register |
|---|---|---|
| banks | 6 | State Bank of Vietnam — foreign-bank-branch register (`sbv.gov.vn`), HCMC branches. The register carries no per-bank URL, so these rows land with **`website_url` blank** rather than a fabricated URL. |
| movers | 3 | FIDI FAIM — HCMC affiliates (Asian Tigers, Saigon Van, Santa Fe HCMC), per-affiliate detail pages |
| schools | 7 | IBO — IB World Schools in HCMC; `accreditation_number` = IB school code |

(10 new supplier rows for 16 capabilities — 6 foreign banks — Citibank, Deutsche, SMBC, Mizuho,
MUFG, BNP Paribas — already existed as supplier entities and gained a new XX-VN capability.)

## Skipped (no browsable public statutory firm register — not padded)
- **legal_admin / tax_finance / housing_agencies** — no browsable English-language statutory
  firm register (HCMC Bar / Vietnam Bar Federation roll not locatable); only firm websites exist.

Note: the SBV site's browser WAF hard-rejects automation; the register table was reachable via the
plain fetcher. Expected APAC weak-register skips (`docs/imports/_verification_priors.md` §4).
