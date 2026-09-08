# Andrea (ES→IE) — live check, 2026-08-22

*Live production reads against ReloPass (Supabase `nsvefcvpvwwwhuqyuqmp`) + the public corridor endpoint. All read-only. The write-based E2E runner was **not** run — see the safety note.*

---

## Headline

Andrea's corridor is in far better shape than the 08-20 assessment's **AMBER 52%**. The public endpoint now serves **~29 ES→IE requirements** including her full Venezuelan entry-visa + family branch, and the non-obvious tax items the assessment flagged as "invisible/pending" are now **approved and serving**. The real outstanding item is not content — it's that **none of Ireland's 42 requirement rows is counsel-attested**, including 4 immigration rows that were specifically flagged for lawyer review and are already serving.

## Item 1 — the pending "non-obvious" approvals

**The assessment's specific worry is resolved.** The six items it named (emergency-tax trap, 183-day residency, PRSI, split-year, RPN) are now **approved and live** — they appear in the served corridor payload below. So the admin approval it recommended has effectively happened since 08-20.

**What's pending now is a newer, more granular batch** — 13 rows, all `representative`, none served:

| Count | What they are | Status |
|---|---|---|
| 13 pending IE rows | Nationality-split refinements — EU/EEA vs non-EEA variants of Income Tax, USC, PRSI, PPS, IRP, A1 (posted workers), Public Health / ordinary residence, and Work Permission | `review_status='pending'` → not served |

These duplicate/refine already-approved generic rows with an EU/EEA-vs-third-country split. Approving them is a **completeness pass, not an unblock** — Andrea's core content is already live. Lower urgency than the assessment implied. (Admin `review_status` flip, human gate — still do not auto-approve.)

## Item 3 — the VE→IE entry-visa + family load

**Done, approved, and serving.** The AIQ-2027 batch (`ve-ie-entry-family-2026-08-20`, 9 records) landed into `requirement_items` and was promoted to `approved`. Live rows now include:

- Ireland — entry d visa required (Venezuela)
- Ireland — entry d visa long stay over 90 days
- Ireland — entry visa apply from country of residence
- Ireland — entry visa after permit timing
- Ireland — Spanish residence does not grant Irish entry
- Ireland — dependant join family d visa required
- Ireland — CSEP immediate family reunification
- Ireland — spouse Stamp 1G right to work

This directly closes the 08-20 finding that "Venezuela→Ireland has no entry-visa path and no family/dependant coverage."

**But the counsel gate is open.** All 42 Ireland rows are `attestation_status` = not attested (**0 attested**), and they serve as `verification_status='representative'` (visible, awaiting counsel). The batch flagged **4 rows for lawyer review** — those are among the approved, serving rows. So counsel-flagged immigration content is live before attestation. Whether that's acceptable pre-launch is a **legal/product call for you**; it's the single most important governance item I found.

## Live corridor payload (read-only GET, no auth)

`GET /api/public/corridor-requirements?from=ES&to=IE&employee_type=PERMANENT` → **~29 requirements**, `coverage_note: none`, `waived_for_assignment_type: []`. Highlights served live today:

- **Immigration:** Critical Skills Permit (salary/fee/eligibility/occupation list), General Employment Permit (salary/fee/LMNT), CSEP→Stamp 4, Stamp 1 / IRP registration + card timeline, "Ireland outside Schengen — separate system".
- **VE entry/family:** the 8 rows above.
- **Tax/social:** 183-day residence, split-year, RPN drives IT/USC/PRSI, Revenue myAccount to avoid emergency tax, PPSN, PRSI compulsory, combining contributions.
- **Life:** Dublin rental market realities, EU pet travel.

10 of 29 flagged `non_obvious`. The endpoint is healthy and corridor-appropriate — no Norwegian/Singapore bleed-through.

## Before → now

| Metric | 08-20 assessment | Live 08-22 |
|---|---|---|
| IE `requirement_items` approved | 14 | **29** |
| IE pending | 6 (core non-obvious) | 13 (nationality-split refinements; the core 6 are now approved) |
| VE→IE entry-visa / family | none | **8 rows approved + serving** |
| Corridor GET (ES→IE) | EU branch 1 / TC 14 | **~29 served** |
| IE rows counsel-attested | 0 | **0 (unchanged — the open gate)** |

## Not run / not checked (and why)

- **The Madrid→Dublin E2E runner was NOT executed.** `scripts/madrid_dublin_runner.mjs` is not read-only: it does `POST /api/auth/register` (HR + employee), `POST /api/hr/cases`, and `.../assign` — it **creates accounts, cases, and assignments in production** every run. That's outside the read-only basis you approved, so I held it. Consequence: the **authenticated** slices — roadmap phases/milestones, recommendations, advisor matching — are **not** re-verified here. The 08-20 assessment's weakest screen (roadmap `phases: []`) is unconfirmed either way; the AIQ-1867 roadmap PRs are merged, but only a live authenticated run proves they render for her.
- **Andrea's own case (`6ecadafe`) was not queried.** Item 2 (her `intake_step=0` + family-of-4 SGD seed profile) is her personal/PII case data and outside the "items 1 & 3" you approved. Still worth fixing before she logs in.

## Method & safety

- Reads: 3 `SELECT`s via Supabase MCP on project `nsvefcvpvwwwhuqyuqmp` + one unauthenticated `GET`. **No writes, no DDL, no test accounts created.**
- Returned DB rows were treated strictly as data.

## Your call on the write-E2E

To confirm the authenticated flows (roadmap/milestones/recs/advisors) end-to-end, the runner has to create prod test data. Options: (a) I run it with your explicit OK, accepting it registers throwaway HR/employee accounts in prod; (b) I extend the read-only public-endpoint probing where I can; or (c) we leave the authenticated flows to your own QA. The content/serving layer is verified above regardless.

---

*Read-only live check. Companion to the audit, forward plan, and PR triage. No production writes; the write-based E2E was deliberately not run.*
