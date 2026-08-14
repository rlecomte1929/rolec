# ReloPass Beta Test Campaign — Spec

**Owner:** Romain Lecomte
**Status:** Draft v2 · 2026-07-04
**Primary objective:** Pipeline generation (warm intros + pilot leads) — usability shakeout and concept resonance are secondary.
**Second objective (v2):** Produce a **traction asset** — hard numbers, named testimonials, and pilot leads Romain can put in front of cofounders and investors.
**Audience for this doc:** build + measurement reference for the corridor stress-test campaign.

---

## 1. Objective and framing

Run a structured, self-serve test of ReloPass across **six locked relocation corridors**, using a **tester-agnostic** model (friends first, potential customers second — same flow, segmented in the data). The campaign optimizes for **warm intros and pilot leads into the pipeline**; usability and comprehension signal are captured as a by-product, not the headline.

Because the corridors are the meaningful unit of this test, the campaign is organized **around the corridor**, not the tester. Each tester exercises the full **HR → Employee** journey on **one assigned corridor**, and we measure completeness and friction *per corridor* so we can rank which corridors are demo-ready.

### 1.1 This campaign is also a traction asset
The test isn't only a product exercise — it's the first thing Romain can point to in a fundraising or cofounder conversation. That changes two things about how it's run:
- **Instrument for the numbers you'll say out loud** (see §6.1). The metrics that land in a pitch (testers, problem-fit %, intros, pilot leads) must be captured from the first invite — top-of-funnel data can't be reconstructed later.
- **Capture proof, not just data.** Named testimonials (with consent), the calibre of who tested, and direct pilot interest are the artifacts that make the numbers credible. These are cheap to collect and impossible to backfill.

### What this campaign can and cannot tell us
- **Can:** where the flow breaks per corridor, whether an outsider understands the value in 60 seconds, which corridors have thin immigration content, **who each tester can introduce us to, who wants a pilot, and quotable proof it resonated.**
- **Cannot (by design):** product-market fit or willingness-to-pay as statistical truth — the testers are not a representative buyer sample. Weight their feedback toward usability and comprehension, and treat the intros, pilot leads, and testimonials as the primary yield.

---

## 2. Locked corridors (the unit of test)

All six corridors below are **locked in** for this campaign. They are **tiered by platform readiness**, which changes what each corridor is actually testing.

| # | Corridor | Code | Origin→Dest ISO | Corridor config | Immigration corpus | Test tier | What it measures |
|---|----------|------|-----------------|-----------------|--------------------|-----------|------------------|
| 1 | Paris → Oslo | `FR_NO` | FR → NO | ✅ `corridors/FR_NO/corridor.yaml` | ✅ ingested | **A — Full** | Depth: does a fully-built corridor hold up end-to-end? |
| 2 | India → Munich | `IN_DE` | IN → DE | ✅ `corridors/IN_DE/corridor.yaml` | ✅ ingested (`20260608100000_ingest_us_fr_in_de_corridors.sql`) | **A — Full** | Depth: second fully-built corridor, non-EU origin |
| 3 | London → New York | `GB_US` | GB → US | ❌ none | ❌ not ingested | **B — Fallback** | Breadth: how does the generic path behave with no corridor knowledge? |
| 4 | Amsterdam → Singapore | `NL_SG` | NL → SG | ❌ none | ❌ not ingested | **B — Fallback** | Breadth: APAC destination, zero corpus |
| 5 | Madrid → Dubai | `ES_AE` | ES → AE | ❌ none | ❌ not ingested | **B — Fallback** | Breadth: GCC destination, zero corpus |
| 6 | Madrid → Dublin | `ES_IE` | ES → IE | ✅ `corridors/ES_IE/corridor.yaml` (+ CSEP pathway) | ❌ not ingested (corpus pending) | **B — Early coverage** | First third-country employment-permit corridor (Critical Skills); config built, moat facts pending corpus |

> **Note on ISO codes:** the UK is `GB` (not `UK`) and Norway's `NO` must be quoted in YAML (bare `NO` parses as boolean false). Any new corridor.yaml must follow the `FR_NO` template exactly.

### 2.1 Decision required before launch — Tier B corridors
The four Tier-B corridors will **run** (the platform falls back to retriever defaults — all trust tiers, `min_similarity=0.25`, global intake questions — see `backend/app/services/corridor_registry.py`), but immigration answers will be shallow because no corpus has been ingested for those destination countries. You have two options:

- **Option A — Test the fallback honestly (recommended for a first pass).** Ship all six as-is. Tier-B corridors become a deliberate stress test of the generic path; "where does an unconfigured corridor visibly break or mislead?" is a legitimate, valuable finding. Cheapest, ships now.
- **Option B — Pre-build the three gaps first.** Add a `corridor.yaml` per gap (clone `FR_NO`) and ingest a minimal immigration corpus for US / SG / AE before testing. Higher fidelity, but each is real work (config + corpus ingest migration) and delays launch.

**Spec default: Option A**, with a clear label in the test UI for Tier-B corridors ("This corridor is in early coverage — expect gaps") so testers don't mistake missing content for a bug and so their feedback is interpreted correctly. Revisit for a second wave.

### 2.2 How corridors are assigned to testers
**Base case (confirmed): one plain link to everyone, server auto-assigns the corridor.** Romain sends a single `relopass.com/test-drive` link to the whole cohort (lowest friction, maximise clicks/completions). The provisioning endpoint auto-allocates one of the six locked corridors per tester via **weighted round-robin favouring Tier-A** (~30% FR_NO, ~30% IN_DE, ~10% each Tier-B), computed from current `test_sessions` counts — see **TD-13** (wave blocker; must ship before the cohort invite). A tester only ever sees the one corridor they were assigned; the allocation is invisible to them.

- **Manual override still available:** an explicit `?corridor=IN_DE` (etc.) link is honoured verbatim, for steering a specific prospect to a specific corridor.
- Corridors themselves are file-based and read-only (git-seeded); there is no per-tenant corridor toggle (out of scope). The assigned `corridor_id` is stored on the test session so every feedback item, event, and survey response can be sliced by corridor.

---

## 3. Tester model (agnostic — but mind the mix)

One flow for everyone; the *segment* is a data dimension, not a different experience.

| Segment | Who | Why they matter | How weighted |
|---------|-----|-----------------|--------------|
| `internal` | Friends, classmates, warm network | Fast, forgiving, good for usability shakeout and pilot | Usability signal only; discount sentiment |
| `prospect` | Potential customers / ICP-adjacent (HR, mobility, corporate) | Real comprehension signal + intro + pilot value + credible testimonials | Weight comprehension, pilot interest, and referrals heavily |

- Each tester self-selects (or is tagged at invite) into a segment. Every feedback row, event, and survey response carries `tester_segment` **and** `corridor_id` so results can be sliced both ways.
- **Tester-quality target (matters for the traction story).** "40 friends tried it" is a weak number; "heads of mobility at multinationals tried it" is a slide. Set an explicit **cross-wave** floor: **≥ 10 `prospect` (real ICP) completers.** Capture each tester's **company, role, and sector/industry** (optional fields in the survey lead-in) so the *calibre* of the pool can be described, not just its size. If the mix skews all-friends, the numbers won't carry weight no matter how good the completion rate.
- **Sector capture + beachhead signal.** The optional **sector** field is the vertical signal — it lets the results say "N mobility leaders *from energy companies* tested it," which supports a focused go-to-market story. With few prospects it is **directional color, not statistical proof** — report it as an early signal, never "validated." If a specific vertical (e.g. energy) is the intended beachhead, **recruit for it deliberately**; capturing sector neutrally then lets real concentration show honestly (avoids confirmation bias). Note: the locked corridors already lean energy-relevant (Oslo, Dubai, Singapore), so steering recruitment toward energy prospects makes "energy-relevant corridors, energy-sector testers" a coherent narrative.
- **Wave-1 caveat (mix).** Wave 1 is friends-heavy (see §8): ~20 `internal` + 5 `prospect`. That is a **shakeout**, not the calibre wave — 5 prospects yields ~2–3 completers, below the ≥10 floor. Treat the ≥10 ICP-completer and sector-confirmation goals as spanning wave 1 **plus a prospect-heavy wave 2** (or raise the wave-1 prospect count if the fundraising narrative is time-sensitive).
- **Identity is synthetic; the label is real.** In-platform accounts are `HR-{FirstName}-{suffix}` and `EMP-{FirstName}-{suffix}`, both flagged `is_test=true`, seeded with fake company + relocation data (fake salary, passport, addresses). The tester's real first name is used only as a human-readable label so feedback maps back to a person; their real name/email/company is captured **only** at the survey step, for follow-up. No real personal data ever enters the relocation flow (GDPR-safe by construction).
- **Duplicate handling:** append a 3–4 char random suffix (e.g. `HR-Romain-7F2`). Collision-proof and still readable.

---

## 4. The test flow (what a tester actually does)

1. **Land on `/test-drive`** — plain-language value prop, the goal of the test, the fake-data reminder, 2–3 short (45–90s) videos, corridor label, and one **Start** button.
2. **One-click provisioning** — enter first name → system creates the `HR-*` and `EMP-*` accounts, seeds fake data, assigns the chosen corridor, drops the tester into the flow. (Reuses `/api/auth/register` + the assignment-claim mechanism; all accounts `is_test=true`.)
3. **HR persona** — walk the HR command center for their seeded case: policy/services setup on the assigned corridor. *Specific task, not "explore":* e.g. "Configure the relocation package and hand it to the employee."
4. **Employee persona** — intake → services & policy → roadmap on the same corridor. *Specific task:* "Complete intake, reach your roadmap, and select a first vendor with an estimated cost."
5. **Throughout** — the persistent **feedback widget** (bottom-right, screenshot capture via `html2canvas` → `feedback` table) is available; testers are told upfront to use it for anything good or bad.
6. **"I've completed my test"** → completion page → **survey** ending in the testimonial, pilot, and intro asks.

Each tester runs **one corridor**. A willing tester can be re-provisioned onto a second corridor (new suffix) if they want to do more — opt-in, never required.

### 4.1 Complement the self-serve with 3–5 live sessions
Self-serve buys breadth and numbers; it does not show you *why* someone hesitated. Run **5–10 moderated live sessions** (screen-share, `prospect` testers) alongside the self-serve wave. It is the highest-insight-per-hour activity in the whole campaign, and doubles as relationship-building with potential design partners and cofounders. Don't let the polished automated flow talk you out of watching a handful of real people use it.

---

## 5. What we're testing (the logic)

Four test lenses, in priority order for a pipeline-first campaign:

1. **Pipeline yield (primary).** Does a completed test reliably convert into a captured warm intro **or a pilot lead**? Measured by intro + pilot-interest rate and quality.
2. **Corridor completeness.** Per corridor: can a tester get from HR setup → employee roadmap → vendor+cost without a dead end? Where does content go missing (esp. Tier-B)? This is the corridor stress test.
3. **Usability / friction.** Where do testers get stuck, confused, or drop off — per step, per persona, per corridor.
4. **Concept resonance.** Can the tester articulate the problem ReloPass solves after doing it once? (Their one-sentence testimonial is the artifact.)

**Test tasks are specific and completion-verifiable** (per CLAUDE.md "goal-driven execution"): each persona has a defined success state (HR: package handed off; Employee: roadmap reached + vendor selected with cost), so completion is measured, not self-reported.

---

## 6. Measurement framework

### 6.1 The headline numbers (define these before a single invite)
Decide the **three numbers Romain will say out loud** in a pitch, and instrument for them now. Recommended headline set:

1. **"N professionals tested ReloPass end-to-end"** — completers, with the `prospect` count called out (the calibre number).
2. **"X% said it addresses a real problem"** — Q3 `Yes` + `Somewhat` share.
3. **"Generated Y warm intros and Z pilot leads"** — the pipeline yield.

Plus a quotable-proof count ("K named testimonials") held in reserve.

**These require the full funnel — capture every stage or the conversion rates are unrecoverable:**

| Funnel stage | Source | Why it matters |
|--------------|--------|----------------|
| Invites sent | invite send, tagged by segment | denominator for every rate |
| Link clicks | per-invite token / UTM on the `/test-drive` link | click-through; the top-of-funnel number investors probe |
| Provisioned | `test_sessions` created | did they actually start |
| Completed | `completed_at` | the core traction number |
| Surveyed | `survey_responses` | feedback + proof captured |
| Intros | referral rows | pipeline yield |
| Pilot-interested | Q6 `Yes`/`Maybe` | the warmest yield |
| Testimonials | Q5 with consent | deck-ready proof |

### 6.2 Supporting metrics
| Metric | Definition | Target (first wave) |
|--------|------------|---------------------|
| **Warm intros + pilot leads** | intros captured + testers wanting a pilot | **≥ 8 intros, ≥ 3 pilot leads** |
| **Intro/pilot rate** | (intros + pilot-yes/maybe) ÷ `prospect` completers | **≥ 50%** |
| Test completion rate | testers reaching "completed" ÷ testers who hit Start | ≥ 40% overall |
| `prospect` completers | real ICP testers who finished | **≥ 10** (calibre floor) |
| Named testimonials | Q5 answers with quote consent | **≥ 6** |
| Corridor completion rate | completions with no reported dead-end, per corridor | Tier-A ≥ 80%, Tier-B measured (baseline) |
| Task success rate | HR handoff reached; Employee roadmap + vendor+cost reached | ≥ 80% (Tier-A) |
| Distinct usability issues | de-duplicated issues from feedback widget | tracked, not targeted |
| Time-to-complete | median minutes Start → completed | ≤ 20 min |

> Pipeline verdict: **8 intros + 3 pilot leads + 6 named testimonials from ~15 completions is a successful campaign** even if product sentiment is lukewarm — that's a fundable slide.

### 6.3 Instrumentation (reuse existing)
- **Feedback:** reuse `FeedbackWidget.tsx` + `feedback` table + `AdminFeedback.tsx`. **One change:** add a `campaign` field (e.g. `insead-corridor-2026`) plus `corridor_id` and `tester_segment` stamps so every item is sliceable by campaign / corridor / segment.
- **Funnel / drop-off:** lightweight event logging on the key steps (invite-sent, click, Start, HR-handoff, intake-start, roadmap-reached, vendor-selected, completed, surveyed). This is what powers §6.1. Even a minimal event table beats self-report.
- **Completion + survey:** completion page → survey (below).

### 6.4 The survey (7 questions — only 3 require typing, all optional)
Full copy in `test-drive-copy.md`. Structure:
1. **Overall** (1–5, one tap).
2. **Biggest struggle / where did you get stuck?** (optional text).
3. **Does this solve a real problem you recognize?** (yes / somewhat / no + one line) — feeds headline #2.
4. **One thing you'd change.** (optional text).
5. **Testimonial (proof):** "In one sentence, how would you describe ReloPass to someone in your field?" + **quote-consent checkbox** — feeds the testimonial count.
6. **Pilot interest (primary):** "Would you or your company want to run a real pilot?" (Yes / Maybe / Not now + note) — the warmest yield.
7. **Intro:** "Who else should I talk to?" — name + contact, optional, attribution consent.

Lead-in captures name, email, **company/role**, and **sector/industry** (the calibre + beachhead signal). The high-value asks (5–7) sit last, where goodwill is highest.

### 6.5 Referral + pilot → pipeline (the payoff)
On submit: Q7 (intro) creates a row in the existing **`prospect_candidates`** pipeline (`admin_prospects.py`) tagged `referred_by` + `corridor_id`. Q6 (`Yes`/`Maybe`) flags the **tester's own** record as a warm pilot lead — a tester who wants a pilot is worth more than a cold referral. Both route into the enrich → triage → outreach workflow you already have.

### 6.6 Reporting
Slice every result two ways — **by corridor** (which corridors are demo-ready?) and **by segment** (discount `internal` sentiment, weight `prospect`). Weekly rollup during the campaign; a closing synthesis that (a) ranks the six corridors by completeness/friction, (b) states the three headline numbers, and (c) lists every intro, pilot lead, and testimonial with follow-up status. The Admin dashboard (build plan §2.8) renders this live.

---

## 7. Build items (reuse map)

Ordered by value for a pipeline-first campaign. Reuse is maximized; only a handful of new builds. Full detail in `test-drive-build-plan.md`.

| # | Item | Build vs reuse | Notes / files |
|---|------|----------------|---------------|
| 1 | **Survey → intro + pilot + testimonial capture** | **Build (small)** | Highest value. Wire Q5–Q7 into `survey_responses` + `admin_prospects.py`. |
| 2 | **Funnel instrumentation** | **Build (small)** | Invites-sent + clicks + stage events — powers the headline numbers (§6.1). |
| 3 | **One-click dual provisioning** | **Build (medium)** | First name → `HR-*`/`EMP-*`, `is_test=true`, seed fake data, assign one corridor. Reuses `/api/auth/register` + assignment-claim. |
| 4 | **`/test-drive` landing page** | **Build (small, mostly content)** | Clone `GetStartedPage` + `PublicLayout` + `routes.ts`. Videos = Playwright/Loom. |
| 5 | **Feedback campaign/corridor/segment tags** | **Build (tiny)** | Add `campaign`, `corridor_id`, `tester_segment` to `feedback` + widget stamp. |
| 6 | **Completion page + survey + email fan-out** | Build (small) | Notify Romain + thank tester (reuse Resend path). |
| 7 | **Admin Test-Drive dashboard** | **Build (medium)** | Scorecard + funnel + pilot leads + testimonials + contacts; clone `AdminFeedback`. |
| — | **Per-tenant corridor toggle** | **Do NOT build** | Restrict via seeded assignment instead (§2.2). |
| — | **Tier-B corridor configs + corpus** | **Deferred (Option B)** | Only if you choose fidelity over speed (§2.1). |

---

## 8. Rollout plan — run it as a launch moment

1. **Phase 0 — define done (now).** Lock the three headline numbers (§6.1) and these targets. This is the definition of success.
2. **Phase 1 — pilot with 3, from 15 Jul 2026.** Run the full flow with 3 people (one Tier-A, one Tier-B, one free). The provisioning endpoint *will* break on first real run — find it here. Fix, then open the wave a few days behind. **Timeline note:** 15 Jul is ~10 days from spec date — the build (§7) + pilot must fit, which is achievable only with tight scope (captions-only videos, no gold-plating). 15 Jul is the *pilot* start, not 40 people on day one.
3. **Phase 2 — full wave, time-boxed to ~2 weeks.** Wave 1 composition: **~20 `internal` + 5 `prospect`** (see §3 wave-1 caveat; plan a prospect-heavy wave 2 for the calibre numbers). Treat it as a **launch, not a trickle** — a defined window is what makes it promotable:
   - **Announce** ("ReloPass is open for testing") at open.
   - **Mid-point signal** ("20 professionals in so far").
   - **Closeout** with the headline numbers — a post/update you can point cofounders and investors to.
   Run the 3–5 live sessions (§4.1) inside this window. Kickoff message, mid-point reminder, closing nudge. Expect heavy drop-off (40 start → ~12–18 complete). Keep each run ≤ 20 min.
   - **Reciprocity:** offer testers the aggregate results back ("I'll send you what we learned"). It lifts completion, which improves every number you'll quote.
4. **Phase 3 — synthesis + follow-up.** Rank corridors, action top-5 usability issues, publish the closeout numbers, and — critically — **follow up on every intro and pilot lead within 48 hours** with a prepared template, while goodwill is warm. Decide this cadence *before* launch; warm leads rot in a dashboard.

---

## 9. Risks and mitigations
- **Friendly bias masks real problems.** → Specific task prompts (not "explore"); ask about *struggles* explicitly; discount `internal` sentiment; enforce the `prospect` floor (§3).
- **Weak tester mix undercuts the traction story.** → Target ≥ 10 ICP completers; capture company/role; recruit prospects deliberately, not just friends.
- **Top-of-funnel data lost.** → Instrument invites-sent + clicks *before* the first invite (§6.1); it can't be backfilled.
- **Tier-B thin content read as bugs.** → Label Tier-B corridors in-UI as early-coverage; interpret their feedback accordingly.
- **Wrong-audience PMF noise.** → Don't measure willingness-to-pay as truth; measure usability + intros + pilot interest.
- **Completion drop-off.** → ≤ 20-min flow; pilot-tuned; reminders; reciprocity offer.
- **Warm leads go cold.** → 48-hour follow-up cadence, template ready before launch.
- **Test data polluting prod.** → Every account `is_test=true`; `test_data_filter.py` keeps it out of dashboards; wipe after campaign.
- **Referral = third-party PII** (GDPR). → Capture minimally; rely on tester attribution consent; mask before any LLM enrichment (`pii_masker`, per CLAUDE.md). Running the whole test on synthetic data is itself a credibility point with enterprise-minded investors — say so.

---

## 10. Decisions log (resolved 2026-07-04)
1. **Headline numbers:** ✅ Confirmed set (§6.1) — testers completed (+ ICP count), % problem-fit, intros + pilot leads; testimonials in reserve. **+ Sector field added** to the survey lead-in as the beachhead signal (report as directional, not proof — see §3).
2. **Tier-B corridors:** ✅ **Option A** — test on fallback now, to speed go-to-market. Revisit for wave 2. (§2.1)
3. **Corridor assignment:** ✅ **One plain link to everyone; server auto-assigns via weighted round-robin (Tier-A favoured)** — TD-13, wave blocker. Manual `?corridor=` override retained. (§2.2)
4. **Wave size + timing + mix:** ✅ Wave 1 = **~20 `internal` + 5 `prospect`**, pilot opening **15 Jul 2026**. ⚠️ 5 prospects is below the ≥10 ICP-completer floor — plan a **prospect-heavy wave 2** (or raise wave-1 prospects). Timeline is tight; keep scope lean. (§3, §8)
5. **Live sessions:** ✅ **5–10 moderated sessions** in the wave, `prospect` testers. (§4.1)

### Still open
- **Wave-2 prospect target + date** — to actually hit ≥10 ICP completers and a credible sector concentration.
- **Pilot vs full-wave date split** — confirm 15 Jul = pilot (3 people), full wave ~18–20 Jul once the pilot is clean.

---

### Appendix — corridor code reference
`FR_NO` (Paris→Oslo, Tier A) · `IN_DE` (India→Munich, Tier A) · `GB_US` (London→New York, Tier B) · `NL_SG` (Amsterdam→Singapore, Tier B) · `ES_AE` (Madrid→Dubai, Tier B).
