# Supplier Catalog — Audit & Build Spec
_Generated 2026-07-04_

---

## Target Corridors (Locked)

These are the corridors ReloPass must fully cover at launch. Coverage means ≥ 3 approved supplier service offerings per category per corridor.

| Corridor | ISO pair | Origin city | Destination city | Seed status |
|---|---|---|---|---|
| France → Germany | FR-DE | Paris | Berlin / Munich / Frankfurt | ✅ 25 vendors seeded |
| Germany → United States | DE-US | Berlin | New York / San Francisco | ✅ 25 vendors seeded |
| United States → France | US-FR | New York | Paris | ✅ 25 vendors seeded |
| **Paris → Oslo** | **FR-NO** | **Paris** | **Oslo** | ❌ Not seeded |
| **London → New York** | **GB-US** | **London** | **New York** | ❌ Not seeded |
| **India → Munich** | **IN-DE** | **Mumbai / Bangalore / Delhi** | **Munich** | ❌ Not seeded |
| **Amsterdam → Singapore** | **NL-SG** | **Amsterdam** | **Singapore** | ❌ Not seeded |
| **Madrid → Dubai** | **ES-AE** | **Madrid** | **Dubai** | ❌ Not seeded |

The 5 stress-test corridors (bold) are not covered by the existing seeded vendors and require a dedicated seeding migration before launch. See **GAP 0** below.

---

## Part 1 — Audit Findings: What Already Exists

The codebase is significantly more advanced than expected. Before building anything, you need to understand what's already in place to avoid duplicating work or conflicting with existing systems.

### Database (Supabase migrations)

| Table | What it does | Status |
|---|---|---|
| `suppliers` | Entity layer — company name, contact, status, verified flag | ✅ Exists |
| `supplier_service_capabilities` | Offering layer — service category, country, city, budget, tags per supplier | ✅ Exists (the two-layer model is done) |
| `supplier_scoring_metadata` | Rating, review count, admin_score, manual_priority, last_verified_at | ✅ Exists |
| `company_preferred_suppliers` | Customer preference junction table | ✅ Table exists, no HR write RLS |
| `service_catalog_items` | Master catalog items with `source` enum (scraper/manual/seed/hr_promoted) | ✅ Exists, source tracking here |
| `company_vendor_selections` | HR per-company curation, custom vendor JSON | ✅ Exists with HR RLS |
| `catalog_destination_allowlist` | Admin-approved cities for scraping | ✅ Exists |
| `catalog_scrape_quota` | Per-company per-day scrape quota | ✅ Exists |
| `catalog_destination_requests` | HR tickets for off-allowlist destinations | ✅ Exists |
| `catalog_employee_demand` | Tracks empty-state hits by category/city | ✅ Exists |
| `supplier_cluster_cache` | ML clustering cache for recommendation tiering | ✅ Exists |
| `vendor_metric_snapshots` | Historical rating/cost trend data | ✅ Exists |
| `vendors` | Separate vendor table (different system), seeded with real data | ✅ Exists — **25 real vendors seeded** |

### Backend — Routers

| File | Endpoints | Status |
|---|---|---|
| `backend/app/routers/suppliers.py` (304 lines) | Full CRUD: list, search, create, update, set_status, capability CRUD, scoring update | ✅ Complete |
| `backend/app/routers/admin_catalog.py` (417 lines) | Catalog items, allowlist, demand gaps, intake corridors, promote HR vendors | ✅ Complete |
| `backend/app/routers/hr_vendors.py` (236 lines) | List vendors by corridor+category, single vendor, corridors dropdown | ✅ Complete |
| `backend/app/routers/marketplace.py` (273 lines) | Suppliers × policy × preferred_suppliers join | ✅ Complete |
| `backend/app/routers/providers.py` (819 lines) | Provider portal, ratings | ✅ Complete |

### Backend — Services

| File | What it does | Status |
|---|---|---|
| `catalog_scraper.py` | LLM-based (OpenAI) scraper — generates plausible vendors, NOT real scraping | ✅ Exists but LLM only |
| `service_catalog.py` | CRUD for service_catalog_items, source filtering | ✅ Complete |
| `catalog_coverage.py` | Coverage report per city | ✅ Complete |
| `catalog_promotion_service.py` | Promotes HR custom vendors to master catalog | ✅ Complete |
| `scrape_safety.py` | Allowlist and quota management | ✅ Complete |
| `supplier_registry.py` | Supplier entity + capability CRUD | ✅ Complete |
| `vendor_curation.py` | HR vendor curation service | ✅ Complete |

### Backend — Recommendations

14 plugins exist: `banks`, `childcare`, `electricity`, `insurance`, `language_integration`, `legal_admin`, `living_areas`, `medical`, `movers`, `schools`, `storage`, `tax_finance`, `telecom`, `transport`.

### Frontend — Admin

| File | What it does | Status |
|---|---|---|
| `AdminSuppliers.tsx` (304 lines) | List suppliers, filter by category/country/status, status toggle | ✅ Exists |
| `AdminSupplierDetail.tsx` (938 lines) | Full supplier detail, capability management, scoring | ✅ Exists |
| `AdminSupplierNew.tsx` | Create new supplier | ✅ Exists |
| `AdminCatalogQueuePage.tsx` (432 lines) | Destination allowlist, tickets, demand gaps, intake corridors | ✅ Exists |

### Real Seeded Data (Critical Finding)

Migration `20260518100000_vendor_directory_extension.sql` already seeds **25 real vendors** across 5 categories × 3 corridors (FR→DE, DE→US, US→FR):

- **Housing**: Homelike, Spotahome, Habyt, Nestpick, Wunderflats
- **Immigration**: Fragomen, KPMG Law, Deloitte Legal, PwC Legal, GT-Visa
- **Moving**: Crown Relocations, Santa Fe, Gosselin, AGS Movers, Allied Van Lines
- **School search**: ISS, Expatica, TIE Online, Expat School Guide DE, Paris School Advisor FR
- **Destination**: Dwellworks, Cartus, Aires, ECA International, Weichert

**This covers 3 of the 8 locked corridors. The 5 stress-test corridors (FR-NO, GB-US, IN-DE, NL-SG, ES-AE) have zero seed coverage and are blocking launch for those routes. See GAP 0.**

---

## Part 2 — What's Missing (The Gaps)

Six gaps remain. They're targeted — the infrastructure is solid underneath.

---

### GAP 0 — Seed the 5 Stress-Test Corridors
**Priority: P0 — launch blocker for those routes. Can run in parallel with GAP 1.**

#### What's missing

The following 6 corridors have zero supplier coverage: FR-NO (Paris→Oslo), GB-US (London→New York), IN-DE (India→Munich), NL-SG (Amsterdam→Singapore), ES-AE (Madrid→Dubai), ES-IE (Madrid→Dublin). No discovery tool or vetting workflow helps until there is something to vet.

#### What to build

**Migration** — new file `supabase/migrations/<timestamp>_seed_stress_test_corridors.sql`:

Follow the exact pattern of `20260518100000_vendor_directory_extension.sql`. For each corridor, seed 3–5 vendors per category into the `vendors` table (which will be migrated into `suppliers` in GAP 6). Source = `'seed'`. All `is_approved = true`.

**Corridor codes to use** (add to `corridors` arrays alongside any existing global ones):

```
FR-NO, NO-FR   — Paris ↔ Oslo
GB-US, US-GB   — London ↔ New York
IN-DE, DE-IN   — India ↔ Munich
NL-SG, SG-NL   — Amsterdam ↔ Singapore
ES-AE, AE-ES   — Madrid ↔ Dubai
```

**Suggested seed vendors per corridor** (verified global providers known to cover these routes — admin confirms before merge):

| Category | FR-NO / Oslo | GB-US / New York | IN-DE / Munich | NL-SG / Singapore | ES-AE / Dubai |
|---|---|---|---|---|---|
| **Housing** | Norse Relocations, Domus Scandinavia, Krogsveen Expat | Furnished Quarters, Blueground, AKA Hotels | NoBroker Global, Nestaway Corporate, Zolo | CapitaLand Serviced, Hmlet, Figment | Asteco, Allsopp & Allsopp, CBRE UAE |
| **Immigration** | Fragomen (NO), Brækhus Law, PwC Legal NO | Fragomen (US), FordMurray, Berry Appleman | KPMG Law India, Fragomen India, Cyril Amarchand | Fragomen Singapore, Drew & Napier, Wong Partnership | Fragomen UAE, Al Tamimi & Co, BSA Ahmad Bin Hezeem |
| **Moving** | Crown Relocations, Santa Fe Relocation, Schenker | Allied Van Lines, Crown Relocations, Graebel | Crown Relocations, AGS Movers, Santa Fe | Santa Fe Relocation, Crown, Asian Tigers | AGS Movers, Crown Relocations, Allied Pickfords |
| **School search** | Oslo International School, British School Oslo, ISS | ISS, Schoolmatch NYC, Nursery World | Munich International School, ISS, NIST | Singapore American School, ISS, United World College | GEMS Education, ISS Dubai, Nord Anglia |
| **Destination** | ECA International, Cartus, Dwellworks | Aires, Cartus, Weichert | Dwellworks, Cartus, ECA International | Dwellworks, Santa Fe DSP, Crown DSP | Cartus, Aires, Dwellworks |

> These are directional — the build agent should verify each company still operates and has a corporate/expat offering before inserting. The names are well-known international providers with documented coverage in these cities.

**Also add to `catalog_destination_allowlist`** in the same migration (so the discovery tool can fire on these cities without an admin ticket):

```sql
INSERT INTO public.catalog_destination_allowlist (city, country, notes)
VALUES
  ('Oslo',      'NO', 'Stress-test corridor FR-NO'),
  ('London',    'GB', 'Stress-test corridor GB-US'),
  ('New York',  'US', 'Stress-test corridor GB-US'),
  ('Mumbai',    'IN', 'Stress-test corridor IN-DE'),
  ('Bangalore', 'IN', 'Stress-test corridor IN-DE'),
  ('Delhi',     'IN', 'Stress-test corridor IN-DE'),
  ('Munich',    'DE', 'Stress-test corridor IN-DE'),
  ('Amsterdam', 'NL', 'Stress-test corridor NL-SG'),
  ('Singapore', 'SG', 'Stress-test corridor NL-SG'),
  ('Madrid',    'ES', 'Stress-test corridor ES-AE'),
  ('Dubai',     'AE', 'Stress-test corridor ES-AE')
ON CONFLICT DO NOTHING;
```

#### Acceptance criteria
- All 8 locked corridors show ≥ 3 approved vendor entries per service category in the coverage dashboard (`GET /api/admin/catalog/intake-corridors` returns no uncovered categories for these cities)
- All 5 new destination cities appear in `catalog_destination_allowlist`
- No duplicate entries if migration is re-run (use `ON CONFLICT DO NOTHING`)
- `pytest` passes — no existing tests broken

---

### GAP 1 — Source + Vetting Fields on Supplier Capabilities
**Priority: P0 — everything else depends on this**

#### What's missing
`supplier_service_capabilities` has no `platform_vetting_status`, no `vetted_by`, no `vetted_at`, no `vetting_notes`. `suppliers` has no `source` enum or `source_url`. The `verified` boolean on suppliers is too coarse — it's not a workflow, it's a flag.

`service_catalog_items` already has a `source` enum, but that's a different table from the main supplier registry. The gap is that the supplier registry itself has no provenance or vetting lifecycle.

#### What to build

**Migration** — new file `supabase/migrations/<timestamp>_supplier_vetting_provenance.sql`:

```sql
BEGIN;

-- Source provenance on the supplier entity
ALTER TABLE public.suppliers
  ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'admin_manual'
    CHECK (source IN ('admin_manual', 'customer_upload', 'scraper_discovery', 'directory_import')),
  ADD COLUMN IF NOT EXISTS source_url text NULL,
  ADD COLUMN IF NOT EXISTS source_reference text NULL; -- e.g. EuRA member ID, FIDI number, scrape batch ID

-- Per-service-offering vetting lifecycle
ALTER TABLE public.supplier_service_capabilities
  ADD COLUMN IF NOT EXISTS platform_vetting_status text NOT NULL DEFAULT 'pending'
    CHECK (platform_vetting_status IN ('pending', 'approved', 'rejected', 'suspended')),
  ADD COLUMN IF NOT EXISTS vetted_by uuid NULL,           -- references auth.users.id
  ADD COLUMN IF NOT EXISTS vetted_at timestamptz NULL,
  ADD COLUMN IF NOT EXISTS vetting_notes text NULL;

CREATE INDEX IF NOT EXISTS idx_supplier_capabilities_vetting
  ON public.supplier_service_capabilities (platform_vetting_status);

COMMIT;
```

> **Important**: No RLS change needed — the existing supplier RLS policies already scope correctly. Backfill: existing capabilities where `suppliers.status = 'active'` should default to `platform_vetting_status = 'approved'` so nothing breaks in production. Add a second statement:
> ```sql
> UPDATE public.supplier_service_capabilities ssc
> SET platform_vetting_status = 'approved'
> FROM public.suppliers s
> WHERE ssc.supplier_id = s.id AND s.status = 'active';
> ```

**Backend** — update `backend/app/services/supplier_registry.py`:
- `create_supplier()`: accept `source`, `source_url`, `source_reference` in payload, write to suppliers
- `add_capability()`: accept `platform_vetting_status` (default `pending`), write to capabilities
- `approve_capability(session, capability_id, vetted_by_user_id, notes)`: new function — sets status to `approved`, stamps vetted_by + vetted_at
- `reject_capability(session, capability_id, vetted_by_user_id, notes)`: new function — sets status to `rejected`, requires notes (raise ValueError if empty)
- Update `list_suppliers()` and `search_by_service_destination()` serialization to include new fields

**Backend** — update `backend/app/routers/suppliers.py`:
- `POST /api/suppliers/{id}/capabilities/{cap_id}/approve` — calls `approve_capability`, requires admin
- `POST /api/suppliers/{id}/capabilities/{cap_id}/reject` — calls `reject_capability`, requires admin, body must include `notes`
- Update existing routes to surface `source`, `platform_vetting_status` in response shapes

**Backend** — update `backend/main.py`:
- Register the updated suppliers router (it's already there — just verify the new endpoints show up via the verification command in CLAUDE.md)

**Frontend** — update `AdminSupplierDetail.tsx`:
- In the capability card, add a status badge showing `platform_vetting_status` (pending = yellow, approved = green, rejected = red)
- Add Approve / Reject buttons visible to admin, with a notes input that blocks rejection without text
- Show `source` and `source_url` in the supplier header section

#### Acceptance criteria
- A newly created supplier capability defaults to `pending`
- Admin clicking Approve: status → `approved`, vetted_by populated, vetted_at set, notes saved
- Admin clicking Reject without notes: blocked with validation error
- Existing active suppliers' capabilities remain `approved` after migration (backfill)
- `tsc --noEmit` passes, `pytest` passes

---

### GAP 2 — Admin Vetting Queue UI
**Priority: P1 — workflow depends on GAP 1**

#### What's missing
There is no queue showing "pending capabilities awaiting review." AdminSuppliers shows a flat list filtered by supplier status, but you can't see a cross-supplier view of capabilities that need vetting decisions.

#### What to build

**Backend** — new endpoint in `backend/app/routers/suppliers.py`:
```
GET /api/suppliers/capabilities/pending
```
Returns: `[{supplier_id, supplier_name, capability_id, service_category, country_code, city_name, source, source_url, created_at}]` — all capabilities where `platform_vetting_status = 'pending'`, ordered by `created_at ASC` (oldest first). Requires admin.

Register in both `backend/app/main.py` and `backend/main.py` per CLAUDE.md hard rule.

**Frontend** — new page `frontend/src/pages/admin/AdminVettingQueue.tsx`:
- Table: supplier name, service category, country/city, source (badge), date discovered
- Row click: opens `AdminSupplierDetail` for that supplier (or inline side panel)
- Approve / Reject buttons per row, reject requires a notes input
- Empty state: "No pending capabilities — catalog is fully reviewed"
- Badge count in admin sidebar nav showing pending count (reuse `/api/admin/catalog/notification-counts` pattern or add a new count to that endpoint)

**Route** — add to `frontend/src/App.tsx` and `frontend/src/navigation/routes.ts`:
```
/admin/vetting-queue → AdminVettingQueue (lazy loaded, admin-only guard)
```

**Sidebar** — add "Vetting Queue" link in `PlatformShellSidebar.tsx` / admin nav with the badge count.

#### Acceptance criteria
- Queue shows all pending capabilities across all suppliers
- Admin can approve/reject directly from the queue without navigating to supplier detail
- Badge count updates after each decision
- Queue is empty after all decisions made

---

### GAP 3 — Recommendation Engine Hard-Filter on Vetting Status
**Priority: P1 — employees must never see unapproved suppliers**

#### What's missing
The recommendation plugins query `search_by_service_destination()` in `supplier_registry.py`, but that function does not filter on `platform_vetting_status`. A pending or rejected capability could surface in recommendations.

#### What to build

**Backend** — update `backend/app/services/supplier_registry.py`:

In `search_by_service_destination()`, add mandatory filter:
```python
q = q.filter(SupplierServiceCapability.platform_vetting_status == 'approved')
```
This is a one-line change but it's load-bearing. Add to the query before the limit/offset.

Also filter `suppliers.status = 'active'` in the same query (it may already be there — verify).

**Backend** — update `backend/app/recommendations/plugins/base.py` (or whichever base class all plugins inherit from):
- If plugins construct their own queries rather than calling `search_by_service_destination`, each plugin needs the same filter applied. Audit all 14 plugins to confirm they go through the central function. If any bypass it, add the filter directly.

**Test** — add to `backend/tests/` (or wherever recommendation tests live):
- Test that a supplier with `platform_vetting_status = 'pending'` does NOT appear in recommendation results
- Test that a supplier with `platform_vetting_status = 'approved'` DOES appear

#### Acceptance criteria
- No pending or rejected capability appears in recommendation output
- Existing approved suppliers continue to appear normally
- Test passes with `pytest`

---

### GAP 4 — HR Preferred Supplier Write Access
**Priority: P2 — flywheel mechanism**

#### What's missing
The `company_preferred_suppliers` table exists but has **no HR-write RLS policy** — only `service_role` can write. There is no API endpoint for HR to add/remove their preferred suppliers, and no frontend UI for it.

Note: `company_vendor_selections` does have HR write access and is a parallel system. For the preferred supplier flywheel, use `company_preferred_suppliers` as it's the simpler, more direct model.

#### What to build

**Migration** — new file `supabase/migrations/<timestamp>_company_preferred_suppliers_hr_rls.sql`:
```sql
BEGIN;

-- HR can read and write their own company's preferred suppliers
DROP POLICY IF EXISTS company_preferred_suppliers_hr_select ON public.company_preferred_suppliers;
CREATE POLICY company_preferred_suppliers_hr_select ON public.company_preferred_suppliers
  FOR SELECT TO authenticated
  USING (
    company_id IN (
      SELECT company_id::text FROM public.profiles WHERE id::uuid = auth.uid()
    )
  );

DROP POLICY IF EXISTS company_preferred_suppliers_hr_insert ON public.company_preferred_suppliers;
CREATE POLICY company_preferred_suppliers_hr_insert ON public.company_preferred_suppliers
  FOR INSERT TO authenticated
  WITH CHECK (
    company_id IN (
      SELECT company_id::text FROM public.profiles
      WHERE id::uuid = auth.uid() AND role IN ('HR', 'ADMIN')
    )
  );

DROP POLICY IF EXISTS company_preferred_suppliers_hr_delete ON public.company_preferred_suppliers;
CREATE POLICY company_preferred_suppliers_hr_delete ON public.company_preferred_suppliers
  FOR DELETE TO authenticated
  USING (
    company_id IN (
      SELECT company_id::text FROM public.profiles
      WHERE id::uuid = auth.uid() AND role IN ('HR', 'ADMIN')
    )
  );

COMMIT;
```

**Backend** — new router `backend/app/routers/hr_preferred_suppliers.py`:
```
GET  /api/hr/preferred-suppliers           — list company's preferred suppliers (HR/Admin)
POST /api/hr/preferred-suppliers           — add a preferred supplier by supplier_id + service_category
DELETE /api/hr/preferred-suppliers/{id}    — remove a preference
```

On POST: validate `supplier_id` exists and has an `approved` capability for the given `service_category`. Create the row with the caller's `company_id` from their profile. If the supplier has no matching approved capability yet, still create the preference but flag it as `pending_platform_review` in the notes.

Register in both `backend/app/main.py` and `backend/main.py`.

**Frontend** — new page `frontend/src/features/platform-v2/hr-preferred-suppliers/HrPreferredSuppliersPage.tsx`:
- List current preferred suppliers per category
- Search/browse approved catalog suppliers to add
- "Add as preferred" button per supplier per service category
- Remove button with confirmation
- Route: `/hr/preferred-suppliers` in HR nav

**Recommendation engine** — update `marketplace.py` `_get_preferred_supplier_ids()` to read from `company_preferred_suppliers` via the FastAPI/SQLAlchemy layer rather than a raw query if it isn't already, and ensure results surface first in the recommendation ranking.

#### Acceptance criteria
- HR user can add a supplier from the approved catalog as preferred
- That supplier surfaces first for their company's employees in the relevant service category
- HR from Company A cannot see Company B's preferred suppliers (RLS test)
- Admin can still manage via the existing service_role bypass

---

### GAP 5 — Real Supplier Discovery (Replace/Augment LLM Scraper)
**Priority: P3 — expansion tool, not launch blocker**

#### What's missing
`catalog_scraper.py` uses OpenAI to *generate* plausible vendor names from training data — it is not grounded in real businesses. The original prompt chain proposed Google Maps via Apify or the Google Places API. These return real businesses with real contact info, websites, ratings, and reviews. The LLM approach is useful for brainstorming but insufficient for building a trustworthy supplier catalog.

The existing scraper infrastructure (allowlist, quota, admin UI) is solid and reusable. Only the data source needs replacing or augmenting.

#### What to build

**Backend** — new service `backend/app/services/maps_discovery.py`:

```python
"""
Google Places / Apify discovery adapter.
Replaces the LLM synthesis in catalog_scraper.py with real business data.

Provider is configured via env:
  DISCOVERY_PROVIDER=google_places | apify | disabled (default)
  GOOGLE_PLACES_API_KEY=...
  APIFY_API_TOKEN=...

Returns: list of dicts with name, website, phone, address, rating, 
         review_count, place_id (source_url), category_matches
"""
```

Implement `search_businesses(category: str, city: str, country: str) -> list[dict]` which:
1. Maps ReloPass service category slug to a search keyword (e.g. `movers` → `"international moving company"`, `legal_admin` → `"immigration lawyer expats"`, `living_areas` → `"furnished apartments corporate housing"`)
2. Calls Google Places API Text Search or Apify `compass/crawler-google-places` actor
3. Returns structured results — name, website, phone, formatted_address, rating, user_ratings_total, place_id as source_url

Provider is configured by env var so you can swap from Apify → Google Places → disabled without code changes. When `DISCOVERY_PROVIDER=disabled` (default), returns `[]` cleanly.

**Backend** — new admin endpoint in `backend/app/routers/admin_catalog.py`:
```
POST /api/admin/catalog/discover
Body: { category: str, city: str, country: str }
```
- Checks allowlist (reuse existing `scrape_safety.is_destination_allowlisted`)
- Calls `maps_discovery.search_businesses()`
- Returns raw results WITHOUT writing to DB — admin reviews first
- Separate endpoint `POST /api/admin/catalog/discover/import` accepts selected items and creates suppliers + pending capabilities

**Frontend** — new tab in `AdminCatalogQueuePage.tsx` called "Discover":
- Category dropdown (from ReloPass taxonomy), city + country inputs
- "Search" button — calls `/api/admin/catalog/discover`, shows results table
- Results: name, website, rating, review count, address, "Add to catalog" checkbox per row
- "Import selected" button — calls `/api/admin/catalog/discover/import` with checked rows
- Imported items land in the vetting queue as `platform_vetting_status = 'pending'`, `source = 'scraper_discovery'`, `source_url = place_id` (Google Maps link)
- Already-in-catalog items shown with a "Already exists" badge (deduplication by website domain or name similarity)

#### API key configuration
Admin settings should surface a read-only indicator of which provider is active (green/grey) based on env var state. Do NOT expose the key itself in the UI.

#### Acceptance criteria
- Admin searches "movers" + "Paris" + "France" → receives real Google Places results
- Selecting 3 results and importing → 3 suppliers created with pending capabilities in vetting queue
- Source URL stored as Google Maps place link
- With `DISCOVERY_PROVIDER=disabled`, the endpoint returns `[]` with no error
- Deduplication correctly flags businesses already in catalog

---

### GAP 6 — Resolve the Two-System Confusion
**Priority: P2 — architectural clarity, avoids compounding debt**

#### What's missing
There are currently two parallel supplier data systems:

**System A** — `suppliers` + `supplier_service_capabilities` + `supplier_scoring_metadata`
- ORM-based (SQLAlchemy models in `backend/app/models.py`)
- Powers `AdminSuppliers`, `AdminSupplierDetail`, the recommendations plugins, the RFQ flow
- No real seeded data for main corridors

**System B** — `vendors` + `service_catalog_items` + `company_vendor_selections`
- SQL-based (raw queries via `database.py`)
- Powers `hr_vendors.py`, `admin_catalog.py`, `marketplace.py`
- Has the 25 real seeded vendors

Both systems are partially bridged by migration `20260626000000_backfill_service_catalog_masters_from_registry.sql` which copies System A suppliers into System B's `service_catalog_items`, but they remain independent write surfaces.

This creates confusion: when GAP 1 adds vetting to `supplier_service_capabilities`, do the vendors in the `vendors` table also need vetting? When GAP 5 discovers new suppliers, which table do they go into?

#### Decision required (before building)

You need to pick one of two paths:

**Option A — Converge on System A** (recommended):
- System A (`suppliers` + `supplier_service_capabilities`) becomes the single source of truth
- Migrate the 25 real vendors from `vendors` into System A via a data migration script
- Update `hr_vendors.py` and `marketplace.py` to query System A instead of `vendors`
- Deprecate `vendors` as a write surface (keep for legacy reads with a VIEW if needed)
- All future work (GAP 1 through GAP 5) targets System A exclusively

**Option B — Converge on System B** (more disruptive):
- System B (`service_catalog_items`) becomes truth
- All recommendation plugins re-point to it
- The ORM models become facades

Option A is recommended because System A has the richer data model (capabilities, scoring, ORM types), the admin UI is built on it, and the new vetting fields in GAP 1 go there.

#### What to build (Option A path)

**Script** `backend/scripts/migrate_vendors_to_suppliers.py`:
- Read all rows from `vendors` where `is_active = true`
- For each, upsert into `suppliers` (id = generated UUID, name = vendor.name, source = 'admin_manual', status = 'active')
- For each service type in `vendor.service_types`, insert a row in `supplier_service_capabilities` (service_category = service_type, coverage_scope_type = 'corridor', country_code from corridors array, `platform_vetting_status = 'approved'`)
- Idempotent — skip if supplier with same name + website already exists
- Run once as: `python -m backend.scripts.migrate_vendors_to_suppliers`

**Migration** — after running the script, create `supabase/migrations/<timestamp>_deprecate_vendors_write.sql`:
- Add comment: `-- vendors table is now read-only; write surface is suppliers + supplier_service_capabilities`
- Revoke INSERT/UPDATE on `vendors` from `authenticated` role (keep SELECT for backward compat)

**Backend** — update `backend/app/routers/hr_vendors.py`:
- Rewrite queries to read from `supplier_service_capabilities JOIN suppliers` instead of `vendors`
- Map column names to preserve the existing response shape so frontend doesn't break
- Test against existing HR vendor page

#### Acceptance criteria
- 25 seeded vendors appear in `suppliers` + `supplier_service_capabilities` after migration
- `AdminSuppliers` page shows all previously-seeded vendors
- HR vendor list returns same results as before (same names, same corridors)
- `vendors` table becomes read-only (INSERT returns 403/RLS error)

---

## Part 3 — Build Order & Tool/Model Recommendations

### Sequencing

```
GAP 0 (stress-test corridor seeding) ─┐
GAP 1 (vetting fields + source)       ├─ run in parallel, both P0
                                      ↓
GAP 3 (recommendation filter) — can parallel with GAP 2
GAP 2 (vetting queue UI)
                                      ↓
GAP 6 (system unification) — before GAP 5 to clarify which table receives discoveries
                                      ↓
GAP 5 (maps discovery)
                                      ↓
GAP 4 (HR preferred supplier upload)
```

GAP 0 and GAP 1 can be built simultaneously — they touch different tables. GAP 6 must precede GAP 5 so there is no ambiguity about where discovered suppliers land.

---

### Tool: Use Claude Code CLI with the `relopass-dev-queue` skill

All six gaps are code implementation tasks — migrations, backend Python, frontend TypeScript. The right tool is **Claude Code CLI** running in an interactive session with the repo mounted, using the `relopass-dev-queue` skill which handles the full lifecycle: fetch Notion task → codebase recon → plan → approval gate → implement → validate → commit.

**Do not use Cowork for these tasks.** Cowork (what generated this spec) can't run `tsc --noEmit`, run `pytest`, or do iterative file editing across the dual-router registration pattern without risk of missing the second registration.

**How to launch:**
1. Open Claude Code CLI in your terminal from the repo root
2. Type `/relopass-dev-queue` or start a session and the skill will trigger
3. Reference this spec file: `docs/supplier-catalog-spec.md`
4. For each gap, create a Notion task (or paste the gap spec directly) and let the skill execute

**For each Claude Code session, include in the context:**
```
Read docs/supplier-catalog-spec.md GAP N before starting.
Remember the dual-router registration rule from CLAUDE.md: every new router 
goes in BOTH backend/app/main.py AND backend/main.py.
Run python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if '<prefix>' in r.path))" to verify after registering.
Run cd frontend && npx tsc --noEmit after every frontend change.
```

---

### Model Recommendations per Gap

| Gap | Task type | Recommended model | Why |
|---|---|---|---|
| GAP 0 — Stress-test corridor seeding | SQL migration with real vendor data | **claude-sonnet-5** | Pure data entry following the existing seed pattern; verify vendor names before merge |
| GAP 1 — Vetting fields migration + service layer | SQL migration + Python service update | **claude-sonnet-5** | Mechanical but precise; follows existing patterns in supplier_registry.py |
| GAP 2 — Vetting queue UI | React/TypeScript new page | **claude-sonnet-5** | Existing admin pages are clear patterns to follow |
| GAP 3 — Recommendation filter | One-line Python change + tests | **claude-sonnet-5** | Simple but needs careful test coverage |
| GAP 4 — HR preferred suppliers | Migration + router + frontend | **claude-sonnet-5** | Multi-file but each piece is well-defined |
| GAP 5 — Maps discovery adapter | New service with external API + admin UI | **claude-opus-4-8** | External API integration with pluggable provider design requires more reasoning |
| GAP 6 — System unification | Architecture decision + data migration + router rewrite | **claude-opus-4-8** | Highest risk of subtle regression; needs to reason about both systems holistically |

**General rule:** Use `claude-sonnet-5` for tasks where the pattern is already visible in the codebase. Use `claude-opus-4-8` when the task involves cross-system reasoning, new architecture, or external integrations where a subtle mistake is costly.

---

## Part 4 — Validation Checklist (Copy into each Notion task)

Use this checklist as acceptance criteria for every gap:

```
[ ] Migration file exists in supabase/migrations/ with correct timestamp format
[ ] RLS enabled on any new table; at least one policy defined; anon revoked
[ ] New router registered in BOTH backend/app/main.py AND backend/main.py
[ ] Route verified with: python3 -c "from backend.main import app; print(...)"
[ ] cd frontend && npx tsc --noEmit passes with zero errors
[ ] cd backend && pytest passes (or new tests added for new behavior)
[ ] Pending capability does NOT appear in recommendation results (test)
[ ] Approved capability DOES appear in recommendation results (test)
[ ] No existing functionality broken (smoke test AdminSuppliers, HR vendor list, employee recommendations)
```

---

## Quick Reference — Key Files

```
backend/app/models.py                           Supplier, SupplierServiceCapability, SupplierScoringMetadata ORM models
backend/app/services/supplier_registry.py       Service layer for all supplier CRUD
backend/app/services/catalog_scraper.py         LLM scraper (to be augmented by GAP 5)
backend/app/services/service_catalog.py         service_catalog_items CRUD
backend/app/routers/suppliers.py               Admin supplier endpoints
backend/app/routers/admin_catalog.py           Admin catalog + demand gaps + allowlist
backend/app/routers/hr_vendors.py              HR vendor list (reads vendors table — to change in GAP 6)
backend/app/routers/marketplace.py             Employee recommendations join
backend/app/recommendations/plugins/           14 recommendation plugins
frontend/src/pages/admin/AdminSuppliers.tsx    Supplier list
frontend/src/pages/admin/AdminSupplierDetail.tsx  Supplier detail + capability management
frontend/src/pages/admin/AdminCatalogQueuePage.tsx  Allowlist + demand gaps + tickets
supabase/migrations/20260312100000_supplier_registry.sql  Base schema
supabase/migrations/20260328000000_company_preferred_suppliers.sql  Preference table
supabase/migrations/20260518100000_vendor_directory_extension.sql  Real seeded vendors
```
