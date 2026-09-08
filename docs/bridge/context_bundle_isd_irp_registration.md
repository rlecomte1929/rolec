# CONTEXT BUNDLE — promote `isd_irp_registration` (ES→IE third-country)

**Bundle id:** `context_bundle:ES-IE:thirdcountry:isd_irp_registration`
**Generated:** 2026-08-22 · read-only export (SELECTs + file reads; no writes, no promotion)
**Batch:** `es-ie-thirdcountry-requirements-2026-08-22` · **Project:** `nsvefcvpvwwwhuqyuqmp`
**Bridge role:** Generator input (Cursor). Generation is read-only; a wired applier dry-runs,
diffs against your prediction, and only then applies. You have no handle to prod — do not
assume one.

> **Snapshot semantics.** Everything below is frozen at export time. The applier reconciles
> against live at apply time. Generate against this snapshot; do not invent state not in it.

> **Second topic through this loop.** The first
> (`context_bundle_immigration_work_authorization.md`) applied clean: 3 inserts, 0 updates,
> pre-existing fingerprint unchanged. Same structure, same contract.

---

## ⚠️ READ THIS BEFORE GENERATING — the grain mismatch

The repo's normal promotion path (`backend/imports/otto/executor.py::promote()` →
`mappings.resolve()`) emits **one `requirement_items` row per staged *topic*, not per fact.**
It would merge all 11 facts of this topic into a single row titled
*"Ireland - ISD registration and the Irish Residence Permit (third-country professional)"*.

**This task is different: 7 specific facts must become rows.** Generate **per-fact rows with
per-fact titles** — you cannot reuse `mappings.py`'s `title = entity.title` rule, because it
would produce one row for all eleven. Use §2 for how the *other* columns are derived, and
choose a title per fact (§6 constrains this). **The title you choose is the dedup key** — §1.

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
on the previous topic. Derive ids the same way; do not emit random uuids.

### ⚠️ Two schema traps

1. **`review_status` DEFAULTS to `'approved'`.** Omitting the column publishes unreviewed
   facts to real users the moment the write lands. **Always set `'pending'` explicitly.**
2. **`pillar` has NO CHECK constraint.** An unrecognised value is written happily and invents
   a pillar nothing renders. Only the seven in §2 are legal.

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
IMMIGRATION_PILLAR = "RESIDENCE"   # the DEFAULT, not the verdict
```

### Pillar resolution (PR #1973 — `resolve_pillar`)

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
pillar refuses; a fact carrying the default says nothing; two different non-default pillars
refuse.

> **This topic's resolved pillar: `RESIDENCE`.**
> All 11 staged facts carry `applies_to.pillar = "RESIDENCE"` — unanimous, no alias, no
> conflict. `resolve_pillar` returns the `domain_area` default unchanged. Every row you
> generate is `pillar='RESIDENCE'`.

### Other derivations

- `title` — normally `entity.title` verbatim. **Not usable here; see the grain-mismatch box.**
- `purpose` — `PURPOSES[applies_to.status]`; all facts are `professional` ⇒ **`employment`**.
- `country_code` — `iso_to_catalog_name('IE')` ⇒ **`IRELAND`** (full uppercase country names,
  **not** ISO codes).
- `applies_to_nationality_classes_json` — all facts `non-EEA` ⇒ **`["THIRD_COUNTRY"]`**.
- `description` — that fact's `fact_text` verbatim. (`compose_description` would join and
  order many facts; at one-fact-per-row it reduces to the fact's own text. None of these
  facts carries `applies_to.non_obvious_note`, so no `"Why this is easy to miss: "` marker is
  appended — the equivalent prose is already inside `fact_text`.)
- `citations_json` — **one citation object per distinct `source_url`**, not bare URL strings.
  Shape from `mappings._citations_for`:
  `{"url", "topic_key", "name", "corridor"}` plus `"needs_lawyer_review": true` **only when**
  the fact carries it. A bare URL resolves against nothing and serves an empty citation list
  while the provenance guard still passes.
- `severity` = `WARN`, `owner` = `EMPLOYEE`, `required_fields_json` = `"[]"`.
- `verification_status` = **`representative`** (what every fact here carries).
  **Nothing may write `expert_verified`.**
- `non_obvious` — from `applies_to.non_obvious`.
- `timing` — from `applies_to.timing` when present. **No fact in this topic carries one**, so
  leave `timing` NULL. (See the D4 note at the end: the *live* row's timing is wrong, but
  fixing it is an UPDATE and out of scope for this append-only bundle.)
- `last_verified_at` — NOT NULL; use `now() AT TIME ZONE 'utc'`, matching `promote()`.

**Note on source diversity:** unlike the previous topic (single DETE URL), this topic spans
**three** ISD URLs. Citations must reflect each fact's own `source_url`, and `name` differs
per source — do not collapse them to one citation.

---

## 3. SOURCE SNAPSHOT (JSON)

Staged entity and **all 11** fact candidates. Each is tagged `"__promote": true|false` —
**exactly 7 are `true`.**

Classification per
`docs/imports/es-ie-thirdcountry-requirements-2026-08-22/RECONCILIATION_REPORT.md`:
**7 NEW · 2 DUP · 2 HELD-FOR-D4.**

```json
{
  "entity": {
    "destination_country": "IE",
    "topic_key": "ES-IE:thirdcountry:isd_irp_registration",
    "domain_area": "immigration",
    "title": "Ireland - ISD registration and the Irish Residence Permit (third-country professional)",
    "batch_id": "es-ie-thirdcountry-requirements-2026-08-22",
    "source": "otto_research"
  },
  "facts": [
    {
      "__promote": true, "__classification": "NEW",
      "__overlaps_content": "Partly restated inside pending row acdddd42's description/non-obvious note, but MORE PRECISE: it is the BOOKING inside 90 days that preserves presence, where acdddd42 says only that permission 'will not be cancelled while waiting'. No natural-key collision. Flagged so the reviewer sees the redundancy.",
      "fact_key": "booked_appointment_within_90_days_preserves_lawful_presence",
      "fact_type": "other",
      "fact_text": "Where no appointment slot is available inside the 90 days, a successfully BOOKED appointment made within the 90 days of arrival is sufficient to remain in the State until the appointment date.\n\nCommonly believed: If you cannot get an appointment within 90 days you fall out of permission.\n\nActually: The booking, not the appointment, is what has to happen inside 90 days. This is the single most reassuring registration fact and it is not on the main registration page.\n\nAction required: Book as early as possible and retain the booking confirmation as evidence of lawful presence until the appointment.",
      "source_url": "https://www.irishimmigration.ie/registering-your-immigration-permission/frequently-asked-questions-for-registration/",
      "evidence_quote": "Once you have successfully booked an appointment within the 90 days of arrival, this will be sufficient to remain in the state until the date of your appointment.",
      "confidence": "high", "confidence_score": 0.9, "accuracy_tier": "auto_accepted",
      "applies_to": {"topic":"isd_irp_registration","pillar":"RESIDENCE","status":"professional","nationality":"non-EEA","corridor":"ES->IE","non_obvious":true,"needs_lawyer_review":false,"verification_status":"representative","source_name":"ISD - Frequently asked questions for Registration"}
    },
    {
      "__promote": true, "__classification": "NEW",
      "fact_key": "burgh_quay_nationwide_registration_office",
      "fact_type": "where_to_apply",
      "fact_text": "Burgh Quay Registration Office in Dublin city centre is the single nationwide office where every first-time registration appointment takes place, at 13/14 Burgh Quay, Dublin 2, D02 XK70. A Dublin-based arrival is at the office; an arrival anywhere else in the State must still travel to Dublin for it.",
      "source_url": "https://www.irishimmigration.ie/registering-your-immigration-permission/frequently-asked-questions-for-registration/",
      "evidence_quote": "Burgh Quay Registration Office, located in Dublin City Centre is the nationwide Registration Office for Ireland where all first time registration appointments take place.",
      "confidence": "high", "confidence_score": 0.9, "accuracy_tier": "auto_accepted",
      "applies_to": {"topic":"isd_irp_registration","pillar":"RESIDENCE","status":"professional","nationality":"non-EEA","corridor":"ES->IE","non_obvious":false,"needs_lawyer_review":false,"verification_status":"representative","source_name":"ISD - Frequently asked questions for Registration"}
    },
    {
      "__promote": true, "__classification": "NEW",
      "fact_key": "cannot_hold_residence_permits_in_two_eu_states",
      "fact_type": "other",
      "fact_text": "A residence permit cannot be held for more than one EU country at a time. For a third-country professional moving from Spain, the existing Spanish residence authorisation and an Irish residence permission are mutually exclusive.\n\nCommonly believed: You keep your Spanish residence card as a fallback while you settle in Ireland.\n\nActually: ISD states a residence permit cannot be held for more than one EU country at a time. Registering in Ireland is a decision about the Spanish permission too - and the years of Spanish residence do not transfer, because Ireland is outside Schengen and is not bound by the EU Long-Term Residents Directive.\n\nAction required: Take advice on the Spanish permission BEFORE registering in Ireland; this is a two-jurisdiction decision, not an Irish formality.",
      "source_url": "https://www.irishimmigration.ie/registering-your-immigration-permission/frequently-asked-questions-for-registration/",
      "evidence_quote": "In addition, you cannot hold a residence permit for more than one EU country at a time.",
      "confidence": "medium", "confidence_score": 0.6, "accuracy_tier": "auto_accepted",
      "applies_to": {"topic":"isd_irp_registration","pillar":"RESIDENCE","status":"professional","nationality":"non-EEA","corridor":"ES->IE","non_obvious":true,"needs_lawyer_review":true,"verification_status":"representative","source_name":"ISD - Frequently asked questions for Registration"}
    },
    {
      "__promote": true, "__classification": "NEW",
      "fact_key": "employment_permit_registration_valid_12_months",
      "fact_type": "other",
      "fact_text": "Permission registered on the basis of an employment permit is usually valid for 12 months and is renewable subject to qualifying conditions. Renewals and stamp changes are completed by online application, not at Burgh Quay. Permission should be renewed at least one month before expiry to avoid unlawful presence.",
      "source_url": "https://www.irishimmigration.ie/registering-your-immigration-permission/how-to-register-your-immigration-permission-for-the-first-time/required-documents/",
      "evidence_quote": "Registration granted to persons to work based on an Employment Permit is usually valid for 12 months, thereafter the permission may be renewed subject to qualifying conditions.",
      "confidence": "high", "confidence_score": 0.9, "accuracy_tier": "auto_accepted",
      "applies_to": {"topic":"isd_irp_registration","pillar":"RESIDENCE","status":"professional","nationality":"non-EEA","corridor":"ES->IE","non_obvious":false,"needs_lawyer_review":false,"verification_status":"representative","source_name":"ISD - Required Documents (first-time registration)"}
    },
    {
      "__promote": true, "__classification": "NEW",
      "fact_key": "irp_absence_limit_90_days_rolling_year",
      "fact_type": "other",
      "fact_text": "Counting holidays plus personal and work-related travel, absence from the State should not exceed 90 days in a rolling year for an IRP holder.\n\nCommonly believed: Once you hold an IRP you can travel as much as your job requires.\n\nActually: ISD applies a 90-day-in-a-rolling-year absence expectation, and heavy business travel or extended returns to family abroad can erode the residence record that later long-term residence and naturalisation applications rest on.\n\nAction required: Keep a running total of days outside the State from the first day of permission.",
      "source_url": "https://www.irishimmigration.ie/registering-your-immigration-permission/frequently-asked-questions-for-registration/",
      "evidence_quote": "Between holidays, personal and work related travel, absence from the state should not exceed 90 days in a rolling year.",
      "confidence": "medium", "confidence_score": 0.6, "accuracy_tier": "auto_accepted",
      "applies_to": {"topic":"isd_irp_registration","pillar":"RESIDENCE","status":"professional","nationality":"non-EEA","corridor":"ES->IE","non_obvious":true,"needs_lawyer_review":false,"verification_status":"representative","source_name":"ISD - Frequently asked questions for Registration"}
    },
    {
      "__promote": true, "__classification": "NEW",
      "fact_key": "leaving_state_before_registration_needs_new_entry_visa",
      "fact_type": "other",
      "__note": "CONDITIONAL record: asserts the CONSEQUENCE for a visa-required national only; whether a nationality is visa-required is governed by batch ie-isd-visa-required-2026-08-22. Preserve that hedge in the description — do not promote it into an unconditional claim.",
      "fact_text": "CONDITIONAL FACT - ISD states that a visa-required national who leaves the State before their registration appointment cannot re-enter without a new entry visa. Whether a given nationality is visa-required is governed by the ISD visa-required nationality list (batch ie-isd-visa-required-2026-08-22); this record asserts only the CONSEQUENCE for a national who is visa-required.\n\nCommonly believed: You can travel in and out of Ireland freely once you have arrived on your visa and permit.\n\nActually: The entry visa is typically single-entry until the permission is registered. A weekend back in Madrid before the Burgh Quay appointment can strand a visa-required national outside the State.\n\nAction required: Do not leave Ireland between arrival and the registration appointment.",
      "source_url": "https://www.irishimmigration.ie/registering-your-immigration-permission/frequently-asked-questions-for-registration/",
      "evidence_quote": "Note: If you are a visa-required national and you leave the state prior to your registration appointment, you will not be able to re-enter the state without a new entry visa.",
      "confidence": "medium", "confidence_score": 0.6, "accuracy_tier": "auto_accepted",
      "applies_to": {"topic":"isd_irp_registration","pillar":"RESIDENCE","status":"professional","nationality":"non-EEA","corridor":"ES->IE","non_obvious":true,"needs_lawyer_review":true,"assertion_mode":"conditional","verification_status":"representative","source_name":"ISD - Frequently asked questions for Registration"}
    },
    {
      "__promote": true, "__classification": "NEW",
      "fact_key": "registration_cannot_be_booked_before_arrival",
      "fact_type": "other",
      "fact_text": "Appointments can only be booked after arrival in the State, once the instruction to register has been received. The 90-day clock and the appointment queue therefore both start on landing and cannot be pre-empted from Madrid.\n\nCommonly believed: You can arrange your immigration appointment in advance, like a visa appointment.\n\nActually: ISD will not accept a booking made before arrival. Nothing about the registration step can be front-loaded, so the queue is entered cold on day one of a 90-day deadline.\n\nAction required: Plan to create the ISD portal account and book on the day of arrival.",
      "source_url": "https://www.irishimmigration.ie/registering-your-immigration-permission/frequently-asked-questions-for-registration/",
      "evidence_quote": "Appointments should only be booked after you receive an instruction to register, on arrival in the State.",
      "confidence": "high", "confidence_score": 0.9, "accuracy_tier": "auto_accepted",
      "applies_to": {"topic":"isd_irp_registration","pillar":"RESIDENCE","status":"professional","nationality":"non-EEA","corridor":"ES->IE","non_obvious":true,"needs_lawyer_review":false,"verification_status":"representative","source_name":"ISD - Frequently asked questions for Registration"}
    },

    { "__promote": false, "__classification": "DUP",
      "__duplicates_live": "IRP card — first-time registration timeline and fee (572b697b-c6cd-5c14-b1d6-b80906743e0b, approved)",
      "fact_key": "irp_registration_fee_300", "fact_type": "fee",
      "source_url": "https://www.irishimmigration.ie/registering-your-immigration-permission/how-to-register-your-immigration-permission-for-the-first-time/required-documents/" },

    { "__promote": false, "__classification": "DUP",
      "__duplicates_live": "IRP card — first-time registration timeline and fee (572b697b…, approved) + Immigration permission – Stamp 1 / IRP registration (c07c4900…, approved)",
      "fact_key": "registration_appointment_biometrics_and_irp_card", "fact_type": "document",
      "source_url": "https://www.irishimmigration.ie/registering-your-immigration-permission/frequently-asked-questions-for-registration/" },

    { "__promote": false, "__classification": "HELD-FOR-D4",
      "__reason": "Contradicts pending live row acdddd42, whose timing AND description state the 90 days runs from ISD granting permission. These facts say it runs from the landing stamp at arrival. Correcting acdddd42 is an UPDATE — out of scope for an append-only bundle. See the D4 note at the end of this file.",
      "fact_key": "isd_registration_required_over_90_days", "fact_type": "eligibility",
      "source_url": "https://www.irishimmigration.ie/registering-your-immigration-permission/" },

    { "__promote": false, "__classification": "HELD-FOR-D4",
      "__reason": "Same conflict — this is the fact that carries the correct trigger ('the landing stamp will instruct that you register within 90 days'). Held so the correction happens as one deliberate D4 edit rather than by adding a second row that contradicts a live one.",
      "fact_key": "landing_stamp_90_day_registration_deadline", "fact_type": "deadline",
      "source_url": "https://www.irishimmigration.ie/registering-your-immigration-permission/frequently-asked-questions-for-registration/" }
  ]
}
```

**Counts to reconcile against: 11 facts total · 7 `__promote: true` · 2 DUP · 2 HELD-FOR-D4.**

---

## 4. LIVE STATE (JSON) — existing `requirement_items` for the IRP / registration concept

`country_code='IRELAND'`. All `purpose='employment'`, `pillar='RESIDENCE'`.

```json
[
 {"id":"acdddd42-8404-56f4-968b-cdaf76e071c7","title":"IRP / ISD Immigration Registration (non-EEA nationals)","purpose":"employment","pillar":"RESIDENCE","review_status":"pending","verification_status":"representative","non_obvious":true,"timing":"within 90 days of ISD granting permission","__flag":"D4 — timing AND description carry the WRONG trigger; see note at end. NOT a tripwire (pending), but MUST NOT be touched by this append-only artifact."},
 {"id":"572b697b-c6cd-5c14-b1d6-b80906743e0b","title":"IRP card — first-time registration timeline and fee","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"corpus_grounded","non_obvious":false,"__flag":"TRIPWIRE — approved + corpus_grounded"},
 {"id":"c07c4900-7792-561c-b07e-b2464c2f913b","title":"Immigration permission – Stamp 1 / IRP registration","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":false,"__flag":"TRIPWIRE — approved"},
 {"id":"c9402361-26ff-594f-adfc-205202e08e9b","title":"Immigration permission – CSEP to Stamp 4","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":false,"__flag":"TRIPWIRE — approved"},
 {"id":"a114fd40-f8d1-5562-aba4-d0e83e127670","title":"Ireland — spouse stamp 1g right to work","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":true,"__flag":"TRIPWIRE — approved"},
 {"id":"0c97ae08-d8a8-58c1-a607-a70a7edb0626","title":"Ireland outside the Schengen area — separate immigration system","purpose":"employment","pillar":"RESIDENCE","review_status":"approved","verification_status":"representative","non_obvious":false,"__flag":"TRIPWIRE — approved; adjacent to cannot_hold_residence_permits_in_two_eu_states"}
]
```

**On `registration_process`:** the brief lists it as a candidate. It exists only in
`public.requirement_entities`, where it is **"Vehicle Registration Process & Deadline
(Ireland)"** with **0 facts** — a vehicle-import topic, not immigration. It has **no
`requirement_items` row** and is **not** a merge or collision candidate here. Ignore it.

**Naming conventions in play** — live titles use two families: `"… – …"` (en-dash U+2013, e.g.
*Immigration permission – Stamp 1 / IRP registration*) and `"… — …"` (em-dash U+2014, e.g.
*IRP card — first-time registration timeline and fee*, *Ireland — spouse stamp 1g right to
work*). Since **title is the upsert key**, a title differing by one dash character is a
*different row*. Pick titles colliding with none of the 6 above, and keep the dash you choose
exact.

**Wider collision surface:** IRELAND holds **45** `requirement_items` rows in total (42 at the
start of this bridge test + 3 added by the `immigration_work_authorization` topic). The 6 above
are the concept-adjacent ones; your titles must not collide with **any** IRELAND row.

---

## 5. RULES

1. **Append-only.** Generate `INSERT`s only. **No `UPDATE`, no `DELETE`, no `UPSERT`/
   `ON CONFLICT DO UPDATE`.** If a collision is possible, do *not* emit that row and say so in
   the prediction.
2. **Dedup on `(country_code, purpose, title)`** — the natural key. All live rows are
   `('IRELAND','employment', …)`, so **your titles must differ from every existing one**.
3. **Honor the pillar** per §2 ⇒ **`RESIDENCE`** on all 7 rows. Never write a pillar outside
   `CANONICAL_PILLARS`.
4. **Promote to PENDING.** `review_status='pending'` **explicitly on every row** — the column
   defaults to `'approved'`.
5. **MUST NOT touch or overwrite any existing row.** Off-limits ids:
   - `572b697b-c6cd-5c14-b1d6-b80906743e0b` — *IRP card — first-time registration timeline and
     fee* — **approved + `corpus_grounded`**, the strongest row in this concept.
   - `c07c4900-7792-561c-b07e-b2464c2f913b` — *Immigration permission – Stamp 1 / IRP registration*
   - `c9402361-26ff-594f-adfc-205202e08e9b` — *Immigration permission – CSEP to Stamp 4*
   - `a114fd40-f8d1-5562-aba4-d0e83e127670` — *Ireland — spouse stamp 1g right to work*
   - `0c97ae08-d8a8-58c1-a607-a70a7edb0626` — *Ireland outside the Schengen area*
   - `acdddd42-8404-56f4-968b-cdaf76e071c7` — *IRP / ISD Immigration Registration (non-EEA)* —
     **pending, and known-wrong; its correction is D4, a separate step. Do not fix it here.**
6. **Exactly 7 rows.** Only `__promote: true`. The 2 DUP and 2 HELD-FOR-D4 facts produce no row.
7. **Nothing served.** `verification_status` must never be `expert_verified`; use
   `representative`.
8. **No invention.** Every value traces to §3 or a §2 rule. A field the snapshot does not carry
   stays NULL (including `timing` — no fact here carries one). Do not invent citations,
   numbers or confidence scores. **Preserve the conditional hedge** on
   `leaving_state_before_registration_needs_new_entry_visa`.
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
follow the live corpus dash conventions in §4, collide with no existing IRELAND row, and not
merely restate the `fact_key`.

### OUTPUT CONTRACT

Cursor must return EXACTLY these three delimited sections and nothing else:

```
===ARTIFACT_SQL===
-- INSERT statement(s) ONLY. Append-only: no UPDATE, no DELETE, no BEGIN/COMMIT/ROLLBACK (the applier wraps it in a dry-run transaction). End each INSERT with:
--   RETURNING country_code, purpose, title, pillar, review_status
INSERT INTO public.requirement_items (…columns…) VALUES (…) RETURNING country_code, purpose, title, pillar, review_status;

===PREDICTION_JSON===
{
  "expected_inserts": [ {"country_code":"IRELAND","purpose":"…","title":"…","pillar":"…","review_status":"pending"}  /* exactly 7 */ ],
  "expected_insert_count": 7,
  "must_not_touch_ids": [ "<reviewed row ids from LIVE STATE>" ],
  "dedup_key": ["country_code","purpose","title"],
  "assumptions": "…"
}

===VERIFICATION_SQL===
-- A SELECT the applier runs AFTER a real apply to confirm the 7 rows exist as predicted, all review_status='pending', and no reviewed row changed.
SELECT …;
```

**Filling it in for this bundle:**
- `expected_inserts` — exactly **7** entries, one per `__promote: true` fact; all
  `country_code:"IRELAND"`, `purpose:"employment"`, `pillar:"RESIDENCE"`,
  `review_status:"pending"`.
- `must_not_touch_ids` — the six ids in §5.5, `acdddd42-8404-56f4-968b-cdaf76e071c7` included.
- `assumptions` — anything the snapshot did not settle (title wording above all). If a rule in
  §5 makes the task impossible, say so here rather than emitting SQL that breaks it.

---

## ⚠️ SEPARATE ITEM — D4 correction (NOT part of this bundle)

**Do not fold this into the append-only artifact. It is an `UPDATE`, and this bundle forbids
`UPDATE`.** Recorded here so it is not lost, and handled as its own step at apply time.

**Row:** `acdddd42-8404-56f4-968b-cdaf76e071c7` — *IRP / ISD Immigration Registration (non-EEA
nationals)* · `review_status='pending'` · `verification_status='representative'`

**Defect — the 90-day clock is anchored to the wrong event, in two places:**

| field | current live value (wrong) | correct rule |
|---|---|---|
| `timing` | `"within 90 days of ISD granting permission"` | **within 90 days of arrival** (the landing stamp at the port of entry) |
| `description` | *"Once ISD grants a permission to stay in Ireland …, the person must register that permission with Irish immigration authorities within 90 days."* | same correction — the trigger is the landing stamp, not the grant |

**The `description` matters as much as `timing`.** An earlier reading of this defect treated it
as a `timing`-only fix; the description carries the identical wrong trigger and would still be
served.

**Evidence for the correct rule** (ISD, `irishimmigration.ie`, staged as
`landing_stamp_90_day_registration_deadline`):

> "When you first arrive in Ireland and are permitted to enter, your passport will be endorsed
> with a landing stamp. The landing stamp will instruct that you register with Immigration
> Service Delivery within 90 days."

and, as `booked_appointment_within_90_days_preserves_lawful_presence`:

> "Once you have successfully booked an appointment within the 90 days **of arrival**, this
> will be sufficient to remain in the state until the date of your appointment."

**Why it matters:** the two events can differ by weeks. A permit granted before travel makes
"90 days from grant" *earlier* than the true deadline in some cases and *later* in others —
and "later" means an employee believing they are compliant while out of permission.

**Mitigating:** the row is `pending`, so `requirements_builder` (approved-only) is **not
serving it today**. This is a correct-before-approval item, not a live-defect hotfix.

**Suggested handling at apply time:** correct `timing` and the offending sentence in
`description` on `acdddd42` in the same session as this promotion, then promote the two
HELD-FOR-D4 facts if a reviewer wants them as standalone rows — or leave them held, since the
corrected `acdddd42` would then state the rule. That is a reviewer's call, not the generator's.

---

*Bundle built read-only: SELECTs against `nsvefcvpvwwwhuqyuqmp` plus file reads. No writes, no
promotion, no secrets.*
