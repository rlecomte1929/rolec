# Resources Module — Database Schema Summary

## Migration Files

| File | Description |
|------|-------------|
| `supabase/migrations/20260306000000_resources_module_full_schema.sql` | Enums, role helpers, table alterations, RLS policies, secure views |

**Depends on:** `20260304000000_rkg_resources.sql`, `20260305000000_resources_cms_workflow.sql`

---

## Enums Created

| Enum | Values |
|------|--------|
| `resource_status` | draft, in_review, approved, published, archived |
| `resource_source_type` | official, institutional, commercial, community, internal_curated |
| `resource_trust_tier` | T0, T1, T2, T3 |
| `resource_entry_type` | guide, checklist_item, provider, place, event_source, tip, official_link, cost_snapshot, safety_tip, community_group, school, healthcare_facility, housing_listing_source, transport_info |
| `resource_audience_type` | all, single, couple, family, with_children, spouse_job_seeker |
| `resource_budget_tier` | low, mid, high |
| `resource_event_type` | cinema, concert, festival, sports, family_activity, networking, museum, theater, market, nature, kids_activity, community_event |
| `resource_audit_entity_type` | resource, event, category, tag, source |
| `resource_audit_action_type` | create, update, submit_for_review, approve, publish, archive, delete, restore, unpublish |

---

## Tables

| Table | Action | Notes |
|-------|--------|-------|
| `resource_categories` | Altered | Added updated_at, created_by_user_id, updated_by_user_id; indexes |
| `resource_tags` | Altered | Added updated_at, created_by_user_id, updated_by_user_id; index on tag_group |
| `resource_sources` | Altered | Added updated_at, created_by_user_id, updated_by_user_id; indexes |
| `country_resources` | Altered | Added country_name, content_json; indexes; child_age constraint |
| `country_resource_tags` | Unchanged | Existing |
| `rkg_country_events` | Altered | Added country_name, trust_tier; end>=start constraint; indexes |
| `country_event_tags` | **Created** | event_id, tag_id, unique(event_id, tag_id) |
| `case_resource_preferences` | Altered | Added updated_at; unique on case_id |
| `resource_audit_log` | Altered | performed_by_user_id now nullable |

---

## Helper Functions

| Function | Returns | Purpose |
|----------|---------|---------|
| `resources_current_user_role()` | text | Role from `profiles` where `profiles.id = auth.uid()::text`; returns 'none' if no profile |
| `resources_is_admin()` | boolean | `resources_current_user_role() = 'ADMIN'` |
| `resources_can_read_published()` | boolean | Role in ('ADMIN', 'HR', 'EMPLOYEE') |

**Assumption:** Roles are stored in `public.profiles` with `id` (text) and `role` (text). `auth.uid()` is cast to text for lookup. Roles: `ADMIN`, `HR`, `EMPLOYEE`.

---

## Secure Published Views

| View | Purpose |
|------|---------|
| `published_country_resources` | Safe columns only; filters status=published, is_visible_to_end_users=true, effective date window |
| `published_country_events` | Safe columns only; filters status=published, is_visible_to_end_users=true |
| `published_resource_sources_safe` | id, source_name, publisher, source_type, url, retrieved_at, trust_tier (no notes) |

**Critical:** Non-admin (HR/Employee) application code must query these views, not the base tables, to avoid exposing `review_notes`, `internal_notes`, `created_by_user_id`, and other governance columns.

---

## RLS Policies

### resource_categories
- **Admin:** Full CRUD
- **HR/Employee:** SELECT only where `is_active = true`

### resource_tags
- **Admin:** Full CRUD
- **HR/Employee:** SELECT all (needed for filters)

### resource_sources
- **Admin:** Full CRUD
- **HR/Employee:** No access (use `published_resource_sources_safe` if needed)

### country_resources
- **Admin:** Full CRUD
- **HR/Employee:** SELECT only where status=published, is_visible_to_end_users=true, effective date window

### country_resource_tags
- **Admin:** Full CRUD
- **HR/Employee:** SELECT only for tags linked to published+visible resources

### rkg_country_events
- **Admin:** Full CRUD
- **HR/Employee:** SELECT only where status=published, is_visible_to_end_users=true

### country_event_tags
- **Admin:** Full CRUD
- **HR/Employee:** SELECT only for tags linked to published+visible events

### case_resource_preferences
- **Admin:** Full CRUD
- **HR/Employee:** No access (ownership not yet modeled)

### resource_audit_log
- **Admin:** SELECT, INSERT
- **HR/Employee:** No access

---

## Assumptions

1. **Role storage:** `public.profiles` with `id` (text) and `role` (text). Values: `ADMIN`, `HR`, `EMPLOYEE`.
2. **Auth:** Supabase Auth with `auth.uid()` returning uuid. Profiles joined via `auth.uid()::text`.
3. **Backend:** Admin operations use `service_role`, which bypasses RLS.
4. **Client access:** When using anon/authenticated keys with JWT, RLS applies. App must use `published_*` views for HR/Employee reads.
5. **Existing tables:** `country_resources`, `rkg_country_events` (not `country_events`), `resource_categories`, `resource_tags`, `resource_sources` from prior migrations. Workflow columns from `20260305000000_resources_cms_workflow.sql`.

---

## Unresolved Dependencies

- **case_resource_preferences:** `case_id` is text. No FK to `relocation_cases` or `case_assignments`. Ownership-based RLS deferred until case ownership is normalized.
- **admin_allowlist:** Some flows may treat admin as allowlist-only (e.g. `@relopass.com`). This migration uses `profiles.role` only.

---

## Recommended Next Steps

1. **Backend:** Update API layer to query `published_country_resources` and `published_country_events` (instead of base tables) when serving HR/Employee.
2. **Enums:** Migrate existing text columns (e.g. `resource_type`, `audience_type`) to enum types in a follow-up migration if desired.
3. **case_resource_preferences:** Add FK to cases table and ownership-based RLS when case model is finalized.
4. **admin_allowlist:** If admin is determined by allowlist, extend `resources_is_admin()` to check `admin_allowlist` where `email = (select email from auth.users where id = auth.uid())`.
