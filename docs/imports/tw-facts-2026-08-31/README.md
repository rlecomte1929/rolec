# Taiwan requirement facts — 2026-08-31 (wave 9, rank 53)

12 browser-grounded facts for a **third-country national** relocating to **Taiwan** for
employment. Landed **9 requirement_items** (topic-grained) to `TAIWAN`, all
`review_status='pending'` / `verification_status='corpus_grounded'` — nothing served.
Append-only: global approved held at 153, `expert_verified=0`.

## Sourcing (all official `*.gov.tw`)
- `immigration.gov.tw` (National Immigration Agency) — ARC 30-day deadline, address/employer-change reporting, dependent income floor, APRC standard + fast-track
- `ezworktaiwan.wda.gov.tw` (Workforce Development Agency) — specialised-work salary floor, employer-files-work-permit
- `ntbt.gov.tw` (National Taxation Bureau) — 18% non-resident withholding, foreign-special-professional 50%-over-NT$3M break
- `goldcard.nat.gov.tw` — Employment Gold Card (self-sponsored combined permit)
- `nhi.gov.tw` — NHI enrolment from day one for the employed
- `bli.gov.tw` — labour pension now covers all foreign professionals (2026-01-01 change)

## Verification
confirm_quotes referee: **11/12 CONFIRMED** by headless fetch; **1 (NHI) REVIEW_BROWSER**
(nhi.gov.tw served a WAF/JS challenge to curl) — the quote was then **browser-verified verbatim**
on the live page before landing. Nationality categorised `non-EEA → THIRD_COUNTRY` (non-EEA
destination). Notable: NIA's current guideline says ARC within **30 days** (not the widely-repeated
15), captured as the TIMELINE fact.
