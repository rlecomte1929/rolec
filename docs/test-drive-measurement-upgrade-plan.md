# Test-Drive Measurement Upgrade — goals, plan, metrics, verification

**Owner:** Romain · **Status:** Plan for approval · 2026-07-15
**Purpose:** turn the specialist recommendations into an implementable plan with measurable success criteria and a confidence gate, so we run the cohort only once the measurement layer is proven.

---

## 0. The governing principle (read first)

At ~25 friendly testers, **conversion percentages are statistically meaningless** — the error bars are enormous. So this upgrade does **not** add more counters. It builds the layer that produces *understanding*: hearing from everyone (not just finishers), seeing *why* people struggle, and turning high-signal testers into conversations. Every item below is judged by one test: does it help us understand **why**, or just count **what**? Anything that only counts is deprioritised.

---

## 1. Goals

**G1 — Hear from 100% of testers, not just finishers.** Recover the dropout voice (currently silent; the most informative segment).

**G2 — Understand the *why* behind every hesitation and drop-off.** Move from "10 dropped at intake" to "10 stalled on the document field for 4 minutes."

**G3 — Capture predictive signal, not just agreement.** Add trust/intent-to-use, the signal that actually forecasts a pilot and a raise — beyond "does this solve a problem?"

**G4 — Convert high-signal testers into conversations automatically.** Anyone who wants a pilot, rejects the value, or drops early gets flagged for a personal follow-up.

**G5 — Make the dashboard tell the truth at small n.** Segment-split by default (never blend friends with buyers), weight completion by quality, and compare waves over time.

**Overarching (G0) — Confidence to run.** Reach a state where every intended signal is proven to land end-to-end, on clean data, before a single cohort invite goes out.

---

## 2. Scope decisions — what we are and aren't doing

- **Invite counter: simplify, don't extend.** Keep a single "invited ≈ N this wave" number (so completion-off-invites is computable — investors ask). **Drop the channel/segment granularity** — at this scale it's noise. No per-person invite links (fights the one-link model).
- **Not building at n=25 (defer to a later wave):** heavy statistical dashboards, cohort A/B tests, anything whose value only appears at scale.
- **Bought, not built:** session replay (§W2). Building recording is wasted effort.
- **Hard constraint throughout:** everything runs only on **test-drive / `is_test`** sessions and a **qa campaign** during build; no real customer data recorded; PII masked before any third party; zero Resend dependency added.

---

## 3. Workstreams

Each workstream states the goal, exactly what I want, the implementation plan (mapped to the existing system), the **implementation metrics** (how we know it's built right), and its verification.

### W0 — Identity capture at the START  *(serves G1, G4 · PRIORITY 0 — foundation)*

**What I want:** capture the tester's real **name + email at provision** (beside the first name), so every session — including dropouts — is tied to a reachable person. Framed as a convenience ("we'll generate/optionally email your two logins"), required-but-gentle.

**Plan:** add `tester_name` + `tester_email` to `test_sessions` (additive migration); provision endpoint stores them; the `/test-drive` start form gains an email field; the survey lead-in **pre-fills** from the session instead of re-asking; the page's data-honesty copy is corrected to distinguish the **real contact email (follow-up only)** from the **synthetic relocation data**.

**Implementation metrics:** 100% of provisioned sessions carry a real `tester_email`; an abandoned session still has the contact; the survey pre-fills; the page no longer claims "nothing is personal."

**Verification:** provision → session has name+email; abandon mid-flow → contact still present; open survey → pre-filled; read the page → honest split between contact email and synthetic data.

**Why it's first:** W1 (dropout follow-up) and W5 (follow-up engine) are only possible once every session has a reachable contact. This replaces W1's optional in-modal email field.

### W1 — Dropout / friction capture  *(serves G1, G2 · priority 1)*

**What I want:** when a tester stalls on a stage or tries to leave without advancing, a one-tap prompt — "What stopped you here?" — with quick reasons (confusing · broken · boring · no time · other + optional text), plus an optional "leave your email if you're happy for me to follow up." Every answer is tied to the session and the stage they were on.

**Plan:**
- Trigger on exit-intent (route-away / `beforeunload` / tab-hide) and on an idle-on-stage timeout, **only** when the current stage hasn't advanced.
- Store as a `friction` event in the existing **`funnel_events`** table (`event_type='friction'`, metadata = `{stage, reason, text, email?}`) — no new table.
- Constraint: dropouts have **no email** (email is captured at survey, which they never reached), so recovery must happen **in-flow**; the optional email field is the only way to re-contact them — keep it optional and low-friction.

**Implementation metrics:**
- In a QA dry-run of 10 deliberate abandonments, **≥ 8** produce a `friction` event or an explicit dismissal (we captured the moment, not silence).
- Friction events carry a non-null `stage` and a `reason` in 100% of submissions.
- The prompt never fires for a tester who advanced normally (0 false triggers in a clean happy-path run).

**Verification:** start a session, reach intake, abandon (close tab / navigate away) → a `friction` row appears with the correct stage; submit a reason → persisted; complete a normal flow → no prompt fired.

### W2 — Session replay  *(serves G2 · priority 2 · buy, don't build)*

**What I want:** watch recordings of testers using the flow, one per session, linkable from each dashboard row.

**Plan:**
- Integrate a replay tool. **Recommended: PostHog (EU cloud)** — replay + events + funnels in one, generous free tier, EU-hosted / self-hostable (fits the compliance positioning). **Alternative: Microsoft Clarity** — free and unlimited, zero cost, but data goes to Microsoft (weaker fit for a compliance-first brand). *Decision needed — see §8.*
- **Gate the SDK to test-drive sessions only** (behind the test-drive session context + campaign flag) — never record the real product.
- Tag each recording with `session_id` so a dashboard row deep-links to its replay.
- Mask PII in recordings (the tester's real name/email at the survey step) even though case data is synthetic.

**Implementation metrics:**
- **≥ 90%** of QA test-drive sessions produce a viewable recording.
- 100% of recordings are reachable from the matching dashboard row (session_id link resolves).
- The SDK does **not** initialise on any non-test-drive page (verify on a normal HR/employee login: no recording).
- Survey name/email are masked in the replay (visual check).

**Verification:** run one full session → recording appears in the tool within minutes, watchable, linked from `/admin/test-drive`; log into the real app as a normal user → confirm no recording is created; inspect a replay → PII masked.

### W3 — Time-on-stage & drop-off context  *(serves G2 · priority 3 · low effort)*

**What I want:** for every stage, how long testers spent and how many fell off between stages — not just that a stage was reached.

**Plan:**
- Stage-to-stage timing is **derivable from existing `funnel_events`** (`created_at` + `session_id`) — no new capture, just computation.
- Ensure enough granularity to measure dwell (a stage-entered signal where only a milestone exists today — confirm during recon; add the minimal missing events).
- Add to `/admin/test-drive`: **median time per stage** and **per-stage drop-off %**, segment-split.

**Implementation metrics:**
- Dashboard shows median time-on-stage and drop-off % for every funnel stage.
- Computed values match a hand-calculation from the raw `funnel_events` for a sample session (±0).
- Timing is available per corridor and per segment.

**Verification:** drive 2–3 flows with deliberate pauses at known stages → dashboard timing reflects the pauses; drop-off math reconciles with a direct DB query.

### W4 — Trust / intent-to-use survey question  *(serves G3 · priority 4 · trivial)*

**What I want:** one added question — *"Would you trust ReloPass with a real relocation?"* (or *"If this existed today, would you use it?"*) — likely-yes / maybe / no + optional why.

**Plan:**
- Add `trust_intent` (enum) + `trust_intent_why` (text) to `survey_responses` (additive migration — note: a migration is **🔴 Red** per the rubric, but tiny and additive).
- Render as one tap in the survey; surface in the dashboard sentiment block, segment-split.

**Implementation metrics:**
- The answer persists to `survey_responses.trust_intent` for 100% of submissions that answer it.
- The dashboard shows a trust/intent breakdown split by prospect vs internal.
- Migration passes the RLS/gate review (additive columns, no new table).

**Verification:** submit a survey with each trust value → column populated correctly; dashboard reflects the distribution.

### W5 — Auto-follow-up engine  *(serves G4 · priority 5)*

**What I want:** a "Follow up" queue that automatically surfaces every tester who (a) said **pilot = yes/maybe**, (b) answered **problem-fit = no**, or (c) **dropped early** (and left an email in W1), each with a one-click action (mailto / LinkedIn) and their context.

**Plan:**
- Compute the union of the three triggers from `survey_responses` + session status + W1 friction emails; rank (pilot-yes first).
- Surface as a dashboard panel **and** an in-app notification (reuses the AIQ-1547 in-app notification work — no Resend).
- One-click thank-you / outreach mailto pre-filled (reuses the TD-12 mailto pattern).

**Implementation metrics:**
- The queue contains 100% of sessions matching each trigger in a seeded test (3 triggers × ≥1 each).
- Each entry has a working one-click action.
- A `pilot = yes` completion fires exactly one in-app notification (0 Resend sends).

**Verification:** seed one session per trigger → all three appear in the queue with correct actions; a pilot-yes fires the in-app notification; confirm no email is sent.

### W6 — Dashboard truth layer  *(serves G5 · priority 6 · partly defer)*

**What I want:** (a) **segment-split by default** (prospect vs internal side by side, not blended); (b) a **completion-quality** composite (reached roadmap + selected vendor + wrote free-text + real time-on-task) to separate genuine engagement from click-through; (c) a **wave-over-wave** date filter to compare cohorts as fixes ship.

**Plan:** dashboard-only changes reading existing data. (a) and (c) are cheap; (b) is a derived score. **Defer (b) and (c) if time is short** — they matter more at wave-2 scale.

**Implementation metrics:**
- Default dashboard view shows prospect and internal columns without changing a filter.
- Completion-quality score is computed and shown per completion (if built).
- A date/wave filter changes the numbers correctly (if built).

**Verification:** open the dashboard cold → both segments visible by default; apply a wave date range → metrics recompute to that window.

---

## 4. Dependencies & sequencing

**Prerequisite — ✅ DONE (shipped in commit `0567a0d6`):** the measurement-integrity fixes **AIQ-1537** (dashboard campaign scoping) and **AIQ-1546** (survey attribution: corridor/campaign from session) are merged and live. The foundation is in place. Four things keep them *meaningful*, and are the actual work now:
1. **Operational discipline (most important):** all QA/verification runs must provision under a **separate `qa-*` campaign**, never `insead-2026` — 1537 only protects the real numbers if test traffic is tagged differently. Confirm prod `RELOPASS_TEST_DRIVE_CAMPAIGN` = `insead-2026` (or unset → defaults to it).
2. **Prove it once in prod:** one qa session → verify the `survey_responses` row carries the correct `corridor_id`, `campaign` *and* `tester_segment`; the dashboard scoped to that qa campaign shows it under the right corridor/segment; `insead-2026` still reads zero.
3. **Close the orphan-survey gap (AIQ-1542):** 1546 derives attribution *from the session*, so a survey with no valid session lands unattributed and dilutes per-corridor analysis. Handle the unlinked-survey case or accept a slow drip of null-attribution rows.
4. **No backfill needed:** the `insead-2026` purge removed all old null-corridor rows, so there is nothing historical to repair.

Then:
- **Phase A — data capture layer:** W1 (dropout) + W3 (timing) + W4 (trust question). These generate the raw signal.
- **Phase B — replay:** W2 (tool decision → integrate → gate → mask → link).
- **Phase C — surfacing:** W5 (follow-up engine) + W6 (dashboard truth).
- **Phase D — the confidence gate:** §6 verification dry-run → §7 gate → invite the cohort.

Order matters: capture before surfacing (you can't display a signal you didn't record), and replay can run in parallel with A.

---

## 5. The campaign KPIs this enables (the purpose)

These are what the dashboard should monitor once the above lands — always **segment-split**:

- **Activation:** % reaching the roadmap (the true "aha"); % selecting a vendor with cost.
- **Diagnostic:** per-stage drop-off % + median time-on-stage.
- **Completion quality:** the composite score, not raw completions.
- **Sentiment:** problem-fit %, avg experience (1–5), and the new **trust/intent** — prospect vs internal.
- **Dropout insight:** top friction reasons by stage (from W1).
- **Pipeline:** completions (with prospect count), pilot leads, warm intros, consented testimonials.
- **Cuts:** completion + sentiment per corridor (Tier-A vs Tier-B) and per sector (the energy hypothesis).

---

## 6. Verification plan (detailed)

Three layers. Nothing is "done" until all three pass on a **qa campaign**, `is_test` data only.

**6.1 Per-workstream** — each workstream's own metrics + verification above (unit/integration tests, DB checks, targeted UI checks). `pytest -k test_drive` and `npx tsc --noEmit` green for every code task; each migration passes the RLS gate.

**6.2 The end-to-end instrumentation dry-run** — one scripted pass that exercises every signal at once, then confirms each landed:
1. **Happy path:** provision → HR case (corridor locked) → handoff → employee → intake → roadmap → vendor+cost → complete → survey (answer trust + pilot=yes + a referral + a consented testimonial).
2. **Abandonment:** a second session that quits at intake → confirm a W1 friction event (and an optional email if provided).
3. **Detractor:** a third session that completes but answers problem-fit=no.
Then verify, with evidence, that **all** of the following landed and are correctly attributed to the right session/corridor/campaign/segment:
   - funnel_events with correct **timings** and stage order (resolves the parked mid-funnel question too);
   - a **friction** event for the abandoner;
   - a **replay recording** for each session, linked from the dashboard, PII masked;
   - the **trust/intent** answer persisted;
   - the **follow-up queue** contains the pilot-yes and the problem-fit-no (and the abandoner if email given);
   - exactly one **in-app notification** per completion, **zero Resend sends**, **zero `notification_outbox` rows**;
   - the **dashboard** reflects all of it, segment-split, with time-on-stage and drop-off populated.

**6.3 Data hygiene & privacy** — all rows `is_test` + under the qa campaign; no test data under `insead-2026`; replay does not fire on the real app; PII masked in replay and never sent to an LLM unmasked; the qa data is cleanly purgeable afterward.

---

## 7. Confidence gate — "ready to run the cohort"

Do **not** send the cohort link until every box is checked:

- [ ] AIQ-1537 + AIQ-1546 merged and deployed (attribution + scoping clean).
- [ ] W1 dropout capture: friction events land on abandonment (≥8/10 in dry-run).
- [ ] W3 timing + drop-off visible and reconciled against raw data.
- [ ] W4 trust/intent question live and persisting.
- [ ] W2 replay: ≥90% of sessions recorded, linked, PII-masked, off on the real app.
- [ ] W5 follow-up queue surfaces all three triggers with one-click actions; in-app notify fires; zero Resend.
- [ ] W6 dashboard defaults to segment-split.
- [ ] §6.2 end-to-end dry-run: **every** signal landed and correctly attributed — one clean pass.
- [ ] §6.3 hygiene: qa/`is_test` only, `insead-2026` still empty, PII masked, purge path confirmed.
- [ ] One human walk-through by Romain: run it as a naive tester, confirm the friction prompt, the survey, and that the admin side shows the full picture.

When all are green, the campaign will not just count what happened — it will explain it, and turn it into conversations.

---

## 8. Priorities & the one decision I need from you

**Build order by value at n=25:** W1 (dropouts) → W2 (replay) → W3 (timing) → W4 (trust) → W5 (follow-up) → W6a (segment-split). **Defer** W6b (completion-quality score) and W6c (wave view) unless they're cheap — they earn their keep at wave-2 scale, not now.

**Decision — ✅ PostHog EU (chosen).** Privacy-aligned (EU-hosted, GDPR-fit for a compliance-first brand), one tool for replay + events + funnels, free tier. Implementation notes for W2: use the **EU ingest host** (`eu.i.posthog.com`); initialise the SDK **only** inside the test-drive session context (gate on the campaign flag) so the real product is never recorded; enable input/text masking so the survey name/email are redacted in replays; and tag each recording with `session_id` (PostHog person/session property) so the admin dashboard row deep-links to the replay.
