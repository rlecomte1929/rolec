# Audos — Q1 verdict accepted · three findings filed · CARD Q1-B (corrected)

---

## 1. Your Q1 finding was correct. My card sent you to the wrong place.

You searched five HR surfaces and concluded there is no RFQ creation entry point in the HR UI. **That is right.** The card told you to search HR because `POST /api/hr/rfq-requests` exists in the backend — I inferred a UI from an endpoint, and the inference was wrong.

**RFQ creation lives in the EMPLOYEE Services flow:**

```
Employee → Services → questions → recommendations → estimate
        → [Request quotes]  ← disabled until a shortlist exists
        → /employee/case/:caseId/services/rfq/new
```

`ServicesNavRibbon.tsx:15` carries the "Request quotes" nav item; `ServicesEstimate.tsx:160` holds the button, `disabled={!hasShortlist}`. It calls `servicesAPI.createRfq → POST /api/rfqs`.

**Your negative finding was worth more than a positive one would have been** — chasing why it was negative resolved a question that had been open for three days.

---

## 2. What your run resolved

### The three parallel RFQ models — settled

| Model | Rows | Status |
|---|---|---|
| `rfqs` + `rfq_items` + `rfq_recipients` | 9 / 9 / 17 | ✅ **canonical** — `client.ts:3065` calls it *"the canonical RFQ flow"* |
| `quote_requests` | 51 | ⛔ **retired** — AIQ-1525; endpoint returns 410; rows dead since 29 June |
| `rfq_requests` | 25 | ⚠️ **orphaned** — backend live, client wrappers exist, **zero component callers** |

That closes an audit card outright. No further work needed on it.

### Your HTTP 500 — root-caused completely

`GET /api/cases/{id}/vendors` runs `LEFT JOIN public.vendors`. **`public.vendors` no longer exists** — confirmed via `pg_class`, which now returns only `case_vendor_shortlist` and `suppliers`. The table was present earlier the same day (0 rows) and was dropped as part of the vendors deprecation. The query throws, a bare `except` catches it, and it returns 500.

Cause of the cause: that deprecation was my recommendation, and I never said to grep for readers first.

**Good news for the batch: this 500 does NOT block the RFQ flow.** `recommendations` and `shortlist` live in `ServicesFlowContext` backed by localStorage, and `list_case_vendors` is a read-back for HR display, not the shortlist builder.

### Three findings filed in Notion

| Priority | Finding |
|---|---|
| **P1** | 500 on `/api/cases/{id}/vendors` — joins the dropped `vendors` table |
| **P2** | `POST /api/hr/rfq-requests` orphaned — decide: wire it or retire it |
| **P3** | "HR owner" field shows the employee email |

Two more of your observations are logged but not filed: *"Approve case"* jumps `Not started → Complete` with no intermediate state, and `ERR_ABORTED` on `/api/hr/assignments` (benign navigation cancellation — you called that correctly).

---

## 3. CARD Q1-B — RFQ creation via the employee Services flow

**Question:** Can an RFQ be created end to end through the employee Services flow, and does it write to `rfqs`?

**Campaign:** `qa-q1b` · **Corridor:** `FR_NO` · **Budget:** ~25 · **Fresh session.**

### ⭐ STEP 1 — the probe. Do this before anything else.

**Question:** does Services open on an HR-created case that has a route but no completed intake?

Everything downstream depends on the answer, and it takes about four actions.

1. Provision on `?campaign=qa-q1b&corridor=FR_NO`, first name `RfqQ1B`. Decline the analytics banner.
2. **Capture both credential pairs immediately.** Non-ASCII password → record and stop.
3. Sign in as **HR**, create a case, assign it to the employee. **Record both ids, labelled** — the URL id (assignment) and any separate case id.
4. Sign in as the **EMPLOYEE** in a fresh context. Open **Services** — do not complete intake.

**Record which of these happens:**

- **(a) Services opens** → continue to Step 2. The whole batch is unblocked without the harness.
- **(b) Blocked on missing intake** → record the exact message and **STOP**. Q1-B needs the staged-provisioning fixture. That is a clean, valuable answer.
- **(c) Blocked on missing destination** → record the exact wording and stop. That would be an F15 regression and matters on its own.

### Steps 2–6 — only if the probe returned (a)

2. Walk the Services flow: **questions → recommendations**. Record what each step asks and whether anything blocks.
3. On **recommendations**, select suppliers to build a **shortlist**. Prefer **movers** or **banks** — both have Norway suppliers seeded, which sets up S1. **Record every supplier offered, by name.**
4. Continue to **estimate**. Confirm the **Request quotes** button becomes enabled once the shortlist is non-empty. If it stays disabled with a shortlist present, that is the finding — record and stop.
5. Click **Request quotes** → `/employee/case/{id}/services/rfq/new`. Complete the minimum fields. Record anything that blocks.
6. Submit. Record: confirmation? RFQ reference? **Is a supplier magic link visible anywhere** — a copy-link control, an invite list, a dispatch log? Q2 depends on obtaining one; if links are email-only, say so explicitly.

### Do not

Complete intake (the probe is the point) · type into country fields (use the dropdown — "France" becomes "Franceance") · approve any supplier record · use `insead-2026`.

### Report block

```
CARD: Q1-B            DATE: ____
CAMPAIGN: qa-q1b      CORRIDOR: FR_NO
SESSION LABEL: ____
ASSIGNMENT ID (from URL): ____
CASE ID (if separately shown): ____
BUDGET USED: __/50

⭐ PROBE RESULT: (a) Services opens / (b) blocked on intake / (c) blocked on destination
   Exact message if blocked: ____

VERDICT: PASS / FAIL / BLOCKED / NOT-RUN

WHAT I OBSERVED (facts only):
  ____

SUPPLIERS OFFERED ON RECOMMENDATIONS (by name): ____
REQUEST QUOTES BUTTON: enabled once shortlist non-empty? ____
RFQ SUBMITTED: yes (ref: ____) / no (blocked at: ____)
SUPPLIER LINK OBTAINABLE FROM UI: yes (where: ____) / no — email only

🔴 CRITICAL (report first, stop the batch): ____

FOR COWORK — DB VERIFICATION:
  Tables: rfqs / rfq_items / rfq_recipients (expect the write here, NOT rfq_requests)
  Identifiers: ____

ARTIFACTS TO PURGE (list ALL): ____

BLOCKED BY: ____
```

---

## 4. Standing notes

- **The probe result is the deliverable**, even if it is (b). A clean "blocked on intake, exact message X" tells us the harness is required and is worth the session.
- **`qa-q1` artifacts from your last run still need purging** — Cowork will handle it; your list was complete and correctly flagged the mutated case state.
- **Do not start S1 yourself.** It reuses the Q1-B RFQ and needs Cowork's DB check first to confirm the write landed in `rfqs`.
