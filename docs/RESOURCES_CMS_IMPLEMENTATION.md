# Resources CMS Implementation Summary

## Overview

Admin-only CMS for managing Resources tab content: country resources, events, categories, tags, and sources. HR and Employee users see only published content in read-only mode.

## Files Changed / Added

### Database
- **supabase/migrations/20260305000000_resources_cms_workflow.sql** — Workflow columns on `country_resources` and `rkg_country_events`, `resource_audit_log`, `updated_at` triggers
- **supabase/seed_resources_cms.sql** — Seed data: categories, tags, sources, sample resources and events

### Backend
- **backend/services/admin_resources.py** — Service layer: CRUD, workflow (draft→in_review→approved→published→archived), audit logging, taxonomy
- **backend/services/rkg_resources.py** — Added `published_only` and `status_filter` to `get_country_resources` and `get_country_events`; public API uses `published_only=True`
- **backend/app/routers/admin_resources.py** — Admin API router at `/api/admin/resources/*`
- **backend/main.py** — Included admin_resources router; updated `/api/resources/country` to pass `published_only=True` to RKG calls

### Frontend
- **frontend/src/api/client.ts** — `adminResourcesAPI` with list/create/update/workflow and taxonomy methods
- **frontend/src/navigation/routes.ts** — `adminResources`, `adminResourcesNew`, `adminResourcesEdit`, `adminEvents`, `adminEventsEdit`, `adminCategories`, `adminTags`, `adminSources`
- **frontend/src/pages/admin/AdminLayout.tsx** — Added "Resources CMS" nav link
- **frontend/src/pages/admin/AdminResources.tsx** — Main CMS hub: resources list, events tab, taxonomy tab, dashboard counts
- **frontend/src/pages/admin/AdminResourceEditor.tsx** — Create/edit resource form, workflow buttons
- **frontend/src/pages/admin/AdminEvents.tsx** — Events list with filters
- **frontend/src/pages/admin/AdminEventEditor.tsx** — Create/edit event form
- **frontend/src/pages/admin/AdminCategories.tsx** — Categories management
- **frontend/src/pages/admin/AdminTags.tsx** — Tags management
- **frontend/src/pages/admin/AdminSources.tsx** — Sources management
- **frontend/src/App.tsx** — Routes for all admin Resources CMS pages

## Routes Added

| Route | Page | Description |
|-------|------|-------------|
| `/admin/resources` | AdminResources | Hub: resources list, events, taxonomy, counts |
| `/admin/resources/new` | AdminResourceEditor | Create resource |
| `/admin/resources/:id` | AdminResourceEditor | Edit resource |
| `/admin/events` | AdminEvents | Events list |
| `/admin/events/:id` | AdminEventEditor | Create/edit event (id=new for create) |
| `/admin/resources/categories` | AdminCategories | Categories management |
| `/admin/resources/tags` | AdminTags | Tags management |
| `/admin/resources/sources` | AdminSources | Sources management |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/resources` | List resources (filters: country, city, status, etc.) |
| GET | `/api/admin/resources/counts` | Dashboard counts (draft, in_review, published, archived) |
| GET | `/api/admin/resources/:id` | Get resource by ID |
| POST | `/api/admin/resources` | Create resource |
| PUT | `/api/admin/resources/:id` | Update resource |
| POST | `/api/admin/resources/:id/submit-for-review` | Submit for review |
| POST | `/api/admin/resources/:id/approve` | Approve |
| POST | `/api/admin/resources/:id/publish` | Publish |
| POST | `/api/admin/resources/:id/unpublish` | Unpublish |
| POST | `/api/admin/resources/:id/archive` | Archive |
| GET | `/api/admin/resources/:id/audit` | Audit log for resource |
| GET | `/api/admin/resources/events` | List events |
| GET | `/api/admin/resources/events/:id` | Get event |
| POST | `/api/admin/resources/events` | Create event |
| PUT | `/api/admin/resources/events/:id` | Update event |
| POST | `/api/admin/resources/events/:id/publish` | Publish event |
| POST | `/api/admin/resources/events/:id/archive` | Archive event |
| GET/POST/PUT | `/api/admin/resources/taxonomy/categories` | Categories |
| GET/POST/PUT | `/api/admin/resources/taxonomy/tags` | Tags |
| GET/POST/PUT | `/api/admin/resources/taxonomy/sources` | Sources |

## Access Rules

- **Admin**: Full access to CMS; create, edit, review, approve, publish, archive, manage taxonomy
- **HR / Employee**: Read-only access to published content on public Resources page; no access to CMS
- **Enforcement**: Backend API checks admin via `_require_admin` (token + db role); frontend shows "Admin only" for non-admin on CMS pages

## Workflow

- **Resources**: draft → in_review → approved → published → archived; unpublish sets `is_visible_to_end_users=false`
- **Events**: draft → published → archived (simplified workflow)
- **Visibility**: Only `status=published` and `is_visible_to_end_users=true` are shown to HR/Employee on the public Resources page

## Assumptions

1. Supabase RKG tables exist (`country_resources`, `rkg_country_events`, `resource_categories`, `resource_tags`, `resource_sources`, `country_resource_tags`)
2. Migration `20260305000000_resources_cms_workflow.sql` has been applied (adds status, audit columns)
3. Admin users are identified via `relopass_role=ADMIN` (demo) or backend `db.get_user_by_token` + profile/allowlist
4. Public Resources page uses `/api/resources/country` which now filters by `published_only=True`

## Next Recommended Steps

1. **Run migrations**: Apply `20260305000000_resources_cms_workflow.sql` and `seed_resources_cms.sql` in Supabase
2. **RLS policies**: If using direct Supabase client access (anon/key), add RLS policies restricting writes to admin; reads for published content
3. **Preview mode**: Add "Preview published rendering" in AdminResourceEditor to render the card as end users see it
4. **Bulk actions**: Implement bulk submit/approve/publish/archive for resources list
5. **Duplicate resource**: Add "Duplicate" action for quick cloning of resources
