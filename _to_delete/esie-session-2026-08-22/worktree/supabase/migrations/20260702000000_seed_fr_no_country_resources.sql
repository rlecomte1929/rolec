-- [RESOURCE-CONTENT-1 follow-up / data seed] France (FR) + Norway (NO) country resources.
--
-- Same pattern as 20260701000000_seed_de_country_resources.sql: content-only seed
-- (no schema change) into the canonical CMS tables, reusing the 6 sections and adding
-- official FR/NO sources + 18 published resources per country across Admin essentials /
-- Housing / Healthcare / Daily life / Transport / Cost of living.
--
-- HONESTY / PROVENANCE: every resource carries a real source_url (official French /
-- Norwegian government portals, trust_tier T0). Content is accurate, official-source-
-- grounded guidance ('representative'), not fabricated specifics.
-- is_family_friendly=true so essentials stay visible for family cases (the page read-
-- path keeps only is_family_friendly rows when familyFriendly is set).
-- Idempotent: categories/sources upsert on unique keys; resources guarded by
-- NOT EXISTS on (country_code,title). Safe to re-run.

BEGIN;

-- Sections already exist from the DE seed; ensure present (no-op if so).
INSERT INTO public.resource_categories (key, label, description, icon_name, sort_order, is_active) VALUES
  ('admin_essentials', 'Admin essentials', 'Registration, ID, banking — the first official steps', 'clipboard', 10, true),
  ('housing',          'Housing',          'How the rental market works and what you need to apply',  'home',      20, true),
  ('healthcare',       'Healthcare',       'Health cover, finding a doctor, emergency numbers',        'heart',     30, true),
  ('daily_life',       'Daily life',       'Mobile, shopping, recycling — settling-in basics',         'shopping',  40, true),
  ('transport',        'Transport',        'Public transport and driving',                             'train',     50, true),
  ('cost_of_living',   'Cost of living',   'Typical costs, taxes and money norms',                     'wallet',    60, true)
ON CONFLICT (key) DO NOTHING;

-- Official FR + NO sources
INSERT INTO public.resource_sources (source_name, publisher, source_type, url, trust_tier) VALUES
  ('Welcome to France (Government)', 'French Government / Campus France', 'official', 'https://www.welcometofrance.com', 'T0'),
  ('Service-Public.fr',             'French Government', 'official', 'https://www.service-public.fr', 'T0'),
  ('Ameli (Assurance Maladie)',     'French Health Insurance', 'official', 'https://www.ameli.fr', 'T0'),
  ('Impots.gouv.fr',                'French Tax Administration', 'official', 'https://www.impots.gouv.fr', 'T0'),
  ('New in Norway (Government)',     'Norwegian Government', 'official', 'https://www.nyinorge.no', 'T0'),
  ('UDI (Directorate of Immigration)', 'Norwegian Directorate of Immigration', 'official', 'https://www.udi.no', 'T0'),
  ('Skatteetaten (Tax Administration)', 'Norwegian Tax Administration', 'official', 'https://www.skatteetaten.no', 'T0'),
  ('Helsenorge',                    'Norwegian Directorate of e-Health', 'official', 'https://www.helsenorge.no', 'T0')
ON CONFLICT (source_name) DO NOTHING;

-- France (FR)
WITH seed(country_code, country_name, title, summary, body, resource_type, category_key, source_name, external_url) AS (
  VALUES
  ('FR','France','Validate your visa / residence permit','Non-EU arrivals validate their long-stay visa with OFII, then apply at the prefecture.','Non-EU nationals with a long-stay visa (VLS-TS) must validate it online with OFII within three months of arrival, then apply for or renew a residence permit (titre de sejour) at the prefecture. EU/EEA citizens do not need a permit. Keep copies of every document.','guide','admin_essentials','Welcome to France (Government)','https://www.welcometofrance.com/en/residence-permit'),
  ('FR','France','Register for social security','Register with Assurance Maladie to get a social security number.','Register with the French health system (Assurance Maladie) to get a social security number and access healthcare reimbursement. Your employer or ameli handles the registration; you will need ID and proof of residence.','official_link','admin_essentials','Ameli (Assurance Maladie)','https://www.ameli.fr/assure/droits-demarches/principes/protection-universelle-maladie-puma'),
  ('FR','France','Open a French bank account','A compte courant is needed for salary, rent and direct debits.','A French current account (compte courant) is needed for your salary and rent. Banks ask for ID, proof of address (justificatif de domicile) and often your residence permit. You receive a RIB (bank details) used to set up direct debits.','guide','admin_essentials','Welcome to France (Government)','https://www.welcometofrance.com/en/open-a-bank-account'),
  ('FR','France','How renting works in France','Rent + charges; a deposit and sometimes a guarantor are usual.','Rentals quote the loyer (rent) plus charges. Expect a deposit (depot de garantie, usually one month unfurnished) and the landlord may require a guarantor (garant). Leases are typically three years unfurnished or one year furnished.','guide','housing','Service-Public.fr','https://www.service-public.fr/particuliers/vosdroits/N20360'),
  ('FR','France','Documents to rent a flat (dossier)','Landlords ask for a dossier: ID, payslips, contract, tax notice.','Landlords ask for a dossier: ID, proof of income (around three payslips), your employment contract, last tax notice, and often a guarantor. The state Visale scheme can act as a free guarantor for eligible tenants.','checklist_item','housing','Service-Public.fr','https://www.service-public.fr/particuliers/vosdroits/F1169'),
  ('FR','France','Housing benefit (APL) and utilities','You may get housing aid from CAF; arrange electricity before moving.','You may be eligible for housing assistance (APL) from CAF, paid monthly. Electricity and gas are arranged by you directly, so set up a contract before you move in.','guide','housing','Service-Public.fr','https://www.service-public.fr/particuliers/vosdroits/F12006'),
  ('FR','France','Health cover and the carte Vitale','Once registered you get a carte Vitale; a mutuelle covers the rest.','Once registered with Assurance Maladie you receive a carte Vitale for automatic reimbursement. Many people also take a complementary insurance (mutuelle), often through their employer, to cover the part not reimbursed.','official_link','healthcare','Ameli (Assurance Maladie)','https://www.ameli.fr/assure/remboursements/etre-bien-rembourse/carte-vitale'),
  ('FR','France','Choose a GP (medecin traitant)','Declare a primary doctor for full reimbursement and referrals.','Declare a medecin traitant (primary doctor) with Assurance Maladie to get full reimbursement and referrals to specialists. You can change your declared doctor at any time.','guide','healthcare','Ameli (Assurance Maladie)','https://www.ameli.fr/assure/remboursements/etre-bien-rembourse/medecin-traitant-parcours-soins-coordonnes'),
  ('FR','France','Emergency numbers','15 SAMU (medical), 18 fire, 17 police, 112 EU-wide.','In an emergency: 15 for medical (SAMU), 18 for fire, 17 for police, or 112 across the EU. 114 is the emergency number for people who are deaf or hard of hearing.','tip','healthcare','Service-Public.fr','https://www.service-public.fr/particuliers/vosdroits/F12483'),
  ('FR','France','Mobile phones and internet','Prepaid and contract plans; contracts need a French RIB.','Prepaid (sans engagement) and contract mobile plans are widely available. Contract plans and home internet usually require a French bank account (RIB). Compare operators for coverage and price.','guide','daily_life','Welcome to France (Government)','https://www.welcometofrance.com/en/daily-life-in-france'),
  ('FR','France','Shopping and opening hours','Many shops close Sunday afternoons and some Mondays; markets are common.','Many shops close on Sunday afternoons and some on Monday mornings. Fresh-produce markets (marches) are common and worth seeking out. Larger supermarkets keep longer hours.','tip','daily_life','Welcome to France (Government)','https://www.welcometofrance.com/en/daily-life-in-france'),
  ('FR','France','Waste sorting (tri selectif)','Recyclables, glass and general waste are separated; rules vary by commune.','France separates recyclable packaging (often a yellow bin), glass, and general waste; the exact rules vary by commune. Check your building or town hall (mairie) for local collection days.','tip','daily_life','Service-Public.fr','https://www.service-public.fr/particuliers/vosdroits/F33840'),
  ('FR','France','Public transport passes','Cities have integrated networks; in Paris the Navigo pass covers all modes.','French cities have integrated public transport. In the Paris region the Navigo pass covers metro, RER, bus and tram on one subscription. Always validate your ticket or pass.','guide','transport','Welcome to France (Government)','https://www.welcometofrance.com/en/getting-around-in-france'),
  ('FR','France','Trains (SNCF)','SNCF runs regional (TER) and high-speed (TGV) trains; book ahead.','SNCF operates regional (TER) and high-speed (TGV) trains. Booking in advance gives much cheaper fares on long-distance routes. Regional travel often uses the same transport passes.','guide','transport','Welcome to France (Government)','https://www.welcometofrance.com/en/getting-around-in-france'),
  ('FR','France','Driving licence exchange','Drive on your licence for up to a year, then exchange it.','Depending on the issuing country, you can usually drive on your existing licence for up to one year, then must exchange it for a French one. Some licences exchange without a test; others require one.','guide','transport','Service-Public.fr','https://www.service-public.fr/particuliers/vosdroits/F1460'),
  ('FR','France','Typical monthly costs','Rent is the main cost; budget for mutuelle and transport.','Rent is usually your biggest cost. Also budget for a complementary health insurance (mutuelle), transport, and utilities. The taxe d''habitation has been abolished for most main residences.','guide','cost_of_living','Welcome to France (Government)','https://www.welcometofrance.com/en/cost-of-living-in-france'),
  ('FR','France','Income tax (prelevement a la source)','Income tax is withheld at source; you still file an annual return.','French income tax is withheld directly from your salary (prelevement a la source). You still file an annual income declaration, which adjusts the amount. Keep your payslips and tax notices.','official_link','cost_of_living','Impots.gouv.fr','https://www.impots.gouv.fr/particulier/le-prelevement-la-source'),
  ('FR','France','Banking and salary norms','Salaries are net on the payslip; bills are paid by prelevement.','Salaries on your payslip are shown net after social charges. Rent and most bills are paid by direct debit (prelevement) using your RIB, so keep your account funded.','tip','cost_of_living','Welcome to France (Government)','https://www.welcometofrance.com/en/open-a-bank-account')
)
INSERT INTO public.country_resources
  (country_code, country_name, category_id, title, summary, body, resource_type, audience_type,
   language_code, source_id, trust_tier, external_url, status, is_visible_to_end_users, is_active, is_family_friendly)
SELECT s.country_code, s.country_name, cat.id, s.title, s.summary, s.body, s.resource_type, 'all',
   'en', src.id, src.trust_tier, s.external_url, 'published', true, true, true
FROM seed s
JOIN public.resource_categories cat ON cat.key = s.category_key
JOIN public.resource_sources src ON src.source_name = s.source_name
WHERE NOT EXISTS (SELECT 1 FROM public.country_resources cr WHERE cr.country_code=s.country_code AND cr.title=s.title);

-- Norway (NO)
WITH seed(country_code, country_name, title, summary, body, resource_type, category_key, source_name, external_url) AS (
  VALUES
  ('NO','Norway','Residence permit and police registration','Apply via UDI; non-EU arrivals confirm the permit with the police.','Non-EU nationals apply for a residence permit through UDI before or after arriving, then book an appointment with the police to confirm it. EU/EEA nationals register with the police if staying longer than three months.','guide','admin_essentials','UDI (Directorate of Immigration)','https://www.udi.no/en/want-to-apply/'),
  ('NO','Norway','Get a national ID number (D-number)','Register with the Tax Administration for an ID number, needed for everything.','Register with the Tax Administration (Skatteetaten) to get a national identity number or a D-number. You need it for a bank account, salary, healthcare and most contracts. Book an ID check appointment.','official_link','admin_essentials','Skatteetaten (Tax Administration)','https://www.skatteetaten.no/en/person/national-registry/move/move-to-norway/'),
  ('NO','Norway','Tax deduction card and bank account','Order a skattekort so the right tax is withheld; open a bank account.','Order a tax deduction card (skattekort) from Skatteetaten so your employer withholds the correct tax. Open a Norwegian bank account (you need your ID number) to receive your salary and pay bills.','guide','admin_essentials','Skatteetaten (Tax Administration)','https://www.skatteetaten.no/en/person/taxes/tax-deduction-cards-and-advance-tax/'),
  ('NO','Norway','How renting works in Norway','Mostly unfurnished; a deposit goes into a separate deposit account.','Most rentals are unfurnished. Expect a deposit (depositum) of up to three months'' rent, which must be held in a separate deposit account (depositumskonto) in your name. Read the lease (leiekontrakt) carefully.','guide','housing','New in Norway (Government)','https://www.nyinorge.no/en/New-in-Norway/Housing/Renting-a-home/'),
  ('NO','Norway','Finding and applying for a home','Most rentals are listed on finn.no; bring ID and proof of income.','Most rental homes are advertised on finn.no. Bring ID and proof of income when applying. Make sure the deposit goes into a proper deposit account and that the contract is in writing.','checklist_item','housing','New in Norway (Government)','https://www.nyinorge.no/en/New-in-Norway/Housing/'),
  ('NO','Norway','Electricity and registering your address','Electricity is self-arranged; report your address after moving.','Electricity is arranged by you directly and prices vary by region and season. After moving, report your address to the National Registry so official post reaches you.','guide','housing','New in Norway (Government)','https://www.nyinorge.no/en/New-in-Norway/Housing/'),
  ('NO','Norway','The GP scheme (fastlege)','Residents get a regular GP; change it online via Helsenorge.','Residents are assigned a regular GP (fastlege) through the public health service. You can change your GP or check your assignment online via Helsenorge. The GP refers you to specialists.','official_link','healthcare','Helsenorge','https://www.helsenorge.no/en/'),
  ('NO','Norway','Health services and the frikort','Public care has modest fees up to a yearly cap, then a frikort.','Public healthcare charges modest fees up to an annual cap; once you reach it you automatically receive a frikort (exemption card) and pay nothing more that year. Children are largely exempt.','guide','healthcare','Helsenorge','https://www.helsenorge.no/en/'),
  ('NO','Norway','Emergency numbers','113 medical, 110 fire, 112 police; 116117 non-urgent medical.','In an emergency: 113 for medical, 110 for fire, 112 for police. For urgent but non-life-threatening medical help, call 116117 to reach the on-call service.','tip','healthcare','Helsenorge','https://www.helsenorge.no/en/emergencies-and-the-emergency-room/'),
  ('NO','Norway','Mobile phones and internet','SIMs are sold in shops; registration needs ID.','SIM cards are available in shops and supermarkets; you register them with ID. Contract plans and home broadband usually need a Norwegian bank account. Coverage is strong in populated areas.','guide','daily_life','New in Norway (Government)','https://www.nyinorge.no/en/New-in-Norway/'),
  ('NO','Norway','Shopping and Vinmonopolet','Groceries are pricey; stronger alcohol is sold only at Vinmonopolet.','Groceries and eating out are expensive in Norway. Alcohol stronger than about 4.7% is sold only at the state Vinmonopolet shops, which keep limited opening hours, so plan ahead.','tip','daily_life','New in Norway (Government)','https://www.nyinorge.no/en/New-in-Norway/'),
  ('NO','Norway','Bottle deposit (pant) and recycling','Bottles and cans carry a deposit refunded at shop machines.','Many bottles and cans carry a deposit (pant) refunded at machines in supermarkets when you return them. Household waste is sorted (paper, food, plastics, residual) - check your local scheme.','tip','daily_life','New in Norway (Government)','https://www.nyinorge.no/en/New-in-Norway/'),
  ('NO','Norway','Public transport','Cities have integrated transport with ticket apps (e.g. Ruter in Oslo).','Norwegian cities have integrated bus, tram and metro networks with mobile ticket apps (for example Ruter in the Oslo region). Buy and activate your ticket before boarding.','guide','transport','New in Norway (Government)','https://www.nyinorge.no/en/New-in-Norway/'),
  ('NO','Norway','Trains and regional travel','Vy runs most trains; book ahead for cheaper fares.','Vy runs most train services in Norway. Booking in advance gives cheaper fares on longer routes. Scenic regional lines are popular, so reserve seats in high season.','guide','transport','New in Norway (Government)','https://www.nyinorge.no/en/New-in-Norway/'),
  ('NO','Norway','Driving licence','EU/EEA licences are valid; others may need to exchange within a year.','Driving licences from the EU/EEA are valid in Norway. Licences from many other countries must be exchanged within one year of residence, sometimes after a test. Check the rules for your country.','guide','transport','New in Norway (Government)','https://www.nyinorge.no/en/New-in-Norway/'),
  ('NO','Norway','Typical costs','Norway is expensive; rent, groceries and eating out are high.','Norway has a high cost of living: budget for high rent, groceries and eating out. Public healthcare and education keep some essential costs low. Salaries are correspondingly higher.','guide','cost_of_living','New in Norway (Government)','https://www.nyinorge.no/en/New-in-Norway/'),
  ('NO','Norway','Taxes','Tax is withheld via your skattekort; check the pre-filled return.','Income tax is withheld through your tax deduction card (skattekort). Each spring you receive a pre-filled tax return to review and correct before the deadline. Keep your documents.','official_link','cost_of_living','Skatteetaten (Tax Administration)','https://www.skatteetaten.no/en/person/taxes/'),
  ('NO','Norway','Banking and salary norms','Salary is paid to your account; bills via online banking / AvtaleGiro.','Your salary is paid into your Norwegian account. Bills are usually paid through online banking or set up as automatic payments (AvtaleGiro / eFaktura). Norway is largely cashless.','tip','cost_of_living','New in Norway (Government)','https://www.nyinorge.no/en/New-in-Norway/')
)
INSERT INTO public.country_resources
  (country_code, country_name, category_id, title, summary, body, resource_type, audience_type,
   language_code, source_id, trust_tier, external_url, status, is_visible_to_end_users, is_active, is_family_friendly)
SELECT s.country_code, s.country_name, cat.id, s.title, s.summary, s.body, s.resource_type, 'all',
   'en', src.id, src.trust_tier, s.external_url, 'published', true, true, true
FROM seed s
JOIN public.resource_categories cat ON cat.key = s.category_key
JOIN public.resource_sources src ON src.source_name = s.source_name
WHERE NOT EXISTS (SELECT 1 FROM public.country_resources cr WHERE cr.country_code=s.country_code AND cr.title=s.title);

COMMIT;
