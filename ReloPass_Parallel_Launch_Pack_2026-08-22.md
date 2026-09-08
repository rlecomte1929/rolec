# ReloPass — Next-Move Assessment & Parallel Launch Pack

**Date:** 2026-08-22 · **Owner:** Romain · **Author:** Claude (Cowork)
**Grounded in:** live prod state, the AI Work Queue, North Star v2, the Andrea Experience Audit, the Otto↔Claude tandem plan, the Generator–Relay–Applier bridge, the Theory→Product / ThemeDigest / ES-IE Landing plans, and the corridor data on disk.

> **Reading note on "Denis":** I could not find a "Denis" in the Notion workspace or as a case. Given the queue, I've read this as **Denis — the NO→FR (Norway→France) reference case** (tasks D1–D4, AIQ-2067–2071), the twin of **Andrea** (ES→IE, Venezuelan, Google Dublin). The whole plan below serves *both named people directly*. If Denis is a real third person (a design partner / HR contact), tell me and I'll re-point the lanes.

---



## 1. The assessment — is it workflow, or corridor data, or both?

**It's both — but they are not the trade-off they look like, because they run on different engines, and there is exactly one ordering rule that makes "both at once" safe.**

The instinct to "use Otto's spare capacity to build and expand corridors" is right, but North Star v2 names the precise trap it must avoid: *"shipping breadth without operating the engine that makes breadth safe… activity is not validated capability."* You have 12 corridor folders on disk and only **3 corridors actually serving** (ES→IE, FR→NO, IN→DE). More raw corridor data does not move the needle for Andrea or Denis, and un-gated breadth is "competitor #159 with data you can't stand behind."

So the highest-leverage next move is **neither "more features" nor "more corridors."** It is the one piece that unlocks *both*:

> **Wire the serving layer to read** `applies_to.nationality_scope_basis`**, render** `assertion_mode=conditional`**, and surface** `non_obvious` **traps — proven against the Andrea ES→IE golden fixture.**

Every strategy artifact converges here independently — ES-IE Landing **Phase 5**, ThemeDigest **AIQ-1984.4**, Theory→Product cards **1938/1969/1971/1972**, and tandem **CT-4**. It is the "Operate & prove" rung made numeric, and it is the **gate every future corridor must pass through** before its facts can serve. Land it once and Andrea's corridor becomes *correctly* served **and** the throttle opens for Denis's NO→FR and everything after — each new corridor inherits the trust instead of multiplying the mis-serve bug (the EEA/third-country exemption error).

**Therefore the sequencing, not the choice:**

- **Deep, serialized, gated — the value path for Andrea & Denis:** serving-correctness wiring → hydrate their cases → close the HR quote-approval loop → *then* promote their staged corridor facts through the human/lawyer gate. This is one careful Claude Code lane because these steps share files and the promotion depends on the serving code being correct first.
- **Wide, parallel, on spare engines — the expansion, made safe:** point **Otto** at corridor research (discovery-only, official sources → verified NDJSON, **staged inert, served to no one**) and **Cursor** at bulk read-only codegen. These pre-load the pipeline *behind the gate* so nothing waits and nothing mis-serves. This is exactly where "auto's" spare capacity goes.

The one-way valve between the two is your promotion gate. Below is the pack to run **both lanes in parallel today**, engineered so they cannot collide.

**The P0 is already cleared.** The requirements-500 that the Andrea audit flagged as the spine being down was fixed hours later (PR #2001, `516d1b86`; prod verified 200). So we are past "unblock" and into "make it real."

---



## 2. The one rule that governs all parallelism

**Serving-correctness code (Lane 1) lands before any new corridor data is *promoted to serving*. Only Lane 1 touches the requirement-serving files.**

- Reserved-to-Lane-1 files: `backend/app/routers/requirement_facts.py`, `backend/app/services/requirements_sufficiency.py`, `backend/app/services/requirements_builder.py`, `backend/app/routers/public_corridor.py`.
- Every other lane is scoped to *not* touch those files, so worktrees run in parallel without merge conflicts.
- Otto and Cursor lanes never write the repo or `public.requirement_facts` — Otto writes only `otto_staging` (inert), Cursor only generates. Staging is safe and reversible; **promotion is the only gated step**.

---



## 3. Lane map


| Lane   | Engine                      | What it delivers                                                              | Touches                  | Runs in parallel with    | Gate                                           |
| ------ | --------------------------- | ----------------------------------------------------------------------------- | ------------------------ | ------------------------ | ---------------------------------------------- |
| **L1** | Claude Code (solo)          | Serving-correctness wiring + Andrea golden fixture (**CT-4 / P5**)            | serving files ⚠️         | everything except itself | 🔴 PR, do not merge without you                |
| **L2** | Claude Code / Conductor     | Hydrate Andrea & Denis cases (HR doc-extraction intake + roadmap regen)       | intake/case/roadmap svcs | L1, L3, L4, Otto         | 🟡 self-validate; final roadmap regen after L1 |
| **L3** | Claude Code / Conductor     | HR quote-comparison + approval screen (AIQ-2118) + one-click RFQ (AIQ-2117)   | frontend + rfq/quote API | L1, L2, L4, Otto         | 🟡 self-validate + sample                      |
| **L4** | Claude Code / Conductor     | Neighbourhood advisor (2119) + HR-vendors-visible (1992) + tick-a-step (2057) | rec/housing/curation     | L1, L2, L3, Otto         | 🟡 self-validate + sample                      |
| **I**  | Claude Code (ingest runner) | Poll the bus; stage every Otto batch into `otto_staging` (**CT-1**)           | `otto_staging` only      | all                      | 🟢 staging only (inert)                        |
| **O1** | Otto chat                   | **ES→IE origin** (Spain departure) — completes **Andrea**                     | Audos only               | all                      | 🔴 lawyer on legal rows                        |
| **O2** | Otto chat                   | **NO→FR destination** (France) — **Denis**                                    | Audos only               | all                      | 🔴 lawyer on legal rows                        |
| **O3** | Otto chat                   | **NO→FR origin** (Norway departure) — **Denis**                               | Audos only               | all                      | 🔴 lawyer on legal rows                        |
| **O4** | Otto chat                   | **IE→ES** (Dublin→Madrid) — breadth                                           | Audos only               | all                      | 🔴 lawyer on legal rows                        |
| **O5** | Otto chat                   | **GB→NO** (post-Brexit, third-country) — breadth                              | Audos only               | all                      | 🔴 lawyer on legal rows                        |
| **C1** | Cursor fleet (via Otto)     | Bulk promotion-SQL + tests for staged corridors (optional)                    | generates only           | all                      | applier dry-run→verify                         |


**Critical path to value:** `L1 → (human/lawyer gate) → promote ES→IE` while `L2/L3/L4` build the surface in parallel and `O1–O5 + I` pre-stage the next corridors' knowledge. Denis's corridor (O2/O3) lands the moment L1 is green.

---



## 4. LANE 1 — Serving-correctness + Andrea made real  *(the critical one)*

**Paste into: a Claude Code session in** `rolec`**. This lane owns the serving files; run nothing else against them.**

```
ROLE — You are Claude Code in the rolec repo. Ship the serving-correctness layer that lets ReloPass serve nationality-aware, conditional, non-obvious relocation requirements correctly — proven on Andrea's ES→IE case. This is the gate every corridor must pass before its facts can serve (tandem CT-4 / ES-IE Landing Phase 5 / AIQ-1984.4). Output is a branch + PR you HAND TO ROMAIN — do NOT merge, do NOT promote anything to serving.

CONTEXT
- Andrea = Venezuelan national (third country), resident in Spain, moving to Google Dublin, family of 4. Corridor ES→IE. So on this corridor she gets the THIRD-COUNTRY path (Critical Skills Permit → D-visa → IRP/Stamp 1 → PPSN → RPN), and must NOT be served the EEA-free-mover exemptions.
- The staged ES→IE batch (otto_staging, batch es-ie-thirdcountry-requirements-2026-08-22, 38 facts / 6 entities) is verified and waiting. It is NOT to be promoted in this lane.
- Supabase project: nsvefcvpvwwwhuqyuqmp. Serving path must stay LLM-free.

STEP 0 — Reconcile the persona/fixture FIRST (blocking).
The docs disagree: ThemeDigest calls Andrea "Spanish (EEA)", the Experience Audit calls her "Venezuelan (third country)". Freeze docs/esie-andrea-golden-fixture.md on the AUDIT truth: nationality = Venezuelan/third-country on the ES→IE corridor. Define expected_served_rules (the audience_scope ES→IE rules + the third-country nationality_determined rules) and must_not_assert (no EEA exemption served to her; and, for an EEA control persona on the same corridor, never assert she IS visa-required).

STEP 1 — Wire the serving layer (branch fix/serving-nationality-scope).
In backend/app/routers/requirement_facts.py + backend/app/services/requirements_sufficiency.py (and requirements_builder.py's crud.list_requirements path):
  - Gate applicability on applies_to.nationality_scope_basis:
      * nationality_determined → filter by the case's nationality.
      * audience_scope → applies to EVERYONE on the corridor; do NOT hide from an EEA mover.
  - Render assertion_mode=conditional as a CONDITIONAL statement (surface conditional_on). Never assert unconditionally that a nationality IS/ISN'T visa-required.
  - Surface non_obvious=true as an "easy-to-miss trap" flag on the served item.

STEP 2 — TDD the golden fixture.
Write/extend a test that loads docs/esie-andrea-golden-fixture.md and asserts: Andrea (VE/third-country) is served the third-country rules + audience_scope rules; the EEA control persona still sees the audience_scope rules and is NOT told visa-required; no served item violates must_not_assert. Keep check_serving_llm_isolation and check_route_auth green. Add a regression test that GET /api/public/corridor-requirements returns 200 + non-empty for ES→IE and FR→NO (guards the #2001 class).

STEP 3 — Prepare (do NOT execute) the ES→IE promotion.
Produce a DRY-RUN promotion plan for the 38 staged facts: append-only, dedupe on (country_code, purpose, title), pillar-honoring (respect PR #1973 if unmerged — flag the dependency), promote-to-pending, NEVER overwrite a reviewed row. Output the exact rows it WOULD insert and the reviewed rows it must NOT touch. This is the artifact Romain approves at the gate; it does not run here.

DELIVERABLES: branch + PR with the serving diff + tests green; the golden fixture frozen; the dry-run promotion plan as a markdown/JSON artifact. Report the diff and the fixture results to Romain. STOP at the gate.
```

---



## 5. LANE 2 — Hydrate Andrea & Denis (so everything computes)

**Paste into: a Conductor worktree / separate Claude Code session. Does not touch serving files. Coordinate the *final* roadmap regen to run after L1 merges.**

```
ROLE — Claude Code in rolec. Make Andrea's (and Denis's, once his case exists) case REAL so every profile-driven feature lights up. Today Andrea's case 6ecadafe still carries the hardcoded family-of-4 "Singapore" seed (intake_step=0): 0 services, 0 recommendations, 0 RFQs, 0 vendors, and 16 stale generic roadmap milestones. The machinery already works for profiled cases (399 corridor milestones / 55 cases; 1,069 rec slates) — it just has nothing to compute from.

BUILD — HR document-extraction intake (the HR-facilitation move):
  1. Endpoint: HR uploads the employee's contract/offer → Claude doc-extraction proposes intake fields as SCHEMA-LOCKED JSON (align with AIQ-2039 structured-outputs migration) → HR validates once → intake is pre-filled. No employee re-entry.
  2. Kill the Singapore seed on Andrea's case; write her real profile (Grand Canal Dock office, family of 4, VE nationality, ES→IE).
  3. Regenerate Andrea's roadmap so the CSEP/D-visa/IRP steps + durations replace the 16 generic milestones. (Run this final regen AFTER Lane 1 merges, so she picks up correctly-served requirements.)
OUTCOME: recommendations, curated Dublin vendors (29 already curated), services, RFQs all become available on her profile.

SCOPE GUARD: touch intake/case/profile/roadmap services and a new extraction endpoint ONLY. Do NOT edit requirement_facts.py / requirements_sufficiency.py / requirements_builder.py / public_corridor.py (Lane 1 owns them). Do NOT run the AIQ-2133 mass backfill of the 2,027 legacy seed cases here — that's a separate Red task; this lane is Andrea (+Denis) only.
DELIVERABLE: branch + PR; Andrea's case shown hydrated with a live recommendation slate + non-empty roadmap.
```

---



## 6. LANE 3 — Close the HR service loop (the biggest genuine product gap)

**Paste into: a Conductor worktree. Frontend + RFQ/quote API. The Experience Audit calls this the #1 missing half — 0 of 30 RFQs ever had a preferred quote set.**

```
ROLE — Claude Code in rolec. Assemble the HR-facing "quote summary + comparison table → approve" experience. The pieces exist as API (GET …/quotes?comparison=1; assignment_policy_service_comparisons with policy cap/variance/approval_required; rfqs.preferred_quote_id / validated_quote_id / validation_reason) but were never assembled into a screen, so the selection loop is never completed.

Execute AIQ-2118 (HR quote comparison + approval screen) and AIQ-2117 (one-click "Request quotes" from the employee's curated Dublin movers list) exactly per their Notion execution prompts. One HR screen per service: quotes side-by-side, policy cap + variance, a recommended pick, and a one-click "Approve this quote" that writes validated_quote_id + reason. One-click RFQ launches to the curated movers and creates the quote requests.

SCOPE GUARD: frontend HR case view + rfq/quote endpoints ONLY. Do NOT touch the requirement-serving files (Lane 1). VALIDATE: a 2-quote case renders the comparison, approve writes validated_quote_id, the compare event fires. DELIVERABLE: branch + PR + a demoable HR approve flow.
```

---



## 7. LANE 4 — Advice depth + vendor visibility

**Paste into: a Conductor worktree. Recommendation/housing/curation. AIQ-2120 (Dublin settle-in) depends on Otto research — wire it to consume O-lane output when ready.**

```
ROLE — Claude Code in rolec. Deliver the "where do I live / what do I need to know" depth and fix vendor visibility. Execute, per their Notion execution prompts, in one worktree:
  - AIQ-2119 Neighbourhood advisor: geocode Andrea's Grand Canal Dock office; RANK Dublin areas by commute + family + budget with rationale (not just a housing-vendor list).
  - AIQ-1992 HR-approved vendors are invisible to employees: reconcile the curation catalog and the recommendation engine so they rank the SAME vendor population (the 29 curated Dublin suppliers surface to Andrea).
  - AIQ-2057 Let the employee tick a step on the live relocation-plan page.
  - AIQ-2120 Dublin-specific settle-in depth: consume the O-lane Dublin research when it lands; until then, scaffold the surface.

SCOPE GUARD: recommendation/housing/curation/plan-page files ONLY. Do NOT touch the requirement-serving files (Lane 1). DELIVERABLE: branch(es) + PR(s); a ranked Dublin area shortlist for Andrea and curated vendors visible on her profile.
```

---



## 8. INGEST LANE (I) — the receiving end for all Otto batches

**Paste into: one dedicated Claude Code session. It stages whatever any Otto lane pushes — inert, idempotent, safe. This is CT-1; it never promotes.**

```
ROLE — Claude Code, the bridge INGEST runner for the ReloPass corridor tandem (CT-1 only). Otto lanes push verified corridor NDJSON onto the otto-claude-bridge; you pull it, stage it into otto_staging with your service-role key, return a collision ledger, and ack. You NEVER write public.requirement_facts and NEVER promote — staging is inert and served to no one.

BRIDGE: secret in ~/.otto-bridge-secret (chmod 600) → x-hook-secret header; never print it. Execute URL https://audos.com/api/hooks/execute/workspace-776786/otto-claude-bridge. Actions push/pull/ack. Read direction otto_to_claude; reply on claude_to_otto as kind "record". Supabase project nsvefcvpvwwwhuqyuqmp.

POLL LOOP: pull otto_to_claude (sinceId = max id seen). For each MANIFEST row:
  - per entity: INSERT otto_staging.immigration_entities (destination_country, domain_area, topic_key, title, batch_id, source) ON CONFLICT (destination_country, topic_key) DO NOTHING.
  - per fact: INSERT otto_staging.immigration_fact_candidates (destination_country, entity_topic_key, fact_type, fact_key, fact_text, applies_to, source_url, evidence_quote, confidence, confidence_score, accuracy_tier, extraction_method, batch_id, dedupe_key, status) ON CONFLICT (dedupe_key) DO NOTHING.
  - collision ledger vs live: for each (destination_country, entity.topic_key, fact_key), check public.requirement_facts JOIN public.requirement_entities. Reply REPORT (kind record) {ok, staged, collision_ledger:{mapped_new,dup_in_batch,dup_existing_live,entities_created}, rejects, note} echoing correlation_id + in_reply_to. ack the row.
GOVERNANCE: staging_only always; nothing here reaches a mover. Report per-batch ledgers to Romain. Promotion is a SEPARATE, human-gated step that happens only after Lane 1 lands.
```

---



## 9. TONIGHT — the Otto overnight batch  *(your stated objective)*

**Goal:** fire a set of self-contained Otto chats before bed; each researches one corridor from **official sources only**, produces verified candidate NDJSON, **persists it** to the workspace + `otto.md`, and (if the bridge is reachable) pushes it to the bus `staging_only`. Nothing Otto does overnight can reach a mover: it can't write the ReloPass DB, everything is `staging_only`, and every fact lands `review_status=pending` / `verification_status=representative`. So this is the safe way to spend the night building the moat — it's exactly the North-Star "discovery-only, gate-before-serve" posture, run in parallel.

**How to run it (5 minutes to launch):**

1. Open **one fresh Otto chat per task**. Paste the **PREAMBLE** (§9.0) once, then paste one **TASK card** (§9.1) under it. Repeat for as many as you want to run — they share no memory, so each is self-contained.
2. Suggested overnight batch, in priority order (each line = one chat):
  - **Serve Andrea & Denis (do these):** `A-1` ES→IE origin · `B-1` NO→FR destination · `B-2` NO→FR origin · `B-3` Paris vendor directory · `A-2` Dublin support pack · `A-3` Dublin settle-in depth
  - **Breadth (safe, staging-only):** `C-1` IE→ES · `C-2` GB→NO · `C-3` NO→GB · `C-4` FR→NO
  - **Cleanup:** `D-1` re-source Singapore/Australia JS-shell citations
3. Go to sleep. Each chat researches, writes `data/corridor-facts/<corridor>-<side>-2026-08-22.ndjson`, logs coverage to `otto.md → "Overnight corridor run"`, and pushes `staging_only` if it can reach the bus.
4. **In the morning:** skim each chat's coverage summary + `otto.md` board. Then run the **Ingest lane (§8)** in a Claude Code session to stage everything into `otto_staging`, and you'll have collision ledgers per batch. Promotion still waits for Lane 1 + your gate — so nothing you queue tonight can mis-serve.

> **The overnight safety contract (enforced in every card):** official/authoritative sources only; every fact carries a live `source_url` + a **verbatim** `evidence_quote`; `verification_status:"representative"`, `review_status:"pending"` — **never** "verified"; `needs_lawyer_review:true` on any legal-conclusion fact; `non_obvious:true` on easy-to-miss traps; **no promotion, ever.** Unattended = candidates only, never served facts.



### 9.0 PREAMBLE — paste this at the top of every Otto chat (fill the ALLCAPS slots from the card)

```
ROLE — You are Otto, researching the {CORRIDOR} relocation corridor for ReloPass and originating a staging batch on the otto-claude-bridge. You do DISCOVERY-ONLY research from OFFICIAL sources and hand verified candidate facts to Claude Code (the ingest runner) to stage. You never touch the rolec repo or the ReloPass DB, and you NEVER self-certify a fact as "verified" — you produce representative, pending, evidence-linked candidates. Company name is ReloPass (do not let the auto-namer drift to GlobeIQ/TrendNest).

PERSONA / SCOPE: {PERSONA — e.g. Denis, French national repatriating Oslo→Paris, EEA free-mover, family}. Destination = {DEST_COUNTRY}; origin/departure = {ORIGIN_COUNTRY}. Produce the {DEST or ORIGIN} side in THIS lane.

RESEARCH DISCIPLINE (hard):
- Only OFFICIAL / authoritative sources: {LIST — e.g. service-public.fr, CLEISS, ameli.fr, impots.gouv.fr, urssaf.fr}. No blog/forum/JS-shell pages as evidence (they can't be evidence-checked).
- Every fact carries a live source_url and a VERBATIM evidence_quote copied from that page.
- Tag nationality_scope_basis correctly: nationality_determined (gates by nationality) vs audience_scope (applies to everyone on the corridor). Tag assertion_mode: assertion vs conditional (+ conditional_on). Flag non_obvious=true on easy-to-miss traps (the D-number-before-first-pay class). Flag needs_lawyer_review=true on any legal-conclusion fact.
- verification_status:"representative", review_status:"pending", accuracy_tier:"representative". Never "verified".

BRIDGE (secret in the x-hook-secret header, never printed): Execute URL https://audos.com/api/hooks/execute/workspace-776786/otto-claude-bridge. push {direction:"otto_to_claude", kind, payload, source:"otto"}; pull {direction:"claude_to_otto", sinceId?}; ack {ids}. kind: "manifest" for fact batches, "record" for queries, "message" for status.

MESSAGE CONTRACT: envelope payload carries task_id "{CT}-{CORRIDOR}-{DATE}", corridor "{CORRIDOR}", correlation_id (you generate, unique), in_reply_to (null), schema_version "1.0", governance "staging_only". MANIFEST payload: {batch_id "{CORRIDOR-side-DATE}", records:[…otto_staging-shape…], requested_checks:["collision","dedupe"], reply_with:["staged","collision_ledger"]}. Chunk ~10 records/message under one batch_id (dedupe_key makes chunking safe).

FACT RECORD SHAPE (each record): destination_country, corridor, entity{destination_country,topic_key,domain_area,title}, topic_key (bare snake_case), domain_area, fact_key, fact_type(eligibility|document|step|deadline|fee|where_to_apply|account|other), fact_text, source_url, evidence_quote, confidence, confidence_score, accuracy_tier:"representative", dedupe_key (dest:topic:fact), batch_id, applies_to{nationality_scope_basis, assertion_mode, conditional_on?, non_obvious, needs_lawyer_review, review_status:"pending", verification_status:"representative"}.

START NOW (UNATTENDED — I am asleep; do not wait for me):
1. Research {CORRIDOR} {DEST or ORIGIN} side across ONLY the official sources named in the card. For each fact, copy the exact source_url and a VERBATIM evidence_quote from that page.
2. Assemble the verified candidate set in the fact-record shape above (representative / pending — never "verified").
3. PERSIST: write the batch to data/corridor-facts/{CORRIDOR}-{side}-2026-08-22.ndjson AND append a one-line-per-topic note to otto.md → "My Plan" → "Overnight corridor run" (retry on Stream closed) so the work survives and I can see it in the morning.
4. PUSH if reachable: push as MANIFEST chunks (governance staging_only). If the bus is unreachable, keep the NDJSON persisted and log "bus unreachable — ready for morning ingest" — do NOT block or retry forever.
5. Log a final coverage summary to the chat: topics covered, # facts, # needs_lawyer_review, # non_obvious, # sources. Then STOP. Do NOT poll for a reply, do NOT request promotion — promotion is my gate after the serving layer lands.
```



### 9.1 TASK cards — paste ONE under the preamble per chat

Each card fills the preamble's slots and adds the source allow-list + the coverage checklist. Tell Otto: *"TASK for this chat:"* then paste the card.

**A-1 · ES→IE origin — Spain departure (Andrea)** — completes Andrea's corridor; pairs with the already-staged ES→IE destination batch.

```
CORRIDOR=ES-IE, side=ORIGIN (Spain exit). PERSONA=Andrea, Venezuelan national resident in Spain, family of 4, leaving for Dublin.
OFFICIAL SOURCES ONLY: sede.administracionespublicas.gob.es (extranjería), agenciatributaria.es (AEAT), seg-social.es (TGSS), inclusion.gob.es, exteriores.gob.es, your municipal padrón (Madrid: madrid.es).
COVER: padrón/consular de-registration; ending Spanish tax residency (modelo 030, non-resident status); what happens to the TIE on departure; TGSS social-security de-registration + EU/Norway totalization (S1/A1) and its limits for a third-country national; transferring or closing Spanish healthcare; driving licence; obtaining school records. Flag non_obvious traps and needs_lawyer_review on any status/eligibility conclusion.
```

**A-2 · Ireland destination support pack (Andrea)** — vendor directory + ISD visa list + doc-extraction reference (AIQ-2063/2064/2066).

```
CORRIDOR=ES-IE, side=DEST-SUPPORT. PERSONA=third-country professional + family into Dublin.
OFFICIAL/AUTHORITATIVE SOURCES: irishimmigration.ie (ISD visa-required nationality list), citizensinformation.ie, revenue.ie, gov.ie; for the vendor directory use verifiable company/官方 listings only.
COVER: (1) Dublin vendor directory — international movers, letting agents, immigration solicitors, banks (name, official URL, service line — this is a directory, mark fact_type=account/where_to_apply, NOT legal facts); (2) the ISD visa-required vs visa-exempt nationality list as structured rows (nationality_determined); (3) an Irish employment-contract + Spanish-TIE field reference for HR document-extraction (what fields to read off each doc). Keep legal claims flagged needs_lawyer_review.
```

**A-3 · Dublin-specific settle-in depth (Andrea)** — AIQ-2120 / W3-2; today's settle-in content is thin and country-level (all rows city_name=null).

```
CORRIDOR=ES-IE, side=SETTLE-IN (Dublin, city-level). PERSONA=family of 4 relocating to Dublin (Grand Canal Dock area).
AUTHORITATIVE SOURCES: citizensinformation.ie, hse.ie, revenue.ie, gov.ie, dublincity.ie, leapcard.ie, and official school-admissions (gov.ie/education); use rent indices only from official/reputable published sources (rtb.ie Rent Index).
COVER with real Dublin specifics: rent ranges by neighbourhood (RTB index), GP/HSE registration reality, the bank proof-of-address catch-22, Leap card/transport, primary/secondary school admissions, community/expat basics. domain_area=settle_in, fact_type mostly step/where_to_apply; non_obvious=true on the bank/PPS/proof-of-address ordering traps.
```

**B-1 · NO→FR destination — France (Denis)** — AIQ-2067 / D1, P0.

```
CORRIDOR=NO-FR, side=DEST (France). PERSONA=Denis, French national repatriating Oslo/Stavanger→Paris, EEA free-mover, energy sector, family.
OFFICIAL SOURCES ONLY: service-public.fr, cleiss.fr, ameli.fr, impots.gouv.fr, urssaf.fr, caf.fr, interieur.gouv.fr.
COVER: residence formalities for a returning French national; carte vitale / CPAM registration; social-security totalization via CLEISS (S1/A1) coming from Norway (EEA, non-EU); re-establishing French tax residency + prélèvement à la source; CAF/family allocations; banking; driving-licence handling; posted-worker vs local-hire distinction. nationality_scope_basis mostly audience_scope (corridor-wide) — flag the few nationality_determined items; non_obvious on totalization/tax-residency timing.
```

**B-2 · NO→FR origin — Norway departure (Denis)** — AIQ-2068 / D2, completes the partial Norway-exit set.

```
CORRIDOR=NO-FR, side=ORIGIN (Norway exit). PERSONA=Denis leaving Norway for France.
OFFICIAL SOURCES ONLY: skatteetaten.no (folkeregister + tax + D-number), nav.no, udi.no, politiet.no.
COVER: folkeregister "flytte til utlandet" (move-abroad) notice; skattekort/exit-tax + kildeskatt; NAV membership exit and A1/S1 portability into France; D-number / fødselsnummer status after leaving; closing/keeping Norwegian bank + BankID. non_obvious on the social-security-portability and exit-tax timing.
```

**B-3 · Paris/France vendor directory (Denis)** — AIQ-2069 / D3, P0.

```
CORRIDOR=NO-FR, side=DEST-VENDORS (Paris/Île-de-France). PERSONA=family relocating to Paris.
SOURCES: verifiable company/official listings only (no forum/blog as evidence).
COVER a structured vendor directory: international movers, furnished + unfurnished letting agencies, relocation agents, banks with non-resident onboarding, CPAM/social-security help desks, French-lesson providers, international schools. fact_type=account/where_to_apply; this is a directory, not legal advice — do NOT emit legal conclusions here.
```

**C-1 · IE→ES (Dublin→Madrid) — breadth** — AIQ-1987.

```
CORRIDOR=IE-ES, side=DEST (Spain). PERSONA=Irish national (EU citizen) moving Dublin→Madrid.
OFFICIAL SOURCES ONLY: sede.administracionespublicas.gob.es (extranjería), seg-social.es, agenciatributaria.es, inclusion.gob.es, municipal padrón (madrid.es).
COVER: EU-citizen registration certificate (certificado de registro / green NIE); empadronamiento; social-security affiliation employed vs autónomo; AEAT tax residency; healthcare (tarjeta sanitaria); schools. nationality_scope_basis=audience_scope for the EU-mover path; non_obvious on NIE-before-everything ordering.
```

**C-2 · GB→NO (post-Brexit, third-country) — breadth** — AIQ-1988.

```
CORRIDOR=GB-NO, side=DEST (Norway). PERSONA=UK national (now THIRD-COUNTRY to EEA post-Brexit) → Oslo/Stavanger.
OFFICIAL SOURCES ONLY: udi.no, skatteetaten.no, nav.no, politiet.no.
COVER: UDI residence/work permit for a UK national (skilled worker); D-number; skattekort; folkeregister; police registration; NAV/health; banking + BankID catch-22. nationality_determined (UK = third country). Flag non_obvious HEAVILY — UK nationals wrongly assume EEA free movement still applies.
```

**C-3 · NO→GB (post-Brexit) — breadth** — AIQ-1989.

```
CORRIDOR=NO-GB, side=DEST (UK). PERSONA=Norwegian national (now needs UK immigration route post-Brexit) → London/Aberdeen.
OFFICIAL SOURCES ONLY: gov.uk (visas, eVisa/BRP, National Insurance number), nhs.uk (GP registration).
COVER: Skilled Worker visa route; eVisa/BRP; NI number; GP/NHS registration; banking proof-of-address; council tax; driving licence; school admissions. nationality_determined (Norwegian = non-EU to UK). non_obvious on NI-number + proof-of-address ordering.
```

**C-4 · FR→NO (Paris→Oslo) — breadth** — AIQ-1909–1912 cluster.

```
CORRIDOR=FR-NO, side=DEST (Norway). PERSONA=French national (EEA free-mover) → Oslo.
OFFICIAL SOURCES ONLY: udi.no, skatteetaten.no, nav.no, politiet.no.
COVER: EEA free-mover registration (UDI); D-number; skattekort BEFORE first pay; folkeregister; NAV/health; banking + BankID. audience_scope for the EEA path; non_obvious=true on the skattekort-before-first-pay trap (the flagship "invisible requirement").
```

**D-1 · Re-source Singapore + Australia JS-shell citations** — AIQ-2030, data-quality cleanup.

```
TASK=RE-SOURCE (not new corridor). Singapore (55 facts) and Australia (7 facts) currently cite JS-shell pages that can never be evidence-checked. Find the STATIC, archivable official equivalents and emit replacement source_url + verbatim evidence_quote per fact.
OFFICIAL SOURCES: Singapore — ica.gov.sg, mom.gov.sg, iras.gov.sg; Australia — homeaffairs.gov.au, immi.homeaffairs.gov.au, ato.gov.au.
OUTPUT a WORKLIST-style mapping {existing fact_key → new source_url + evidence_quote}; do not change fact_text unless the official source contradicts it (then flag needs_lawyer_review).
```

---



## 10. CURSOR FLEET (C1) — optional bulk codegen, if you want to spend more

If you want to push harder on throughput, add the **Generator–Relay–Applier** loop: Cursor generates (read-only, sandboxed, in a fleet), Otto relays the `context_bundle`/`artifact` over the same bridge, and the one wired applier (Lane I or a dedicated Claude Code) dry-runs → diffs against Cursor's prediction → applies only on match. Best first job (per the bridge doc's own proof test): generate the transactional promotion SQL for the 3 `immigration_work_authorization` staged facts + its prediction, apply as `BEGIN…ROLLBACK` dry-run, confirm `actual == prediction` and zero updates on reviewed rows. If that loop holds, scale it to the full multi-corridor promotion SQL and the CT-4 serving patch. Where it pays: bulk/parallel codegen. Where it doesn't: a single 3-row insert — let the wired agent just do it.

---



## 11. Launch order — tonight vs tomorrow

**Tonight (unattended — pure Otto, zero repo/prod risk):**

1. Fire the overnight Otto batch (§9): start with `A-1, B-1, B-2, B-3, A-2, A-3` (serve Andrea & Denis), then add `C-1…C-4` and `D-1` for as much breadth/cleanup as you want to run. One fresh chat each = PREAMBLE + one TASK card.
2. Sleep. Each chat persists NDJSON + logs to `otto.md` and pushes `staging_only` if it can.

**Tomorrow (at the keyboard — the value path + ingest):**
3. Run the **Ingest lane (§8)** to stage every overnight batch into `otto_staging`; read the collision ledgers.
4. Start **Lane 1** (serving-correctness) — it's the gate; give it your attention when its PR lands. Rebase on latest `main` first (`applies_to_matcher.py` + `requirements_sufficiency.py` were touched today — check for in-flight work before branching).
5. Start **Lanes 2, 3, 4** in Conductor worktrees — Andrea/Denis surface value in parallel; none touch Lane 1's files.
6. At the gate: merge Lane 1 → approve the ES→IE promotion → then Denis (NO→FR) and the breadth corridors land fast through the same gate.
7. **(Optional)** stand up **C1** (Cursor fleet) if you want to push codegen throughput.

## 12. What waits for you (the gates — nothing below auto-fires)

- **Merge Lane 1's serving PR** (🔴) — after you read the diff + fixture results.
- **Promote ES→IE** (🔴) — approve the dry-run plan; clears the 6 `needs_lawyer_review` rows first (you already chose to keep Andrea's 4 VE→IE rows served for her first test; revisit before a real customer).
- **Merge PR #1973** (pillar fix) if still open — prerequisite for correct tax/pillar promotion.
- **Promote Denis (NO→FR) and the breadth corridors** — only after Lane 1 is green; then each lands fast through the same gate.
- **Lawyer sign-off** on legal-conclusion facts across all corridors before any real launch.

---



### One-line version

**Tonight:** fire the Otto overnight batch (§9) — Andrea's + Denis's corridors first, breadth after — all `staging_only`, nothing served. **Tomorrow:** prove the engine on Andrea's corridor (Lane 1), make her and Denis's cases real (Lanes 2–4), ingest the night's research behind the gate, and let promotion be the one-way valve between the two. Both lanes at once, safely — which is the answer to "one, other, or both?": **both, with the gate between them.**