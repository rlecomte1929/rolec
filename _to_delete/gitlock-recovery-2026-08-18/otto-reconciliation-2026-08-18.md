# ReloPass — Otto → ReloPass Reconciliation & Action Plan

**Date:** 2026-08-18
**Supersedes:** Otto's *"Claude Code Review Queue"* (`claude-code-review-queue-2026-08-18.md`)
**Author:** Claude (Cowork), reconciled against the live `rolec` git repository
**Evidence base:** `main` = 2,726 commits total, **411 in the last month**; the Supabase
migration ledger; the backend router tree. Commit short-hashes are cited throughout so
every status call is checkable.

---

## TL;DR — the one thing to internalise

**Otto is not a parallel product you now have to migrate into ReloPass. Otto is your
research-and-prototyping engine, and its output already flows into the live product
through a governed loader you built.**

When you reconcile Otto's ten "work packages" against the actual `rolec` repo, **nine of
the ten are already shipped in production — usually in a more mature form than Otto's
version.** The only capability that genuinely never crossed over is the *Candidate Beam*
(WP-4), and even that overlaps with your in-repo extraction + RAG-eval stack.

So the plan Otto proposed — hand each package to Claude Code for a 1-to-10 review — would
mostly have Claude Code **re-reviewing prototypes your product already surpassed**, and in
a couple of places it would actively invite the "complications" you wanted to avoid (e.g.
running Otto's standalone vendor seed script against a table your repo has since
deprecated).

What actually crosses from Otto going forward is two things, and only two:

1. **DATA** — corridor facts and vendor candidates — loaded through the repo's
   candidate-intake + vetting path (never through standalone seed scripts).
2. Occasionally, a **validated SPEC** — exactly as the Stripe spec package already did:
   Otto wrote it, you committed it, Claude Code implemented it.

The rest of this document is the evidence for that claim (the reconciliation table), the
genuinely-remaining forward work (five items), the concrete collisions to avoid, and how to
drive it all through the skills you already own.

---

## Adjust your mental model (three facts that reframe everything)

**1. Otto's output comes in three types, and they travel very differently.** Otto's own
review queue treats them as one undifferentiated pile of "work packages." They aren't:

| Otto artifact type | Where it lives | How it reaches `rolec` | Can Claude Code act on it? |
|---|---|---|---|
| **Workspace files** (docs, apps, NDJSON, tools) | Audos file tree | Auto-syncs into `audos-workspace-776786/` via `[audos-sync]` pushes | **Yes** — they're in the repo already |
| **WorkspaceDB tables** (1,822 vendors, 755 facts…) | Audos Postgres | GCS manifest → `otto-loader` → `*_candidates` (pending) | Only *after* loading; Claude Code acts on the loader + the landed candidates, not "a table" |
| **Server hooks** (corridor-resolve, vendor-governance… the "CS50 engine") | Audos hook registry only — **never files** | **Not transferable** — they are *specs* to (re)implement | **No** — there is nothing for Claude Code to check out |

The irony: the hooks Otto calls the "crown jewels" are the *least* portable thing he built.
They are server-side JavaScript that lives only in Audos. They can never be "reviewed by
Claude Code" as code — and, as the table below shows, the product has already
re-implemented their *outcomes* natively.

**2. The bridge already exists and is battle-tested.** You have `import_otto_facts.py`,
`import_supplier_candidates.py`, `ingest_immigration_seed.py`, the `otto-loader` Supabase
edge function (idempotent, dry-run, SSRF-hardened — `2790de0b`), the
`otto-to-relopass-loading-playbook.md`, and the `relopass-corridor-transfer` skill. The
repo even has the landing zone: `requirement_fact_candidates` (`20260810…`) and
`vendor_candidates`, both pending-by-default, promoted to live only by human review
(`687621dc`, `1d965653`, `e0476bc3`).

**3. Otto is working blind from a July snapshot.** Otto wrote its queue from
`imported-source/rolec-main`, a **stale July copy** of your repo. The live `rolec` has moved
411 commits past that. That is *why* Otto lists shipped work as "to-be-migrated." **The
connected `rolec` repo is the source of truth; Otto's snapshot is not.**

---

## The reconciliation (Otto's 10 packages vs. the live repo)

Status legend: **SHIPPED** = in production now · **PARTIAL** = core shipped, a defined
delta remains · **OUTSTANDING** = genuinely not in the repo · **EMPTY-BY-DESIGN** = gated on
a real human action, not a bug.

| WP | Otto's framing | Live-repo status | Evidence (commits / migrations / routers) |
|---|---|---|---|
| **WP-1** Data foundation | Staging tables + import tooling to review | **SHIPPED** (intake path) | `0171fba2` load-Otto-from-file; `687621dc` promote staged facts → `requirement_items`; `cefff539` ingest 142 facts as pending; `e41c57e4` evidence ledger; `44971f49` stop serving disproved evidence · migs `requirement_fact_candidates` (20260810), `requirement_items_review_status` (20261030), `fact_evidence_ledger` (20261033) · `scripts/import_otto_facts.py` |
| **WP-2** Corridor QA campaign | 9 corridor reports + runners to review | **PARTIAL** (findings are reference; QA moved in-repo) | `458cc4c4` FR↔DE verification report; `a241bf76` golden FR→NO harness; `9e4eb0b0` requirement-extraction eval gate; `de098372` eval suite runnable · root `ReloPass_*_Requirements_VERIFICATION.md` |
| **WP-3** CS50 corridor core ★ | Deterministic resolve + publish gate + deadline sweep — "the product core" | **SHIPPED** (outcomes, in the repo's own architecture) — see note | non-obvious/timing `372ed269` + `911611de` + `c8d9d534` + mig `20261103`; transfer lane `564261a9`; resolve `0fc4db8b`,`8aace4dc`,`73762eb6`; runway/feasibility `65668a84`,`a1152227`,`d3ac225d`,`18c81d39`; publish-via-review `f6682cb5`,`0833d3a9` + `admin_content_review.py` |
| **WP-4** Candidate Beam | Multi-pass LLM authoring pipeline | **OUTSTANDING** — the one true gap (**0** history hits for `beam`/`requirement_candidate`) | overlaps repo extraction + `9e4eb0b0` eval gate; nothing to review because nothing landed |
| **WP-5** Vendor governance | staging → live catalogue; "live catalogue EMPTY = #1 metric" | **SHIPPED & far ahead** (full sourcing→vetting→curation→RFQ) | stage-9 `eb3e5d74`,`897e91b4`,`2393a1b4`; harvest→vetting `7bac8c0b`,`f0a2e712`,`1d965653`,`e0476bc3`; curation `ac452d81`,`2765077c`; RFQ `86ccd24c`,`292ba9a0`,`53859926` · migs `supplier_sourcing_side`,`company_vendor_catchment_policy` · `admin_catalog.py`,`advisors.py` |
| **WP-6** Data sheet + contract extraction (GDPR) | Extraction hook + data-sheet engine to audit | **SHIPPED & far ahead** | extraction `703c0aa7`,`74e0a0f4`,`53f2e2da`,`bab76d5b`,`c4c2ef4b`; PII/GDPR `43a52d00`,`7eccfa03`,`b261f65b`,`6d13a3ea`,`0075d01f`; data sheet `17eaa41e`,`7a33b703`,`6f3b92ca`,`82224145` · migs `seed_frno_data_sheet`,`seed_de_fr_data_sheets`,`autofill_prefill_provenance` · `case_documents.py`,`gdpr.py`,`admin_dsar.py` |
| **WP-7** Stripe monetization | Two hook generations to reconcile + audit | **SHIPPED** (test mode) | `cdcd4d86` phases 1–7 complete; `472a9e14` paywall rewrite + Case Command Stripe; `5c0cc184` webhook-lag re-verify; `4a22cb0e`/`414b3f9b` fail-closed gates · migs `create_case_addons`,`create_stripe_events`,`add_payment_to_cases` · the `docs(relopass-stripe)` spec commits (Otto's spec, now built) |
| **WP-8** Assurance & attestation (the moat) | 7 tables + 2 apps to assess | **SHIPPED (phase 1)** · attestations still **EMPTY-BY-DESIGN** | `c35f696b` counsel attestation phase 1 (schema, tokenized reviewer flow, admin promote); `2443798e` Postgres fixes; `2393a1b4` legal_admin both-ends · migs `counsel_attestation_phase1` (20261104), `legal_admin_sourcing_side` (20261102) · `attestation.py` |
| **WP-9** Ops & PM (Notion, funnel) | Notion bridge + PostHog funnel to review | **SHIPPED** | Notion `b6f11d38` (today) + active branch `fix/notion-work-queue-repoint`; PostHog `8856e620`,`ca093028`,`2a84e477`,`83907754`,`1cca1ea4` · `admin_product_metrics.py`,`admin_marketing_analytics.py`,`crons.py` |
| **WP-10** Growth surface | Outreach app + landing + ES→IE vendor batch | **SHIPPED** (outreach/landing) · ES→IE batch = **DATA to load** | outreach `79f5a90d`,`dd6240a5` + `admin_outreach.py`,`admin_prospects.py` + migs `prospect_replies`,`message_templates`; landing `13924041`,`f059acec`,`5a90029d`; ES-IE `904f0948`,`73762eb6`,`bdfd1c4a` + mig `seed_es_ie_immigration_corpus` (20261010) |

### The one nuance worth reading in full — WP-3

Otto's WP-3 proposes a specific architecture: a single deterministic `corridor-resolve`
contract, and a *publish gate that requires a passing "Case Verification Report" (CVR) from
a real case.* The **outcomes** of that design are shipped — corridor resolution from cases,
`non_obvious`/`timing` on `requirement_items`, pre-arrival runway + feasibility verdicts,
and human-gated publishing via `requirement_items.review_status` + `/admin/content-review`.
But two of Otto's *specific mechanisms* are **not** in the repo, and both are legitimate
(small) design decisions rather than migrations:

- **A CVR-style publish gate.** The repo gates on human review, not on a passing real-case
  report. Search for `publish.?gate`/`CVR` returns only a docs report — no gate.
- **A deadline sweep that fires "booster" emails once per deadline.** Not present (the
  repo has feasibility windows + `notification_outbox`, but no per-deadline nudge email).

Neither is urgent; both are captured as decisions in the forward list (F4, F5).

---

## What is genuinely left — the real forward list

This is the actual "next stage." Five items, ordered by leverage. Each is written to drop
straight into your existing pipeline (Notion AI Work Queue → the matching skill → an
`aiq-*` branch → PR), which is how the 411 commits above were already made.

### F1 — Counsel attestation **phase 2** (the moat) · highest leverage · **build**
Phase 1 (schema, tokenized reviewer flow, admin promote) shipped in `c35f696b`. The moat
only becomes real when a regulated lawyer records **real** verdicts and the sellability
gate reads them.
- **Goal:** first real lawyer session → first `attestations` rows → a corridor that reads
  as *sellable* because it is actually attested.
- **Spec pointer:** `attestation.py`, mig `20261104…counsel_attestation_phase1`; Otto's
  WP-8 table model as the design reference.
- **Runs via:** `relopass-notion-decomposition` → `relopass-dev-queue`.
- **Metric:** claims with a current attestation (0 → N); corridors at `sellable`.
- **Validation:** one lawyer records one verdict end-to-end on a non-authoritative copy;
  confirm sellability flips *only* when a real attestation exists (never seed placeholders).

### F2 — Keep loading Otto's research through the **governed intake** · recurring value · **data op**
This is the actual, durable value of Otto. Payload waiting now: the **ES→IE 53-row
vendor batch**, the **~1,822 staged vendor candidates**, and any un-loaded corridor facts.
- **Goal:** move verified Otto research into `rolec` as *pending* candidates, then promote
  by human review — additively, deduped, with provenance.
- **Runs via:** `relopass-corridor-transfer` (your skill) → `otto-loader` /
  `import_otto_facts.py` / `import_supplier_candidates.py` → `requirement_fact_candidates` /
  `vendor_candidates` → vetting queue → approve.
- **Metric:** vendors promoted into curation per corridor; corridors with ≥1 vetted vendor
  per key category; facts promoted to `requirement_items`.
- **Validation:** `dry_run=true` first (a re-run must be ~100% skips), then load, then
  verify **by shape** (entities-vs-facts join per country), not just by total.
- **⚠ Do NOT** run `imported-source/seed_es_ie_vendors.py` — see Collisions #1.

### F3 — Decide the Candidate Beam: **keep in Audos** or port · **decision, my recommendation included**
It's the only capability not in the repo (0 history hits). But it's *authoring-side*, and
its output already reaches the product via the loader (as research → candidates).
- **My recommendation: keep it in Audos, do not port it into `rolec`.** Porting adds an LLM
  authoring subsystem to your product codebase for a job the repo already covers with
  extraction agents + the RAG-eval gate (`9e4eb0b0`). If requirement *recall* ever becomes
  the bottleneck, invest in that eval gate — not in a second authoring engine.
- **Decision to record:** keep-in-Audos (recommended) / port later / drop.

### F4 — Close the corridor-QA loop across all 10 corridors · **verification**
Otto QA'd 10 corridors; the repo has verification/eval artifacts for some (FR-NO, FR-DE,
ES-IE). Confirm DE-ES, IE-DE, DE-IE, NO-FR, ES-DE findings are each reflected as an in-repo
fix or eval — and decide on Otto's CVR-gate idea while you're there.
- **Runs via:** `relopass-task-validator` / `relopass-e2e-test` / `notion-task-executor`.
- **Metric:** corridors with a passing requirement-extraction eval; open QA findings with
  no closing artifact.

### F5 — Optional growth mechanic: deadline "booster" emails · **small build, decide want/skip**
Not in the repo today. If you want Otto's once-per-deadline nudge email, it's a small build
on top of the existing `notification_outbox` + feasibility runway. Low priority.

> Also on the board but **not a build**: **Stripe go-live** (WP-7). The implementation is
> complete in TEST MODE (`cdcd4d86`); the remaining step is flipping to live keys behind a
> go-live checklist — an ops decision, not a review.

---

## Collisions to avoid (the "no complications" payoff)

1. **Do NOT run `imported-source/seed_es_ie_vendors.py` against the database.** Your repo
   dropped `public.vendors` → `vendors_legacy` and deprecated writes to it
   (`f1f98baa`, `9d3fab9b`, mig `20260825…deprecate_vendors_write`). The live path is
   `vendor_candidates` → vetting queue. Otto's script upserts directly into
   `vendor_providers`-style columns, which would bypass vetting and can hit a
   deprecated/renamed table. **Load the 53 rows through F2's intake instead.**
2. **Do NOT hand Otto's hooks to Claude Code "to review."** They aren't in the repo and
   never will be. Where you want the *functionality* checked, point Claude Code at the
   repo's implementation (`attestation.py`, `admin_catalog.py`, `case_documents.py`, …).
3. **Do NOT rebuild vendor-governance, contract-extraction, Stripe, or the funnel.** All
   shipped and hardened. Re-implementing from Otto's prototype is a regression risk.
4. **Treat `imported-source/rolec-main` as stale.** The connected `rolec` is source of
   truth (411 commits ahead).

---

## How to drive this with Claude Code (reuse your own pipeline)

Otto's review template was built to *grade* work. Flip it into an **action** template and
feed it through the machine you already run. For each forward item: create one Notion AI
Work Queue task, let the matching skill execute it against a fresh `aiq-*` branch, ship a PR.

**Action template (paste at the top of a task):**

```
You are advancing ONE item of ReloPass (B2B relocation-compliance; corridor roadmaps for
HR, paid case unlocks). This is an ACTION task, not a review. Work against the live rolec
repo — never Otto's July snapshot, never Otto's hooks.

1. GOAL — the user-visible or revenue outcome this delivers.
2. SPEC — inputs, outputs, invariants, auth model, failure modes. Reuse existing repo
   patterns; cite the files you build on.
3. PLAN — the smallest change that delivers the goal. No rewrites of working systems.
4. ACCEPTANCE TEST — the check that proves it works (eval / e2e / migration-applies).
5. AUTONOMY TIER — Green / Yellow / Red per the autopilot rubric.
Output: a branch + PR, the Notion task updated, and the acceptance test passing.
```

**Worked example — F2, the ES→IE vendor load:**

> *Goal:* land Otto's 53 reviewer-corrected ES→IE vendors as pending `vendor_candidates` so
> they enter the vetting queue. *Spec:* source = `es_ie_vendors_2026-08-16.ndjson`; target =
> `vendor_candidates` (pending), deduped on `(lower(name), city, source_url,
> service_category)`, provenance preserved; **not** `vendor_providers`, **not**
> `seed_es_ie_vendors.py`. *Plan:* `relopass-corridor-transfer` → `import_supplier_candidates.py`
> (or `otto-loader`), `dry_run` first. *Acceptance:* dry-run shows 53 mapped/0 unrouted;
> real load inserts 53; they appear in the vetting queue; a re-run inserts 0. *Tier:* Yellow.

---

## Appendix — Otto WP → your existing skill

| Otto WP | Disposition | Your skill / tool that owns it now |
|---|---|---|
| WP-1 facts | LOAD (ongoing) | `relopass-corridor-transfer`, `import_otto_facts.py` |
| WP-2 QA | VERIFY (F4) | `relopass-task-validator`, `relopass-e2e-test` |
| WP-3 corridor core | SHIPPED; small decisions F4/F5 | `relopass-dev-queue` |
| WP-4 Candidate Beam | DECIDE (F3) — keep in Audos | — (authoring stays in Audos) |
| WP-5 vendor governance | SHIPPED; LOAD data via F2 | `relopass-corridor-transfer`, `admin_catalog` |
| WP-6 data sheet / extraction | SHIPPED (drop Otto's version) | `relopass-fix-*` for any bug follow-ups |
| WP-7 Stripe | SHIPPED; ops go-live | `relopass-dev-queue` (go-live checklist) |
| WP-8 attestation | BUILD phase 2 (F1) | `relopass-notion-decomposition` → `relopass-dev-queue` |
| WP-9 ops / funnel | SHIPPED | `notion-task-executor` |
| WP-10 growth | SHIPPED; ES→IE = LOAD via F2 | `relopass-corridor-transfer` |
