# London providers — UK destination (2026-08-31)

Otto-first was attempted (bus); the reliable engine (a Claude Code research subagent) sourced 27
London providers from the authoritative UK register per category, each with a **per-entity URL**.
Delivered as a 9-column CSV matching the Dublin batch; validated by `read_csv` + `vendor_harvester.validate`
(27/27 pass), staged run-scoped, promoted to the vetting queue.

## What landed (27/27, all `platform_vetting_status='pending'`)
| category | n | register cited | tier |
|---|---|---|---|
| movers | 7 | FIDI FAIM affiliate (per-entity URL) | 1 |
| legal_admin | 3 | SRA — Solicitors Regulation Authority register (per-firm, SRA number) | 2 |
| tax_finance | 2 | ICAEW — Find a Chartered Accountant (per-firm) | 2 |
| banks | 6 | FCA Financial Services Register (per-firm, FRN) | 2 |
| schools | 5 | GIAS — Get Information About Schools / DfE (per-school, URN) | 2 |
| housing_agencies | 4 | ARLA Propertymark member directory (per-branch) | 2 |

## Code this batch required (Runbook B widening — same shape as the Dublin/SG batches)
- `registry_sources.py`: added the `XX-GB` **destination-coverage** corridor and 5 UK `RegistrySource`
  entries (SRA, ICAEW, FCA, GIAS, ARLA — all HTTP_LISTING tier 2 with a per-entity `entry_url_pattern`).
  Movers reuse the existing global FIDI source (`corridors=CORRIDORS` now includes `XX-GB`).
- `backend/imports/suppliers/parsers.py`: 5 domain→source rows (`sra.org.uk`, `icaew.com`,
  `fca.org.uk`, `get-information-schools.service.gov.uk`, `propertymark.co.uk`).
- `test_vendor_harvester.py`: pairs-in-scope 36 → 42 (7 corridors × 6 categories).

## Load record (Runbook B)
```
read_csv + vendor_harvester.validate   -> 27/27 validate, country_code=GB
stage(dry_run=False)                    -> 6 runs, 24 new + 3 already-held, 0 rejects
promote(run_ids=<those>, dry_run=False) -> promoted 27, skipped 0, problems 0
verify: suppliers 207->233 (+26); capabilities +27, all 'pending'; approved caps unchanged (130->130)
```

**Honest rejects (subagent):** dropped EY Frank Hirth (ICAEW page JS-rendered, identity unconfirmable),
Chestertons + a legacy Hamptons branch (Propertymark slug 404 / sales-only), and Dartford/Croydon
"London" movers — rather than guess.

**Gate remaining (human):** vet each at `/admin/vetting-queue`; nothing is served to an employee until
`platform_vetting_status='approved'` and HR-curated. Code lands via PR (founder merge).
