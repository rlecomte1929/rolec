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

### XX-GB movers (Aberdeen) — `vendor-resourced-xx-gb-movers-2026-09-08` (landed 2026-09-09)
- Source (GCS): `1788917900665_fz0ta7k4.ndjson` (+ manifest `1788917902083_ivvzb79f.json`).
- Otto manifest: **2 firms found on FIDI, 2 rejected** (Purdie Worldwide — Euromovers member only,
  not a published FIDI affiliate; Simpsons International Removals — Dartford/Kent, not Aberdeen, no
  FIDI/EuRA listing). Honest rejects, not fabricated.
- **Independently re-verified**: both `source_url`s are FIDI `/find-fidi-affiliate/…` per-entity
  pages returning HTTP 200 with the firm named (Shore Porters, Clark & Rose) — curled 2026-09-09.
- Landed: **+2 new suppliers** (The Shore Porters Society, Clark & Rose — GB/movers), +2 pending
  capabilities, 0 duplicates, 0 rejected. Tripwire: `ssc` `approved` **130 → 130**, unchanged.
- Label note: `accreditation_body` here is `FIDI-FAIM` (vs `FIDI` on FR-NO) — same register, a
  cosmetic label variant; the tier gate keys on the `fidi.org` domain, not the label, so it is
  immaterial. `accreditation_number` NULL on both (FIDI publishes only a FAIM expiry year).

### FR-DE movers (Frankfurt) — `vendor-resourced-fr-de-movers-2026-09-08` (processed 2026-09-09)
- Source (GCS): `1788921051328_bmh0husu.ndjson` (+ manifest `1788921077900_oz4xrsov.json`).
- Otto: **1 firm found, 2 rejected** (Zapf Umzüge, Arnold & Hanl — small local German movers,
  legitimately not FIDI/EuRA members; international-relocation networks don't list local firms —
  expect similar low yield on other local-mover batches).
- **NO new supplier landed.** The one firm, **Crown Relocations Frankfurt**, is a DUPLICATE —
  already a supplier in prod, so the tier gate/dedupe staged 0 (dry-run: staged 0, duplicates 1,
  rejected 0). No prod write done — nothing new to stage, and re-recording a duplicate adds no
  queue-visible candidate. The re-sourced EuRA evidence is preserved here in the committed NDJSON.
- **Vetter caveat (flagged honestly by Otto):** the EuRA `source_url`
  (`/members/crown-worldwide-group`) is the GLOBAL PARENT (Crown Worldwide Group), not a
  Frankfurt-specific listing. It clears the shape gate (a real EuRA per-entity page), but whether
  the parent's EuRA membership evidences the Frankfurt office is a vetter judgment at
  `/admin/vetting-queue` — recorded here, not auto-decided.

### XX-IE movers (Dublin) — `vendor-resourced-xx-ie-movers-2026-09-09` (landed 2026-09-09)
- Source (GCS): `1788940289394_ug4b14d3.ndjson` (+ manifest `1788940293455_itqle5rs.json`).
- Otto manifest: **4 sourced, 12 rejected** — rejects honest by name: 5 FIDI pages whose address
  is not Dublin (Farmington Hills MI, Dartford, Brandon, Montreal, Uxbridge), Crown 404, and 6 EuRA
  members that are DSP/RMC/serviced-apartment providers or Cork/Kinsale-based, not Dublin removal
  movers. Reported, not fabricated.
- **Independently re-verified 2026-09-09**: all 4 `source_url`s are FIDI `/find-fidi-affiliate/…`
  (×3) or EuRA `/members/…` (×1) per-entity pages returning HTTP 200 with the firm named. Guarded
  against a directory-template false positive with a cross-contamination check — each FIDI page
  contains ONLY its own firm (Cronin 11/0/0, Irish Relo 0/3/0, Get Cracking 0/0/4), all
  Dublin/Ireland; FIDI `<title>` = `CRONIN RELOCATIONS IRELAND | FIDI`.
- **Cronin de-duplicated:** the batch listed the same firm twice — "Cronin Relocations Ireland"
  (FIDI) and "Cronin Ireland Relocations" (EuRA), same website `ireland-relocations.com` and phone.
  Kept the FIDI-FAIM row (stronger register for a mover), dropped the EuRA row from the CSV — its
  evidence is preserved in `src/xx-ie-movers.ndjson`. Moot in the end: Cronin was **already staged
  + promoted** in prod (`vendor_candidates` ES-IE/movers, dedupe_key `ireland-relocations.com`) from
  earlier work, so the pipeline skipped it regardless (dry-run: read 3, staged 2).
- Landed: **+2 new suppliers** (Irish Relo, Get Cracking Relocations — IE/movers), **+2 pending
  capabilities**, 0 duplicates, 0 tier-gate rejects (Cronin skipped as already-staged). Tripwire:
  `ssc` `approved` **130 → 130**, md5 `1c4c3899…` unchanged; total pending **982 → 984** (+2).
  FIDI `source_url` persisted verbatim on both new suppliers.
- Corridor-label note: the converter maps destination `IE → ES-IE` (its hardcoded corridor) and
  `_dest_iso_from_corridor` recovers `country_code=IE`, so both capabilities scope to **destination
  IE** (`coverage_scope_type='country'`) — the label is cosmetic, the scope is Ireland.
  `accreditation_number` NULL (FIDI publishes only a FAIM expiry year).

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
