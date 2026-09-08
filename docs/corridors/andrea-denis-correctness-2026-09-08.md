# Andrea / Denis content-correctness gate — 2026-09-08

**Card:** [AIQ-2160](https://app.notion.com/p/3c5887c64d4881f18c2ee21815faf5cd)  
**Method:** relocator-trust closed loop (`docs/specs/relocator-trust-closed-loop.md`) + repo corridor bindings.  
**Writes:** none to `requirement_items` / `requirement_facts`.  
**UI walk:** not done this session (no employee login). Public API table from 2026-09-08 is the content check, not Q7.

Personas: **Andrea** ES→IE VE CSEP · **Denis** NO→FR FR returning EEA. Adrien / Abraham are out of this card’s Expected Output; they are noted only where they show a related serving defect.

## Set-level verdict (criterion 4)

| Corridor | One coherent person? | Finding |
|---|---|---|
| ES→IE / Andrea | **No — firehose** | Public serve: 206 rows, class `THIRD_COUNTRY`. CSEP is present, but the list is not a digest of *her* move. Origin side is empty in the binding (`corridors/ES_IE/facts.yaml` `origin_facts: []`). |
| NO→FR / Denis | **No — thin + possible dual person** | Public serve: 21 rows, class `OWN_NATIONAL`. Origin bindings exist (4 `origin_facts` in git) but Q2 was INCOMPLETE on the public list. Prior set-level contradiction (ws 636 outside French SS vs 637/630 inside) is still the failure mode to re-check in admin; not re-measured live this session. |

## Defect rate (criterion 2) — API / binding grain, not 206-row claim-vs-quote

This pass does **not** yet judge every served requirement CORRECT/WRONG. That needs the hydrated plan screen + admin row walk. Grain used here is the **seven relocator questions**.

| Persona | Questions judged | TRUSTED | INCOMPLETE | MISSING | MISINFORM | UNTRUSTED / not walked |
|---|---|---|---|---|---|---|
| Andrea | 7 | 1 leaning (Q4) | Q1, Q5 | Q2 | — | Q3, Q6, Q7 not walked in UI |
| Denis | 7 | 0 | Q1, Q2, Q4, Q5 | — | — | Q3, Q6, Q7 no live case / not walked |

**Andrea rate this grain:** 0/7 TRUSTED. **Denis:** 0/7 TRUSTED.

## WRONG / urgent first (criterion 3)

None newly proven WRONG for Andrea/Denis on 2026-09-08 without a logged-in walk.

**Carry-forward WRONG-class (from AIQ-1845 worksheet, still the user-facing consequence until admin re-checks):**

1. **GEP first-application fee** served as €1,500 for 6–36 months. Official first application is €1,000 up to 24 months (€500 ≤6 months); €1,500 is renewal. Consequence: employer over-budgets ~€500 on a first GEP. Gate that would catch it: none of classify_source / quote / URL-resolve / attestation — only claim-vs-source of the *fee table*.
2. **CSEP 90% refund (€900)** cited on a page that does not contain “refund”. Consequence: false cash-flow expectation. Quote gate should catch if quote is empty or off-claim; landing-page / unsupported-specifics class.

**Adrien (out of card, do not mix into Andrea/Denis rate):** Q3 **MISINFORM** if UI shows a generic “30 days” on FR→SG EP.

## Question-level findings (Andrea / Denis)

| Q | Andrea | Denis | Smallest next fix (separate card) |
|---|---|---|---|
| Q1 mine? | INCOMPLETE — 206-row firehose; CSEP present | INCOMPLETE — 21 rows, own-national | Digest / nationality-scoped checklist, not more facts |
| Q2 origin? | **MISSING** — `origin_facts: []` still true in git 2026-09-08 | INCOMPLETE — 4 origin bindings in git; not in public dest list | **AIQ-2062 A2** (reopened Otto ready): Spain exit NDJSON still absent (`docs/imports/es-departure-*` not in repo) |
| Q3 order/days? | not walked | no live case | Hydrate + walk plan (AIQ-2145 notes VE hydration 2026-09-02; re-ask required) |
| Q4 traps? | TRUSTED-leaning (emergency tax, IRP 90d in payload) | INCOMPLETE | Keep; do not dilute with GEP fee if she is CSEP-only |
| Q5 source? | INCOMPLETE — 6 empty `source`; **45 truncated labels (code fix in repo, not on Render yet)** | INCOMPLETE — 5 unsourced incl. DPAE + tax domicile; confirmation URL added in repo | Truncation + EEA IRP leak = serving; empty seed sources left (dropping them hides emergency tax) |
| Q6 act this week? | not walked | not walked | **AIQ-2048** family forms (Otto): IE still 0 templates; CTA is empty list |
| Q7 product? | not walked | no live case | Same as Q3 |

## Which shipped gates would have caught each class (criterion 7)

| Defect class | classify_source | quote gate | URL identifies a rule | URL resolves | attestation | this card |
|---|---|---|---|---|---|---|
| Empty origin set | no | no | no | no | no | **yes** (set-level / Q2) |
| Firehose / N/A over-serve | no | no | no | no | no | **yes** |
| GEP fee vs table | no | only if quote ≠ claim | maybe | yes | no | **yes** |
| Truncated labels | no | no | no | no | no | **yes** (UNTRUSTED copy) |
| Empty `source` on served row | no | related | no | n/a | no | **yes** |
| Join-family CTA → empty forms | no | no | no | no | no | **yes** (Q6/Q7) |
| Set contradiction 636 vs 637 | no | no | no | no | no | **yes** |

## Criterion 6 (no catalog writes)

This file only. Row counts in prod were not mutated.

## Live re-measure — 2026-09-08 (public API, after first pass)

`GET /api/public/corridor-requirements` (prod, commit on Render may lag this repo):

| Query | n | class | truncated `label` | empty `source` |
|---|---|---|---|---|
| ES→IE `nationality=VE` | 206 | THIRD_COUNTRY | **45** (all 178 chars; full claim in `description`) | 6 seed rows (tax residence, split-year, RPN, emergency tax, PRSI, combining contributions) |
| ES→IE `nationality=ES` | 163 | EU_EEA | 45 | 7 |
| NO→FR `nationality=FR` | 21 | OWN_NATIONAL | 0 | 5 (incl. DPAE, tax domicile, plus unsourced confirmation) |
| FR→SG `nationality=FR` | 16 | THIRD_COUNTRY | 0 | 4 + **Minimum lead time / 30 days** still served |

**EEA control still MISINFORM-risk:** ES national on ES→IE is served titles starting `Non-EEA nationals…` (IRP) because `appliesToNationalityClasses` is NULL.

**GEP fee (AIQ-1845 carry-forward):** description on prod is now the official first-application €1,000 / €500 and renewal €1,500. Verdict **CORRECT** (the €1,500 needle is renewal copy). Do not treat as WRONG.

**CSEP refund:** still served (“90% … €900 is refunded”). Claim-vs-source of the *fees* page remains open — admin, not this code change.

## Code that changes those verdicts (this session)

Serve-time only. No `requirement_items` writes.

1. **Truncated labels** — `display_title()` uses the first description line when the title ends in `…` / `...`. Wired on the public list and the case dossier builder. Expected: Andrea Q5 truncated-label class → 0 on those 45 rows after deploy.
2. **NULL-scoped Non-EEA titles** — EEA / own-national lists drop rows whose title is an instruction *to* Non-EEA/Non-EU. Expected: ES control Q1 MISINFORM-risk for IRP → gone.
3. **Generic 30-day lead** — dropped for `THIRD_COUNTRY`. Expected: Adrien Q3 MISINFORM if UI showed that row.
4. **Own-national confirmation citation** — europa.eu residence-rights URL. Expected: Denis confirmation empty-source → sourced. The other four unsourced FR rows stay (catalog citations), not withheld — dropping DPAE would hide a real obligation.

**Not done:** origin binding (`origin_facts: []` until Otto A2). Empty-source *seed* IE rows not filtered (Q4 emergency-tax would disappear).

Tests: `backend/tests/test_requirement_serve_hygiene.py`, four new cases in `test_public_corridor.py`.

## Stop condition for the next session

1. Deploy the serve-hygiene change; re-curl ES→IE VE and ES EEA.  
2. Logged-in Andrea plan: re-ask Q3 and Q7.  
3. Admin: CSEP refund quote vs enterprise.gov.ie fees page.  
4. Otto A2 still required for Andrea Q2.
