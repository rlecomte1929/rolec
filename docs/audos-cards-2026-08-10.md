# Audos cards — 2026-08-10 batch

**Four cards. Paste each into its own Otto thread. They are independent — launch all four.**

Audos is idle (Queued 0 / Running 0 / Blocked 0) and agent compute is comped, so the only
real cost of running these in parallel is your review time. Cards A and B are browser QA;
C and D are public-web research with no browser budget cap.

**Before you paste:** clear the READY FOR REVIEW backlog first (28 items as of tonight).
Otto has nowhere to put a result you will not read, and four more reports on top of 28
unread ones is how the last batch got lost.

---

## Shared rules — every card carries this footer verbatim

These are not style preferences. Each one is a failure that already cost a run.

```
RULES (non-negotiable)
- Type by keyboard. Setting a field programmatically does not fire the React handler.
- PageDown for inner scroll containers — they ignore the mouse wheel.
- Click custom controls by coordinate, never by ref. Ref-clicks silently no-op on the
  segment toggle, consent checkbox, pilot-interest buttons and "Add to package".
- Country fields: use the dropdown, never type. Typing corrupts them ("France" ->
  "Franceance").
- Decline the analytics consent banner. It overlays the page and blocks clicks, and it
  reappears after navigation.
- One fixture per browser session. Two fixtures in one browser caused a stale-session
  logout. Confirm the top-right account label before acting.
- Never touch campaign `insead-2026`. Never set OUTBOX_DISPATCH_CRON_ENABLED. Approve no
  supplier records. Apply no migrations. Create no tables. Delete nothing.
- Stripe: test mode only, on-screen test card only. A real payment is stop-everything.
- Label every claim [VERIFIED] (you saw it) or [CLAIM] (you inferred it). You cannot see
  our database or our repo — do not report a fact about either.
- A blocked path is a FINDING, not something to route around. "NONE" is a valid answer.
- A FAIL is not final until you capture the exact failing request (URL + status + body),
  or you say INCONCLUSIVE. An empty panel is not a FAIL until you name the failing request.
- Stop before the budget cap. Never die mid-action.
```

---
---

# CARD A — RUN 004-X close-out (budget ≤20 actions, two jobs)

**Why this card exists:** RUN 004-X was declared *"the final verification gating v0
launch"* and then **no one recorded its outcome**. Two assertions have been sitting
unanswered for two weeks while we treated v0 as shipped. This closes that.

Two jobs. Each has **one** starred assertion. The moment it resolves, record it and
**STOP that job.** Do not chain, do not add adversarial variants, do not pivot.

## Deploy gate — run this first, for both jobs

```bash
curl -s https://api.relopass.com/health
```

**Record the `commit` value, then PROCEED.** Do not stop on an unfamiliar commit.

> Earlier versions of this card pinned an exact SHA and said "if it differs, STOP". That
> gate went stale in **26 minutes** — `main` deployed `0baf6461` over `5aecaa54` while the
> card was being written, and the run halted at 2/20 actions having tested nothing. On a
> repo that deploys several times an hour, an exact-SHA gate mostly catches its own
> staleness.
>
> The gate's real job is **attributing a result to the code that produced it**, not
> deciding whether to run. Recording the commit does that. Reconciling it against the repo
> is our side of the job, and we can see the repo — you cannot.

**Only stop if `/health` itself fails** (non-200, timeout, or no `commit` field). That is a
genuine finding: report the status and body.

For reference, `0baf6461` was live at 17:24 UTC on 2026-08-10. If you see something older
than that, say so in the report — but still run.

## Vocabulary appendix — exact strings, do not accept look-alikes

RUN 004-V produced a false FAIL by reading the wrong HR panel. Hence this section.

- Fixture: `POST https://api.relopass.com/api/test-drive/provision-staged`,
  body `{"first_name","campaign","corridor_id","stage"}`.
- The response JSON contains `employee.email`, `employee.password`, `hr.email`,
  `hr.password`, `session_id`, `case_id`, `assignment_id`, `stage`, `shortlist`.
- `stage: "shortlist_ready"` = the shortlist rows already exist.
  `stage: "roadmap_ready"` = you start *before* the shortlist, so you exercise the Add flow.
- The 400 under test is on `POST /api/ai/decisions` — the audit write. **Not** services-state.
- If the password contains `O`, `I`, `l`, `0` or `1`, note it. If sign-in then 401s, re-mint
  with a different `first_name` rather than assuming the account is broken.

## JOB A — all 12 movers reachable (#1699)

**Mint:**
```bash
curl -sX POST https://api.relopass.com/api/test-drive/provision-staged \
  -H 'Content-Type: application/json' \
  -d '{"first_name":"R4x1b","campaign":"qa-r4x1b","corridor_id":"NL_SG","stage":"shortlist_ready"}'
```

**If the mint fails:** HTTP 404 = the test-drive flag is off or the campaign gate rejected
it — report the exact body, that is a config finding not a test failure. `shortlist: []` =
re-run **once** with `"first_name":"R4x1c"`; if it fails twice, stop and report, that is
the seeding intermittency reproduced.

**Steps:** sign in as `employee` → confirm the account label → Services → Recommendations
→ **Movers** tab.

**⭐ Single assertion:** a **"Show all"** / **"Show N more"** control is present, and using
it reaches **all 12** distinct movers. The old defect hard-capped this at 10 with no way to
see the rest.

- PASS = 12 reachable → ✅, STOP.
- FAIL = still 10 with no reveal control → record exactly what the "N more" banner says, STOP.

## JOB B — zero 400s on the audit write (#1696 / #1700)

**Fresh browser session.** Mint:
```bash
curl -sX POST https://api.relopass.com/api/test-drive/provision-staged \
  -H 'Content-Type: application/json' \
  -d '{"first_name":"R4x2b","campaign":"qa-r4x2b","corridor_id":"FR_NO","stage":"roadmap_ready"}'
```

**Steps:** sign in as `employee` → Services → select **Movers + Schools** → answer the
pre-filled questions → **Get recommendations** → add **6 items** (3 movers + 3 schools),
**deliberately including non-top picks in each category**. Non-top picks are the ones that
used to 400.

**⭐ Single assertion:** **zero `400`s on `POST /api/ai/decisions`** across all 6 adds.
The old failure sent `decision:'override'` with no reason and returned
`400 {"detail":"Reason is required for decision 'override'."}`.
If your harness has no network panel, assert instead that **no
`Failed to load resource … 400` console line** appears during the 6 adds — and say which
method you used.

- PASS = zero 400s, all 6 in the package, "Request quotations" enables → ✅, STOP.
- FAIL = any 400 on `/api/ai/decisions` → capture URL + status + body, STOP.

## Report block

```
RUN 004-X CLOSE-OUT   DATE ____
DEPLOY GATE: commit ____ (record only — never a reason to stop)

JOB A  campaign qa-r4x1b  corridor NL_SG
  mint HTTP ____  stage ____  shortlist non-empty? ____
  ⭐ all 12 movers reachable? PASS / FAIL / INCONCLUSIVE
  reveal control label seen: ____
  if FAIL — exact request URL + status + body: ____
  case_id ____   assignment_id ____   session_id ____
  BUDGET USED __/20

JOB B  campaign qa-r4x2b  corridor FR_NO
  mint HTTP ____  stage ____
  ⭐ zero 400s on POST /api/ai/decisions? PASS / FAIL / INCONCLUSIVE
  detection method: network panel / console line
  items added: __/6   "Request quotations" enabled? ____
  if FAIL — exact request URL + status + body: ____
  case_id ____   assignment_id ____   session_id ____
  BUDGET USED __/20

ARTIFACTS TO PURGE: qa-r4x1b, qa-r4x2b (+ qa-probe-gate, minted 2026-08-10 by a
  reachability probe — please include it)
BLOCKED BY: ____
```

**What a PASS unlocks:** both v0 launch-blockers become dual-verified once the database
side corroborates, and the two-week-old "is v0 actually shipped?" question closes.

RULES: *(paste the shared footer)*

---
---

# CARD B — post-fix regression sweep (budget ≤20 actions)

**Why this card exists:** Audos found six defects in July. All six were fixed and merged.
**None has been re-tested since.** Six merged fixes with zero regression coverage is a
standing bet that nothing downstream touched them, and we have no evidence either way.

This is a breadth card, not a depth card. One line per defect. Do **not** investigate a
regression you find beyond capturing it — report and move to the next.

## Setup

Deploy gate as in Card A — **record the commit and proceed**; it is for attribution, not for gating. Then mint one fixture and use it throughout:

```bash
curl -sX POST https://api.relopass.com/api/test-drive/provision-staged \
  -H 'Content-Type: application/json' \
  -d '{"first_name":"RegB","campaign":"qa-regb","corridor_id":"FR_NO","stage":"shortlist_ready"}'
```

You get **both** `hr` and `employee` credentials. Checks 1–3 are HR-side, 4–6 are
employee-side. **Do the HR checks first, then sign out and switch** — never both personas
in one session.

## The six checks — one line of evidence each

| # | Was | Check | Verdict |
|---|---|---|---|
| 1 | Country autocomplete corrupted input ("France" → "Franceance") | On any HR form with a country field, **use the dropdown** and confirm the stored value reads back exactly. Then look at whether the field still accepts free typing at all. | HOLDS / REGRESSED / INCONCLUSIVE |
| 2 | Policy publish hung 20–40s (a RAG re-index on the publish path) | HR → Policy → publish. **Time it.** Under 5s = holds. Over 15s = regressed. In between = inconclusive, report the number. | " |
| 3 | Policy tabs contradicted each other | HR → Policy → read each tab. Do any two tabs state a different value for the same setting? Name the setting and both values. | " |
| 4 | `GET /api/cases/{id}/vendors` returned 500 | Employee → Services → the vendors/providers surface loads with content, no error state. | " |
| 5 | "HR owner" displayed the employee's email | Anywhere an HR owner is shown, confirm it is the **HR** address, not the employee's. Both are in your mint response — compare them literally. | " |
| 6 | Services destination gate | Employee → Services. Confirm the destination is the corridor destination (**Norway / NOK** for FR_NO), not a default or USD. | " |

## Report block

```
REGRESSION SWEEP   DATE ____   CAMPAIGN qa-regb
DEPLOY GATE: commit ____ (record only — never a reason to stop)
hr.email ____    employee.email ____   (so #5 can be judged)

1 country autocomplete ......... HOLDS / REGRESSED / INCONCLUSIVE   evidence: ____
2 policy publish ............... HOLDS / REGRESSED / INCONCLUSIVE   seconds: ____
3 policy tabs consistent ....... HOLDS / REGRESSED / INCONCLUSIVE   evidence: ____
4 vendors surface loads ........ HOLDS / REGRESSED / INCONCLUSIVE   evidence: ____
5 HR owner shows HR email ...... HOLDS / REGRESSED / INCONCLUSIVE   value shown: ____
6 destination + currency ....... HOLDS / REGRESSED / INCONCLUSIVE   shown: ____

🔴 ANY REGRESSION: ____
NEW DEFECTS SEEN IN PASSING (do not chase, just name): ____
BUDGET USED __/20
ARTIFACTS TO PURGE: qa-regb
```

RULES: *(paste the shared footer)*

---
---

# CARD C — accreditation-registry harvest (research; no browser budget cap)

**Why this card exists:** an HR buyer's security review will ask where our supplier data
came from. *"FIDI FAIM registry, entry #1234, verified 2026-08-10, evidence URL attached"*
is an answer. A Google Maps scrape is not. The curation **is** the moat, so the sourcing
rule below is the whole point of the task — not a constraint on it.

Feeds AIQ-1788. You are doing the research half. Someone else writes the database half —
**you write to nothing.**

## Scope — exactly this, nothing adjacent

**Corridors:** FR→DE and FR→NO.
**Categories (5):** movers · housing_agencies · legal_admin · tax_finance · banks.
That is 10 corridor×category pairs.

**Out of scope, deliberately:** rmc, dsp, healthcare_ipmi, language_cultural. They have no
live suppliers and weaker public registries. Do not include them even if you find good
candidates — they get their own task with different sourcing rules.

## Sourcing rule — the one that matters

**Every candidate must trace to an accreditation, licensing or membership registry** that a
third party can check. Good sources by category:

- **movers** — FIDI FAIM, IAM, national removers' associations
- **housing_agencies** — national estate-agent registers, chamber listings
- **legal_admin** — bar association rolls, notary chambers
- **tax_finance** — accountancy/tax-adviser institutes, statutory registers
- **banks** — the national banking authority's register of authorised institutions

**Not acceptable:** Google Maps, Yelp, aggregator "top 10" blog posts, the supplier's own
marketing site as the *only* source. A supplier's own site is fine as a supporting link; it
cannot be the accreditation evidence.

**If a category has no usable registry for a corridor, say so and move on.** A short
honest list beats a padded one — a fabricated accreditation number is worse than a gap,
because it will be checked. Target 40–80 rows total, but **do not pad to reach 40.**

## Output format

One markdown table per corridor×category pair:

```
### FR→DE · movers
| supplier_name | country | source_name | source_url | accreditation_body | accreditation_number | accreditation_expiry | confidence | notes |
```

- `confidence` — high / medium / low, your own read on how firm the registry match is.
- `accreditation_expiry` — leave blank if the registry does not publish one. Do not guess.
- Flag any supplier appearing in more than one category.

Then a closing section: **"Categories the registries could not cover"**, one line each with
what you tried.

## Report block

```
ACCREDITATION HARVEST   DATE ____
Pairs attempted: __/10
Rows returned: ____  (high ____ / medium ____ / low ____)
Registries used: ____
Pairs with NO usable registry: ____
Suppliers appearing in >1 category: ____
Anything you were tempted to include but excluded under the sourcing rule: ____
```

RULES: *(paste the shared footer)* — plus: **write to no database, submit no supplier
records, approve nothing.** This is research output only.

---
---

# CARD D — competitor + AEO recon (research; no browser budget cap)

**Why this card exists:** it is the TrendNest job before we have TrendNest, and it feeds
the ad copy directly. Two halves — do both, keep them separate in the report.

## Half 1 — competitors

**Topia (Horizon)** · **Jobbatical** · **Localyze** · **Benivo**

For each:

1. **Positioning** — their own one-line description, quoted, with the URL.
2. **Pricing** — only if publicly stated. "Not public" is the honest answer and is useful.
3. **AI claims** — what they say their AI does, quoted.
4. **⭐ Compliance claims** — does any of them claim an **EU AI Act** status: "EU AI Act
   Ready", "compliant", "certified", "conformant", or describe itself as a *high-risk* AI
   system? **Quote it exactly with the URL if so.**

   Why this is starred: we are **forbidden** from making that claim ourselves — our own
   legal assessment says a false or premature compliance claim is itself a liability. So
   this is not competitive envy. It tells us what buyers are being shown, and whether a
   competitor has exposed themselves. Report it; propose nothing.

5. **MCP / agent integration** — do they expose an MCP server or advertise integration with
   enterprise AI agents? Quote and link.

## Half 2 — AEO (answer-engine optimisation)

Ask a public LLM assistant these five questions and record, per question: the substance of
the answer, and **which sources it cites by name**.

1. "What does an HR team need to relocate an employee from France to Norway?"
2. "What's the best software for managing employee relocation?"
3. "How long does a Norwegian residence permit take for an EU citizen?"
4. "What documents do I need to relocate to Germany for work?"
5. "Who are the alternatives to Topia for global mobility?"

For each: is ReloPass mentioned? Is any competitor? Which domains get cited?

**Do not correct the assistant, and do not judge whether the answers are right** — we want
what it *says*, not what is true. The accuracy question is ours to handle separately.

## Report block

```
COMPETITOR + AEO RECON   DATE ____

— HALF 1 —
Topia/Horizon  positioning: ____  pricing: ____  AI claim: ____
   ⭐ EU AI Act status claim? none / QUOTE + URL: ____   MCP? ____
Jobbatical     (same five fields)
Localyze       (same five fields)
Benivo         (same five fields)

— HALF 2 —
Q1 .. Q5, each: answer substance ____ | sources cited ____ | ReloPass mentioned? ____
   | competitors mentioned? ____
Domains cited most often across all five: ____

MOST USEFUL THING FOR AD COPY (one sentence): ____
```

RULES: *(paste the shared footer)* — plus: **quote, never paraphrase, any compliance or
pricing claim.** A paraphrase of a legal claim is worthless as evidence.

---
---

## After the four come back

- **Card A** → the two assertions get corroborated against the database before either is
  called closed. Browser and database must agree; neither half self-certifies.
- **Card B** → any REGRESSED line becomes a Notion bug immediately, at the priority the
  original carried.
- **Card C** → becomes the harvester script's fixture and the staged `vendor_candidates`
  rows. Nothing is promoted to the live supplier directory without a human pass.
- **Card D** → Half 1 informs positioning; Half 2 becomes the AEO content plan, which is
  the output of the ad test that survives the ad test.
