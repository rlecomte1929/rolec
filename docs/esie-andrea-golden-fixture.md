# ES→IE golden fixture — Andrea

**Card:** AIQ-1984.1 · **Branch:** `audit/stage-esie-serving-loop` · **Created:** 2026-08-22
**Status:** frozen spec. The pytest (`backend/tests/test_andrea_esie_fixture.py`) is `xfail`
until AIQ-1984.4 (step 6) flips it green.

This is the acceptance contract for Phase A. It is a *correctness* fixture, not a smoke test:
it asserts what Andrea must see, and — more importantly — what she must **never** be told.

---

## 1. Persona

| field | value |
|---|---|
| name | Andrea |
| corridor | **ES → IE** (Madrid → Dublin) |
| nationality | **Spanish — EU/EEA national** |
| nationality class | `OWN_NATIONAL` + `EU_EEA` (**not** `THIRD_COUNTRY`) |
| employee type | professional / **direct employee** (not posted, not intra-company, not student) |
| purpose | `employment` |
| destination `country_code` | `IRELAND` (catalog name, not the ISO code) |
| move date | `D` — parameterised; the dated-action assertions are relative to it |

> **The single most important fact about this fixture.** Andrea is an **EEA free mover**. She
> needs no employment permit and no ISD registration. The entire
> `es-ie-thirdcountry-requirements-2026-08-22` batch — 38 facts, every one of them
> `applies_to.nationality = "non-EEA"` → `["THIRD_COUNTRY"]` — is about a *different* person.
> If any of it reaches Andrea, the product has told a free mover she needs a visa. That is the
> failure this fixture exists to catch.

---

## 2. `expected_served_rules`

**Provenance — read this before trusting the list.** The Phase A pack specifies this set as
"the ES→IE `audience_scope` rule set **[needs Tier-1 list from Otto]**". At the time of
writing, `otto_to_claude` is **empty** — no `fixture_facts` relay has arrived (pulled
2026-08-22, `{"ok":true,"rows":[]}`). The set below is therefore **derived from prod**
(`nsvefcvpvwwwhuqyuqmp`, read-only) rather than relayed, and is marked **PROVISIONAL**. A
WORKLIST has been pushed to Otto. When the Tier-1 list arrives, reconcile against it; any
difference is a finding, not a merge conflict.

### 2a. What actually serves Andrea today (approved + nationality-agnostic)

`requirements_builder` serves **approved rows only**. For `country_code='IRELAND'`,
`purpose='employment'`, the nationality-class split in prod is:

| `applies_to_nationality_classes_json` | items | approved |
|---|---|---|
| `["THIRD_COUNTRY"]` | 42 | 23 |
| `null` (⇒ applies to everyone) | 6 | **6** |
| `["OWN_NATIONAL","EU_EEA"]` | 6 | **0** |

So Andrea's served set today is exactly the **6 nationality-agnostic approved rows**:

| # | id | title | pillar | non_obvious | timing (literal today) |
|---|---|---|---|---|---|
| 1 | `de5418cf-887d-52a4-b6c5-e8297f01efe7` | Irish tax residence turns on 183 days in a year, or 280 across two | EMPLOYMENT | true | `assessed per tax year` |
| 2 | `8e4041a0-63a6-5945-b99e-83c2c4719a18` | Register the job with Revenue through myAccount to avoid emergency tax | EMPLOYMENT | true | `immediately on starting the job` |
| 3 | `d47357e6-c886-53d9-942b-608f8158047a` | Split-year treatment can be requested for the year of arrival | EMPLOYMENT | true | `requested for the tax year of arrival` |
| 4 | `91bd4c65-e307-572d-9ea3-08c1a4e995fc` | The employer's RPN drives Income Tax, USC and PRSI deductions | EMPLOYMENT | true | `from the first payroll run after registration` |
| 5 | `618091c7-c704-59ac-bfe2-0e6c48cf610c` | Contributions paid abroad can be combined with Irish contributions | SOCIAL_SECURITY | true | `when claiming a social insurance payment` |
| 6 | `6a3bc272-03e3-5fa4-9100-19b674ec0c50` | PRSI is compulsory for most employees between 16 and pensionable age | SOCIAL_SECURITY | true | `from the start of employment` |

**All six are `non_obvious=true`** and **all six are `verification_status='representative'`**
(none `expert_verified`). Every one carries a *literal* timing string and **no date** — which
is precisely what AIQ-1972 (step 5) must turn into a real date from `D`.

### 2b. ⚠️ The EEA-specific set is 0-approved — a coverage gap, not a fixture bug

Six IRELAND rows are scoped `["OWN_NATIONAL","EU_EEA"]` — Andrea's own audience — and **every
one is `review_status='pending'`**, so none of them serves:

| id | title | non_obvious | timing |
|---|---|---|---|
| `78c86802-f32f-5208-944d-4b642677280a` | A1 Certificate — Posted Workers from Spain (EU/EEA nationals) | true | apply at least 4 weeks before work begins in Ireland |
| `3db4efb6-a5d7-52b3-be20-7d42f7a31410` | PPS Number — Application and Uses (EU/EEA nationals) | true | proof of address must be dated within the last 3 months |
| `c5bcb3ab-6634-57e0-9a88-7695e6f84522` | Public Health Entitlement — Ordinary Residence (EU/EEA nationals) | true | requires one year's residence, or documented intent… |
| `cdf091ad-1b5b-56d1-ba4d-777b0a22d6ca` | PRSI — Compulsory Social Insurance (EU/EEA nationals) | true | from 1 October 2025 |
| `ab45d82c-524f-52ce-b831-8d16a702f671` | Universal Social Charge — Threshold (EU/EEA nationals) | true | — |
| `e7284e86-f6a1-5c72-b6ae-3af6cdda7402` | Irish Income Tax — Rates and Bands (EU/EEA nationals) | false | — |

**Consequence:** Andrea today gets tax and social-security guidance and **nothing about PPSN,
health entitlement, or the A1 certificate** — the practical first-week items. This is a
**human approval gate**, not code: approving these is the lawyer/Romain call at
`/admin/countries`, and this fixture must not auto-approve them.

The fixture therefore asserts the 6 rows in §2a as the **served floor**, and records the 6 in
§2b as `expected_after_approval` — asserted only once a human approves them. A test that
demanded them today would be red for a reason no code change can fix.

---

## 3. `must_not_assert` — the hard failures

The fixture fails if Andrea's served roadmap contains **any** of these. Each is checked
positively (string/semantic match on served copy), not merely by row-id absence.

| # | must_not_assert | why it would be wrong | detection |
|---|---|---|---|
| 1 | **"needs an employment permit / work visa"** | Andrea is an EEA free mover. CSEP/GEP/ICT and entry-visa content is `THIRD_COUNTRY`-scoped. | no served item whose title/description asserts a permit or entry-visa requirement; explicitly none of the 42 `["THIRD_COUNTRY"]` rows |
| 2 | **"unconditionally exempt from Irish Emergency Tax"** | Emergency Tax relief is **conditional** — on a PPS number *and* the employer holding a correct RPN. Rendering it as a flat exemption is the AIQ-1969 failure. | no served copy asserting exemption without its condition; the `assertion_mode='conditional'` fact must render **with** `conditional_on` |
| 3 | **any `nationality_determined` non-EEA rule reaching an EEA mover** | The general form of #1 — the class-level invariant. | for every served item, `appliesToNationalityClasses` is `null` **or** intersects `{OWN_NATIONAL, EU_EEA}`; **never** `["THIRD_COUNTRY"]` alone |

**Tripwire ids for #1/#3** — the highest-risk near-neighbours, all `THIRD_COUNTRY`, all
approved, all ES→IE-flavoured, and three of them promoted into this very corridor's work:

- `6bff7336-efb0-582b-b0db-38fb1ae1b1a0` — *Work Permission Requirement for Non-EEA Workers*
- `57073a0e-85fb-5926-9213-e6564812ae7e` — *Critical Skills Employment Permit — eligibility*
- `c07c4900-7792-561c-b07e-b2464c2f913b` — *Immigration permission – Stamp 1 / IRP registration*
- `04c9ba47-8c41-5b28-9012-4a10393cfb45` — *Ireland — spanish residence does not grant irish entry*
- `466feb22-4242-508a-a9b8-d610bc60d7fd` — *Critical Skills Permit – nine-month employer mobility restriction* (promoted 2026-08-22, pending)
- `57f1720c-fa9b-5de0-a048-e2dad9816d31` — *Critical Skills Permit – employer 50:50 workforce rule* (promoted 2026-08-22, pending)
- `94837181-c418-5a94-8702-a3657684b7cd` — *Ireland — employment permit 12-week application lead time* (promoted 2026-08-22, pending)

---

## 4. The other Phase A assertions (xfail until their card lands)

| card | assertion | green at |
|---|---|---|
| **AIQ-1969** | a `conditional` fact renders **with** its `conditional_on`; never "you are exempt". `non_obvious=true` → an easy-to-miss treatment. All 6 served rows are `non_obvious`. | step 2 |
| **AIQ-1938** | Andrea's tuple `(ES→IE, EU_EEA, professional)` is **in-distribution** → full roadmap. An unsupported tuple → visible *"outside my verified zone"*, never a fabricated timeline nor a silent empty. | step 3 |
| **AIQ-1971** | Andrea resolves to the **professional / direct-employee** branch; a different employee type gets a different, correct branch; the tree is enumerable. | step 4 |
| **AIQ-1972** | every served `timing` becomes a **date** from `D`. Today all 6 are literal strings and **0 are dated** — so the target is `0` literal-only deadlines. | step 5 |

---

## 5. Definition of done (AIQ-1984.4)

`backend/tests/test_andrea_esie_fixture.py` green with `xfail` removed, and:

1. Andrea sees the §2a `audience_scope` rules (6 today; +6 once approved).
2. Conditionals render **conditionally**, with their condition.
3. `non_obvious` rows are flagged easy-to-miss.
4. Deadlines are **dated** from `D`.
5. **None** of §3 appears.
6. `scripts/check_serving_llm_isolation.py` and `scripts/check_route_auth*` stay green.

---

## 6. Notes for whoever picks this up

- **Test location.** The Phase A pack specifies `tests/e2e/test_andrea_esie_fixture.py`. That
  directory is the **Playwright/TypeScript** harness, and CI's pytest lane runs
  `python -m pytest … backend/tests scripts/tests` — it does **not** discover `tests/e2e/`.
  A pytest placed there would never execute: a green gate that checks nothing. The test is at
  **`backend/tests/test_andrea_esie_fixture.py`** so it actually gates. Move it only together
  with a CI discovery change.
- **`null` nationality classes mean "everyone".** All 6 served rows have `null`, which is why
  they reach Andrea at all. `mappings.py` warns that NULL is dangerous *for visa-track
  content*; for tax/PRSI it is correct. Do not "fix" these to `["OWN_NATIONAL","EU_EEA"]`
  without a human — that would narrow rows that legitimately apply to everyone.
- **Nothing in this card writes.** No serving change, no DB write, no promotion. Steps 2–7 do
  that, each behind its own gate.
