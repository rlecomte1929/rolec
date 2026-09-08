# Jakarta provider harvest — 2026-08-31 (wave 9, XX-ID)

Relocation-service providers in **Jakarta, Indonesia**, each sourced from an official register.
Landed to **pending** in the admin vetting queue; nothing served. Append-only: approved
capabilities held at 130.

## Landed (promoted=9 → suppliers +9, pending capabilities +9)
| category | rows | register |
|---|---|---|
| movers | 3 | FIDI FAIM — the complete Indonesia affiliate set (Santa Fe Jakarta, PT Kellys Express, Asian Tigers Indonesia), per-affiliate detail pages |
| schools | 6 | IBO — IB World Schools in DKI Jakarta; `accreditation_number` = IB school code |

## Skipped
- **banks** — OJK (`ojk.go.id`), Bank Indonesia and LPS were all **network-unreachable** from the
  harvest environment (ECONNREFUSED / ECONNRESET; Indonesian gov domains are browser-allowlist-gated
  here). The generator refused to cite a register listing it could not open, so banks were skipped
  rather than fabricated. Re-runnable once OJK/BI/LPS are reachable — the richest ID category is
  purely blocked by environment, not by absence of a register.
- **legal_admin / tax_finance / housing_agencies** — no browsable public statutory firm register;
  not padded with firm sites (priors §4).
