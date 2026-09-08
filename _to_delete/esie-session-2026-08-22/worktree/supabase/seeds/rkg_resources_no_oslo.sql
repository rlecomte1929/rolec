-- RKG Seed: Norway / Oslo pilot
-- Categories, tags, resources, events for structured Resources page

-- Idempotent: clear Oslo resources (re-run safe)
DELETE FROM public.country_resource_tags WHERE resource_id IN (SELECT id FROM country_resources WHERE country_code = 'NO' AND city_name = 'Oslo');
DELETE FROM public.country_resources WHERE country_code = 'NO' AND city_name = 'Oslo';
DELETE FROM public.rkg_country_events WHERE country_code = 'NO' AND city_name = 'Oslo';

-- 5.1 resource_categories
INSERT INTO public.resource_categories (key, label, description, icon_name, sort_order, is_active) VALUES
  ('admin_essentials', 'Administrative Essentials', 'Residence registration, tax, ID, bank, mobile', 'admin', 1, true),
  ('housing', 'Housing', 'Guides, neighborhoods, rental platforms', 'housing', 2, true),
  ('schools', 'Schools & Childcare', 'Public, international, kindergartens', 'schools', 3, true),
  ('healthcare', 'Healthcare', 'Registration, clinics, emergency', 'healthcare', 4, true),
  ('transport', 'Transportation', 'Public transport, apps, driving', 'transport', 5, true),
  ('daily_life', 'Daily Life Essentials', 'Groceries, banks, postal', 'daily_life', 6, true),
  ('community', 'Community & Social Integration', 'Expat groups, language, networking', 'community', 7, true),
  ('culture_leisure', 'Events & Culture', 'Cinema, concerts, museums, theater', 'culture', 8, true),
  ('nature', 'Nature & Weekend Activities', 'Parks, hiking, skiing', 'nature', 9, true),
  ('cost_of_living', 'Cost of Living', 'Rent, transport, groceries snapshot', 'cost', 10, true),
  ('safety', 'Safety & Practical Tips', 'Emergency numbers, seasonal advice', 'safety', 11, true)
ON CONFLICT (key) DO NOTHING;

-- 5.2 resource_sources
INSERT INTO public.resource_sources (source_name, publisher, source_type, url, trust_tier) VALUES
  ('Skatteetaten', 'Norwegian Tax Administration', 'official', 'https://www.skatteetaten.no/', 'T0'),
  ('Helsenorge', 'Norwegian Health Network', 'official', 'https://helsenorge.no/', 'T0'),
  ('Oslo Kommune', 'City of Oslo', 'official', 'https://www.oslo.kommune.no/', 'T0'),
  ('Ruter', 'Oslo Public Transport', 'institutional', 'https://ruter.no/', 'T0'),
  ('Finn.no', 'Schibsted', 'commercial', 'https://www.finn.no/', 'T2'),
  ('Internations', 'Internations.org', 'community', 'https://www.internations.org/', 'T3')
ON CONFLICT (source_name) DO NOTHING;

-- Get category IDs (assumes categories exist)
DO $$
DECLARE
  cat_admin uuid; cat_housing uuid; cat_schools uuid; cat_health uuid; cat_transport uuid;
  cat_daily uuid; cat_comm uuid; cat_culture uuid; cat_nature uuid; cat_cost uuid; cat_safety uuid;
  src_skat uuid; src_helse uuid; src_oslo uuid; src_ruter uuid; src_finn uuid;
BEGIN
  SELECT id INTO cat_admin FROM resource_categories WHERE key = 'admin_essentials' LIMIT 1;
  SELECT id INTO cat_housing FROM resource_categories WHERE key = 'housing' LIMIT 1;
  SELECT id INTO cat_schools FROM resource_categories WHERE key = 'schools' LIMIT 1;
  SELECT id INTO cat_health FROM resource_categories WHERE key = 'healthcare' LIMIT 1;
  SELECT id INTO cat_transport FROM resource_categories WHERE key = 'transport' LIMIT 1;
  SELECT id INTO cat_daily FROM resource_categories WHERE key = 'daily_life' LIMIT 1;
  SELECT id INTO cat_comm FROM resource_categories WHERE key = 'community' LIMIT 1;
  SELECT id INTO cat_culture FROM resource_categories WHERE key = 'culture_leisure' LIMIT 1;
  SELECT id INTO cat_nature FROM resource_categories WHERE key = 'nature' LIMIT 1;
  SELECT id INTO cat_cost FROM resource_categories WHERE key = 'cost_of_living' LIMIT 1;
  SELECT id INTO cat_safety FROM resource_categories WHERE key = 'safety' LIMIT 1;
  SELECT id INTO src_skat FROM resource_sources WHERE source_name = 'Skatteetaten' LIMIT 1;
  SELECT id INTO src_helse FROM resource_sources WHERE source_name = 'Helsenorge' LIMIT 1;
  SELECT id INTO src_oslo FROM resource_sources WHERE source_name = 'Oslo Kommune' LIMIT 1;
  SELECT id INTO src_ruter FROM resource_sources WHERE source_name = 'Ruter' LIMIT 1;
  SELECT id INTO src_finn FROM resource_sources WHERE source_name = 'Finn.no' LIMIT 1;

  INSERT INTO country_resources (country_code, country_name, city_name, category_id, title, summary, resource_type, audience_type, external_url, trust_tier, is_featured, is_active)
  VALUES
    ('NO', 'Norway', 'Oslo', cat_admin, 'Residence registration (Folkeregisteret)', 'Register within 7 days of arrival', 'official_link', 'all', 'https://www.skatteetaten.no/en/person/national-registry/', 'T0', true, true),
    ('NO', 'Norway', 'Oslo', cat_admin, 'Tax card (Skatt kort)', 'Apply 1–2 weeks after registration', 'official_link', 'all', 'https://www.skatteetaten.no/', 'T0', true, true),
    ('NO', 'Norway', 'Oslo', cat_admin, 'Bank account & BankID', 'Required for salary, utilities, ID', 'guide', 'all', NULL, NULL, true, true),
    ('NO', 'Norway', 'Oslo', cat_housing, 'Finn.no', 'Main rental and property portal in Norway', 'provider', 'all', 'https://www.finn.no/bolig/', 'T2', true, true),
    ('NO', 'Norway', 'Oslo', cat_housing, 'Hyalite', 'Expat-focused rental platform', 'provider', 'all', 'https://hyalite.io/', 'T2', false, true),
    ('NO', 'Norway', 'Oslo', cat_housing, 'Bærum', 'Family-friendly suburb west of Oslo', 'place', 'family', NULL, NULL, true, true),
    ('NO', 'Norway', 'Oslo', cat_schools, 'Oslo International School', 'International curriculum, English', 'provider', 'with_children', NULL, NULL, true, true),
    ('NO', 'Norway', 'Oslo', cat_schools, 'Barnehage enrollment', 'Register kindergarten before arrival', 'official_link', 'with_children', 'https://oslo.kommune.no/barn-og-utdanning/', 'T0', true, true),
    ('NO', 'Norway', 'Oslo', cat_health, 'GP registration (fastlege)', 'Register with a doctor in first month', 'official_link', 'all', 'https://helsenorge.no/', 'T0', true, true),
    ('NO', 'Norway', 'Oslo', cat_health, 'Emergency 113', 'Police, ambulance, fire', 'tip', 'all', NULL, NULL, true, true),
    ('NO', 'Norway', 'Oslo', cat_transport, 'Ruter', 'Oslo public transport, app, monthly pass ~700–900 NOK', 'provider', 'all', 'https://ruter.no/', 'T0', true, true),
    ('NO', 'Norway', 'Oslo', cat_transport, 'VY', 'Norwegian railways, airport train', 'provider', 'all', 'https://www.vy.no/', 'T0', false, true),
    ('NO', 'Norway', 'Oslo', cat_daily, 'Rema 1000, Kiwi, Meny', 'Main grocery chains', 'provider', 'all', NULL, NULL, false, true),
    ('NO', 'Norway', 'Oslo', cat_daily, 'Foodora, Wolt', 'Food delivery apps', 'provider', 'all', NULL, NULL, false, true),
    ('NO', 'Norway', 'Oslo', cat_comm, 'Internations Oslo', 'Expat meetups and networking', 'provider', 'all', 'https://www.internations.org/oslo-expats', 'T3', true, true),
    ('NO', 'Norway', 'Oslo', cat_comm, 'Meetup Oslo', 'Events and interest groups', 'provider', 'all', 'https://www.meetup.com/cities/no/oslo/', 'T3', false, true),
    ('NO', 'Norway', 'Oslo', cat_culture, 'Munch Museum', 'Art museum, Munch collection', 'place', 'all', 'https://www.munchmuseet.no/', NULL, true, true),
    ('NO', 'Norway', 'Oslo', cat_culture, 'Opera House', 'Opera and ballet', 'place', 'all', 'https://operaen.no/', NULL, true, true),
    ('NO', 'Norway', 'Oslo', cat_nature, 'Nordmarka', 'Forest, lakes, hiking, skiing. 30 min from city', 'place', 'all', NULL, NULL, true, true),
    ('NO', 'Norway', 'Oslo', cat_nature, 'Vigeland Park', 'Sculpture park, free entry', 'place', 'all', NULL, NULL, true, true),
    ('NO', 'Norway', 'Oslo', cat_nature, 'Sognsvann', 'Lake, jogging, family-friendly', 'place', 'family', NULL, NULL, true, true),
    ('NO', 'Norway', 'Oslo', cat_safety, 'Emergency 113', 'Police, ambulance, fire — keep in phone', 'tip', 'all', NULL, NULL, true, true),
    ('NO', 'Norway', 'Oslo', cat_safety, 'Winter tips', 'Dress in layers, watch for ice', 'tip', 'all', NULL, NULL, false, true)
  ;
END $$;

-- 5.3 resource_tags
INSERT INTO public.resource_tags (key, label, tag_group) VALUES
  ('family_friendly', 'Family-friendly', 'family_type'),
  ('free', 'Free', 'free_paid'),
  ('paid', 'Paid', 'free_paid'),
  ('indoor', 'Indoor', 'indoor_outdoor'),
  ('outdoor', 'Outdoor', 'indoor_outdoor'),
  ('weekend', 'Weekend', 'weekday_weekend'),
  ('cinema', 'Cinema', 'interest'),
  ('concert', 'Concert', 'interest'),
  ('museum', 'Museum', 'interest'),
  ('networking', 'Networking', 'interest'),
  ('family_activity', 'Family activity', 'interest')
ON CONFLICT (key) DO NOTHING;

-- 5.6 country_events (rkg_country_events) - Oslo sample
INSERT INTO public.rkg_country_events (country_code, city_name, title, description, event_type, venue_name, address, start_datetime, end_datetime, price_text, currency, is_free, is_family_friendly, external_url, booking_url) VALUES
  ('NO', 'Oslo', 'Weekend cinema: Family matinee', 'Family-friendly film screening', 'cinema', 'Colosseum Kino', 'Storgata 2, Oslo', (CURRENT_DATE + INTERVAL '2 days') + TIME '11:00', (CURRENT_DATE + INTERVAL '2 days') + TIME '13:00', '120 NOK', 'NOK', false, true, 'https://www.oslokino.no/', NULL),
  ('NO', 'Oslo', 'Oslo Philharmonic concert', 'Evening classical concert', 'concert', 'Oslo Concert Hall', 'Munkedamsveien 14', (CURRENT_DATE + INTERVAL '3 days') + TIME '19:00', (CURRENT_DATE + INTERVAL '3 days') + TIME '21:30', 'From 250 NOK', 'NOK', false, false, 'https://oslofilharmonien.no/', 'https://oslofilharmonien.no/billetter'),
  ('NO', 'Oslo', 'Nordmarka guided hike', 'Free guided hike, all levels', 'family_activity', 'Nordmarka', 'Meeting at Frognerseteren', (CURRENT_DATE + INTERVAL '5 days') + TIME '10:00', (CURRENT_DATE + INTERVAL '5 days') + TIME '14:00', 'Free', 'NOK', true, true, NULL, NULL),
  ('NO', 'Oslo', 'Munch Museum exhibition', 'Temporary exhibition', 'museum', 'Munch Museum', 'Edvard Munchs plass 1', (CURRENT_DATE + INTERVAL '1 days') + TIME '10:00', (CURRENT_DATE + INTERVAL '1 days') + TIME '18:00', '160 NOK', 'NOK', false, true, 'https://www.munchmuseet.no/', NULL),
  ('NO', 'Oslo', 'Internations Oslo meetup', 'Monthly expat networking', 'networking', 'TBD bar', 'Oslo city center', (CURRENT_DATE + INTERVAL '7 days') + TIME '18:30', (CURRENT_DATE + INTERVAL '7 days') + TIME '21:00', 'Free', 'NOK', true, false, 'https://www.internations.org/oslo-expats', NULL),
  ('NO', 'Oslo', 'Vigeland Park Sunday tour', 'Free sculpture park guided tour', 'family_activity', 'Vigeland Park', 'Nobels gate 32', (CURRENT_DATE + INTERVAL '6 days') + TIME '12:00', (CURRENT_DATE + INTERVAL '6 days') + TIME '13:30', 'Free', 'NOK', true, true, NULL, NULL),
  ('NO', 'Oslo', 'National Theatre: contemporary play', 'Norwegian drama with subtitles', 'theater', 'National Theatre', 'Stortingsgata 15', (CURRENT_DATE + INTERVAL '4 days') + TIME '19:00', (CURRENT_DATE + INTERVAL '4 days') + TIME '21:30', 'From 200 NOK', 'NOK', false, false, 'https://www.nationaltheatret.no/', NULL),
  ('NO', 'Oslo', 'Kids disco at Kulturhuset', 'Children''s dance and music', 'family_activity', 'Kulturhuset', 'Youngstorget 3', (CURRENT_DATE + INTERVAL '6 days') + TIME '14:00', (CURRENT_DATE + INTERVAL '6 days') + TIME '16:00', '50 NOK', 'NOK', false, true, NULL, NULL)
ON CONFLICT DO NOTHING;
