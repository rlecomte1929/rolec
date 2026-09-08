# Audos — clarification before you launch

Two answers, then go. **Card R1 is restated in full at the bottom so you can start immediately.**

---

## 1. ⚠️ You do not need any stored credentials — do NOT use `E2E_EMPLOYEE_PASSWORD`

**Every card provisions its own accounts.** There is no shared HR test login, and you should not go looking for one.

The flow is:

1. Navigate to `https://relopass.com/test-drive?campaign=qa-r1&corridor=FR_NO`
2. Decline the analytics banner
3. Type a first name into the "Start the test" form (e.g. `RfqR1`) and click **Start the test**
4. The page then issues **two fresh credential pairs on screen** — one HR, one employee, both `@probe.test`
5. Use those. They are synthetic, disposable, and scoped to a throwaway tenant

**Do not use `E2E_EMPLOYEE_PASSWORD` or any other workspace secret.** That account may belong to a real or shared tenant; provisioning your own is the whole point of the test-drive flow, and it keeps every artifact inside a purgeable `qa-*` campaign.

**Login URL** for signing in with the issued credentials: `https://relopass.com/auth?mode=login`

### "Capture credentials before navigating away" means something specific

Not "retrieve a stored secret." It means: **the moment the page displays the two pairs, write them down**, because the test-drive session does **not** survive navigation (this is a confirmed P1 bug). Navigate away and come back, and the credential panel is gone — the page resets to an empty form and the accounts are unrecoverable.

Two prior runs died exactly this way. Copy both email/password pairs into your run log before you click anything else.

Also note: passwords are generated and have occasionally contained non-ASCII characters, which broke earlier runs. **If a password contains a non-ASCII character, record it and stop** — that is itself a finding worth reporting.

---

## 2. The doc does contain per-card steps — you likely received a truncated copy

Each card in that document has numbered steps, its own campaign name, a budget, and an explicit "Record" list. The standardised report block is at the bottom, verbatim.

You have had repeated trouble reading attachments (web fetch limits, curl fallbacks), so a truncated read is the likely cause rather than a gap in the spec.

**Proceed on the restated R1 below.** When you finish it, say so and the next card will be sent inline as text rather than as an attachment — that removes the fetch problem entirely.

**On selectors and coordinates:** the cards deliberately do not specify them. The UI shifts between builds, and hard-coded coordinates have broken previous runs. Screenshot, locate, click — the rule that matters is *click custom controls by coordinate rather than by element ref*, because ref-clicks silently fail on the segment toggles, consent checkboxes and pilot-interest buttons in this app.

---

## 3. CARD R1 — restated in full. Start here.

**Question:** Where can an RFQ actually be started, and what case state does it require?

**Campaign:** `qa-r1` · **Corridor:** `FR_NO` · **Budget:** ~12 actions · **Submit nothing — map only.**

### Steps

1. Navigate to `https://relopass.com/test-drive?campaign=qa-r1&corridor=FR_NO`. Decline the analytics banner (it overlays the page bottom and blocks clicks).
2. Confirm the page reads **Paris → Oslo**. If it shows any other corridor, stop — the `&corridor=` override is not being honoured, and that is the finding.
3. Enter first name `RfqR1`, click **Start the test**.
4. **Capture both credential pairs into your run log now**, before any navigation.
5. Sign in as the **HR** account at `https://relopass.com/auth?mode=login`.
6. Create a case and assign it to the employee account. **Record the case ID from the URL.**
7. From the case page, look for any RFQ / quote / "request quotes" entry point. Record its **exact label and URL**.
8. Check the HR sidebar — Service providers, Mobility command center — for any other RFQ entry point.
9. Record whether an RFQ can be started **without** the employee having completed intake.

### Known from the code — confirm in the UI

- `POST /api/hr/rfq-requests` exists, so an HR-initiated RFQ should be possible without the employee journey.
- `POST /api/employee/quote-requests` returns **410 Gone** — the employee-initiated path is deprecated. Do not chase it.

### Record

- Every RFQ entry point found: label, URL, which persona
- Whether intake completion is required first
- Whether a service category must be chosen before starting
- The case ID

### Report block — use verbatim

```
CARD: R1              DATE: ____
CAMPAIGN: qa-r1       CORRIDOR: FR_NO
SESSION LABEL: ____   CASE ID: ____
BUDGET USED: __/50

VERDICT: PASS / FAIL / BLOCKED / NOT-RUN

WHAT I OBSERVED (facts only, no interpretation):
  ____

🔴 CRITICAL (if any — report first, stop the batch):
  ____

FOR COWORK — DB VERIFICATION:
  Tables to check: ____
  Identifiers: ____

ARTIFACTS TO PURGE: ____

BLOCKED BY: ____
```

---

## Standing rules

Decline the analytics banner first · click custom controls by coordinate, never by ref · country fields: use the dropdown, **never type** (typing appends to an injected autocomplete — "France" becomes "Franceance") · never use `insead-2026` · never set `OUTBOX_DISPATCH_CRON_ENABLED` · approve no supplier records · a blocked path is a finding, not something to route around · one card per session.
