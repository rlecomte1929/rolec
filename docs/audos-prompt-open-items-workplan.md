# Audos brief — open items work plan (everything except Stripe)

**Context date:** 2026-07-20 · **Repo:** `rlecomte1929/rolec` · **Supabase:** `nsvefcvpvwwwhuqyuqmp`
**Stripe is tracked separately** in `docs/audos-prompt-stripe-portable.md`. Do not mix the two.

Eight open items, sequenced by risk. **Work them in order.** S1 and S2 are safety items that must land before the INSEAD cohort goes out; everything else waits behind them.

**Executor key:** 🌐 **Audos browser** · 🔧 **Cursor** (repo + Supabase) · 👤 **Romain decides**
Your DB tools reach WorkspaceDB only — never report a Supabase or repo fact you did not get from Cursor. Label every claim.

---

# S — SAFETY (before the cohort)

## S1 🔧 Email dispatcher has no recipient filter

**Risk:** `518bf11c` merged a GitHub Actions cron (`.github/workflows/outbox-dispatch.yml`) that calls `POST /api/crons/dispatch-outbox` every 15 minutes and emails HR for policy exceptions. `notification_outbox_dispatch.py` sends to whatever `to_email` sits on the row — **no allowlist, no domain restriction, no dry-run.** It is currently inert only because it is gated behind `vars.OUTBOX_DISPATCH_CRON_ENABLED`. A feature flag is not a safety mechanism.

**Do:**
1. Confirm `OUTBOX_DISPATCH_CRON_ENABLED` is **unset** in GitHub repo variables. Report its state. Do not set it.
2. Add a hard recipient guard in `notification_outbox_dispatch.py` — send only when the recipient matches an explicit allowlist, defaulting to `@probe.test` only, controlled by an env var (e.g. `RELOPASS_OUTBOX_ALLOWED_DOMAINS`). Non-matching rows are skipped and logged, never sent.
3. Answer: **was email-by-default for policy exceptions an intentional decision?** It contradicts RUN 003 §C4 (HR gets an in-app notification, **zero** emails) and the stated preference to minimise Resend sends. If unintentional, propose reverting to in-app-only and stop for approval.

**Evidence:** the guard's diff · a test proving a non-allowlisted address is skipped · the variable's current state.
**Stop after:** report before enabling anything. 🔴 Red — automated external send.

## S2 🔧 Unverified suppliers are reachable by customers

**Confirmed repo-side:** `verified` is read, written and serialised in `supplier_registry.py` (lines 182, 358, 427–428) but **never used as a query filter**. `rfq_recipient_mapping.py` and `vendor_curation.py` do not reference it at all. So the 9 Norway suppliers — `status='active'`, `verified=false`, `source='directory_import'`, written 2026-07-19 15:36:57 — are **live and eligible** for RFQ recipient mapping and recommendations. They are not pending anything, despite being described that way twice.

**Do:**
1. Trace and report every path where a supplier can reach a customer: recommendations, RFQ recipient mapping, supplier search, HR vendor curation. For each, quote the filter — or confirm none exists.
2. Report whether any of the 9 has already been sent an RFQ or shown to a user.
3. Propose the gate: which field is authoritative (`verified`, `status`, or a new `platform_vetting_status`), and where the filter belongs so it cannot be bypassed.
4. **Do not approve, verify, or delete any supplier record.** 👤 Romain decides the policy.

**Evidence:** quoted filters or explicit "none exists" per path · RFQ/exposure history for the 9.
**Stop after:** step 3. 🔴 Red — customer-facing data exposure.

---

# G — THE RUN 004 GATE

## G1 🌐 Track B — seed success rate *(never created as a task; deferred four times)*

**Question:** when a test-drive session is provisioned, does its company reliably end up with a **published** policy-config version?

**Do — five times, clean browser context each:**
1. `https://relopass.com/test-drive?campaign=qa-p0-1&corridor=FR_NO`
2. Decline the analytics consent banner (it overlays the page and blocks clicks). If a "You're already signed in" guard appears, click **Sign out and use my test account**.
3. First name `QaSeed1`…`QaSeed5`, one per run. Click **Start the test**.
4. **Capture both credential pairs before navigating away** — a lost password already killed one run.
5. Confirm the page reads **Paris → Oslo**. If not, stop: the `&corridor=` override is not honoured.
6. Sign in as HR. Determine whether a **published** policy exists:
   - **Primary:** HR Policy/Benefits section shows a published version.
   - **Fallback A:** on **Create your first case →**, the *"you haven't published a benefits policy"* warning is **absent** = policy present.
   - **Fallback B:** employee Services shows *"Company policy comparison is active"*.

**Report a clean n/5** from these five sessions only. **Do not inherit the 15/15 figure** — it was observational and unverifiable (`test_sessions.hr_user_id` ↔ `profiles.id` returns zero matches).

- **5/5** → seed healthy; that line closes; persistence becomes the sole P0-1 critical path.
- **0–4/5** → intermittent; have Cursor capture the **actual exception text** from the swallow at `backend/app/routers/test_drive.py:229–232` (called line 313). Report the real string; do not hypothesise.

**Hygiene:** never `insead-2026`. Report every `qa-p0-1` artifact for purging.

## G2 🔧 AIQ-1631 — both prior recommendations are VOID

#84501 (18:13) said runtime aliasing wins and the taxonomy JSON should be dropped. #84574 (21:33) said the shared taxonomy wins. Direct opposites — and **both reasoned from a read-only 2026-07-16 snapshot**, which predates `3f9ed63a` and `121403c8`. Neither had the inputs. Treat both as void; do not cite either as settled.

**Do — from the real code, not a snapshot:**
1. Fetch and diff the actual commits: `121403c8` (`fix/f14-shared-taxonomy`) and `3f9ed63a` (`audit/stage-p0-1-eager-policy-resolution`), against current `main` (`518bf11c`).
2. Map the four competing attempts and what each changed: `c765c4d2`, `bef49ab7`, `03d4b18e`, `38e53704` (all on `main`) plus `121403c8`. Note `main:9791` calls `_with_legacy_benefit_key_aliases()`.
3. Determine which direction wins — canonical taxonomy or runtime aliasing — state what gets deleted, and whether `121403c8` needs amending before merge.
4. **Confirm explicitly that you read the live files, not a snapshot**, and cite SHAs.

**Stop after:** the recommendation. 👤 Romain approves before any change.

## G3 🔧 Persistence design — re-derive Option C from the real diff

`3f9ed63a` writes `policy_id = 'policy_config_matrix:<vid>'` into a column verified in production as **`uuid NOT NULL`**, FK → `company_policies(id)`. A colon-bearing string fails at the cast, before the FK is evaluated — **relaxing the FKs does not fix it.**

#84574 recommended **Option C**, which matches Romain's preference — but was derived from the stale snapshot, so re-derive it:

- **A** — relax FKs, widen columns to `text`. Weakens integrity for real customers too.
- **B** — shadow `company_policies` / `policy_versions` rows. No migration, but writes synthetic rows other consumers treat as real.
- **C** — `policy_id`/`policy_version_id` nullable, add `policy_config_version_id uuid` FK → `policy_config_versions`, plus a CHECK that exactly one source is populated.

**Constraints:** any migration is 🔴 Red — commit the file only, never apply, never write to `supabase_migrations.schema_migrations`. Idempotent DDL. Real-customer resolution must not regress (baseline: 3 of 21 cases resolved).

**Stop after:** the recommendation. This is the true P0-1 critical path — nothing else moves RUN 003 B16.

---

# A — ANTI-WASTE AUDITS *(after S and G)*

## A1 🔧 §C — RFQ/quote consolidation audit. **Create nothing.**

Three overlapping models are live simultaneously in Supabase:

| Model | Tables (rows) |
|---|---|
| 1 | `rfqs` (9) · `rfq_items` (9) · `rfq_recipients` (17) |
| 2 | `rfq_requests` (25) |
| 3 | `quote_requests` (21) · `quotes` (6) · `quote_lines` (10) · `quote_conversations` (9) |

Also `quote_participants` (0), `quote_messages` (0), `case_budget_lines` (0), `policy_cap_requests` (1). All have RLS.

This is the F14 pattern in a second subsystem. **Do not add a fourth vocabulary.**

**Produce:** read/write map per table with file paths (start at `hr_rfq.py`, `supplier_rfq.py`, `employee_quotes.py`, `rfq_brief.py`, `rfq_evaluation_service.py`, `rfq_recipient_mapping.py`; also grep `backend/main.py`) · migration archaeology (which migration introduced each, in order) · liveness per table (`SELECT count(*), min(created_at), max(created_at)`) distinguishing real usage from QA residue · **verdict**: canonical / legacy / partially-wired (written-never-read or read-never-written — the silent-failure smell) · consolidation recommendation.

**Stop after the verdict.** No table, no migration, no schema change.

## A2 🔧 Vendor seed gap — 80 in the files, 17 in production

`backend/app/recommendations/datasets/` holds 80 suppliers (movers 10, living_areas 38, schools 32). Production `suppliers` has ~17–25 rows, of which **exactly one is `verified=true`** (SIRVA). The seed has never fully run.

**Report before any new vendor work:** why only a fraction landed · whether `seed_suppliers.py` is idempotent-safe to re-run against production · the **true verified count per category**. The "5 verified per category" deliverable depends on this number and is currently unknown.

**Also:** the 3 Oslo schools (`s-o1/2/3`) are in **no** queryable store — not Supabase, not WorkspaceDB. They were reported as created. Confirm they do not exist and, if wanted, re-create them through the proper path into Supabase.

---

# H — HOUSEKEEPING

## H1 Duplicate commit loop — fix the emitter
~40 identical `docs: add stripe-relopass-package…` commits across two occurrences. Cause (your own diagnosis, accepted): one-file-per-commit via the Contents API × repeated re-briefs of the same task. **Fix:** commit via the **Git Trees API** — one atomic commit for all files; never re-run a commit task that already succeeded; cancel duplicates before they queue. No history rewrite on `main` — just stop the emitter.

## H2 Branch discipline
New work goes on dedicated branches off `main`. **Do not use `fix/td-qa-services-batch-0719`** — it carries ~40 duplicate doc commits plus unrelated migrations and is effectively unreviewable.

---

# Rules

- **NONE is a valid answer.** "Finished" with no branch, SHA, files or DB objects means nothing shipped — say so.
- **Never report a Supabase/repo fact from WorkspaceDB.** Label every claim `[VERIFIED]` or `[CLAIM]`.
- **Stop at every gate.** S1, S2, G2, G3, A1 all end in a recommendation for Romain, not an implementation.
- **Approve no supplier records.** **Apply no migrations.** **Create no tables.**
- **Don't work around blockers** — if a token lacks scope, stop and report, as you correctly did with the PR 403.
- Every report: branch · SHA · files changed · what you measured (raw output) · what is blocked.

---

# Report

```
S1 EMAIL GUARD
  OUTBOX_DISPATCH_CRON_ENABLED state: ____
  Recipient guard diff: ____  Test proving non-allowlisted skipped: ____
  Email-by-default intentional? ____  [STOPPED]

S2 SUPPLIER EXPOSURE
  Paths where a supplier reaches a customer + filter quoted (or NONE): ____
  Have any of the 9 been sent an RFQ / shown to a user? ____
  Proposed gate field + location: ____  [STOPPED]

G1 TRACK B
  1:__ 2:__ 3:__ 4:__ 5:__  →  ___/5   Indicator used: ____
  Corridor pinned on all 5? ____
  If <5/5 — actual exception text: ____
  Artifacts to purge: ____   VERDICT: healthy / intermittent ____

G2 AIQ-1631
  Read live files (not snapshot)? ____  SHAs cited: ____
  Direction: ____  Deleted: ____  Amend 121403c8? ____  [STOPPED]

G3 PERSISTENCE
  Re-derived option: ____  Reasoning: ____  Migration needed? ____  [STOPPED]

A1 RFQ AUDIT
  Canonical: ____  Legacy: ____  Partially-wired: ____
  Recommendation: ____  [STOPPED — nothing created]

A2 SEED GAP
  True verified count per category: ____  Why partial: ____  Idempotent-safe? ____
  Oslo schools confirmed absent? ____

H1/H2  Emitter fixed? ____  Branches used: ____
```

**Sequence:** S1 → S2 → G1 (browser, runs in parallel, no lock) → G3 → G2 → A1 → A2. G1 can start immediately; it needs no code lock and it gates RUN 004.
