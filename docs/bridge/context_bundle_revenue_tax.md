# CONTEXT BUNDLE — promote `revenue_rpn_emergency_tax` + `taxation` (ES→IE third-country)

**Bundle id:** `context_bundle:ES-IE:thirdcountry:revenue_tax`
**Generated:** 2026-08-22 · read-only export (SELECTs + file reads; no writes, no promotion)
**Batch:** `es-ie-thirdcountry-requirements-2026-08-22` · **Project:** `nsvefcvpvwwwhuqyuqmp`
**Bridge role:** Generator input (Cursor). Generation is read-only; a wired applier dry-runs,
diffs against your prediction, and only then applies. You have no handle to prod — do not
assume one.

> **Snapshot semantics.** Everything below is frozen at export time. The applier reconciles
> against live at apply time. Generate against this snapshot; do not invent state not in it.

> **Third unit through this loop.** `immigration_work_authorization` applied clean (3 inserts,
> 0 updates, fingerprint unchanged); `isd_irp_registration` applied clean (7 inserts). Same
> structure, same contract. IRELAND now holds **52** `requirement_items` rows.

---

## ⚠️ READ THIS BEFORE GENERATING — two boxes, both load-bearing

### A. The grain mismatch

The repo's normal promotion path (`backend/imports/otto/executor.py::promote()` →
`mappings.resolve()`) emits **one `requirement_items` row per staged *topic*, not per fact.**
It would collapse these two topics into two rows titled *"Ireland - Revenue, the RPN and
emergency tax (third-country professional)"* and *"Ireland - taxation (third-country
professional)"*.

**This task is different: 7 specific facts must become 7 rows.** Generate **per-fact rows with
per-fact titles** — you cannot reuse `mappings.py`'s `title = entity.title` rule. Use §2 for
how the *other* columns are derived, and choose a title per fact (§6 constrains this). **The
title you choose is the dedup key** — §1.

### B. Two topics, one bundle — and why

The previous two units were one topic each. This one carries **both** tax topics together,
because they share a collision surface: `emergency_usc_flat_8_percent` (revenue) and the
`taxation` facts both live beside *Universal Social Charge — Threshold*, *Irish Income Tax —
Rates and Bands* and *Irish tax residence turns on 183 days…*. Generated as two independent
bundles, two title sets could collide **with each other** and neither generation would see it.

Treat them as **one title namespace**: your 7 titles must be distinct from each other *and*
from every live IRELAND row in §4.

---

## ⚠️ CORRECTION TO THE BRIEF — the pillar fix is NOT on `main`

`ES-IE_Promotion_Decision_Brief_2026-08-22.md` gates these two topics on **D2 — merge PR
#1973** (`fix(otto): honor applies_to.pillar over the domain_area default on promotion`).

**#1973 shows `MERGED`, but it was merged into `feat/enrich-curated-batches-non-obvious`, not
into `main` — and that parent branch had already merged to `main` (PR #1969) at 09:27Z, three
and a half hours before #1973 landed on it at 13:02Z.** Verified: merge commit
`23716c2c9f6e929ba13f3090e782d01f6dfb9f24` is **not** an ancestor of `origin/main`, and
`resolve_pillar` / `CANONICAL_PILLARS` / `PILLAR_ALIASES` **do not exist** in
`backend/imports/otto/mappings.py` on `origin/main`. The fix is stranded on a dead branch and
needs re-landing.

**What this changes for you: nothing, and that is the point.** This bundle produces
hand-written `INSERT`s at per-fact grain — it does not call `promote()`. The pillar is set
directly in the SQL, to the value §2 adjudicates. `resolve_pillar` is reproduced in §2 as the
*intended* rule and as the arithmetic that justifies `EMPLOYMENT`; it is **not** running code
on `main` today. Do not assume any code will correct a pillar you get wrong.

---

## 1. TARGET SCHEMA — `public.requirement_items`

Live column list (from `information_schema`, verified at export time):

| column | type | nullable | default |
|---|---|---|---|
| `id` | character varying | NO | — |
| `country_code` | character varying | YES | — |
| `purpose` | character varying | NO | — |
| `pillar` | character varying | NO | — |
| `title` | character varying | NO | — |
| `description` | text | NO | — |
| `severity` | character varying | NO | — |
| `owner` | character varying | NO | — |
| `required_fields_json` | text | NO | — |
| `citations_json` | text | NO | — |
| `last_verified_at` | timestamp without time zone | NO | — |
| `applies_to_assignment_types_json` | text | YES | — |
| `verification_status` | text | YES | — |
| `applies_to_nationality_classes_json` | text | YES | — |
| `review_status` | text | NO | **`'approved'`** |
| `reviewed_by` | text | YES | — |
| `reviewed_at` | timestamp with time zone | YES | — |
| `non_obvious` | boolean | NO | `false` |
| `timing` | text | YES | — |
| `attestation_status` | text | YES | — |
| `attested_at` | timestamp with time zone | YES | — |
| `attested_by` | text | YES | — |
| `latest_attestation_request_id` | uuid | YES | — |

### The natural upsert key

**`(country_code, purpose, title)`.**

`backend/app/crud.py::create_requirement_item` **upserts on that key**, and on collision it
**rewrites `description`, `severity`, `owner` and `citations_json`** of whatever row it finds.
There is no merge and no conflict check — the incoming payload wins. That is why §5 forbids
producing any row whose `(country_code, purpose, title)` matches a row in §4.

`id` is `character varying`, **not** uuid-typed. Both writers derive it as
`uuid5(_SEED_NS, f"{country_code}|{purpose}|{title}")` with
`_SEED_NS = UUID("a1c9e349-0000-4000-8000-000000000001")`
(`backend/scripts/seed_requirements.py`; re-used at `executor.py:477`), so the promoter and
the YAML seeder converge on one row per natural key rather than racing. **Confirmed working**
on the previous two units. Derive ids the same way; do not emit random uuids.

### ⚠️ Two schema traps

1. **`review_status` DEFAULTS to `'approved'`.** Omitting the column publishes unreviewed
   facts to real users the moment the write lands. **Always set `'pending'` explicitly.**
2. **`pillar` has NO CHECK constraint.** An unrecognised value is written happily and invents
   a pillar nothing renders. Only the seven in §2 are legal. **This is the trap this unit is
   most exposed to** — see the pillar section.

Constraints present on the table: only `requirement_items_review_status_check`
(`review_status IN ('pending','approved','rejected')`).

---

## 2. MAPPING RULES — `backend/imports/otto/mappings.py`

```python
# applies_to.nationality -> applies_to_nationality_classes_json
NATIONALITY_CLASSES = {
    "EU":  [OWN_NATIONAL, EU_EEA],
    "EEA": [OWN_NATIONAL, EU_EEA],
    "non-EEA": [THIRD_COUNTRY],
    "non-EU": [THIRD_COUNTRY],
}
# NOT present: "any". NULL in that column means "applies to everyone" — categorise or refuse.

# applies_to.status -> purpose (target enum is exactly employment|study|family|other)
PURPOSES = {"professional": "employment", "student": "study",
            "family": "family", "any": "other"}

DEFAULT_SEVERITY = "WARN"     # neutral; raising to BLOCKER is a human act
DEFAULT_OWNER    = "EMPLOYEE" # documents the relocating person obtains
IMMIGRATION_PILLAR = "RESIDENCE"   # the DEFAULT read off domain_area, not the verdict
```

### Pillar resolution — the intended rule (PR #1973, **NOT on `main`** — see the correction box)

```python
CANONICAL_PILLARS = ("RESIDENCE", "IDENTITY", "EMPLOYMENT", "HOUSING",
                     "SOCIAL_SECURITY", "TIMELINE", "HEALTHCARE")

PILLAR_ALIASES = {"TAX": "EMPLOYMENT", "PAYROLL": "EMPLOYMENT"}

def resolve_pillar(facts, *, default=IMMIGRATION_PILLAR):
    stated = []
    for fact in facts:
        raw = (fact.applies_to or {}).get("pillar")
        if raw is None or not str(raw).strip():
            continue
        value = str(raw).strip().upper()
        value = PILLAR_ALIASES.get(value, value)
        if value not in CANONICAL_PILLARS:
            return None, "...is not a catalog pillar ... would invent a pillar nothing renders"
        if value not in stated:
            stated.append(value)

    distinctive = [p for p in stated if p != default]
    if not distinctive:
        return default, None          # no fact states one -> domain_area default
    if len(distinctive) > 1:
        return None, "facts disagree on applies_to.pillar ... one topic promotes to one row"
    return distinctive[0], None
```

Rules in words: honor `applies_to.pillar` when stated; fall back to the
`domain_area='immigration'` default only when no fact states one; `TAX`→`EMPLOYMENT`; unknown
pillar refuses; a fact carrying the default (`RESIDENCE`) says nothing; two different
non-default pillars refuse.

**Applied to this unit — both topics resolve to `EMPLOYMENT`:**

| topic | stated `applies_to.pillar` | after aliasing | distinctive (≠ RESIDENCE) | resolved |
|---|---|---|---|---|
| `revenue_rpn_emergency_tax` (7 facts) | `RESIDENCE` ×5, `EMPLOYMENT` ×2 | same | `[EMPLOYMENT]` | **`EMPLOYMENT`** |
| `taxation` (3 facts) | `RESIDENCE` ×1, `TAX` ×2 | `RESIDENCE` ×1, `EMPLOYMENT` ×2 | `[EMPLOYMENT]` | **`EMPLOYMENT`** |

> **Every row you generate is `pillar='EMPLOYMENT'`.** This matches the live convention —
> `Irish tax residence turns on 183 days…`, `Register the job with Revenue through myAccount…`,
> `The employer's RPN drives Income Tax, USC and PRSI deductions` and *Split-year treatment…*
> are **all** `EMPLOYMENT` (§4). It is also the reconciliation report's explicit adjudication
> for both topics ("**Pillar → EMPLOYMENT**").

**Two honest caveats, neither of which changes the answer:**

1. **`TAX` is not a catalog pillar.** Without the alias, `resolve_pillar` refuses; without
   `resolve_pillar` at all (today's `main`), `promote()` writes `RESIDENCE`. Writing the literal
   `TAX` would invent an unrenderable eighth pillar — §5 forbids it absolutely.
2. **In `revenue_rpn_emergency_tax`, the pillar is decided by facts that are not being
   promoted.** The 2 `EMPLOYMENT`-carrying facts are `emergency_tax_week_5_full_40_percent`
   (`__promote: true`) and `first_job_in_state_must_be_registered_by_employee` (a **DUP**, not
   promoted). `resolve_pillar` reads the whole topic, so this is the code's real behaviour, not
   a shortcut — but do not be surprised that 4 of the 5 promoted revenue rows carry a
   `RESIDENCE` `applies_to.pillar` and are nonetheless written `EMPLOYMENT`.

Existing live rows that are misfiled at `RESIDENCE` for the same concept (*Irish Income Tax —
Rates and Bands*, *Universal Social Charge — Threshold*, both audiences) are **pre-existing
debt (D3/D7)** and **out of scope**. This bundle is append-only; do not touch them.

### Other derivations

- `title` — normally `entity.title` verbatim. **Not usable here; see box A.**
- `purpose` — `PURPOSES[applies_to.status]`; all 10 facts are `professional` ⇒ **`employment`**.
- `country_code` — `iso_to_catalog_name('IE')` ⇒ **`IRELAND`** (full uppercase country names,
  **not** ISO codes).
- `applies_to_nationality_classes_json` — all facts `non-EEA` ⇒ **`["THIRD_COUNTRY"]`**.
- `description` — that fact's `fact_text` **verbatim**, newlines included. Several of these
  carry an inline `"Commonly believed: … Actually: … Action required: …"` block — that prose is
  the batch's whole value. **Keep it; do not summarise, reflow or trim it.**
  (`compose_description` would join many facts; at one-fact-per-row it reduces to the fact's own
  text. No fact here carries `applies_to.non_obvious_note`, so no `"Why this is easy to miss: "`
  marker is appended — the equivalent prose is already inside `fact_text`.)
- `citations_json` — **one citation object per distinct `source_url`**, not bare URL strings.
  Shape from `mappings._citations_for`: `{"url", "topic_key", "name", "corridor"}`, where
  `topic_key` is the **entity's** `topic_key` and `name`/`corridor` come from the fact's
  `applies_to.source_name` / `applies_to.corridor`. `"needs_lawyer_review"` is added **only
  when** the fact carries it — **no fact in this unit does** (all `false`). A bare URL resolves
  against nothing and serves an empty citation list while the provenance guard still passes.
- `severity` = `WARN`, `owner` = `EMPLOYEE`, `required_fields_json` = `"[]"`.
- `verification_status` = **`representative`** on all 7. Derivation:
  `corpus_grounded` requires `accuracy_tier == 'auto_accepted'` **and** a non-empty
  `evidence_quote`. **All 10 facts carry `accuracy_tier='needs_review'`**, so every row is
  `representative` regardless of quotes (which are in fact all present).
  **Nothing may write `expert_verified`.**
- `non_obvious` — from that fact's `applies_to.non_obvious`. **Per-fact, not per-topic** — at
  one-fact-per-row the `any(...)` in `mappings.resolve` reduces to the fact's own flag. Values
  are in §3; 3 of the 7 are `true`.
- `timing` — from `applies_to.timing` when present. **No fact in either topic carries one**, so
  leave `timing` NULL on all 7 rows. (Note the live `EMPLOYMENT` tax rows *do* carry timings —
  *"immediately on starting the job"*, *"from the first payroll run after registration"*. Do not
  copy or invent one; NULL is the honest value here.)
- `last_verified_at` — NOT NULL; use `now() AT TIME ZONE 'utc'`, matching `promote()`.

**Note on sources:** the 7 promoted facts span **three** Revenue URLs (emergency-tax rules,
emergency-tax overview, tax residence). Citations must reflect each fact's own `source_url` and
its own `source_name` — do not collapse them to one citation.

---

## 3. SOURCE SNAPSHOT (JSON)

Both staged entities and **all 10** fact candidates. Each is tagged `"__promote": true|false` —
**exactly 7 are `true`.**

Classification per
`docs/imports/es-ie-thirdcountry-requirements-2026-08-22/RECONCILIATION_REPORT.md`:
**revenue = 5 NEW · 2 DUP · taxation = 2 NEW · 1 PARTIAL.**

```json
{
  "entities": [
    {
      "destination_country": "IE",
      "topic_key": "ES-IE:thirdcountry:revenue_rpn_emergency_tax",
      "domain_area": "immigration",
      "title": "Ireland - Revenue, the RPN and emergency tax (third-country professional)",
      "batch_id": "es-ie-thirdcountry-requirements-2026-08-22",
      "source": "otto_research",
      "resolved_pillar": "EMPLOYMENT"
    },
    {
      "destination_country": "IE",
      "topic_key": "ES-IE:thirdcountry:taxation",
      "domain_area": "immigration",
      "title": "Ireland - taxation (third-country professional)",
      "batch_id": "es-ie-thirdcountry-requirements-2026-08-22",
      "source": "otto_research",
      "resolved_pillar": "EMPLOYMENT"
    }
  ],
  "facts": [
    {
      "topic_key": "ES-IE:thirdcountry:revenue_rpn_emergency_tax",
      "fact_key": "emergency_tax_trigger_is_missing_rpn",
      "fact_type": "other",
      "fact_uid": "ES_IE:THIRD_COUNTRY:emergency_tax_trigger_is_missing_rpn",
      "fact_text": "Emergency Tax is an alternative basis of deduction applied when the employer cannot obtain a Revenue Payroll Notification for the employee. Avoiding it requires two things together: the employer holding the PPSN, and the job being registered with Revenue.",
      "evidence_quote": "Income Tax and Universal Social Charge (USC) are deducted from your gross pay at the Emergency Tax rates by your employer. This happens in certain circumstances where your employer is unable to get a Revenue Payroll Notification (RPN) for you.",
      "source_url": "https://www.revenue.ie/en/jobs-and-pensions/emergency-tax/index.aspx",
      "source_name": "Revenue - Emergency Tax (overview)",
      "applies_to": {"pillar": "RESIDENCE", "status": "professional", "nationality": "non-EEA", "non_obvious": false, "corridor": "ES->IE", "needs_lawyer_review": false},
      "confidence": "high",
      "accuracy_tier": "needs_review",
      "__promote": true,
      "__class": "NEW"
    },
    {
      "topic_key": "ES-IE:thirdcountry:revenue_rpn_emergency_tax",
      "fact_key": "emergency_tax_no_ppsn_all_pay_at_40_percent",
      "fact_type": "other",
      "fact_uid": "ES_IE:THIRD_COUNTRY:emergency_tax_no_ppsn_all_pay_at_40_percent",
      "fact_text": "Where the employee has not provided a PPSN to the employer, all pay is taxed at the higher rate of 40% from the first payroll run - with no rate band and no credits.",
      "evidence_quote": "Your employer will tax all your pay at the higher rate of tax (40%).",
      "source_url": "https://www.revenue.ie/en/jobs-and-pensions/emergency-tax/emergency-tax-rules.aspx",
      "source_name": "Revenue - Emergency Tax rules",
      "applies_to": {"pillar": "RESIDENCE", "status": "professional", "nationality": "non-EEA", "non_obvious": false, "corridor": "ES->IE", "needs_lawyer_review": false},
      "confidence": "high",
      "accuracy_tier": "needs_review",
      "__promote": true,
      "__class": "NEW"
    },
    {
      "topic_key": "ES-IE:thirdcountry:revenue_rpn_emergency_tax",
      "fact_key": "emergency_tax_first_four_weeks_single_rate_band",
      "fact_type": "other",
      "fact_uid": "ES_IE:THIRD_COUNTRY:emergency_tax_first_four_weeks_single_rate_band",
      "fact_text": "Where the PPSN HAS been given but the job is not registered, a single person's rate band is allowed for the first four weeks of employment: 20% up to the weekly rate band, 40% above it.",
      "evidence_quote": "Where you have provided your PPSN, you are allowed a single person’s rate band for the first four weeks of employment.",
      "source_url": "https://www.revenue.ie/en/jobs-and-pensions/emergency-tax/emergency-tax-rules.aspx",
      "source_name": "Revenue - Emergency Tax rules",
      "applies_to": {"pillar": "RESIDENCE", "status": "professional", "nationality": "non-EEA", "non_obvious": false, "corridor": "ES->IE", "needs_lawyer_review": false},
      "confidence": "high",
      "accuracy_tier": "needs_review",
      "__promote": true,
      "__class": "NEW"
    },
    {
      "topic_key": "ES-IE:thirdcountry:revenue_rpn_emergency_tax",
      "fact_key": "emergency_tax_week_5_full_40_percent",
      "fact_type": "deadline",
      "fact_uid": "ES_IE:THIRD_COUNTRY:emergency_tax_week_5_full_40_percent",
      "fact_text": "The four-week concession expires. From week 5 onwards the employee's FULL income is taxed at the higher rate of 40%, even though the PPSN was provided, for as long as the job remains unregistered and no RPN exists.\n\nCommonly believed: Emergency tax is a small first-payslip annoyance that sorts itself out.\n\nActually: It escalates on a statutory clock. Weeks 1-4 keep a single person's rate band; from week 5 the whole of gross pay is taxed at 40% plus emergency USC. For a professional salary that is a very large cash-flow hit landing in the same weeks as Dublin rental deposits.\n\nAction required: Register the job in Revenue myAccount within the first four weeks - the week-5 cliff, not the first payslip, is the real deadline.",
      "evidence_quote": "From Week 5 onwards, your full income will be taxed at the higher rate (40%).",
      "source_url": "https://www.revenue.ie/en/jobs-and-pensions/emergency-tax/emergency-tax-rules.aspx",
      "source_name": "Revenue - Emergency Tax rules",
      "applies_to": {"pillar": "EMPLOYMENT", "status": "professional", "nationality": "non-EEA", "non_obvious": true, "corridor": "ES->IE", "needs_lawyer_review": false},
      "confidence": "high",
      "accuracy_tier": "needs_review",
      "__promote": true,
      "__class": "NEW",
      "__note": "fact_type='deadline', but applies_to carries NO timing. Leave the timing column NULL; the deadline lives in the prose."
    },
    {
      "topic_key": "ES-IE:thirdcountry:revenue_rpn_emergency_tax",
      "fact_key": "emergency_usc_flat_8_percent",
      "fact_type": "other",
      "fact_uid": "ES_IE:THIRD_COUNTRY:emergency_usc_flat_8_percent",
      "fact_text": "On the emergency basis, USC is charged at a flat rate - 8% in 2026 - on all income, on top of the Income Tax deducted at the emergency rates. The headline 40% understates the total deduction.",
      "evidence_quote": "The emergency rate of USC is a flat percentage rate (8% in 2026) applied to all income.",
      "source_url": "https://www.revenue.ie/en/jobs-and-pensions/emergency-tax/emergency-tax-rules.aspx",
      "source_name": "Revenue - Emergency Tax rules",
      "applies_to": {"pillar": "RESIDENCE", "status": "professional", "nationality": "non-EEA", "non_obvious": false, "corridor": "ES->IE", "needs_lawyer_review": false},
      "confidence": "high",
      "accuracy_tier": "needs_review",
      "__promote": true,
      "__class": "NEW",
      "__note": "Carries a year-stamped rate (8% in 2026). Keep the year in the text — it is what makes the claim re-checkable."
    },
    {
      "topic_key": "ES-IE:thirdcountry:revenue_rpn_emergency_tax",
      "fact_key": "first_job_in_state_must_be_registered_by_employee",
      "fact_type": "other",
      "fact_uid": "ES_IE:THIRD_COUNTRY:first_job_in_state_must_be_registered_by_employee",
      "fact_text": "For any later job the employer registers the employment. For a first job in the State the employee must register it themselves in Revenue myAccount under PAYE Services.\n\nCommonly believed: Payroll onboarding handles your tax registration, as it does for colleagues.\n\nActually: Revenue splits the duty by whether it is the person's first employment in Ireland. On a first Irish job the employer CANNOT register it - only the employee can, through myAccount. Both sides assuming the other will do it is the ordinary way movers reach the week-5 40% cliff.\n\nAction required: Register for Revenue myAccount and add the job yourself under PAYE Services; do not wait for payroll.",
      "evidence_quote": "Your employer needs to register your employment if it is not your first job. If it is your first job in the State, you can register your job on myAccount, by clicking ‘Add Job or Pension Details’ under ‘PAYE Services’.",
      "source_url": "https://www.revenue.ie/en/jobs-and-pensions/emergency-tax/index.aspx",
      "source_name": "Revenue - Emergency Tax (overview)",
      "applies_to": {"pillar": "EMPLOYMENT", "status": "professional", "nationality": "non-EEA", "non_obvious": true, "corridor": "ES->IE", "needs_lawyer_review": false},
      "confidence": "high",
      "accuracy_tier": "needs_review",
      "__promote": false,
      "__class": "DUP",
      "__dup_of": "8e4041a0-63a6-5945-b99e-83c2c4719a18 — 'Register the job with Revenue through myAccount to avoid emergency tax' (approved, EMPLOYMENT)"
    },
    {
      "topic_key": "ES-IE:thirdcountry:revenue_rpn_emergency_tax",
      "fact_key": "rpn_follows_first_job_registration",
      "fact_type": "other",
      "fact_uid": "ES_IE:THIRD_COUNTRY:rpn_follows_first_job_registration",
      "fact_text": "Once the first job is registered, Revenue makes a Revenue Payroll Notification available to the new employer, which the employer uses to calculate Income Tax and USC. The RPN is the output of the employee's registration - the employer cannot conjure it.",
      "evidence_quote": "When you have registered your first job, Revenue will make a Revenue Payroll Notification (RPN) available to your new employer. Your employer will use the RPN to calculate how much Income Tax and Universal Social Charge (USC) to deduct from your pay.",
      "source_url": "https://www.revenue.ie/en/jobs-and-pensions/starting-your-first-job/index.aspx",
      "source_name": "Revenue - Starting your first job",
      "applies_to": {"pillar": "RESIDENCE", "status": "professional", "nationality": "non-EEA", "non_obvious": false, "corridor": "ES->IE", "needs_lawyer_review": false},
      "confidence": "high",
      "accuracy_tier": "needs_review",
      "__promote": false,
      "__class": "DUP",
      "__dup_of": "91bd4c65-e307-572d-9ea3-08c1a4e995fc — 'The employer's RPN drives Income Tax, USC and PRSI deductions' (approved, EMPLOYMENT)"
    },
    {
      "topic_key": "ES-IE:thirdcountry:taxation",
      "fact_key": "irish_tax_status_has_three_independent_tests",
      "fact_type": "eligibility",
      "fact_uid": "ES_IE:THIRD_COUNTRY:irish_tax_status_has_three_independent_tests",
      "fact_text": "Irish tax status is not a single question. A person can be resident, ordinarily resident, domiciled, or any combination of the three, and the combination decides what income is chargeable. A third-country professional arriving mid-year will typically hold a different combination in the arrival year than in later years.",
      "evidence_quote": "You can be resident, ordinarily resident, domiciled or any combination of the three.",
      "source_url": "https://www.revenue.ie/en/jobs-and-pensions/tax-residence/index.aspx",
      "source_name": "Revenue - Tax residence",
      "applies_to": {"pillar": "RESIDENCE", "status": "professional", "nationality": "non-EEA", "non_obvious": false, "corridor": "ES->IE", "needs_lawyer_review": false},
      "confidence": "high",
      "accuracy_tier": "needs_review",
      "__promote": false,
      "__class": "PARTIAL",
      "__partial_of": "de5418cf-887d-52a4-b6c5-e8297f01efe7 — 'Irish tax residence turns on 183 days in a year, or 280 across two' (approved, EMPLOYMENT). This fact frames the 183-day test as only one of three axes; the live row states that test alone. Held back: reframing an approved row is a reviewer's call, not an append."
    },
    {
      "topic_key": "ES-IE:thirdcountry:taxation",
      "fact_key": "resident_and_domiciled_means_worldwide_income",
      "fact_type": "other",
      "fact_uid": "ES_IE:THIRD_COUNTRY:resident_and_domiciled_means_worldwide_income",
      "fact_text": "Once resident AND domiciled in Ireland for tax purposes, the person is chargeable to Irish tax on worldwide income - the total earned anywhere in the world in the tax year - subject to relief under an applicable Double Taxation Agreement.\n\nCommonly believed: You pay Irish tax on your Irish salary.\n\nActually: The charge follows residence and domicile, not the source of the money. Spanish rental income, investments or trailing Spanish employment income can fall into the Irish charge, with the Ireland-Spain Double Taxation Agreement as relief rather than exemption.\n\nAction required: List every non-Irish income source before the first Irish return and take advice on the DTA position.",
      "evidence_quote": "If you are resident and domiciled in Ireland for tax purposes, you are chargeable to tax in Ireland on your worldwide income. Worldwide income is the total income that you earn anywhere in the world in a tax year. This is subject to any relief due under the terms of a relevant Double Taxation Agreement.",
      "source_url": "https://www.revenue.ie/en/jobs-and-pensions/tax-residence/index.aspx",
      "source_name": "Revenue - Tax residence",
      "applies_to": {"pillar": "TAX", "status": "professional", "nationality": "non-EEA", "non_obvious": true, "corridor": "ES->IE", "needs_lawyer_review": false},
      "confidence": "medium",
      "accuracy_tier": "needs_review",
      "__promote": true,
      "__class": "NEW",
      "__note": "applies_to.pillar is the literal 'TAX'. Alias to EMPLOYMENT; NEVER write 'TAX'. confidence='medium' — there is no confidence column; do not invent one."
    },
    {
      "topic_key": "ES-IE:thirdcountry:taxation",
      "fact_key": "non_resident_but_ordinarily_resident_and_domiciled",
      "fact_type": "other",
      "fact_uid": "ES_IE:THIRD_COUNTRY:non_resident_but_ordinarily_resident_and_domiciled",
      "fact_text": "A person can be non-resident for Irish tax purposes while still being ordinarily resident and domiciled, and that combination changes what income remains chargeable to Irish tax. The Irish tax relationship therefore outlasts the physical move in both directions.\n\nCommonly believed: Tax follows where you live: leave Ireland and the Irish charge stops.\n\nActually: Ordinary residence and domicile persist after residence ends, so Irish tax exposure can continue for years after departure - which matters for a professional treating Dublin as one posting in a longer international career.\n\nAction required: Model the exit position at the same time as the arrival position, not when leaving.",
      "evidence_quote": "You might be non-resident in Ireland for tax purposes, but ordinarily resident and domiciled. This will affect what income is chargeable to Irish tax.",
      "source_url": "https://www.revenue.ie/en/jobs-and-pensions/tax-residence/index.aspx",
      "source_name": "Revenue - Tax residence",
      "applies_to": {"pillar": "TAX", "status": "professional", "nationality": "non-EEA", "non_obvious": true, "corridor": "ES->IE", "needs_lawyer_review": false},
      "confidence": "medium",
      "accuracy_tier": "needs_review",
      "__promote": true,
      "__class": "NEW",
      "__note": "applies_to.pillar is the literal 'TAX'. Alias to EMPLOYMENT; NEVER write 'TAX'."
    }
  ]
}
```

**Counts to reconcile against: 10 facts total · 7 `__promote: true` · 2 DUP · 1 PARTIAL.**

---

## 4. LIVE STATE (JSON) — existing `requirement_items` for the tax / payroll concept

`country_code='IRELAND'`, all `purpose='employment'`. **Tripwires are the `approved` rows.**

```json
[
 {"id":"8e4041a0-63a6-5945-b99e-83c2c4719a18","title":"Register the job with Revenue through myAccount to avoid emergency tax","pillar":"EMPLOYMENT","review_status":"approved","verification_status":"representative","non_obvious":true,"timing":"immediately on starting the job","__flag":"TRIPWIRE — approved; the DUP target for first_job_in_state_must_be_registered_by_employee"},
 {"id":"91bd4c65-e307-572d-9ea3-08c1a4e995fc","title":"The employer's RPN drives Income Tax, USC and PRSI deductions","pillar":"EMPLOYMENT","review_status":"approved","verification_status":"representative","non_obvious":true,"timing":"from the first payroll run after registration","__flag":"TRIPWIRE — approved; the DUP target for rpn_follows_first_job_registration"},
 {"id":"de5418cf-887d-52a4-b6c5-e8297f01efe7","title":"Irish tax residence turns on 183 days in a year, or 280 across two","pillar":"EMPLOYMENT","review_status":"approved","verification_status":"representative","non_obvious":true,"timing":"assessed per tax year","__flag":"TRIPWIRE — approved; the PARTIAL target for irish_tax_status_has_three_independent_tests"},
 {"id":"0c52c2c8-e92c-51c1-9ebb-728da7e603f4","title":"PPSN (Personal Public Service Number) — application and emergency tax","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":false,"timing":null,"__flag":"TRIPWIRE — approved; states the PPSN/emergency-tax link"},
 {"id":"6a3bc272-03e3-5fa4-9100-19b674ec0c50","title":"PRSI is compulsory for most employees between 16 and pensionable age","pillar":"SOCIAL_SECURITY","review_status":"approved","verification_status":"representative","non_obvious":true,"timing":"from the start of employment","__flag":"TRIPWIRE — approved"},
 {"id":"d47357e6-c886-53d9-942b-608f8158047a","title":"Split-year treatment can be requested for the year of arrival","pillar":"EMPLOYMENT","review_status":"approved","verification_status":"representative","non_obvious":true,"timing":"requested for the tax year of arrival","__flag":"TRIPWIRE — approved; the third live EMPLOYMENT tax row. Adjacent to both taxation facts."},
 {"id":"e7284e86-f6a1-5c72-b6ae-3af6cdda7402","title":"Irish Income Tax — Rates and Bands (EU/EEA nationals)","pillar":"RESIDENCE","review_status":"pending","verification_status":"representative","non_obvious":false,"timing":null,"__flag":"pending; pillar misfiled at RESIDENCE — pre-existing D3 debt, OUT OF SCOPE"},
 {"id":"fa84a4e4-7597-5c07-988a-47f2608951f6","title":"Irish Income Tax — Rates and Bands (non-EEA nationals)","pillar":"RESIDENCE","review_status":"pending","verification_status":"representative","non_obvious":false,"timing":null,"__flag":"pending; same audience as this batch; pillar misfiled — OUT OF SCOPE"},
 {"id":"ab45d82c-524f-52ce-b831-8d16a702f671","title":"Universal Social Charge — Threshold (EU/EEA nationals)","pillar":"RESIDENCE","review_status":"pending","verification_status":"representative","non_obvious":true,"timing":null,"__flag":"pending; nearest neighbour to emergency_usc_flat_8_percent — OUT OF SCOPE"},
 {"id":"d915d664-1bdf-5a8a-8a4b-6b39006bb821","title":"Universal Social Charge — Threshold (non-EEA nationals)","pillar":"RESIDENCE","review_status":"pending","verification_status":"representative","non_obvious":true,"timing":null,"__flag":"pending; nearest neighbour to emergency_usc_flat_8_percent — OUT OF SCOPE"},
 {"id":"cdf091ad-1b5b-56d1-ba4d-777b0a22d6ca","title":"PRSI — Compulsory Social Insurance (EU/EEA nationals)","pillar":"RESIDENCE","review_status":"pending","verification_status":"representative","non_obvious":true,"timing":"from 1 October 2025","__flag":"pending — OUT OF SCOPE"},
 {"id":"ee048fa8-8a62-57e3-adc5-320ce5bc6316","title":"PRSI — Compulsory Social Insurance (non-EEA nationals)","pillar":"RESIDENCE","review_status":"pending","verification_status":"representative","non_obvious":true,"timing":"from 1 October 2025","__flag":"pending — OUT OF SCOPE"}
]
```

### Full collision surface — all 52 live IRELAND titles

Your 7 titles must match **none** of these, exactly or near-exactly:

```
A1 Certificate — Posted Workers from Spain (EU/EEA nationals)         [pending/RESIDENCE]
Bringing a pet from Spain to Ireland — EU pet travel rules            [approved/RESIDENCE]
Contributions paid abroad can be combined with Irish contributions    [approved/SOCIAL_SECURITY]
Critical Skills Employment Permit — eligibility                       [approved/RESIDENCE]
Critical Skills Permit – application fee                              [approved/RESIDENCE]
Critical Skills Permit – employer 50:50 workforce rule                [pending/RESIDENCE]
Critical Skills Permit – nine-month employer mobility restriction     [pending/RESIDENCE]
Critical Skills Permit – occupation list                              [approved/RESIDENCE]
Critical Skills Permit – salary threshold                             [approved/RESIDENCE]
Dublin rental market — practical realities                            [approved/RESIDENCE]
General Employment Permit – application fee                           [approved/RESIDENCE]
General Employment Permit – Labour Market Needs Test                  [approved/RESIDENCE]
General Employment Permit – salary threshold                          [approved/RESIDENCE]
Immigration permission – CSEP to Stamp 4                              [approved/RESIDENCE]
Immigration permission – Stamp 1 / IRP registration                   [approved/RESIDENCE]
Ireland — a residence permit cannot be held in two EU states at once   [pending/RESIDENCE]
Ireland — booking within 90 days preserves lawful presence            [pending/RESIDENCE]
Ireland — Burgh Quay is the nationwide first-time registration office  [pending/RESIDENCE]
Ireland — csep immediate family reunification                         [approved/RESIDENCE]
Ireland — csep no labour market needs test thresholds                 [approved/RESIDENCE]
Ireland — dependant join family d visa required                       [approved/RESIDENCE]
Ireland — employment permit 12-week application lead time             [pending/RESIDENCE]
Ireland — employment permit registration is valid 12 months and renews online [pending/RESIDENCE]
Ireland — entry d visa long stay over 90 days                         [approved/RESIDENCE]
Ireland — entry d visa required venezuela                             [approved/RESIDENCE]
Ireland — entry visa after permit timing                              [approved/RESIDENCE]
Ireland — entry visa apply from country of residence                  [approved/RESIDENCE]
Ireland — IRP absence limit of 90 days in a rolling year              [pending/RESIDENCE]
Ireland — leaving before registration can require a new entry visa    [pending/RESIDENCE]
Ireland — registration cannot be booked before arrival                [pending/RESIDENCE]
Ireland — spanish residence does not grant irish entry                [approved/RESIDENCE]
Ireland — spouse stamp 1g right to work                               [approved/RESIDENCE]
Ireland outside the Schengen area — separate immigration system       [approved/RESIDENCE]
Irish Income Tax — Rates and Bands (EU/EEA nationals)                 [pending/RESIDENCE]
Irish Income Tax — Rates and Bands (non-EEA nationals)                [pending/RESIDENCE]
Irish tax residence turns on 183 days in a year, or 280 across two    [approved/EMPLOYMENT]
IRP / ISD Immigration Registration (non-EEA nationals)                [pending/RESIDENCE]
IRP card — first-time registration timeline and fee                   [approved/RESIDENCE]
PPS Number — Application and Uses (EU/EEA nationals)                  [pending/RESIDENCE]
PPS Number — Application and Uses (non-EEA nationals)                 [pending/RESIDENCE]
PPSN (Personal Public Service Number) — application and emergency tax [approved/RESIDENCE]
PRSI — Compulsory Social Insurance (EU/EEA nationals)                 [pending/RESIDENCE]
PRSI — Compulsory Social Insurance (non-EEA nationals)                [pending/RESIDENCE]
PRSI is compulsory for most employees between 16 and pensionable age  [approved/SOCIAL_SECURITY]
Public Health Entitlement — Ordinary Residence (EU/EEA nationals)     [pending/RESIDENCE]
Public Health Entitlement — Ordinary Residence (non-EEA nationals)    [pending/RESIDENCE]
Register the job with Revenue through myAccount to avoid emergency tax [approved/EMPLOYMENT]
Split-year treatment can be requested for the year of arrival         [approved/EMPLOYMENT]
The employer's RPN drives Income Tax, USC and PRSI deductions         [approved/EMPLOYMENT]
Universal Social Charge — Threshold (EU/EEA nationals)                [pending/RESIDENCE]
Universal Social Charge — Threshold (non-EEA nationals)               [pending/RESIDENCE]
Work Permission Requirement for Non-EEA Workers (Ireland) (non-EEA nationals) [pending/RESIDENCE]
```

**Naming conventions in play.** Live titles use three families:
`"… – …"` (en-dash U+2013, the permit family), `"… — …"` (em-dash U+2014, the
`Ireland — …` / `PRSI — …` families), and **bare sentence titles with no dash at all** —
which is what the live `EMPLOYMENT` tax rows use: *"Irish tax residence turns on 183 days in a
year, or 280 across two"*, *"Register the job with Revenue through myAccount to avoid emergency
tax"*, *"The employer's RPN drives Income Tax, USC and PRSI deductions"*, *"Split-year treatment
can be requested for the year of arrival"*.

> **This is the convention to follow for this unit** — the sibling rows your 7 titles will sit
> beside are all bare declarative sentences that state the rule. Prefer that shape here over
> the `Ireland — …` prefix, which in this corpus marks immigration rows. Whichever you choose,
> **title is the upsert key**: a title differing by one dash character is a *different row*.

---

## 5. RULES

1. **Append-only.** Generate `INSERT`s only. **No `UPDATE`, no `DELETE`, no `UPSERT`/
   `ON CONFLICT DO UPDATE`.** If a collision is possible, do *not* emit that row and say so in
   the prediction.
2. **Dedup on `(country_code, purpose, title)`** — the natural key. All live rows are
   `('IRELAND','employment', …)`, so **your titles must differ from every existing one**, and
   from each other.
3. **Pillar is `EMPLOYMENT` on all 7 rows** (§2). **NEVER write the literal `TAX`** — it is not
   in `CANONICAL_PILLARS`, the column has no CHECK constraint, and it would invent an eighth
   pillar nothing renders. Never write a pillar outside `CANONICAL_PILLARS`.
4. **Promote to PENDING.** `review_status='pending'` **explicitly on every row** — the column
   defaults to `'approved'`.
5. **MUST NOT touch or overwrite any existing row.** Off-limits ids (the approved tripwires):
   - `8e4041a0-63a6-5945-b99e-83c2c4719a18` — *Register the job with Revenue through myAccount…*
   - `91bd4c65-e307-572d-9ea3-08c1a4e995fc` — *The employer's RPN drives Income Tax, USC and PRSI…*
   - `de5418cf-887d-52a4-b6c5-e8297f01efe7` — *Irish tax residence turns on 183 days…*
   - `0c52c2c8-e92c-51c1-9ebb-728da7e603f4` — *PPSN … application and emergency tax*
   - `6a3bc272-03e3-5fa4-9100-19b674ec0c50` — *PRSI is compulsory for most employees…*
   - `d47357e6-c886-53d9-942b-608f8158047a` — *Split-year treatment can be requested for the year of arrival*
   …and the 6 `pending` rows in §4, which are **pre-existing D3 debt and out of scope**.
6. **Exactly 7 rows.** Only `__promote: true`. The 2 DUP and 1 PARTIAL facts produce no row.
7. **Nothing served.** `verification_status` must be `representative` on all 7 — never
   `expert_verified`, never `corpus_grounded` (every fact is `accuracy_tier='needs_review'`).
8. **No invention.** Every value traces to §3 or a §2 rule. A field the snapshot does not carry
   stays NULL — **including `timing` on all 7 rows**, even the one whose `fact_type` is
   `deadline`. Do not invent citations, numbers, timings or confidence scores. **Keep the
   `Commonly believed: / Actually: / Action required:` prose verbatim** where a fact carries it.
   **Keep the year stamp** in *"8% in 2026"*.
9. **Do NOT wrap in a transaction.** Emit bare `INSERT` statements — **no `BEGIN`, `COMMIT` or
   `ROLLBACK`.** The applier supplies the dry-run transaction. End each `INSERT` with
   `RETURNING country_code, purpose, title, pillar, review_status`.
10. **Deterministic ids** — `uuid5(a1c9e349-0000-4000-8000-000000000001,
    'IRELAND|employment|<title>')`, emitted as text literals. No random uuids, no
    `gen_random_uuid()`.

---

## 6. TASK + OUTPUT CONTRACT

### Task

Generate the append-only `INSERT` SQL that promotes the **7 `__promote: true` facts** from §3
into `public.requirement_items`, obeying every rule in §5 — **plus a prediction** of exactly
what applying it will produce, **plus a verification `SELECT`** to run after a real apply.

Choose one reader-facing title per fact (this is what a relocating employee sees). Titles must
follow the live conventions in §4 — for this unit, the bare declarative sentence used by the
sibling `EMPLOYMENT` tax rows — collide with no existing IRELAND row and with none of each
other, and not merely restate the `fact_key`.

**One editorial note worth your judgement:** five of these seven rows are facets of a single
mechanism (no RPN → emergency basis → 40% / week-5 cliff / 8% USC). Titled badly they read as
five near-duplicates. Titled well they read as a sequence a mover can act on. That sequencing
is the judgement this step exists for.

### OUTPUT CONTRACT

Cursor must return EXACTLY these three delimited sections and nothing else:

```
===ARTIFACT_SQL===
-- INSERT statement(s) ONLY. Append-only: no UPDATE, no DELETE, no BEGIN/COMMIT/ROLLBACK (the applier wraps it in a dry-run transaction). End each INSERT with:
--   RETURNING country_code, purpose, title, pillar, review_status
INSERT INTO public.requirement_items (…columns…) VALUES (…) RETURNING country_code, purpose, title, pillar, review_status;

===PREDICTION_JSON===
{
  "expected_inserts": [ {"country_code":"IRELAND","purpose":"employment","title":"…","pillar":"EMPLOYMENT","review_status":"pending","source_fact_key":"…"}  /* exactly 7 */ ],
  "expected_insert_count": 7,
  "must_not_touch_ids": [ "<approved tripwire ids from LIVE STATE>" ],
  "dedup_key": ["country_code","purpose","title"],
  "assumptions": "…"
}

===VERIFICATION_SQL===
-- A SELECT the applier runs AFTER a real apply to confirm the 7 rows exist as predicted, all review_status='pending' and pillar='EMPLOYMENT', and no reviewed row changed.
SELECT …;
```

**Filling it in for this bundle:**
- `expected_inserts` — exactly **7** entries, one per `__promote: true` fact; all
  `country_code:"IRELAND"`, `purpose:"employment"`, `pillar:"EMPLOYMENT"`,
  `review_status:"pending"`. Include `source_fact_key` so the applier can map row → fact.
- `must_not_touch_ids` — the six approved ids in §5.5.
- `assumptions` — anything the snapshot did not settle (title wording above all). If a rule in
  §5 makes the task impossible, say so here rather than emitting SQL that breaks it.

---

## ⚠️ SEPARATE ITEMS — recorded so they are not lost, NOT part of this bundle

Both are `UPDATE`s, and this bundle forbids `UPDATE`.

**1. D3 — pillar debt on the live tax rows.** *Irish Income Tax — Rates and Bands* (both
audiences) and *Universal Social Charge — Threshold* (both audiences) sit at `RESIDENCE` while
every other live Irish tax row is `EMPLOYMENT`. After this unit lands, the same concept will be
split across two pillars — 4 rows at `RESIDENCE`, 10 at `EMPLOYMENT`. That is worse than
today's inconsistency, not better, and it wants a small gated backfill. **A reviewer's call.**

**2. PR #1973 is stranded.** See the correction box at the top. The pillar fix needs re-landing
onto `main` as a fresh PR before any future run of `scripts/import_otto_facts.py --promote`
will file tax content correctly. It does not block this bundle.

---

*Bundle built read-only: SELECTs against `nsvefcvpvwwwhuqyuqmp` plus file reads. No writes, no
promotion, no secrets.*
