# RFQ & Quote Workflow

End-to-end flow for creating RFQs, vendor responses, and quote comparison.

## Supplier ↔ Vendor Mapping

- **Suppliers** (supplier registry): recommendations source. `supplier.id` = item_id in recommendations.
- **Vendors** (vendors table): RFQ recipients. `rfq_recipients.vendor_id` links to vendors.
- **Bridge**: `supplier.vendor_id` links supplier → vendor. When null, `supplier_id` is used as `vendor_id` (for SQLite/dev).
- **RFQ creation**: Frontend sends `supplier_ids` (from shortlist item_ids). Backend `resolve_recipient_ids()` maps to `vendor_ids`.
- **Validation**: If an id is not a registered supplier, creation fails with a clear error.

## Vendor Access

- Vendor inbox and quote submission require `require_vendor`: user must have a row in `vendor_users` linking `user_id` → `vendor_id`.
- For demo: insert into `vendor_users` (user_id, vendor_id, role, created_at) linking a test user to a vendor. Ensure `vendors` has a row with id = supplier_id (used as vendor_id when supplier.vendor_id is null).

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/rfqs | HR/Employee | Create RFQ (supplier_ids or vendor_ids) |
| GET | /api/employee/assignments/{id}/rfqs | HR/Employee | List RFQs for assignment |
| GET | /api/rfqs/{id} | HR/Employee | RFQ detail |
| GET | /api/rfqs/{id}/quotes?comparison=1 | HR/Employee | List quotes (emit quote_compared if 2+) |
| PATCH | /api/rfqs/{id}/quotes/{quote_id}/accept | HR/Employee | Accept quote |
| GET | /api/vendor/rfqs | Vendor | List RFQs for vendor |
| GET | /api/vendor/rfqs/{id} | Vendor | RFQ detail for vendor |
| POST | /api/vendor/rfqs/{id}/quotes | Vendor | Submit quote |

## Analytics

- `quote_received`: when vendor submits a quote
- `quote_compared`: when employee opens quotes with `comparison=1` and 2+ quotes
- `quote_accepted`: when employee accepts a quote
