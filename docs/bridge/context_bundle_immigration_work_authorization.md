# CONTEXT BUNDLE — promote `immigration_work_authorization` (ES→IE third-country)

**Bundle id:** `context_bundle:ES-IE:thirdcountry:immigration_work_authorization`
**Generated:** 2026-08-22 · read-only export (SELECTs + file reads; no writes, no promotion)
**Batch:** `es-ie-thirdcountry-requirements-2026-08-22` · **Project:** `nsvefcvpvwwwhuqyuqmp`
**Bridge role:** Generator input (Cursor). Generation is read-only; a wired applier dry-runs,
diffs against your prediction, and only then applies. You have no handle to prod — do not
assume one.

> **Snapshot semantics.** Everything below is frozen at export time. The applier reconciles
> against live at apply time. Generate against this snapshot; do not invent state not in it.

---

## ⚠️ READ THIS BEFORE GENERATING — the grain mismatch

The repo's normal promotion path (`backend/imports/otto/executor.py::promote()` →
`mappings.resolve()`) emits **one `requirement_items` row per staged *topic*, not per fact.**
It would merge all 9 facts of this topic into a single row titled
*"Ireland - Immigration and work authorisation (third-country professional)"*.

**This task is different: 3 specific facts must become rows.** So you must generate
**per-fact rows with per-fact titles** — you cannot reuse `mappings.py`'s
`title = entity.title` rule verbatim, because it would produce one row, and one title, for
all nine. Use §2 for how the *other* columns are derived, and choose a title per fact
(§6 constrains this). **The title you choose is the dedup key** — see §1.

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
producing any row whose `(country_code, purpose, title)` matches a reviewed row in §4.

`id` is `character varying`, **not** uuid-typed. Both writers derive it as
`uuid5(_SEED_NS, <natural key>)` with
`_SEED_NS = UUID("a1c9e349-0000-4000-8000-000000000001")`
(`backend/scripts/seed_requirements.py`), so the promoter and the YAML seeder converge on one
row for one natural key rather than racing. Derive ids the same way; do not emit random uuids.

### ⚠️ Two schema traps

1. **`review_status` DEFAULTS to `'approved'`.** Omitting the column publishes unreviewed
   facts to real users the moment the write lands. **Always set `'pending'` explicitly.**
2. **`pillar` has NO CHECK constraint.** An unrecognised value is written happily and invents
   a pillar nothing renders. Only the seven in §2 are legal.

Constraints present on the table: only `requirement_items_review_status_check`
(`review_status IN ('pending','approved','rejected')`).

---

## 2. MAPPING RULES — `backend/imports/otto/mappings.py`

How each target column is derived from a staged entity + its facts. Excerpted; comments
trimmed for length, logic verbatim.

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
IMMIGRATION_PILLAR = "RESIDENCE"   # the DEFAULT, not the verdict
```

### Pillar resolution (PR #1973 — `resolve_pillar`)

```python
CANONICAL_PILLARS = ("RESIDENCE", "IDENTITY", "EMPLOYMENT", "HOUSING",
                     "SOCIAL_SECURITY", "TIMELINE", "HEALTHCARE")

PILLAR_ALIASES = {"TAX": "EMPLOYMENT", "PAYROLL": "EMPLOYMENT"}

def resolve_pillar(facts, *, default=IMMIGRATION_PILLAR):
    """The pillar a topic's facts state, or `default` when they state none.
    Returns (pillar, None) or (None, reason)."""
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

Rules in words:
- **Honor `applies_to.pillar` when stated**; fall back to the `domain_area='immigration'`
  default (`RESIDENCE`) only when no fact states one.
- **`TAX` → `EMPLOYMENT`** (grounded in `candidate_beam.importer.PILLAR_BY_CATEGORY`).
- **Unknown pillar → refuse.** Do not write it.
- **A fact carrying `RESIDENCE` says nothing** (it is what the default already yields);
  the signal is the non-default pillar. **Two different non-default pillars → refuse.**
- For **this** topic all 9 facts carry `pillar: "RESIDENCE"` ⇒ **resolved pillar =
  `RESIDENCE`** for every row you generate. No alias, no conflict.

### Other derivations

- `title` — normally `entity.title` verbatim. **Not usable here; see the grain-mismatch box.**
- `purpose` — `PURPOSES[applies_to.status]`; all 9 facts are `professional` ⇒ **`employment`**.
- `country_code` — `iso_to_catalog_name(destination_country)`; `IE` ⇒ **`IRELAND`**
  (the column holds full uppercase country names, **not** ISO codes).
- `applies_to_nationality_classes_json` — all facts `non-EEA` ⇒ **`["THIRD_COUNTRY"]`**.
- `description` — `compose_description(facts)`: fact texts joined, ordered by `fact_type`
  (`eligibility, step, document, deadline, fee, where_to_apply, other`) then `fact_key`, so
  re-runs are byte-identical. Any `applies_to.non_obvious_note` is appended behind the marker
  `"\n\nWhy this is easy to miss: "`.
- `citations_json` — **one citation object per distinct `source_url`**, not bare URL strings.
  A bare URL resolves against nothing and serves an empty citation list while the provenance
  guard still passes. Carry `needs_lawyer_review` through.
- `severity` = `WARN`, `owner` = `EMPLOYEE`, `required_fields_json` = `"[]"`.
- `verification_status` — `corpus_grounded` only when **every** contributing fact cleared the
  sourcing gate; otherwise weaker. **Nothing here may write `expert_verified`.**
- `non_obvious` — from `applies_to.non_obvious`.
- `timing` — from a contributing fact's `applies_to.timing`, when present.

---

## 3. SOURCE SNAPSHOT (JSON)

Staged entity and **all 9** fact candidates for this topic, from `otto_staging`. Each fact is
tagged `"__promote": true|false` — **exactly 3 are `true`.**

Classification is from `docs/imports/es-ie-thirdcountry-requirements-2026-08-22/RECONCILIATION_REPORT.md`
(3 NEW · 5 DUP · 1 PARTIAL). **PARTIAL counts as do-not-promote**, leaving 3.

```json
{
  "entity": {
    "destination_country": "IE",
    "topic_key": "ES-IE:thirdcountry:immigration_work_authorization",
    "domain_area": "immigration",
    "title": "Ireland - Immigration and work authorisation (third-country professional)",
    "batch_id": "es-ie-thirdcountry-requirements-2026-08-22",
    "source": "otto_research"
  },
  "facts": [
    {
      "__promote": true,
      "__classification": "NEW",
      "fact_key": "csep_nine_month_employer_lock",
      "fact_type": "eligibility",
      "fact_text": "A new employment permit for a DIFFERENT employer cannot be considered until 9 months have elapsed since the holder first commenced employment in the State under an employment permit. Redundancy, and unforeseen circumstances that fundamentally change the employment relationship, are the stated exceptions.\n\nCommonly believed: The 2-year job offer is the commitment; you can move employer if a better role appears.\n\nActually: Statute (section 18, Employment Permits Regulations 2024) blocks a different-employer permit for the first 9 months. For a mover who has already relocated a household, the first 9 months carry no employer mobility at all.\n\nAction required: Treat the first 9 months as employer-locked when weighing the offer and the move.",
      "source_url": "https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/",
      "evidence_quote": "In accordance with section 18 of the Employment Permits Regulations 2024, a new employment permit (for a different employer) cannot be considered if less than 9 months has elapsed since the permit holder first commenced employment in the State pursuant to an employment permit.",
      "confidence": "high",
      "confidence_score": 0.9,
      "accuracy_tier": "auto_accepted",
      "status": "new",
      "dedupe_key": "IE|ES-IE:thirdcountry:immigration_work_authorization|csep_nine_month_employer_lock",
      "applies_to": {
        "topic": "immigration_work_authorization", "pillar": "RESIDENCE",
        "status": "professional", "nationality": "non-EEA", "corridor": "ES->IE",
        "persona": "third-country professional relocating Madrid->Dublin",
        "fact_uid": "ES_IE:THIRD_COUNTRY:csep_nine_month_employer_lock",
        "non_obvious": true, "needs_lawyer_review": true,
        "review_status": "pending", "verification_status": "representative",
        "quote_verbatim_confirmed": true,
        "nationality_scope_basis": "nationality_determined",
        "source_name": "DETE - Critical Skills Employment Permit",
        "batch_id": "es-ie-thirdcountry-requirements-2026-08-22"
      }
    },
    {
      "__promote": true,
      "__classification": "NEW",
      "fact_key": "employer_50_percent_eea_workforce_rule",
      "fact_type": "eligibility",
      "fact_text": "A permit for a non-EEA professional is refused unless 50% or more of the employer's workforce are EEA nationals when the application is made. The applicant's own eligibility is therefore not sufficient - the employer's headcount composition is a gating condition the candidate cannot influence.\n\nCommonly believed: Permit eligibility is about the applicant's qualifications and salary.\n\nActually: The 50:50 rule is an EMPLOYER-side test. A small or newly-founded Irish entity staffed mainly by non-EEA nationals cannot sponsor, regardless of how well the candidate qualifies. Start-ups within 2 years of establishment that are Enterprise Ireland or IDA Ireland clients may have it waived.\n\nAction required: Confirm with the employer that they meet the 50:50 test, or hold the waiver, before resigning the current role.",
      "source_url": "https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/",
      "evidence_quote": "An employment permit will not be granted to companies unless 50% or more of the employees in the firm are EEA nationals at the time of application.",
      "confidence": "medium",
      "confidence_score": 0.6,
      "accuracy_tier": "auto_accepted",
      "status": "new",
      "dedupe_key": "IE|ES-IE:thirdcountry:immigration_work_authorization|employer_50_percent_eea_workforce_rule",
      "applies_to": {
        "topic": "immigration_work_authorization", "pillar": "RESIDENCE",
        "status": "professional", "nationality": "non-EEA", "corridor": "ES->IE",
        "persona": "third-country professional relocating Madrid->Dublin",
        "fact_uid": "ES_IE:THIRD_COUNTRY:employer_50_percent_eea_workforce_rule",
        "non_obvious": true, "needs_lawyer_review": false,
        "review_status": "pending", "verification_status": "representative",
        "quote_verbatim_confirmed": true,
        "nationality_scope_basis": "nationality_determined",
        "source_name": "DETE - Critical Skills Employment Permit",
        "batch_id": "es-ie-thirdcountry-requirements-2026-08-22"
      }
    },
    {
      "__promote": true,
      "__classification": "NEW",
      "fact_key": "permit_application_12_week_lead_time",
      "fact_type": "deadline",
      "fact_text": "Every employment permit application must reach DETE at least 12 weeks before the proposed employment start date. For a non-EEA professional this 12 weeks is only the FIRST leg of the runway: where an entry visa is also needed, the visa application can only follow the permit grant.\n\nCommonly believed: You apply for the permit once you have accepted the job offer.\n\nActually: The 12-week minimum is a DETE intake rule, not a processing estimate, and it runs before any visa or registration step. A start date agreed with the employer inside 12 weeks of the offer cannot lawfully be met through this route.\n\nAction required: Fix the permit lodgement date first and work the agreed start date backwards from it.",
      "source_url": "https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/",
      "evidence_quote": "An application for any employment permit must be received at least 12 weeks before the proposed employment start date.",
      "confidence": "medium",
      "confidence_score": 0.6,
      "accuracy_tier": "auto_accepted",
      "status": "new",
      "dedupe_key": "IE|ES-IE:thirdcountry:immigration_work_authorization|permit_application_12_week_lead_time",
      "applies_to": {
        "topic": "immigration_work_authorization", "pillar": "RESIDENCE",
        "status": "professional", "nationality": "non-EEA", "corridor": "ES->IE",
        "persona": "third-country professional relocating Madrid->Dublin",
        "fact_uid": "ES_IE:THIRD_COUNTRY:permit_application_12_week_lead_time",
        "non_obvious": true, "needs_lawyer_review": false,
        "review_status": "pending", "verification_status": "representative",
        "quote_verbatim_confirmed": true,
        "nationality_scope_basis": "nationality_determined",
        "source_name": "DETE - Critical Skills Employment Permit",
        "batch_id": "es-ie-thirdcountry-requirements-2026-08-22"
      }
    },

    { "__promote": false, "__classification": "DUP",
      "__duplicates_live": "Ireland — csep no labour market needs test thresholds (8e59eed1-11d1-50fd-bd0b-61cc22c8b9b3, approved)",
      "fact_key": "csep_no_labour_market_needs_test", "fact_type": "eligibility",
      "source_url": "https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/" },

    { "__promote": false, "__classification": "DUP",
      "__duplicates_live": "Critical Skills Permit – application fee (118c69a1-c647-5268-b25b-2ee5c6bb0003, approved, verification_status='verified') ⚠ TRIPWIRE",
      "fact_key": "csep_processing_fee_and_refund", "fact_type": "fee",
      "source_url": "https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/" },

    { "__promote": false, "__classification": "DUP",
      "__duplicates_live": "Critical Skills Permit – salary threshold (ecf6c3bb-632f-5d5a-860c-c8e17ed4e51b, approved)",
      "fact_key": "csep_remuneration_thresholds", "fact_type": "eligibility",
      "source_url": "https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/" },

    { "__promote": false, "__classification": "DUP",
      "__duplicates_live": "Immigration permission – CSEP to Stamp 4 (c9402361-26ff-594f-adfc-205202e08e9b, approved)",
      "fact_key": "csep_stamp4_after_permit_no_support_letter", "fact_type": "other",
      "source_url": "https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/" },

    { "__promote": false, "__classification": "DUP",
      "__duplicates_live": "Ireland — entry visa after permit timing (4c119775-b9c9-5bc0-8bbe-1c162b567cb0, approved)",
      "fact_key": "entry_visa_follows_permit_if_visa_required", "fact_type": "other",
      "__note": "record is explicitly CONDITIONAL: asserts ordering only, not any nationality's visa-required status",
      "source_url": "https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/" },

    { "__promote": false, "__classification": "PARTIAL",
      "__overlaps_live": "Immigration permission – Stamp 1 / IRP registration (c07c4900-7792-561c-b07e-b2464c2f913b, approved) + Work Permission Requirement for Non-EEA Workers (6bff7336-efb0-582b-b0db-38fb1ae1b1a0, pending)",
      "fact_key": "employment_permit_is_not_residence_permission", "fact_type": "eligibility",
      "source_url": "https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/" }
  ]
}
```

**Counts to reconcile against: 9 facts total · 3 `__promote: true` · 5 DUP · 1 PARTIAL.**

---

## 4. LIVE STATE (JSON) — existing `requirement_items` for this concept

`country_code='IRELAND'`, CSEP / employment-authorisation concept. **All are `purpose='employment'`,
`pillar='RESIDENCE'`.** 14 approved, 1 pending.

```json
[
 {"id":"57073a0e-85fb-5926-9213-e6564812ae7e","title":"Critical Skills Employment Permit — eligibility","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":false},
 {"id":"118c69a1-c647-5268-b25b-2ee5c6bb0003","title":"Critical Skills Permit – application fee","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"verified","non_obvious":false},
 {"id":"0899a9ab-364c-50a6-9c33-14a227917484","title":"Critical Skills Permit – occupation list","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":false},
 {"id":"ecf6c3bb-632f-5d5a-860c-c8e17ed4e51b","title":"Critical Skills Permit – salary threshold","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":false},
 {"id":"bfec7cda-547a-5c1d-b616-9e3644d7a6f9","title":"General Employment Permit – application fee","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":false},
 {"id":"82cc8204-f1d6-538f-8ffb-3b2b23730bd0","title":"General Employment Permit – Labour Market Needs Test","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":false},
 {"id":"240c3810-0e70-5ee5-9a22-d9140ef3ecb0","title":"General Employment Permit – salary threshold","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":false},
 {"id":"c9402361-26ff-594f-adfc-205202e08e9b","title":"Immigration permission – CSEP to Stamp 4","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":false},
 {"id":"c07c4900-7792-561c-b07e-b2464c2f913b","title":"Immigration permission – Stamp 1 / IRP registration","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":false},
 {"id":"07e907f6-94ae-5766-bf7e-77c50c83dc57","title":"Ireland — csep immediate family reunification","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":true},
 {"id":"8e59eed1-11d1-50fd-bd0b-61cc22c8b9b3","title":"Ireland — csep no labour market needs test thresholds","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":false},
 {"id":"4c119775-b9c9-5bc0-8bbe-1c162b567cb0","title":"Ireland — entry visa after permit timing","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":true},
 {"id":"9505e3f3-ea45-5788-9f84-90f14bb9e5ed","title":"Ireland — entry visa apply from country of residence","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":false},
 {"id":"a114fd40-f8d1-5562-aba4-d0e83e127670","title":"Ireland — spouse stamp 1g right to work","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":true},
 {"id":"6bff7336-efb0-582b-b0db-38fb1ae1b1a0","title":"Work Permission Requirement for Non-EEA Workers (Ireland) (non-EEA nationals)","purpose":"employment","pillar":"RESIDENCE","review_status":"approved_status_is_pending","verification_status":"representative","non_obvious":true,"__review_status":"pending"}
 ]
```

> Note on the last row: its `review_status` is **`pending`** (the `approved_status_is_pending`
> string is a transcription guard, not a value — use `pending`).

**Naming conventions in play** — live titles use two families, `"Critical Skills Permit – …"`
(en-dash) and `"Ireland — csep …"` (em-dash). Since **title is the upsert key**, a new title
that differs by so much as a dash character is a *different row*. Pick titles that cannot
collide with any of the 15 above.

---

## 5. RULES

1. **Append-only.** Generate `INSERT`s only. **No `UPDATE`, no `DELETE`, no `UPSERT`/
   `ON CONFLICT DO UPDATE`** against `requirement_items`. If a collision is possible, the
   correct behaviour is to *not emit that row* and say so in the prediction.
2. **Dedup on `(country_code, purpose, title)`** — the natural key. All 15 live rows in §4 are
   `('IRELAND','employment', …)`, so **your titles must differ from all 15**.
3. **Honor the pillar** per §2. For this topic that resolves to **`RESIDENCE`** on all 3 rows.
   Never write a pillar outside `CANONICAL_PILLARS`.
4. **Promote to PENDING.** `review_status='pending'` **explicitly on every row** — the column
   defaults to `'approved'`, so omitting it publishes unreviewed facts.
5. **MUST NOT touch or overwrite any existing reviewed row.** All 15 ids in §4 are off-limits;
   the highest-value tripwires:
   - `118c69a1-c647-5268-b25b-2ee5c6bb0003` — *Critical Skills Permit – application fee* —
     **`verification_status='verified'`**, the only non-`representative` row here.
   - `8e59eed1-11d1-50fd-bd0b-61cc22c8b9b3` — *Ireland — csep no labour market needs test thresholds*
   - `ecf6c3bb-632f-5d5a-860c-c8e17ed4e51b` — *Critical Skills Permit – salary threshold*
   - `c9402361-26ff-594f-adfc-205202e08e9b` — *Immigration permission – CSEP to Stamp 4*
   - `4c119775-b9c9-5bc0-8bbe-1c162b567cb0` — *Ireland — entry visa after permit timing*
6. **Exactly 3 rows.** Only the `__promote: true` facts. The 5 DUP and 1 PARTIAL facts must
   produce no row.
7. **Nothing served.** `verification_status` must never be `expert_verified`. Use
   `representative` (what the facts carry) or `corpus_grounded` at most.
8. **No invention.** Every value must trace to §3 or to a §2 rule. A field the snapshot does
   not carry stays NULL. Do not invent citations, numbers, or confidence scores.
9. **Do NOT wrap in a transaction.** Emit bare `INSERT` statements — **no `BEGIN`, `COMMIT` or
   `ROLLBACK`.** The applier supplies the dry-run transaction around your SQL. End each
   `INSERT` with `RETURNING country_code, purpose, title, pillar, review_status`.
10. **Deterministic ids** — `uuid5(a1c9e349-0000-4000-8000-000000000001, <natural key>)`,
    emitted as text. No random uuids, no `gen_random_uuid()`.

---

## 6. TASK + OUTPUT CONTRACT

### Task

Generate the append-only `INSERT` SQL that promotes the **3 `__promote: true` facts** from §3
into `public.requirement_items`, obeying every rule in §5 — **plus a prediction** of exactly
what applying it will produce, so the applier can diff actual against predicted before
committing, **plus a verification `SELECT`** to run after a real apply.

Choose one title per fact. Titles must be reader-facing (this is what an employee sees), must
not collide with any of the 15 in §4, and should follow the shape of the live corpus rather
than restating the `fact_key`.

### OUTPUT CONTRACT

Cursor must return EXACTLY these three delimited sections and nothing else:

```
===ARTIFACT_SQL===
-- INSERT statement(s) ONLY. Append-only: no UPDATE, no DELETE, no BEGIN/COMMIT/ROLLBACK (the applier wraps it in a dry-run transaction). End each INSERT with:
--   RETURNING country_code, purpose, title, pillar, review_status
INSERT INTO public.requirement_items (…columns…) VALUES (…) RETURNING country_code, purpose, title, pillar, review_status;

===PREDICTION_JSON===
{
  "expected_inserts": [ {"country_code":"IRELAND","purpose":"…","title":"…","pillar":"…","review_status":"pending"}  /* exactly 3 */ ],
  "expected_insert_count": 3,
  "must_not_touch_ids": [ "<reviewed row ids from LIVE STATE>" ],
  "dedup_key": ["country_code","purpose","title"],
  "assumptions": "…"
}

===VERIFICATION_SQL===
-- A SELECT the applier runs AFTER a real apply to confirm the 3 rows exist as predicted, all review_status='pending', and no reviewed row changed.
SELECT …;
```

**Filling it in for this bundle:**
- `expected_inserts` — exactly 3 entries, one per `__promote: true` fact in §3; all
  `country_code:"IRELAND"`, `purpose:"employment"`, `pillar:"RESIDENCE"`,
  `review_status:"pending"`.
- `must_not_touch_ids` — the reviewed row ids from §4 / §5.5.
- `assumptions` — anything you had to decide that the snapshot did not settle (title wording
  above all). If a rule in §5 makes the task impossible, say so here rather than emitting SQL
  that breaks it.

---

*Bundle built read-only: SELECTs against `nsvefcvpvwwwhuqyuqmp` plus file reads at
`fix/otto-promote-honors-applies-to-pillar` (PR #1973). No writes, no promotion, no secrets.*
