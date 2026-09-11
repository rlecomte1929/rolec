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

## Landed (candidate-only) — 33 batches, 201 items — all 4 personas complete

*(21 in the first pull below + 4 Denis packages recovered via Otto's GCS listing + 4 Abraham
US→EC vendor batches completed from Otto's metadata re-run — see the two sections before "Deferred".)*

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

### Denis NO→FR — recovered via GCS listing (2026-09-11)

Otto's `list_media` (100-item cap) recovered 14 of Denis's ~28 files; these 4 complete packages
are staged. Bundle sha256 for D-P2 matches Otto's stated hash (`c809e876…310b8ce9`).

| Batch | Type | Content |
|---|---|---|
| no-fr-predeparture-health-2026-09-10 (D-P2) | resource bundle (draft) | 8 resources (EHIC/S1, CPAM/PUMa, médecin traitant) |
| no-fr-paris-language-2026-09-10 (D-P6) | vendor | 6 accepted (Label FLE) / 4 rejects |
| no-fr-paris-dual-career-2026-09-10 (D-P7) | vendor | 5 accepted (SIRENE) / 5 rejects |
| no-fr-paris-medical-2026-09-10 (D-P4) | vendor | **honest-zero** (0 / 2 rejects) — ameli/Ordre annuaire is JS/SPA |

Still missing (beyond the 100-item listing window) — a targeted Otto re-run is queued:
**D-P1** no-departure (14 facts), **D-P10** fr-no-return (9 facts), **D-P3** no-fr-paris-temp-housing,
**D-P5** no-fr-driving-licence. The two facts packages are the priority — Denis has no departure/return
facts landed until they arrive.

### Abraham US→EC — vendor batches completed (2026-09-11, metadata re-run)

Otto regenerated rejects/manifest/README from the existing `providers.csv` (task #134438). Every
`providers.csv` / `rejects.csv` / `README.md` sha256 matches the value Otto stated **and** the value
declared inside each manifest; the manifest's own `sha256.manifest` is a self-hash (blanked-field
canonical form), so it is not a raw-bytes match by design. Manifest schema is leaner than §3.C
(`slug` + `providers_count`, no per-category self-assessment) — noted for the reviewer; the vendor
loader reads `providers.csv`, not the manifest.

> **Gate fix applied.** Otto's re-run manifests carried the batch id under `slug` and omitted the
> contract's `batch_id`, so `scripts/check_otto_batches.py` failed ("manifest batch_id matches the
> directory name — None"). A `batch_id` key equal to the directory name (the value already present as
> `slug`) was added to each of the 4 manifests — a mechanical normalization, no content changed;
> providers/rejects/README stay byte-identical and sha-verified. Consequence: the manifest's own
> `sha256.manifest` self-hash is now stale (it covered the pre-normalization bytes). **Feedback for
> Otto:** the metadata-regen path should emit `batch_id` (= dir name), not `slug`, or every future
> vendor batch from it will fail this gate.

| Batch (slug) | Accepted | Rejects | Note |
|---|--:|--:|---|
| ec-quito-temp-housing-2026-09-10 (AB-P3) | 0 | 5 | **honest-zero** — EC registers WAF/JS-blocked |
| ec-language-2026-09-10 (AB-P6) | 1 | 4 | Escuela de Español UDLA (SACIC) |
| ec-quito-dual-career-2026-09-10 (AB-P7) | 4 | 4 | ICF coach profiles |
| ec-quito-core-providers-2026-09-10 (AB-CORE) | 10 | 5 | 5 banks + 5 legal |

*(Corrupted superseded AB-CORE rejects upload `1789155493577_2e2p19cr.csv` was ignored per Otto's
flag; the byte-perfect `1789155617167_a7kffdbu.csv` is used.)*

## Deferred to the load step (needs backend venv + DB, out of this PR's scope)

- `scripts/import_otto_facts.py <batch> --dry-run` → `--apply --promote` (facts → `requirement_items`, `pending`).
- `scripts/import_supplier_candidates.py <csv>` dry-run/apply (vendors → `suppliers`, `pending`). *(loader needs `sqlalchemy`; not installed here.)*
- `scripts/import_resources.py --bundle <path> --mode draft_only` (resources → `country_resources`, draft). Full validation resolves platform categories/tags against Supabase, unavailable here.
- ✅ **Pathway graphs AUTHORED** (Notion AB-WIRE / AD-WIRE): `corridors/FR_SG/pathways/EMPLOYMENT_PASS_2026/v1.yaml`
  and `corridors/US_EC/pathways/PROFESSIONAL_RESIDENCE_2026/v1.yaml`, sourced from the corridors'
  reviewed/representative `requirement_items` + the delivered facts, wired into each `corridor.yaml`
  (derived SLA windows: FR_SG 50d, US_EC 36d). Load cleanly (no cycles, one arrival anchor each);
  `test_corridor_pathways` + `test_corridor_cycle_detection` + `test_corridor_sla` + `test_corridor_feasibility`
  pass. Still deferred: each corridor's **`facts.yaml`** (fact→step binding) — its refs resolve only
  after the facts load, so authoring it now would invent refs.

## Outstanding — needs Otto (not recoverable in-repo)

- **Denis NO→FR — 6 of 8 packages landed; 2 facts batches returned to Otto.** Landed: D-P2 health,
  D-P4 medical (honest-zero), D-P6 language, D-P7 dual-career (from the listing) + **D-P3
  no-fr-paris-temp-housing** (4 accepted/2 rejects) and **D-P5 no-fr-driving-licence** (7 resources,
  from the re-run #134437, content sha256-verified, `batch_id` normalized).
  - **D-P1 `no-departure-2026-09-10`** (16 facts) and **D-P10 `fr-no-return-2026-09-10`** (12 facts)
    initially failed the evidence-citation gate (7 source_urls were homepages/language-roots) and were
    returned to Otto. **Now RESOLVED:** Otto re-sourced all 7 with deep links that state the rule, each
    carrying a fresh verbatim `evidence_quote`; fact_keys unchanged. Re-pulled, all 6 files
    sha256-verified, 0 offending source_urls, gate PASS — **landed** (batch_id normalized). Denis is
    complete (8/8 packages).
- **Abraham US→EC vendor batches — RESOLVED (#134438).** Metadata re-run delivered full filenames;
  all 4 batches completed and landed (see the Abraham vendor section above). No longer outstanding.
- **Abraham Job C (#134263)** — all honest-zeros (Quito registers WAF/JS-blocked); no content to load.

## Honest-zeros to retry (registers were offline/blocked at research time)

Dublin dual-career, Dublin tax-advisors, and the Quito provider set — re-run when CAI/ITI
Find-a-Firm and the EC registers are reachable (needs a headless browser).
