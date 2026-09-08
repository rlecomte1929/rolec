-- Seed data for Resources CMS: categories, tags, sources, sample resources and events
-- Run after 20260305000000_resources_cms_workflow.sql

-- Categories (if not exists from RKG migration)
INSERT INTO public.resource_categories (id, key, label, description, sort_order, is_active)
VALUES
  (gen_random_uuid(), 'schools', 'Schools & Childcare', 'Education and childcare resources', 10, true),
  (gen_random_uuid(), 'housing', 'Housing', 'Housing and accommodation guidance', 20, true),
  (gen_random_uuid(), 'healthcare', 'Healthcare', 'Healthcare and medical services', 30, true),
  (gen_random_uuid(), 'daily_life', 'Daily Life', 'Practical daily life tips', 40, true),
  (gen_random_uuid(), 'community', 'Community', 'Community groups and networking', 50, true),
  (gen_random_uuid(), 'culture', 'Culture & Events', 'Culture, cinema, concerts, events', 60, true),
  (gen_random_uuid(), 'cost_of_living', 'Cost of Living', 'Cost of living summaries', 70, true),
  (gen_random_uuid(), 'safety', 'Safety', 'Safety and practical tips', 80, true)
ON CONFLICT (key) DO NOTHING;

-- Tags
INSERT INTO public.resource_tags (id, key, label, tag_group)
VALUES
  (gen_random_uuid(), 'family_friendly', 'Family Friendly', 'family_type'),
  (gen_random_uuid(), 'budget_low', 'Budget: Low', 'budget'),
  (gen_random_uuid(), 'budget_mid', 'Budget: Mid', 'budget'),
  (gen_random_uuid(), 'indoor', 'Indoor', 'indoor_outdoor'),
  (gen_random_uuid(), 'outdoor', 'Outdoor', 'indoor_outdoor'),
  (gen_random_uuid(), 'free', 'Free', 'free_paid')
ON CONFLICT (key) DO NOTHING;

-- Sources
INSERT INTO public.resource_sources (id, source_name, publisher, source_type, trust_tier)
VALUES
  (gen_random_uuid(), 'ReloPass Curated', 'ReloPass', 'internal_curated', 'T0'),
  (gen_random_uuid(), 'Official Govt', 'Government', 'official', 'T0'),
  (gen_random_uuid(), 'Community Wiki', 'Community', 'community', 'T3')
ON CONFLICT (source_name) DO NOTHING;

-- Sample resources (get category_id from first category)
DO $$
DECLARE
  cat_id uuid;
  src_id uuid;
BEGIN
  SELECT id INTO cat_id FROM public.resource_categories WHERE key = 'schools' LIMIT 1;
  SELECT id INTO src_id FROM public.resource_sources WHERE source_name = 'ReloPass Curated' LIMIT 1;

  IF cat_id IS NOT NULL THEN
    INSERT INTO public.country_resources (
      country_code, country_name, city_name, category_id, title, summary,
      resource_type, audience_type, is_family_friendly, is_featured, source_id,
      status, is_visible_to_end_users
    )
    VALUES
      ('NO', 'Norway', 'Oslo', cat_id, 'International Schools in Oslo', 'Overview of international schools for expat families.', 'guide', 'family', true, true, src_id, 'published', true),
      ('NO', 'Norway', 'Oslo', cat_id, 'Public School Registration', 'How to register for Norwegian public schools.', 'guide', 'all', true, false, src_id, 'draft', false),
      ('NO', 'Norway', NULL, cat_id, 'Childcare Options Norway', 'National overview of childcare options.', 'guide', 'family', true, true, src_id, 'in_review', false);
  END IF;
END $$;

-- Sample events
INSERT INTO public.rkg_country_events (
  country_code, city_name, title, description, event_type,
  venue_name, start_datetime, end_datetime, is_free, is_family_friendly,
  status, is_visible_to_end_users
)
VALUES
  ('NO', 'Oslo', 'Winter Market 2026', 'Seasonal market with local food and crafts.', 'festival', 'City Center', NOW() + interval '7 days', NOW() + interval '7 days' + interval '8 hours', true, true, 'published', true),
  ('NO', 'Oslo', 'Expat Meetup', 'Monthly expat networking event.', 'networking', 'TBD', NOW() + interval '14 days', NOW() + interval '14 days' + interval '2 hours', true, false, 'draft', false);
