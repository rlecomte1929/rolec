# ReloPass — Andrea's End-to-End Assessment · Madrid → Dublin (ES→IE)

**Date:** 2026-08-20 · **Corridor:** ES→IE · **Persona:** Andrea — Venezuelan national, legally
resident in Spain, moving to Google Dublin, family of 4 (third-country / Critical Skills path)
**Method:** live production DB (Supabase `nsvefcvpvwwwhuqyuqmp`) + API re-run of the T18 runner
against `api.relopass.com` (commit `1d8d8435`) + Notion AI Work Queue reconciliation.
**Predecessor:** `ReloPass_T18_Madrid-Dublin_Report_2026-08-13.md` (scored 41%, RED).

---

## Verdict

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ES→IE  Madrid → Dublin  •  20 Aug 2026  •  ~52%  •  AMBER (was 41% RED)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 The corridor is no longer selling a move it cannot service. The three most
 dangerous T18 findings are fixed and live. What still fails for Andrea is
 mostly BUILT and sitting in unmerged PRs — the bottleneck is review+merge,
 not engineering.
```

**Can Andrea get the go-ahead within a week?** Yes, on this path: **merge the 5 already-built PRs**
(lights up settle-in, neighbourhoods, geocoding, advisors, movers, HR readiness), **build one thing**
(AIQ-1867 — her journey), and **load one research batch** (AIQ-1993→2027 — her entry visa + family).
Her vendors are already done.

API E2E, both personas, 54 checks: **28 PASS / 2 PARTIAL / 24 FAIL** (T18 was 22 / 32). Persona B
(third-country) is Andrea's legal branch.

---

## Acting as Andrea, screen by screen

**Intake → profile.** Her real case (`andrea.peinado10@gmail.com`, case `6ecadafe`, company
"Google") is **paid** (`access_tier=roadmap`) but `intake_step=0` and her `profile_json` still
carries a hardcoded **family-of-four "budgetMonthlySGD"** seed — a Singapore/Oslo default that never
got overwritten. If she logs in today, her profile is wrong and empty. She needs to complete intake
(or have it pre-filled) and the seed cleared.

**Immigration.** This is now genuinely good where it works. `/employee/cases/{id}/immigration`
correctly branches on nationality: an EU mover is told *"You do not need a work permit or visa for
this move… this is the complete answer, not a missing one,"* and Andrea (third-country) is told
*"Your immigration file has not been opened yet — your HR team opens the file."* The **"EU Blue Card"**
that T18 flagged as *wrong* for Ireland is **gone** (`visa_type: null`). But the message is also a
**dead end**: no ES→IE rows exist in the corridor immigration engine, so HR has nothing to open the
file with — `available-forms: []`, `milestones: []`, and there is no entry-visa or family coverage
for her Venezuelan branch at all.

**Her requirements checklist.** Real content now appears: **14 approved Ireland requirements** serve
to third-country nationals (Critical Skills Permit €40,904, General Permit €36,605, PPSN, IRP/Stamp 1,
the Schengen-travel caveat, pets, rentals) — a genuine fix of T18's empty corridor. The EU branch
still gets only 1. **Six high-value "non-obvious" items (emergency-tax trap, 183-day residency, PRSI,
split-year, RPN) sit `review_status='pending'` and are therefore invisible** — an admin approval
turns them on.

**Her journey / roadmap.** Still the weakest screen. `/relocation-plans/{id}/view` returns
`phases: []`, `total_tasks: 0`, `empty_state_reason: "No action required right now"`,
`roadmap_released: true` — **identical to T18's F5**. Her case carries 16 milestones, but they are the
**generic** template (`task_visa_docs_prep`, `task_visa_submit`…), not the Ireland journey. Telling a
Venezuelan with a permit-required move that there is "no action required" is still a false statement.

**Vendors / marketplace.** The big turnaround. Her employer "Google" has **29 real Irish suppliers
curated**: AIB, Bank of Ireland, Permanent TSB, Revolut (banks); Savills, Lisney, Sherry FitzGerald,
DNG (housing); Fragomen Ireland, Matheson, Mason Hayes & Curran (legal/immigration); PwC, KPMG,
Deloitte, BDO, Grant Thornton Ireland (tax); Nord Anglia, St Andrew's, International School of Dublin
(schools); Santa Fe Dublin, Crown Relocations Dublin, Cronin (movers). T18's Norwegian banks are gone.
Caveat: this is **per-company** — a fresh/uncurated company still gets wrong defaults (the API returned
a *Munich* school for a Dublin move), and the raw marketplace endpoint is still not corridor-filtered.

**Settle-in, neighbourhoods, advisors.** Live, these are still broken — country resource pack empty,
housing/schools recommendations empty, geocoding disabled, and advisor matching still returns two
advisors whose specialisms are "EU Blue Card" / "schengen long-stay" (neither exists for Ireland) with
`example.com` contact URLs. **But all of these are already built** — see the merge queue below.

---

## HR validation state — what has and hasn't been done for her

The quality of Andrea's experience is gated by three things HR/admin control, and they are **mixed**:

| HR/admin gate | State for Andrea | Evidence |
|---|---|---|
| **Vendor curation** (`company_vendor_selections`) | ✅ Done — 29 Irish suppliers across all 6 categories | company "Google" `46fc3db0` |
| **Roadmap release** (`roadmap_review_status.released_to_user`) | ✅ Released | `6ecadafe` released=true |
| **Requirement approval** (`review_status`) | ⚠️ 14 approved, **6 non-obvious tax items still pending** | see checklist above |
| **Immigration file opened** (`immigration_cases`) | ❌ Not opened — and no ES→IE content exists to open it with | 0 rows for any *→IE corridor |
| **Her intake / profile** | ❌ `intake_step=0`, family-of-4 SGD seed profile | case `6ecadafe` |

So HR has done the vendor work and released the roadmap, but the **immigration file and her own
profile are the two things still standing between her and a coherent experience** — and the immigration
side needs platform content (AIQ-1993→2027), not just an HR click.

---

## Fixed & live vs still-broken (reconciled against the Notion queue)

**Confirmed fixed and deployed** (verified live 2026-08-20):

- **AIQ-1878** — the "EU Blue Card for Ireland" default is gone (`visa_type: null`).
- **AIQ-1831** — ES→IE landed in `requirement_items`; 14 approved rows serve to third-country nationals.
- **AIQ-1745** — the corridor now propagates; requirements branch EU_EEA vs THIRD_COUNTRY.
- **AIQ-1880** — nationality branching fires (14 THIRD_COUNTRY vs 1 EU_EEA); the "never persists" premise is refuted. *(Reconciled to Done this session.)*
- **AIQ-1870 / 1846 / 1844** — Irish vendors curated and reaching the employee for the curated company.

**Still broken live — but already built and awaiting merge.** This is the key finding: the tickets sit
in "Human Review," my live test shows the behaviour still broken, and the reason is simply that the PRs
have not merged to `main` (so nothing deployed).

| Merge order | Ticket | Unlocks for Andrea | PR |
|---|---|---|---|
| 1 | AIQ-1879 | `relocationBasics` stops 500ing (corridor write endpoint) | #1925 |
| 2 | AIQ-1746 | Dublin settle-in pack — real content, false residence-registration line removed | #1913 |
| 3 | AIQ-1882 | Dublin neighbourhoods + geocoding on (housing / schools / commute) | #1915 |
| 4 | AIQ-1868 | HR "no verified IE readiness template" flag cleared | #1920 |
| 5 | AIQ-1883 + AIQ-1872 | Ireland-capable advisors; Dublin movers — no more Singapore / example.com | #1927 |

**Still broken and genuinely unbuilt** (the only real engineering left for Andrea):

- **AIQ-1867** — her journey is generic; wire the CSEP_2026 step-graph (already authored in
  `corridors/ES_IE/pathways/CSEP_2026/v1.yaml`) into the roadmap generator so it shows Critical Skills
  Permit → long-stay D visa → IRP/Stamp 1 (Burgh Quay, 90 days) → PPSN → Revenue RPN, not 16 boilerplate
  steps. *(Execution prompt authored + assigned to Claude Code this session.)*
- **AIQ-1993 → AIQ-2027** — Venezuela→Ireland has no entry-visa path and no family/dependant coverage.
  *(Research delivered this session — see below; load is AIQ-2027.)*

---

## The go-live plan (ROI-ranked)

**Wave 1 — merge (owner: Romain).** The five PRs above. Fastest lever; each is verified-needed and
verified-not-deployed. Order them 1→5 as listed. Note #1927 closes two tickets.
Plus the **non-PR quick win**: approve the 6 pending Ireland `requirement_items` to switch on the
emergency-tax / residency / PRSI content (human gate — do not auto-approve).

**Wave 2 — build (delegated).**
- AIQ-1867 (Claude Code) — the roadmap. Highest single-screen ROI. Prompt ready.
- AIQ-1993 → AIQ-2027 — her immigration reality. Research done; AIQ-2027 (Claude Code) loads it as
  candidates, a reviewer confirms quotes verbatim, and counsel clears 4 flagged rows before approval.

**Wave 3 — platform (not blocking Andrea-VE).** AIQ-1994→2028 (EU/EEA free-mover branch),
AIQ-1871 (marketplace allowlist for uncurated companies), AIQ-1884 (relocation-agent seat).

Tracking page: **Andrea (ES→IE) Go-Live Plan — 2026-08-20** (Notion, under AI Work Queue).

---

## What was done this session

1. **Notion staged & reconciled** — created the go-live tracker; corrected AIQ-1880 to Done (premise
   refuted, branching verified live); mapped every corridor ticket to live reality; identified the
   5-PR merge queue as the fast path.
2. **AIQ-1867 prepared for Claude Code** — full self-contained execution prompt authored (CSEP
   step-graph → roadmap generator), constraints (serving/LLM isolation, HR release gate,
   both-router registration), validation + test command, assigned to Claude Code.
3. **AIQ-1993 research delivered** — 9 sourced VE→IE entry-visa + family/dependant candidate facts
   (`docs/imports/ve-ie-entry-family-2026-08-20/`, sha256 `2186f59a…`), all `review_status='pending'`,
   6 non-obvious, 4 flagged for counsel; AIQ-2027 pointed at the artifact.
4. **This assessment.**

---

## Evidence appendix

- **API E2E** (`scripts/madrid_dublin_runner.mjs`, 2026-08-20): 28 PASS / 2 PARTIAL / 24 FAIL. Fixed
  vs T18: PUB corridor-requirements (0→14 third-country), immigration view (404→correct branch),
  visa_type (blue_card→null). Still failing: PLAN (0 phases), forms, milestones, recommendations,
  geocode, resources, advisors — the built-but-unmerged set.
- **DB (live):** Ireland `requirement_items` = 14 approved + 6 pending; `immigration_requirements`
  = 135 rows across DE/PT/US/UK/FR corridors with **no *→IE**; `immigration_milestones` = 0;
  Andrea `6ecadafe` roadmap-paid, released, 16 generic milestones, seed profile.
- **Sources (VE→IE):** Citizens Information (visa requirements; employment permits & family members);
  Immigration Service Delivery (employment visa; family dependents); DETE (Critical Skills Permit).

*Nothing was written to production data or code. All changes were Notion staging, one repo research
artifact under `docs/imports/`, and delivered files.*
