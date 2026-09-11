# es-ie-dublin-tax-advisors-2026-09-10 — Dublin tax-advisor vendors (A-P9)

**Corridor:** ES-IE · **service_category:** tax_finance · Dublin (IE)

## What this is
Vendor shortlist with **official provenance required**: a provider is accepted only if `source_url`
is an official register page that actually lists the firm. A provider's own website alone = tier-3 -> rejects.csv.

## Files
- `providers.csv` — 9 columns: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry
- `rejects.csv` — same 9 columns + `reject_reason`
- `manifest.json` — batch metadata, per-file records + sha256, accepted/rejected totals

**Accepted: 0 · Rejected: 2** · Register: Irish Tax Institute member directory / Chartered Accountants Ireland Find-a-Firm (both attempted)

## Status
Candidate-only: `platform_vetting_status=pending`. accreditation_number/expiry are blank where the register does not publish them (not guessed).

## Honest notes
- **Honest zero.** Both required registers were down at fetch time (2026-09-11): ITI 'Find a CTA' is temporarily offline for a database update; CAI's main site returned a maintenance page and its Firms Directory renders results client-side (no fetchable listing).
- No firm names captured, so none invented. Both register-level blocks are recorded in rejects.csv.
- Retry once ITI search is restored and CAI exits maintenance (CAI likely needs a headless/browser fetch).
