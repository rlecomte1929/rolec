# Claude Code Execution Prompt — Vendor Sourcing Sides & HR Catchment Override

> **How to use.** Open Claude Code at the repo root and paste **everything below the horizontal line** — that is the whole instruction set. It is self-contained: it names the files, quotes the real code, states the acceptance tests, and carries the `CLAUDE.md` hard rules inline so they cannot be missed. It is deliberately **phase-gated** — Claude Code stops for your approval between phases rather than running to the end.
>
> **Before you paste, check:**
> 1. You are on a clean tree at repo root (`~/Documents/GitHub/rolec`), branched off an up-to-date `main`.
> 2. `git config core.hooksPath .githooks` has been run in this clone (the pre-push build hook).
> 3. `DATABASE_URL` is exported in **session mode — port 5432, not the 6543 pooler**. Phases 0 and 3 and every eval run need it.
> 4. These five files are committed and present — the prompt tells Claude Code to read them and will be much weaker without them:
>    `audit/ReloPass_Vendor_Sourcing_Addendum_2026-08-13.md` · `audit/ReloPass_HR_Catchment_UX_Proposal.md` · `audit/ReloPass_Data_Integration_Audit_2026-08-13.md` · `design/relopass-hr-catchment-mockup.html` · `evals/relopass_integration_evals.py`
>
> **Tier:** 🔴 Red. Touches tenant-scoped data, deletes production rows, and changes what employees see. **Do not run under autopilot**, and do not let `relopass-dev-queue` pick this up as a queue item — it is too large for that workflow.
>
> **Prerequisite:** Phase 0 is a data task with no code. If you would rather vet the 15 supplier rows yourself in the admin UI, do that first and tell Claude Code to start at Phase 1.

---

## CONTEXT

You are implementing **Addendum A — Vendor Sourcing Sides & HR Catchment Override**.

**Read these before writing any code.** They carry the production evidence behind every decision below; this prompt is the execution plan, not the reasoning.

| file | read it for | needed by |
|---|---|---|
| `audit/ReloPass_Vendor_Sourcing_Addendum_2026-08-13.md` | the full spec — schema, `resolve_catchment()`, sourcing-side mapping, backfill rules | all phases |
| `audit/ReloPass_HR_Catchment_UX_Proposal.md` | three-tier cascade, reason codes, API envelope shape, screen states | phases 2, 4 |
| `design/relopass-hr-catchment-mockup.html` | the interactive UI reference — **open it in a browser**, don't just read the source | phase 4 |
| `audit/ReloPass_Data_Integration_Audit_2026-08-13.md` | why any of this is broken; the production numbers you must reproduce | phases 0, 3 |
| `evals/relopass_integration_evals.py` | the harness you extend | all gates |

### The problem in one paragraph

ReloPass currently sources every vendor category from the **destination** country. That is wrong for movers: an international household-goods move is contracted from the **origin** agent, who surveys and packs at origin and subcontracts the destination agent through their FIDI/IAM/OMNI network. Worse, the candidate list is not geo-filtered at all — `_load_dataset_with_registry` appends Singapore demo seed data from `backend/app/recommendations/datasets/*.json` with no geographic check, so 128 French employees relocating to Oslo were served Singaporean movers as recently as 2026-08-12. Separately, `company_vendor_selections` has no origin column, so HR literally cannot express "my approved French movers for outbound-France moves."

### What already half-exists

`backend/app/recommendations/criteria_builder.py:249` already prefills origin for movers:

```python
# Prefill origin from case for movers
if svc_key == "movers" and not criteria.get("origin_city") and origin_city:
    criteria["origin_city"] = origin_city
```

`MoversPlugin.CriteriaModel` declares `origin_city: str = ""`. Nothing consumes it — `_service_area_score(c.destination_city, ...)` scores destination only, and `search_by_service_destination()` in `backend/app/services/supplier_registry.py:286` takes **no origin parameter**. You are finishing wiring that someone started.

---

## GOALS

| id | goal | measurable outcome |
|---|---|---|
| **G1** | Each service category is sourced from the correct side of the corridor | `sourcing_side` drives candidate selection for all 11 categories; eval C7 green |
| **G2** | No employee is shown a vendor that cannot serve their move | Slate geo-precision 100% on FR→NO, DE→FR, IN→DE; evals B1, B3 green |
| **G3** | HR can widen the catchment for border cases, deliberately and auditably | `company_vendor_catchment` in use; every extension carries a reason and an actor; evals C5, C6 green |
| **G4** | HR curation state is trustworthy | 325 cross-country + 14 orphan rows deleted; movers rows re-confirmed not guessed; eval C1 green |
| **G5** | RFQs go to vendors who can actually serve the corridor | Eval D6 green |

**Non-goals — do not do these:**
- Do not fix the corridor-knowledge wiring (audit F-4). Separate work.
- Do not touch `rfq_requests_legacy`, `vendors_legacy`, or `case_vendor_shortlist` typing. Noted in the audit, out of scope here.
- Do not refactor `backend/main.py`. Surgical changes only.
- Do not add configurability nobody asked for. Per `CLAUDE.md` §Simplicity First: minimum code that solves the problem.

---

## HARD RULES — from `CLAUDE.md`, non-negotiable

1. **Dual router registration.** Any new router goes in **both** `backend/main.py` *and* `backend/app/main.py`. Render boots `uvicorn backend.main:app`; a router only in the modular app 405s in prod. This has bitten the team three times (AI-002 v2, AIQ-567, AIQ-568). Verify with:
   ```bash
   python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if 'catchment' in r.path))"
   ```
2. **New `public` tables need all three:** `ENABLE ROW LEVEL SECURITY`, at least one tenant-scoped policy, and `REVOKE ALL ... FROM anon`. Use the `case_milestones` policies as the pattern reference. This gate exists because SEC-002 exposed 8 tables of GDPR-scope PII.
3. **Never run `supabase db push`.** 147+ pending migrations reach back to April, two of them destructive. Commit migration files; a human operator applies out-of-band and reconciles the ledger.
4. **Migration timestamp = above the max of BOTH** the repo max and the prod ledger max:
   ```bash
   git ls-tree origin/main --name-only supabase/migrations/ | sed 's|.*/||' | cut -c1-14 | sort | tail -1
   psql "$DATABASE_URL" -tAc "SELECT max(version) FROM supabase_migrations.schema_migrations"
   ```
   Repo max was `20261027000000` on 2026-08-13. Use `20261101000000`+ and re-check before committing. Do not batch-merge two migration PRs back to back.
5. **Tests that mount the prod app** (`from backend.main import app`) must import auth deps from `backend.app.auth_deps`. There is a second `get_current_user` in `backend/main.py`; `dependency_overrides` keyed to the wrong reference silently never fires. This is what sank AIQ-567's tests.
6. **Read `DESIGN.md` before any UI change.** Navy `#0b2b43` + teal `#1f8e8b`, Inter + JetBrains Mono, 8px grid, `frontend/src/components/antigravity/` first. No purple. Prefer `navy-*` / `accent-*` / `--rp-*` over hex literals.
7. **Type-check and test before flagging anything complete:** `cd frontend && npx tsc --noEmit` and `cd backend && pytest`.
8. **Branch:** `audit/stage-9-vendor-sourcing`. One PR per phase, or one PR with phase-tagged commits — your call, but P3's deletions must be reviewable in isolation.

---

## SPEC

### S1 — Sourcing side taxonomy

Add `sourcing_side` to `public.supplier_service_categories`, `NOT NULL DEFAULT 'destination'`, `CHECK (sourcing_side IN ('origin','destination','both','either'))`.

| code | sourcing_side |
|---|---|
| `movers` | `origin` |
| `tax_finance` | `both` |
| `rmc`, `healthcare_ipmi` | `either` |
| `dsp`, `housing_agencies`, `schools`, `banks`, `legal_admin`, `language_cultural`, `partner_family` | `destination` (default) |

### S2 — `resolve_catchment()` is the single source of truth

New module `backend/app/services/vendor_catchment.py`:

```python
def resolve_catchment(
    category: str,
    origin_country: str | None,
    destination_country: str | None,
    company_id: str | None,
) -> Catchment:
    """Countries a vendor may be based in to be eligible for this (category, corridor).

    BOTH the recommendation engine AND the HR curation view must call this. If they
    diverge, audit finding F-3 reappears in a new shape.
    """
```

Behaviour:
- `origin` → `{origin_country}`; `destination` → `{destination_country}`; `both`/`either` → both
- **Neighbours are DEFAULT-INCLUDED for origin-sourced categories** (product decision, 2026-08-13). Union in `neighbours_of(origin_country)` from `country_adjacency`, subject to **two** filters:
  1. `country_adjacency.default_included = true` — excludes short-sea (UK↔FR, IE↔UK, DK↔SE) and cross-bloc pairs (ES↔MA, PL↔UA, FI↔RU, IN↔PK…)
  2. `has_eligible_vendors(nb, category, destination_country)` — **a neighbour with zero eligible vendors is never added to the catchment and never rendered.** This is what makes default-on safe rather than noisy.
  A neighbouring-country *mover* is plausible; a neighbouring-country *bank* or *school* is not, so this applies to origin-sourced categories only.
- Respect `company_vendor_catchment_policy.include_neighbours` (default `true`) — HR can switch it off.
- Union in HR's `company_vendor_catchment` extras (now genuinely exceptional: non-adjacent, short-sea, cross-bloc)
- Returns `Catchment(base: set[str], extended: set[str], all: set[str])`

> **Do not widen the escape hatch.** `default_included` only ever admits countries that already have a row in `country_adjacency`. AU has no adjacency row to NO, so the 177 Sydney-for-Norway approvals still fail C1 and C6. If your implementation makes them pass, it is wrong.

**Eligibility:**
```
vendor.based_in ∈ catchment.all
  AND (sourcing_side != 'origin' OR vendor_reaches(destination_country))
```

**`vendor_reaches(dest)`** is satisfied by ANY of:
1. `supplier_service_capabilities.coverage_scope_type = 'global'`
2. a `supplier_service_area_coverage` row (supplier + category) with `area_id` = destination ISO2 or a containing region
3. a `supplier_accreditations` row with `status='verified'` from `FIDI FAIM`, `IAM`, or `OMNI`

Rule 3 is what those accreditations mean, the table already exists with 27 rows, and its CHECK constraint already guarantees a verified row has `evidence_url + verified_at`.

### S3 — Schema

Exactly as specified in Addendum A §A.5. Do not improvise column names — the evals reference them.

- `supplier_service_categories.sourcing_side`
- `company_vendor_selections` + `origin_country char(2)`, `selection_basis text NOT NULL DEFAULT 'in_catchment' CHECK IN ('in_catchment','hr_extended')`, `extension_reason text`, `extended_by_user_id uuid`, and constraint `cvs_extension_requires_reason`
- new `company_vendor_catchment` (RLS + policy + REVOKE)
- new `country_adjacency` (REVOKE; reference data, no tenant scope)

**`company_vendor_selections.country` keeps meaning DESTINATION.** Do not repurpose it — that silently reinterprets 6,301 live rows.

### S4 — Hard geo gate

In `backend/app/recommendations/engine.py::_load_dataset_with_registry`, static-dataset items are currently appended with no geographic check:

```python
if registry_items:
    dataset = list(registry_items)
    for d in static_dataset:                 # ← no geo check
        if iid and iid not in existing_ids and iid not in twin_ids:
            dataset.append(d)
else:
    dataset = list(static_dataset)           # ← 100% static fallback
```

Gate both branches on the resolved catchment. **An item with no geo metadata is excluded, not admitted** — that inversion is the entire root cause of F-1. 13 of 17 dataset files have no `country` or `city` field.

### S5 — Fix `_service_area_score` region tiers

`backend/app/recommendations/plugins/movers.py` hardcodes Asia only:
```python
asia_keywords = ("asia", "asia-pacific", "apac")
if any(k in a for a in areas_lower for k in asia_keywords):
    return 75.0
return 20.0     # ← "Europe" lands here
```
Make the tiers continent-complete. This becomes ranking-only once S2 makes reach a hard predicate, but leaving it biased toward Asia is indefensible.

### S6 — HR curation reads the catchment

`backend/app/services/vendor_curation.py::list_curation()` currently filters on `company_id + category` only, with city applied in Python and `country` never used:

```python
sql = ("SELECT * FROM company_vendor_selections "
       "WHERE company_id = :co AND category = :cat "
       "ORDER BY display_order ASC, created_at ASC")
```

Add corridor parameters and filter through `resolve_catchment()`. **Preserve `_canon_city()`** — the NFKD/diacritic normalisation exists because HR's picker city ("Zürich") and the employee's intake city ("Zurich") are separately sourced (AIQ-1457). Do not regress it.

### S7 — HR catchment API + UI

`POST/GET/DELETE /api/hr/catalog/catchment`, guarded by `require_admin_or_hr`, tenant-scoped. **Register in both `main.py` files.**

UI in `frontend/src/pages/HrVendorCuration.tsx`: show the resolved catchment, an "Extend catchment" flow with a **mandatory** reason field, and a badge on vendors approved via extension.

### S8 — RFQ validates recipients

RFQ creation (`backend/main.py:9292`, `create_rfq`) checks resolved recipients against the catchment. Reject with a clear message, following the existing honest-error pattern in `rfq_recipient_mapping.py`: `"Cannot request a quote from {name}: it is not a supplier we can reach."`

---

## PLAN — phase-gated, stop for approval between phases

### Phase 0 — Unblock supply *(data only, no code)*

**Do this first or Phase 2 ships an empty vendor list.**

FR has 4 mover capabilities and DE has 11 — **all with `platform_vetting_status != 'approved'`**, and the employee-facing filter hard-requires `approved`. So all 15 are invisible today.

1. Report the 15 rows: supplier name, country, category, current vetting status, and whether destination reach is evidenced.
2. **Do not self-approve them.** Produce a vetting worksheet and stop. A human decides what "vetted" means here.

→ **Gate:** ≥3 FR-based movers approved with verified NO reach. Report and wait.

### Phase 1 — Taxonomy *(read-only additions, no behaviour change)*

1. Migration: `sourcing_side` column + the 4 UPDATEs from S1.
2. Migration: `country_adjacency` (incl. `default_included boolean NOT NULL DEFAULT true`) + seed EEA + UK + CH (~80 symmetric rows). Seed `default_included` per Addendum A §A.5.4:
   - `land_border` within EU/EEA/CH → `true`
   - `short_sea` (UK↔FR, IE↔UK, DK↔SE) → **`false`**
   - `land_border` across a bloc edge (ES↔MA, PL↔UA, FI↔RU, …) → **`false`**
3. Migration: `company_vendor_catchment_policy` with `include_neighbours boolean NOT NULL DEFAULT true` (RLS + policy + REVOKE).
4. `backend/app/services/vendor_catchment.py` with `sourcing_side()`, `neighbours_of(country, default_included=True)`, and `has_eligible_vendors()`.
5. Unit tests.

→ **Gate:** mapping matches Addendum A §A.2; adjacency symmetric — **assert both directions have the same `default_included` value**, an asymmetry here is a silent one-way border; `pytest` green; zero behaviour change.

### Phase 2 — Resolution + geo gate *(this is the fix that stops the bleeding)*

1. `resolve_catchment()` + `vendor_reaches()` per S2.
2. `search_by_service_destination` → `search_by_service_corridor(origin_country, destination_country, ...)`. Keep a thin deprecated shim if other callers exist; do not chase them all.
3. Thread `origin_country` from `criteria_builder` through `engine` to the registry search. The plumbing to `criteria` already exists — extend it, don't rebuild it.
4. Hard geo gate per S4.
5. Fix `_service_area_score` per S5.

→ **Gate:** evals B1, B3, C7 green for FR→NO, DE→FR, IN→DE. `pytest` green.

### Phase 3 — Curation schema + backfill *(destructive — review in isolation)*

1. Migration per S3.
2. Backfill per Addendum A §A.8:
   - destination-sourced rows → `origin_country = NULL`, `selection_basis = 'in_catchment'`
   - **all `movers` rows → `origin_country = NULL`, `selected = false`** (origin was never captured; do not guess it — writing `origin_country = country` would assert every company's movers are Norwegian, which is false and unrecoverable)
   - `DELETE` the 325 cross-country rows and the 14 orphan-company rows; log counts
3. `list_curation()` per S6.

→ **Gate:** evals C1, C2, C5 green. Deletion counts match the audit exactly (325 / 14) — **if they don't, stop and report the discrepancy rather than adjusting the query to fit.**

### Phase 4 — HR UI

Per S7. **Read `DESIGN.md` first**, then open `design/relopass-hr-catchment-mockup.html` in a browser and click through all four preview states — it is the authoritative UI reference and shows behaviour the source alone won't tell you.

Use `frontend/src/components/antigravity/` (`Card`, `Checkbox`, `Modal`, `Badge`, `Tabs`, `CountryFlag`, `StatusPill`, `ConversationalEmptyState` all already exist — do not build new primitives).

The details that carry the design, in priority order:
1. **Zero-vendor countries are omitted, not greyed out.** A chip that yields nothing implies coverage that isn't there.
2. **Neighbour vendors get a quiet `neighbouring country` badge, HR-added ones get `extended`.** Different provenance, different treatment.
3. **Counts everywhere reflect the full eligibility predicate** — in catchment *and* reaches destination.
4. **Two employee-facing provenance lines** (UX proposal §8). Never attribute a default-catchment neighbour to "your HR team" — HR never touched it.

→ **Gate:** `npx tsc --noEmit` clean; eval C6 clean or warnings triaged; manual walkthrough passes.

### Phase 5 — RFQ integrity

1. S8 recipient validation.
2. Write `was_recommended` + `recommendation_snapshot` on RFQ creation — currently NULL on all 30 production RFQs, which makes recommendation adherence unmeasurable.
3. Reject RFQ creation with 0 `rfq_items` (one such RFQ exists in prod, with 3 recipients emailed).

→ **Gate:** evals D1, D5, D6 green.

---

## METRICS

Report these before and after:

| metric | source | now | target |
|---|---|---|---|
| Sourcing-Side Compliance (movers, FR→NO) | eval C7 | 0% | 100% |
| Slate Geo-Precision (FR→NO) | eval B1 | 27% | 100% |
| Curation Geo-Validity (movers) | eval C1 | 39.7% | 100% |
| Origin Supply Depth | Phase 0 | 0 origin countries with ≥3 approved movers | ≥3 per live corridor |
| Extension Plausibility | eval C6 | n/a | ≥95% |
| Eval suite | harness | 8/25 | 25/25 |

---

## VALIDATION PROCESS

Run in order. Do not skip to the end.

1. **Unit** — `resolve_catchment()` table-driven: 11 categories × {origin, destination, both, either} × {adjacent-with-vendors, adjacent-zero-vendors, short-sea, cross-bloc, non-adjacent} × {neighbours on/off} × {extended, not-extended}. Pure function, no DB. This is where the sourcing logic is actually proven. **Must include:** an adjacent country with zero eligible vendors is absent from `catchment.base`, and AU is absent from a FR→NO catchment under every combination.
2. **Integration** — `cd backend && pytest`. Tests mounting the prod app import auth deps from `backend.app.auth_deps` (Hard Rule 5). `RELOPASS_DISABLE_RATE_LIMITS=1` to bypass slowapi.
3. **Type-check** — `cd frontend && npx tsc --noEmit`. Strict mode; `noUnusedLocals` and `noUnusedParameters` are on.
4. **Eval harness** —
   ```bash
   export DATABASE_URL='postgresql://…@…:5432/postgres'   # session mode, 5432 not 6543
   export RELOPASS_REPO=$(pwd)
   python evals/relopass_integration_evals.py --baseline evals/evals_baseline.json
   ```
   Regressions block the phase. Regenerate the baseline with `--write-baseline` after each phase gate.
5. **Route registration** — for any new router:
   ```bash
   python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if 'catchment' in r.path))"
   ```
   If the route is absent, prod is dead on arrival.
6. **Manual, one corridor** — HR curates FR→NO movers → extends to DE with a reason → employee sees French + German movers, zero Singaporeans → RFQ dispatches to a French mover.

---

## EVALS

`evals/relopass_integration_evals.py` exists and runs today at 8/25. Update it as part of this work:

**Amend C1** so intentional border approvals pass and leaks still fail:
```python
catchment = resolve_catchment(row.category, row.origin_country, row.country, row.company_id)
if vendor_country in catchment.base: return PASS
if (vendor_country in catchment.extended
        and row.selection_basis == 'hr_extended'
        and row.extension_reason): return PASS
return FAIL
```

**Amend B1** to resolve against `resolve_catchment(...)` rather than `dest_country` alone — otherwise correct origin-sourced movers reads as a B1 regression on day one.

**Add C5** — every `hr_extended` row has `extension_reason` ≥10 chars and a non-null `extended_by_user_id`.

**Add C6** — extension plausibility. Extended country must be in `country_adjacency` with the base country, or the vendor holds a verified global-network accreditation. **Emit as a warning, not a hard failure** — HR may have a real reason the adjacency table doesn't model, and false failures train people to ignore the suite.

> **C6 is the eval that stops the escape hatch becoming the new bug.** Without it, relabelling the 177 Sydney-for-Norway rows as `hr_extended` with the reason "approved by HR" turns C1 green while the product stays broken. C6 catches AU↛NO as non-adjacent and surfaces it.

**Add C7** — vendors in served slates are based in the resolved catchment for the corridor's sourcing side. Fails at introduction for movers on FR→NO; that is correct.

**Add D6** — `rfq_recipients` on origin-sourced items resolve to suppliers based in the origin catchment.

---

## DEFINITION OF DONE

- [ ] All 6 phases complete, each gate passed and reported
- [ ] `python evals/relopass_integration_evals.py` → **25/25**, new baseline committed
- [ ] `cd backend && pytest` green
- [ ] `cd frontend && npx tsc --noEmit` clean
- [ ] Every new router verified present in `backend.main:app`
- [ ] Every new `public` table has RLS + policy + `REVOKE ALL FROM anon`
- [ ] Migration timestamps above max(repo, ledger); files committed; **no `db push`**
- [ ] Manual FR→NO walkthrough passes, including the DE border extension
- [ ] Notion AI Work Queue updated
- [ ] Committed on `audit/stage-9-vendor-sourcing`

---

## WHEN TO STOP AND ASK

Per `CLAUDE.md` §Think Before Coding — don't assume, don't hide confusion, surface tradeoffs. Stop and ask if:

- **Phase 0 vetting criteria are unclear.** Do not self-approve suppliers. This is a trust boundary.
- **`legal_admin` should be `both`, not `destination`.** It is `compliance_critical = true`. Flag rather than default.
- **The 325 / 14 deletion counts don't match** what you find. Report the discrepancy; do not adjust the query until the numbers agree.
- **A live customer contracts movers at destination.** Then `movers` needs a per-company override rather than a fixed taxonomy value, and the schema changes.
- **Any change would require touching >3 files in `backend/main.py`.** Propose the approach first.
- **A neighbour country where `has_eligible_vendors` is expensive to compute.** The count must reflect the *full* predicate (in catchment AND reaches destination). If that turns into an N+1 per country per page load, propose the query shape before optimising blind.

*(Resolved, do not re-litigate: `include_neighbours` defaults to `true` for movers; `short_sea` pairs are `default_included = false`.)*

---

## REFERENCE — key files

| file | what |
|---|---|
| `backend/app/recommendations/engine.py` | `_load_dataset_with_registry` — the geo gate goes here |
| `backend/app/recommendations/criteria_builder.py:249` | origin already prefilled for movers |
| `backend/app/recommendations/plugins/movers.py` | `_service_area_score`, `MoversCriteria.origin_city` |
| `backend/app/recommendations/datasets/*.json` | Singapore demo seed; 13/17 have no geo fields |
| `backend/app/services/supplier_registry.py:286` | `search_by_service_destination` → becomes corridor-aware |
| `backend/app/services/vendor_curation.py` | `list_curation`, `upsert_master_selection`, `_canon_city` |
| `backend/app/services/employee_recommendations_filter.py` | `apply_hr_curation` — the strict gate; logic is correct, leave it |
| `backend/app/routers/hr_catalog.py` | HR curation endpoints |
| `backend/main.py:9292` | `create_rfq` |
| `frontend/src/pages/HrVendorCuration.tsx` | HR curation UI |
| `frontend/src/api/hrCatalog.ts` | HR catalog API client |
| `evals/relopass_integration_evals.py` | the harness |
| `audit/ReloPass_Vendor_Sourcing_Addendum_2026-08-13.md` | full spec — **read first** |
| `audit/ReloPass_HR_Catchment_UX_Proposal.md` | cascade, reason codes, API envelope, screen states |
| `design/relopass-hr-catchment-mockup.html` | interactive UI reference — open in a browser |
| `audit/ReloPass_Data_Integration_Audit_2026-08-13.md` | evidence behind every decision |
| `DESIGN.md` | design system — mandatory before any UI change |

---

**Start with Phase 0. Report the 15 unvetted FR/DE mover rows and stop for approval.**
