# ReloPass - Pre-Departure Health Bundle (NO -> FR, Paris/France)

**Bundle file:** `fr-predeparture-health-2026-09-10.bundle.json`
**Traveller:** "Denis" (French / EEA national) plus accompanying family
**Corridor:** Norway -> France (EEA arrival)
**Status:** All resources are `draft` (candidate-only, pending review).

## What this is

A candidate research bundle covering pre-departure and on-arrival HEALTH steps for an
EEA national and family relocating to Paris. For EEA arrivals the relevant story is
CPAM / PUMa affiliation + carte Vitale and continuity of cover - NOT an entry
vaccination gate.

## Contents

- **Resources:** 8
- **Sources:** 8 (all official: `ameli.fr` and `service-public.gouv.fr`)
- **Categories:** Healthcare
- **Events:** none

## Topics covered

1. **EHIC / CEAM + S1 (gap cover)** - order the EHIC/CEAM before departure (free, online,
   at least 20 days ahead); CEAM is for temporary stays while the portable S1 is used to
   register in the new country of residence. (2 resources + S1 guide)
2. **CPAM / Assurance Maladie (PUMa) affiliation & carte Vitale** - opening rights on the
   basis of stable and lawful residence or first hour worked (form S1106 / S1110), the
   3-month wait if not working, updating the carte Vitale; plus the returning-national
   scenario. (3 resources)
3. **Medecin traitant** - choosing and declaring a treating doctor (form S3704) and the
   parcours de soins coordonnes. (1 resource)
4. **Medical records & repeat prescriptions** - carrying records/prescriptions and using
   Mon espace sante. (1 resource)
5. **Recommended vaccinations (routine, EEA context)** - the French calendrier vaccinal
   applies to all residents; check the family is up to date. (1 resource)

## Source-access notes

- Every `source_url` was fetched and read on an official source and directly supports the
  resource body. Domains used: `ameli.fr`, `service-public.gouv.fr` (the current official
  domain of service-public.fr).
- Several deep ameli.fr pages (choisir-et-declarer-votre-medecin-traitant,
  vaccination/faire-vacciner, and the CEAM ordering page) repeatedly returned empty
  content via the scraper and could NOT be verified. Rather than cite an unread page, the
  equivalent, verifiable official pages were used instead:
  - Medecin traitant -> `service-public.gouv.fr` fiche F163.
  - Vaccination calendar -> `service-public.gouv.fr` fiche F724.
  - CEAM ordering -> `service-public.gouv.fr` demarche R49815.
- No fact, fee, deadline, URL, or citation was invented. Anything that could not be
  verified on an official source was omitted (e.g. exact vaccine lists/ages were not
  transcribed; the resource points to the official calendar instead).

## Disclaimer

Candidate-only draft for internal review. Not legal or medical advice. Verify all
details against the linked official sources before publishing to end users.
