# Audos execution brief — Track B seed measurement + §C RFQ consolidation audit

**Context date:** 2026-07-19 · **Repo:** `rlecomte1929/rolec` · **Supabase:** `nsvefcvpvwwwhuqyuqmp`
**You own both tracks end to end.** Neither is being run by Cowork. Do not hand either back.

---

## 0. The visibility rule — how you verify what you cannot query

Your DB tools reach **Audos WorkspaceDB only**. Both deliverables here concern **Supabase**, which you cannot query directly. That does not block you — it changes the method:

| Need | Your method |
|---|---|
| Did a provisioned company get a published policy? | **Browser / UI observation** (§1.3) — you have browser tools |
| Row counts, recency, live SQL in Supabase | **Queue a Cursor job** (§1.5, §2) — Cursor runs in-repo with `SUPABASE_*` secrets |
| Which code reads which table | **Queue a Cursor job** (§2) — repo file inspection |

**Never report a Supabase fact from WorkspaceDB.** If a number came from WorkspaceDB, label it as such. An unlabelled cross-store number is what produced the `relopass_vendors` confusion.

---

## 1. TRACK B — seed success rate (you execute now)

**Question:** when a test-drive session is provisioned, does its company reliably end up with a **published** policy-config version?

**Why it matters:** if 5/5, the seed is healthy, that line closes, and the persistence design becomes the sole critical path for P0-1. If fewer, the seed is intermittent and needs the real exception captured. Two prior figures are both unreliable — an n=1 success and an observational 15/15 whose linkage could not be verified (the `test_sessions.hr_user_id` ↔ `profiles.id` join returns **zero** matches). **Do not inherit either number.**

### 1.1 Provisioning — repeat 5 times

Each run in a **clean browser context** (new incognito/profile; no carried session).

1. Navigate to `https://relopass.com/test-drive?campaign=qa-p0-1&corridor=FR_NO`
2. Dismiss the analytics consent banner — click **Decline** (it overlays the page bottom and blocks clicks).
3. If a "You're already signed in as … Sign out first" guard appears, click **Sign out and use my test account**.
4. Enter first name — use `QaSeed1` … `QaSeed5`, one per run, so sessions are identifiable.
5. Click **Start the test**.
6. **Capture and record both credential pairs before navigating away** — HR email + password, employee email + password. A lost password has already killed one run. Credentials are `@probe.test`.
7. Confirm the page reads **Paris → Oslo** (corridor pinned). If it shows any other corridor, stop and report — the `&corridor=` override is not honoured.

### 1.2 Sign in as HR
Click **Sign in →**, or go to `/auth?mode=login` and use the captured HR credentials. If a coordinate click on the Sign in button doesn't submit, click it **by element reference** or focus a field and press **Enter**.

### 1.3 Determine whether a published policy exists — UI method

Use the **primary** indicator. If it's ambiguous, use the fallbacks and say which you used.

**Primary — HR policy surface.** In the HR console, open the Policy / Benefits section and look for a **published** version (a "Published" tab or state showing an active policy version). Present = YES.

**Fallback A — the missing-policy banner.** Start creating a case (**Create your first case →**). Since AIQ-1621, a provisioned company has a seeded published policy, so the warning *"you haven't published a benefits policy"* should be **absent**. Banner **absent** = policy present. Banner **shown** = no policy.

**Fallback B — employee Services banner.** Sign in as the employee and open Services. *"Company policy comparison is active"* = policy present.

Record **YES / NO** per session, plus which indicator you used and a screenshot.

### 1.4 Report
Report a clean **n/5** from these five sessions only.

- **5/5** → seed healthy. State: "seed line closed; persistence design is the sole P0-1 critical path."
- **0–4/5** → seed intermittent. Queue a Cursor job to capture the **actual exception text** from the swallow at `backend/app/routers/test_drive.py:229–232` (best-effort try/except around `_seed_default_published_policy`, called at line 313). **Report the real error string — do not hypothesise a cause.**

### 1.5 Cursor confirmation job (queue alongside)

Have Cursor run this against Supabase and paste the raw output:

```sql
WITH pub AS (
  SELECT pc.company_id::text AS cid
  FROM policy_configs pc
  JOIN policy_config_versions pcv ON pcv.policy_config_id::text = pc.id::text
  WHERE pcv.status='published' GROUP BY 1
)
SELECT co.is_test,
       count(*)                                    AS cases,
       count(*) FILTER (WHERE pub.cid IS NOT NULL) AS company_has_published_policy,
       count(rap.id)                               AS cases_with_resolution
FROM relocation_cases rc
JOIN companies co ON co.id::text = rc.company_id::text
LEFT JOIN pub ON pub.cid = co.id::text
LEFT JOIN resolved_assignment_policies rap ON rap.case_id::text = rc.id::text
WHERE rc.created_at::timestamptz > now() - interval '1 day'
GROUP BY co.is_test;
```

Real-customer baseline must not regress: currently **3 of 21** cases resolved.

### 1.6 Hygiene
- **Never use `insead-2026`** — it is live cohort data, already purged twice.
- Report every `qa-p0-1` artifact created (session labels, company names) so it can be purged.
- If you also run RUN 003 Segment B step B16, label it **`PRE-MERGE BASELINE (main @ 1f2e4593)`**. Commit `3f9ed63a` is undeployed, so production runs old code and "No policy rule" there is expected — **not** a regression.

---

## 2. §C — RFQ/quote consolidation audit (queue as a Cursor job)

**Deliverable: an audit and a recommendation. Create nothing. No migration, no new table, no schema change.**

### 2.1 The problem
Three overlapping RFQ/quote models are live in Supabase simultaneously:

| Model | Tables (rows) |
|---|---|
| 1 | `rfqs` (9) · `rfq_items` (9) · `rfq_recipients` (17) |
| 2 | `rfq_requests` (25) |
| 3 | `quote_requests` (21) · `quotes` (6) · `quote_lines` (10) · `quote_conversations` (9) |

Also present: `quote_participants` (0), `quote_messages` (0), `case_budget_lines` (0), `policy_cap_requests` (1). All have RLS enabled.

This is the same pattern currently being arbitrated in the policy layer — four overlapping attempts (AIQ-1631/1635/1636 + `fix/f14-shared-taxonomy`). **Do not add a fourth RFQ vocabulary.**

### 2.2 What Cursor must produce

1. **Read/write map.** For each of the 12 tables: which code reads it, which writes it, with file paths and line numbers. Start from `backend/app/routers/hr_rfq.py`, `supplier_rfq.py`, `employee_quotes.py`; services `rfq_brief.py`, `rfq_evaluation_service.py`, `rfq_recipient_mapping.py`, `supplier_link_dispatch.py`, `supplier_jwt.py`; frontend `ServicesRfqNew.tsx`, `QuoteRfqDetail.tsx`, `QuoteRequestPage.tsx`, `SupplierQuotePage.tsx`. Also grep the whole repo for each table name — some writes may sit in `backend/main.py`.
2. **Migration archaeology.** For each model, which migration introduced it and when. The six known RFQ migrations start at `supabase/migrations/20260918000000_rfq_supplier_identity.sql`. Order them; the newest actively-written model is the likely canonical one.
3. **Liveness.** Have Cursor run, per table:
   ```sql
   SELECT count(*) AS rows, min(created_at) AS first, max(created_at) AS last
   FROM public.<table>;
   ```
   Distinguish real usage from test residue — rows created only during known QA windows are residue.
4. **Verdict:** which model is **canonical**; which are **legacy/abandoned**; what the non-canonical live rows represent; whether any is partially wired (written but never read, or read but never written — a silent-failure smell).
5. **Consolidation recommendation:** what gets deprecated, what data (if any) must move, and what the risk is. Recommendation only — no execution.

### 2.3 Stop condition
When the verdict and recommendation are written, **stop**. Romain approves the canonical model before any consolidation work begins.

---

## 3. Guardrails (apply to both tracks)

- **No new tables anywhere.** Not in Supabase, not in WorkspaceDB.
- **Any migration is 🔴 Red** — commit the file only; never apply it; never write to `supabase_migrations.schema_migrations`.
- **Any new `public` table** (not expected here) needs `ENABLE ROW LEVEL SECURITY` + a policy + `REVOKE ALL FROM anon`. SEC-002 exposed 8 tables of GDPR-scope PII this way.
- **Approve no supplier records.** The 9 Norway suppliers and 3 Oslo schools remain behind Romain's gate.
- **Don't work around a blocker.** If a token lacks scope or a job can't reach the DB, stop and report — as you correctly did with the PR 403.
- **Report format:** branch · commit SHA · what changed · what you measured (raw output) · what is blocked. Two prior reports contained only the repo name and a hash; the work looked like it hadn't happened.

---

## 4. Report

```
TRACK B — SEED RATE
  Sessions: QaSeed1..5  campaign qa-p0-1  corridor FR_NO
  Published policy present:  1:__  2:__  3:__  4:__  5:__   →  ___/5
  Indicator used (primary / fallback A / fallback B): ____
  Corridor pinned correctly on all 5? ____
  If <5/5 — actual exception text from test_drive.py:229-232: ____
  Cursor SQL output: [paste raw]
  Real-customer baseline (was 3/21): ____
  Artifacts to purge: ____
  VERDICT: seed healthy / intermittent ____

§C — RFQ AUDIT
  Canonical model: ____
  Legacy/abandoned: ____
  Partially-wired tables (written-never-read or read-never-written): ____
  Non-canonical live rows represent: ____
  Consolidation recommendation: ____
  [STOPPED — nothing created, awaiting approval]

STILL OPEN (unchanged)
  Track A gate 1 — AIQ-1631 direction: ____
  Track A gate 2 — persistence A/B/C (Romain prefers C): ____
  Task #84515 — Stripe file path(s) / spec-only?: ____
```

**Sequencing:** Track B starts immediately — browser-driven, needs no code lock. Queue the §C Cursor job now so it takes the lock when Track A releases it. **#84574 (Track A) keeps priority — do not cancel it.**
