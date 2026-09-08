# Audos brief — open items, revision 2

**Context date:** 2026-07-20 · **Repo:** `rlecomte1929/rolec` · **Supabase:** `nsvefcvpvwwwhuqyuqmp`
**Supersedes** `docs/audos-prompt-open-items-workplan.md`. Stripe stays separate (`audos-prompt-stripe-portable.md`).

Your runner diagnosis was right and it was the real blocker — the previous brief was written for a repo-checkout executor that does not exist here. Corrected throughout. Several items also shrank because the live-database halves are now **done** (§2).

---

## 0. Approvals

- ✅ **Cancel #84750, #84751, #84752** — duplicate Stripe-doc commits; #84567 already landed those files.
- ✅ **Start G1 (Track B) now** — browser-only, no lock, no repo. It gates RUN 004 and nothing in the queue jam blocks it.
- ✅ **Execution routing accepted:** code work via **GitHub REST / Trees API through the `GITHUB_TOKEN` proxy** (the proven path — #84567, #84492 landed that way). **Never assume a local checkout, `grep`, `pytest`, or a Supabase connection.** Live-database questions come to Cowork.

---

## 1. Do this before staging anything

Reconcile against **#84762, #84764, #84765** — they appear to already carry S1/S2/G/A from the previous brief. **Re-brief those in place with the GitHub-API auth path. Do not stage new copies.** A fourth duplicate is exactly what H1 exists to prevent. Also clear the stale #84601.

---

## 2. Live-database findings — DELIVERED. Do not re-request or re-derive.

Cowork queried production directly. Treat these as `[VERIFIED — Supabase]`.

### 2.1 The approval gate is not the field we thought
`suppliers.verified` is **vestigial** — 0 true across living_areas, banks, legal_admin, tax_finance. The operative gate is **`supplier_service_capabilities.platform_vetting_status`**, and **92 of 97** capability rows are `approved`.

### 2.2 ⚠️ The 9 Norway suppliers are marked APPROVED with no approver
All nine: `platform_vetting_status = 'approved'`, **`vetted_by = NULL`, `vetted_at = NULL`**, `verified = false`.

They were **auto-approved at import**. They are not pending anything — and the audit trail records an approval no human gave. **This reframes S2 (see §3).**

### 2.3 Exposure is currently zero
`rfq_recipients`, `case_vendor_shortlist`, `company_preferred_suppliers` all return **0** rows for `no-%`. No customer has seen them. The risk is prospective, not realised.

### 2.4 Category coverage — the "80 vs 17" framing was wrong on both sides

| Category | Suppliers | Capability rows approved |
|---|---|---|
| living_areas | 40 | 38 |
| schools | 33 | 32 |
| movers | 14 | 14 |
| banks | 4 | 3 |
| legal_admin | 3 | 3 |
| tax_finance | 3 | 2 |

**Six categories are populated, not three.** `legal_admin` and `tax_finance` exist (from the Norway import). The earlier "immigration and tax are unseeded" claim came from dataset files, not the database, and is withdrawn.

### 2.5 RFQ liveness — three generations, cleanly separated

| Table | Rows | First | Last |
|---|---|---|---|
| `quote_requests` | 51 | 2026-05-11 | **2026-06-29** |
| `rfq_recipients` | 17 | 2026-07-14 | 2026-07-14 |
| `rfq_requests` | 12 | **2026-07-19** | 2026-07-19 |
| `quote_lines` | 10 | — | — |
| `rfqs` / `rfq_items` / `quote_conversations` | 9 / 9 / 9 | 2026-07-14 | 2026-07-14 |
| `quotes` | 6 | 2026-07-14 | 2026-07-14 |

`quote_requests` is **legacy** — dead for three weeks. The Jul 14 cluster is one day's activity but the only complete relational model. `rfq_requests` is the most recent. **Which of the latter two is canonical needs the code map — that is your job in A1.**

### 2.6 Oslo schools
`s-o1/2/3` exist in **no** queryable store — not Supabase, not WorkspaceDB. Confirmed absent.

---

## 3. The cards

**Legend:** ✅ GitHub API (code) · 🌐 Audos browser · 👤 Romain decides

| # | Card | Exec |
|---|---|---|
| **G1** | Track B — 5 sessions, clean n/5 | 🌐 **start now** |
| **S1a** | Outbox recipient allowlist guard | ✅ |
| **S1b** | `OUTBOX_DISPATCH_CRON_ENABLED` state + email-by-default decision | ✅ |
| **S2a** | ⚠️ **Reframed** — find the auto-approving import path | ✅ |
| **G3** | Persistence — re-derive A/B/C from the real diff | ✅ |
| **G2** | AIQ-1631 — direction, from live files | ✅ |
| **A1** | RFQ read/write code map → canonical verdict | ✅ |
| **A2** | Seed idempotency + Oslo schools re-create | ✅ |
| **H1/H2** | Trees API commits; dedicated branches | ✅ |

**Sequence:** G1 now (parallel) → S1a → S1b → S2a → G3 → G2 → A1 → A2.

---

## 4. Detail on what changed

### S2a — ⚠️ substantially reframed
**The task is no longer "add a filter on `verified`."** Per §2.1–2.2, the defect is upstream: the supplier import writes `platform_vetting_status='approved'` with a null `vetted_by`.

**Do:**
1. Find the code path that imported the 9 Norway suppliers (`source='directory_import'`, written 2026-07-19 15:36:57) and writes `supplier_service_capabilities`. Likely `supplier_registry.py`, `seed_suppliers.py`, `vendor_discovery/`, or an admin import route.
2. **Quote the line that sets `platform_vetting_status`.** Is `approved` a default, a hardcode, or passed in?
3. Propose the fix: imports write **`pending`**, and `approved` is only ever set with a non-null `vetted_by` + `vetted_at`. Consider a CHECK constraint enforcing that pairing — if so it is a migration, 🔴 Red, commit only.
4. Separately: does **anything** filter on `platform_vetting_status` when surfacing suppliers to customers? Trace recommendations, `rfq_recipient_mapping.py`, supplier search, `vendor_curation.py`. Quote the filter or write **NONE**.
5. **Do not modify any supplier record.** 👤 Romain decides whether the 9 get reset to pending.

**Stop after step 4.**

### A1 — code map only; liveness is done
§2.5 supplies the row counts and dates. You need the **read/write map**: for each of the 12 tables, which code reads it and which writes it, with file paths and line numbers. Start at `hr_rfq.py`, `supplier_rfq.py`, `employee_quotes.py`, `rfq_brief.py`, `rfq_evaluation_service.py`, `rfq_recipient_mapping.py`; also grep `backend/main.py`. Add migration archaeology (which migration introduced each model, in order).

**Verdict required:** canonical · legacy · **partially-wired** (written-never-read or read-never-written — the silent-failure smell; `case_budget_lines`, `quote_participants` and `quote_messages` are all at 0 rows and are prime suspects). **Create nothing.** Stop at the verdict.

### A2 — trimmed
Counts are done (§2.4). Remaining: is `seed_suppliers.py` **idempotent-safe** to re-run against production, and what explains the gap between the dataset files and the loaded rows? Plus re-create the 3 Oslo schools into Supabase through the proper path — with `platform_vetting_status='pending'`, not approved.

### S1a / S1b / G2 / G3 — unchanged in substance
Only the execution path changes: GitHub REST/Trees API, no checkout assumed.

- **S1a:** add a recipient allowlist in `notification_outbox_dispatch.py` (`RELOPASS_OUTBOX_ALLOWED_DOMAINS`, default `@probe.test` only); non-matching rows skipped and logged, never sent. Branch `safety/outbox-guard`. **Do not set `OUTBOX_DISPATCH_CRON_ENABLED`.**
- **S1b:** report the variable's state; answer whether email-by-default for policy exceptions was intentional (it contradicts RUN 003 §C4 — in-app, zero emails — and the minimise-Resend preference). Recommend; stop.
- **G2:** fetch and diff `121403c8`, `3f9ed63a`, and `c765c4d2` / `bef49ab7` / `03d4b18e` / `38e53704` against `main@518bf11c`. Both prior recommendations are **void** — they used a 2026-07-16 snapshot predating the commits under review. **Confirm in the report that you read live files, and cite SHAs.**
- **G3:** re-derive Option A/B/C for the `policy_id` `uuid NOT NULL` cast failure. Note a colon-bearing string fails at the cast before the FK is evaluated, so FK relaxation alone does not fix it. Romain's preference is C; re-derive rather than inherit.

---

## 5. Rules

- **NONE is a valid answer.** "Finished" with no branch, SHA, files or DB objects means nothing shipped — say so.
- **Label every claim** `[VERIFIED]` or `[CLAIM]`. Never report a Supabase or repo fact from WorkspaceDB.
- **Stop at every gate.** S1a, S1b, S2a, G2, G3, A1 all end in a recommendation, not an implementation.
- **Approve no supplier records. Apply no migrations. Create no tables.**
- **One atomic commit** via the Git Trees API — never one file per commit. That pattern produced ~40 duplicate commits twice.
- **Dedicated branches off `main@518bf11c`.** Never `fix/td-qa-services-batch-0719`.
- **Don't work around blockers** — if a token lacks scope, stop and report, as you correctly did with the PR 403.
- Live-database questions go to Cowork. Do not stage a Cursor job that needs a Supabase read.

---

## 6. Report

```
QUEUE
  #84750/51/52 cancelled: ____
  #84762/64/65 reconciled (re-briefed, not duplicated): ____
  #84601 cleared: ____

G1 TRACK B
  1:__ 2:__ 3:__ 4:__ 5:__  →  ___/5   Indicator used: ____
  Corridor pinned on all 5? ____
  If <5/5 — actual exception text (test_drive.py:229-232): ____
  Artifacts to purge: ____        VERDICT: healthy / intermittent ____

S1a  Branch/SHA: ____  Guard diff: ____  Skip-test: ____  [STOPPED]
S1b  OUTBOX_DISPATCH_CRON_ENABLED state: ____  Email-by-default intentional? ____  [STOPPED]

S2a  Import path + line setting platform_vetting_status: ____
     'approved' is default / hardcode / passed-in: ____
     Anything filtering on platform_vetting_status when surfacing? [quote or NONE] ____
     Proposed fix: ____  Migration needed? ____  [STOPPED]

G3   Re-derived option: ____  Reasoning: ____  [STOPPED]
G2   Live files read (not snapshot)? ____  SHAs: ____  Direction: ____  Amend 121403c8? ____  [STOPPED]
A1   Canonical: ____  Legacy: ____  Partially-wired: ____  Recommendation: ____  [STOPPED]
A2   seed_suppliers.py idempotent-safe? ____  Gap explanation: ____  Oslo schools re-created as pending? ____

H1/H2  Emitter fixed (Trees API)? ____  Branches used: ____
```
