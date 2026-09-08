# Verification Steps: Remaining Gaps Closed

## A. HR Adds Preferred Supplier

1. Log in as HR (or Admin with HR company).
2. Go to **Preferred** in the HR nav (between Company Profile and Policy).
3. Click **Add preferred supplier**.
4. Select a supplier from the dropdown (active suppliers from registry).
5. Optionally set service category (e.g. Movers), priority rank, notes.
6. Click **Add**.
7. **Verify**: The supplier appears in the table.
8. **Verify**: Data is in `company_preferred_suppliers` (Supabase or DB).

## B. Employee Sees Preferred Label and Ranking Effect

1. Ensure HR has added at least one preferred supplier for movers (or another service).
2. Log in as Employee with an assignment linked to the same company.
3. Go to Services flow → Movers (or the relevant service).
4. Complete questions with a destination city where the preferred supplier has coverage.
5. View recommendations.
6. **Verify**: The preferred supplier shows a **"Preferred by your company"** badge (indigo).
7. **Verify**: Preferred suppliers appear higher in the list (ranking boost applied).

## C. Employee Creates RFQ and Rows Appear in Supabase

**Prerequisites**: Suppliers used for RFQ must have `vendor_id` set to an existing row in `vendors`.

1. Create a vendor in Supabase if needed:
   ```sql
   INSERT INTO vendors (id, name, service_types, countries, status)
   VALUES (gen_random_uuid(), 'Test Mover', ARRAY['movers'], ARRAY['DE'], 'active');
   ```
2. In Admin > Suppliers, set the test supplier's `vendor_id` to that vendor's UUID.
3. As Employee, go to Services → Recommendations → select movers supplier → Request quote / Create RFQ.
4. Submit the RFQ.
5. **Verify**: In Supabase, check `rfqs`, `rfq_items`, `rfq_recipients` for new rows.
6. **Verify**: If a supplier has no `vendor_id`, the app shows a clear error (no silent failure).

## D. case_milestones Exists

1. Run migration: `supabase/migrations/20260325000000_case_milestones.sql`
2. Or in Supabase SQL Editor: verify `SELECT 1 FROM public.case_milestones LIMIT 1` succeeds.
3. **Verify**: Backend startup logs show `case_milestones` in `present=` list.

## E. analytics_events Exists

1. Run migration: `supabase/migrations/20260326000000_analytics_events.sql`
2. Or in Supabase SQL Editor: verify `SELECT 1 FROM public.analytics_events LIMIT 1` succeeds.
3. **Verify**: Backend startup logs show `analytics_events` in `present=` list.
