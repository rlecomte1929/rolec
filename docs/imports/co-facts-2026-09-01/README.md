# Colombia requirement facts — 2026-09-02 (wave 10, rank 57)

12 researched, **11 landed** → 11 requirement_items on COLOMBIA (pending), 1 held. Greenfield.
Append-only; expert_verified=0.

## Coverage (pillars): RESIDENCE 5 · EMPLOYMENT 4 · HEALTHCARE 1 · SOCIAL_SECURITY 1
Non-obvious: V/M/R visa types (Resolución 5477/2022); the M-Trabajador work permit locked to the
exact role+employer (any change = new visa); a multi-year M visa auto-voids after 180 continuous
days abroad; >183-day DIAN tax residency pulls worldwide income in with no foreigner grace period;
health EPS mandatory (no home-coverage exemption) but pension affiliation voluntary for foreigners.

## Verification
confirm_quotes 10/12 headless + 1 browser-verified (permanent_residence, cancilleria). Sources
official only (cancilleria.gov.co, migracioncolombia.gov.co, dian.gov.co, funcionpublica.gov.co).
nationality=non-EEA → THIRD_COUNTRY; scope guard clean.

## Held (held.ndjson) — re-source worklist
- **foreigner_id** (Cédula de Extranjería 15-day deadline) — the cited migracioncolombia.gov.co
  page returns empty/redirect in both curl and browser; the quote could not be verified. Re-source
  the 15-day deadline from a loadable Migración page or the governing decree.
