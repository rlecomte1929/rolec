# es-ie-dublin-dual-career-2026-09-10 — Dublin dual-career / spouse-employment vendors (A-P7)

**Corridor:** XX-IE · **service_category:** spouse · Dublin (IE)

## What this is
Vendor shortlist with **official provenance required**: a provider is accepted only if `source_url`
is an official register page that actually lists the firm. A provider's own website alone = tier-3 -> rejects.csv.

## Files
- `providers.csv` — 9 columns: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry
- `rejects.csv` — same 9 columns + `reject_reason`
- `manifest.json` — batch metadata, per-file records + sha256, accepted/rejected totals

**Accepted: 0 · Rejected: 5** · Register: ICF / EMCC accredited directories + CRO (all attempted)

## Status
Candidate-only: `platform_vetting_status=pending`. accreditation_number/expiry are blank where the register does not publish them (not guessed).

## Honest notes
- **Honest zero.** ICF find-a-coach, EMCC Global directory and CRO/opencorporates search are all JS-driven, login-gated or captcha-gated and returned no fetchable listing.
- All 5 candidates found are provider own-sites (tier-3) and are in rejects.csv with reasons.
- Retry when a fetchable/official directory endpoint is available (these directories mostly list individual coaches, not firms).
