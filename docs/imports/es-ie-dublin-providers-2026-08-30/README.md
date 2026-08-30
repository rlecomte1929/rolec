# Dublin providers — ES→IE (Andrea), 2026-08-30

Otto-sourced vendor batch for the Madrid→Dublin corridor's destination city, driven from the
Dublin **register preflight** (Otto identified the authoritative Irish register per category, then
sourced firms from each). Delivered as a 9-column CSV to GCS; pulled and verified by Claude Code.

## Files
- `providers.csv` — 17 providers across all 6 live categories.
- `rejects.csv` — firms Otto considered and dropped, each with a reason.
- `manifest.json` — Otto's per-category counts + self-assessment.

## What landed (17/17)
| category | n | register cited | tier |
|---|---|---|---|
| movers | 2 | FIDI FAIM affiliate (per-entity URL) | 1 |
| legal_admin | 2 | Law Society of Ireland — Find a Solicitor | 2 |
| tax_finance | 1 | CPA Ireland firm directory | 2 |
| banks | 5 | Central Bank Register of Authorised Firms | 2 |
| schools | 3 | Tusla Register of Independent Schools | 2 |
| housing_agencies | 4 | PSRA Register of Licensed Property Services Providers | 2 |

## The provenance decision (Option C, founder-approved 2026-08-30)
Only the 2 movers cite a **per-entity** register URL (FIDI). The other 15 firms are real and on
their statutory register, but those registers (Law Society, CPA, Central Bank, Tusla, PSRA) expose
**no per-entity URL** — only a search form or flat page. The vendor gate normally rejects such rows
("a search page evidences nobody").

Decision: admit permalink-less **statutory** registers as a new `Acquisition.PUBLIC_REGISTER`
(tier 2), staged `claimed` and **pending** in `/admin/vetting-queue`, where a human confirms each
firm against the register. All 17 land as candidates for admin vetting; none is served to an
employee until vetted (`platform_vetting_status='approved'`) and HR-curated. See
`backend/app/services/registry_sources.py` (`PUBLIC_REGISTER` docstring) and the 5 Irish
`RegistrySource` entries.

## Otto's honest rejects (quality signal)
Otto correctly excluded **Ulster Bank** and **KBC** (both exited the Irish retail market), UK/US-
addressed "Ireland" movers, FIDI pages returning 404, and JS-rendered directory firms it could not
confirm — rather than inventing coverage.

## Gate / reproduce
```bash
python - <<'PY'
from pathlib import Path
from backend.imports.suppliers.parsers import read_csv
from backend.app.services.vendor_harvester import validate
rows = list(read_csv(Path("docs/imports/es-ie-dublin-providers-2026-08-30/providers.csv")))
for c in rows: validate(c)          # all 17 pass
print(len(rows), "providers validate")
PY
```
Promotion to prod (`vendor_candidates` → `suppliers`, `platform_vetting_status='pending'`) is the
opt-in `scripts/import_supplier_candidates.py … --apply --promote` step — a human/prod action.
