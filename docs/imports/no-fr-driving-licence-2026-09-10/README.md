# D-P5 - NO->FR driving licence resources (`no-fr-driving-licence-2026-09-10`)

**Package type:** resource JSON (ImportBundle)
**Corridor:** NO -> FR
**Persona:** Denis - Norwegian national (EEA), Oslo -> Paris
**Resources:** 7

## Files
- `no-fr-driving-licence-2026-09-10.json` - ImportBundle with 7 resources
- `no-fr-driving-licence-2026-09-10-manifest.json` - sha256 + counts
- `no-fr-driving-licence-2026-09-10-README.md` - this file

## Status flags (per hard constraints)
- `status`: `draft` (bundle and every resource)
- No DB writes, no webhook calls - files only.

## Bundle shape
`bundle_type`, `schema_version`, `slug`, `corridor` (`NO-FR`), `category` (`driving_licence`), `generated_at`, `status`, `persona`, `resources[]`.
Each resource: `resource_key`, `title`, `url`, `source_authority`, `category` (`driving_licence`), `status` (`draft`), `corridor` (`NO-FR`), `note`.

## Coverage
1. EEA recognition - Norwegian licence valid in France without exchange while valid
2. Optional ANTS exchange procedure (permisdeconduire.ants.gouv.fr)
3. EU/EEA exchange conditions and deadlines
4. Licence categories (B, BE, C ...) and EEA equivalence
5. Lost / stolen foreign licence while resident in France
6. International Driving Permit - not needed within EEA, useful for third countries
7. Renewing / replacing a Norwegian licence (Statens vegvesen)

## Accuracy note
Resource URLs point to authoritative issuers (Service-Public.fr, ANTS, Statens vegvesen). They are marked `status: draft`; exact Service-Public fiche numbers should be confirmed at verification. The core rule - a valid Norwegian EEA licence needs **no** exchange to drive in France - is the headline non-obvious relief for this corridor.
