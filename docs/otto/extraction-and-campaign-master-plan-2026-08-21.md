# Otto Extraction & Campaign Master Plan

**Date:** 2026-08-21 · **Author:** Claude Code (grounded survey of repo, prod DB, Notion queue, Audos workspace)
**Status:** PROPOSAL — nothing here has been dispatched to Otto or written to Notion. Romain approves; then dispatch.

This document is the single plan for (I) **extracting everything already built** with Otto and on
branch `fix/td-qa-services-batch-0719` that has not yet landed, and (II) **distributing engineered
campaigns to Otto** so it does the heavy lifting — corridor data, theory-corpus work, vendors,
evals — delivering in formats Claude Code can load with near-zero translation cost.

Companion documents (this plan does not duplicate them):
- `docs/otto/andrea-denis-brief-2026-08-21.md` (PR #1960, open) — the **canonical delivery
  contract** (§3 there). This plan generalizes it; the contract itself lives there.
- `docs/notion-otto-workflow.md` — board mechanics, lanes, card rules.
- `docs/corridors/README.md` + `docs/corridors/DATA-PATHS.md` — corridor artifact model.

---

## 0. Goals, operating model, and the one rule that makes this work

**Goals (in priority order):**
1. **Zero stranded work.** Every artifact Otto has ever produced is either landed as candidates,
   landed as repo docs, or explicitly retired with a reason. Measured: the stranded-asset register
   in §1.2 reaches zero open rows.
2. **One delivery contract.** Three contracts currently disagree (§1.5) and that drift has killed
   at least three whole batches. After this plan, exactly one contract exists and every Otto brief
   points at it.
3. **Corridor coverage that serves.** Every corridor in the registry has nationality-scoped,
   evidence-quoted requirement facts (destination + origin), vendors, and a RAG corpus — loaded as
   candidates and moving through review. Measured: `corridors-serving-nothing = 0`,
   `nonobvious_recall` per corridor×employee-type slice, `overserved_requirements = 0`.
4. **The theory corpus becomes product.** The 37 course analyses + 10 book analyses + synthesis
   playbook stop being DOCX-in-ZIPs-on-GCS and become greppable repo markdown feeding the
   `[Architecture]/[Corridor Knowledge]/[Evaluation]/[Trust]/[Data Quality]` card families
   (AIQ-1936–1985, 2018–2022) that are already decomposed in Notion.
5. **No review bottleneck.** Otto's throughput is not the constraint — human review is. Every
   campaign is sized to the review budget (§7.3), and machine gates run before any human looks.

**Operating model — who does what:**

| Actor | Does | Never does |
|---|---|---|
| **Otto** (Audos) | Research, NDJSON/JSON/CSV/md deliverables via the workspace file channel (`audos-workspace-776786/data/`, synced to branch) | Write code, migrations, DB rows; set served statuses; push to `main` |
| **Claude Code** | Gate scripts, converters, loaders, landing PRs, eval harnesses, reconciliation, the "reuse" code half | Invent data; approve facts; flip `expert_verified` |
| **Romain / human** | Approve candidates, counsel-flag decisions, merge PRs, CVR sessions | Be the machine gate (that's scripted) |

**The one rule:** *reconcile the run, not the table.* Every Otto delivery is a **batch** with a
manifest, a sha256, and exact counts. The gate reconciles the batch; a discrepancy is the batch's
problem to explain. No un-manifested data ever enters the pipeline.

---

## 1. Ground truth (measured 2026-08-21)

### 1.1 Branch `fix/td-qa-services-batch-0719` — what is genuinely unmerged

Most of the branch already landed on `main` via PRs #1884/#1891/#1910 (serving/LLM guard, B3
docs, IE→ES batch). Diffed against **current** main, four deliverables remain:

| # | Asset | State | Extraction action |
|---|---|---|---|
| B1 | `audos-workspace-776786/data/es-ie-general-2026-08-21.jsonl` (33 facts) + `no-fr-general-2026-08-21.jsonl` (20 facts) | **All 53 refused by the loader** — `applies_to.nationality` null on every record | Do **not** hand-repair. Otto re-delivers under the contract (campaign C-ESIE-1 / C-NOFR-1; Notion AIQ-1833 + AIQ-2061/2067 already exist) |
| B2 | `backend/app/services/verification_guard.py` + `test_verified_write_guardrail.py` + migration `20261108…_requirement_verified_write_guardrail.sql` | Complete, unmerged. Enforces: generators can never write `expert_verified`; only a human actor can; a human signature can't be silently overwritten | **Cherry-pick to a fresh PR** (E2). Closes the gap in memory "requirement approval has no counsel gate". Timestamp must be re-chosen above max(repo, ledger) |
| B3 | `test_corridor_import_idempotency.py` + migration `20261109…_corridor_import_idempotency.sql` | Complete, unmerged. Matches Notion **AIQ-1982** (Otto-ready, P0) | Cherry-pick to a fresh PR (E3); close AIQ-1982 with it |
| B4 | Branch copy of `20261107000000_ie_es_requirement_items.sql` | Superseded — main has its own IE_ES migration (unapplied) | Retire; no action beyond noting here |

### 1.2 The stranded-asset register (built, not landed)

This is Part I's work list. **"Owner" = who moves it next.**

| ID | Asset | Size | Where | Why stranded | Owner |
|---|---|---|---|---|---|
| S1 | **10 book analyses + synthesis** (Kissinger, Huyen, Berryman&Ziegler, Kai-Fu Lee, Mollick, Garn, Wasserman, Raschka, Kim&Mauborgne, Sutton&Rao) | 11 md files | `~/Downloads/relopass-github-bridge/docs/book-analysis/` | Never `git add`-ed. Notion **AIQ-1838** open ("low risk — just commit") | Claude Code (E1) |
| S2 | **Learning-to-action infrastructure doc** + **playbook roadmap** | 2 md, 35KB+ | Untracked in one worktree: `docs/audos/relopass-learning-to-action-infrastructure.md`, `docs/playbook-roadmap.md` | One `git clean` from gone | Claude Code (E1) |
| S3 | **37 course analyses** (CS50x ×12, MIT 6.7960 ×7, MLOps, AI Dev 26) | DOCX in ZIPs | GCS bundles + `~/Downloads/*.zip` | DOCX-in-ZIP: not greppable, not diffable, unusable as agent context | Otto re-materializes to md (T1); Claude lands |
| S4 | **GCS wave batches — 18 countries** of requirement entities+facts (NO 308, IE 109, NZ 70, SG 69, AT 68, DK 67, FR 65, CH 60, NL 57, SE 55, AU 50, CA 50, BE 49, JP 37, +DE/AE/PT) | ~1,100+ facts | GCS only; indexed in `audos-workspace-776786/data/gcs-deliverable-index.md` | Never landed in-repo; wrong (wave) vocabulary; **ES, GB, IT were never written to GCS at all** | Otto re-delivers per corridor campaign (§4) — do NOT bulk-convert (see §4.0 rationale) |
| S5 | **NL batch**: 30 entities / 56 facts / 123-row corridor CSV / reliability report | 5 files | `audos-workspace-776786/` top level | Wrong vocabulary (`destination_iso2`, `entity_id`; `entity_topic_key` absent → fails parser line 1) | Claude Code converter (E5), then review |
| S6 | **`public.requirement_facts` dead-end table**: 2,350 pending rows across 38 destination countries | 2,350 rows | Prod DB | The promote path reads `otto_staging`, never this table (memory: two pipelines); Notion **AIQ-1832** ("review 2,290 before promotion") | Decision + drain plan (E6) |
| S7 | **`otto_staging.immigration_fact_candidates`**: 109 `ready` | 109 rows | Prod DB | Awaiting human move `new→ready→promote`; per-country promote loop now fixed | Human review sprint (E7) |
| S8 | **Vendor estate**: 3 markdown vendor directories (FR→NO by-city, global cities, qualification) + `es_ie_vendors_2026-08-16.ndjson` (53 rows) + 433 pending `vendor_candidates` (most missing source_tier/corridor — AIQ-1835) | ~500 rows | Workspace + DB | Markdown isn't machine-readable; only `card-c-harvest.csv` shape is importable | Otto re-emits machine-readable (V-campaigns §4); Claude imports |
| S9 | **58 `crawled_source_documents`** stuck `extraction_status='pending'` | 58 rows | Prod DB | Nothing advances extraction (Notion **AIQ-2013**, blocked) | Claude Code (E8) |
| S10 | **B3 artifacts** (20 corridor flags · 6 directions + 13 city records) | in-repo `docs/imports/data/B3/` | Landed as artifacts only, deliberately | Loadable now that converters exist; DK/DE hosts now allowlisted | Claude Code loads as candidates (E9) |
| S11 | **`linked_references` scrape substrate** — 6,421 rows (~50MB) incl. CS50/MIT/summify/fidi.org content | on `main` | `data/workspace-db-export/2026-08-18/` | Not stranded, but under-used: Otto can re-extract offline from it | Input to T-campaigns |
| S12 | Gap-analysis build specs ×3, `OTTO_TASK_LAUNCH_PROMPT.md`, `relopass_gap_manifest.json`, loading playbooks | ~10 docs | `audos-workspace-776786/` | Prior-art briefs, partly superseded by PR #1960 contract | Fold into §3; mark superseded in place (E10) |

### 1.3 Corridor coverage matrix (summary; full matrix in the corridor agent report → to be committed as `docs/corridors/COVERAGE-2026-08-21.md`)

12 corridor dirs on main. Serving engine keys on **destination only** via the 11-entry
`_ISO_TO_CATALOG_NAME` map; step graphs overlay per-corridor via the registry.

| Tier | Corridors | State |
|---|---|---|
| **Rich, live-demo** | ES_IE (19 steps, 14 non_obvious, 2 traps), NO_FR (32 steps, 14 non_obvious, 4 traps, `status: authoring`) | The Andrea/Denis thrust. Facts partially served (from seeds, not corridor artifacts) |
| **Rich, no trap content** | IN_DE (21 steps, **0 non_obvious** on the longest-runway corridor), IE_ES (only corridor with a full data batch — 25 records — and it is **unapplied + unapproved**, and excluded from two all-corridor test invariants) | |
| **Generated stubs** | DE_NO, ES_NL, FR_CH, FR_ES, FR_NL (93-line clones, 6 steps, zero non_obvious), FR_DE (9 steps, zero non_obvious — the biggest live corridor with the thinnest asset) | Need real research |
| **Registry-absent** | GB_NO (deliberate: post-Brexit UK national is third-country for Norway; copying the EEA pathway would ship the wrong legal basis) — but the intake dropdown offers GB → **silent coverage gap** | Needs a THIRD_COUNTRY pathway authored, then registry entry |

Prod served rows: only **156** `requirement_items` across 10 destinations; SPAIN 25 and DENMARK 11
all pending review; zero corridor serves its own corridor-derived records.

### 1.4 Notion queue state (measured today)

35 **Otto ready** · 70 **Ready for AI** · 24 Needs Decomposition · 15 Blocked · 27 To Do.
The Andrea/Denis series **already exists** as AIQ-2061–2071 (+ near-duplicates AIQ-2051–2056 —
consolidate, §7.2). Corridor research cards exist for IE→ES (1987), GB→NO (1988), NO→GB (1989),
re-source SG/AU (2030). The theory card families AIQ-1936–1985/2018–2022 are the book/course
theory already decomposed into ~40 implementation cards. **This plan creates few new cards; it
mostly arms existing ones with engineered prompts.**

### 1.5 Why batches died: the three-contract drift

| | `parsers.py` (what loads) | `OTTO_TASK_LAUNCH_PROMPT.md` (what Otto was told) | wave/NL batches (what Otto shipped) |
|---|---|---|---|
| topic key | **`entity_topic_key`** | `topic_key` | `entity_id`/`topic_key` |
| country | `destination_country` | same ✅ | `destination_iso2` (forbidden alias) |
| applies_to | `.nationality` `.status` `.quote_verbatim_confirmed` | `.nationalities` `.scenario` | varies |
| fact_type vocab | 7 values (no `account`) | 8 (with `account`) | varies |

The parser does **no aliasing** — `topic_key` instead of `entity_topic_key` fails at line 1.
Additionally `classify_source()` rejects any host not allowlisted, and the allowlist has been too
narrow **four documented times** (IE, IE-semi, DK/DE, ES). Both failure modes are now handled
structurally in §3.

---

## 2. Part I — Extraction campaign (land what exists; no new research)

Every task: **Goal / Steps / Acceptance / Notion**. Lane: Claude Code unless stated. These are
small, high-certainty, and unblock everything downstream — run before or alongside wave 1.

**E1 · Land the theory corpus files that already exist.**
Goal: S1+S2 in the repo. Steps: copy `~/Downloads/relopass-github-bridge/docs/book-analysis/`
(11 md + README) into `docs/book-analysis/`; move the two untracked docs into `docs/audos/`;
one PR. Respect `PUSH_INSTRUCTIONS.md` (never `[audos-sync]` in the commit message).
Acceptance: `git ls-tree` shows 13+ files; CI green. Notion: closes **AIQ-1838**.

**E2 · Merge the verified-write guardrail.**
Goal: B2 shipped. Steps: cherry-pick from the branch onto fresh branch; re-stamp migration above
max(repo, ledger); run `backend-tests`; PR. Acceptance: `test_verified_write_guardrail.py` green;
migration applied out-of-band + ledger reconciled per CLAUDE.md. Notion: create one card (Human
Review after merge).

**E3 · Merge corridor-import idempotency.** Same procedure for B3. Closes **AIQ-1982** (P0).

**E4 · Build `scripts/check_otto_batches.py` — the generic batch gate.**
Goal: the missing Phase-0 asset of the Otto→Served plan; the machine gate every campaign in §4/§5
cites as its Test Command. Steps: generalize `check_ve_ie_batch.py`/`verify_b3_batch.py`:
sha256 + count reconciliation vs manifest, real `parsers.read_jsonl` with zero rejections,
`_unscoped_topics` empty (nationality + status present on every fact), candidate-only statuses,
citation-URL resolution check (HEAD each `source_url`, ≥95% must resolve, hard-fail on any
allowlist-rejected host with the host named). Emits a machine-readable report JSON.
Acceptance: gate passes on `ve-ie-entry-family-2026-08-20` (the known-good batch) and fails on
`es-ie-general-2026-08-21` (the known-bad batch) — prove the gate discriminates.
Notion: new card, Ready for AI, P0.

**E5 · NL conversion.** Goal: S5 loadable. Steps: `scripts/convert_nl_to_otto_jsonl.py`
(join entities→facts to recover `entity_topic_key`; map `destination_iso2`→`destination_country`;
carry `applies_to` through with nationality/status mapping; unmappable rows to a named reject file,
never dropped silently). Dry-run through E4's gate; land `docs/imports/nl-conversion-2026-08-2x/`.
Acceptance: conversion report reconciles 56 = converted + rejected(with reasons). Load as
candidates only.

**E6 · Decide and drain the `requirement_facts` dead end (2,350 pending).**
Goal: the largest data asset stops rotting. This is a **decision task first**: (a) build a
`requirement_facts → otto_staging` bridge so the existing promote path serves it, (b) export per
country and route through the corridor campaigns as review material Otto refreshes, or (c) retire
rows older than a staleness cutoff and keep only corridor-campaign-refreshed facts.
Recommendation: **(b) for campaign corridors, (a) for the rest** — corridor campaigns produce
fresher, contract-clean facts anyway; bulk-bridging 2,350 rows into human review is exactly the
bottleneck §7.3 forbids. Steps: write the decision doc + per-country export
(`docs/imports/factbank-export-2026-08/`); wire chosen path. Notion: supersedes **AIQ-1832**'s
"review 2,290" framing (review-all is not a plan); update that card with the decision.

**E7 · Promote the 109 `ready` staging candidates.** Human review sprint over
`otto_staging.immigration_fact_candidates` (`status='ready'`), ≤25/session per §7.3. Claude
prepares a review sheet (fact, quote, source, proposed scoping) per session.

**E8 · Unstick the crawler extraction (58 docs).** Implement the extraction advance (Notion
**AIQ-2013**/2014 are already written and blocked) — schema-locked extraction per AIQ-2039.

**E9 · Load B3 as candidates.** `convert_b3_to_otto_jsonl.py` output through E4's gate,
`import_otto_facts.py --apply` (candidates only). The DK/DE allowlist fix already landed.

**E10 · Mark prior-art briefs superseded.** One-line header on `OTTO_TASK_LAUNCH_PROMPT.md`, the
three gap-analysis specs, and `relopass_gap_manifest.json` pointing at the PR #1960 contract +
this plan. Prevents Otto ever re-reading a dead contract.

**E11 · Commit the corridor coverage matrix** (§1.3 full version) as
`docs/corridors/COVERAGE-2026-08-21.md`, and fix the two matrix-discovered defects: IE_ES's
exclusion from `_FREE_MOVEMENT`/`_EXPECTED_ANCHORS` test invariants, and the stale corridor
README count. (Also file the missing `requirement_items` natural-key unique index —
DATA-PATHS documents the 3-step fix and zero duplicates exist today.)

---

## 3. The canonical Otto delivery contract — one contract, five deliverable types

**§3 of `docs/otto/andrea-denis-brief-2026-08-21.md` is the contract of record for requirement
facts.** This section adds what that brief scopes out: the other four deliverable types, and two
structural fixes that end the recurring failure modes. Every campaign brief in §4/§5 embeds a
pointer to this section — never a paraphrase.

**Type 1 — Requirement-fact batch** (NDJSON): exactly brief §3.1–3.6. Non-negotiables repeated
once because they have each killed a batch: field names are the **parser's** (`entity_topic_key`,
`destination_country`, `fact_key`, `fact_text`, `source_url` — no aliases, no `topic_key`, no
`destination_iso2`); `applies_to.nationality` ∈ {EEA, EU, non-EEA, non-EU}, **never null, never
"any"** — a universal obligation becomes two records; `applies_to.status` ∈ {professional,
student, family, any}; no `fact_type:"step"` in the fact stream (steps → README "step candidates"
list for the pathway graphs); official publishers only; evidence_quote verbatim;
candidate-only statuses.

**Type 2 — Vendor batch** (NDJSON, one provider per line):
`{name, official_url, categories[], service_cities[], country_iso2, corridor, contact_url_or_email, registry_evidence_url, source_tier, retrieved_at}`.
`registry_evidence_url` = companies-register / bar-register / trade-body page proving the entity
exists (the Card-C lesson); `source_tier` per the existing T0–T3 vocabulary. No markdown tables —
markdown vendor directories are read by humans and imported by no one (S8). A row without a
resolving `official_url` is not delivered.

**Type 3 — RAG corpus bundle**: one clean-text file per Tier-1 source page
(`<slug>.txt` + per-file `{url, publisher, retrieved_at, sha256}` in the manifest), 8–15 docs per
corridor, exactly the pages the fact batch cites. Claude indexes into `immigration_corpus_chunks`.

**Type 4 — Reference dataset** (JSON): closed-world lookups (e.g. the ISD visa-required
nationality list — AIQ-2052/2063). `{key → value, retrieved_at, source_url}` per entry; every
entry cites the official page; no gap-filling — a nationality the source doesn't list is absent,
not guessed.

**Type 5 — Theory analysis / spec digest** (markdown, NOT DOCX): uses the
`relopass-content-extraction` analysis template, but delivered as `.md` through the file channel
so it lands greppable in `docs/book-analysis/` or `docs/course-analysis/`. Mandatory sections:
Source & provenance (verbatim-text? reconstructed? QA status) · Core claims with citations ·
**Application to ReloPass** (mapped to the five anchors: corridor knowledge graph,
generator–verifier architecture, fear-relief positioning, SME HR ICP, data moat) ·
**Implementation hooks** — for each applicable claim, the Notion card family it feeds
(AIQ-1936–1985/2018–2022 id where one exists) and a concrete acceptance criterion Claude Code can
implement against. Provenance rule: a reconstruction from third-party AI summaries (the
CS229/CS230 case) must say so in its header and is Tier-2 — it may inspire, never ground, a
product claim.

**Batch envelope (all five types):** manifest per brief §3.2 (sha256, exact counts,
`load_task: AIQ-nnnn`), folder `audos-workspace-776786/data/<batch-id>/` (the file channel that
syncs to the branch — Otto's only delivery path; Claude Code re-lands curated copies under
`docs/imports/<batch-id>/`), batch-id `<corridor-or-topic>-<theme>-<YYYY-MM-DD>`.

**Two structural fixes (new, learned from §1.5):**

1. **Source-preflight step.** Before researching a corridor, Otto delivers a one-page
   `sources-manifest.md`: every host it intends to cite, one line each on why it is the official
   publisher. Claude Code diffs it against `_OFFICIAL_HOSTS`/`_OFFICIAL_SUFFIXES` and lands any
   allowlist additions **before** the batch arrives. This converts the four historical
   "rejects cluster by country" incidents from batch-killers into a 10-minute PR. Preflight is
   Deliverable 0 of every corridor campaign.
2. **Echo-the-contract check.** Every batch README opens with the contract version line
   (`contract: andrea-denis-brief-2026-08-21 §3`) and the S1-style scoping self-audit table
   (per-fact one-line nationality justification). A batch without both is returned unopened.

**Guardrails (unchanged, brief §8):** never write code/DB; never null or guess nationality;
never invent a source, number, fee, deadline; never a served status; never merge.

---

## 4. Part II — Corridor data campaigns (the heavy lifting)

### 4.0 Why re-deliver instead of converting the wave batches

S4's ~1,100 GCS facts are pre-contract: wrong vocabulary, no nationality/status scoping, unknown
citation quality, and ES/GB/IT don't exist at all. Converting them means Claude Code hand-repairs
scoping for 1,100 rows — precisely the review bottleneck this plan exists to avoid, and scoping
is the one field that cannot be inferred mechanically (it's read from each fact's own text).
Otto re-delivering under the contract costs Otto compute (free) instead of human review (the
constraint), and the wave content remains available to Otto as its own prior research.
**Exception:** NL (S5) converts mechanically because its entities file preserves topic joins.

### 4.1 The standard corridor campaign package

One campaign = one corridor direction = **7 deliverables**, each its own Notion card, in
dependency order. This is the template; per-corridor tailoring below.

| # | Deliverable | Type | Gate |
|---|---|---|---|
| 0 | Source preflight (`sources-manifest.md`) | md | Allowlist diff lands first |
| 1 | Destination requirement facts, nationality-scoped, per employee-status | Type 1 | E4 gate; 100% promote (0 Unmapped) |
| 2 | Origin/departure obligations (de-registration, tax exit, social-security exit, the "preserve X before leaving" traps) | Type 1 | E4 gate |
| 3 | Non-obvious traps annex: for each trap, `non_obvious_note` (Commonly believed / Actually / Action required) + step-candidate list for the pathway graph | in 1&2 + README | ≥N non_obvious facts (per-corridor target) |
| 4 | Vendor directory (destination city): movers, letting/relocation agents, bank onboarding, immigration counsel where relevant | Type 2 | Every row: resolving URL + registry evidence |
| 5 | RAG corpus (Tier-1 pages the facts cite) | Type 3 | sha256 per doc; publisher = official |
| 6 | Reference datasets the corridor's advisories need (visa-required lists, fee tables, processing-time pages) | Type 4 | Closed-world, cited |
| 7 | CVR prep pack: the corridor's facts as the CVR-TEMPLATE "did you already know this?" question set | md | Maps 1:1 to delivered non_obvious facts |

**Per-campaign metrics** (in the batch README, re-checked by Claude): promote rate 100% ·
nationality-scoped 100% (S1 audit + `overserved_requirements` stays 0 for the slice) · manifest
reconciliation exact · citation-resolves ≥95% · zero fabrication (every fact_text has a
supporting quote) · non-obvious recall ≥ prior for the corridor slice.

### 4.2 The campaign schedule

**Wave 1 — the live demo corridors (dispatch on approval).** Cards exist; arm them with §3.
- **C-ESIE · ES→IE (Andrea, non-EEA/THIRD_COUNTRY):** = AIQ-2061(A1 redo), 2062/2051(ES exit),
  2063/2052(ISD list), 2064(Dublin vendors — also unblocks AIQ-1871's empty marketplace),
  2065(corpus — supersedes the estimated-lead-times problem in AIQ-1852), 2066/2053(doc-extraction
  ref), 2071(S1 self-audit). Non-obvious target: ≥9 (the CSEP graph already carries 14 — facts
  must at least cover the graph's traps).
- **C-NOFR · NO→FR (Denis, EEA):** = AIQ-2067(D1 redo), 2068/2054(NO exit — **hand Otto the 4
  existing `NO_FR` origin fact_keys first**, per the handoff), 2069/2055(Paris vendors),
  2070/2056(FR corpus). Plus the FR_NO third-country pathway decision (the pinned
  `KNOWN_VIOLATIONS` overserving) stays a product decision, not an Otto task.

**Wave 2 — served-but-thin corridors (dispatch as wave-1 batches clear review).**
- **C-FRDE · FR→DE:** biggest live corridor, thinnest asset (9 stub steps, zero traps, and the
  historical "Germany seeded `[other]` only" scar). Full 7-deliverable package; non-obvious
  target ≥8 (Anmeldung timing, Rundfunkbeitrag, church-tax opt-out, Steuer-ID vs Steuernummer…).
- **C-INDE · IN→DE:** the 21-step Blue Card graph has **zero** non_obvious annotations — this
  campaign is traps-first (deliverables 0,1(gap-fill),2,3 only, then 4–7 later). THIRD_COUNTRY
  scoping throughout.
- **C-IEES · IE→ES:** data batch already exists (25 records, pending). Campaign is **review
  support, not re-research**: Otto delivers the dead-link re-sourcing (the 2 SPAIN 404s), the
  evidence pack refresh, and the counsel-question briefs for the 2 treaty records. Claude
  applies the unapplied migration + review. Notion: AIQ-1987 reframed accordingly.
- **C-GBNO / C-NOGB · GB↔NO:** = AIQ-1988/1989. **Blocked on a Claude-side prerequisite:** author
  the GB_NO THIRD_COUNTRY pathway + registry entry first (the corridor is deliberately
  unregistered; researching facts before the pathway exists repeats the IE_ES
  "authored-not-served" trap). Otto's brief must state UK-national-as-third-country explicitly.

**Wave 3 — the stubs, by demand signal.** DE_NO, ES_NL, FR_CH, FR_ES, FR_NL each get the
package only when a real case, prospect, or demand-pull signal exists (AIQ-1961's measured
corridor-reuse score is the gate — no anchoring case, no campaign; that is card AIQ-1944's
principle). Until then they keep their stub graphs and fail closed.

**Cross-cutting re-sourcing:** AIQ-2030 (Singapore 55 + Australia 7 facts citing JS-shell pages
that can never be evidence-checked) runs as its own Otto card with Type-1 re-delivery of just the
citations.

---

## 5. Part III — Theory-corpus campaigns (the "real core" work)

The theory corpus (10 books + 37 course analyses + synthesis playbook) is ReloPass's conceptual
engine: generator–verifier separation, corridor transfer as fine-tuning, the relief-moment eval,
data-moat-by-non-obviousness. Nearly all of it already exists as *analysis*; ~40 Notion cards
already exist as *implementation intents*. What's missing is the connective tissue. Otto does
three things:

**T1 · Re-materialize the corpus as repo markdown.**
Goal: every analysis greppable in-repo. Spec: Type-5 delivery of all 37 course analyses (from
Otto's own GCS bundles/ZIPs — it authored them) into `docs/course-analysis/<source>/<item>.md`,
including the QA-failed stubs (marked) and the provenance headers; the reconstructed CS229/CS230
files flagged Tier-2 per §3. Books are E1 (already done, just committing). Acceptance: 37 files,
each with provenance header + Application-to-ReloPass section; index README mapping analysis →
theme → Notion card ids. Notion: one card.

**T2 · Theory-to-spec digests, one per theme (7).**
Goal: turn each theme (Architecture · Transfer Learning · Data Quality · Human-in-Loop · Scaling
Laws · Trust Architecture · Relief Moment) into a Claude-Code-implementable digest. Spec: per
theme, a Type-5 doc that (a) collects every claim across the 47 analyses supporting the theme,
(b) maps each to the existing card(s) in AIQ-1936–1985/2018–2022 — **naming the card id** —
(c) for each card, drafts the missing engineering artifacts: acceptance criteria, eval metric,
test sketch, and the decomposition proposal where the card sits in Needs Decomposition
(1936, 1937, 1938, 1944, 1945, 1947, 1963, 1973, 1978, 2019…), (d) flags claims **no card
covers** as proposed-new-card stubs (proposals only — card creation stays with Romain/Claude per
§7). Acceptance: every AIQ id in the families appears in exactly one digest; each Needs-
Decomposition card has a proposed subtask breakdown ready for the `notion-decomposition` flow.
This is what makes Otto "work on all the theories": not re-reading books, but converting
finished theory into executable specs.

**T3 · Eval ground-truth packs (the returns-on-investment engine).**
Goal: the evals the theory demands get their data from Otto, their harnesses from Claude.
- **T3a · Golden relocation cases** (AIQ-1898): 10 fully-specified personas across the wave-1/2
  corridors (nationality, family, employer, dates) with the *expected* requirement set +
  non-obvious traps + infeasibility flags, each expectation cited. Feeds `nonobvious_recall`,
  `overserved_requirements`, and the CSP feasibility check (AIQ-1947).
- **T3b · HLP baselines per corridor** (extending `backend/eval/hlp_nonobvious_baseline.json`):
  what a competent generalist would list unaided for each corridor×employee-type slice — the
  denominator of the moat metric.
- **T3c · Relief-moment eval design pack** (AIQ-1945): the measurement spec (what event, what
  proxy, what instrumentation) drafted from the fear-relief theory for human review before any
  model work.
- **T3d · Hard-negative registry** (AIQ-1943): the look-alike pairs (Norway EEA-not-EU, Ireland
  non-Schengen, post-Brexit GB) as a Type-4 dataset with citations.
Acceptance: each pack loads into the existing eval harnesses (`nonobvious_recall.py`,
`overserving.py`) without code changes beyond registration.

**T4 · Competitive/positioning research** already queued (AIQ-2043 Benivo teardown, AIQ-1571
Why-Now narrative, AIQ-1899 posted-worker pack, AIQ-1900 transparency page draft, AIQ-1901 cost
model): arm each card's Execution Prompt with the Type-5 format + the §3 honesty rules
(**no compliance-status claims** — the AIQ-1513 hard gate binds marketing research too).

---

## 6. Metrics, evals, validation — the return on all of it

**Per batch (machine, before any human):** E4 gate report — sha256 ✓, counts ✓, 0 parser
rejections, scoping 100%, citations ≥95% resolve, candidate-only ✓.

**Per corridor (after load):** `nonobvious_recall` ≥ baseline for the slice ·
`overserved_requirements` = 0 (precision axis: an EEA mover never sees third-country content) ·
corridors-serving-nothing = 0 for the campaign's destination · citation-evidence spot-check
(quote verbatim on page) on a 20% sample · CVR within 30 days of serving (the §4.1#7 pack makes
this cheap).

**Programme (weekly, one dashboard number each):**
1. Stranded-asset register open rows (§1.2) → 0.
2. Candidates awaiting human review (should stay under ~50; if it grows, pause dispatch — §7.3).
3. Corridors with served, corridor-derived, nationality-scoped facts (today: 0; wave 1 target: 2).
4. Theory cards with engineered spec attached (T2 coverage of the ~40-card families).
5. Eval suite: slices green / total slices.

**Validation pipeline per batch (Claude side, unchanged from brief §6):** gate → load as
candidates (`--apply`) → promote to `pending` (`--promote`) → human review → reuse code (corpus
indexing, vendor registry, extractor locales, reference-data wiring). A batch failing the gate
goes back to Otto with the gate report — never hand-repaired (the one exception on record:
mechanical NL conversion, E5).

---

## 7. Notion routing & anti-bottleneck rules

**7.1 Lanes.** Otto cards → `Otto ready` (bridge lists priority-ascending; a human triggers; the
bridge writes back only the Status flip — results arrive through the file channel, and Claude
Code reconciles the run). Anything whose deliverable is a commit → `Ready for AI`. Cards are
fetched/updated **by page URL**, never by AIQ search.

**7.2 Card hygiene before dispatch (one-time cleanup, Claude Code):**
- Consolidate the duplicate Andrea/Denis series: keep AIQ-2061–2071, fold AIQ-2051–2056 into
  them as links, close the duplicates with a pointer.
- Fix the five known-unrunnable cards (AIQ-1993/1994/1852 no agent; **AIQ-1833** no Execution
  Prompt — it becomes the pointer card to §3 of the brief; AIQ-1571 no Validation Criteria).
- Every dispatched card's `Execution Prompt` embeds: the §3 contract pointer + deliverable type,
  the exact batch-id, the E4 Test Command, and its Acceptance line. `Autonomy Tier = 🔴` for
  anything feeding served content.

**7.3 Anti-bottleneck rules (the design constraint the user set):**
1. **Machine gates before human eyes.** No human reviews a batch the E4 gate hasn't passed.
2. **Batch size ≤25 facts.** Bigger research splits into multiple batches (a 300-fact NO wave is
   12 reviewable batches, not one wall).
3. **WIP limit: max 2 corridor campaigns awaiting review at once.** Otto can research ahead
   (waves are pipelined), but nothing new is *dispatched to review* while the review queue holds
   >50 candidates.
4. **Parallel lanes don't block each other.** Theory campaigns (T1–T4) are review-light (docs,
   not served data) and run concurrently with corridor waves; extraction tasks (E-series) are
   Claude-only and run immediately.
5. **Returns are inspected per batch**, not per campaign: a batch that clears the gate and review
   ships its reuse code the same week — value lands continuously, not at campaign end.

**7.4 Dispatch cadence.** Weekly: dispatch next cards per WIP rule → reconcile arrived batches →
review sprint (E7-style sheets) → update the five programme metrics → the Friday digest cites the
dashboard numbers.

---

## 8. Sequencing — what happens the moment this is approved

1. **Merge PR #1960** (the contract this whole plan points at).
2. **E-series in parallel** (Claude Code): E1 (theory files — 30 min), E2+E3 (guardrail +
   idempotency PRs), E4 (the gate — blocks all dispatch), E10, E11.
3. **Card hygiene** (§7.2), then **dispatch Wave 1** (C-ESIE + C-NOFR full packages) and
   **T1+T2** (corpus re-materialization + theory digests) — these four campaigns saturate Otto
   without touching the review budget until the gate is live.
4. E5–E9 as review capacity allows; E6 decision doc to Romain within the week.
5. Wave 2 dispatch when Wave 1 batches clear review; GB↔NO only after the pathway prerequisite.

**Explicitly deferred decisions (Romain's):** E6 option choice · GB_NO pathway authoring
priority · FR_NO third-country overserving resolution · wave-3 corridor order.
