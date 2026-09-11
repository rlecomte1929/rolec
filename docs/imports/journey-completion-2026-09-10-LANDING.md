# Journey-completion batches — GCS landing record (2026-09-10 batch set)

**Landed by:** Claude Code, 2026-09-11, from Otto's Audos task outputs (#134003 / #134016 /
#134224 / #134116 / #134210 / #134243 / #134263). **Scope of this PR: stage + gate only —
candidate artifacts committed to the repo. No production DB writes.**

## Why this exists

The 34 journey-completion research packages (`docs/otto/journey-completion-brief-2026-09-10.md`)
showed `Otto ready` in Notion and had nothing under `docs/imports/`, so they looked un-started.
They were not: Otto ran them and stored the deliverables to **GCS only** (the prompts correctly
instructed files-to-GCS, no repo writes), and the Notion→Audos bridge never synced the outputs
back. This record pulls those verified deliverables into the repo in the delivery-contract layout.

**Provenance.** All files pulled from the public GCS prefix:
`https://storage.googleapis.com/audos-images/workspace-media/d0c29613-9cb5-4652-9c6a-494eeed352e5/`
(objects are anonymously readable; the bucket denies anonymous listing, which is why Denis —
below — cannot be recovered here).

**Verification.** Every facts `*.ndjson` was re-hashed and **matches its manifest `sha256`**
(the gate's reconciliation), and `scripts/check_otto_batches.py <batch>` **PASSES** for all 7
facts batches. Everything is candidate-only: facts `review_status=pending` /
`verification_status=representative`, resources `status=draft`, vendors land at
`platform_vetting_status=pending`. **Nothing is served; the human lawyer gate at
`/admin/countries` (facts) and the vetting queue (vendors) remain.**

## Landed (candidate-only) — 21 batches, 128 items

### Requirement FACTS — 58 facts (39 non-obvious, 12 needs_lawyer_review), gate PASS

| Batch | Facts | non-obvious | lawyer | corridor | nationality |
|---|--:|--:|--:|---|---|
| es-departure-2026-09-10 (Andrea) | 9 | 7 | 1 | ES→IE | THIRD_COUNTRY |
| ie-es-return-2026-09-10 (Andrea) | 9 | 5 | 2 | IE→ES | THIRD_COUNTRY |
| fr-departure-2026-09-10 (Adrien) | 8 | 6 | 1 | FR→SG | EU_EEA |
| fr-sg-tax-2026-09-10 (Adrien) | 6 | 4 | 1 | FR→SG | THIRD_COUNTRY |
| sg-fr-return-2026-09-10 (Adrien) | 7 | 6 | 0 | SG→FR | THIRD_COUNTRY |
| us-departure-2026-09-10 (Abraham) | 10 | 7 | 5 | US→EC | THIRD_COUNTRY |
| ec-us-return-2026-09-10 (Abraham) | 9 | 4 | 2 | EC→US | THIRD_COUNTRY |

### RESOURCE bundles — 38 resources, all `status=draft`

| Batch | Resources | Category |
|---|--:|---|
| ie-predeparture-health-2026-09-10 (Andrea) | 6 | healthcare |
| ie-driving-licence-2026-09-10 (Andrea) | 5 | transport |
| sg-predeparture-health-2026-09-10 (Adrien) | 7 | healthcare |
| sg-driving-licence-2026-09-10 (Adrien) | 4 | transport |
| ec-predeparture-health-2026-09-10 (Abraham) | 9 | healthcare |
| ec-driving-licence-2026-09-10 (Abraham) | 7 | transport |

### VENDOR directories — 32 accepted providers (9-column contract header verified)

| Batch | Accepted | Rejects | Note |
|---|--:|--:|---|
| es-ie-dublin-temp-housing-2026-09-10 | 6 | 0 | Fáilte Ireland / Discover Ireland |
| es-ie-dublin-medical-2026-09-10 | 6 | 0 | HSE Find-a-GP |
| es-ie-dublin-language-2026-09-10 | 3 | 3 | TrustEd Ireland statutory list |
| es-ie-dublin-dual-career-2026-09-10 | 0 | 5 | **honest-zero** — ICF/EMCC/CRO JS/captcha-gated |
| es-ie-dublin-tax-advisors-2026-09-10 | 0 | 2 | **honest-zero** — ITI/CAI registers offline |
| fr-sg-singapore-temp-housing-2026-09-10 | 6 | 3 | HLB/STB Licensed Hotels register |
| fr-sg-singapore-medical-2026-09-10 | 6 | 3 | MOH CHAS register |
| fr-sg-singapore-dual-career-2026-09-10 | 5 | 3 | ACRA (UENs confirmed) |

## Deferred to the load step (needs backend venv + DB, out of this PR's scope)

- `scripts/import_otto_facts.py <batch> --dry-run` → `--apply --promote` (facts → `requirement_items`, `pending`).
- `scripts/import_supplier_candidates.py <csv>` dry-run/apply (vendors → `suppliers`, `pending`). *(loader needs `sqlalchemy`; not installed here.)*
- `scripts/import_resources.py --bundle <path> --mode draft_only` (resources → `country_resources`, draft). Full validation resolves platform categories/tags against Supabase, unavailable here.
- Author `corridors/FR_SG/` and `corridors/US_EC/` pathway graphs + `facts.yaml` from these facts (Notion AB-WIRE / AD-WIRE, currently Blocked).

## Outstanding — needs Otto (not recoverable in-repo)

- **Denis NO→FR (#134016) — 24 files exist on GCS but filenames were never captured.** The bucket
  denies anonymous listing, so they can't be recovered here. Requested from Otto: (a) GCS-listing
  by the ~07:10 UTC window cross-checked to the known D-P1 sha256 `3fcbe327…`, and (b) a re-run as
  fallback. Known content: D-P1 no-departure (14 recs), D-P10 fr-no-return (9), D-P2 health (8),
  D-P5 driving (6), D-P3 housing (4), D-P6 language (6), D-P7 dual-career (5); D-P4 medical honest-zero.
- **Abraham US→EC vendor batches — partial filenames only** (AB-P3/P6/P7/CORE providers captured,
  but rejects/manifest/README timestamps are partial). Requested from Otto: paste the full filenames
  (or GCS-list the #134224 `1789135…` and #134263 `178914[1|2]…` windows).
- **Abraham Job C (#134263)** — all honest-zeros (Quito registers WAF/JS-blocked); no content to load.

## Honest-zeros to retry (registers were offline/blocked at research time)

Dublin dual-career, Dublin tax-advisors, and the Quito provider set — re-run when CAI/ITI
Find-a-Firm and the EC registers are reachable (needs a headless browser).
