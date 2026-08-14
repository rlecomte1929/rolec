# ReloPass — Data Integration & RFQ Audit
**Date:** 2026-08-13 · **Corridor under test:** FR → NO (Paris → Oslo) · **Method:** production Supabase (read-only SQL) + repo code trace + static dataset inspection · **Project:** `nsvefcvpvwwwhuqyuqmp`

---

## 0. Executive answer

You asked three things. Short answers first.

**"Is the imported data integrated correctly?"**
Partially. The *vendor/supplier* chain (`suppliers → supplier_service_capabilities → service_catalog_items → company_vendor_selections → rfqs`) is referentially clean — zero orphans on every FK-equivalent join I tested. The *corridor/immigration knowledge* chain is not integrated: what you import into `corridors/**` is written to `rce.*` by a script that has never run in production, and the employee-facing requirements/roadmap surfaces read three entirely different tables fed by three unrelated pipelines.

**"Do users see the right information in the right place?"**
No — and this is the headline. **A French employee relocating to Oslo is currently shown Singaporean movers.** Across 128 distinct FR→NO cases, 1,170 of 1,817 movers-slate impressions (64%) were Singapore vendors and 151 were an Australian vendor. Most recent occurrence: **2026-08-12** — yesterday. This is live, not historical.

**"Test the RFQ process — for a given corridor, do we see the vendors HR approved and the employee picks from?"**
The HR-approval *gate* works as designed (strict allow-list, no fallback to the global catalog when HR has curated). But the gate is downstream of a candidate list that is not geo-filtered, and HR's own approvals are themselves geographically wrong: **all 177 companies with Norway curation have approved a Sydney, Australia mover as a Norway vendor.** So the answer to "do we observe the list of vendors HR is approving" is: yes, faithfully — and that list is wrong.

Additionally: **30 of 30 RFQs in production are stuck at `status='sent'`.** None has ever been validated or awarded. Only 9 quotes exist against 30 RFQs.

---

## 1. Findings, ranked by severity

### 🔴 F-1 — Employee vendor slates are not geo-filtered; Singapore seed data leaks into every corridor
**Severity: Critical · Live · User-visible · Affects all corridors**

`backend/app/recommendations/engine.py::_load_dataset_with_registry` builds the candidate list as:

```python
if registry_items:
    dataset = list(registry_items)          # geo-filtered — correct
    for d in static_dataset:                 # ← appended with NO geo check
        if iid and iid not in existing_ids and iid not in twin_ids:
            dataset.append(d)
else:
    dataset = list(static_dataset)           # ← 100% static when registry is empty
```

The static datasets in `backend/app/recommendations/datasets/` are Singapore demo seed data. **13 of 17 carry no `city` or `country` field at all**, so nothing can filter them:

| dataset | n | geo fields | example rows |
|---|---|---|---|
| `movers.json` | 10 | `service_areas` only | Asian Tigers, Shalom Movers, Movers.sg, JK Movers *(all SG)* |
| `banks.json` | 10 | **none** | DBS, OCBC, UOB, Citibank |
| `medical.json` | 10 | **none** | Raffles Medical, Mount Elizabeth, Gleneagles |
| `telecom.json` | 3 | **none** | Singtel, StarHub, M1 |
| `electricity.json` | 10 | **none** | SP Group, Tuas Power, Geneco, Senoko |
| `insurance.json` | 10 | **none** | AIA Singapore, Prudential |
| `tax_finance.json` | 2 | **none** | KPMG Singapore, Deloitte |
| `legal_admin.json` | 2 | **none** | Quahe Woo & Palmer, Dentons Rodyk |
| `transport.json` | 2 | **none** | ComfortDelGro Driving Centre, SSDC |
| `storage.json` | 2 | **none** | Lock+Store, Extra Space Asia |
| `childcare.json` | 3 | **none** | EtonHouse, Cherrybrook, MindChamps |
| `language_integration.json` | 2 | **none** | British Council Singapore, Inlingua |
| `housing_agencies.json` | 8 | ✅ `city` + `country` | Oslo Serviced Living, Nordic Stay… |
| `schools.json` | 32 | ✅ `city` | Oslo Int'l School, Tanglin Trust… |
| `living_areas.json` | 38 | ✅ `city` | Frogner, Grünerløkka, Tiong Bahru… |

`housing_agencies` is the control that proves the mechanism: it is the only vendor category with proper geo fields, and it is the only one that came back **100% correct** for FR→NO (Oslo Serviced Living, Nordic Stay Apartments, Frogner Rental Partners, Oslo Home Finders — 4/4 Oslo).

**Production evidence (FR→NO movers slates, `recommendation_slates`):**

| bucket | impressions | distinct cases | first served | last served |
|---|---|---|---|---|
| Singapore movers *(Allied Pickfords, Asian Tigers, Crown, Transworld, Leo's, Movers.sg, Pacific, Shalom, JK)* | **1,170** | **128** | 2026-07-21 | **2026-08-12** |
| Australian mover *(Santa Fe Relocation, Sydney)* | **151** | **128** | 2026-07-21 | **2026-08-12** |
| Correct FR/NO/global *(Déménagements Delahaye, SIRVA, Crown Norway, AGS Movers Norway)* | 496 | 122 | 2026-07-21 | 2026-08-12 |

**Only 27% of what a Paris→Oslo employee saw for movers was geographically plausible.** Singapore neighbourhoods (Toa Payoh, Serangoon, Bukit Timah, Tiong Bahru, Robertson Quay…) were also served as `living_areas` to 3 Oslo cases, and Singapore/Dubai schools (Dover Court, GEMS World Academy, ISS International, NPS International) to 2.

**Secondary defect in the same file** — `plugins/movers.py::_service_area_score` is the only thing that penalises wrong geography, and it is a *soft weight*, not a filter. Its regional tier hardcodes Asia only:

```python
asia_keywords = ("asia", "asia-pacific", "apac")
if any(k in a for a in areas_lower for k in asia_keywords):
    return 75.0
return 20.0     # ← "Europe" falls through to 20
```

A mover whose `service_areas` include `"Europe"` scores **20** for an Oslo move while one covering `"Asia-Pacific"` scores **75**. The scoring function actively favours the wrong continent.

**Fix (2 layers, both needed):**
1. Hard geo gate in `_load_dataset_with_registry` — drop any static item whose `country`/`city`/`service_areas` cannot be reconciled with `destination_country`/`destination_city`. Items with no geo metadata must be **excluded by default**, not admitted by default.
2. Backfill `country` + `city` on every row in `datasets/*.json`, or delete the Singapore-only datasets and let those categories return the honest `hr_pending` empty state instead of wrong vendors.

---

### 🔴 F-2 — HR curation itself contains geographically impossible approvals
**Severity: Critical · Live · Data quality**

`company_vendor_selections` rows carry a `country`, but the row's `master_item_id` frequently points at a catalog item in a different country:

| selection `country` | catalog item location | rows | companies |
|---|---|---|---|
| NO | **Sydney, AU** *(Santa Fe Relocation)* | 177 | **177 — every NO company** |
| SG | Sydney, AU | 110 | 110 |
| DE | Sydney, AU | 14 | 14 |
| NO | *(no country, no city)* | 340 | 170 |
| SG | *(no country, no city)* | 220 | 110 |

Scoped to companies that actually have FR→NO cases, the movers category is **39.7% geo-valid**:

| category | HR-approved rows | geo-valid for Oslo | unlocated | wrong country | % valid |
|---|---|---|---|---|---|
| banks | 474 | 474 | 0 | 0 | 100% |
| housing_agencies | 596 | 596 | 0 | 0 | 100% |
| legal_admin | 474 | 474 | 0 | 0 | 100% |
| schools | 495 | 495 | 0 | 0 | 100% |
| tax_finance | 316 | 316 | 0 | 0 | 100% |
| **movers** | **796** | **316** | **316** | **164** | **39.7%** |

The distribution also tells you these were not deliberate decisions: **avg 19.4 selections per company, max 24, across 320 companies, created over 17 days.** Every Norway company approved ~19 of the ~17–20 available items. This is auto-select-all at signup, not curation. The product premise — "HR chooses who the employee may use" — is not being exercised anywhere in production.

**Fix:** add a `CHECK`-equivalent at the write path in `vendor_curation.upsert_master_selection()` rejecting a `(country, destination_city)` that disagrees with the referenced `service_catalog_items` row; backfill-delete the 325 cross-country rows; decide explicitly whether auto-select-all is the intended onboarding default and, if so, say so in the HR UI.

---

### 🟠 F-3 — `company_vendor_selections.country` is never used as a filter
**Severity: High · Latent (not yet firing)**

`backend/app/services/vendor_curation.py::list_curation()`:

```sql
SELECT * FROM company_vendor_selections
WHERE company_id = :co AND category = :cat
ORDER BY display_order ASC, created_at ASC
```
```python
return [r for r in rows
        if not r.get("destination_city") or _canon_city(r.get("destination_city")) == want]
```

`country` is written but never read as a predicate, and `destination_city IS NULL` is treated as "matches every city". **6,301 of 6,335 rows (99.5%) are `city NULL / country set`** — i.e. every one of them matches every destination.

Today this does not fire, because **0 companies have approvals in more than one country** (verified). The moment one company curates two corridors, its Singapore vendors become visible on its Norway cases and vice versa. It already fires *now* on the HR screen: `GET /api/hr/catalog/curation?destination_city=Oslo` returns rows HR approved for other countries, presented as Oslo approvals.

**Fix:** add `AND (country IS NULL OR country = :dest_country)` to the SQL, and treat `destination_city IS NULL` as country-scoped rather than global.

---

### 🟠 F-4 — Corridor knowledge in `corridors/**` is disconnected from what employees see
**Severity: High · Wasted investment**

Three independent pipelines write three different tables; the employee reads none of the one you import into.

| what you author | loader | writes to | who reads it |
|---|---|---|---|
| `corridors/FR_NO/**` (corridor.yaml + pathway YAML) | `backend/scripts/populate_rce_from_cases.py --apply` | `rce.rules`, `rce.steps`, `rce.cases`, `rce.deadlines`, `rce.rule_citations` | `GET /api/hr/cases/{id}/steps` **(HR only)** |
| `backend/seeds/requirements/*.yaml` | `backend/scripts/seed_requirements.py` | `requirement_items` | employee "Destination Requirements" |
| `corpus/*.json` | `backend/scripts/ingest_corridor_corpus.py` | `immigration_requirements` | employee "Move at a Glance" |
| crawled sources | `immigration-indexer.yml` *(manual dispatch)* | `immigration_corpus_chunks` | AI roadmap generation |

Consequences for FR→NO specifically:
- **No `norway.yaml`** exists in `backend/seeds/requirements/`. Norway's only `requirement_items` come from a generic `long_term_only.yaml` block (3 items, LTA/PERMANENT-gated). The employee's Destination Requirements panel for Oslo is near-empty by construction.
- **No FR_NO file in `corpus/`** → `immigration_requirements` has no FR→NO row → "Move at a Glance" has nothing corridor-specific.
- `populate_rce_from_cases.py` is **not wired to `render.yaml`, any GitHub Actions schedule, any cron endpoint, or `package.json`**. Nothing has ever populated `rce.*` for FR_NO in production.
- The one live consumer of your pathway YAML is `case_feasibility.py`, which reads the file off disk at request time for the HR overview banner — and for FR_NO (free movement, `arrival_anchor: true`) it always resolves to `ok` and renders nothing.

So the FR_NO corridor content — which your own `ReloPass_FR-NO_Requirements_VERIFICATION.md` confirms as verified against Skatteetaten / UDI / NAV / CLEISS — reaches **zero employee-facing surfaces**.

**Fix:** pick one canonical corridor store. Cheapest path to value: make `corridors/**` the authoring format and add a build step that compiles it into `requirement_items` + `immigration_requirements`, wired to CI on merge, not a manual local script.

---

### 🟠 F-5 — 44% of profiles have `company_id = NULL`, which bypasses HR curation entirely
**Severity: High · Security/correctness**

`engine.py:302`: `will_curate = bool(company_id) and not plugin.advisory`
`employee_recommendations_filter.py:83`: `if not company_id: return items, None  # pass through`

Production: **1,293 of 2,911 `profiles` rows have `company_id IS NULL`** (44.4%). Any such user who reaches the recommendations endpoint gets the **full un-curated master catalog** for every category — HR's allow-list never applies. The comment calls this "legacy un-curated behavior… admin debug, internal jobs", but it is reachable by any authenticated employee whose profile row was created without a company.

**Fix:** fail closed. If `company_id` cannot be resolved for a non-admin caller, return `([], "hr_pending")` rather than the global catalog. Add an explicit `admin_debug=True` flag for the legitimate internal case.

---

### 🟠 F-6 — RFQ funnel is 100% stalled after `sent`
**Severity: High · Product**

All 30 RFQs: `status='sent'`. `validated_quote_id` is NULL on all 30. `was_recommended` is NULL on all 30 — the recommendation-attribution telemetry that `rfqs.recommendation_snapshot` / `was_recommended` / `override_reason_category` exist to capture is **never written**, so you cannot measure whether employees pick what the engine recommends.

- 30 RFQs → 135 recipients → **9 quotes** (6.7% recipient response rate; 8 of 30 RFQs got any quote at all)
- 22 of 30 RFQs are the identical `movers,schools` / 6-recipient shape → almost certainly seeded, not organic
- **RFQ `4933a2e3` has 0 `rfq_items` but 3 `rfq_recipients`** — three suppliers were emailed a request with no service line on it. Nothing prevents this at write time.

**Fix:** `NOT NULL`-equivalent guard on RFQ creation (≥1 item before recipients are created); populate `was_recommended` + `recommendation_snapshot` at creation from the serving slate; instrument the `sent → viewed → quoted → validated` funnel.

---

### 🟡 F-7 — Employee services routes have no client-side role guard
**Severity: Medium**

`frontend/src/navigation/routes.ts:93-98` declares `roles: ['EMPLOYEE','ADMIN']` for the whole services/RFQ flow. `frontend/src/App.tsx:389-396` renders them **unwrapped**:

```tsx
<Route path={ROUTE_DEFS.caseServicesRfqNew.path} element={<ServicesRfqNew />} />
```

Every comparable route in the file uses `<RequireHrRoute>` or `<RequireEmployeeRoute>`. Server-side auth still holds (`_require_assignment_visibility` in `create_rfq`), so this is a UX/defence-in-depth gap rather than a data leak — but it is inconsistent with the declared route contract and with every other route tree.

---

### 🟡 F-8 — Three supplier identity spaces, reconciled by `CAST(... AS TEXT)`
**Severity: Medium · Tech debt**

- RFQ path keys on `suppliers.id` (varchar)
- `case_vendor_shortlist.vendor_id` is `uuid`, FK'd to `public.vendors` — **a table that has been dropped**
- `cases_read.py:2594` joins `LEFT JOIN suppliers s ON CAST(s.vendor_id AS TEXT) = CAST(cvs.vendor_id AS TEXT)` — a *fourth* column (`suppliers.vendor_id`, not `suppliers.id`)
- `relocation_cases.company_id` is `text`; `company_vendor_selections.company_id` is `uuid` — every tenancy join across these two needs a cast
- `backend/app/routers/hr_vendors.py` still serves `GET /api/hr/vendors`, `/{id}`, `/corridors` from **`vendors_legacy` (0 rows in prod)**, registered only in `backend/main.py`

Referential integrity is nonetheless **clean today** — all of these returned 0 orphans:

| check | orphans |
|---|---|
| `service_catalog_items.supplier_id → suppliers.id` | 0 |
| `supplier_service_capabilities.supplier_id → suppliers.id` | 0 |
| `company_vendor_selections.master_item_id → service_catalog_items.id` | 0 |
| `rfq_recipients.vendor_id → suppliers.id` | 0 |
| `quotes.vendor_id → suppliers.id` | 0 |
| `company_vendor_selections.company_id → companies.id` | **14** |

---

### 🟡 F-9 — 93.7% of the master catalog cannot be sent an RFQ
**Severity: Medium · Not yet firing on FR→NO**

RFQ recipient resolution (`rfq_recipient_mapping.resolve_recipient_ids`) walks `service_catalog_items.external_id → .supplier_id → suppliers.id`. **923 of 985 `service_catalog_items` have `supplier_id IS NULL`** — picking any of them yields *"Cannot request a quote from X: it is not a supplier we can reach."*

FR→NO is currently unaffected: **all 17 Norway catalog items have `supplier_id` set** and are RFQ-able. But 94% of the catalog is a dead end for the corridors you expand into next.

---

### 🟡 F-10 — Data-quality noise in `supplier_service_capabilities`
**Severity: Low–Medium**

- Rows with `coverage_scope_type = 'country'` **and** `city_name = 'Oslo'` populated (movers, tax_finance) — contradictory scope; whether they match depends on which OR-branch fires.
- `city_name == destination_city` is **exact, case-sensitive, untrimmed** in `supplier_registry.find_suppliers_for_service`, while `vendor_curation._canon_city()` does NFKD + diacritic-strip + lowercase. `"Zürich"` matches in one layer and not the other.
- `country_code.upper()[:2]` silently truncates rather than validating ISO-3166-1 alpha-2.
- Norway coverage today (post `platform_vetting_status='approved'` filter): banks 3, housing 4, legal_admin 3, schools 3, movers **2**, tax_finance **2**; and **0** for `dsp`, `healthcare_ipmi`, `language_cultural`, `rmc`. Those four categories fall straight through to the Singapore static datasets (see F-1).
- `corridor_coverage_targets.current_verified_count` **is accurate** — it matches the live approved-capability count exactly for all 6 NO categories. Good; keep it.

---

## 2. FR → NO RFQ trace (the requested end-to-end test)

**Population:** 176 `relocation_cases` with `corridor='FR-NO'`, 175 destined Oslo. All 176 have a `company_id`; 165 of those companies have curation rows. 273 recommendation slates served to these cases.

| stage | expected | observed | verdict |
|---|---|---|---|
| 1. Admin master catalog for NO | vendors serving Norway | 17 active items, all with `supplier_id` → RFQ-able | ✅ |
| 2. HR curates per (company, category, city) | HR narrows the master | 3,368 rows / 177 companies, ~19 each, `city NULL` | ⚠️ auto-select-all, not curation (F-2) |
| 3. HR approvals are geo-correct | Norway vendors only | movers **39.7%** geo-valid; every company approved a Sydney mover | ❌ **F-2** |
| 4. Engine builds candidates for Oslo | geo-filtered | registry items geo-filtered ✅, then 10 SG static movers appended unfiltered | ❌ **F-1** |
| 5. HR gate applied | only approved items survive | `apply_hr_curation` strict allow-list, no catalog fallback | ✅ *(gate logic is correct)* |
| 6. Employee sees the slate | Oslo vendors | 64% Singapore, 8% Australia, 27% correct — through 2026-08-12 | ❌ **F-1** |
| 7. Employee picks → RFQ created | recipients resolve | 0 orphan `rfq_recipients.vendor_id`; NO items all resolvable | ✅ |
| 8. RFQ dispatched → quote → award | funnel completes | 30/30 stuck at `sent`; 9 quotes; 0 awarded | ❌ **F-6** |

**Verdict on your question:** the employee does see exactly what HR approved — the gate is faithful. But steps 3 and 4 poison the input, so "what HR approved" and "what the employee sees" are both wrong for the corridor. The gate is working; the thing it is gating is not.

---

## 3. Goals

| # | Goal | Why it matters | Target |
|---|---|---|---|
| **G1** | **Geographic correctness.** No employee is ever shown a vendor that cannot serve their destination. | This is a trust-destroying, demo-killing bug. A Paris→Oslo employee seeing "Movers.sg" ends the conversation. | 100% of served slate items geo-valid for the case's destination |
| **G2** | **Curation fidelity.** What HR approves is exactly what the employee can pick — no more, no less, no bypass. | This is the core product promise to the HR buyer. | 0 un-curated slates for users with a company; 0 geo-invalid approvals |
| **G3** | **Corridor knowledge reaches the employee.** Verified corridor content appears in the employee's requirements and roadmap. | You have verified FR→NO content that no employee can see. Pure sunk cost until wired. | ≥1 employee-facing surface per authored corridor, CI-enforced |
| **G4** | **RFQ completes.** An RFQ moves from sent → quoted → awarded. | 30/30 stalled means the revenue path has never been exercised end-to-end. | ≥1 corridor with a full sent→awarded RFQ in staging; funnel instrumented |
| **G5** | **Regressions are caught before merge.** Every invariant above is an executable assertion. | All ten findings were silently true in prod for weeks. | Eval harness green in CI on every PR |

---

## 4. Spec — the invariants

These are the contracts. Each maps to an eval in §7.

**Vendor geography**
- **S1** Every item in a served slate must satisfy: `item.country == case.dest_country` **OR** `item.city == case.dest_city` **OR** item is explicitly flagged `global_coverage: true`. Absence of geo metadata is **not** global coverage.
- **S2** Every row in `datasets/*.json` must carry `country` (ISO-3166-1 alpha-2) or an explicit `global_coverage: true`.
- **S3** `_service_area_score` regional tiers must cover every continent ReloPass sells into, or be deleted in favour of a hard filter.

**Curation**
- **S4** `company_vendor_selections.country` must equal `service_catalog_items.country` for the referenced `master_item_id`, unless the item is `global_coverage`.
- **S5** `list_curation()` must filter on `country` as well as `destination_city`.
- **S6** A non-admin caller with unresolvable `company_id` returns `([], "hr_pending")`, never the global catalog.
- **S7** Every `company_vendor_selections.company_id` resolves to a `companies` row.

**RFQ**
- **S8** An RFQ cannot be created with 0 `rfq_items`.
- **S9** Every `rfq_recipients.vendor_id` resolves to a `suppliers` row (currently holds — keep it).
- **S10** Every RFQ records `was_recommended` + `recommendation_snapshot` at creation.
- **S11** Every catalog item exposed to an employee has a non-null `supplier_id` (i.e. is reachable).

**Corridor knowledge**
- **S12** Every directory in `corridors/` has a corresponding non-empty row set in at least one employee-read table (`requirement_items` or `immigration_requirements`) for its destination.
- **S13** Corridor compilation runs in CI, not from a developer laptop.

**Identity / tenancy**
- **S14** One canonical supplier id space. `case_vendor_shortlist.vendor_id` re-typed to match `suppliers.id`; the `CAST(... AS TEXT)` join deleted.
- **S15** `relocation_cases.company_id` and `company_vendor_selections.company_id` share a type.

---

## 5. Metrics

**Correctness (the ones that matter now)**

| metric | definition | now | target |
|---|---|---|---|
| **Slate Geo-Precision** | served slate items geo-valid ÷ total served, per corridor | **27%** (FR→NO movers) | **100%** |
| **Curation Geo-Validity** | `company_vendor_selections` rows whose item location matches the row's country ÷ total | **39.7%** (FR→NO movers) | **100%** |
| **Curation Bypass Rate** | recommendation calls with unresolvable `company_id` ÷ total | ~44% of profiles at risk | **0%** |
| **RFQ Reachability** | catalog items with `supplier_id` set ÷ active items | **6.3%** | **100%** |
| **Corridor Wiring** | corridors with ≥1 employee-visible row ÷ corridors authored | **0 / 10** | **10 / 10** |

**Funnel (instrument these; you cannot currently compute them)**

| metric | definition | now |
|---|---|---|
| RFQ dispatch rate | RFQs with ≥1 recipient invited ÷ created | 29/30 |
| Recipient response rate | recipients submitting a quote ÷ invited | **6.7%** |
| RFQ completion rate | RFQs with `validated_quote_id` ÷ created | **0%** |
| Recommendation adherence | RFQs where the picked vendor was in the served slate ÷ total | **unmeasurable** — `was_recommended` never written |
| Time-to-first-quote | `quote_submitted_at − invited_at`, p50/p90 | unmeasurable |

**Coverage**

| metric | now (FR→NO) |
|---|---|
| Categories with ≥3 approved suppliers | 4 of 10 (`banks`, `housing_agencies`, `legal_admin`, `schools`) |
| Categories at zero | 4 (`dsp`, `healthcare_ipmi`, `language_cultural`, `rmc`) — these fall through to Singapore static data |
| `corridor_coverage_targets` accuracy | ✅ exact match to live counts |

---

## 6. Validation process

**Stage 0 — Freeze the bleeding (today, ~2h)**
Add the hard geo gate in `_load_dataset_with_registry`. Ship behind a feature flag, default **on**. Categories that go empty as a result render the existing `hr_pending` empty state — "Your HR is finalizing providers for {category}" — which is honest and already implemented. *An empty list beats a Singapore mover.*
→ **Gate:** re-run the harness; Slate Geo-Precision = 100% for FR→NO, DE→FR, IN→DE.

**Stage 1 — Data repair (1 day)**
Backfill `country`/`city` on `datasets/*.json` or delete the SG-only ones. Delete the 325 cross-country `company_vendor_selections` rows and the 14 orphan-company rows. Backfill `service_catalog_items.supplier_id`.
→ **Gate:** S2, S4, S7, S11 pass. Migration file committed per `CLAUDE.md` discipline; ledger reconciled; **no `supabase db push`**.

**Stage 2 — Close the bypasses (1 day)**
Fail closed on missing `company_id` (S6). Add the `country` predicate to `list_curation` (S5). Wrap the employee services routes in `RequireEmployeeRoute` (F-7). Guard RFQ creation against 0 items (S8).
→ **Gate:** S5, S6, S8 pass; `npx tsc --noEmit` clean; `pytest` green.

**Stage 3 — Corridor wiring (2–3 days)**
Compile `corridors/**` → `requirement_items` + `immigration_requirements` in CI. Start with FR_NO since it is already SME-verified.
→ **Gate:** S12, S13 pass; an FR→NO employee sees ≥5 Norway-specific requirements in the Dossier.

**Stage 4 — RFQ funnel (2 days)**
Write `was_recommended` + `recommendation_snapshot` on creation. Instrument the funnel. Drive one real RFQ sent→quoted→awarded in staging.
→ **Gate:** S10 passes; recommendation-adherence computable; one awarded RFQ exists.

**Standing rules** — inherited from `CLAUDE.md`, not negotiable here: every new router registered in **both** `backend/main.py` and `backend/app/main.py`; every new `public` table gets RLS + policy + `REVOKE ALL FROM anon`; migrations applied out-of-band then reconciled; no compliance-status claims in copy.

---

## 7. Evals

Delivered as `relopass_integration_evals.py` — read-only, no writes to production, runnable standalone or under pytest, exits non-zero on failure so it drops straight into CI.

```bash
export DATABASE_URL='postgresql://...:5432/postgres'   # session mode, port 5432
export RELOPASS_REPO=/path/to/rolec

python relopass_integration_evals.py                    # all evals, all corridors
python relopass_integration_evals.py --corridor FR-NO   # one corridor
python relopass_integration_evals.py --json report.json # machine-readable
pytest relopass_integration_evals.py -v                 # CI mode
```

**Suite A — Static dataset hygiene** *(no DB; runs in <1s, catches F-1 at source)*
- `A1` every `datasets/*.json` row has `country` or `global_coverage: true` → **currently fails: 13/17 files**
- `A2` no dataset is single-country-only unless named as such
- `A3` `_service_area_score` regional keywords cover EU/NA/APAC/MEA

**Suite B — Slate geo-precision** *(the F-1 regression test)*
- `B1` for every corridor, every `recommendation_slates` item resolves to a vendor geo-valid for `dest_country`/`dest_city` → **currently fails: FR→NO at 27%**
- `B2` no slate contains a vendor whose known country ≠ destination country
- `B3` a simulated Oslo slate contains zero Singapore-dataset names

**Suite C — Curation integrity** *(F-2, F-3, F-5)*
- `C1` `company_vendor_selections.country` == referenced item country → **fails: 325 rows**
- `C2` every `company_id` resolves to a `companies` row → **fails: 14 rows**
- `C3` no company has approvals spanning >1 country while `list_curation` ignores country → passes today, guards F-3
- `C4` `profiles.company_id` null rate below threshold → **fails: 44.4%**

**Suite D — RFQ integrity** *(F-6, F-8, F-9)*
- `D1` every RFQ has ≥1 `rfq_item` → **fails: 1 RFQ**
- `D2` every `rfq_recipients.vendor_id` resolves to `suppliers` → passes
- `D3` every `quotes.vendor_id` resolves to `suppliers` → passes
- `D4` active catalog items have `supplier_id` → **fails: 93.7%**
- `D5` RFQs older than 14 days are not all still `sent` → **fails: 30/30**

**Suite E — Corridor wiring** *(F-4)*
- `E1` every `corridors/*/` dir has employee-visible rows in `requirement_items` or `immigration_requirements` → **fails: 0/10**
- `E2` corridor `corridor.yaml` parses and declares ≥1 pathway → passes

**Suite F — Referential integrity** *(regression guard on what currently works)*
- `F1`–`F5` the five FK-equivalent joins from §F-8 → all pass; lock them in

**Baseline as of 2026-08-13:** 8 of 21 evals pass. `evals_baseline.json` ships alongside so you can diff each run against today rather than against an aspiration.

**Grading policy.** These are deterministic assertions, not LLM judgments — geographic correctness is a fact, not an opinion. The only place an LLM-graded eval earns its keep here is Suite E's *content quality* (does the compiled FR→NO requirement text actually match the verified source?), and that should reuse the existing `ai_replay_records` / `agent_runs` substrate rather than a new pipeline.

---

## 8. What I would do first

1. **The geo gate** (Stage 0). Two hours. It stops a Paris→Oslo employee being shown Movers.sg, which is currently happening.
2. **Delete or fix the Singapore datasets.** They are demo residue with no `country` column, and they are the single root cause of F-1.
3. **Wire the harness into CI.** Every finding in this report was silently true in production for three weeks.

Then Stage 1–2 (data repair + bypass closure), and only after that the corridor-knowledge wiring — it is the largest investment and the least urgent, because nobody is currently being shown *wrong* corridor content, only *no* corridor content.

---

*Method note: all production figures are from read-only `SELECT` against project `nsvefcvpvwwwhuqyuqmp` on 2026-08-13. No writes, no migrations, no test RFQs created. Code excerpts are from the working tree at `~/Documents/GitHub/rolec`.*
