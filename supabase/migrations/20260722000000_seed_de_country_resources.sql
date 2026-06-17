-- [RESOURCE-CONTENT-1 / data seed] Germany (DE) country resources.
--
-- The Resources tab UI (ResourcesPageContent.tsx) + read path
-- (published_country_resources view → country_resources WHERE status='published'
-- AND is_visible_to_end_users=true) are fully built, but every resource table is
-- empty in prod, so the tab renders blank. This is a CONTENT seed only — NO schema
-- change. It populates the canonical CMS tables (resource_categories / resource_sources
-- / country_resources), NOT hardcoded component data.
--
-- HONESTY / PROVENANCE (CLAUDE.md content-provenance): every resource carries a real
-- source_url via resource_sources. Content is accurate, official-source-grounded
-- guidance ("representative"), not fabricated specifics. Sources are official German
-- government / public-information portals (trust_tier T0/T1).
--
-- Idempotent: categories/sources upsert on their unique keys; resources insert only
-- when an identical (country_code,title) row doesn't already exist. Safe to re-run.

BEGIN;

-- 1. Sections (resource_categories) — keys match ResourcesPageContent SECTIONS.categoryKeys
INSERT INTO public.resource_categories (key, label, description, icon_name, sort_order, is_active) VALUES
  ('admin_essentials', 'Admin essentials', 'Registration, tax ID, banking — the first official steps', 'clipboard', 10, true),
  ('housing',          'Housing',          'How the rental market works and what you need to apply',     'home',      20, true),
  ('healthcare',       'Healthcare',       'Health insurance, finding a doctor, emergency numbers',       'heart',     30, true),
  ('daily_life',       'Daily life',       'Mobile, shopping, recycling — settling-in basics',            'shopping',  40, true),
  ('transport',        'Transport',        'Public transport, the Deutschlandticket, driving',            'train',     50, true),
  ('cost_of_living',   'Cost of living',   'Typical monthly costs and money norms',                       'wallet',    60, true)
ON CONFLICT (key) DO NOTHING;

-- 2. Provenance sources (resource_sources) — official German portals with real URLs
INSERT INTO public.resource_sources (source_name, publisher, source_type, url, trust_tier) VALUES
  ('Make it in Germany (Federal Government)', 'German Federal Government', 'official', 'https://www.make-it-in-germany.com', 'T0'),
  ('Handbook Germany',                        'Handbook Germany (publicly funded)', 'institutional', 'https://handbookgermany.de', 'T1'),
  ('Federal Central Tax Office (BZSt)',       'Bundeszentralamt fuer Steuern', 'official', 'https://www.bzst.de', 'T0'),
  ('Deutschlandticket',                       'BMDV / German transport authorities', 'official', 'https://www.deutschlandticket.de', 'T0'),
  ('116117 Medical On-Call Service',          'Kassenaerztliche Bundesvereinigung', 'official', 'https://www.116117.de', 'T0'),
  ('Rundfunkbeitrag (ARD ZDF Deutschlandradio)', 'Beitragsservice', 'official', 'https://www.rundfunkbeitrag.de', 'T0')
ON CONFLICT (source_name) DO NOTHING;

-- 3. Resources (country_resources), joined to category + source by key/name.
WITH seed(title, summary, body, resource_type, category_key, source_name, external_url, sort_w) AS (
  VALUES
  -- Admin essentials
  ('Register your address (Anmeldung)',
   'Within ~14 days of moving in, register at your local Buergeramt.',
   'After you move into a flat you must register your address (Anmeldung) at the local Buergeramt/Buergerbuero, usually within two weeks. Bring your passport and a landlord confirmation (Wohnungsgeberbestaetigung). The certificate you receive (Meldebescheinigung) is required for almost everything else — bank account, tax ID, contracts. Book the appointment online early; slots fill up in big cities.',
   'guide', 'admin_essentials', 'Handbook Germany', 'https://handbookgermany.de/en/city-registration', 1),
  ('Get your tax ID (Steuer-ID)',
   'An 11-digit tax ID is mailed automatically after you register.',
   'Once your address is registered, the tax office automatically sends your 11-digit Tax Identification Number (Steuer-Identifikationsnummer) by post within a few weeks. Your employer needs it to run payroll at the correct tax rate, so give it to HR as soon as it arrives. You can request it again from the Federal Central Tax Office if you lose it.',
   'official_link', 'admin_essentials', 'Federal Central Tax Office (BZSt)', 'https://www.bzst.de/EN/Private_individuals/Tax_identification_number/tax_identification_number_node.html', 2),
  ('Open a German bank account',
   'A current account (Girokonto) is needed for salary, rent and bills.',
   'You need a German current account (Girokonto) to receive your salary and pay rent and bills by direct debit. Most banks ask for your passport, your registration certificate (Meldebescheinigung) and sometimes your residence permit. Both traditional branch banks and app-based banks operate nationwide; compare account fees before choosing.',
   'guide', 'admin_essentials', 'Make it in Germany (Federal Government)', 'https://www.make-it-in-germany.com/en/living-in-germany/discovering-germany/bank-account', 3),
  -- Housing
  ('How the rental market works',
   'Rent is quoted as Kaltmiete + Nebenkosten = Warmmiete; deposits are common.',
   'Listings usually quote the base rent (Kaltmiete) plus running costs (Nebenkosten); together they make the total (Warmmiete). Expect a deposit (Kaution) of up to three months base rent, held in a separate account and returned when you leave. Most flats are unfurnished and may not include kitchen fittings.',
   'guide', 'housing', 'Handbook Germany', 'https://handbookgermany.de/en/renting-an-apartment', 1),
  ('What you need to apply for a flat',
   'Landlords ask for proof of income, a SCHUFA report and ID.',
   'To apply for a flat, landlords typically want proof of income (about three recent payslips), a SCHUFA credit report, your ID, and sometimes confirmation that you owe no rent to a previous landlord (Mietschuldenfreiheitsbescheinigung). Prepare a single PDF with these documents to respond quickly — popular flats go fast.',
   'checklist_item', 'housing', 'Handbook Germany', 'https://handbookgermany.de/en/renting-an-apartment', 2),
  ('Setting up utilities and internet',
   'Electricity is self-arranged; internet contracts run 12-24 months.',
   'Electricity and sometimes gas are arranged by you directly, and you can freely switch providers to compare prices. Water and heating are often included in your Nebenkosten. Home internet contracts typically run 12 to 24 months, so check the minimum term before signing.',
   'guide', 'housing', 'Handbook Germany', 'https://handbookgermany.de/en/electricity-and-gas', 3),
  -- Healthcare
  ('Health insurance is mandatory',
   'Everyone in Germany must have health insurance; employees use statutory (GKV).',
   'Health insurance is compulsory for everyone living in Germany. Most employees are covered by statutory health insurance (gesetzliche Krankenversicherung, GKV); your employer registers you and the contribution is shared between you and your employer. Higher earners and the self-employed may choose private insurance. You receive an insurance card (Gesundheitskarte) to show at appointments.',
   'official_link', 'healthcare', 'Make it in Germany (Federal Government)', 'https://www.make-it-in-germany.com/en/living-in-germany/health-insurance', 1),
  ('Find a doctor (Hausarzt)',
   'Choose a local GP for routine care and specialist referrals.',
   'Register with a local general practitioner (Hausarzt) for routine care; they refer you to specialists when needed. Bring your insurance card (Gesundheitskarte) to appointments. For non-urgent medical help outside surgery hours, call the on-call service on 116117.',
   'guide', 'healthcare', '116117 Medical On-Call Service', 'https://www.116117.de', 2),
  ('Emergency numbers',
   'Dial 112 for medical/fire emergencies, 110 for police.',
   'In an emergency dial 112 for medical or fire services (free of charge, and English is usually available). For the police, dial 110. For urgent but non-life-threatening medical issues outside opening hours, call the medical on-call service on 116117.',
   'tip', 'healthcare', '116117 Medical On-Call Service', 'https://www.116117.de', 3),
  -- Daily life
  ('Mobile phones and SIM cards',
   'Prepaid SIMs are sold widely; registration needs ID.',
   'Prepaid SIM cards are available in supermarkets, drugstores and phone shops; by law you must register the SIM with your ID. Monthly contract plans usually require a German bank account. Coverage is good in cities; compare networks if you commute through rural areas.',
   'guide', 'daily_life', 'Handbook Germany', 'https://handbookgermany.de/en/mobile-phone-and-internet', 1),
  ('Shops close on Sundays',
   'Most shops and supermarkets are closed on Sundays and public holidays.',
   'Almost all shops and supermarkets are closed on Sundays and public holidays, so plan your grocery shopping for Monday to Saturday. Exceptions include shops at main train stations, airports and petrol stations. Pharmacies operate an emergency rota for Sundays.',
   'tip', 'daily_life', 'Handbook Germany', 'https://handbookgermany.de/en/shopping', 2),
  ('Bottle deposit (Pfand) and recycling',
   'Many bottles carry a refundable deposit; waste is separated.',
   'Many drink bottles and cans carry a deposit (Pfand) of roughly 8 to 25 cents, refunded at supermarket machines when you return them. Germany separates household waste into paper, packaging (often a yellow bin or Gelber Sack), glass by colour, organic and residual waste — check your building bins.',
   'tip', 'daily_life', 'Handbook Germany', 'https://handbookgermany.de/en/waste-separation', 3),
  -- Transport
  ('The Deutschlandticket',
   'A nationwide monthly subscription for regional and local transport.',
   'The Deutschlandticket is a monthly subscription ticket valid on regional and local public transport across the whole of Germany for a single flat monthly price. It does not cover long-distance trains (ICE/IC). You subscribe through a transport operator and can cancel monthly.',
   'official_link', 'transport', 'Deutschlandticket', 'https://www.deutschlandticket.de', 1),
  ('Public transport basics',
   'Cities run integrated U-Bahn, S-Bahn, tram and bus networks.',
   'German cities have integrated public transport (U-Bahn, S-Bahn, tram and bus) where one ticket covers a zone and time window across modes. Validate or activate your ticket as required before travelling — fines for travelling without a valid ticket are high and checks are frequent and in plain clothes.',
   'guide', 'transport', 'Handbook Germany', 'https://handbookgermany.de/en/local-transport', 2),
  ('Exchanging your driving licence',
   'You may drive on your existing licence for a limited period, then exchange it.',
   'Depending on the country that issued your licence, you can usually drive on it for up to six months after registering, after which you must exchange it for a German one. Some countries licences exchange without a test; others require a theory and/or practical test. Check the rules for your specific licence before the deadline.',
   'guide', 'transport', 'Make it in Germany (Federal Government)', 'https://www.make-it-in-germany.com/en/living-in-germany/driving-licence', 3),
  -- Cost of living
  ('Typical monthly costs',
   'Budget for rent, health insurance, transport and the broadcasting fee.',
   'Your largest cost is usually rent. Also budget for health insurance (shared with your employer if you are on statutory insurance), groceries, transport (e.g. the Deutschlandticket), and the household broadcasting fee (Rundfunkbeitrag). Costs vary a lot between big cities and smaller towns.',
   'guide', 'cost_of_living', 'Handbook Germany', 'https://handbookgermany.de/en/cost-of-living', 1),
  ('Broadcasting fee (Rundfunkbeitrag)',
   'Every household pays the Rundfunkbeitrag, regardless of owning a TV.',
   'Each household in Germany pays a public broadcasting fee (Rundfunkbeitrag), independent of whether you own a television or radio. After moving in you register your household and pay one fee per household (not per person). Register promptly to avoid back-payment notices.',
   'official_link', 'cost_of_living', 'Rundfunkbeitrag (ARD ZDF Deutschlandradio)', 'https://www.rundfunkbeitrag.de', 2),
  ('Gross vs net salary and direct debits',
   'Salaries are quoted gross; bills are paid by SEPA direct debit.',
   'German salaries are quoted gross (brutto); your take-home (netto) is after income tax and social contributions, which are deducted by your employer. Rent and most bills are paid automatically by SEPA direct debit (Lastschrift) from your current account, so keep it funded.',
   'tip', 'cost_of_living', 'Handbook Germany', 'https://handbookgermany.de/en/banking', 3)
)
INSERT INTO public.country_resources
  (country_code, country_name, category_id, title, summary, body, resource_type,
   audience_type, language_code, source_id, trust_tier, external_url,
   status, is_visible_to_end_users, is_active, is_family_friendly)
SELECT
  'DE', 'Germany', cat.id, s.title, s.summary, s.body, s.resource_type,
  'all', 'en', src.id, src.trust_tier, s.external_url,
  'published', true, true,
  -- General relocation essentials apply to everyone incl. families. The page
  -- read-path sets familyFriendly=true for users with children and then keeps
  -- only is_family_friendly rows, so essentials must be flagged true to remain
  -- visible to family cases (it does not hide them from non-family users).
  true
FROM seed s
JOIN public.resource_categories cat ON cat.key = s.category_key
JOIN public.resource_sources src ON src.source_name = s.source_name
WHERE NOT EXISTS (
  SELECT 1 FROM public.country_resources cr
  WHERE cr.country_code = 'DE' AND cr.title = s.title
);

COMMIT;
