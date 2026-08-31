# Taipei provider harvest — 2026-08-31 (wave 9, XX-TW)

Relocation-service providers in **Taipei, Taiwan**, each sourced from an official statutory
register. Landed to **pending** (`platform_vetting_status='pending'`) in the admin vetting queue;
nothing served. Append-only: approved capabilities held at 130, fingerprint unchanged.

## Landed (promoted=22 → suppliers +19, pending capabilities +22)
| category | rows | register |
|---|---|---|
| banks | 12 | Central Bank of the ROC (Taiwan) — domestic-bank list (`cbc.gov.tw`), incl. expat-relevant foreign subsidiaries (Standard Chartered / HSBC / Citibank Taiwan) |
| movers | 2 | FIDI FAIM — the only two Taiwan affiliates (Crown Van Lines, Allied Moving Services), per-affiliate detail pages |
| schools | 8 | IBO — IB World Schools in Taipei; `accreditation_number` = IB school code |

(19 new supplier rows for 22 capabilities — 3 banks already existed as supplier entities from other
corridors and gained a new XX-TW capability.)

## Skipped (no browsable public statutory firm register — not padded with firm sites)
- **legal_admin** — Taipei Bar Association roster lists individual opted-in lawyers, not firms.
- **tax_finance** — CPA registers are individual-practitioner rolls.
- **housing_agencies** — MOI real-estate-broker system is verify-by-name, not enumerable.

These are the expected APAC weak-register skips (see `docs/imports/_verification_priors.md` §4).
