# Paris providers — NO→FR (Denis), 2026-08-30

Otto-sourced vendor batch for the Norway→Paris corridor's destination city, driven from the Paris
register preflight. Delivered as a 9-column CSV to GCS; pulled and verified by Claude Code.

## Files
- `providers.csv` — 29 providers across all 6 live categories.
- `rejects.csv` — firms Otto considered and dropped, each with a reason.
- `manifest.json` — Otto's per-category records (wrapped with `batch_id` for the repo batch gate; the original is under `otto_manifest`).

## What lands (25/29) — stronger provenance than Dublin
Most French registers expose **per-entity URLs**, so these land with a real `entry_url_pattern`
(not `PUBLIC_REGISTER`); only the Barreau is search-only.

| category | n | register | provenance |
|---|---|---|---|
| banks | 5 | REGAFI / ACPR (`?…id_referentiel=…`) | per-entity, tier 2 |
| schools | 6 | annuaire-education (`/etablissement/…`) | per-entity, tier 2 |
| tax_finance | 5 | Ordre des Experts-Comptables (`/expert-comptable/…`) | per-entity, **tier 1** |
| housing_agencies | 4 | FNAIM (`/agence-immobiliere/…`) | per-entity, tier 2 |
| movers | 2 | CSD (`/annuaire-demenageurs/…`) | per-entity, tier 2 |
| legal_admin | 3 | Barreau de Paris (`/annuaire`) | PUBLIC_REGISTER (tier 2, claimed) |

## Re-source worklist (4) — do NOT land as-is
- **1818 Immobilier** — cites the FNAIM *listing* page, not a per-agency record.
- **AGS France · Santa Fe · Gosselin** (movers) — cite `fidi-france.com/fidi-france` (a bare
  page → SELF_DECLARED). Re-source to their `fidi.org/find-fidi-affiliate/<firm>` records.

## Gate / reproduce
```bash
python - <<'PY'
from pathlib import Path
from backend.imports.suppliers.parsers import read_csv
from backend.app.services.vendor_harvester import validate, HarvestRejected
ok=fail=0
for c in read_csv(Path("docs/imports/no-fr-paris-providers-2026-08-30/providers.csv")):
    try: validate(c); ok+=1
    except HarvestRejected: fail+=1
print(ok, "land /", fail, "re-source")   # 25 / 4
PY
```
Nothing reaches an employee until admin-vetted (`platform_vetting_status='approved'`) and
HR-curated. Note: Otto flagged REGAFI as a JS-rendered SPA — the per-firm `id_referentiel` URLs are
real and citable, and the CIB codes were cross-confirmed; the human vetter is the existence check.
