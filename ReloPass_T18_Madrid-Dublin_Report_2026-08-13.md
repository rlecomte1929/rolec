# ReloPass Test Campaign — T18: Madrid → Dublin

**Scenario:** Amazon Spain → Google Ireland, permanent local hire, relocation-agent supported
**Run date:** 13 August 2026 · **Runner:** `madrid_dublin_runner.mjs` (T18, purpose-built)
**Target:** `api.relopass.com` (commit `0833d3a9`) · **Method:** API-driven, cloud sandbox
**Personas:** two, run identically apart from citizenship

| | Persona A | Persona B |
|---|---|---|
| Name | Lucía Fernández | Priya Raghavan |
| Citizenship | Spanish — **EU/EEA** | Indian — **third country**, resident in Spain |
| Move | Madrid → Dublin, permanent, target 1 Oct 2026 | identical |
| Employer | Google Ireland Ltd, Grand Canal Dock | identical |
| Correct legal path | Free movement. No permit, no visa, no registration. | Critical Skills Employment Permit → D visa → IRP Stamp 1 |

---

## Verdict

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 T18  Madrid → Dublin   •   13 Aug 2026   •   Overall: 41%   RED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 Area                    Pass   Fail   Score   Verdict
 Setup / case lifecycle   10      2     83%    ✅ works
 Agent & coordinator       4      2     67%    🟡 shell only
 Local services            4      6     40%    ❌ wrong country
 Neighbourhood            2      6     25%    ❌ nothing returned
 Documents & papers        2     14     13%    ❌ corridor unsupported
 The journey itself        0      2      0%    ⛔ empty
 ─────────────────────────────────────────────
 OVERALL                  22     32     41%    RED

 P0 blockers: 6      P1: 6      P2: 5
 Persona A vs B divergence: 0 checks out of 27
```

**One-line answer to your question:** ReloPass would sell your friend a Dublin
relocation and then hand her a Singapore school list, a Norwegian bank, an EU Blue
Card that does not exist in Ireland, and a plan screen that says *"No action required
right now"* — seven weeks before she moves country.

The plumbing (auth, case creation, assignment, advisor matching) works. Everything
that constitutes the *product* — the papers, the areas, the services, the journey —
is either empty or belongs to a different country.

---

## The single most important finding

**Every case ReloPass creates is pre-loaded with a hardcoded Oslo → Singapore,
family-of-four profile, and no write path in the API corrects it.**

Immediately after `POST /api/hr/cases` — before anything is entered — the case's
`profile_json` reads:

```json
"movePlan": { "origin": "Oslo, Norway", "destination": "Singapore" },
"familySize": 4,
"dependents": [ {...}, {...} ],
"spouse": { "wantsToWork": true },
"housing": { "bedroomsMin": 3, "budgetMonthlySGD": null },
"schooling": { "budgetAnnualSGD": null }
```

Verified on **4 independently created cases** across 2 personas. `budgetMonthlySGD`
and `budgetAnnualSGD` — Singapore dollars — are baked into the schema.

Then all four routes that should overwrite it fail to:

| Route | Result |
|---|---|
| `PATCH /api/cases/{id}` | **200** — writes to a separate `draft` object; `profile_json` untouched |
| `PATCH /api/cases/{id}/relocationBasics` | **500 Internal Server Error** (`request_id c7f79b10-d808-408a-a591-a5bbbc8a8444`) |
| `PATCH /api/employee/assignments/{aid}/intake-draft` | **200** — `movePlan` still Oslo → Singapore |
| `PUT /api/employee/cases/{id}/relocation-profile` | **200** with every field `null`, `completion_pct: 0`, `last_updated_at: null` — accepted and discarded |

So the case carries **two divergent representations of the same move**: a `draft`
that correctly says Madrid → Dublin, and a `profile_json` that says Oslo → Singapore.
Downstream services read the second one.

This is almost certainly the root cause of Findings 6, 9 and 10 below. **Fix this
first — several other findings may resolve with it.**

---

## P0 blockers

### F1 — Hardcoded Oslo → Singapore seed profile on every case
Above. Root cause candidate for most of the campaign.

### F2 — `PATCH /api/cases/{id}/relocationBasics` returns 500
The canonically-named endpoint for setting the corridor is dead. `request_id
c7f79b10-d808-408a-a591-a5bbbc8a8444`, reproducible. There is currently **no working
API path that sets a case's destination in `profile_json`.**

### F3 — Ireland is sellable but not serviceable
`GET /api/employee/destinations` returns **334 destinations including Dublin**, marked
`"notes": "ReloPass curated"`, approved 2026-05-18. Cork, Galway, Limerick and
Waterford were added 2026-08-12 by a "geo-expansion (top-5 cities per country)" job.

But the immigration engine says:

```json
{ "covered": false, "coverage_reason": "corridor_not_supported", "corridor": "ES→IE" }
```

And `/api/public/corridor-requirements` returns **0 requirements for IE at every
employee type** (PERMANENT, LTA, STA), with `nationality_class: null`.

Control matrix — same query, other destinations:

| Dest | nat=ES (EU) | nat=IN (3rd country) | Branching? |
|---|---|---|---|
| **IE** | **0 reqs, class `null`** | **0 reqs, class `null`** | **none** |
| DE | 7 reqs, `EU_EEA` | 7 reqs, `THIRD_COUNTRY` | ✅ |
| NO | 11 reqs, `EU_EEA` | 8 reqs, `THIRD_COUNTRY` | ✅ |
| NL | 6 reqs, `EU_EEA` | 8 reqs, `THIRD_COUNTRY` | ✅ |
| FR | 5 reqs, `EU_EEA` | 9 reqs, `THIRD_COUNTRY` | ✅ |
| CH, ES | 0 | 0 | none |

The engine is capable — Norway's entries are genuinely good, with sourced text
("*without one, the employer must deduct 50 percent tax*" for the skattekort, citing
Skatteetaten). Ireland simply has nothing in it. The geo-expansion job widened the
catalog without widening the content.

**Note for the repo:** `corridors/ES_IE/corridor.yaml` and
`pathways/CSEP_2026/v1.yaml` exist and are well-reasoned — the 104-day at-risk window
derived from the CSEP step graph is sound. **None of it reaches the deployed API.**
The corridor file's own header already flags this: *"no ES_IE corpus chunks exist yet."*

### F4 — Ireland is offered an EU Blue Card, which does not exist there
`visa_type` defaults to `"blue_card"` for the ES→IE corridor, and is returned to the
**employee** via `/api/employee/cases/{id}/immigration-snapshot`:

```json
{ "covered": false, "corridor_from": "ES", "corridor_to": "IE", "visa_type": "blue_card" }
```

Returned even when `corridor_to=IE` is passed explicitly. The European Commission is
unambiguous: *"The EU Blue Card applies in 25 of the 27 EU Member States. **It does
not apply in Denmark and Ireland.**"* Ireland's instrument is the Critical Skills
Employment Permit.

This is the one finding that is not merely *missing* — it is *wrong*, and it is shown
to the employee. For Persona B it would send her down a legal path that does not exist.

### F5 — The journey screen tells her there is nothing to do
`GET /api/relocation-plans/{case_id}/view`, as the employee, 7 weeks before a
cross-border move:

```json
{ "phases": [], "summary": { "total_tasks": 0 },
  "next_action": null,
  "empty_state_reason": "No action required right now",
  "roadmap_released": true }
```

`roadmap_released: true` means the system believes it has delivered a plan. An empty
state is a gap; **"No action required right now" is a false statement of fact** to
someone who has a PPSN appointment, a Revenue registration, a tenancy and (Persona B)
a 12-week permit lodgement deadline ahead of her.

### F6 — The Dublin marketplace contains no Irish suppliers
`GET /api/employee/assignments/{aid}/marketplace` → **62 vendors, `corridor: null`**,
byte-identical before and after the destination is set:

| Category | n | What she is actually shown |
|---|---|---|
| schools | 32 | Tanglin Trust (Singapore), UNIS (New York), Munich International, Oslo International, Dubai British School… |
| movers | 14 | Asian Tigers, Movers.sg, Shalom Movers, AGS Movers **Norway**, Crown Relocations **Norway** |
| housing_agencies | 8 | Frogner Rental Partners (**Oslo**), Singapore Serviced Residences, Bavaria Rental Agency |
| banks | 3 | **DNB, Nordea Norway, SpareBank1** — all Norwegian |
| tax_finance | 2 | **PwC Norway**, **BDO Norway** |
| legal_admin | 3 | Fragomen, Expat Relocation Norway, **Immigrationlawyer.no** |

**Zero Irish suppliers. Zero Dublin coverage.** Bank of Ireland, AIB, Revolut, an
Irish mover, an Irish letting agent — none present. `corridor: null` means no
destination filter is applied at all, so this list is what *every* case sees.

`GET /api/cases/{id}/vendors` returns `[]` separately.

---

## P1 — high

### F7 — Zero nationality branching, end to end
`GET /api/cases/{id}/requirements` for Persona A (Spanish) and Persona B (Indian) is
**byte-identical apart from `caseId` and `computedAt`**. Both return
`nationalityClass: null`, `requirements: []`, `nationalityWaived: []`.

`GET /api/employee/cases/{id}/intake-nationality` returns `{"nationality": null}`
*after* the employee submitted `nationality: "ES"` through the intake draft.

The distinction that decides everything about this move — free movement vs. a
12-week permit chain — is not captured, not stored, and not acted on. Other corridors
prove the mechanism exists (DE/NO/NL/FR all branch correctly); it never fires for IE
because the corridor is empty, and it could not fire anyway because nationality does
not persist.

### F8 — The employee's immigration view is a dead end
`GET /api/employee/cases/{id}/immigration` → **404**:

> `"No immigration case found for this relocation. Contact your HR team."`

She is assigned to the case, logged in, and the HR side has no way to create the
missing immigration case either (`available-forms: []`, `milestones: []`). "Contact
your HR team" is the terminal state for both roles.

### F9 — No neighbourhood curation for Dublin
- `GET /api/recommendations/housing?case_id=…` → `[]`
- `GET /api/recommendations/schools?case_id=…` → `[]`
- `GET /api/employee/geocode/autocomplete?q=Grand Canal Dock Dublin` → `{"disabled": true, "suggestions": []}`

Geocoding is **disabled in production**, so there is no address entry, no commute
calculation, and no basis for area ranking even if the data existed.

### F10 — The Ireland "settle in" pack is empty scaffolding, and the one populated part is wrong
`GET /api/resources/country?assignment_id=…` returns 12 sections. The profile block is
correct (`destination_country: IE, destination_city: Dublin`) — so the resource layer
*does* see Dublin. The content does not:

```
housing        → "Rental market information will appear here."  neighborhoods: []
schools        → school_types: ["Public","International","Private"]
healthcare     → "Healthcare system and registration."  emergency: "112"
cost_of_living → Average rent "—" · Transport pass "—" · Groceries "—"
community      → groups: []      culture_leisure → events: []
welcome        → "Punctuality is valued", "Formal communication initially"
```

The only section with real content is factually wrong for Ireland:

> `admin_essentials → "Residence registration — Within 7-14 days"`

- **Persona A (EU citizen):** Ireland requires **no residence registration at all**.
  Citizens Information: EEA/Swiss citizens *"do not need to register with the
  immigration authorities and you do not need a residence card to live here."*
- **Persona B (non-EEA):** IRP registration is **within 90 days**, at Burgh Quay,
  €300 — not 7–14 days.

Wrong for both branches. Also note `emergency: "112"` is correct for Ireland, but
999 is the more commonly used Irish number — a generic-EU tell.

### F11 — Geocoding disabled in production
`{"disabled": true}`. Blocks commute-to-Grand-Canal-Dock, the single most useful
input for ranking Dublin areas.

### F12 — No relocation agent can actually be attached to her case
This was one of your four coverage areas, and it is a shell:

- `GET /api/hr/cases/{id}/providers` → `{"providers": []}`
- `GET /api/cases/{id}/coordinator/session` → `{"rolling_summary": "", "recent_turns": [], "model": "", "status": "none"}`
- The role enum is `HR | EMPLOYEE | ADMIN` — **there is no agent/coordinator role.**
  A separate `/api/provider/auth/*` surface exists but nothing links a provider to
  this case.

Her Google-appointed relocation agent has nowhere to sit in the system, cannot see
her case, and cannot hand anything back to HR.

---

## P2 — medium

| # | Finding | Evidence |
|---|---|---|
| **F13** | `GET /api/cases/{id}` returns **404 "Case not found"** to the HR user who just created it, while `PATCH /api/cases/{id}` on the same path returns 200 and `GET /api/hr/cases/{id}` returns 200. Read/write asymmetry on one route. | reproduced on 3 cases |
| **F14** | `POST /api/advisors/match` for ES→IE returns 2 advisors, **neither covering Ireland**: specialisms are *"EU Blue Card"* (doesn't exist in IE), *"schengen long-stay"* (Ireland is not in Schengen), *"EU free movement"*. `contact_url` values are `…example.com` placeholders. Identical for both personas. | `advisors` payload |
| **F15** | `PUT /api/employee/cases/{id}/relocation-profile` returns **200 with every field null** and `completion_pct: 0` — silently discards the submission. No error surfaced. | verify3 run |
| **F16** | `available-forms` → `{"forms": []}`. No CSEP application form, no PPSN REG1, no Revenue job-registration guidance, no IRP booking. Ireland has well-defined forms; none are modelled. | `forms` payload |
| **F17** | `immigration/milestones` → `{"milestones": []}`. No timeline, no deadlines, no at-risk window — despite `corridors/ES_IE/corridor.yaml` defining `at_risk_window_days: 104` in the repo. The corridor file never reaches the case. | `milestones` payload |

---

## What she actually needs — and what ReloPass returned

Researched against DETE, ISD, Revenue, Citizens Information, RTB, Daft and the
European Commission (all sourced below). This is the gap, item by item.

### Persona A — Spanish national (free movement)

| What she needs | ReloPass returned |
|---|---|
| **No permit, no visa, no registration.** The correct first message is *"you need nothing from immigration."* | `visa_type: "blue_card"` ❌ |
| **PPSN** — apply on MyWelfare.ie, then a **mandatory in-person appointment**; needs a signed offer of employment + proof of address **under 3 months old** | nothing |
| **Register the job herself in Revenue myAccount** — the employer cannot do it. Miss it and from **week 5 it is 40% income tax + 8% USC** on a Google salary | nothing |
| **Bank account catch-22** — needs photo ID *plus a distinct* proof of address under 6 months. She has no utility bill, no insurance, and **no IRP (EEA citizens don't get one)**. Realistic sequence: PPSN → Revenue doc → bank | Norwegian banks ❌ |
| **Healthcare is not free.** No medical card at Google salary (limit €184/wk single). GP €45–65, unregulated, many practices closed to new patients. **€100 ED charge without a GP referral** | "Healthcare system and registration." |
| **Spanish licence exchangeable, €65**, but the online route needs a Public Services Card → needs PPSN first | nothing |
| **Rent:** Dublin 1-bed avg **€2,012**, 2-bed **€2,609** (Daft Q1 2026). South City 2-bed **€2,850**; North City **€2,444** | cost_of_living: "—" |
| **RPZs were abolished 1 March 2026**, replaced by national rent control (2% or CPI, whichever lower; 6-year tenancy cycles) | nothing |

### Persona B — Indian national (adds, on top of all of the above)

| What she needs | ReloPass returned |
|---|---|
| **Critical Skills Employment Permit** — SOC 2136 is on the Critical Skills list → **€40,904** threshold (a Google salary clears it easily). Fee €1,000, 90% refunded if refused | `blue_card` ❌ |
| **The binding constraint: the CSEP application must be received ≥12 weeks before the start date.** DETE's current backlog is only ~9 days — the 12-week rule is what actually sets the timeline | no milestones |
| **Long-stay 'D' visa required** — India is visa-required. Applies **via the Irish Embassy in Madrid**, not Delhi. Her **Spanish residence permit gives her no Irish entry right** (Ireland is outside Schengen) — a common and expensive misunderstanding | nothing |
| **IRP within 90 days**, first-time registration **only at Burgh Quay, Dublin**, **€300**, Stamp 1 | "residence registration within 7-14 days" ❌ |
| **Spouse gets Stamp 1G on registration → can work with no permit** (a real CSEP advantage over the General permit's 12-month wait) | nothing |
| **Indian licence is not exchangeable** — full Irish process from the theory test; IDP valid 12 months | nothing |
| Realistic envelope: **~3–4.5 months** offer → first day | plan says "No action required right now" ❌ |

### Three corrections worth pushing into content regardless of this campaign

1. **Ireland is not in the EU Blue Card scheme** (European Commission).
2. **The Trusted Partner Initiative is discontinued** — DETE folded employer
   verification into Employment Permits Online. Most third-party guides still
   advertise it as a fast-track.
3. **Rent Pressure Zones ended 1 March 2026.** Any RPZ-based rent modelling is
   five months stale.

---

## What worked

Worth stating plainly, because the failure list is long:

- Auth, HR registration with a new company, employee registration — clean, ~1.6s
- Case creation and **assignment in 1.45s** (the old B3 hang is gone)
- `PATCH /api/cases/{id}` round-trips the draft correctly and fast
- Dublin, Cork, Galway, Limerick, Waterford **are** in the destination catalog
- The requirements engine **works well where populated** — Norway's entries are
  genuinely high quality, with real citations and non-obvious warnings
- `/api/resources/country` correctly resolves the case to `IE` / `Dublin` — the
  routing is right, only the content is missing
- Advisor matching returns structured results with SLAs and ratings — the shape is
  right, the Irish coverage is not
- API performance was healthy throughout: /health 200 in 2.7s cold, most calls
  0.5–2.2s

**The architecture is not the problem. The Ireland content and one seed-profile bug are.**

---

## Recommended order of work

| # | Action | Unblocks |
|---|---|---|
| 1 | Kill the hardcoded Oslo→Singapore seed; make one write path authoritative for `profile_json` | F1, likely F6, F9, F10 |
| 2 | Fix the 500 on `PATCH /api/cases/{id}/relocationBasics` | F2 |
| 3 | Persist `nationality` from intake → `nationalityClass` | F7, F15 |
| 4 | Remove the `blue_card` default; make `visa_type` corridor-derived, CSEP for IE | F4, F14 |
| 5 | Ingest ES_IE Tier-1 sources; wire `corridors/ES_IE/*` into the deployed engine | F3, F16, F17 |
| 6 | Replace `"No action required right now"` with an honest unsupported-corridor state | F5 |
| 7 | Gate the destination catalog on content coverage, or label uncovered destinations | F3 |
| 8 | Seed Irish suppliers; apply the corridor filter to `/marketplace` | F6 |
| 9 | Re-enable geocoding; populate Dublin areas | F9, F11 |
| 10 | Decide the agent/coordinator model — role, permissions, case linkage | F12 |

Items 1–4 are small and unblock disproportionately. Item 5 is the real content work.

---

## Method & caveats

- **API-driven from the Anthropic cloud sandbox.** `relopass.com` (the frontend) is
  not on this sandbox's network allowlist, so **the browser/UI layer was not tested**.
  Everything above is the API contract the UI consumes. Some findings may present
  differently in the rendered UI — F5's empty plan and F6's Norwegian banks will not.
- 54 checks × 2 personas, plus 42 matrix probes and 3 targeted verification runs.
- Every P0/P1 finding was reproduced on at least 2 independent cases.
- Test accounts are throwaway (`romain+t18*@hotmail.com`, epoch-suffixed). Cases were
  left in place for inspection — case IDs are in the results JSON.
- **CASE-3 correction:** the runner's "nationality not readable" check used
  `GET /api/cases/{id}`, which 404s. `GET /api/hr/cases/{id}` works. That check is
  reclassified as F13 (route asymmetry) rather than a persistence failure — though
  the underlying nationality gap is independently confirmed as F7.
- Nothing was written to Notion, per your instruction.

### Artifacts

- `t18_results_1786634420882.json` — 54 scored checks, both personas
- `t18_evidence_1786634420882.json` — full raw payloads for every check
- `madrid_dublin_runner.mjs` — the runner, re-runnable as-is

---

## Sources

- [European Commission — EU Blue Card (does not apply in Ireland)](https://home-affairs.ec.europa.eu/policies/migration-and-asylum/eu-immigration-portal/eu-blue-card_en)
- [DETE — Critical Skills Employment Permit](https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/)
- [DETE — Current application processing dates](https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/current-application-processing-dates/)
- [DETE — Critical Skills Occupations List](https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/employment-permit-eligibility/highly-skilled-eligible-occupations-list/)
- [DETE — Trusted Partner Initiative (discontinued)](https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/trusted-partner-initiative/)
- [Citizens Information — Residence rights of EU citizens in Ireland](https://www.citizensinformation.ie/en/moving-country/moving-to-ireland/rights-of-residence-in-ireland/residence-rights-eu-national/)
- [Citizens Information — Registration of non-EEA nationals](https://www.citizensinformation.ie/en/moving-country/moving-to-ireland/rights-of-residence-in-ireland/registration-of-non-eea-nationals-in-ireland/)
- [Citizens Information — Visa requirements for entering Ireland](https://www.citizensinformation.ie/en/moving-country/visas-for-ireland/visa-requirements-for-entering-ireland/)
- [Citizens Information — Employment permits and family members](https://www.citizensinformation.ie/en/moving-country/working-in-ireland/employment-permits/spousal-work-permit-scheme/)
- [gov.ie — Get a PPS Number](https://www.gov.ie/en/department-of-social-protection/services/get-a-personal-public-service-pps-number/)
- [Revenue — Emergency Tax rules](https://www.revenue.ie/en/jobs-and-pensions/emergency-tax/emergency-tax-rules.aspx)
- [Citizens Information — Tax and starting work](https://www.citizensinformation.ie/en/employment/starting-work-and-changing-job/starting-work/tax-and-starting-work/)
- [Citizens Information — Proof of identity to open a bank account](https://www.citizensinformation.ie/en/money-and-tax/personal-finance/banking/financial-institutions-and-identification/)
- [Citizens Information — Medical card means test (under 70s)](https://www.citizensinformation.ie/en/health/medical-cards-and-gp-visit-cards/medical-card-means-test-under-70s/)
- [Citizens Information — Charges for hospital services](https://www.citizensinformation.ie/en/health/health-services/gp-and-hospital-services/hospital-charges/)
- [NDLS — Exchange my foreign driving licence](https://www.ndls.ie/licensed-driver/exchange-my-foreign-driving-licence.html)
- [RTB — Rental law changes from 1 March 2026](https://rtb.ie/renting/rental-law-changes-from-1-march-2/)
- [Daft.ie Rental Report Q1 2026](https://www.rte.ie/documents/news/2026/05/daft.ie-rental-report-2026q1.pdf)
- [Embassy of Ireland, Spain — Visas for Ireland](https://www.ireland.ie/en/spain/madrid/services/visas/visas-for-ireland/)
- [Leap Card — Fare capping](https://about.leapcard.ie/fare-capping)
