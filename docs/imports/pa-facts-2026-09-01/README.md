# Panama requirement facts — 2026-09-02 (wave 10, rank 61)

12 researched, **11 landed** → 11 requirement_items on PANAMA (pending), 1 held. Greenfield.
Append-only; expert_verified=0.

## Coverage (pillars): EMPLOYMENT 5 · RESIDENCE 4 · IDENTITY 1 · SOCIAL_SECURITY 1
Non-obvious: the 2021 Friendly Nations reform (now a 2-year provisional permit → permanent, not
immediate PR); the **Migración ≠ MITRADEL split** (separate residence visa + work permit); Labour
Code foreign-worker quotas (90% national / 15% specialist); Carné validity; CSS affiliation within
6 business days; **territorial taxation** (foreign-source income excluded) + single-salary return
exemption.

## Verification
Panama gov is heavily Imperva/WAF-walled to curl (confirm_quotes reached only 2/12). The other 9
were applier-verified: 5 migracion + 2 Labour-Code (cetippat) via direct curl+pdfplumber of the
real PDFs, 2 panamadigital in-browser. Sources all `.gob.pa`. nationality=non-EEA → THIRD_COUNTRY;
scope guard clean.

## Held (held.ndjson) — re-source worklist
- **specialist_substitution** — the cited Labour Code substring is not verbatim in the PDF
  (`obligación de sustituir al trabajador` is present, but not the exact quoted phrasing). Re-source
  art. 18 with the page's exact wording.
