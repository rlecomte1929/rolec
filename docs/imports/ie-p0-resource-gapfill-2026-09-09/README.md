# IE-P0 re-source gap-fill — 2026-09-09

Three **candidate** `requirement_items` for destination **Ireland (IE-P0)**, filling gaps the
2026-08-31 IE-P0 sweep left open. Each is sourced to a **verbatim quote from an official Irish
source**. Candidates only — nothing here is approved or served.

## Why this batch exists (and why it is small)

The Audos "Ireland Relocation Corridor Research" thread was meant to re-source ~39 `-resrc`
worklist gaps (incl. ~15 PSC/PPSN items that had 403'd, + 5 named timeline gaps). That thread
would not dispatch (it went idle twice without producing a task, and the workspace then dropped to
a re-auth wall), so this batch was produced **directly** instead — researching the well-defined,
officially-sourceable gaps against the primary sources.

Checked against the **145 `ie_` facts already in prod**, most of the original gaps were **already
closed** by the 08-31 gap-fill (that is why 145 exist). What remained genuinely missing *and*
quotable from an official source is the three facts below. The rest of the residual `-resrc` set
(appointment lead times, city/seasonal appointment capacity, some processing-time figures) is **not
quotable from an official source** and is deliberately **left unsourced** rather than invented — it
stays a research gap for a future pass with live access to the `-resrc` files.

## Records (all `verification_status=representative`, `review_status=pending`)

| id | pillar | source | verbatim evidence_quote |
|---|---|---|---|
| `ie_timeline_emergency_tax_refund_via_payroll` | TIMELINE | [revenue.ie — How to get a refund of Emergency Tax](https://www.revenue.ie/en/jobs-and-pensions/emergency-tax/get-refund-emergency-tax.aspx) | "Your employer will refund any Income Tax and Universal Social Charge (USC) that you have overpaid on your next pay day." |
| `ie_timeline_myaccount_password_by_post` | TIMELINE | [revenue.ie — Registering for myAccount](https://www.revenue.ie/en/online-services/services/myaccount/help-guides/registering.aspx) | "Where it is not possible to verify this information immediately, the temporary password will be issued to you by post." |
| `ie_medical_card_ordinarily_resident_requirement` | HEALTHCARE | [citizensinformation.ie — Medical cards](https://www.citizensinformation.ie/en/health/medical-cards-and-gp-visit-cards/medical-card/) | "If you are 'ordinarily resident' in Ireland you can apply for a medical card. This means that you are living in Ireland and intend to live here for at least one year." |

Each is **net-new** — no id collision with the 145 existing `ie_` facts (verified against prod
`nsvefcvpvwwwhuqyuqmp`), and each fills a gap the existing facts do not cover (existing emergency-tax
facts cover only *onset*; existing myAccount facts cover only *prerequisites*; existing medical-card
facts cover only *income thresholds / coverage*, not the residency gate).

## Governance / how to land

- `src/ie-p0-resource-gapfill.ndjson` is the source of truth (sha256 in `manifest.json`).
- `gen_load.py` regenerates the migration from it — do not hand-edit the `.sql`.
- Migration `supabase/migrations/20261133000000_ie_p0_resource_gapfill_candidates.sql` inserts the
  3 rows as `review_status='pending'` with `ON CONFLICT (id) DO NOTHING` (idempotent; never
  overwrites a reviewer's later decision). Timestamp `20261133000000` is above both the repo file
  max (`20261127000000`) and the prod ledger max (`20261132000000`).
- **Apply is operator-run and out-of-band** (this repo has no apply-on-merge); after applying,
  reconcile the ledger with `supabase migration repair --status applied 20261133000000`.
- Facts serve to users only after a human flips `review_status` to `approved`. None are `verified`
  (no counsel sign-off).

## Verify

```bash
cd docs/imports/ie-p0-resource-gapfill-2026-09-09
shasum -a 256 -c <<< "a0062466ff5350f5fca53620a5e8da72be778b31644803ca75e3730ebe7fe7f7  src/ie-p0-resource-gapfill.ndjson"
python3 gen_load.py   # regenerates the migration; git diff should be empty
```
