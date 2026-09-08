# ReloPass — Otto ↔ Claude Code Tandem Execution Plan

**Date:** 2026-08-22 · **Author:** Claude (Cowork) · **Owner:** Romain
**Built on:** the proven `otto-claude-bridge` (self-test PASSED 2026-08-22 — see `Bridge_Value_SelfTest_2026-08-22.md`).
**Purpose:** stand up a repeatable way for **Otto** (research) and **Claude Code** (ingest + code + DB) to execute ReloPass's critical corridor work **in tandem over the bridge**, with a hard contract for how one passes information to the other and a progress board kept in a fresh Otto chat.

> **Scope note.** I've scoped "critical tasks" to the **corridor-delivery pipeline** — turning verified relocation research into *correctly-served* product behaviour. That is ReloPass's core knowledge moat and legal-trust surface, and it is exactly the work the bridge unlocks (it needs a research side *and* a DB/code side). Pure Claude-Code-solo work (UI bugs, RLS fixes, infra) is **not** a tandem candidate and stays in your normal `relopass-dev-queue` / `relopass-fix-*` flows — noted in §7. Say the word to widen scope.

---

## 1. Why these are the critical tasks

ReloPass sells *correct, trustworthy relocation requirements*. Two failure modes kill it: (a) the knowledge never lands (the Phase-4 promotion wall — the founder `OTTO_LOADER_TOKEN` Otto doesn't have), and (b) it lands but serves wrong (the S1 audit risk: an EEA mover told they're exempt from Irish Emergency Tax). The bridge removes (a) as a transport blocker and makes (b) a disciplined, testable handoff. Everything below attacks those two.

The capability split is real and forces the tandem — it's not a preference:

| | Otto (Audos workspace) | Claude Code (rolec + Supabase) | Cowork-Claude (me) |
|---|---|---|---|
| Corridor research / NDJSON | ✅ owns it | ❌ | ❌ |
| Reach `audos.com` bridge | ✅ | ✅ | ❌ (egress-blocked) |
| Write ReloPass DB (service-role) | ❌ no path | ✅ owns it | ✅ (read/write, no bus) |
| Edit `rolec` code / branch / commit | ❌ code-editing disabled | ✅ owns it | ❌ |
| Run pytest / CI | ❌ | ✅ | ❌ |

No single agent can carry a corridor from research to served. The bridge is the seam that lets two credential-siloed agents act as one pipeline.

## 2. The operating model

- **Otto** = *Researcher + Bus Originator + Progress Keeper.* Produces/holds verified corridor NDJSON; pushes manifests, queries and specs onto the bus; pulls Claude Code's receipts; **maintains the run's progress board and persists it to `otto.md`.** Never touches `rolec` or the DB.
- **Claude Code** = *Ingest + Code + Verify Runner.* Polls the bus; stages facts into `otto_staging`; runs live collision checks; wires and tests serving code; promotes to serving **only after the human gate**; pushes receipts / worklists back. Runs its existing skills (`relopass-corridor-transfer`, `relopass-dev-queue`) to do the actual work — the bridge is the *intake*, not a replacement for those skills.
- **Human (Romain)** = the gate for every 🔴 action: promotion to serving, serving-code merge, lawyer review. Nothing 🔴 auto-fires.
- **Cowork-Claude (me)** = orchestration, plan authorship, DB reads/reviews on request. Can't touch the bus, so I'm not in the live loop — I set it up and audit it.

**The bus (fixed facts both agents rely on):**
- Execute URL: `https://audos.com/api/hooks/execute/workspace-776786/otto-claude-bridge`
- Actions: `push {direction, kind, payload, source?}` → `{ok,id}` · `pull {direction, sinceId?, limit?}` → `{ok, rows}` (pending only, id asc, `id > sinceId`, limit 50/max 500) · `ack {ids:[…]}` → `{ok, updated}` (flips pending→consumed, idempotent)
- Auth: secret in the `x-hook-secret` header. Claude Code reads it from `~/.otto-bridge-secret` (chmod 600); Otto uses its in-workspace secret. **Never in a payload, never printed.**
- Directions: `otto_to_claude`, `claude_to_otto`. Table `otto_claude_bridge` is `serverHooksOnly` — the hook is the only writer.
- **`kind` enum: `["message","record","manifest"]`.** Use `manifest` for fact batches, `record` for structured replies/queries, `message` for plain notes. `"receipt"` is rejected `400 invalid_kind`.

## 3. Critical tasks (the tandem queue)

Each is a true tandem with a defined direction of flow. IDs are stable; they map onto your ES→IE plan phases and are corridor-agnostic (ES→IE runs them first; the pattern repeats for NO→FR, DE→FR, …).

| ID | Task | Flow | ES-IE phase | Tier |
|---|---|---|---|---|
| **CT-1** | **Transport + stage** a corridor batch into `otto_staging` (+ collision ledger) | Otto → CC | 4 (transport) | 🟡 |
| **CT-2** | **Live collision check-as-a-service** — is this fact/topic already live? | Otto ↔ CC | 3 | 🟢 |
| **CT-3** | **Editorial reconciliation** — KEEP/SUPERSEDE/MERGE across the 4 representations; resolve conflicts | CC → Otto → CC | 6 | 🔴 |
| **CT-4** | **Wire the serving layer** — read `nationality_scope_basis`, render `assertion_mode=conditional`, surface `non_obvious`; TDD on the golden fixture | Otto (spec) → CC (build) | 5 | 🔴 |
| **CT-5** | **Promote to serving** — staged → `requirement_facts`, after review + lawyer gate | CC (human-gated) → Otto (notify) | 4 (real) | 🔴 |
| **CT-6** | **Re-sourcing worklist loop** — rejects / needs-lawyer items back to Otto to re-research | CC → Otto → CC | 7 | 🟡 |

**Critical path to value (ES→IE):** `CT-1` (stage all facts — safe, staging-only) ∥ `CT-4` (wire serving) → `CT-3` (reconcile) → **human/lawyer gate** → `CT-5` (promote). `CT-2` runs on demand throughout; `CT-6` is the exception loop. Serving (CT-4) must be correct *before* promotion (CT-5), or you promote a mis-served correctness bug.

## 4. The handoff contract (how one passes information to the other)

This is the crux. The agents **share no memory** — the bus message is the *only* channel. So every message must be self-contained and typed. One envelope, six payload types.

**Envelope (every message):**
```json
{ "direction": "otto_to_claude | claude_to_otto",
  "kind": "manifest | record | message",
  "source": "otto | claude_code",
  "payload": { "task_id": "CT-1:ES-IE:2026-08-22",
               "corridor": "ES-IE",
               "correlation_id": "<unique, generated by originator>",
               "in_reply_to": <originating PUSH_ID or null>,
               "schema_version": "1.0",
               "governance": "staging_only | promotion_requires_human_gate",
               "…type-specific fields…" } }
```

**Payload types:**

1. **MANIFEST** (Otto → CC, kind `manifest`) — a batch to stage. `batch_id`, `records:[…]` (each record in the `otto_staging` shape below), `requested_checks:["collision","dedupe"]`, `reply_with:[…]`. Chunk large batches (~10 records/message) under one shared `batch_id`; idempotency makes chunking safe.
2. **QUERY** (Otto → CC, kind `record`) — a live-DB question. `question:"collision"`, `keys:[{destination_country, topic_key, fact_key}]`, `reply_with:["dup_existing_live"]`.
3. **REPORT / RECEIPT** (CC → Otto, kind `record`) — result of staging/collision/promotion. `ok`, `staged:[{entity_id, fact_candidate_id}]`, `collision_ledger:{mapped_new, dup_in_batch, dup_existing_live, entities_created}`, `rejects:[…]`, `note`.
4. **WORKLIST** (CC → Otto, kind `record`) — re-sourcing / needs-lawyer items. `items:[{fact_uid, reason:"reject|needs_lawyer_review|conflict", detail}]`.
5. **SPEC** (Otto → CC, kind `record`) — golden-fixture / S1 expectations for serving wiring. `fixture:{persona, expected_served_rules:[…], must_not_assert:[…]}`.
6. **STATUS / ACK** — `ack {ids:[…]}` on every consumed row; a `message`-kind STATUS line at each milestone for the progress board.

**A fact record (the `otto_staging` shape — this is what MANIFEST.records must contain):**
```json
{ "destination_country":"IE", "corridor":"ES-IE",
  "entity": { "destination_country":"IE", "topic_key":"…", "domain_area":"immigration", "title":"…" },
  "topic_key":"…", "domain_area":"immigration",
  "fact_key":"…", "fact_type":"eligibility|document|step|deadline|fee|where_to_apply|account|other",
  "fact_text":"…", "source_url":"https://…", "evidence_quote":"…",
  "confidence":"high|medium|low", "confidence_score":0.9, "accuracy_tier":"representative",
  "dedupe_key":"<dest:topic:fact — the idempotency key>",
  "batch_id":"…",
  "applies_to": { "nationality_scope_basis":"nationality_determined|audience_scope",
                  "assertion_mode":"assertion|conditional", "conditional_on":"…",
                  "non_obvious":false, "needs_lawyer_review":false,
                  "review_status":"pending", "verification_status":"representative", "…":"…" } }
```

**The eight requirements every handoff MUST satisfy (highlighted, because these are what make the tandem safe):**

1. **Self-containment.** No shared memory. Every message carries `task_id` + all data the receiver needs to act. If it isn't in the payload, the other side can't use it.
2. **Correlation.** Every reply carries `in_reply_to` (the originating `PUSH_ID`) **and** `correlation_id`, so the originator matches replies without context. Poll with `sinceId` and match on these two.
3. **Idempotency.** Facts carry a stable `dedupe_key`; staging inserts are `ON CONFLICT (dedupe_key) DO NOTHING`; `ack` is idempotent. Re-runs and re-chunks are safe no-ops — never a double-write.
4. **Governance flags on the wire.** Every manifest/report states `staging_only` vs `promotion_requires_human_gate`. Nothing serves unreviewed. Promotion (CT-5) and serving merges (CT-4) are 🔴 — they wait for Romain.
5. **Provenance travels with data.** Staged rows keep `source`, `batch_id`, `verification_status`, `review_status`; reports say who verified. The receiver can always trace a fact to its origin and its review state.
6. **Durability / async.** The bus is a durable queue; the two halves need not run at the same time. A pending row waits until acked. Poll, don't block.
7. **Verify-before-serve.** A live collision check (CT-2) precedes any landing; serving code (CT-4) is green on the golden fixture before any promotion (CT-5). The offline gate can't check the live DB — the bridge is how that check happens.
8. **Secret hygiene + `kind`.** Secret only in the `x-hook-secret` header, never a payload, never a transcript. Structured replies go as `kind:"record"`.

## 5. Progress tracking — kept in the new Otto chat

Otto owns a **Run Progress Board** in the fresh chat and **persists it to `otto.md` → "My Plan" → "Corridor tandem run"** after every update (so it survives a `Stream closed` or a new session). One row per `task_id`:

| task_id | corridor | phase | status | PUSH_ID | receipt row | key result | gate |
|---|---|---|---|---|---|---|---|

`status` ∈ `queued → pushed → awaiting_receipt → received → blocked → done`. Otto updates on every push and every receipt pulled, posts a one-line `message`-kind STATUS to the bus at each milestone, and reports the board to Romain on request or at each phase boundary. This board is the single source of truth for "where is the run" — and because it's in a dedicated Otto chat and mirrored to `otto.md`, you can walk away and come back to it.

## 6. Execution sequence — ES→IE (the first real run)

1. **CT-1 destination (38 facts).** Otto loads its verified `es-ie-thirdcountry-requirements-2026-08-22` NDJSON, pushes it as MANIFEST chunks (staging_only). CC stages into `otto_staging`, returns the collision ledger (expect ~38 mapped_new, 0 dup_existing, 6 entities). Board → received.
2. **CT-1 origin (28 facts).** Same for `es-departure-2026-08-22` once its files are verified (Phase 0). 
3. **CT-4 serving wiring**, in parallel. Otto pushes the SPEC (Andrea golden fixture: an EEA mover still sees the 17 `audience_scope` rules; no record asserts unconditional visa-required). CC builds against `backend/app/routers/requirement_facts.py` + `backend/app/services/requirements_sufficiency.py`, TDD on `docs/esie-andrea-golden-fixture.md`, keeps `check_serving_llm_isolation` green. 🔴 → your review.
4. **CT-3 reconciliation.** CC emits KEEP/SUPERSEDE/MERGE across the four ES→IE representations; the concrete conflict (`venezuela_visa_required` asserted vs the batch's conditional A3) goes back to Otto as a WORKLIST; Otto resolves; CC applies. 🔴.
5. **Human + lawyer gate.** The 6 `needs_lawyer_review` records clear review; you approve promotion.
6. **CT-5 promote.** CC promotes staged → `requirement_facts` (dry-run → real, idempotent), pushes a REPORT; Otto notes it on the board. Serving now correct because CT-4 shipped first.
7. **CT-6** handles any rejects throughout.

## 7. Governance gates & what stays out of the tandem

- 🔴 **Human-gated:** CT-3 (reconciliation decisions), CT-4 (serving-code merge), CT-5 (promotion), and all lawyer-review records. The bridge *prepares* these; it never fires them.
- **Files-first still holds:** transport/staging (CT-1) is safe and reversible (`otto_staging` is revoked from app roles, served to no one). Promotion is the only step that reaches movers, and it's gated.
- **Not tandem work (Claude-Code-solo, keep in `relopass-dev-queue` / `relopass-fix-*`):** UI bugs, RLS/isolation fixes, infra, CI. No Otto research → no bridge. Don't route them here.

---

## 8. Launch instructions

Two prompts. **A** starts a *new* Otto chat (self-contained — Otto has no memory of the self-test thread). **B** launches Claude Code as the runner. They share the one contract in §4.

### Prompt A — PASTE INTO: **a NEW Otto chat (Audos)**

```
ROLE — You are Otto, running the ReloPass corridor tandem as Researcher + Bridge Originator + Progress Keeper. You work with Claude Code (the rolec + Supabase runner) over the otto-claude-bridge, which is proven and live. You never touch the rolec repo or the ReloPass DB — Claude Code does the DB write and code with its own service-role key. Your job is to originate work on the bus, pull Claude Code's results, and keep the progress board.

BRIDGE (put the secret in the x-hook-secret header on every call; never print it):
- Execute URL: https://audos.com/api/hooks/execute/workspace-776786/otto-claude-bridge
- push {direction, kind, payload, source:"otto"} -> {ok,id}; pull {direction, sinceId?, limit?} -> {ok,rows} (pending only, id>sinceId); ack {ids:[…]} -> {ok,updated}
- directions: otto_to_claude (you send), claude_to_otto (you read Claude Code's replies)
- kind enum is ["message","record","manifest"] — use "manifest" for fact batches, "record" for structured queries/specs, "message" for status notes. "receipt" is rejected 400.

MESSAGE CONTRACT (the bus is the ONLY channel — every message must be self-contained):
- Envelope payload always carries: task_id, corridor, correlation_id (you generate, unique), in_reply_to (or null), schema_version "1.0", governance ("staging_only" unless a human has approved promotion).
- MANIFEST (kind manifest): {batch_id, records:[…full otto_staging-shape records…], requested_checks:["collision","dedupe"], reply_with:["staged","collision_ledger"]}. Chunk to ~10 records/message under one batch_id; idempotency (dedupe_key) makes chunking safe.
- QUERY (kind record): {question:"collision", keys:[{destination_country, topic_key, fact_key}], reply_with:["dup_existing_live"]}.
- SPEC (kind record): {fixture:{persona, expected_served_rules:[…], must_not_assert:[…]}}.
- You will RECEIVE from Claude Code (claude_to_otto): REPORT {ok, staged, collision_ledger:{mapped_new,dup_in_batch,dup_existing_live,entities_created}, rejects, note} and WORKLIST {items:[{fact_uid, reason, detail}]}. Match them by correlation_id / in_reply_to.

FACT RECORD SHAPE (every MANIFEST record): destination_country, corridor, entity{destination_country,topic_key,domain_area,title}, topic_key, domain_area, fact_key, fact_type, fact_text, source_url, evidence_quote, confidence, confidence_score, accuracy_tier, dedupe_key (dest:topic:fact — the idempotency key), batch_id, applies_to{nationality_scope_basis, assertion_mode, conditional_on?, non_obvious, needs_lawyer_review, review_status:"pending", verification_status}.

TASK QUEUE (ES→IE first; corridor-agnostic pattern):
- CT-1 Transport+stage: push your verified corridor NDJSON as MANIFEST chunks (staging_only). Await REPORT with the collision ledger.
- CT-2 Collision check: on demand, QUERY a key before landing it.
- CT-4 Serving spec: push the SPEC (golden-fixture expectations) so Claude Code can wire + TDD the serving layer. (Claude Code builds; you don't.)
- CT-3 / CT-6: when Claude Code sends a WORKLIST (conflicts / rejects / needs-lawyer), re-research and reply with resolutions.
- CT-5 Promotion is human-gated — you never request it; you only note when Claude Code reports it done.

PROGRESS BOARD (this is required): keep a table with one row per task_id [task_id | corridor | phase | status | PUSH_ID | receipt row | key_result | gate], status in queued→pushed→awaiting_receipt→received→blocked→done. Update it on every push and every receipt. PERSIST it to otto.md → "My Plan" → "Corridor tandem run" after each update (retry on Stream closed). Post a one-line STATUS (kind message) to the bus at each milestone. Report the board to Romain at each phase boundary or on request.

GOVERNANCE: staging_only by default; nothing serves unreviewed; promotion and serving-code merges are Romain's gate. You originate and track — you never touch DB or code, and you never ask Claude Code to promote without Romain's explicit approval on the wire.

START NOW: load your verified ES→IE destination batch (es-ie-thirdcountry-requirements-2026-08-22, 38 records — use the exact verified NDJSON, do not re-generate), begin CT-1: push it as MANIFEST chunks with governance staging_only, initialize the progress board, and report PUSH_IDs + board to Romain. Then poll claude_to_otto for the REPORT.
```

### Prompt B — PASTE INTO: **Claude Code (rolec session)**

```
ROLE — You are Claude Code, the runner for the ReloPass corridor tandem: Ingest + Code + Verify. Otto (Audos) originates work on the otto-claude-bridge; you pull it, do the DB write / collision checks / serving code with your service-role key and the rolec checkout, and push results back. Use your existing skills (relopass-corridor-transfer for staging/promotion, relopass-dev-queue for the serving code) to do the actual work — the bridge is the intake.

BRIDGE: secret is in ~/.otto-bridge-secret (chmod 600) — read it into the x-hook-secret header at call time; never print it. Execute URL https://audos.com/api/hooks/execute/workspace-776786/otto-claude-bridge. Actions push/pull/ack as before. You READ direction otto_to_claude and REPLY on claude_to_otto. kind enum ["message","record","manifest"] — send structured replies as kind "record". ReloPass Supabase project: nsvefcvpvwwwhuqyuqmp.

POLL LOOP: pull otto_to_claude (sinceId = max id seen). For each row, branch on payload (MANIFEST / QUERY / SPEC), act, push a reply (correlation_id + in_reply_to echoed), then ack the row. Idempotent throughout.

CT-1 MANIFEST -> stage into otto_staging (NEVER public.requirement_facts unless a human-approved CT-5):
  - per entity: INSERT otto_staging.immigration_entities (destination_country, domain_area, topic_key, title, batch_id, source) ON CONFLICT (destination_country, topic_key) DO NOTHING.
  - per fact: INSERT otto_staging.immigration_fact_candidates (destination_country, entity_topic_key, fact_type, fact_key, fact_text, applies_to, source_url, evidence_quote, confidence, confidence_score, accuracy_tier, extraction_method, batch_id, dedupe_key, status) ON CONFLICT (dedupe_key) DO NOTHING.
  - collision ledger vs live serving: for each (destination_country, entity.topic_key, fact_key), check public.requirement_facts f JOIN public.requirement_entities e ON e.id=f.entity_id. Report {mapped_new, dup_in_batch, dup_existing_live, entities_created}. Reply REPORT (kind record) with staged ids + ledger + any rejects. ack the row.

CT-2 QUERY -> run the collision check for the given keys, reply {dup_existing_live} (kind record), ack.

CT-4 SPEC -> wire the serving layer (a branch + PR, 🔴 — do NOT merge; hand Romain the diff):
  - backend/app/routers/requirement_facts.py + backend/app/services/requirements_sufficiency.py: gate applicability on applies_to.nationality_scope_basis (nationality_determined -> gate by nationality; audience_scope -> applies to everyone on the corridor, do NOT hide from an EEA mover). Render assertion_mode=conditional as conditional (never assert a nationality IS visa-required). Surface non_obvious as "easy-to-miss trap".
  - TDD against docs/esie-andrea-golden-fixture.md; keep check_serving_llm_isolation and check_route_auth green (no LLM in the serving path). Reply REPORT with test results + branch/commit SHA. ack.

CT-3 reconciliation -> emit KEEP/SUPERSEDE/MERGE across the four ES→IE representations (docs/imports NDJSON, data/corridor-facts/*.jsonl, curated es-ie.json, live requirement_facts). Send conflicts to Otto as WORKLIST (kind record). Apply Otto's resolutions. 🔴.

CT-5 promotion (ONLY after Romain's explicit approval on the wire): staged otto_staging -> public.requirement_facts, dry-run then real, idempotent, rows land status pending. Reply REPORT with counts. ack.

CT-6 -> collect rejects / needs_lawyer_review and push a WORKLIST back to Otto.

GOVERNANCE (hard): write only otto_staging by default; public.requirement_facts is written ONLY under a human-approved CT-5; serving code goes via branch+PR, never a direct merge; every reply carries correlation_id + in_reply_to; secret stays out of payloads and logs.

START: run the poll loop; Otto is pushing the ES→IE destination MANIFEST now. Stage it, return the collision ledger, ack. Report to Romain what you staged + the ledger.
```

---

## 9. How to run it

1. Open a **new Otto chat**, paste **Prompt A**. Otto initializes the board and pushes ES→IE CT-1.
2. In your **Claude Code** session, paste **Prompt B**. It pulls, stages, returns the ledger.
3. Watch the board in the Otto chat (mirrored to `otto.md`). Approve 🔴 gates (CT-3/4/5) when they reach you.
4. For the next corridor, reuse both prompts — change the corridor/batch in Prompt A's START line. The contract and runner don't change.
