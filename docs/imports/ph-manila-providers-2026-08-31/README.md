# Metro Manila provider harvest — 2026-08-31 (wave 9, XX-PH)

Relocation-service providers in **Metro Manila, Philippines**, each sourced from an official
statutory register. Landed to **pending** in the admin vetting queue; nothing served. Append-only:
approved capabilities held at 130, fingerprint unchanged.

## Landed (promoted=16 → suppliers +15, pending capabilities +16)
| category | rows | register |
|---|---|---|
| banks | 8 | Bangko Sentral ng Pilipinas — directory of BSP-supervised universal/commercial banks (`bsp.gov.ph`; the FCDU-authority list is the concrete register document, the JS directory hub being unfetchable). Some rows land with `website_url` blank (register carries none). |
| movers | 3 | FIDI FAIM — Metro Manila affiliates (AGS Four Winds, Asian Tigers PH, Santa Fe Manila), per-affiliate detail pages |
| schools | 5 | IBO — IB World Schools in Metro Manila; `accreditation_number` = IB school code |

## Skipped (no browsable public statutory firm register — not padded)
- **legal_admin** (IBP), **tax_finance** (PRC/Board of Accountancy CPA), **housing_agencies**
  (PRC real-estate brokers) — all three are individual-practitioner rolls / per-name verification
  portals, not browsable firm directories.

Discipline note: `ibo.org` presented a Cloudflare Turnstile; the generator did **not** click it
(bot-detection bypass is off-limits) and used the indexed finder for school codes instead. Expected
APAC weak-register skips (`docs/imports/_verification_priors.md` §4).
