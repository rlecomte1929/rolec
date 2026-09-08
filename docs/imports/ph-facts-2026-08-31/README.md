# Philippines requirement facts — 2026-08-31 (wave 9, rank 56)

12 browser-grounded facts for a **third-country national** relocating to the **Philippines** for
employment. Landed **8 requirement_items** (topic-grained) to `PHILIPPINES`, all
`review_status='pending'` / `verification_status='corpus_grounded'` — nothing served.
Append-only: global approved held at 153, `expert_verified=0`.

## Sourcing (all official `*.gov.ph`)
- `immigration.gov.ph` (Bureau of Immigration) — 9(g) work visa, PWP, ACR I-Card, ECC, tourist-stay cap, and the **AEP** requirement (from BI's own 9(g) documentary-requirements PDF)
- `sss.gov.ph` — compulsory SSS coverage (flagged `needs_lawyer_review`: the RA 11199 extension to foreign nationals rests on the statute, not the quoted sentence)
- `philhealth.gov.ph` — foreign-national PhilHealth registration via the ACR I-Card

## Verification
confirm_quotes referee: **12/12 CONFIRMED**. The AEP fact cites a BI PDF
(`.../V-NI-007-Rev_1Conversion.pdf`); it first mis-scored `HOLD_WRONG_SRC` under a
`confirm_quotes` PDF-detection bug (`raw[:5] == b"%PDF"` never matches), fixed in the same wave —
the quote is present verbatim in the PDF. The generator correctly skipped `bir.gov.ph` (JS SPA)
and DOLE / officialgazette (403 WAF) rather than fabricate, anchoring AEP to the BI PDF instead.
Nationality categorised `non-EEA → THIRD_COUNTRY`.
