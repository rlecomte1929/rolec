# ie-predeparture-health-2026-09-10 — Dublin pre-departure health resources (A-P2)

**City:** Dublin (IE) · **Category:** healthcare · ImportBundle JSON.

## What this is
A pre-departure health bundle for Andrea + accompanying family: 6 resources covering
cross-border/repeat prescriptions + Schengen Article 75 controlled-medicine certificate,
bringing medicines through Irish customs, entitlement to Irish public health services (ordinary
residence, with the non-EU dependants nuance), bringing medical/immunisation records + registering
with an Irish GP, the HSE Find-a-GP tool, and the Irish childhood vaccination schedule / catch-up.

## Files
- `ie-predeparture-health-2026-09-10.bundle.json` — {categories, tags, sources, resources, events}

## Provenance & status
- **Official hosts only** — HSE (hse.ie), Citizens Information (citizensinformation.ie), NDLS (ndls.ie), RSA (rsa.ie). Every resource body summarises a page actually fetched; `source_url` is that page.
- All resources `status=draft` (candidate-only). Nothing lawyer-confirmed.

## Honest gaps
- Ireland has **no mandatory entry vaccinations**, so the schedule is sourced from Citizens Information (recommended), not a "required for entry" page.
- **EHIC "cover gap"**: not cleanly covered by a usable official page (the HSE EHIC page fetched was link-only). Rather than fabricate an "EHIC bridges your Madrid->Dublin gap" claim, the entitlement resource states the accurate position: an EHIC covers necessary care during a temporary stay, and a general work/family move does not confer portable EU cover — join the Irish public system once ordinarily resident.
