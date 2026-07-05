# Supplier systems — real state (2026-07-05)

ReloPass historically had two parallel supplier data surfaces. This documents the
**verified prod reality** (queried directly on project `nsvefcvpvwwwhuqyuqmp`) and
the convergence decision, correcting the stale premises in
`docs/supplier-catalog-spec.md`.

## Source of truth: System A — `suppliers` + `supplier_service_capabilities`

- **~82 suppliers / ~80 capabilities** in prod (living_areas, schools, movers),
  derived from the recommendation datasets via `backend/app/seed_suppliers.py`.
- ORM: `backend/app/models.py` (`Supplier`, `SupplierServiceCapability`).
- Powers: employee recommendations (`recommendations/engine.py`), the marketplace,
  RFQ supplier detail, `AdminSuppliers`/`AdminSupplierDetail`, the GAP 1–5 vetting
  lifecycle (`platform_vetting_status`), HR preferred suppliers, and maps discovery.
- **This is the only surface new work should target.**

## Retained read-only: System B — `vendors`

- Prod is the **redesign schema** (`is_active`, `corridor_codes[]`,
  `countries_served[]`, `email`, label `category`, wildcard corridors) — NOT the
  columns in the March migration files. It holds **~8 demo rows**.
- The migration-file history is misleading: `20260518100000` seeded 25 rows using
  March-shape columns, but `20260520000000` runs a guarded `DROP TABLE … CASCADE`
  (whenever `slug` is absent) and recreates the redesign shape + re-seeds 8 rows,
  so the 25-row seed is dead and never reached prod. `20260823000000`'s original
  vendor seed (old columns) likewise could not apply and was removed.
- Still read by: `hr_vendors.py` (legacy HR "Service providers" list),
  `hr_rfq.py` + `db/vendors.py` (`validate_vendor_ids`, RFQ vendor-name join),
  `hr_vendor_performance.py`. **No backend code writes to it.**

## Convergence decision (GAP 6, lightweight)

- `backend/scripts/migrate_vendors_to_suppliers.py` copies each active vendor into
  `suppliers` (`source='directory_import'`, `vendor_id` = the vendor id) with one
  category-mapped capability marked `platform_vetting_status='pending'` — nothing is
  lost, and the demo rows don't pollute recommendations until an admin approves them.
  Idempotent; run once: `python -m backend.scripts.migrate_vendors_to_suppliers`.
- `20260825000000_deprecate_vendors_write.sql` locks `vendors` write intent
  (defense-in-depth) while keeping SELECT for RFQ.
- **Deferred:** repointing `hr_vendors`/`hr_rfq`/`hr_vendor_performance` at System A
  (a real HR-UX change — the "Service providers" list would switch from 8 curated
  demo vendors to the 82 real suppliers, and the redesign vocabulary/wildcard
  corridors need a mapping). That is its own scoped effort pending product input.
