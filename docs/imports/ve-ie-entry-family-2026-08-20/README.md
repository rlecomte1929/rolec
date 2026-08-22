# VE→IE entry-visa + family/dependant facts — candidate batch `ve-ie-entry-family-2026-08-20`

**AIQ-1993 research deliverable.** Authored by Claude (Cowork) on 2026-08-20 for Andrea's real
test case: a **Venezuelan national, legally resident in Spain, moving Madrid → Dublin for Google,
with a Macedonian spouse and no children**. This is the third-country employment-permit path,
not EU free movement.

> **Household corrected 2026-08-22.** This batch was authored against "family of 4". Andrea has
> no children; the household is two. The immigration facts are unaffected — the CSEP/GEP
> reunification rule is nationality- and size-neutral — but a served requirement must not
> describe one customer's household, so the wording moved off the persona.

## What this closes

The 14 already-approved `IRELAND` / `THIRD_COUNTRY` `requirement_items` cover CSEP/GEP salary
floors, PPSN, IRP registration, the Schengen-travel caveat, pets and rentals — but they carry
**no entry-visa path and no family/dependant coverage**. That is exactly the AIQ-1993 gap. These
9 facts are **additive** and do not modify any existing row.

## Contents

| file | purpose |
|---|---|
| `ve_ie_entry_family_requirement_facts.ndjson` | 9 candidate facts, one JSON object per line |
| `manifest.json` | count, sha256, corridor/nationality scope, load contract |

**sha256** (ndjson): `2186f59ae0cb06bb7403ef4bed2f291ff1ad4313bc270fb0051883f7e63a46d6`
**counts:** 9 facts · 6 non-obvious · 4 flagged `needs_lawyer_review`

## The facts (topic_key → what it establishes)

1. `entry_d_visa_required_venezuela` — Venezuela is visa-required; a long-stay 'D' employment visa is needed **before** travel *(non-obvious)*
2. `entry_d_visa_long_stay_over_90_days` — >3-month employment uses the long-stay 'D' visa
3. `entry_visa_after_permit_timing` — visa is applied for only **after** the permit is granted; ~8-week decision; apply up to 3 months pre-travel *(non-obvious)*
4. `entry_visa_apply_from_country_of_residence` — applied from Spain (country of legal residence), not Venezuela
5. `spanish_residence_does_not_grant_irish_entry` — **the load-bearing trap**: a Spanish TIE / EU long-term residence gives no Irish entry right (Ireland is non-Schengen) *(non-obvious, lawyer-review)*
6. `csep_immediate_family_reunification` — CSEP = immediate family reunification (GEP = 12-month wait) *(non-obvious, lawyer-review)*
7. `spouse_stamp_1g_right_to_work` — CSEP spouse gets Stamp 1G → works with no separate permit *(non-obvious, lawyer-review)*
8. `dependant_join_family_d_visa_required` — visa-required dependants need an Irish 'D' Join Family visa before travel *(non-obvious, lawyer-review)*
9. `csep_no_labour_market_needs_test_thresholds` — no LMNT; €40,904 / €36,848 / €68,911 thresholds; the holder can then apply directly for a Stamp 4
   <br>*(corrected 2026-08-21: this line read "Stamp 4 after 2 years". The artifact's `fact_text` says only "After the permit, the holder can apply directly for a Stamp 4" — no interval appears anywhere in the delivered data, so the two years were invented by this summary. The fact itself was never wrong.)*

## Sources (all official publishers)

- Citizens Information — Visa requirements for entering Ireland
- Immigration Service Delivery (irishimmigration.ie) — Employment visa; Family dependents
- Citizens Information — Employment permits and family members (spousal work permit scheme)
- DETE (enterprise.gov.ie) — Critical Skills Employment Permit

## Load contract (for AIQ-2027, Claude Code)

- **Candidates only.** Every row is `review_status='pending'`, `verification_status='representative'`. Nothing is `approved` / `verified` / `lawyer_verified` / `live`.
- Target `public.requirement_items` (varchar `id` carries `fact_uid` verbatim), `country_code='IRELAND'`, `applies_to_nationality_classes_json=["THIRD_COUNTRY"]`.
- Idempotent on `fact_uid`; `ON CONFLICT` must **not** touch `review_status` (never un-approve a reviewer's decision).
- `quote_verbatim_confirmed: false` on every row — a reviewer must confirm each `evidence_quote` verbatim against its source before approval. The 4 `needs_lawyer_review` rows (5,6,7,8) need counsel before they can be approved at all.
- Do **not** apply to production from a CLI/MCP. Commit the migration file; production apply is out-of-band per CLAUDE.md migration discipline.
