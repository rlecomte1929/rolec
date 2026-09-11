# AD-P2 · Singapore pre-departure health resources (FR->SG)

**batch_id:** `sg-predeparture-health-2026-09-10`
**corridor:** FR-SG (Paris -> Singapore) · destination-side health
**persona:** Adrien (EP) + accompanying family (Dependant's Pass)
**artifact:** `sg-predeparture-health-2026-09-10.bundle.json` · **resources:** 7 · **events:** 1
**sha256:** `f745a6aad2a7ed78e68c01578000f6e15e4c4022d93ff73ce14abe2ef294159d`

## Status (all resources)
- status: `draft` (every resource and event)
- All content is candidate-only, awaiting human/lawyer verification.

## Format
JSON ImportBundle: `{ categories, tags, sources, resources, events }`. Every resource is `country_code=SG`, `city_name=Singapore`, `category_key=healthcare`, with a verbatim official-source quote embedded in the body.

## Coverage
1. EP medical examination - decided per case, stated on the IPA, done after arrival (MOM).
2. Dependant's Pass eligibility ($6,000 salary threshold) + medical form (MOM).
3. Bringing prescription medication - 3-month rule, prescription letter, original packaging (HSA).
4. Controlled-substance medication needs HSA approval, apply >=2 weeks before arrival (HSA) - flagged non-obvious.
5. Prohibited medications - cannabis extracts, chewing-gum form, CTGTP (HSA) - flagged non-obvious.
6. Private health insurance - EP holders are NOT covered by MediShield Life (MOH) - flagged non-obvious.
7. Finding a GP after arrival - SMC-registered doctors, HealthHub, GPGoWhere (HSA).

## Sources (official only)
- **mom.gov.sg** - Employment Pass application; Dependant's Pass eligibility
- **hsa.gov.sg** - Travelling with medications to Singapore (personal medications)
- **moh.gov.sg** - MediShield Life

## Notes / access
- No official-source access issues for this package. ica.gov.sg has a medical-examination-report form but the EP medical-exam trigger is stated on the MOM EP page (the IPA letter), which was used instead.
- The strongest non-obvious flags for Adrien: (a) a routine French prescription may be a controlled substance requiring HSA approval; (b) CBD/cannabis products legal in France are prohibited in Singapore; (c) EP + DP holders are not on MediShield Life and need private cover.
