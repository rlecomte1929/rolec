# Supplier Registry — Current State Audit

## 1. Existing Vendor/Supplier Data

### Tables (Supabase + SQLite)

| Table | Columns | Purpose |
|-------|---------|---------|
| **vendors** | id (uuid), name, service_types[], countries[], logo_url, contact_email, status, created_at | Thin provider entity for RFQ |
| **vendor_users** | user_id, vendor_id, role | Maps Supabase auth users to vendors |
| **case_vendor_shortlist** | case_id, service_key, vendor_id, selected | User shortlist per case |
| **service_recommendations** | case_id, service_key, vendor_id, match_score, estimated_min/max, metadata | Stores recommendation results (case-bound) |
| **rfq_recipients** | rfq_id, vendor_id, status | Vendors receiving RFQs |
| **quotes** | rfq_id, vendor_id, total_amount, status | Vendor quotes |

### Gaps in vendors

- No `legal_name`, `description`, `website`, `contact_phone`
- No `languages_supported`, `verified`, `updated_at`
- No per-service capabilities (only `service_types[]`, `countries[]`)
- No budget ranges, specialization, family/corporate flags
- No scoring metadata (rating, SLA, preferred_partner)
- Minimal schema; not suitable for recommendation matching

---

## 2. Recommendation Data Sources

### Current: JSON datasets (static files)

| Dataset | Item shape | Service category |
|---------|------------|------------------|
| living_areas.json | item_id, name, city, avg_rent_*, commute_*, tags, rating | living_areas |
| schools.json | item_id, name, city, type, curriculum, tuition_level | schools |
| movers.json | item_id, name, service_areas[], international_capable, max_volume_m3 | movers |
| banks.json | item_id, name | banks |
| insurance.json | item_id, name | insurance |
| electricity.json | item_id, name, green_options, contract_flexibility | electricity |
| childcare, medical, telecom, etc. | Similar item_id/name + category-specific | Various |

**Flow:** Plugins call `load_dataset()` → read JSON → score each item → return top N. No DB lookup.

### Gap

- Recommendations are **decoupled** from vendors table
- RFQ uses `vendor_ids` but frontend passes `item_id` (e.g. "m-1") — **mismatch**: item_id ≠ vendor uuid
- No single source of truth linking recommended items to vendors/suppliers

---

## 3. Supplier-Related API Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/rfqs` | POST | Create RFQ; accepts `vendor_ids` |
| (internal) `db.create_rfq` | — | Inserts rfq, rfq_items, rfq_recipients |

**Gaps:** No supplier/vendor list, search, or filter APIs. No admin CRUD for vendors.

---

## 4. Admin Pages

- **VendorInbox** (`/vendor/inbox`) — Placeholder: "RFQs assigned to your vendor account"
- **VendorRfq** (`/vendor/rfq/:id`) — RFQ detail (vendor view)
- **AdminResourceEditor** — Resources CMS, not vendors
- **ServicesRfqNew** — RFQ builder; uses recommendation `item_id` as vendor_id (broken)

**Gaps:** No admin UI to list/edit vendors or suppliers.

---

## 5. Seed Data

- No vendor seed files found
- Recommendations use static JSON only
- `service_recommendations` and `case_vendor_shortlist` are populated at runtime from recommendations flow, but vendor_id comes from item_id (string) which does not match vendors.id (uuid)

---

## 6. Summary

| Area | State | Gap |
|------|-------|-----|
| Vendor table | Thin schema | Missing contact, capabilities, scoring |
| Recommendation source | JSON files | No DB registry; not linked to vendors |
| RFQ ↔ Recommendations | Broken | item_id ≠ vendor uuid |
| Admin supplier UI | None | No list/filter/detail |
| Supplier capabilities | None | No per-service, geo, budget, tags |
