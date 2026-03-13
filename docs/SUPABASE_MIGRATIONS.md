# Supabase Migrations Required for Production

## Overview

ReloPass uses `DATABASE_URL` as the single source of truth. When deploying to Render with Supabase Postgres, ensure these migrations have been applied to your Supabase project.

## Tables That Must Exist

| Table | Migration | Purpose |
|-------|-----------|---------|
| vendors | 20260301012000_services_rfq_quotes | Required for rfq_recipients.vendor_id FK |
| rfqs | 20260301012000_services_rfq_quotes | RFQ creation |
| rfq_items | 20260301012000_services_rfq_quotes | RFQ line items |
| rfq_recipients | 20260301012000_services_rfq_quotes | RFQ vendor recipients |
| quotes | 20260301012000_services_rfq_quotes | Vendor quotes |
| quote_lines | 20260301012000_services_rfq_quotes | Quote line items |
| case_milestones | 20260325000000_case_milestones | Timeline milestones |
| analytics_events | 20260326000000_analytics_events | Workflow analytics |
| suppliers | 20260312000000_supplier_registry | Supplier registry |
| supplier_service_capabilities | 20260312000000_supplier_registry | Supplier coverage |
| supplier_scoring_metadata | 20260312000000_supplier_registry | Supplier scoring |
| company_preferred_suppliers | 20260328000000_company_preferred_suppliers | HR preferred suppliers |
| policy_documents | 20260329000000_policy_documents | Policy document intake pipeline |
| policy_document_clauses | 20260330000000_policy_document_clauses | Clause segmentation with traceability |
| policy_versions, policy_benefit_rules, policy_rule_conditions, policy_exclusions, policy_evidence_requirements, policy_assignment_type_applicability, policy_family_status_applicability, policy_tier_overrides, policy_source_links | 20260331000000_policy_normalization | Canonical policy normalization |

## Migrations to Apply Manually

If tables are missing in production:

1. **Via Supabase Dashboard**  
   Go to SQL Editor and run each migration file in order from `supabase/migrations/`.

2. **Minimum set for RFQ/quote + milestones + analytics + suppliers**  
   ```
   20260301012000_services_rfq_quotes.sql  (vendors, rfqs, rfq_items, rfq_recipients, quotes, quote_lines)
   20260324000000_canonical_case_id_phase1.sql   (adds canonical_case_id to rfqs)
   20260325000000_case_milestones.sql
   20260326000000_analytics_events.sql
   20260327000000_quotes_created_by_user.sql
   20260312000000_supplier_registry.sql
   20260328000000_company_preferred_suppliers.sql
   20260329000000_policy_documents.sql
   ```

3. **Dependencies**  
   Run migrations in chronological order (by filename). Later migrations may depend on earlier ones.

## Startup Check

On startup, the backend logs which expected tables are present vs missing:

```
db_tables: present=[...] missing=[...] (postgres). Apply migrations if missing.
```

Review logs after deploy to confirm all required tables exist.

## RFQ Production Notes

- **vendor_id required**: Suppliers used for RFQ must have `vendor_id` set to an existing `vendors` row. Add `vendor_id` in Admin > Suppliers before using a supplier for RFQ.
- **Validation**: The backend validates vendor_ids exist before insert and fails clearly if missing.
