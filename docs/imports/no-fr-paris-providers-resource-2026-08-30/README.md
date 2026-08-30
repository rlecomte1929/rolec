# Paris providers — re-source of 4 rejected rows (NO→FR, 2026-08-30)

The `no-fr-paris-providers-2026-08-30` batch landed 25 of 29 providers. **Four were rejected** for a
bare/listing `source_url` (a search or listing page evidences no single firm — the gate requires the
per-entity register record). Otto re-sourced all four to per-entity pages; this batch lands them.

## The 4 (corridor `NO-FR`, all `platform_vetting_status='pending'`)
| firm | category | per-entity source | accreditation |
|---|---|---|---|
| AGS France (SOFDI) | movers | `fidi.org/find-fidi-affiliate/ags-france` | FIDI FAIM → 2028 |
| Santa Fe Relocation Services France | movers | `fidi.org/find-fidi-affiliate/santa-fe-relocation-paris` | FIDI FAIM → 2029 |
| Gosselin Mobility Solutions | movers | `fidi.org/find-fidi-affiliate/gosselin-5` | FIDI FAIM → 2027 |
| 1818 Immobilier | housing_agencies | `fnaim.fr/agence-immobiliere/27634/…` | FNAIM 27634 |

Zero rejects this round — every firm resolved to a genuine per-entity page.

## Landed
`import_supplier_candidates.py … --apply`, then a **run-scoped** promote (`promote(run_ids=[…])`) —
NOT the CLI's unscoped `--promote`, which would push the ~474-row pending backlog. Result: 3 staged +
1 duplicate (AGS France already in the pipeline; landed under its full legal name at cc=FR), all 4
promoted to `public.supplier_service_capabilities` at `platform_vetting_status='pending'`. The admin
vet at `/admin/vetting-queue` is still required before any employee sees them.

## Notes
- **Category normalisation:** Otto delivered `service_category` as `moving`/`housing`; normalised to
  the canonical `movers`/`housing_agencies` (the brief's own vocabulary, and what
  `vendor_harvester`/`registry_sources` match on). Nothing else in the rows changed.
- **1818 Immobilier flag (Otto, honest):** its site resolves to `banqueprivee1818.com` — a private
  bank's HNW property arm, not a general letting agent. The FNAIM record is genuine; confirm
  standard-rental fit at vet time, or tag as premium/specialist.
