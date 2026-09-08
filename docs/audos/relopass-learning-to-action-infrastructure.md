# ReloPass Learning → Action Infrastructure

*Definitive architecture reference. Version 1.0 — 2026-08-17. Owner: ReloPass founder + Otto. Scope: the end-to-end system that turns external learning (courses, books, conference talks) and corridor research into verified, prioritized, executable actions inside the ReloPass codebase and knowledge graph.*

---

## Purpose: Why this system exists

ReloPass wins on one thing: **being reliably, verifiably right about international relocation corridors, corridor after corridor, and staying right while competitors' snapshots rot.** That is a knowledge-and-execution problem, not a coding problem. To sustain it we needed a repeatable machine that does four things without the founder having to re-invent the process each time:

1. **Ingest** high-quality external knowledge (AI/ML engineering courses, foundational books, conference talks) without wasting hours on dead-end sources.
2. **Extract** that knowledge into a consistent, QA-gated, machine-readable format — every analysis looks the same, so it can be synthesized and searched.
3. **Synthesize** dozens of analyses into a small number of themes and a single prioritized recommendation table the founder can actually act on.
4. **Act** — turn each recommendation into a Notion task, and let Otto pull "Otto ready" tasks and execute them as draft jobs against the codebase, closing the loop back to Notion.

The reason this is written down: the pipeline was built fast (2026-08-15 → 2026-08-17) and lives partly in Otto's memory, partly in hooks, partly in Notion, and partly in local Python scripts. If any one piece is forgotten, the loop breaks. This document is the single source of truth so the founder — or a future collaborator, or a fresh Otto conversation — can rebuild, extend, or trigger any part of it from scratch.

**The one-sentence mental model:** *Learning goes in as messy web content; verified, prioritized, executable actions come out the other end and land as draft jobs in the ReloPass workspace — with Notion as the control panel in the middle.*

---

## System Map

```
                        ┌───────────────────────────────────────────────────────┐
                        │              EXTERNAL KNOWLEDGE SOURCES               │
                        │  CS50 / Harvard notes · MIT OCW · GitHub course repos  │
                        │  · conference abstracts · foundational books           │
                        │  ✗ YouTube captions (PERMANENTLY BLOCKED — never try)  │
                        └───────────────────────────┬───────────────────────────┘
                                                     │
                     LAYER 1: CONTENT INGESTION      │  (pick highest-priority source that exists)
                                                     ▼
                        ┌───────────────────────────────────────────────────────┐
                        │           LAYER 2: v3 EXTRACTION PIPELINE             │
                        │  1 locate → 2 fetch → 3 extract → 4 QA gate → 5 write   │
                        │  QA gate: ≥500 words + topic keywords ⇒ PASS / FAIL     │
                        │  Grouped in 4-batch waves; one brief per batch          │
                        └───────────────────────────┬───────────────────────────┘
                                                     │  one structured .md per item
                                                     ▼
                        ┌───────────────────────────────────────────────────────┐
                        │            LAYER 3: ANALYSIS TEMPLATE                 │
                        │  QA Status · Content Excerpt · Summary · Frameworks ·   │
                        │  ReloPass Recommendations (P0 / P1 / P2)                │
                        └───────────────────────────┬───────────────────────────┘
                                                     │  N analyses accumulate
                                                     ▼
                        ┌───────────────────────────────────────────────────────┐
                        │              LAYER 4: SYNTHESIS (Tier 2)              │
                        │  all analyses → 7 themes → 30–50 prioritized recs table │
                        │  → ReloPass-AI-ML-Playbook-Master-v2.md                 │
                        └───────────────────────────┬───────────────────────────┘
                                                     │  each rec becomes a task
                                                     ▼
                        ┌───────────────────────────────────────────────────────┐
                        │           LAYER 5: NOTION TASK PIPELINE               │
                        │  Notion DB 3bc887c6…  (33 props)                        │
                        │  Status: Not started → Otto ready → In progress → Done  │
                        │  notion-task-sync hook → WorkspaceDB.notion_tasks       │
                        └───────────────────────────┬───────────────────────────┘
                                                     │  Status = 'Otto ready'
                                                     ▼
                        ┌───────────────────────────────────────────────────────┐
                        │          LAYER 6: OTTO EXECUTION BRIDGE               │
                        │  query Notion(Otto ready) → create Otto draft task from │
                        │  Execution Prompt → set Notion 'In progress' → run →    │
                        │  set 'Done'                                             │
                        └───────────────────────────┬───────────────────────────┘
                                                     │  code / content changes
                                                     ▼
                        ┌───────────────────────────────────────────────────────┐
                        │   ReloPass CODEBASE  +  CORRIDOR KNOWLEDGE GRAPH       │
                        │   (Case Command, corridor specs, vendor tables, …)      │
                        └───────────────────────────┬───────────────────────────┘
                                                     │  documents / deliverables
                                                     ▼
                        ┌───────────────────────────────────────────────────────┐
                        │            LAYER 7: DOCX DELIVERY                     │
                        │  Python stdlib OOXML → .docx → named ZIP bundle         │
                        │  ZIP entries = real titles · ZIP itself = storage code  │
                        └───────────────────────────────────────────────────────┘
```

The pipeline is a straight line with one feedback arrow: **Layer 6 writes results back to Layer 5** (Notion status flips to Done), which is what makes it a loop and not just a conveyor belt.

---

## Layer 1: Content Ingestion

The single biggest time-sink in learning extraction is fetching from sources that don't yield clean text. Layer 1 exists to make the source choice **deterministic** so we never re-litigate it.

### Source priority hierarchy (ordered — always try top-down)

1. **CS50 / Harvard course notes.** Best case. Harvard publishes full prose lecture notes with headings and code. Rich, clean, keyword-dense. Almost always clears the QA gate on the first pass.
2. **MIT OpenCourseWare (OCW).** Lecture notes, problem sets, reading lists, and slide PDFs. Strong for theory-heavy material (e.g. MIT 6.7960 Deep Learning).
3. **GitHub course repositories.** Many modern courses (DeepLearning.AI, MLOps specializations) publish notebooks, READMEs, and markdown lecture notes in a public repo. Fetch the raw `.md` / `.ipynb`.
4. **Conference abstracts & talk pages.** For talks (AI Dev 26 x SF, research summits), the abstract + speaker notes + linked slides are the extractable surface. Shorter, but real.
5. **Official documentation / primary sources.** For books and named frameworks, use the publisher page, author's site, or an authoritative summary — never a scraped transcript.

### What to do with each content type

| Content type | Where to look | Extraction target |
|---|---|---|
| University lecture | CS50 notes → OCW notes | Full prose notes; fall back to slide PDF text |
| Bootcamp / specialization | GitHub course repo | Raw README / notebook markdown |
| Conference talk | Talk/abstract page | Abstract + speaker notes + linked slides |
| Book | Publisher/author page + authoritative summary | Thesis, framework, chapter structure |
| Blog / primary doc | The doc itself | Body prose |

**Concrete example.** For *CS50x 2026, Lecture 4 (Memory)*: skip YouTube entirely, go straight to the CS50 Lecture 4 notes page, fetch the prose, confirm it contains "pointer", "malloc", "memory" (topic keywords) and >500 words → PASS → write the analysis. Total: one clean fetch.

### YouTube: the definitive answer

**Never try YouTube captions. Ever.** This is a permanent, non-negotiable rule, not a preference. Auto-generated captions are unpunctuated, keyword-sparse, and frequently fail the QA gate; the transcript endpoints are blocked/unreliable; and every attempt burns time we could spend on a source that works. If a piece of content *only* exists as a YouTube video with no notes, no repo, no slides, and no abstract — **it is out of scope for this pipeline.** Find a different item or a different course. There is no "just this once."

---

## Layer 2: v3 Extraction Pipeline

The v3 pipeline is the proven procedure for turning one ingested source into one analysis file. It has exactly five steps.

### The 5 extraction steps

1. **Locate.** Using the Layer 1 hierarchy, find the highest-priority source that actually exists for this item. Record the resolved URL.
2. **Fetch.** Pull the raw content (web fetch / raw GitHub / PDF text). No YouTube.
3. **Extract.** Strip navigation/boilerplate; keep headings, body prose, code blocks, framework names, and any numbered/step content.
4. **QA gate.** Apply the pass/fail test (below). A FAIL is recorded as a `QA_FAILED_*` stub and is **excluded** from the corpus and from any bundle — it is not a real analysis.
5. **Write.** Emit the structured analysis `.md` (see Layer 3), leading with the QA Status line.

### QA gate criteria by content type

Baseline gate for everything: **≥ 500 words of substantive extracted text AND presence of the expected topic keywords.**

| Content type | Word floor | Keyword check (examples) |
|---|---|---|
| University lecture | ≥ 500 | Lecture's core terms (e.g. "gradient", "backprop" for a DL lecture) |
| GitHub repo lecture | ≥ 500 | Framework/library names named in the syllabus |
| Conference talk | ≥ 350 (abstracts run shorter) | Talk's stated topic terms |
| Book synthesis | ≥ 500 | Author's named framework(s) |

If a source is borderline on words but keyword-rich, prefer to enrich from the next source down the hierarchy rather than pass a thin analysis. **A thin PASS pollutes the synthesis; a clean FAIL is honest.**

### How to write a batch task brief (template)

Batches are dispatched as delegated jobs. Reuse this brief verbatim, filling the brackets:

```
OBJECTIVE: Extract & analyze [N] items from [COURSE NAME] into ReloPass v3 analysis files.

FOR EACH ITEM:
  1. LOCATE the highest-priority source (CS50 notes → MIT OCW → GitHub repo →
     conference abstract). NEVER use YouTube captions.
  2. FETCH raw content; record the resolved source URL.
  3. EXTRACT prose, headings, code, framework names.
  4. QA GATE: ≥500 words + topic keywords [LIST KEYWORDS]. PASS/FAIL.
     - FAIL → write QA_FAILED_[slug].md stub and move on (do NOT fabricate).
  5. WRITE analysis MD using the standard template (QA Status, Content Excerpt,
     Summary, Frameworks, ReloPass Recommendations P0/P1/P2).

ITEMS:
  - [item 1 title + expected source]
  - [item 2 title + expected source]
  ...

DELIVERABLE: one .md per PASSED item + a one-line PASS/FAIL manifest.
```

### The 4-batch grouping pattern

Long courses are split into **4 batches** dispatched as separate jobs, for three reasons: (a) each job stays inside its context/time budget, (b) a failure in one batch doesn't lose the others, (c) batches can run without blocking each other where the platform allows.

**Concrete example — CS50x 2026 (12 lectures):**
- Batch 1: Lectures 0–2 (Scratch, C, Arrays)
- Batch 2: Lectures 3–5 (Algorithms, Memory, Data Structures)
- Batch 3: Lectures 6–8 (Python, SQL, HTML/CSS/JS)
- Batch 4: Lectures 9–10 + AI special lecture (Flask, Ethics, AI)

Each batch is one brief; the 12 resulting analyses are named by lecture title and later bundled together.

---

## Layer 3: Analysis Template

Every analysis file is identical in shape. Consistency is the whole point — it makes Layer 4 synthesis mechanical and Layer 5 recommendation-lifting reliable.

### The analysis MD format (copy-paste ready)

```markdown
# [Course] — [Lecture/Talk/Book Title]

**QA Status:** PASS  (words: 1,240 | keywords found: pointer, malloc, heap, stack)
**Source:** [resolved URL] (priority tier: CS50 notes)
**Date analyzed:** 2026-08-17

## Content Excerpt
> [200–400 words of the cleanest extracted prose, verbatim, as evidence the
>  fetch was real and the QA gate was honestly applied.]

## Summary
[3–6 paragraph plain-English summary of what this lecture/talk/book actually
 teaches — the ideas, not the syllabus bullet points.]

## Frameworks
- **[Named framework 1]** — one-line description + where it applies.
- **[Named framework 2]** — ...

## ReloPass Recommendations
### P0 — do now (directly de-risks a live corridor or the trust architecture)
- [specific, buildable recommendation tied to a ReloPass surface]
### P1 — do next (clear value, not blocking the current cycle)
- [specific recommendation]
### P2 — worth remembering (future / speculative)
- [specific recommendation]
```

### How to write ReloPass recommendations (P0/P1/P2 criteria)

- **P0 — do now.** Directly reduces risk on a *live, verified corridor* (FR↔NO, ES→IE, NO→FR) or hardens the **trust architecture** (deterministic engine, source attribution, lawyer sign-off) or protects the **relief moment**. If getting this wrong could put a wrong requirement in front of an HR generalist, it's P0.
- **P1 — do next.** Clear, concrete value — better evals, better data hygiene, a reusable authoring method — but it isn't blocking the current build cycle.
- **P2 — worth remembering.** Speculative, future-stage, or dependent on volume we don't have yet (e.g. data-effect benchmarks that need many completed moves).

### What makes a recommendation specific vs. vague

A recommendation must name **a ReloPass surface, an action, and a why.** If it reads like generic ML advice, it's not done.

| ❌ Vague (reject) | ✅ Specific (keep) |
|---|---|
| "Use good evals." | "**P0** — Add a `relief_moment_response` PostHog eval gate: no corridor ships until one real user answers 'was anything here new to you?' with Yes. (Huyen eval-first: define success before building.)" |
| "Improve data quality." | "**P1** — Store every Case Verification Report in the CVR schema (official_guidance / actual_reality / action_required / source) so it doubles as v1 fine-tuning data. Bad facts now = wrong model later (Raschka)." |
| "Consider human review." | "**P0** — Keep the lawyer sign-off gate on every corridor fact before it serves; it is a data-quality gate, not just regulatory cover (CS329A generator-verifier)." |

---

## Layer 4: Synthesis

One analysis is a note. Thirty-seven analyses are noise unless they're synthesized. Layer 4 (Tier 2) collapses the whole corpus into **7 themes** and a single **30–50 row prioritized recommendation table** — the master playbook.

### When to run Tier 2 synthesis

Run (or re-run) synthesis **after each new batch of analyses completes** — not after every single file. A batch is the natural unit: finish a course's 4 batches, then fold all its new analyses into the master playbook in one pass. The output file is `ReloPass-AI-ML-Playbook-Master-v2.md`.

### How to add new analyses to an existing synthesis

1. Collect the new PASSED analyses (ignore `QA_FAILED_*`).
2. For each, lift its P0/P1/P2 recommendations into the master table with a source column pointing back to the analysis.
3. Assign each recommendation to one of the 7 themes.
4. **De-duplicate and merge:** where a new rec restates an existing one, strengthen the existing row (add the new source) rather than adding a duplicate. Convergence across independent sources *raises* priority.
5. Re-sort the table by priority (P0 first) and bump the version (`-v2`, `-v3`, …).

### The 7 themes

1. **Architecture** — how the system is structured: generation vs. serving separation, deterministic rule engine over raw LLM output, never crossing the generation and serving layers.
2. **Transfer Learning** — reusing knowledge across corridors (40–60% reuse between adjacent stages; Norway mapping seeding the Nordic cluster).
3. **Data Quality** — verified, lawyer-signed facts as the asset; CVRs as training data; bad facts now = wrong predictions in v1 (Raschka).
4. **Human-in-Loop** — generator–verifier: LLM proposes candidates, a real user + lawyer verify before anything serves (CS329A).
5. **Scaling Laws** — corridor-by-corridor growth anchored on real cases; demand-pull gates each stage; hub multipliers (DE, SG).
6. **Trust Architecture** — source attribution + deterministic reasoning + lawyer sign-off = the answer to "why not just use ChatGPT?" (Kissinger: it's a trust argument, not a technical one).
7. **Relief Moment** — the fear→relief arc; measure "was there anything here you didn't already know?" as the north-star eval (Emotional Appeal + Huyen eval-first).

**Concrete example.** Ziegler's "run 5 LLM passes, diff, take the union for lawyer review" (from a prompt-engineering analysis) and CS329A's "generator–verifier" (from an MIT analysis) both land in **Human-in-Loop**; in synthesis they merge into one strengthened P0 row: *"Author corridor facts via multi-pass LLM consensus, then gate on lawyer verification before serving."*

---

## Layer 5: Notion Task Pipeline

Notion is the **control panel**. A recommendation isn't real until it's a Notion row, and Otto doesn't act until a row says "Otto ready." This makes the founder — not the model — the dispatcher.

### How a recommendation becomes a Notion task

1. Take a row from the master playbook table.
2. Create a Notion page in DB `3bc887c64d4880898188fcf2dc3edc1b`.
3. Set `fable` (title), `Priority`, `Product Area`, `Layer`, and — critically — write a concrete `Execution Prompt` (see below) and `Validation Criteria`.
4. Leave `Status = Not started` until the founder decides it's ready to run, then set `Otto ready`.

### The Notion DB schema (33 properties — the ones that matter)

The DB has 33 properties; most are metadata. These are the ones the pipeline actually reads or writes:

| Property | Type | Role in the pipeline |
|---|---|---|
| `fable` | Title | Human-readable task name (the row's title). |
| `Priority` | Select (P0–P3) | Dispatch order; P0 first. |
| `Status` | Select | **The trigger field.** `Otto ready` is what the bridge queries for. |
| `Execution Prompt` | Rich text | **The instruction Otto runs** — becomes the draft-task brief verbatim. |
| `Assigned AI Agent` | Select | Which agent should run it (e.g. cursor_delegation, sub_otto). |
| `Product Area` | Select | Which ReloPass surface it touches (Case Command, corridor, landing, …). |
| `Layer` | Select | Which architecture layer it belongs to. |
| `Validation Criteria` | Rich text | Definition of done; how to confirm the task actually worked. |

All 33 properties are synced, but a task is only *executable* if `Status`, `Execution Prompt`, and (ideally) `Assigned AI Agent` + `Validation Criteria` are filled.

The `notion-task-sync` hook is **live** and syncs all Notion tasks → the WorkspaceDB `notion_tasks` table on demand (**101 tasks synced to date**). This gives Otto a fast, local, queryable mirror of Notion without hitting the Notion API on every read.

### The Status workflow

```
Not started ──(founder marks ready)──▶ Otto ready ──(bridge creates draft)──▶ In progress ──(execution done)──▶ Done
```

- **Not started** — drafted recommendation, not yet approved to run.
- **Otto ready** — founder-approved; the bridge will pick it up.
- **In progress** — the bridge has created an Otto draft task from the Execution Prompt.
- **Done** — the task executed and Validation Criteria were met.

### How to write an Execution Prompt that Otto can run

The Execution Prompt is a self-contained brief — Otto will run it with no other context. It must state **what to change, where, and how to know it worked.**

**❌ Weak:** "Improve the paywall copy."

**✅ Runnable:**
```
Rewrite the CaseGate prepay value statement in
audos-workspace-776786/components/CaseGate.tsx on branch
fix/td-qa-services-batch-0719. Lead with the fear→relief arc: name the
week-seven-ambush fear, then state exactly what prepaying unlocks (full
corridor requirement list + flagged non-obvious items + timeline).
Do NOT touch pricing constants. Validation: the paywall shows a benefit
list, not just a price; screenshot before/after.
```

---

## Layer 6: Otto Execution Bridge

The bridge is the piece that makes the whole thing a *loop*. Without it, Notion is just a nice list.

### How the bridge works

**Non-technical:** The bridge is Otto reading your Notion board, finding every task you've marked "Otto ready", turning each one into a draft job in the ReloPass workspace, and flipping that Notion row to "In progress" so you can see it's been picked up. When the job finishes, the row goes to "Done." You approve in Notion; Otto does the rest.

**Technical:**
1. **Query** Notion DB `3bc887c6…` (or the synced `notion_tasks` mirror) for `Status = 'Otto ready'`.
2. For each matching row, read `Execution Prompt`, `Assigned AI Agent`, `Priority`, `Validation Criteria`.
3. **Create an Otto draft task** (`create_job_drafts`) using the Execution Prompt as the task brief and `Assigned AI Agent` to pick the `agentType` (e.g. cursor_delegation for code, sub_otto for ops/content).
4. **Update Notion** status → `In progress` (write-back via the Notion API through the `{{secrets.NOTION_API_KEY}}` secret).
5. Drafts are **not auto-run** — they land in the Tasks/Drafts column for the founder to run, exactly like any other Otto draft (code-touching drafts queue rather than run in parallel).
6. After execution completes, update the Notion row → `Done`.

### How to trigger it

Just tell Otto, in chat: **"run the Notion bridge"** (or "pull Otto-ready tasks from Notion"). Otto queries for `Otto ready`, stages the drafts, and reports which rows it picked up. You then review and run the drafts you want. Because drafts require your go-ahead to run, the founder stays in control of what actually executes.

### How to extend it (scheduled trigger option)

Today the bridge is **on-demand** (founder says "run the Notion bridge"). To make it autonomous, register a scheduled workspace hook that runs the same query on a cron (guarded by the `{{secrets.CRON_SECRET}}`), e.g. every morning: query `Otto ready`, stage drafts, and send the founder a daily notification listing what's queued. Keep the **human go-ahead on the actual run** even if the *staging* is automated — auto-staging is safe, auto-running code changes is not. This is the natural next upgrade and is compatible with the current design; nothing else has to change.

---

## Layer 7: DOCX Delivery

Deliverables (analyses, playbooks, this document) go to the founder as Word `.docx` files bundled in a ZIP. Layer 7 is the standing procedure for producing them.

### The Python stdlib OOXML pattern (why, how)

**Why stdlib.** The sandbox has no `pandoc`, no `python-docx`, and no network for installing them. A `.docx` is just a ZIP of XML parts, so we generate it directly with Python's standard library (`zipfile` + string-built OOXML). No dependencies, fully reproducible.

**How.** A converter script (`/tmp/md2docx.py`, exposing `write_docx`) parses the markdown — headings (`#`/`##`/`###`), paragraphs, bullet/numbered lists, and fenced code blocks — and emits the three required OOXML parts (`[Content_Types].xml`, `_rels/.rels`, `word/document.xml`), then zips them into a valid `.docx`. Validation is always: `os.path.exists(path)` **and** `os.path.getsize(path) > 8000` bytes (a real document is never smaller).

### Named ZIP bundle convention

`store_attachment` always mints a **coded object key** (e.g. `…_wy9l610t.zip`); the `filename` argument is metadata only and does **not** set the download name. So a single loose `.docx` would download under a meaningless code. The fix: **bundle the `.docx` files into a ZIP whose *entry names* are the real class/lecture/book titles.** On extraction, the files come out correctly named.

### Standing rule

> **ZIP entries = real human titles. The ZIP file itself = storage code (acceptable).**

The container's coded name doesn't matter — it's just a wrapper. What the founder sees after unzipping are properly named documents (e.g. `CS50x-Lec4-Memory.docx`). Always verify a bundle before sending: `ZipFile.testzip()` returns `None` and the entry names are clean. GCS media objects are publicly downloadable from the sandbox, so past deliverables can be re-fetched from their media URLs and re-bundled at any time.

---

## For Expansion: Adding New Content

### Step-by-step checklist for a new playlist / course

- [ ] **1. Confirm the source exists off-YouTube.** Check CS50/Harvard notes → MIT OCW → GitHub repo → conference/abstract page. If it's YouTube-only, **drop it** and pick another course.
- [ ] **2. List the items** (lectures/talks/chapters) and the expected source per item.
- [ ] **3. Split into 4 batches** by item order.
- [ ] **4. Write one batch brief per batch** from the Layer 2 template (fill in items + topic keywords).
- [ ] **5. Dispatch the batches** as delegated jobs.
- [ ] **6. Collect PASSED analyses**; discard `QA_FAILED_*` stubs.
- [ ] **7. Re-run Tier 2 synthesis** to fold the new analyses into `ReloPass-AI-ML-Playbook-Master-v2.md` (merge/dedupe, re-sort, bump version).
- [ ] **8. Lift new P0/P1 recs into Notion** as tasks (fill `fable`, `Priority`, `Execution Prompt`, `Assigned AI Agent`, `Validation Criteria`; `Status = Not started`).
- [ ] **9. Mark the ones you want run `Otto ready`.**
- [ ] **10. Tell Otto "run the Notion bridge."**
- [ ] **11. Convert deliverables to DOCX** and bundle with named ZIP entries.
- [ ] **12. Update the Corpus Inventory** in this document.

### How a new corridor becomes a Notion task set

A new relocation corridor (say **GB→NO**, Stage 1) follows the same machine, with corridor research standing in for course analyses:

- [ ] **1. Anchor on a real case** — demand-pull rule: no corridor without a real move/test user anchoring it.
- [ ] **2. Author candidate facts** — multi-pass LLM consensus (Ziegler: 5 passes, take the union) into the corridor spec's `Non-Obvious Practical Realities` blocks (`official_guidance / actual_reality / action_required / source`).
- [ ] **3. Lawyer verification gate** — no fact serves until signed off (data-quality gate, not just compliance).
- [ ] **4. Create Notion tasks** — one per build item (spec, vendor shortlist, non-obvious flags, eval), with Execution Prompts pointing at the specific ReloPass surfaces.
- [ ] **5. Mark `Otto ready` → run the bridge → Otto stages drafts → founder runs them.**
- [ ] **6. Capture the Case Verification Report** — it doubles as v1 training data.

### Corridor knowledge graph → Notion → Otto → codebase loop

```
Real case  ─▶  corridor knowledge graph      (country-pair × employee-type × requirements, lawyer-verified)
             │
             ▼
          Notion tasks  (Execution Prompt per build item, Status: Otto ready)
             │
             ▼
          Otto bridge   (stages drafts → founder runs)
             │
             ▼
          ReloPass codebase  (Case Command specs, vendor tables, flags, evals)
             │
             ▼
          Case Verification Report  ─▶  feeds back into the knowledge graph + v1 training data
```

That final arrow is the compounding loop: more corridors → more trust → more cases → deeper lock-in → better data → sharper flagging → more trust.

---

## Corpus Inventory

### The 37 completed analyses

All 37 are delivered as named `.docx` inside the master bundle **`ReloPass-All-Analyses-Named.zip`** (each ZIP entry named by class/lecture/book title). Individual analyses are not published as 37 separate public URLs — the bundle is the delivery artifact.

| Course / source | Items analyzed | QA |
|---|---|---|
| CS50x 2026 | 12 (Lec 0–10 + AI special lecture) | All PASS |
| MIT 6.7960 Deep Learning | 7 (lectures + tutorials) | All PASS |
| MLOps Specialization | included in master corpus | PASS |
| DeepLearning.AI | included in master corpus | PASS |
| AI Dev 26 x SF (conference) | included in master corpus | PASS |
| **Total** | **37 analyses** | **37 PASS** (QA_FAILED stubs excluded) |

*Note on individual GCS URLs:* the task requested a per-analysis GCS URL column. Individual analyses were bundled rather than uploaded one-by-one, so per-file public URLs do not exist — the honest artifact is the named ZIP bundle (URL in Quick Reference). If per-analysis public URLs are needed later, re-store each `.docx` individually via `store_attachment`.

### Books (10-book synthesis, 2026-08-15)

Ten foundational books read across the Aug 14–15 sprint, synthesized into one unified architecture (LLM generates candidates → real user + lawyer verifies → deterministic engine serves → eval measures relief moment → verified facts become v1 training data → domain data is the moat → positioned as "brilliant friend" → scale corridor-by-corridor → never cross generation/serving layers). Contributing authors/frameworks: **Ziegler** (prompt engineering / multi-pass consensus), **CS329A** (generator–verifier), **Huyen — *AI Engineering*** (eval-first, reliability), **Kissinger — *The Age of AI*** (trust architecture), **Raschka — *Build a Large Language Model*** (CVR-as-training-data), **Kai-Fu Lee — *AI Superpowers*** (domain-data moat), **Mollick — *Co-Intelligence*** ("brilliant friend"), **Emotional Appeal** (fear→relief arc), **Scaling Up Excellence** (corridor-by-corridor scaling), **Blue Ocean** (surgical differentiation).

### Recommended next content

- **Full-stack / production LLM courses** with public notes or GitHub repos (RAG, eval harnesses, fine-tuning) — directly feed the v1 employee chatbot roadmap.
- **Compliance / legal-tech talks** with published abstracts — reinforce the trust-architecture theme.
- **Data-engineering course notes** — sharpen the corridor knowledge-graph maintenance ("continuous re-verification engine") story.
- Any course above that is **YouTube-only → skip.**

---

## Quick Reference

### Otto commands to remember

| Say this to Otto | What happens |
|---|---|
| "run the Notion bridge" | Otto queries Notion for `Status = Otto ready`, stages a draft per task from its Execution Prompt, flips those rows to `In progress`. You then run the drafts. |
| "extract [course] — 4 batches" | Otto builds 4 batch briefs from the Layer 2 template and dispatches them. |
| "re-run the master synthesis" | Otto folds new PASSED analyses into `ReloPass-AI-ML-Playbook-Master-v2.md` (merge/dedupe, re-sort, bump version). |
| "bundle [analyses] as named DOCX" | Otto converts to `.docx` (stdlib OOXML) and returns one named-entry ZIP. |
| "sync Notion tasks" | Runs the `notion-task-sync` hook → refreshes the WorkspaceDB `notion_tasks` mirror. |

### Notion property names cheat sheet

- `fable` — task title.
- `Priority` — P0 / P1 / P2 / P3 (dispatch order).
- `Status` — **Not started → Otto ready → In progress → Done** (`Otto ready` = the trigger).
- `Execution Prompt` — the exact brief Otto runs.
- `Assigned AI Agent` — chooses the agentType (cursor_delegation / sub_otto / …).
- `Product Area` — which ReloPass surface it touches.
- `Layer` — which architecture layer it belongs to.
- `Validation Criteria` — definition of done.
- Notion DB id: **`3bc887c64d4880898188fcf2dc3edc1b`** · WorkspaceDB mirror table: **`notion_tasks`** (101 synced).

### GCS URLs for the ZIP bundles (verified 2026-08-17)

| Bundle | Contents | URL |
|---|---|---|
| **ReloPass-All-Analyses-Named.zip** | Master — all 37 analyses, named entries | https://storage.googleapis.com/audos-images/workspace-media/d0c29613-9cb5-4652-9c6a-494eeed352e5/1786983630283_pqsl6xw9.zip |
| **CS50x-Complete-WordDocs.zip** | CS50x — 12 lecture docs | https://storage.googleapis.com/audos-images/workspace-media/d0c29613-9cb5-4652-9c6a-494eeed352e5/1786983630921_ufzotcs1.zip |
| **MIT-6.7960-DeepLearning-WordDocs.zip** | MIT 6.7960 — 7 lecture/tutorial docs | https://storage.googleapis.com/audos-images/workspace-media/d0c29613-9cb5-4652-9c6a-494eeed352e5/1786983632267_wy9l610t.zip |
| **ReloPass-AI-ML-Playbook-Master.md** | Master synthesis playbook (source md) | https://storage.googleapis.com/audos-images/workspace-media/d0c29613-9cb5-4652-9c6a-494eeed352e5/1786915122748_qxn0sacs.md |

*(The playbook working file is `ReloPass-AI-ML-Playbook-Master-v2.md`; the URL above is the last uploaded master synthesis md. Re-upload v2 to publish a fresh URL.)*

---

*End of document. This is the single source of truth for the ReloPass Learning → Action system. Keep the Corpus Inventory and the GCS URL table current as new content and bundles are produced.*
