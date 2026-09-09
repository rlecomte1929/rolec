# AIQ-2192 — composed Ireland 20-week lead time (premise check)

**Date:** 2026-09-09  
**Verdict:** premise **refuted**. No new `requirement_items` row was loaded. A parallel
session had already committed a pending 12+8≈20 candidate on this branch; that commit
was reverted because it would have published a combined figure the live catalog already
argues against.

## What the task claimed

The 2026-08-30 brief: two approved Ireland / `THIRD_COUNTRY` halves exist, and **nothing
states the composition**. Sequential permit (12 weeks) then visa (~8 weeks) should be
authored as **approximately 20 weeks** before the start date, pending review.

## What production held on 2026-09-09 (read-only)

Queried `public.requirement_items` where `country_code = 'IRELAND'` (253 rows). The two
source rows exist and are **approved**. A third approved row already states the sequence.

| id | title | `review_status` | `reviewed_by` |
|---|---|---|---|
| `94837181-c418-5a94-8702-a3657684b7cd` | Ireland — employment permit 12-week application lead time | `approved` | AIQ-2094 session note (representative, not counsel) |
| `4c119775-b9c9-5bc0-8bbe-1c162b567cb0` | Ireland — entry visa after permit timing | `approved` | `4e275218-b362-419e-9120-17e5f039a8da` |
| `598eb3c3-8d82-5521-992f-fabd767ca0d0` | Ireland — the 12-week permit minimum does not cover the visa leg | `approved` | `4e275218-b362-419e-9120-17e5f039a8da` |

Those two source rows were **not** updated by this ticket.

### The composition row already served

`598eb3c3-…` is `THIRD_COUNTRY`, cites **both** DETE CSEP and ISD employment-visa URLs, and
says the DETE 12-week rule and the entry-visa decision are **SEQUENTIAL, not parallel**.
It works backwards from the intended start date. It does **not** add 12+8 into a 20-week
statutory-looking total. Its actual_reality is the opposite of that sum: the 12 weeks is
an intake minimum **measured to the start date**, so lodging at T-12 leaves the ~8-week
visa with no room after grant.

A search for `20 week` / `20-week` on Ireland descriptions/titles/timing returned only
an unrelated RTB tenant-rights row (`ie_tenant_rights_rtb_dispute_routes`).

## Why 12+8 ≈ 20 was not authored

The task forbids inventing numbers. Adding “12 weeks before start” to “~8 weeks after
grant” treats the lodgement rule as processing time that sits *before* the visa. The
approved composition row already records that the 12 weeks is **to the start date**, so
the visa wait is **inside** that window after grant — not a second 8 weeks stacked on
top. Shipping “approximately 20 weeks” would contradict a live approved fact and invent
a combined figure neither DETE nor ISD states.

The remaining product gap (if any) is serving/roadmap **display** of `598eb3c3-…`, not a
missing catalog sentence. That is AIQ-2160’s lane (validate the claim, not just its
presence), not a new pending row.

## What was not done

- No `--apply` / `--promote` against production.
- No edit to the two source rows.
- The false candidate under `docs/imports/ie-composed-lead-time-2026-09-09/` was reverted
  with the mapping/test support that existed only to load it.
