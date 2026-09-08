-- Migration: 20260522190000_seed_pet_import_rules.sql
-- Purpose: Seed pet_import_rules with country-specific data for 15 destination countries.
--          Two species rows per country (dog + cat).  Source-verified May 2026.
-- Task: AIQ-160-D  Created: 2026-05-22

-- Use ON CONFLICT DO UPDATE so this seed is idempotent (safe to re-run).

INSERT INTO public.pet_import_rules
  (destination_country_code, species, requirements, quarantine_days,
   microchip_required, rabies_cert_required, health_cert_required,
   notes, source_url, last_verified_at)
VALUES

-- ─── Australia ────────────────────────────────────────────────────────────────
(
  'AU', 'dog',
  '["ISO 15-digit microchip (implanted before rabies vaccination)",
    "Rabies vaccination with RNATT titre test ≥ 0.5 IU/mL (blood draw ≥ 180 days before travel)",
    "External parasite treatment within 21 days before travel",
    "Health certificate from accredited vet",
    "Import permit from DAFF (apply ≥ 5 weeks in advance)",
    "Flights only via approved quarantine stations (Mickleham, Melbourne)"]'::jsonb,
  10, true, true, true,
  'All pets arriving in Australia undergo 10-day quarantine at Mickleham. The 180-day RNATT waiting period is the most common trip-planner pitfall. New Zealand–origin animals face different rules (see NZ).',
  'https://www.agriculture.gov.au/biosecurity-trade/cats-dogs',
  '2026-05-01'
),
(
  'AU', 'cat',
  '["ISO 15-digit microchip (implanted before rabies vaccination)",
    "Rabies vaccination with RNATT titre test ≥ 0.5 IU/mL (blood draw ≥ 180 days before travel)",
    "External parasite treatment within 21 days before travel",
    "Health certificate from accredited vet",
    "Import permit from DAFF (apply ≥ 5 weeks in advance)",
    "Flights only via approved quarantine stations (Mickleham, Melbourne)"]'::jsonb,
  10, true, true, true,
  'Same rules as dogs. Cats not originating from approved countries require 10-day quarantine at Mickleham. Specialist cat carriers may be required for the quarantine period.',
  'https://www.agriculture.gov.au/biosecurity-trade/cats-dogs',
  '2026-05-01'
),

-- ─── New Zealand ──────────────────────────────────────────────────────────────
(
  'NZ', 'dog',
  '["ISO 15-digit microchip",
    "Rabies vaccination + RNATT titre test ≥ 0.5 IU/mL (not required for AU-origin)",
    "Import permit (apply ≥ 30 working days in advance)",
    "Health certificate issued within 10 days of departure",
    "Tick and flea treatment within 48 hours before departure",
    "Internal parasite (tapeworm) treatment 14–21 days before departure"]'::jsonb,
  10, true, true, true,
  'Australia-origin dogs are exempt from the titre test but still require a 10-day quarantine. Only Air New Zealand and Qantas carry pets to NZ. Import permit required before booking a flight.',
  'https://www.mpi.govt.nz/importing-animals-plants/live-animals/pets/',
  '2026-05-01'
),
(
  'NZ', 'cat',
  '["ISO 15-digit microchip",
    "Rabies vaccination + RNATT titre test ≥ 0.5 IU/mL (not required for AU-origin)",
    "Import permit (apply ≥ 30 working days in advance)",
    "Health certificate issued within 10 days of departure",
    "Tick and flea treatment within 48 hours before departure"]'::jsonb,
  10, true, true, true,
  'Same quarantine and permit rules as dogs. New Zealand has a zero-tolerance policy on pests; non-compliance results in the pet being returned or euthanised.',
  'https://www.mpi.govt.nz/importing-animals-plants/live-animals/pets/',
  '2026-05-01'
),

-- ─── United Kingdom ───────────────────────────────────────────────────────────
(
  'GB', 'dog',
  '["ISO 15-digit microchip (before or same day as rabies vaccination)",
    "Rabies vaccination (pets from unlisted countries: titre test ≥ 0.5 IU/mL + 3-month wait)",
    "Animal Health Certificate (AHC) issued within 10 days of travel",
    "Tapeworm (Echinococcus) treatment 1–5 days before arrival",
    "Entry only via POAO-approved routes/carriers"]'::jsonb,
  0, true, true, true,
  'Post-Brexit: EU Pet Passports no longer valid for entry into GB. An AHC is required for every trip. Dogs must have tapeworm treatment — this is unique to GB and often missed.',
  'https://www.gov.uk/bring-pet-to-great-britain',
  '2026-05-01'
),
(
  'GB', 'cat',
  '["ISO 15-digit microchip (before or same day as rabies vaccination)",
    "Rabies vaccination (pets from unlisted countries: titre test ≥ 0.5 IU/mL + 3-month wait)",
    "Animal Health Certificate (AHC) issued within 10 days of travel"]'::jsonb,
  0, true, true, true,
  'No tapeworm treatment required for cats. AHC required per trip — cannot reuse. Cats from unlisted countries must wait 3 months post-titre test.',
  'https://www.gov.uk/bring-pet-to-great-britain',
  '2026-05-01'
),

-- ─── Japan ────────────────────────────────────────────────────────────────────
(
  'JP', 'dog',
  '["ISO 15-digit microchip",
    "Two rabies vaccinations using inactivated vaccines only (primary + booster; specific timing requirements)",
    "RNATT titre test ≥ 0.5 IU/mL at APHIS-approved lab (180-day wait after blood draw)",
    "Health certificate issued within 10 days of arrival",
    "Advance notification to Quarantine Station (40 days before arrival)",
    "Rabies antibody test result endorsed by official veterinarian"]'::jsonb,
  0, true, true, true,
  'Japan has the strictest dog import rules of any OECD country. The full process takes 180+ days. Only inactivated rabies vaccines are accepted. Failure to meet any documentation step results in extended quarantine (up to 180 days at owner''s expense). Advance notification 40 days before arrival is mandatory.',
  'https://www.maff.go.jp/aqs/animals/dog/index.html',
  '2026-05-01'
),
(
  'JP', 'cat',
  '["ISO 15-digit microchip",
    "Two rabies vaccinations using inactivated vaccines only",
    "RNATT titre test ≥ 0.5 IU/mL at APHIS-approved lab (180-day wait after blood draw)",
    "Health certificate issued within 10 days of arrival",
    "Advance notification to Quarantine Station (40 days before arrival)"]'::jsonb,
  0, true, true, true,
  'Same 180-day protocol as dogs. Cats arriving without correct documentation are quarantined for up to 180 days at owner''s cost in Tokyo or Osaka facilities.',
  'https://www.maff.go.jp/aqs/animals/dog/index.html',
  '2026-05-01'
),

-- ─── Singapore ────────────────────────────────────────────────────────────────
(
  'SG', 'dog',
  '["ISO 15-digit microchip",
    "Rabies vaccination (Schedule I/II countries) or RNATT titre test (Schedule III)",
    "Import licence from AVS (apply via GoBusiness portal)",
    "Health certificate from government-accredited vet",
    "All import procedures handled by AVS-recognised agents at CAPQ only (from April 2026)",
    "Approved breeds only — no banned/restricted breeds"]'::jsonb,
  0, true, true, true,
  'From April 2026, all dog/cat imports must use AVS-recognised agents at the Central Animal Processing Quarantine (CAPQ) facility. Schedule I (AU, NZ, UK, etc.) = 0-day quarantine. Schedule III (rabies-endemic) = 30-day. Breed restrictions apply — Pit Bulls and Akitas prohibited.',
  'https://www.nparks.gov.sg/avs/pets/bringing-animals-into-singapore-and-exporting/bringing-in-and-transiting-dogs-and-cats/importing-dogs',
  '2026-05-01'
),
(
  'SG', 'cat',
  '["ISO 15-digit microchip",
    "Rabies vaccination (Schedule I/II countries) or RNATT titre test (Schedule III)",
    "Import licence from AVS (apply via GoBusiness portal)",
    "Health certificate from government-accredited vet",
    "All import procedures handled by AVS-recognised agents at CAPQ only (from April 2026)"]'::jsonb,
  0, true, true, true,
  'Cats follow the same schedule-based quarantine tiers as dogs (0 days for Schedule I/II; 30 days for Schedule III). No breed restrictions for cats.',
  'https://www.nparks.gov.sg/avs/pets/bringing-animals-into-singapore-and-exporting/bringing-in-and-transiting-dogs-and-cats/importing-cats',
  '2026-05-01'
),

-- ─── France ───────────────────────────────────────────────────────────────────
(
  'FR', 'dog',
  '["ISO 15-digit microchip (implanted before or same day as first rabies vaccination)",
    "Rabies vaccination (primary + booster every 1–3 years as per manufacturer)",
    "EU Pet Passport (for EU-resident pets) or Animal Health Certificate — AHC (for non-EU residents; valid 10 days from issue date, 4 months for return trips)",
    "Tapeworm (Echinococcus) treatment 1–5 days before entry (required from some third countries)",
    "EU Pet Passport mandatory within EU from 22 April 2026"]'::jsonb,
  0, true, true, true,
  'France follows EU Regulation 576/2013. From 22 April 2026, EU Pet Passports became mandatory for travel between EU member states. Non-EU residents need an AHC per trip. Three-pet maximum per traveller unless competing.',
  'https://agriculture.ec.europa.eu/farming/animal-health/movement-pets_en',
  '2026-05-01'
),
(
  'FR', 'cat',
  '["ISO 15-digit microchip (implanted before or same day as first rabies vaccination)",
    "Rabies vaccination (primary + booster every 1–3 years)",
    "EU Pet Passport (EU residents) or AHC (non-EU residents; valid 10 days)",
    "EU Pet Passport mandatory within EU from 22 April 2026"]'::jsonb,
  0, true, true, true,
  'Same EU Reg. 576/2013 rules as dogs. No tapeworm treatment required for cats entering France.',
  'https://agriculture.ec.europa.eu/farming/animal-health/movement-pets_en',
  '2026-05-01'
),

-- ─── Germany ──────────────────────────────────────────────────────────────────
(
  'DE', 'dog',
  '["ISO 15-digit microchip",
    "Rabies vaccination current (valid within manufacturer''s stated interval)",
    "EU Pet Passport (EU residents) or AHC (non-EU residents)",
    "EU Pet Passport mandatory within EU from 22 April 2026"]'::jsonb,
  0, true, true, true,
  'Germany follows EU Reg. 576/2013. Breed restrictions under Hundeverbringungs- und -einfuhrbeschränkungsgesetz (HundVerbrEinfG) — banned breeds include Pit Bull Terrier, American Staffordshire, Staffordshire Bull Terrier, Bull Terrier. Check federal state (Bundesland) rules too.',
  'https://agriculture.ec.europa.eu/farming/animal-health/movement-pets_en',
  '2026-05-01'
),
(
  'DE', 'cat',
  '["ISO 15-digit microchip",
    "Rabies vaccination current",
    "EU Pet Passport (EU residents) or AHC (non-EU residents)",
    "EU Pet Passport mandatory within EU from 22 April 2026"]'::jsonb,
  0, true, true, true,
  'Same EU Reg. 576/2013. No breed restrictions for cats.',
  'https://agriculture.ec.europa.eu/farming/animal-health/movement-pets_en',
  '2026-05-01'
),

-- ─── Netherlands ──────────────────────────────────────────────────────────────
(
  'NL', 'dog',
  '["ISO 15-digit microchip",
    "Rabies vaccination current",
    "EU Pet Passport (EU residents) or AHC (non-EU residents)",
    "EU Pet Passport mandatory within EU from 22 April 2026"]'::jsonb,
  0, true, true, true,
  'Netherlands follows EU Reg. 576/2013. Amsterbull and related breeds restricted under Honden Besluit. AHC required for non-EU travelers entering NL directly.',
  'https://agriculture.ec.europa.eu/farming/animal-health/movement-pets_en',
  '2026-05-01'
),
(
  'NL', 'cat',
  '["ISO 15-digit microchip",
    "Rabies vaccination current",
    "EU Pet Passport (EU residents) or AHC (non-EU residents)"]'::jsonb,
  0, true, true, true,
  'Standard EU rules. No additional NL-specific requirements for cats.',
  'https://agriculture.ec.europa.eu/farming/animal-health/movement-pets_en',
  '2026-05-01'
),

-- ─── Spain ────────────────────────────────────────────────────────────────────
(
  'ES', 'dog',
  '["ISO 15-digit microchip",
    "Rabies vaccination current",
    "EU Pet Passport (EU residents) or AHC (non-EU residents)",
    "EU Pet Passport mandatory within EU from 22 April 2026"]'::jsonb,
  0, true, true, true,
  'Spain follows EU Reg. 576/2013. Potentially Dangerous Dog (PPP) breed list under RD 287/2002 — includes Rottweiler, Pit Bull, Doberman etc.; insurance and muzzle requirements apply. Some regions have stricter rules.',
  'https://agriculture.ec.europa.eu/farming/animal-health/movement-pets_en',
  '2026-05-01'
),
(
  'ES', 'cat',
  '["ISO 15-digit microchip",
    "Rabies vaccination current",
    "EU Pet Passport (EU residents) or AHC (non-EU residents)"]'::jsonb,
  0, true, true, true,
  'Standard EU rules. No additional ES-specific requirements for cats.',
  'https://agriculture.ec.europa.eu/farming/animal-health/movement-pets_en',
  '2026-05-01'
),

-- ─── Italy ────────────────────────────────────────────────────────────────────
(
  'IT', 'dog',
  '["ISO 15-digit microchip (mandatory since 2005 for all Italian-resident dogs)",
    "Rabies vaccination current",
    "EU Pet Passport (EU residents) or AHC (non-EU residents)",
    "EU Pet Passport mandatory within EU from 22 April 2026"]'::jsonb,
  0, true, true, true,
  'Italy follows EU Reg. 576/2013. All dogs resident in Italy must be microchipped and registered in the national anagrafe canina. This requirement applies immediately on relocation.',
  'https://agriculture.ec.europa.eu/farming/animal-health/movement-pets_en',
  '2026-05-01'
),
(
  'IT', 'cat',
  '["ISO 15-digit microchip",
    "Rabies vaccination current",
    "EU Pet Passport (EU residents) or AHC (non-EU residents)"]'::jsonb,
  0, true, true, true,
  'Standard EU rules. Italy recommends voluntary microchip registration in the anagrafe felina (cat registry) but it is not legally mandatory.',
  'https://agriculture.ec.europa.eu/farming/animal-health/movement-pets_en',
  '2026-05-01'
),

-- ─── Portugal ─────────────────────────────────────────────────────────────────
(
  'PT', 'dog',
  '["ISO 15-digit microchip",
    "Rabies vaccination current",
    "EU Pet Passport (EU residents) or AHC (non-EU residents)",
    "EU Pet Passport mandatory within EU from 22 April 2026"]'::jsonb,
  0, true, true, true,
  'Portugal follows EU Reg. 576/2013. Dangerous/aggressive breeds under Decreto-Lei 315/2009 require insurance, sterilisation, and cannot be rehomed — verify breed status before relocation.',
  'https://agriculture.ec.europa.eu/farming/animal-health/movement-pets_en',
  '2026-05-01'
),
(
  'PT', 'cat',
  '["ISO 15-digit microchip",
    "Rabies vaccination current",
    "EU Pet Passport (EU residents) or AHC (non-EU residents)"]'::jsonb,
  0, true, true, true,
  'Standard EU rules. No PT-specific requirements beyond EU Reg. 576/2013 for cats.',
  'https://agriculture.ec.europa.eu/farming/animal-health/movement-pets_en',
  '2026-05-01'
),

-- ─── Switzerland ─────────────────────────────────────────────────────────────
(
  'CH', 'dog',
  '["ISO 15-digit microchip",
    "Rabies vaccination current (minimum 21 days old at time of travel)",
    "EU Pet Passport or AHC accepted (CH recognises EU pet travel documents)",
    "Registration in AMICUS national dog database required within 10 days of arrival"]'::jsonb,
  0, true, true, true,
  'Switzerland is not an EU member but has adopted equivalent pet movement rules via bilateral agreements. The EU AHC format is accepted. All dogs must be registered in AMICUS within 10 days of establishment of residence.',
  'https://www.blv.admin.ch/blv/en/home/tiere/reisen-mit-heimtieren.html',
  '2026-05-01'
),
(
  'CH', 'cat',
  '["ISO 15-digit microchip",
    "Rabies vaccination current",
    "EU Pet Passport or AHC accepted"]'::jsonb,
  0, true, true, true,
  'Same bilateral-agreement framework as dogs. No mandatory cat registry in CH, but microchip registration in a Swiss database is recommended.',
  'https://www.blv.admin.ch/blv/en/home/tiere/reisen-mit-heimtieren.html',
  '2026-05-01'
),

-- ─── United Arab Emirates ─────────────────────────────────────────────────────
(
  'AE', 'dog',
  '["ISO 15-digit microchip",
    "Rabies vaccination (valid; boosters per manufacturer''s schedule)",
    "DHPP/DHPL core vaccinations (distemper, hepatitis, parvovirus, leptospirosis)",
    "Health certificate issued by USDA/CFIA/official vet endorsed by MOCCAE",
    "Import permit from MOCCAE (valid 90 days; apply online minimum 30 days before travel)",
    "Maximum 2 pets per person per year"]'::jsonb,
  0, true, true, true,
  'MOCCAE (Ministry of Climate Change & Environment) is the competent authority. Import permit is mandatory before shipping. A 2-pet/person/year import limit is enforced. Brachycephalic breeds have airline carry restrictions; verify with airline. Some local emirate-level rules may apply.',
  'https://www.moccae.gov.ae/en/services/veterinary-affairs-services/pet-import.aspx',
  '2026-05-01'
),
(
  'AE', 'cat',
  '["ISO 15-digit microchip",
    "Rabies vaccination (valid)",
    "FVRCP core vaccinations (feline herpesvirus, calicivirus, panleukopenia)",
    "Health certificate issued by official vet endorsed by MOCCAE",
    "Import permit from MOCCAE (valid 90 days)",
    "Maximum 2 pets per person per year"]'::jsonb,
  0, true, true, true,
  'Same import permit and 2-pet limit as dogs. Cats are generally well-tolerated in AE; no breed bans. FeLV/FIV testing not mandatory but often required by airlines.',
  'https://www.moccae.gov.ae/en/services/veterinary-affairs-services/pet-import.aspx',
  '2026-05-01'
),

-- ─── Canada ───────────────────────────────────────────────────────────────────
(
  'CA', 'dog',
  '["Rabies vaccination certificate required for dogs ≥ 3 months old",
    "Health certificate for commercial imports or dogs < 8 months old",
    "Microchip strongly recommended but not legally required for entry",
    "Dogs from the US or other countries: declare at border; CFIA may inspect"]'::jsonb,
  0, false, true, false,
  'Canada CFIA rules are among the most relaxed for pet-friendly countries. Dogs under 8 months from commercial sources need a health cert. Provinces may have additional requirements (e.g., Ontario requires rabies vaccination by law within 30 days of residency).',
  'https://inspection.canada.ca/importing-food-plants-or-animals/pets/eng/1326600389775/1326600500578',
  '2026-05-01'
),
(
  'CA', 'cat',
  '["No federal entry requirements for cats from most countries",
    "Microchip recommended but not required",
    "Declaration at border required; CFIA may inspect"]'::jsonb,
  0, false, false, false,
  'Canada has no federal rabies vaccination or health certificate requirement for cats from most countries. Some airlines still require a health certificate — check carrier requirements separately.',
  'https://inspection.canada.ca/importing-food-plants-or-animals/pets/eng/1326600389775/1326600500578',
  '2026-05-01'
),

-- ─── United States ────────────────────────────────────────────────────────────
(
  'US', 'dog',
  '["ISO 15-digit or 11-digit microchip (ISO or AVID) required for dogs arriving from high-risk countries",
    "Rabies vaccination required for dogs from high-risk countries (CDC list)",
    "CDC Dog Import Form (DogImportForm.cdc.gov) required for ALL dogs entering the US",
    "Valid rabies vaccination documentation from a licensed vet",
    "Dogs must appear healthy at point of entry"]'::jsonb,
  0, true, true, false,
  'CDC''s updated 2024 dog import rule: ALL dogs entering the US (regardless of origin) must complete the CDC Dog Import Form online before arrival. Microchip and rabies requirements depend on the dog''s country of origin — high-risk countries have stricter rules. Dogs without proper documentation may be denied entry.',
  'https://www.cdc.gov/importation/dogs.html',
  '2026-05-01'
),
(
  'US', 'cat',
  '["Cats must appear healthy at port of entry",
    "No federal microchip, vaccination, or health certificate requirement for most cats"]'::jsonb,
  0, false, false, false,
  'The US has no federal rabies vaccination, microchip, or health certificate requirement for cats from most countries. Some states may have additional rules post-entry. Airlines may require a health certificate — check carrier requirements.',
  'https://www.cdc.gov/importation/cats.html',
  '2026-05-01'
)

ON CONFLICT (destination_country_code, species)
DO UPDATE SET
  requirements          = EXCLUDED.requirements,
  quarantine_days       = EXCLUDED.quarantine_days,
  microchip_required    = EXCLUDED.microchip_required,
  rabies_cert_required  = EXCLUDED.rabies_cert_required,
  health_cert_required  = EXCLUDED.health_cert_required,
  notes                 = EXCLUDED.notes,
  source_url            = EXCLUDED.source_url,
  last_verified_at      = EXCLUDED.last_verified_at,
  updated_at            = now();
