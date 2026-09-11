# es-ie-dublin-medical-2026-09-10 — Dublin GP / medical vendors (A-P4)

**Corridor:** XX-IE · **service_category:** medical · Dublin (IE)

## What this is
Vendor shortlist with **official provenance required**: a provider is accepted only if `source_url`
is an official register page that actually lists the firm. A provider's own website alone = tier-3 -> rejects.csv.

## Files
- `providers.csv` — 9 columns: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry
- `rejects.csv` — same 9 columns + `reject_reason`
- `manifest.json` — batch metadata, per-file records + sha256, accepted/rejected totals

**Accepted: 6 · Rejected: 0** · Register: HSE 'Find a GP' official directory

## Status
Candidate-only: `platform_vetting_status=pending`. accreditation_number/expiry are blank where the register does not publish them (not guessed).

## Honest notes
- source_url is the HSE directory page each practice appears on (name + Eircode).
- website_url filled only where independently confirmed (115 Medical, Fairview, Goatstown); blank otherwise.
- **Could NOT verify from the register** whether a practice accepts new patients or takes private/expat patients without a PPSN — contact each clinic to confirm.
- Medical Council register lists individual doctors, not practices, so HSE is the provenance though accreditation_body is recorded as 'Medical Council' per brief.
- No personal emails used (GDPR).
