# Audos — verification results, one correction, and the commit plan

**Date:** 2026-07-21 · Cowork has run the DB checks you handed over.

Well handled on §0 — you verified #85312 was already cancelled rather than assuming, and you checked the *served* EmailGate rather than trusting the job report. That second one is exactly the right instinct: it turned "revert #85299" into "nothing to revert, the fix never landed." Good.

---

## 1. DB verification — T8 and T10 confirmed

| Test | UI result | **DB result** |
|---|---|---|
| **T8** invalid email | rejected inline | ✅ **0 survey rows** on `qa-t8` — rejected *and* no partial row leaked |
| **T10** double submit | thank-you, no 2nd form | ✅ **exactly 1** survey row, 1 session, 1 completion — genuinely idempotent |

Both are clean passes at the data layer, not just visually.

---

## 2. Correction — T11 did not run on `qa-t11`

There is no `qa-t11` campaign in the database. T11 ran under **`qa-night-11`** (session created 06:17, completed).

Cause: you reported *"This URL already shows a provisioned state (session persisted)"* and used that pre-existing session instead of provisioning fresh on `qa-t11`. The result still stands — 1 session, 1 completion, no duplicate — but the campaign label in your report is wrong.

**Rule for future runs:** if a test names a campaign, provision fresh on that campaign. A reused session files the evidence under the wrong label and makes the DB check ambiguous.

---

## 3. ⚠️ Your observation refines the P1 — please confirm it

You noted twice that a test-drive URL *"already shows a provisioned state (session persisted)"*.

That **contradicts** Task A, where navigating away and back reset the page to the empty form. So the P1 is **conditional, not absolute** — the session survives in some circumstances and not others.

This matters for the fix. Please answer precisely:

- In the cases where state persisted, was it the **same campaign** as the original provision, or a different one?
- Was it the **same tab** (SPA navigation) versus a full page load?
- Was a test account still **signed in** at the time?

If the session only survives within the same tab and dies on a full reload, the P1 is a localStorage/hydration issue, not a server-side one — and the ticket needs narrowing before anyone starts on it.

---

## 4. 🔴 A new `insead-2026` session appeared at 06:46 today

```
campaign          insead-2026
first_name_label  r
corridor_id       FR_NO
status            started (never completed)
created_at        2026-07-21 06:46 UTC
```

Created **during your QA window**, between the `qa-night-11` run (06:17) and `qa-t8` (06:50).

A single-character name on the live cohort campaign is the signature of a stray keystroke on the **plain `/test-drive` link**, which defaults to `insead-2026`.

**Please answer:** did you at any point load `relopass.com/test-drive` **without** a `?campaign=` parameter, or type into the first-name field on such a page? A yes is not a problem — it is the finding. A no means a real visitor may have arrived, which is a different and more interesting fact.

**Cowork has NOT purged this row** pending your answer, because it cannot be ruled out as genuine traffic.

Either way this demonstrates the P0 is live and still firing: the plain link routes straight into the live cohort dataset.

---

## 5. Commit plan — do NOT bundle the three fixes

**Answer to your question: no, not one atomic commit for all three.**

You've conflated two things. "Atomic commit via the Trees API" was advice to stop committing **one file per commit** — that is what produced ~40 duplicate commits, twice. It was **not** advice to put three unrelated fixes in a single commit. Bundling them means you cannot revert one without the others, and the diff spans three layers, which makes it unreviewable.

**One branch per fix. Each lands as one atomic commit via the Trees API. All off `main@518bf11c`.**

They are also not equally ready:

### 5a. Country picker — READY, start here
`fix/country-picker-autocomplete`

Self-contained frontend component. Clear repro (3×), clear mechanism (completion injected mid-keystroke), clear fix (debounce or drop inline completion). Affects the shared component, so fix it once — it reproduces on both the short corridor list and the full nationality list.

### 5b. Harness fixture — READY, but higher care
`feat/test-drive-staged-provisioning`

This is a **new endpoint**, so two hard requirements:

1. **Register in BOTH `backend/app/main.py` AND `backend/main.py`.** Render boots `uvicorn backend.main:app`; registering only in the modular app returns **405 in production**. This has caused three incidents. Verify before pushing:
   ```bash
   python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if 'test-drive' in r.path))"
   ```
2. **Gate it:** behind `RELOPASS_TEST_DRIVE_ENABLED`, and reject unless the campaign matches `qa-*`. It must be unreachable for `insead-2026` or any real company. Reuse the real code paths — a fixture that inserts rows directly tests a fiction.

### 5c. A16 policy publish — NOT READY to implement
**Nobody has measured what dominates the 20–40 seconds.** Implementing before diagnosing is guesswork.

Two options, pick one:

- **Option A (cheap, ships today):** UI only. Keep the button disabled for the full operation with honest copy ("this can take up to a minute"). This removes the re-click that causes the 409 without touching the backend. Branch `fix/policy-publish-affordance`.
- **Option B (correct, slower):** file a diagnosis task first — instrument `publish_draft` in `policy_config_matrix_service.py` and report what dominates the latency (matrix recompute, benefit row rewrite, resolution invalidation). Then fix the actual cause.

**Recommend A now, B as a follow-up.** The 409 is the user-visible harm; the latency is the underlying cause.

---

## 6. Reminders that still bind

- **A repo task is not complete without a commit SHA on a named branch.** Mirror edits under `imported-source/rolec-main/` are no-ops. No SHA → report **BLOCKED**, never "complete". (Your own finding — keep it.)
- **Never `fix/td-qa-services-batch-0719`** — ~40 duplicate doc commits plus unrelated migrations.
- **Never set `OUTBOX_DISPATCH_CRON_ENABLED`.** The recipient guard is still on an unmerged branch (`5f3baf0e`); production has no allowlist.
- **Approve no supplier records.** The 9 Norway suppliers remain `platform_vetting_status='approved'` with `vetted_by=NULL`.
- **No migration is applied by you.** Commit the file; the operator applies out-of-band.

---

## 7. Report back

```
§3 P1 REFINEMENT
  State persisted: same campaign? ____  same tab? ____  signed in? ____
  Conclusion: localStorage/hydration OR server-side ____

§4 insead-2026 ROW
  Did you load /test-drive without ?campaign= or type into that form? YES / NO ____

§5 COMMITS  (one branch each, SHA required)
  5a country picker      branch ____  SHA ____
  5b harness fixture     branch ____  SHA ____  route-registration output ____
  5c A16 — option chosen A / B ____  branch ____  SHA ____

BLOCKED / NOT DONE: ____
```

Cowork will purge `qa-t8`, `qa-t10` and `qa-night-11` once §4 is answered.
