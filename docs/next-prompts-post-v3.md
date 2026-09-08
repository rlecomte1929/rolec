# Post-V3 — three prompts for three tools

**V3 passed at the data layer.** The first RFQ in the product's history landed in `rfqs` (1 row), `rfq_items` (2), `rfq_recipients` (6 — matching the shortlist), and `rfq_requests` got **0**. Canonical model confirmed by a real write. SMOKE-1 is closed.

Two follow-ups, split by tool:

- **Claude Code** → fix the fixture currency literal (P3, already filed).
- **Audos** → CARD Q2/Q3, rescoped to the HR-mediated dispatch (V3 proved there is no employee-facing magic link).
- **Cowork (me)** → DB verification after Q2/Q3, standing by.

---
---

# PROMPT A — CLAUDE CODE (one small task)

Paste from repo root. Base off current `main`.

## Fix the staged-fixture hardcoded currency *(Notion: "fixture hardcodes displayCurrency='EUR'")*

**Branch:** `fix/staged-fixture-currency`

**Problem:** `backend/app/routers/test_drive.py:644` hardcodes `"displayCurrency": "EUR"` in the intake draft the staged provisioner writes. So a seeded FR_NO (Oslo) session displays EUR, while a hand-walked one correctly shows NOK. This breaks the fixture's own contract — "a seeded session and a hand-walked one produce equivalent DB rows."

**Do:**
1. Replace the `"EUR"` literal with a value derived from the corridor's destination country. `TEST_DRIVE_CORRIDOR_ROUTES` already maps each corridor to `host_country` (used ~line 397 for vendor seeding) — use the same source.
2. Route it through `backend/app/services/fx_service.py::normalize_display_currency` rather than any new literal.
3. `grep test_drive.py` — confirm no hardcoded currency literal remains.
4. Test: a minted FR_NO staged session resolves to NOK; a non-covered corridor falls back sanely (fx_service default).

**Do NOT** touch the real intake path or production currency resolution — this is the QA-fixture line only.

Report: branch · SHA · PR · test output.

---
---

# PROMPT B — AUDOS (CARD Q2/Q3, self-contained)

Paste as text. Audos mints via curl and drives the browser in one session.

## What V3 established (do not re-litigate)

- ✅ First RFQ submitted; landed in `rfqs` with 6 recipients. SMOKE-1 closed.
- ✅ The model is **HR-mediated**: employee shortlists → sends to HR → **HR** requests quotes from vendors → employee chooses. **There is no employee-facing supplier magic link** — that was the answer to V3 step 6, and it's correct, not a defect.
- So Q2 (supplier submits a quote) and Q3 (quote returns to requester) run from the **HR side**, not the employee side.

## The open question this card answers

**When HR dispatches the RFQ, how does the supplier receive it — a magic link visible/copyable in the HR UI, or email-only?** That determines whether a supplier can actually be reached, and it's the last unknown before the RFQ loop is fully proven.

## STEP 0 — mint a staged session, capture BOTH credential sets

```bash
curl -sX POST https://api.relopass.com/api/test-drive/provision-staged \
  -H 'Content-Type: application/json' \
  -d '{"first_name":"RfqQ2","campaign":"qa-q2","corridor_id":"FR_NO","stage":"shortlist_ready"}'
```

From the JSON, record: `employee.email` + `employee.password`, **`hr.email` + `hr.password`** (you'll need HR this time), `session_id`, `case_id`, `assignment_id`.

- 404 → test-drive flag off / gate rejected → stop, report the body.
- empty `shortlist` → seeding intermittency; re-run once with `"first_name":"RfqQ2b"`, then stop if it recurs.

## STEP 1 — submit the RFQ as the employee (~6 actions)

1. `/auth?mode=login`, decline banner, sign in as **employee**. Type by keyboard.
2. You land at Review & budget with a shortlist. Open the RFQ page (`Request quotes`), fill the minimum move detail, **submit**. Record the confirmation.

## STEP 2 — ⭐ the HR dispatch, as HR (the new part)

3. Sign out. Sign in as the **HR** account from Step 0.
4. Find the RFQ the employee just created — look under the case, an RFQ/quotes inbox, or Service providers. Record where it lives and its status.
5. ⭐ **Look for how suppliers get contacted.** Is there:
   - a **"Send to suppliers" / "Request quotes" / "Dispatch"** control on the HR side?
   - after dispatch, a **copyable supplier link**, an **invite list**, or a **recipient/status panel** showing each supplier's state?
   - or does the UI say the request was **emailed** with no visible link?
6. If a supplier link **is** obtainable: copy it. That unblocks Q2 — open it in a clean context and submit a quote (amount `1234`, note `QA test`). Then sign back in as HR and confirm the quote appears (Q3).
7. If dispatch is **email-only** with no visible link: record that precisely and **stop** — Q2/Q3 then need a different route (a dev/preview endpoint or the email itself), which is a Cowork/Claude Code question, not a browser one.

### Rules
Type by keyboard · PageDown for wheel-ignoring inner containers · click custom controls by coordinate · never `insead-2026` · never set `OUTBOX_DISPATCH_CRON_ENABLED` · approve no supplier records · a blocked path is a finding.

### Report block
```
CARD Q2/Q3   DATE ____   CAMPAIGN qa-q2
STEP 0: HTTP ____  shortlist non-empty? ____  session ____ case ____ assignment ____
Employee RFQ submitted? ____  confirmation: ____

HR-SIDE DISPATCH:
  RFQ visible to HR at: ____
  Dispatch control present? ____ (label: ____)
  After dispatch — supplier link obtainable in UI? yes (where: ____) / no — email only
  Recipient/status panel present? ____

IF LINK OBTAINABLE:
  Q2 supplier quote submitted? ____  amount 1234  errors: ____
  Q3 quote visible back to HR? ____

🔴 CRITICAL: ____
FOR COWORK — DB: rfqs / rfq_items / rfq_recipients for case ____ ;
  quotes / quote_lines if a quote was submitted; rfq_recipients.token_hash present?
ARTIFACTS TO PURGE: qa-q2 session + case + RFQ (+ quote)
BLOCKED BY: ____
```

---
---

# PROMPT C — COWORK (me, no action needed from you)

I run the DB verification once Audos reports: confirm the second RFQ + recipients, and if a quote was submitted, that it landed in `quotes`/`quote_lines`. If Audos hits "email-only, no visible link", I'll check whether a token can be surfaced through a safe dev path — but `rfq_recipients.token_hash` is hashed, so a plaintext token likely only exists at dispatch time, which would itself be the finding.

---

## Sequence

```
A (Claude Code, currency fix)  ──  independent, ship anytime
B (Audos, Q2/Q3 dispatch)      ──  run now; answers the last RFQ-loop unknown
C (Cowork verify)              ──  after B reports
```

Prompt A and Prompt B are independent — run them in parallel. B is the one that closes the RFQ loop.
