# es-ie-dublin-temp-housing-2026-09-10 — Dublin temp/serviced housing vendors (A-P3)

**Corridor:** XX-IE · **service_category:** temp_accommodation · Dublin (IE)

## What this is
Vendor shortlist with **official provenance required**: a provider is accepted only if `source_url`
is an official register page that actually lists the firm. A provider's own website alone = tier-3 -> rejects.csv.

## Files
- `providers.csv` — 9 columns: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry
- `rejects.csv` — same 9 columns + `reject_reason`
- `manifest.json` — batch metadata, per-file records + sha256, accepted/rejected totals

**Accepted: 6 · Rejected: 0** · Register: Failte Ireland / Discover Ireland quality-assured accommodation directory

## Status
Candidate-only: `platform_vetting_status=pending`. accreditation_number/expiry are blank where the register does not publish them (not guessed).

## Honest notes
- Each accepted firm's Failte Ireland listing page was fetched and shows the approval statement.
- 3 Staycity properties share one operator/site but are separately Failte-Ireland-approved.
- Failte Ireland's Short-Term Letting register is not yet open (pending legislation); Discover Ireland is the usable provenance.
- CRO not cross-checked because Failte Ireland provenance sufficed for all 6.
