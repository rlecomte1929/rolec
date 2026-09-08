# Toronto providers — Canada destination (2026-08-31)

20 Toronto providers across all 6 live categories, sourced from the authoritative Canadian register
per category by a Claude Code research subagent. Validated 20/20, staged run-scoped, promoted to the
vetting queue.

## What landed (20/20, all `platform_vetting_status='pending'`)
| category | n | register cited | tier | per-entity URL |
|---|---|---|---|---|
| movers | 3 | FIDI FAIM affiliate | 1 | yes (FAIM expiry) |
| legal_admin | 3 | Law Society of Ontario directory | 2 | no (PUBLIC_REGISTER) |
| tax_finance | 3 | CPA Ontario firm directory | 2 | no (PUBLIC_REGISTER) |
| banks | 5 | CDIC member institutions list | 2 | no (PUBLIC_REGISTER) |
| schools | 3 | Ontario Min. of Education Private School List (BSID) | 2 | no (PUBLIC_REGISTER) |
| housing_agencies | 3 | RECO registrant search | 2 | no (PUBLIC_REGISTER) |

## Code this batch required
- `registry_sources.py`: `XX-CA` corridor + 5 CA `RegistrySource` entries (LSO, CPA Ontario, CDIC,
  Ontario Min-Ed school list, RECO — all PUBLIC_REGISTER tier 2; movers reuse the global FIDI source).
- `suppliers/parsers.py`: 5 domain→source rows (`lso.ca`, `cpaontario.ca`, `cdic.ca`, `data.ontario.ca`,
  `reco.on.ca`).
- `test_vendor_harvester.py`: pairs-in-scope 42 → 48 (8 corridors × 6 categories).

## Load record (Runbook B)
```
read_csv + vendor_harvester.validate   -> 20/20 validate, country_code=CA
stage(dry_run=False)                    -> 6 runs, 20 staged, 0 dups, 0 rejects
promote(run_ids=<those>, dry_run=False) -> promoted 20, skipped 0, problems 0
verify: suppliers 233->253 (+20); +20 capabilities all 'pending'; approved caps unchanged (130->130)
```

**Honest excludes (subagent):** Fragomen Canada (a CICC consultancy, not an LSO firm — wrong register);
Upper Canada College (BSID verified but website unconfirmed — not guessed); non-Toronto FIDI movers.

**Gate remaining (human):** vet each at `/admin/vetting-queue` (PUBLIC_REGISTER rows staged 'claimed' —
confirm the firm against its register). Code lands via PR (founder merge).
