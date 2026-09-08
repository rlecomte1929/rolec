# Vendor candidates — RE-SOURCED (Option B) — 2026-09-08/09

The 235 tier-3 rejects from [`vendor-candidates-2026-09-08`](../vendor-candidates-2026-09-08/README.md)
routed back to Otto to be re-sourced against real registers (see that batch's
`otto_resourcing_brief.md`). Otto researches → writes NDJSON+manifest to GCS → the "ReloPass
corridor-data import automation" session relays the public GCS URLs → this (applier) session
re-verifies each source against its register, converts → CSV, and lands to the vetting queue
(`platform_vetting_status='pending'`, append-only, human approve-to-serve gate untouched).

This directory **accumulates** the re-sourced sub-batches (one `src/*.ndjson` per city×category)
as they arrive. Each sub-batch is landed with the append-only tripwire verified
(`supplier_service_capabilities` `approved` count + md5 unchanged).

## Sub-batches landed

### FR-NO movers — `vendor-resourced-fr-no-movers-2026-09-08` (landed 2026-09-09)
- Source (GCS, public-read): `1788906918368_362xcyp2.ndjson` (+ manifest `1788906927057_wrp9doza.json`).
- Otto manifest: **4 firms found on a register, 2 rejected** (NFB International Relocations —
  merged into Alfa Mobility Norway, its FIDI slug now resolves to the Alfa page; AGS Movers
  Norway — no NO entity on FIDI/EuRA). Rejects reported by name, not fabricated.
- **Independently re-verified**: all 4 `source_url`s are register per-entity pages that match the
  wired `entry_url_pattern` AND returned HTTP 200 with the firm named on the page (FIDI
  `/find-fidi-affiliate/…` ×3, EuRA `/members/relocation` ×1) — curled 2026-09-09.
- Landed: **+2 new suppliers** (Adams Express, Relocation.no — NO/movers), **+3 pending
  capabilities**; 1 deduped against an existing supplier (Alfa Mobility, already in prod), 0
  rejected by the tier gate. Tripwire: `ssc` `approved` **130 → 130**, md5 unchanged.
- **PSS International Removals** landed as **XX-GB** movers, not FR-NO: its register HQ is
  Croydon, UK, so the converter keys it to its true country (XX-GB). Kept honest rather than
  forced to Norway; it is a valid FIDI mover regardless. The vetter can note NO-corridor service.

## Honesty notes
- `accreditation_number` is NULL on all 4 — FIDI publishes only a FAIM expiry year and EuRA no
  number, so Otto invented none. `accreditation_expiry` column is always blank (the NDJSON carries
  no expiry). The vetter confirms each firm on the register at `/admin/vetting-queue`.
- Nothing here is served. Promotion to served is the separate human approve-to-serve gate.

## Pipeline (per sub-batch)
```bash
PY=.venv311/bin/python
$PY scripts/convert_vendor_ndjson_to_csv.py <dir>/vendor_candidates.csv <dir>/src/*.ndjson
# re-verify each source_url against its register (HTTP 200 + name on page), then:
$PY scripts/land_vendor_candidates.py <dir>/vendor_candidates.csv --apply --promote
```
