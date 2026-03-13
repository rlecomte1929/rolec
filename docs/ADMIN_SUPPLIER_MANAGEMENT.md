# Admin Supplier Management

Admin interface and backend management layer for maintaining suppliers in the Supplier Registry.

## 1. Files Changed

| Path | Change |
|------|--------|
| `backend/app/services/supplier_validation.py` | **New** – validation rules, valid categories, duplicate check |
| `backend/app/services/supplier_registry.py` | Added `update_supplier`, `set_supplier_status`, `add_capability`, `update_capability`, `remove_capability`, `update_scoring` |
| `backend/app/routers/suppliers.py` | Added create, update, status, capabilities, scoring routes |
| `frontend/src/api/client.ts` | Added `create`, `update`, `setStatus`, `addCapability`, `updateCapability`, `removeCapability`, `updateScoring`, `getCategories` |
| `frontend/src/navigation/routes.ts` | Added `adminSuppliersNew` |
| `frontend/src/App.tsx` | Added route for `AdminSupplierNew` |
| `frontend/src/pages/admin/AdminSuppliers.tsx` | Added "Create supplier" button |
| `frontend/src/pages/admin/AdminSupplierNew.tsx` | **New** – create supplier form |
| `frontend/src/pages/admin/AdminSupplierDetail.tsx` | Rewritten as edit page with capability editor, scoring, status controls |

---

## 2. Backend Admin Routes

All require `require_admin` (Bearer token, admin role).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/suppliers/categories` | List valid service categories |
| GET | `/api/suppliers` | List suppliers (filter: status, service_category, country_code, city_name) |
| GET | `/api/suppliers/search` | Search by service + destination |
| POST | `/api/suppliers` | Create supplier |
| GET | `/api/suppliers/{id}` | Get supplier detail |
| PATCH | `/api/suppliers/{id}` | Update supplier |
| PATCH | `/api/suppliers/{id}/status` | Set status (active \| inactive \| draft) |
| POST | `/api/suppliers/{id}/capabilities` | Add capability |
| PATCH | `/api/suppliers/{id}/capabilities/{cap_id}` | Update capability |
| DELETE | `/api/suppliers/{id}/capabilities/{cap_id}` | Remove capability |
| PATCH | `/api/suppliers/{id}/scoring` | Update scoring/verification metadata |

---

## 3. Frontend Admin Pages

| Path | Page | Description |
|------|------|-------------|
| `/admin/suppliers` | AdminSuppliers | Supplier list with filters; "Create supplier" button |
| `/admin/suppliers/new` | AdminSupplierNew | Create supplier form (details, scoring, capabilities) |
| `/admin/suppliers/:id` | AdminSupplierDetail | Edit supplier: details, status, capabilities, scoring |

All under `RequireAdminRoute`; non-admins are redirected.

---

## 4. Validation Rules

- **No duplicate capability**: Same `(supplier_id, service_category, coverage_scope_type, country_code, city_name)` is rejected.
- **Required for active**: `name` must be non-empty.
- **Valid service categories**: Must be in recommendation registry (living_areas, schools, movers, banks, etc.).
- **Valid status**: `active`, `inactive`, `draft`.
- **Valid coverage_scope_type**: `global`, `country`, `city`.
- **Coverage constraints**:
  - `country`: `country_code` required (2-letter).
  - `city`: `country_code` and `city_name` required.
- **Budget**: `min_budget` and `max_budget` must be ≥ 0; `min_budget` ≤ `max_budget`.

---

## 5. Verification Steps

1. **Backend**
   - Ensure admin user/token.
   - `POST /api/suppliers` with valid payload → 200, returns created supplier.
   - `PATCH /api/suppliers/{id}` → 200, returns updated supplier.
   - `PATCH /api/suppliers/{id}/status` with `{"status":"inactive"}` → 200.
   - `POST /api/suppliers/{id}/capabilities` with valid capability → 200.
   - `DELETE /api/suppliers/{id}/capabilities/{cap_id}` → 200.
   - Non-admin → 403 on all above.

2. **Frontend**
   - Log in as admin.
   - Go to `/admin/suppliers` → list loads.
   - Click "Create supplier" → `/admin/suppliers/new` → fill form → submit → redirects to detail.
   - Open supplier detail → edit fields, change status, add/remove capabilities, save scoring.

3. **Validation**
   - Create supplier with duplicate capability → 400.
   - Add capability with invalid `service_category` → 400.

---

## 6. Deferred Items

- **Capability inline edit**: Detail page supports add/remove only; full inline edit of existing capability deferred.
- **Country/city autocomplete**: Free text for country_code and city_name; no autocomplete.
- **Bulk import**: No CSV/Excel import.
- **Audit log**: No history of who changed what.
- **Soft delete**: Deactivate only; no soft delete of supplier.
