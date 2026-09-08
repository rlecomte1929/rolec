# Netherlands destination facts (2026-08-31) — HELD FOR RECONCILIATION (not promoted)

18 dual-audience Dutch facts (EEA + non-EEA + doubled universals), sourced to ind.nl, government.nl,
digid.nl, belastingdienst.nl — captured verbatim via browser get_page_text.

## ⚠️ NOT promoted — Netherlands is already covered AND SERVED
Prod already holds **10 NETHERLANDS `requirement_items`, all 10 `review_status='approved'`** (served):
30% ruling, residence-permit collection, Dutch health insurance, IND-recognised-sponsor contract,
municipality registration + BSN, permanent residence/extension, HSM/EU-Blue-Card permit, signed
contract, valid passport. Promoting this batch would create pending **duplicates of already-approved
rows** — an append-only violation in spirit. Held for reconciliation.

## Genuinely net-new here (worth adding after reconciliation)
- `NL-3C:mvv_entry_visa` — the MVV (Type-D entry visa) step, not in the 10
- `NL-3C:tb_test_after_arrival` — post-arrival TB test
- `NL-3C:single_permit_gvva` — the GVVA single permit (non-HSM paid employment)
- `NL-EEA:no_residence_permit` / `NL-EEA:no_work_permit_twv` — the EU/EEA free-mover facts (the 10 are third-country-shaped)
- `NL-*:digid` — DigiD (gates all online gov/tax/health admin)

The rest (HSM permit, recognised sponsor, BSN, health insurance, 30% ruling, tax residency) overlap
the approved 10 and must be reconciled, never re-added as pending.

## Code note (for whoever reconciles)
None of the Dutch source hosts match the current `overheid.nl` allowlist suffix — landing any NL fact
via the Otto pipeline needs `ind.nl`, `government.nl`, `digid.nl`, `belastingdienst.nl` added to
`_OFFICIAL_SUFFIXES`/`_OFFICIAL_HOSTS` in `backend/imports/otto/parsers.py`.
