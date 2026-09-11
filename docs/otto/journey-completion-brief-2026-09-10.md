# Otto × Claude Code brief — Complete the four demo journeys (round-trip)

**Authored by Claude Code, 2026-09-10.** Otto executes the research packages; Claude Code owns every
line of code, every loader, every DB write, every review. This brief is the standing spec both sides
read. It extends `docs/otto/andrea-denis-brief-2026-08-21.md` to **all four demo movers**, the **full
round-trip** (home-exit → settled → return), and the missing settle-in services found in the
Sept-2026 journey gap analysis.

Goal: make **Andrea, Denis, Adrien, Abraham** walk a *complete* journey with no dead-ends — every
step backed by corridor content that is candidate-only until a human approves it.

---

## 0. How we work together — hand in hand, in tandem

The two never wait on each other. The **file contract is the sync point**; the **AI Work Queue is
the shared board**. Each work-package is one baton:

1. **Otto** researches → drops a batch under `docs/imports/<batch-id>/` (facts NDJSON / resource
   bundle / vendor CSV + manifest, §3) and flips its Notion row `Otto ready → In progress`.
2. **Claude Code** picks it up the moment it lands → runs the gate → **pass:** loads as candidate,
   wires the serving surface / flips the tile, validates the piece, moves the row to Human Review.
   **fail:** returns the batch to Otto with the *exact* gate error (loud refusal); the row goes back
   to `Otto ready`. **A returned batch is Otto's to fix, never Claude Code's to reconcile away.**
3. **A human reviewer** approves the candidate → it goes live. Neither side self-approves.

**Pipelining (this is what "in tandem" means):**
- Claude Code builds the reusable wiring (new service categories, tiles, the return module)
  *concurrently* with Otto's first Andrea research batches — neither blocks the other.
- Otto stays **one corridor ahead**: while Claude Code loads + wires + authors corridor N, Otto is
  already researching corridor N+1. Reference-first keeps this balanced — after Andrea, Claude Code's
  per-corridor work shrinks to *load + author*.
- Within a corridor, the 12 packages fan out: Otto can research the vendor/resource batches
  (P2–P9) in parallel with the P1 facts; Claude Code gates and loads each as it lands.

Otto never writes code, a migration, the database, or a review status. Otto never emits
`fact_type:"step"` (steps are the roadmap graph Claude Code owns). Everything Otto delivers is
`pending`/`draft`/`candidate`.

## 1. The four movers

| | **Andrea** | **Denis** | **Adrien** | **Abraham** |
|---|---|---|---|---|
| Corridor | ES→IE (Madrid→Dublin) | NO→FR (Norway→Paris) | FR→SG (Paris→Singapore) | US→EC (Seattle→Quito) |
| Nationality | Venezuelan — third-country | French — EEA own-national | French — third-country into SG | US — third-country into EC |
| `applies_to.nationality` | `non-EEA` | `EEA` | `non-EEA`¹ | `non-EEA`¹ |
| Legal shape | Critical Skills permit (CSEP) | EEA free-mover | Employment Pass (work pass) | Professional residence visa |
| Return corridor | IE→ES / IE→VE | FR→NO | SG→FR | EC→US |

¹ SG and EC do not use the EU/EEA construct. Scope destination facts to the audience the obligation
governs and map to the closest vocab value **following the precedent of the already-delivered
`fr-sg-facts-2026-08-30` / `sg-ec-browser-grounded-*` batches**; a French/US national is
`THIRD_COUNTRY` from the destination's perspective. When in doubt, `needs_lawyer_review:true`.

## 2. What already exists (build only the delta)

All fact content below is DELIVERED-but-`pending` (candidate). Do **not** re-deliver it; extend it.

| | Andrea ES→IE | Denis NO→FR | Adrien FR→SG | Abraham US→EC |
|---|---|---|---|---|
| Corridor profile | ✅ full + CSEP pathway + `facts.yaml` | ✅ full + EEA pathway + `facts.yaml` | 🟡 `corridor.yaml` only — **no pathway, no facts.yaml** | 🟡 `corridor.yaml` only — **no pathway, no facts.yaml** |
| Immigration / visa | ✅ `es-ie-thirdcountry-*`, `ve-ie-entry-family-*`, `es-ie-family-reunification-*` | ✅ (light by design) | ✅ EP/COMPASS/S-Pass/PEP (`fr-sg-facts-*`) | ✅ residence visa + tourist-trap |
| Destination reg / tax / health | ✅ IRP, PPSN, Revenue, GP | ✅ préfecture, PAS, CPAM | 🟡 reg ✅, **tax = 1 fact (IRAS hole)**, health 🟡 | ✅ cédula, RUC/SRI, IESS |
| Core vendors (movers/housing/bank/legal) | ✅ `es-ie-dublin-providers-*` | ✅ `no-fr-paris-providers-*` | ✅ `fr-sg-providers-*` | 🟡 movers 1 + housing 4; **banks/schools/legal/tax blocked = 0** |
| Origin-departure | 🟡 `es-facts-2026-08-31` (**HELD**, 16) | 🟡 4 in facts.yaml + 3 held + transition (3/15 verified) | ❌ none | ❌ none |
| Overnight consolidated facts | ✅ `corridor-facts-2026-09-08` (all 4 corridors, applied `pending`) | ✅ same | ✅ same | ✅ same |
| Reference-data (ISD visa list) | ✅ `ie-isd-visa-required-*` | ❌ | ❌ | ❌ |

**Absent for all four (the journey-completion delta this brief requests):** temp/serviced housing,
GP/medical directories, driving-licence exchange, language schools, dual-career (spouse *job*
placement), storage, pre-departure health resources, return/repatriation facts, RAG corpus,
document-extraction reference. Adrien and Abraham additionally need the whole origin side + pathway.

## 3. The delivery contract (read once; every §4 package depends on it)

Four deliverable shapes. Pick the shape named in each package. **All land candidate-only.**

### 3.A — Requirement FACTS  → `docs/imports/<batch-id>/` = `<batch-id>.ndjson` + `manifest.json` + `README.md`
One JSON object per line. Required: `destination_country` (ISO-2), `entity_topic_key` (snake_case),
`fact_key` (globally unique, corridor-prefixed, **stable across re-deliveries**), `fact_text`,
`source_url` (**official host** — §3.E), `evidence_quote` (verbatim, ≥25 chars),
`fact_type` (`eligibility|document|deadline|fee|where_to_apply|other` — **never `step`**),
`confidence` (`high|medium|low`), and the make-or-break `applies_to`:
```jsonc
"applies_to": {
  "nationality": "non-EEA",          // EEA|EU|non-EEA|non-EU — NEVER null (§3.F)
  "status": "professional",          // professional|student|family|any
  "pillar": "RESIDENCE",             // RESIDENCE|IDENTITY|EMPLOYMENT|HOUSING|SOCIAL_SECURITY|HEALTHCARE
  "non_obvious": true, "non_obvious_note": "Commonly believed … Actually … Action required …",
  "needs_lawyer_review": false, "quote_verbatim_confirmed": false, "corridor": "ES->IE"
}
```
Manifest: `batch_id` (== dir name), `corridor`, `origin_country_code`, `destination_country_code`,
`nationality_class` (`OWN_NATIONAL|EU_EEA|THIRD_COUNTRY`), `target_table:"public.requirement_items"`,
`record_count`, `non_obvious_count`, `needs_lawyer_review_count`, `artifact`, `sha256` (of the
ndjson bytes), `review_status_all:"pending"`, `verification_status_all:"representative"`, `scope`.
- **Gate:** `python scripts/check_otto_batches.py <batch-id>` (sha256 + counts reconcile, unscoped
  topics empty, no served status). **Load (CC):** `python scripts/import_otto_facts.py <batch>
  [--apply --promote]`. **Parser:** `backend/imports/otto/parsers.py`; refusal logic
  `backend/imports/otto/mappings.py`. **Serving:** approved rows → `requirements_builder.py`.

### 3.B — RESOURCES (guides / checklists / destination content)  → JSON `ImportBundle`
Schema `backend/imports/resources/schemas.py`: `{categories, tags, sources, resources, events}`.
`ImportResource` keys: `country_code`, `city_name`, `category_key` (∈ `admin_essentials, housing,
schools, healthcare, transport, daily_life, community, culture_leisure, safety, cost_of_living`),
`title`, `resource_type` (∈ `guide, checklist_item, official_link, tip, provider…`), `summary`,
`body`, `source_url`, `source_name`, `tags[]`, `status`.
- **Loader (CC):** `python scripts/import_resources.py --bundle <path> --mode draft_only`
  (**forces `status=draft`, invisible**). Gate: `backend/imports/resources/validators.py`. Fixtures
  live under `backend/imports/resources/fixtures/` (not `docs/imports/`). **Serving:** only the
  `published_country_resources` view. Deliver a JSON bundle + a one-page README under
  `docs/imports/<batch-id>/` for the audit trail; Claude Code places the bundle in fixtures.

### 3.C — VENDOR / PROVIDER directories  → `docs/imports/<corridor|XX>-<city>-providers-<date>/`
= `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`. **9-column CSV, fixed header**
(`backend/imports/suppliers/parsers.py`): `corridor, service_category, company_name, website_url,
source_name, source_url, accreditation_body, accreditation_number, accreditation_expiry`.
- Source tier is decided by the **evidence-URL domain**, not `source_name`; a provider's own site is
  tier-3 and insufficient — cite an official register or accreditor. Manifest = per-category
  self-assessment (`register, denominator, accepted, rejected, confidence, notes`) + `files{}` with
  sha256. **Loader (CC):** `python scripts/import_supplier_candidates.py <csv> [--apply --promote]`
  → `suppliers` at `platform_vetting_status='pending'` → `/admin/vetting-queue`; **served only when
  `approved`.** New `service_category` + corridor scope added to `backend/app/services/registry_sources.py`.

### 3.D — REFERENCE-DATA lookups (visa-required lists etc.)  → JSON artefact + `manifest.json`
`manifest.target_table:null` (**never promoted**), `verification_status:"representative"`,
`review_status:"pending"`; integrity test à la `backend/tests/test_isd_visa_required.py`. Read at
request time (`services/isd_visa_required.py`). Use only when a corridor needs an assertable lookup.

### 3.E — Official publishers only (host decides trust)
IE: `irishimmigration.ie`, `gov.ie`, `revenue.ie`, `citizensinformation.ie`. ES: `*.gob.es`,
`seg-social.es`, `agenciatributaria.es`, `sepe.es`, `madrid.es`. NO: `udi.no`, `skatteetaten.no`,
`nav.no`, `politiet.no`, `folkeregisteret.no`. FR: `service-public.fr`, `impots.gouv.fr`, `urssaf.fr`,
`ameli.fr`, `france-visas.gouv.fr`, `ofii.fr`. SG: `mom.gov.sg`, `ica.gov.sg`, `iras.gov.sg`,
`cpf.gov.sg`, `mas.gov.sg`. EC: `*.gob.ec`, `cancilleria.gob.ec`, `sri.gob.ec`, `iess.gob.ec`. US
(departure): `irs.gov`, `ssa.gov`, `travel.state.gov`, the state DOR. **UNOFFICIAL (blog, law firm,
vendor) is rejected and the fact is lost.**

### 3.F — Honesty rules (mirror the platform's own guardrails)
Never null/guess `applies_to.nationality`. A universal obligation (e.g. municipal registration) is
delivered as **two records**, one `EEA` and one `non-EEA`. No fabricated number/fee/deadline/citation
— absent stays absent. Every `fact_text` is backed by an `evidence_quote`. `needs_lawyer_review:true`
for any legal/tax *determination* (treaty tie-breakers, residence-status conclusions), not a
published procedural rule. Never set a served status.

## 4. The work packages

Format per package: **Goal / Spec / Deliverable / Acceptance / Reuse (Claude Code wiring)**.
Reference-first: **§4.A builds every package type fully for Andrea; §4.R replicates to the others.**

### 4.0 — Reusable Claude Code wiring (built once, during Andrea; reused by all corridors)

Not Otto work — listed so both sides see the whole loop:
- Add service categories `temp_accommodation, medical, language, spouse, storage, tax_finance,
  drivers_license` to `backend/app/services/registry_sources.py` + question blocks in
  `backend/app/services/question_schema.py` + mappings in `criteria_builder.py SERVICE_KEY_TO_BACKEND`.
- Flip the `enabled:false → true` tiles in `frontend/src/features/services/serviceConfig.ts`
  (with `backendKey`).
- Build the **return/repatriation module**: a `Phase.REPATRIATION` phase in `roadmap_builder.py`
  + reverse-corridor requirement serving. Any new router registered in **both** `backend/main.py`
  **and** `backend/app/main.py`; any new `public` table gets RLS + policy + `REVOKE ALL … FROM anon`.

### 4.S — First-pass scope & correctness notes

- **Journey-blocking first, polish second.** For the first complete demo, prioritise the 9
  journey-blocking packages (P1–P7, P9, P10). Treat **P8 storage** (usually a capability flag on a
  mover, not a separate service), **P11 RAG corpus** and **P12 doc-extraction reference**
  (answer-quality / OCR, not walk-through-blocking) as a fast-follow Phase 2.
- **Return is a skeleton, not outbound parity.** P10 delivers the 4–6 highest-value return facts per
  corridor (host de-registration, host tax exit, home re-registration, social/pension switch-back) —
  not a mirror of the full outbound set.
- **Never flip a tile onto an empty state.** Claude Code enables a service tile only once ≥1 approved
  vendor exists for the destination — reuse the existing `requiresCuration` pattern already applied to
  Pets in `frontend/src/features/services/serviceConfig.ts`. Until then the category is scaffolded but
  the tile stays "coming soon".
- **A-P1 is reconcile-first.** Spain-departure `es-facts-2026-08-31` is HELD, not missing: Claude Code
  reconciles/loads it; Otto only re-delivers facts that fail the gate or are needed to reach ≥6.
- **Language (P6) is family-scoped where the mover already speaks the destination language** (Denis →
  French is for the accompanying spouse, not Denis).

### 4.A — ANDREA (ES→IE, `non-EEA`) — the gold template

**A-P1 · Complete Spain-departure obligations.** *Goal:* the exit side, currently only HELD.
*Spec:* build on `es-facts-2026-08-31` (16, HELD); topics — baja del padrón, Seguridad Social baja /
posted-worker A1 if on an ES contract, AEAT tax-exit / non-resident transition. Sources: AEAT,
seg-social.es, the ayuntamiento. `non-EEA`, `professional`. *Deliverable:*
`docs/imports/es-departure-2026-09-10/` (facts). *Acceptance:* gate passes, 100% promote, reconciles;
≥6 official-sourced facts. *Reuse:* CC loads → `requirement_items`; binds `ES_IE/facts.yaml
origin_facts`; surfaces in the pre-departure roadmap track.

**A-P2 · Dublin pre-departure health resources.** *Spec:* a resource bundle (§3.B) — recommended
vaccinations, carrying medical records/prescriptions, proof-of-insurance for entry, GP transfer.
Sources: HSE/citizensinformation.ie. *Deliverable:* `docs/imports/ie-predeparture-health-2026-09-10/`
(JSON bundle + README). *Acceptance:* `validate_bundle` passes; all `resource_type` ∈ vocab.
*Reuse:* CC imports `--mode draft_only`; publishes after review; adds a pre-departure health step.

**A-P3..P9 · Dublin settle-in vendor directories** (each a §3.C CSV batch under
`docs/imports/es-ie-dublin-<svc>-2026-09-10/`):
- **A-P3** temp/serviced housing · **A-P4** GP/medical clinics accepting new arrivals ·
  **A-P6** language schools (English, for the VE spouse) · **A-P7** dual-career / spouse-employment ·
  **A-P8** storage · **A-P9** tax advisors (top up).
- *Spec (each):* 4–6 firms, official-register/accreditor evidence URL, 9-column CSV. *Acceptance:*
  `import_supplier_candidates.py --dry-run` clean, ≥3 pass the provenance gate per category.
  *Reuse:* CC adds the `service_category` to `registry_sources.py`, loads to `pending`, flips the tile.

**A-P5 · IE driving-licence exchange facts.** *Spec:* NDLS exchange rules for ES and VE licence
holders — reciprocity, deadline from residence, whether a test is required; `domain_area:vehicle`,
`non-EEA`, scoped by origin licence. Source: ndls.ie/citizensinformation.ie. *Deliverable:*
`docs/imports/ie-driving-licence-2026-09-10/`. *Acceptance:* gate passes; each fact cites the source.
*Reuse:* CC loads; `transport` plugin surfaces the `drivers_license` tile.

**A-P10 · IE→ES/VE return facts (reverse corridor).** *Spec:* the return move — close IRP/Revenue
in IE, Irish tax-residence exit, PPSN retention, re-entry/re-registration in ES (empadronamiento,
Seg-Social) and the VE consular route. `non-EEA`, `professional`; `needs_lawyer_review` on any tax
tie-breaker. *Deliverable:* `docs/imports/ie-es-return-2026-09-10/` (destination = ES/VE).
*Acceptance:* gate passes; return topics distinct from outbound `fact_key`s. *Reuse:* CC serves it in
the `Phase.REPATRIATION` roadmap phase (built in §4.0).

**A-P11 · ES→IE RAG corpus.** *Spec:* clean full text of the 8–12 Tier-1 pages the IE facts cite,
one doc per source + url + retrieved_at + publisher (Andrea's `corridor.yaml` flags none exist).
*Deliverable:* `docs/imports/es-ie-corpus-2026-09-10/`. *Reuse:* CC indexes into
`immigration_corpus_chunks` for `ES_IE`.

**A-P12 · Document-extraction reference.** *Spec:* labelled field/layout patterns of an IE/EN
employment contract and a Spanish TIE card — **no real PII**. *Deliverable:*
`docs/imports/es-ie-doc-reference-2026-09-10/`. *Reuse:* CC adds an IE/EN locale to
`employment_contract.py` + routes the TIE.

### 4.R — Replicate the package set to Denis, Adrien, Abraham

Same P1–P12, re-scoped. Only the deltas differ:

| Package | Denis NO→FR (EEA) | Adrien FR→SG (`non-EEA`¹) | Abraham US→EC (`non-EEA`¹) |
|---|---|---|---|
| **P1 origin-departure** | Complete the 3 held NO candidates + **verify** `no-fr-transition-requirements` quotes (3/15 today); folkeregister move-abroad, folketrygden exit, skattekort, A1-by-URSSAF, "preserve BankID" trap | **NEW** France-departure: impôts/PAS exit, CPAM/URSSAF, A1 for SG posting or totalization | **NEW** US-departure: state tax-residency exit, IRS (FEIE/FBAR context), **no US–EC totalization treaty** as an explicit fact |
| **Pathway + facts.yaml** | exists — skip | **CC AUTHORS** `corridors/FR_SG/pathways/*` + `facts.yaml` from delivered facts | **CC AUTHORS** `corridors/US_EC/pathways/*` + `facts.yaml` |
| **Fill known holes** | docs live under reverse `fr-no/` only | **TAX** (only 1 fact; IRAS mega-menu) — priority; housing-rental; FR→SG totalization | Providers **blocked** (banks/schools/legal/tax = 0) → **browser-grounded** sourcing; IESS rates, income-tax brackets, treaty facts |
| **P6 language** | French | English | Spanish |
| **P3/P4/P7/P8/P9 vendors** | Paris | Singapore | Quito (browser-grounded where registers are blocked) |
| **P10 return** | FR→NO | SG→FR | EC→US |
| **P11 corpus / P12 doc-ref** | NO→FR corpus; FR contract + titre de séjour | FR→SG corpus; SG EP card | US→EC corpus; EC cédula/visa |

**Sequencing:** Andrea (all 12 + all §4.0 wiring) → Denis → Adrien (+ pathway authoring) → Abraham
(+ pathway authoring + unblock providers). Otto starts the next corridor's P2–P9 vendor/resource
batches while Claude Code is still loading the previous corridor's facts (§0 pipelining).

## 5. Metrics & evals (per batch, in the README; re-checked by Claude Code)

| Metric | Target | How |
|---|---|---|
| Promote rate (facts) | 100% | `import_otto_facts.py` dry-run: 0 `Unmapped` |
| Correctly nationality-scoped | 100% | §3.F self-audit + `overserved_requirements` eval stays 0 (EEA never sees third-country content, vice-versa) |
| Manifest reconciliation | exact | sha256 + counts match |
| Citation resolves | ≥95% | every `source_url` fetched; a dead link fails |
| Zero fabrication | 100% | every `fact_text` has a supporting `evidence_quote` |
| Vendor provenance | ≥3/category pass | `import_supplier_candidates.py` dry-run tier check |

**Demo "done" per persona:** roadmap spans pre-departure (origin obligations + health) →
arrival/settle (temp housing, medical, driving, language, spouse, storage, tax) → **return** phase,
no dead-ends; FR_SG and US_EC load a pathway + `facts.yaml`; all content correctly nationality-scoped
and still `pending`/`draft`/`candidate` until reviewed.

## 6. Validation pipeline (Claude Code side, per batch)

1. **Gate** — `scripts/check_otto_batches.py <batch>` (facts) / `validators.py` (resources) /
   `vendor_harvester.validate` (vendors). Fail → return to Otto with the exact error.
2. **Load as candidate** — `import_otto_facts.py --apply` / `import_resources.py --mode draft_only` /
   `import_supplier_candidates.py --apply`.
3. **Promote to `pending`** (facts) — into `requirement_items`, never past `pending`.
4. **Wire** — bind `facts.yaml`, author pathways (FR_SG/US_EC), add service category + flip tile,
   index corpus, add extractor locale, build the return phase. `tsc --noEmit` + `vitest` green;
   `python3 -c "from backend.main import app; ..."` shows any new route.
5. **Review & approve** — human gate; counsel-flagged rows wait for the assurance model.

## 7. Notion mapping (AI Work Queue — the shared board)

DB `3bc887c6-4d48-8089-8188-fcf2dc3edc1b`. One row per package (`<persona>-P<n>`), fields:
`Assigned = Claude Cowork` (Otto research) · `Task Type = Research` · `Autonomy Tier = 🔴 Red — full
human gate` (research feeding served content is never auto-approved) · `Test Command =
python scripts/check_otto_batches.py <batch-id>` (facts) or the loader dry-run (resources/vendors).
The wiring half of each package is a paired dev-lane row (`Assigned = Claude Code`). A package is
`Done` only when **both** rows are.

## 8. Guardrails — what Otto must never do

- Never write code, a migration, the database, or a review status. Deliver files.
- Never null or guess `applies_to.nationality`. Read it from the fact; a universal obligation is two
  records.
- Never emit `fact_type:"step"` — steps are the roadmap graph Claude Code owns.
- Never invent a source, number, fee, deadline, or confidence. Absent stays absent.
- Never set a served status (`approved`/`published`/`verified`/`live`). Everything is
  `pending`/`draft`/`candidate`.
- Never merge to `main` or promote past candidate.
