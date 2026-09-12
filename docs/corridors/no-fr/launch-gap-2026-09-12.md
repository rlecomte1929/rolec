# NO→FR launch gap — 2026-09-12 (Denis, EEA return)

**Corridor id:** `NO_FR` (YAML: quote `"NO"` — bare `NO` is a boolean)
**Legal shape:** French / EEA national returning to France, still on a **Norwegian payroll**. **Not TCN. Not a posting by default.** Pathway `RETURNING_EEA_CITIZEN_2026`. Status: `authoring`.
**KEEP cards:** AIQ-2311 (RP-010 gap audit), AIQ-2067 (D1 destination EEA, Validation), AIQ-2160.

## What is already bound

`corridors/NO_FR/facts.yaml` — eight refs. Destination-side only become `requirement_items` (France). Origin-side stay corridor-surface.

### RP-010 five topic rows (map or missing)

| Topic (card) | Existing `facts.yaml` ref | Fit for Denis? | Gap |
|---|---|---|---|
| **A1** | `EU:social_security-posting:a1_posting` (B2) and `NO:social_security-posting:a1_issued_by_nav` (A5) | **Direction risk.** Both bound facts describe a **Norwegian-issued** A1 that *keeps Norwegian* insurance during a **posting**. The pathway hinge (B1/B2) says permanent relocation is **not** a posting and the A1, if any, is issued by **France (URSSAF)**. Serving the NAV-posting pair to Denis as if he stays in folketrygden is the known ES→IE-style inversion. | **Bound, but wrong shape for this profile.** Do not promote the NAV posting pair as Denis destination truth. New candidate only after a **French** issuer page is quoted (CLEISS / URSSAF / `cleiss.fr`, `urssaf.fr`). `needs_lawyer_review`. |
| **183-day / tax residence** | `FR:tax-residence:residence_criteria` and `FR:tax-residence:worldwide_income` (C4) | French domicile is **CGI art. 4 B three-criteria** (foyer / activité / intérêts économiques), **not** an Irish-style 183-day test. The bound fact is the right French rule. | **Mapped — do not replace with a 183-day invention.** Dual residence vs Norway is Q1/Q2 (`assertion: PENDING`) — counsel, not a new number. |
| **Work authorisation** | None as a destination fact. Pathway C2 is `nothing_to_do` (Dir. 2004/38). | Correct *silence* is a requirement: say there is **no** visa/permit. | **MISSING as a cited destination fact** (the “none, and why”). Fetch `service-public.gouv.fr` / `legifrance.gouv.fr` on EU citizen residence — not a TCN titre. |
| **Professional registration** | None | Only if Denis’s occupation is a *profession réglementée*. No occupation is pinned on the fixture for a generic fetch. | **MISSING — do not author a generic ordre fact.** If a later brief names the profession, fetch that ordre’s official host. |
| **Employer detachment / foreign employer in France** | None bound. Pathway B3 (URSSAF register or Art. 21 delegate) + Q4 PENDING. | CLEISS (fetched 2026-09-12) distinguishes **détaché** (keep origin SS for a mission) vs **expatrié** ( obligatorily under French SS when working in France). Denis’s “Norwegian employer, work in France” is the Art. 21 / firmes étrangères problem, not a NAV posting. | **MISSING as a pending candidate.** Fetch `cleiss.fr`, `urssaf.fr`, and Reg. 987/2009 Art. 21 on `eur-lex.europa.eu`. `needs_lawyer_review`. Do not close Q4 from this note. |

Also already bound, not in the five-row list: `FR:registration-dpae:dpae_before_start` (employer DPAE — HR-owned), `FR:tax-withholding:prelevement_a_la_source`. Origin: `NO:social_security-folketrygdloven:reg_883_via_eea`, `NO:healthcare-posting:s1_during_posting` (same posting-shape caveat as A1).

## Staged batches (not a reason to Human Review this card)

| Batch | Honest state |
|---|---|
| `docs/imports/no-fr-general-curated-2026-08-22/` | 17 curated destination rows; gate-passed as candidates. Quotes still `quote_verbatim_confirmed=false`. |
| `docs/imports/no-fr-transition-requirements-2026-08-22/` | 15 staged in prod historically; **3/15 quotes on-page**. README: not promotable as it stands. Re-source card exists. **Do not promote.** |

## Official sources to fetch

| Topic | URL / host | Allowlist |
|---|---|---|
| Folkeregister move abroad (origin) | `https://www.skatteetaten.no/person/folkeregister/flytte/fra-norge/` — report if abroad **> 6 months**; file **no earlier than 31 days before** the move. Tax residence does **not** end because you filed the move. | `skatteetaten.no` official |
| Norwegian tax after move | `https://www.skatteetaten.no/person/skatt/hjelp-til-riktig-skatt/utland/skatt-flytte-til-utlandet/` | official |
| Coming to work in France / détaché vs expatrié | `https://www.cleiss.fr/particuliers/venir/travailler/index.html` (fetched 2026-09-12) | `cleiss.fr` official |
| DPAE | `entreprendre.service-public.gouv.fr` / `urssaf.fr` | official |
| French tax domicile | `https://www.impots.gouv.fr/resident-de-france` | already quoted in FR.yaml |
| Coordination law | `eur-lex.europa.eu` Reg. 883/2004 Art. 11, Reg. 987/2009 Art. 21 | official |
| Your Europe A1 explainer | `youreurope.europa.eu` | **semi-official** — not enough to auto-accept |

**Pathway vs source conflict to flag (do not silently “fix” the YAML):** A1 Folkeregister step still carries an **8-day post-departure** window marked `PENDING SOURCE VERIFICATION`. Skatteetaten’s live page is **before departure**, earliest **31 days before**, and the duty is tied to a **six-month** stay abroad — not an 8-day after-the-fact window. That is a counsel / authoring correction, not a new approved fact.

## What is missing to serve *approved* facts

1. Counsel close of Q1–Q5 in the pathway (treaty Art. 15, NO source tax, coverage closure, URSSAF mechanics, PUMa vs worker affiliation). Until then the corridor stays `authoring`.
2. Re-shape A1/S1 facts away from “NAV posting keeps Norwegian cover” **or** mark them NOT-APPLICABLE for Denis’s permanent move (AIQ-2160 set-level test).
3. Pending candidates for: “no immigration registration” (cited), URSSAF / Art. 21 (cited), French-issued A1 only if the page says so for *this* fact pattern.
4. Human approval. Otto does not serve.

## Human CVR still required

**Yes — Denis’s real NO→FR move (AIQ-2160).** Especially the set-level contradiction already named on that card (facts that put him both inside and outside French social security). Do not treat a signed row as correct for him.
