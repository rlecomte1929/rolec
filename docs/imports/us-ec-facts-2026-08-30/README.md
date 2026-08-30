# US→EC requirement facts — Abraham (Seattle → Quito), 2026-08-30

First requirement-fact batch for the **greenfield US→EC** corridor (Abraham Romo, a US professional
moving to Quito). Ecuador has no free-movement scheme → **third-country / residence-visa** audience:
`applies_to.nationality="non-EEA"`, `status="professional"`, `corridor="US->EC"`.

## Landed (1 requirement at `review_status='pending'`, `representative`)
Otto delivered **14** facts from `.gob.ec` hosts; `verify_ledger.py` reached all 7 pages and confirmed
13 quotes, 0 rejected (the referee's fetcher read the `.gob.ec` pages Otto's own scraper timed out on).

**2 `fact_type='other'` facts were then dropped for citation quality** — a bare statistic
(`stat_167000_cedulas`) and a "homepage lists RUC" note (`ruc_menu_sri`), both citing a `.gob.ec`
*homepage*, which the `test_check_otto_batches_citations` gate refuses. The SRI RUC "requirement" they
would have formed was deleted from prod; it rested entirely on that homepage citation. 12 facts remain,
promoting **1** requirement:

| requirement | pillar | facts |
|---|---|---|
| Cédula de identidad para extranjeros con residencia temporal | IDENTITY | 7 (registrocivil.gob.ec/cedulacion/) |

Behind the `/admin/countries` gate. EC was greenfield — no pre-existing staged rows, no collisions.

## Onboarding done for this corridor
- **Catalog key** `EC→ECUADOR` — already in `requirements_country_key.py` (#2105).
- **Allowlist** — added `gob.ec` to `_OFFICIAL_SUFFIXES` (`parsers.py`); Spain's `gob.es` doesn't
  catch `.ec` and the bare `gov` doesn't either. 5th too-narrow-allowlist instance. Regression test added.
- **`catalog_destination_allowlist`** — `INSERT (city='Quito', country='Ecuador')` applied to prod as a
  data backfill (makes Quito a selectable destination). PK is `(city, country)`, so idempotent.
- **Corridor profile** — `corridors/US_EC/corridor.yaml` exists (#2105).

## Blocked / worklist (corridor is NOT complete — the core is missing)
- **IESS social security (5 facts) — UNMAPPED.** Staged `ready` but did not promote: Otto put mixed
  pillars on one topic (4 SOCIAL_SECURITY + 1 HEALTHCARE), and a topic maps to exactly one requirement
  = one pillar. **Fix:** re-brief Otto to split IESS into pension (SOCIAL_SECURITY) and health
  (HEALTHCARE) topics; the facts are verified and waiting.
- **The three core pillars returned 0 facts** — JS-rendered / down gov portals defeated Otto's scraper:
  visa/RESIDENCE (`cancilleria.gob.ec` empty), work authorization (`trabajo.gob.ec` timeout), RUC/tax
  183-day rule (`sri.gob.ec` deep paths 404).
- **The #1 non-obvious trap — "90-day visa-exempt entry is TOURIST status and does NOT permit work"**
  — is in `rejects.ndjson` (`fact_key EC-TOURIST-TRAP:eligibility:90day_no_work`, slot preserved),
  because Otto couldn't get a verbatim quote off the JS-rendered cancilleria page. Browser-ground it
  (the pattern used for Denis's tax facts) to land the single most important EC fact.

So EC serves the cédula + RUC identity/tax-registration surface today; the visa, work-auth and tax-rule
core needs a browser-grounding round before the corridor is usable for a real mover.
