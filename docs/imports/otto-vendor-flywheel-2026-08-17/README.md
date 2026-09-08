# Otto vendor flywheel — 2026-08-17

Six GCS NDJSON batches (~248 vendor candidates: Paris/Oslo, Madrid/Dublin, Stavanger/Aberdeen,
Stockholm/Copenhagen, Helsinki/Berlin, Frankfurt/Milan). Converted with
`scripts/convert_vendor_ndjson_to_csv.py` into the nine-column harvest CSV.

**Do not** land these with `scripts/import_supplier_candidates.py`'s unscoped promote flag.
Stage + promote only this run:

```bash
python scripts/land_vendor_candidates.py docs/imports/otto-vendor-flywheel-2026-08-17/b2-madrid-dublin.csv
python scripts/land_vendor_candidates.py docs/imports/otto-vendor-flywheel-2026-08-17/b2-madrid-dublin.csv --apply
```

Dry-run is the default. `--apply` writes `vendor_candidates` then promotes **only those
`run_id`s** to `suppliers` / `supplier_service_capabilities` at `platform_vetting_status='pending'`.
Nothing is employee-visible until a human approves.

## What the converter does
- `corridor` is a single ORIGIN-DEST token (parser dest ISO = token 2). Bidirectional Otto
  fields (`FR-NO,NO-FR`, `FR↔DE`) are split; when `country` is set, only dest-matching pairs
  are kept (a Berlin row with many `DE-xx` origins therefore expands to several CSV rows).
- Accreditation cells are copied only when Otto supplied them. Never invented.
- `source_url` prefers `accreditation_source_url` so a company homepage does not hide a register.

## Gate result (this checkout, after mapping the flywheel registers)

| file | Otto records | CSV rows | `validate()` pass | reject (SELF_DECLARED) |
|---|---|---|---|---|
| b1-paris-oslo | 44 | 44 | 5 | 39 |
| b2-madrid-dublin | 43 | 43 | 18 | 25 |
| b3-stavanger-aberdeen | 45 | 45 | 2 | 43 |
| b4-stockholm-copenhagen | 42 | 63 | 27 | 36 |
| b5-helsinki-berlin | 36 | 144 | 6 | 138 |
| a2a-frankfurt | 19 | 57 | 6 | 51 |
| a2a-milan | 21 | 21 | 0 | 21 |
| **total** | **250** | **417** | **64** | **353** |

Every reject is still SELF_DECLARED: Otto cited the firm's own site (or Wikipedia, North Data,
Proff, PagineGialle, Ufficio Camerale). Those hosts stay **off** `_DOMAIN_TO_SOURCE` on
purpose — the same class of mistake as `blkr-berlin.de`.

Registers that **were** mapped for this flywheel (PUBLIC_REGISTER, tier 2, staged `claimed`):
`abogacia.es`, `reaf.economistas.es`, `charteredaccountants.ie`, `taxinstitute.ie`,
`advokatsamfundet.dk` (alias of Advokatnøglen), `advokatsamfundet.se`, `far.se`,
`lawsociety.org.uk`. Plus FIDI / Irish / Danish / Finnish hosts already in the catalogue.

Leftover unknown hosts: `unknown-domains.txt`. GCS originals stay public-read under
`storage.googleapis.com/audos-images/workspace-media/d0c29613-9cb5-4652-9c6a-494eeed352e5/`.
SHA-256s and URLs are in `manifest.json`.
