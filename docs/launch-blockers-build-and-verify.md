# Launch blockers — build brief + Audos verification cards

**Four launch-blocking items. All four are code → Claude Code builds them. Three are browser-verifiable → Audos confirms each after it ships.**

```
BUILD (Claude Code)                          VERIFY (Audos, after each ships)
────────────────────                          ───────────────────────────────
B1  outbox allowlist merge  (5f3baf0e)   →   (unit test / DB — not browser; Cowork)
B2  provisioning default fix              →   V1  provision on plain link → check attribution
B3  vendor seeding intermittency          →   V2  provision 5× → every one shows suppliers
B4  staged fixture (shortlist_ready) P0   →   V3  ?stage=shortlist_ready → submit the first RFQ
```

**Sequence:** B1 first (safety, standalone). B2 + B3 together (both one-line-ish `test_drive.py` fixes). B4 last (the biggest, and it unblocks the most). Audos runs each V-card only when told its B-item is live.

---
---

# PART 1 — CLAUDE CODE BUILD BRIEF

Paste into Claude Code from the repo root. Base off current `main`. **One branch + one PR per item. Do not combine.**

### Rules that bind

- New/changed router → register in **both** `backend/main.py` and `backend/app/main.py`, verify: `python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if '<prefix>' in r.path))"`
- New `public` table → `ENABLE ROW LEVEL SECURITY` + a policy + `REVOKE ALL FROM anon`.
- Never apply a migration; commit the file, operator applies out-of-band.
- Never log raw user input — `safe_log_text()`.
- `cd frontend && npx tsc --noEmit` and `cd backend && pytest` before every PR.
- One atomic commit per change (Git Trees API), never one-file-per-commit.
- **A task is not done without a commit SHA on a named branch.** Editing the workspace mirror is a no-op.

### B1 — Merge the outbox recipient allowlist ⚠️ first
Branch `5f3baf0e`. Rebase onto `main`, resolve conflicts, open PR, confirm `pytest backend/tests/test_notification_outbox_dispatch.py` passes. **Do NOT set `OUTBOX_DISPATCH_CRON_ENABLED`** — merging the guard ≠ enabling the cron. Report PR URL + SHA.

### B2 — Provisioning campaign default *(Notion: "provisioning still defaults to insead-2026")*
`backend/app/routers/test_drive.py` provision handler. Absent campaign → `NULL`/`unattributed`, never `insead-2026`. Keep explicit `?campaign=insead-2026` working. Mirror AIQ-1639 (`bf725c34`) exactly. Regression test: provision path never writes `insead-2026` unless explicitly passed. Branch `fix/provision-campaign-default`.

### B3 — Vendor seeding intermittency *(Notion: "vendor seeding is intermittent — 63%")*
`test_drive.py` vendor-selection seeding (AIQ-1651 + follow-up `2031a050`). Diagnose why it fires ~63%. **Failures must emit a structured error** (company id + corridor + exception), never a swallowed warning — the swallow pattern already caused a P0. Do **not** touch the `company_vendor_selections` filter in `recommendations/router.py` — that filter is the security control. Test: 10 fresh provisions → 10/10 seeded. Branch `fix/vendor-seeding-intermittency`.

### B4 — Staged-provisioning fixture 🔴 P0 *(Notion: "staged-provisioning fixture")*
`POST /api/test-drive/provision?stage=<credentials|case_created|intake_complete|roadmap_ready|shortlist_ready>`. `shortlist_ready` is the priority — returns a session already at Review & budget with a non-empty shortlist. **Reuse the real code paths** (no direct row inserts — that tests a fiction). Gate: `RELOPASS_TEST_DRIVE_ENABLED` + `qa-*` campaign only, never `insead-2026` or a real company. Register in **both** main files. Branch `feat/test-drive-staged-provisioning`.

Report each: branch · SHA · PR · test output · route-registration check where relevant.

---
---

# PART 2 — AUDOS VERIFICATION CARDS

**Each card is held until its build ships. Paste as text, one at a time. Do not run ahead.**

---

## CARD V1 — provisioning attribution *(run after B2 is live)*

**Confirms:** a plain-link provision no longer lands in the live cohort.
**Campaign:** none (deliberately) + `qa-v1` · **Budget:** ~10

1. Go to `https://relopass.com/test-drive` — **no `?campaign=` parameter at all.** Decline the analytics banner.
2. First name `PlainV1`. **Type by keyboard** (programmatic set doesn't fire the handler). Click **Start the test**.
3. Capture the session label. Do not sign in — provision only.
4. Repeat once at `https://relopass.com/test-drive?campaign=qa-v1&corridor=FR_NO`, first name `TaggedV1`.

**Report:**
```
CARD V1  DATE ____
Plain-link session label: ____
Tagged-link session label: ____
FOR COWORK: confirm PlainV1 session has campaign NULL/unattributed (NOT insead-2026);
            TaggedV1 has campaign='qa-v1'.
ARTIFACTS TO PURGE: the two sessions above
```

**PASS** = Cowork confirms PlainV1 is not `insead-2026`. This is the fix that stops the cohort re-contaminating.

---

## CARD V2 — vendor seeding reliability *(run after B3 is live)*

**Confirms:** every provisioned tester sees suppliers, not an empty marketplace.
**Campaign:** `qa-v2` · **Budget:** ~35

**Do this 5 times** (fresh context each):
1. `https://relopass.com/test-drive?campaign=qa-v2&corridor=FR_NO`. Decline banner. First name `SeedV2a` … `SeedV2e`. Type by keyboard.
2. Capture credentials. Sign in as **employee**. Open **Services** → select **Movers** → Preferences → **Get recommendations**.
   - Inner list ignores wheel-scroll → use **PageDown** to reveal the service cards.
3. Record the **Movers count** on the recommendations page.

**Report:**
```
CARD V2  DATE ____   Campaign qa-v2
Movers count per session:  a:__  b:__  c:__  d:__  e:__   →  __/5 non-zero
Any session showing Movers (0)?  which: ____
FOR COWORK: company_vendor_selections rows for each of the 5 companies
ARTIFACTS TO PURGE: 5 qa-v2 sessions
```

**PASS** = 5/5 show a non-zero count. Anything less means the intermittency isn't fully closed — report which.

---

## CARD V3 — the first RFQ, end to end 🎯 *(run after B4 is live)*

**Confirms:** the staged fixture works AND an RFQ can be submitted. This is the run that finally reaches steps 9–12.
**Campaign:** `qa-v3` · **Budget:** ~25

1. Provision via the fixture: `https://relopass.com/test-drive?campaign=qa-v3&corridor=FR_NO&stage=shortlist_ready`.
   - If the URL param isn't how the fixture is triggered, the build report will say how — follow that. If the page still shows the empty start form, the fixture didn't fire → **stop and report**.
2. Capture credentials, sign in as **employee**. You should land at or near **Review & budget** with a shortlist already built. Record where you land.
3. Confirm currency reads **NOK**.
4. ⭐ Click **Request quotes** → complete the minimum fields → **submit**. Record confirmation, RFQ reference, any error. **This is the first RFQ ever submitted through the product.**
5. ⭐ Record whether a **supplier magic link** is visible anywhere — copy-link, invite list, dispatch log. If email-only, say so. **Q2/Q3 depend on this answer.**
6. Return to `/test-drive?campaign=qa-v3&corridor=FR_NO`, confirm session survived navigation, click **I've completed my test** → complete + submit the survey.

**Report:**
```
CARD V3  DATE ____   Campaign qa-v3
Fixture landed employee at: ____ (expect Review & budget w/ shortlist)
Currency: ____ (expect NOK)
⭐ RFQ SUBMITTED? ____  Reference: ____  Errors: ____
⭐ Supplier magic link visible? yes (where: ____) / no — email only
Session survived navigation? ____   Survey submitted? ____
FOR COWORK: rfqs / rfq_items / rfq_recipients (expect write HERE, not rfq_requests);
            survey_responses (campaign='qa-v3', non-null session_id + corridor_id)
ARTIFACTS TO PURGE: qa-v3 session + case + RFQ
```

**PASS** = an RFQ row lands in `rfqs`. That closes SMOKE-1 and, if step 5 shows a link, unblocks Q2/Q3 in the same run.

---

## Standing rules (all V-cards)

Type by keyboard, never set fields programmatically · PageDown for wheel-ignoring inner containers · click custom controls by coordinate, never by ref · country fields use the dropdown · never `insead-2026` · never set `OUTBOX_DISPATCH_CRON_ENABLED` · approve no supplier records · a blocked path is a finding · stop before the budget cap, never mid-action · **run one card per session, only when told its build is live.**
