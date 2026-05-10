# Resources Page — Relocation Knowledge Graph (RKG) Implementation

## Overview

The country-specific Resources page is built on a structured data model that supports personalization, filtering, and future evolution into a full Relocation Knowledge Graph (RKG).

## Files Changed

### Database
- **`supabase/migrations/20260304000000_rkg_resources.sql`** — New RKG schema
- **`supabase/seeds/rkg_resources_no_oslo.sql`** — Norway/Oslo pilot seed
- **`supabase/config.toml`** — Added RKG seed to `sql_paths`

### Backend
- **`backend/services/rkg_resources.py`** — New RKG service (get_resource_context, get_country_resources, get_country_events, get_recommended_resources, resources_to_sections)
- **`backend/main.py`** — Updated `/api/resources/country`, RKG imports

### Frontend
- **`frontend/src/pages/Resources.tsx`** — Hero, filters, sections, events, recommended block, URL query params
- **`frontend/src/api/client.ts`** — Extended `resourcesAPI.getCountryResources` return type

## Migrations Added

1. **20260304000000_rkg_resources.sql**
   - `resource_categories` — Canonical sections
   - `resource_sources` — Provenance and trust
   - `resource_tags` — Reusable filters
   - `country_resources` — Content per country/city/category
   - `country_resource_tags` — Many-to-many
   - `rkg_country_events` — Structured events (cinema, concert, etc.)
   - `case_resource_preferences` — User filter preferences
   - RLS policies for read access

## New Routes / Endpoints

- **`GET /api/resources/country`** (enhanced)
  - Query params: `assignment_id`, `filters` (JSON)
  - Returns: `profile`, `context`, `hints`, `sections`, `events`, `recommended`, `filters_applied`

## Sample Seed Records

### Norway / Oslo
- **Categories**: 11 (admin_essentials, housing, schools, healthcare, transport, daily_life, community, culture_leisure, nature, cost_of_living, safety)
- **Sources**: 6 (Skatteetaten, Helsenorge, Oslo Kommune, Ruter, Finn.no, Internations)
- **Resources**: 23 (admin, housing, schools, healthcare, transport, daily life, community, culture, nature, safety)
- **Events**: 8 (cinema, concert, museum, networking, theater, family activities)
- **Tags**: 11 (family_friendly, free, paid, indoor, outdoor, weekend, cinema, concert, museum, networking, family_activity)

## Personalization Logic

- **`get_resource_context(draft)`** derives: countryCode, cityName, familyType, hasChildren, childAges, spouseWorking, relocationType, preferredLanguage, recommendedTags
- **Recommended tags** vary by profile:
  - Children → schools, childcare, parks, family_activity
  - Single → networking, expat_groups, cinema, concerts
  - Spouse not working → language_classes, community, spouse_support
  - Short-term → temporary_housing, public_transport
  - Long-term → registration, schooling, healthcare, bank_account

## Filter Support

- **Server-side**: city, family_type, budget, category, child_age (range), family_friendly, event_type
- **Client-side**: search, event_type, free_paid, family_friendly
- **URL persistence**: Filters synced to `?city=Oslo&family_type=family` etc.

## Assumptions

1. Supabase is used for RKG tables; falls back to legacy `_get_section_content` when RKG returns empty
2. `rkg_country_events` is a separate table from existing `country_events` to avoid schema conflict
3. Case draft structure uses `relocationBasics`, `familyMembers` as in current wizard
4. Event `start_datetime` is stored as timestamptz; seed uses `CURRENT_DATE + INTERVAL` for relative dates

## Recommended Next Steps

1. **Run migration and seed**: `supabase db reset` (or push migration to remote)
2. **Add more countries**: Extend seed for Singapore, US (SF/NYC) with same structure
3. **Admin UI**: Build curation UI to manage resources, approve submissions
4. **User submissions**: Add endpoint for users to suggest resources (pending approval)
5. **External APIs**: Integrate event feeds (e.g. Eventbrite, local tourism) for auto-enrichment
6. **HR policy overlay**: Link resources to company policy caps where relevant
