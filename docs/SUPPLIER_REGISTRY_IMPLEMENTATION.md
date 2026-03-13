# Supplier Registry — Implementation Summary

## 1. Current State Audit

See [SUPPLIER_REGISTRY_AUDIT.md](./SUPPLIER_REGISTRY_AUDIT.md) for full audit.

**Summary:** Vendors table is thin; recommendations use static JSON; no link between item_id and vendor UUID; RFQ flow broken for recommendations.

---

## 2. Proposed Schema

### A. suppliers
| Column | Type | Description |
|--------|------|-------------|
| id | uuid/string | Primary key |
| name | text | Display name |
| legal_name | text | Legal entity name |
| status | text | active, inactive, draft |
| description | text | Long description |
| website | text | URL |
| contact_email | text | |
| contact_phone | text | |
| languages_supported | text[]/json | Array of language codes |
| verified | boolean | Verified supplier flag |
| vendor_id | uuid | FK to vendors (for RFQ) |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### B. supplier_service_capabilities
| Column | Type | Description |
|--------|------|-------------|
| id | uuid | PK |
| supplier_id | uuid | FK suppliers |
| service_category | text | living_areas, schools, movers, etc. |
| coverage_scope_type | text | global, country, city |
| country_code | text | e.g. SG, US |
| city_name | text | e.g. Singapore |
| specialization_tags | text[] | e.g. packing, storage |
| min_budget | numeric | |
| max_budget | numeric | |
| family_support | boolean | |
| corporate_clients | boolean | |
| remote_support | boolean | |
| notes | text | |

### C. supplier_scoring_metadata
| Column | Type | Description |
|--------|------|-------------|
| supplier_id | uuid | PK, FK suppliers |
| average_rating | numeric | |
| review_count | int | |
| response_sla_hours | int | |
| preferred_partner | boolean | |
| premium_partner | boolean | |
| last_verified_at | timestamptz | |

---

## 3. Files Changed

| File | Change |
|------|--------|
| `docs/SUPPLIER_REGISTRY_AUDIT.md` | **New** — Audit report |
| `docs/SUPPLIER_REGISTRY_IMPLEMENTATION.md` | **New** — This file |
| `supabase/migrations/20260312000000_supplier_registry.sql` | **New** — Postgres migration |
| `backend/app/models.py` | Added Supplier, SupplierServiceCapability, SupplierScoringMetadata |
| `backend/app/services/supplier_registry.py` | **New** — CRUD, list, search_by_service_destination |
| `backend/app/routers/suppliers.py` | **New** — GET list, search, detail |
| `backend/app/seed_suppliers.py` | **New** — Seed from movers.json |
| `backend/app/recommendations/engine.py` | Added _load_dataset_with_registry; merges registry items |
| `backend/main.py` | Router, seed_suppliers_from_movers |
| `frontend/src/api/client.ts` | Added suppliersAPI |
| `frontend/src/navigation/routes.ts` | adminSuppliers, adminSuppliersDetail |
| `frontend/src/pages/admin/AdminSuppliers.tsx` | **New** — List + filters |
| `frontend/src/pages/admin/AdminSupplierDetail.tsx` | **New** — Detail view |
| `frontend/src/pages/admin/AdminLayout.tsx` | Nav link Suppliers |
| `frontend/src/App.tsx` | Routes for AdminSuppliers, AdminSupplierDetail |

---

## 4. Migration SQL

Located at `supabase/migrations/20260312000000_supplier_registry.sql`.

For SQLite (local dev), tables are created via SQLAlchemy `init_db()` from models.

---

## 5. Backend APIs

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/suppliers` | GET | Admin | List with filters: status, service_category, country_code, city_name |
| `/api/suppliers/search` | GET | Admin | Search by service_category + destination_country/city |
| `/api/suppliers/{id}` | GET | Admin | Supplier detail with capabilities and scoring |

---

## 6. Frontend Pages/Components

- **AdminSuppliers** (`/admin/suppliers`) — Table with filters (status, service, country); row click → detail
- **AdminSupplierDetail** (`/admin/suppliers/:id`) — Details, scoring, service capabilities

---

## 7. Verification Steps

1. **Backend**
   - [ ] `uvicorn backend.main:app` starts without error
   - [ ] `GET /api/suppliers` returns 200 (admin token)
   - [ ] Seed creates suppliers from movers.json on startup
   - [ ] `GET /api/suppliers?service_category=movers` filters correctly
   - [ ] `GET /api/suppliers/{id}` returns detail

2. **Frontend**
   - [ ] Navigate to Admin → Suppliers
   - [ ] List loads (empty or seeded)
   - [ ] Filters work
   - [ ] Click row or View → detail page

3. **Recommendation compatibility**
   - [ ] With seeded movers suppliers, recommendation for movers + Singapore returns registry items merged with JSON
   - [ ] Registry items have `_source: "supplier_registry"` in metadata

4. **Migration**
   - [ ] Run `supabase db push` or apply migration
   - [ ] Tables suppliers, supplier_service_capabilities, supplier_scoring_metadata exist

---

## 8. Deferred Items

- **supplier_contacts** — Per-contact records
- **supplier_documents** — Attachments/certifications
- **supplier_integrations** — API/SSO links
- **Vendor linking** — Create/update vendors when suppliers are added; sync for RFQ
- **Admin create/edit** — Full CRUD UI for suppliers
- **Import from JSON** — Bulk import from all recommendation datasets
- **RFQ fix** — Map recommendation item_id to vendor_id via supplier.vendor_id
