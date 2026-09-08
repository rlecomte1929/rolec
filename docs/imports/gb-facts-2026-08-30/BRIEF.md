# Otto brief — UK destination requirement facts (the 4 remaining gaps)

**Corridor/destination:** United Kingdom (GB) as a **destination**. Audience: a relocating
professional (and family). The UK is **not** in the EEA, so every foreign national classifies as
**third country** for our engine — post-Brexit free movement has ended. Scope every fact
`applies_to.nationality = "non-EEA"`.

**This batch completes the UK.** 12 substantive facts + a template skeleton already landed (pending).
Do **not** re-research immigration/visa/NI/tax-residence/GP topics — they are done. Produce ONLY the
four settling-in topics below, which are currently missing.

## The four topics (one entity each; 1–4 facts per topic)

1. **Council tax** (`entity_topic_key: "council_tax"`, pillar `HOUSING`, status `professional`)
   - Registering with the local council on arrival; who is liable; single-person discount;
     full-time-student exemption. Source: **gov.uk/council-tax** and its sub-pages.
2. **State-school admissions** (`entity_topic_key: "state_school_admissions"`, pillar `HOUSING`,
   status `family`)
   - How to apply (through the local council, not the school); state schools are free; in-year
     admission for children arriving mid-year; the national offer-day timeline. Source:
     **gov.uk/schools-admissions**, **gov.uk/apply-for-primary-school-place**,
     **gov.uk/schools-admission-appeals**.
3. **Driving-licence exchange** (`entity_topic_key: "driving_licence_exchange"`, pillar `IDENTITY`,
   status `professional`)
   - Driving on a non-GB licence (the 12-month rule); which countries' licences can be exchanged
     (designated countries) vs. must re-test; EU/EEA licence rules. Source:
     **gov.uk/driving-nongb-licence**, **gov.uk/exchange-foreign-driving-licence**.
4. **Opening a UK bank account** (`entity_topic_key: "bank_account_opening"`, pillar `IDENTITY`,
   status `professional`)
   - What proof of identity/address a new arrival needs; the "no UK address / no credit history"
     trap; that a bank account is not a legal requirement but is needed for payroll. **If no
     official gov.uk page states a verbatim rule, put it in rejects.ndjson with a reason** — do not
     invent. (This one may not have an official verbatim source; that is an acceptable outcome.)

## The record shape — one JSON object per NDJSON line, fields FLAT (not nested)

```
{
  "destination_country": "GB",
  "entity_topic_key": "council_tax",
  "entity_title": "Council tax registration",
  "fact_key": "GB:council_tax:register_with_council",       // globally unique, STABLE
  "fact_text": "New residents must tell their local council to set up a council tax account.",
  "source_url": "https://www.gov.uk/council-tax",            // official gov.uk host, must resolve 200
  "evidence_quote": "…verbatim substring from the page…",    // char-for-char; V3 checks after landing
  "fact_type": "eligibility",                                 // eligibility|document|deadline|fee|where_to_apply|other — NEVER "step"
  "confidence": "high",
  "applies_to": {
    "nationality": "non-EEA",                                 // ⛔ REQUIRED, never null
    "status": "professional",                                 // or "family" for schools
    "pillar": "HOUSING",
    "non_obvious": true,
    "non_obvious_note": "Commonly believed … Actually … Action required …",
    "needs_lawyer_review": false,
    "quote_verbatim_confirmed": false,
    "corridor": "GB"
  }
}
```

## The rules that decide whether a fact lands (identical to the andrea-denis contract)

1. `applies_to.nationality = "non-EEA"` and `applies_to.status` present on EVERY fact.
2. `evidence_quote` is a VERBATIM substring of the page at `source_url`. Cannot find it → reject.
3. `source_url` is an official **gov.uk** host that returns 200. A blog/aggregator is a reject.
4. `fact_type` is never `"step"`.
5. **Never invent** a source, number, fee, deadline, or quote. A fact you cannot source is a reject,
   not a guess.

## Deliver THREE files to GCS (give me untruncated URLs)

- `facts.ndjson` — the records above, one per line
- `rejects.ndjson` — every fact examined and dropped, each with a `reject_reason`
- `manifest.json` — per-file GCS URL, record_count, sha256, and your prediction of how many pass all
  four rules, plus which topic you were least sure of. `batch_id: "gb-facts-2026-08-30"`,
  `destination_country_code: "GB"`, `target_country_code: "UNITED KINGDOM"`,
  `nationality_class: "THIRD_COUNTRY"`, `review_status_all: "pending"`,
  `verification_status_all: "representative"`.
