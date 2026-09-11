# es-ie-dublin-language-2026-09-10 — Dublin language-school vendors (A-P6)

**Corridor:** XX-IE · **service_category:** language · Dublin (IE)

## What this is
Vendor shortlist with **official provenance required**: a provider is accepted only if `source_url`
is an official register page that actually lists the firm. A provider's own website alone = tier-3 -> rejects.csv.

## Files
- `providers.csv` — 9 columns: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry
- `rejects.csv` — same 9 columns + `reject_reason`
- `manifest.json` — batch metadata, per-file records + sha256, accepted/rejected totals

**Accepted: 3 · Rejected: 3** · Register: TrustEd Ireland statutory listing (QQI/ACELS International Education Mark)

## Status
Candidate-only: `platform_vetting_status=pending`. accreditation_number/expiry are blank where the register does not publish them (not guessed).

## Honest notes
- Below the 4-6 target because only **5 ELE providers are nationally authorised so far**; 3 are unambiguously Dublin.
- 2 rejects are non-Dublin (Cork, Galway); 1 reject (Atlas) is an own-site ACELS claim that could not be confirmed on a register.
- ACELS is now QQI-administered and closed to new applicants; ILEP is closed; the ACELS by-county recognisedproviders map is JS-driven and unreadable, which capped additional Dublin finds.
