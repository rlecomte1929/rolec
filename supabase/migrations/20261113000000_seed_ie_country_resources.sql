-- [AIQ-1746 / T18-06 · data seed] Ireland (IE) country resources.
--
-- Ireland had ZERO rows in country_resources (verified 2026-08-20: DE 21 published,
-- FR 18, NO 18 + 6 Stavanger drafts, DK 7 drafts, IE 0), so an IE/Dublin case fell
-- through to the generic Python defaults. This is a CONTENT seed only — NO schema
-- change — into the canonical CMS tables, mirroring
-- 20260722000000_seed_de_country_resources.sql.
--
-- HONESTY / PROVENANCE (CLAUDE.md content-provenance): every row carries a real
-- source_url via resource_sources. Content is official-source-grounded guidance
-- ("representative"), not fabricated specifics. Sources are Irish government and
-- statutory public-information bodies (T0), plus the standard rental-market
-- reference (T1).
--
-- Two facts here are recent enough that most third-party guides are still wrong,
-- so they are stated explicitly and dated:
--   * Rent Pressure Zones were ABOLISHED on 1 March 2026 (RTB), replaced by
--     national rent control (2 percent or CPI, whichever is lower) with 6-year
--     tenancy cycles. Any RPZ-based guidance is stale.
--   * Ireland is NOT in the EU Blue Card scheme and is NOT in the Schengen area.
--
-- Nationality is deliberately NOT branched on: country_resources has no nationality
-- dimension (audience_type is 'all' on every existing row) and nationality never
-- reaches the resources read path. The residence-registration row below is therefore
-- written to be true for BOTH branches — no registration for EEA/Swiss, IRP within
-- 90 days for non-EEA — rather than asserting one and being wrong for the other.
--
-- Idempotent: categories/sources upsert on their unique keys; resources insert only
-- when an identical (country_code,title) row doesn't already exist. Safe to re-run.

BEGIN;

-- 1. Sections (resource_categories) — same keys the DE seed uses.
INSERT INTO public.resource_categories (key, label, description, icon_name, sort_order, is_active) VALUES
  ('admin_essentials', 'Admin essentials', 'Registration, tax ID, banking — the first official steps', 'clipboard', 10, true),
  ('housing',          'Housing',          'How the rental market works and what you need to apply',     'home',      20, true),
  ('healthcare',       'Healthcare',       'Health insurance, finding a doctor, emergency numbers',       'heart',     30, true),
  ('daily_life',       'Daily life',       'Mobile, shopping, recycling — settling-in basics',            'shopping',  40, true),
  ('transport',        'Transport',        'Public transport, the Leap Card, driving',                    'train',     50, true),
  ('cost_of_living',   'Cost of living',   'Typical monthly costs and money norms',                       'wallet',    60, true)
ON CONFLICT (key) DO NOTHING;

-- 2. Provenance sources (resource_sources) — Irish official / statutory portals.
INSERT INTO public.resource_sources (source_name, publisher, source_type, url, trust_tier) VALUES
  ('Citizens Information',                  'Citizens Information Board (statutory)', 'official',      'https://www.citizensinformation.ie', 'T0'),
  ('gov.ie — Department of Social Protection', 'Government of Ireland',               'official',      'https://www.gov.ie', 'T0'),
  ('Revenue Commissioners',                 'Office of the Revenue Commissioners',    'official',      'https://www.revenue.ie', 'T0'),
  ('Residential Tenancies Board (RTB)',     'Residential Tenancies Board',            'official',      'https://www.rtb.ie', 'T0'),
  ('Health Service Executive (HSE)',        'Health Service Executive',               'official',      'https://www2.hse.ie', 'T0'),
  ('Transport for Ireland (Leap Card)',     'National Transport Authority',           'official',      'https://about.leapcard.ie', 'T0'),
  ('National Driver Licence Service (NDLS)','Road Safety Authority',                  'official',      'https://www.ndls.ie', 'T0'),
  ('Daft.ie Rental Report',                 'Daft.ie / Ronan Lyons',                  'institutional', 'https://www.daft.ie/report', 'T1')
ON CONFLICT (source_name) DO NOTHING;

-- 3. Resources (country_resources), joined to category + source by key/name.
WITH seed(title, summary, body, resource_type, category_key, source_name, external_url, sort_w) AS (
  VALUES
  -- Admin essentials — the ORDER is the advice. Each step issues the document the
  -- next step asks for; a newly-arrived EEA citizen holds no Irish residence document
  -- at all (they get no IRP), so PPSN -> Revenue -> bank is the only sequence that completes.
  ('Step 1 — Get your PPS number (PPSN)',
   'Apply on MyWelfare.ie, then attend a mandatory in-person appointment.',
   'The PPS number is the key that unlocks everything else — payroll, tax, banking and public services. Apply through MyWelfare.ie and you will be given a mandatory in-person appointment. Bring photo ID, a signed offer of employment, and proof of your Irish address dated within the last three months. Allow roughly 10 to 20 days from application to receiving the number, and start it in your first week: nothing else can proceed without it.',
   'guide', 'admin_essentials', 'gov.ie — Department of Social Protection', 'https://www.gov.ie/en/department-of-social-protection/services/get-a-personal-public-service-pps-number/', 1),
  ('Step 2 — Register your job with Revenue yourself',
   'Your employer cannot do this for you. Miss it and emergency tax starts.',
   'Once you have a PPS number, register your employment in Revenue myAccount so that Revenue can issue your employer a Revenue Payroll Notification. Your employer cannot do this step on your behalf. If it is not done, you are taxed on an emergency basis: after four weeks that reaches the higher 40 percent income tax rate plus USC, and although it is refunded later it can badly affect your first months cashflow at exactly the point you are paying a rental deposit.',
   'guide', 'admin_essentials', 'Revenue Commissioners', 'https://www.revenue.ie/en/jobs-and-pensions/emergency-tax/emergency-tax-rules.aspx', 2),
  ('Step 3 — Open an Irish bank account',
   'Banks want photo ID plus a separate proof of address — plan the order.',
   'Irish banks ask for photo identification and, separately, evidence of your Irish address. This is where new arrivals get stuck: you will not yet have a utility bill in your name, and an EEA citizen never receives an Irish Residence Permit to use as a document. Correspondence issued after your PPSN and Revenue registration is usually the first acceptable address evidence you hold, which is why the PPSN and Revenue steps come first.',
   'guide', 'admin_essentials', 'Citizens Information', 'https://www.citizensinformation.ie/en/money-and-tax/personal-finance/banking/financial-institutions-and-identification/', 3),
  ('Residence registration — what applies to you depends on your nationality',
   'EEA and Swiss citizens register nothing. Non-EEA nationals get an IRP within 90 days.',
   'If you are an EU, EEA or Swiss citizen you do not register with the immigration authorities at all and you do not need a residence card to live in Ireland — there is no equivalent of a German Anmeldung or a Norwegian folkeregister step. If you are a non-EEA national you must register and obtain an Irish Residence Permit within 90 days of arrival; first-time registration is done at Burgh Quay in Dublin, costs EUR 300, and an employment-permit holder is normally granted Stamp 1.',
   'guide', 'admin_essentials', 'Citizens Information', 'https://www.citizensinformation.ie/en/moving-country/moving-to-ireland/rights-of-residence-in-ireland/registration-of-non-eea-nationals-in-ireland/', 4),
  ('Exchange your driving licence',
   'EU/EEA licences exchange for EUR 55; most non-EEA licences do not.',
   'A licence issued in another EU or EEA state can be exchanged for an Irish one through the National Driver Licence Service for a fee of EUR 55, without retaking the test. Licences from most other countries cannot be exchanged and require the full Irish process from the theory test onwards, though an International Driving Permit remains valid for up to 12 months while you work through it. Note that the online exchange route needs a Public Services Card, which itself follows from your PPSN.',
   'official_link', 'admin_essentials', 'National Driver Licence Service (NDLS)', 'https://www.ndls.ie/licensed-driver/exchange-my-foreign-driving-licence.html', 5),
  -- Housing
  ('How the Dublin rental market works',
   'Very tight and fast — properties go in days and viewings are group slots.',
   'Dublin has persistent excess demand, so listings move in days rather than weeks and viewings are frequently run as group slots with many attendees. Have your documents ready as a single PDF before you start looking: photo identification, an employment contract or offer letter, and a landlord or agent reference if you have one. Deposits are typically one month rent, and the deposit plus first month is due at signing.',
   'guide', 'housing', 'Daft.ie Rental Report', 'https://www.daft.ie/', 1),
  ('Rent controls changed on 1 March 2026',
   'Rent Pressure Zones were abolished and replaced by national rent control.',
   'Rent Pressure Zones ended on 1 March 2026 and were replaced by a national rent control system under which increases are capped at 2 percent or the rate of inflation, whichever is lower, alongside longer 6-year tenancy cycles. A great deal of published guidance still describes the RPZ regime and is out of date. Whatever your agreement says, register the tenancy with the Residential Tenancies Board — it is the landlord obligation but it is your protection in a dispute.',
   'official_link', 'housing', 'Residential Tenancies Board (RTB)', 'https://www.rtb.ie/', 2),
  ('What Dublin rent actually costs',
   'Dublin averages roughly EUR 2,012 for a 1-bed and EUR 2,609 for a 2-bed.',
   'The Daft.ie Rental Report for Q1 2026 puts the Dublin-wide average at about EUR 2,012 per month for a one-bedroom property and EUR 2,609 for a two-bedroom. Sub-market variation is large and the report quotes two different geographic bases, so compare like with like: a two-bedroom runs approximately EUR 2,850 in the South City against EUR 2,444 in the North City. Budget rent as the dominant line in your monthly costs.',
   'guide', 'housing', 'Daft.ie Rental Report', 'https://www.daft.ie/report', 3),
  -- Healthcare
  ('Healthcare is not free at the point of use',
   'Expect EUR 45–65 per GP visit; a professional salary will not qualify for a medical card.',
   'Ireland does not provide free general practice to most workers. The medical card that covers GP visits is means tested, and with a single-person income limit around EUR 184 per week a professional salary will not qualify. GP fees are unregulated and typically fall between EUR 45 and EUR 65 per consultation. Many employers provide private health insurance, which is worth activating before you arrive rather than after.',
   'guide', 'healthcare', 'Citizens Information', 'https://www.citizensinformation.ie/en/health/medical-cards-and-gp-visit-cards/medical-card-means-test-under-70s/', 1),
  ('Register with a GP early',
   'Many Dublin practices are closed to new patients.',
   'Register with a general practitioner soon after you arrive rather than waiting until you are unwell. A significant number of Dublin practices are not accepting new patients, so it can take several attempts to find one with capacity, and your GP is also the gateway to referrals and to avoiding the emergency department charge.',
   'official_link', 'healthcare', 'Health Service Executive (HSE)', 'https://www2.hse.ie/services/find-a-gp/', 2),
  ('Emergency numbers and the EUR 100 ED charge',
   '112 and 999 both work. Attending ED without a GP referral costs EUR 100.',
   'Both 112 and 999 reach the emergency services in Ireland. Attending a hospital emergency department without a referral from a GP carries a charge of EUR 100 per visit; the charge does not apply if your GP has referred you, which is another reason to register with a practice early.',
   'tip', 'healthcare', 'Citizens Information', 'https://www.citizensinformation.ie/en/health/health-services/gp-and-hospital-services/hospital-charges/', 3),
  -- Transport
  ('Get a Leap Card',
   '90-minute fare EUR 2, daily cap EUR 6, weekly cap EUR 24.',
   'The Leap Card is the cheapest way to use Dublin public transport and it caps your spending automatically, so you never pay more than the cap however many journeys you make. A 90-minute fare covering multiple services costs EUR 2, the daily cap is EUR 6 and the weekly cap is EUR 24. Buy one at the airport or in most convenience shops on arrival.',
   'official_link', 'transport', 'Transport for Ireland (Leap Card)', 'https://about.leapcard.ie/', 1),
  ('Buses, DART and Luas — there is no metro',
   'Dublin runs on buses, the DART coastal rail line and two Luas tram lines.',
   'Dublin has no metro system. The network is buses, the DART electrified coastal railway running north and south along the bay, and two Luas tram lines. Traffic is heavy and city-centre parking is expensive, so most commuters do not drive in. Check journeys on the Transport for Ireland planner, which covers all operators together.',
   'guide', 'transport', 'Transport for Ireland (Leap Card)', 'https://www.transportforireland.ie/', 2),
  -- Daily life
  ('Utilities, broadband and bin collection',
   'Energy and broadband are switchable; refuse collection is a private contract you arrange.',
   'Electricity and gas are arranged by you directly and you can switch supplier freely, so comparing prices is worthwhile. Broadband is competitive and widely available in Dublin. The detail that catches most new arrivals is refuse: household bin collection is not a council service you inherit with the property but a private contract you arrange yourself with an operator.',
   'tip', 'daily_life', 'Citizens Information', 'https://www.citizensinformation.ie/en/environment/waste-management-and-recycling/household-waste-collection/', 1),
  -- Cost of living
  ('Dublin cost snapshot',
   'Rent dominates; transport is capped; healthcare is pay-per-visit.',
   'Dublin is expensive by European standards and rent is the dominant line in almost every budget: roughly EUR 2,012 a month for a one-bedroom and EUR 2,609 for a two-bedroom on Daft.ie Q1 2026 figures. Public transport is capped at EUR 24 a week with a Leap Card. Budget separately for healthcare, which is pay-per-visit at EUR 45 to EUR 65 for a GP unless you have private cover.',
   'guide', 'cost_of_living', 'Daft.ie Rental Report', 'https://www.daft.ie/report', 1),
  ('Salaries, tax and how bills are paid',
   'Salaries are quoted gross; income tax, USC and PRSI are deducted at source.',
   'Irish salaries are quoted gross and your employer deducts income tax, the Universal Social Charge and PRSI through the PAYE system before you are paid. Most recurring bills — rent, utilities, insurance — are paid by SEPA direct debit from an Irish current account, which is a further reason to complete the PPSN, Revenue and bank sequence promptly.',
   'tip', 'cost_of_living', 'Revenue Commissioners', 'https://www.revenue.ie/en/jobs-and-pensions/index.aspx', 2)
)
INSERT INTO public.country_resources
  (country_code, country_name, category_id, title, summary, body, resource_type,
   audience_type, language_code, source_id, trust_tier, external_url,
   status, is_visible_to_end_users, is_active, is_family_friendly)
SELECT
  'IE', 'Ireland', cat.id, s.title, s.summary, s.body, s.resource_type,
  'all', 'en', src.id, src.trust_tier, s.external_url,
  'published', true, true,
  -- Same rationale as the DE seed: the page read-path sets familyFriendly=true for
  -- users with children and then keeps only is_family_friendly rows, so relocation
  -- essentials must be flagged true to stay visible to family cases. It does not
  -- hide them from anyone else.
  true
FROM seed s
JOIN public.resource_categories cat ON cat.key = s.category_key
JOIN public.resource_sources src ON src.source_name = s.source_name
WHERE NOT EXISTS (
  SELECT 1 FROM public.country_resources cr
  WHERE cr.country_code = 'IE' AND cr.title = s.title
);

COMMIT;
