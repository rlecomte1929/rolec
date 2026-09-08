# Bridge Value Self-Test — ES→IE one-fact live round-trip

**Date:** 2026-08-22 · **Author:** Claude (Cowork) · **Owner:** Romain
**Goal:** Prove, with the smallest possible *real* case, that the `otto-claude-bridge` adds value to ReloPass development — by running the exact corridor-transfer hop that is otherwise blocked.
**Status:** ✅ **PASSED — 2026-08-22.** Two-way round-trip proven end to end; workspace torn down clean. Full result log in §7.

---

## 1. Why this is the right test

Today's `ES-IE_Corridor_Landing_Engineering_Plan` has a hard wall at **Phase 4 (promote into the DB)**. Appendix C spells it out:

```
POST https://<project>.supabase.co/functions/v1/otto-loader
  header  x-otto-token: <OTTO_LOADER_TOKEN>   # founder-held; not in this workspace
```

Otto cannot promote a single fact into ReloPass because the production loader needs the **founder-held `OTTO_LOADER_TOKEN`**, plus a GCS upload and the `otto-loader` edge function. That is the "Bridge B / 401 dead end." It is why corridor research piles up as *files* and stalls before it becomes *served product behaviour*.

The bridge changes the topology:

```
BEFORE:  Otto → NDJSON file → [audos-sync git bot] → import_otto_facts.py (needs local DATABASE_URL)
                              └─ or → GCS + manifest → otto-loader edge fn (needs founder OTTO_LOADER_TOKEN) ✗ 401

AFTER:   Otto → push(manifest) → otto_claude_bridge → Claude pulls → Claude writes Supabase (its own service-role key)
                                                    ← push(receipt) ←  (live collision verdict Otto can't compute alone)
```

No founder token. No GCS. No otto-loader. And it is **two-way**, so Claude can hand a result *back* — the piece that was missing entirely before.

**What this one test proves in a single round-trip:**
1. A real, verified ES→IE fact moves from Otto into the ReloPass Supabase DB **with zero `OTTO_LOADER_TOKEN` / GCS / edge function**.
2. Claude returns a **live-DB collision verdict** (`dup_existing`) — the one check the *offline gate cannot do* (the plan calls this out explicitly; it needs a DB export today). Otto gets it on demand, per fact, over the bridge.
3. The return path works end-to-end (push → pull → ack), i.e. the "two-way" claim is real, not just outbound transport.

## 2. What this test deliberately does NOT do (governance stays intact)

- It writes **only to `otto_staging`** — the schema that is `REVOKE`d from `anon`/`authenticated`, invisible to PostgREST, served to no user. It is the *real* first landing zone (`import_otto_facts.py` stages there), so the hop is real — but nothing reaches a mover.
- It does **not** promote to `public.requirement_facts` / `requirement_entities`. Serving stays behind the human + lawyer gate (`review_status: pending`, `representative`). The bridge accelerates *transport*, not *governance*.
- The staged row is tagged `batch_id = "bridge-selftest-2026-08-22"` and a `:bridgetest` dedupe key, so teardown is one DELETE. `main` is never touched; git is never touched.
- The fact chosen (CSEP needs no Labour Market Needs Test) is public, structural, `needs_lawyer_review: false`, `non_obvious: false` — the safest record in the batch.

---

## 3. PROMPT A — paste this to Otto

> Copy everything in the box to Otto.

```
TASK — Bridge value self-test: one-fact live round-trip (ES→IE), staging-only, reversible.

You built the otto-claude-bridge hook (push / pull / ack, secret-gated, table otto_claude_bridge,
execute URL https://audos.com/api/hooks/execute/workspace-776786/otto-claude-bridge). We are proving
it adds real value by running the smallest REAL ReloPass corridor-transfer hop through it — the exact
hop otherwise blocked because the production loader needs the founder-held OTTO_LOADER_TOKEN this
workspace does not have.

This moves ONE real, verified ES→IE fact into ReloPass's staging schema (otto_staging — revoked from all
app roles, served to no one) via the bridge, and gets back from Claude a live-DB collision verdict you
cannot compute yourself. Nothing is promoted to serving tables. The row is deletable by its test batch_id.

Use your bridge's own push/pull/ack action dispatch (whatever field you implemented — action/op/etc.).
Put the bridge secret in the x-hook-secret header on every call. Do NOT print the secret.

STEP 1 — correlation id.
  corr = "bridge-selftest-" + <compact current UTC timestamp>   (e.g. bridge-selftest-20260822T1330Z)

STEP 2 — PUSH the manifest (direction otto_to_claude, kind manifest, source otto). Payload verbatim,
substituting your corr:

{
  "test": true,
  "purpose": "bridge value self-test — staging-only, reversible",
  "correlation_id": "<corr>",
  "corridor": "ES-IE",
  "batch_id": "bridge-selftest-2026-08-22",
  "target_staging_schema": "otto_staging",
  "governance": "STAGING ONLY — do NOT promote to public.requirement_facts; review_status pending; representative",
  "requested_checks": ["live_requirement_facts_collision", "otto_staging_dedupe"],
  "reply_with": ["staged_entity_id","staged_fact_candidate_id","dup_existing_live","mapped_new","staging_count_before","staging_count_after"],
  "record": {
    "target_table": "requirement_facts",
    "destination_country": "IE",
    "corridor": "ES-IE",
    "topic_key": "ES-IE:thirdcountry:immigration_work_authorization",
    "domain_area": "immigration",
    "entity": {
      "destination_country": "IE",
      "topic_key": "ES-IE:thirdcountry:immigration_work_authorization",
      "domain_area": "immigration",
      "title": "Ireland - Immigration and work authorisation (third-country professional)"
    },
    "fact_key": "csep_no_labour_market_needs_test",
    "fact_type": "eligibility",
    "name_en": "Critical Skills permit needs no Labour Market Needs Test",
    "fact_text": "A non-EEA professional whose occupation sits on the Critical Skills Occupations List does NOT need the employer to run a Labour Market Needs Test. This is the structural advantage of the Critical Skills Employment Permit (CSEP) over the General Employment Permit, which does require the test and the 4-week advertising cycle it brings.",
    "source_url": "https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/",
    "source_name": "DETE - Critical Skills Employment Permit",
    "evidence_quote": "Because the skills are identified as being in short supply, a Labour Market Needs Test is not required.",
    "confidence_score": 0.9,
    "confidence": "high",
    "accuracy_tier": "representative",
    "required_fields": [],
    "last_verified_date": "2026-08-21",
    "dedupe_key": "ES-IE:thirdcountry:csep_no_labour_market_needs_test:bridgetest",
    "batch_id": "bridge-selftest-2026-08-22",
    "applies_to": {
      "corridor": "ES->IE",
      "nationality": "non-EEA",
      "status": "professional",
      "persona": "third-country professional relocating Madrid->Dublin",
      "fact_uid": "ES_IE:THIRD_COUNTRY:csep_no_labour_market_needs_test",
      "pillar": "RESIDENCE",
      "topic": "immigration_work_authorization",
      "non_obvious": false,
      "needs_lawyer_review": false,
      "review_status": "pending",
      "verification_status": "representative",
      "quote_verbatim_confirmed": true,
      "source_name": "DETE - Critical Skills Employment Permit",
      "batch_id": "bridge-selftest-2026-08-22",
      "nationality_scope_basis": "nationality_determined"
    }
  }
}

Record the returned id as PUSH_ID. Expect {ok:true, id:<n>}.

STEP 3 — POLL for Claude's receipt. Every 45s, up to 20 tries (~15 min), pull direction claude_to_otto
with sinceId = highest id you've seen (start 0). A receipt is a row whose payload.correlation_id === corr
(or payload.in_reply_to === PUSH_ID). Advance sinceId by the max id you see each poll.

STEP 4 — On receipt: verify it contains staged_entity_id, staged_fact_candidate_id, dup_existing_live,
mapped_new, staging_count_before, staging_count_after. Then ACK it: ack ids:[<receipt row id>].

STEP 5 — REPORT to Romain, compactly:
  • PUSH_ID + push latency
  • receipt arrived? after how many polls / minutes?
  • receipt values — especially dup_existing_live (0 = this fact is genuinely new to the live serving DB;
    1 = already served) and staging_count_before → staging_count_after (expect 0 → 1, mapped_new = 1)
  • ack result
  • one-line verdict: did the bridge move a real ES→IE fact into the ReloPass DB with no OTTO_LOADER_TOKEN /
    GCS / otto-loader, AND return a live check you could not run yourself? Yes/No + one sentence why.

If no receipt after ~15 min, do NOT spin. Report that the push succeeded (PUSH_ID) and the ingest half
(Claude Code) has not run yet — the bridge is a durable queue, so the receipt will be waiting whenever
Claude next runs and we can re-poll. Stop there.

CONSTRAINTS
  • Staging only. You have no DB write path and must not seek one — the point is that CLAUDE does the DB
    write with its service-role key. Do not touch public.requirement_facts / requirement_entities.
  • Do not print the bridge secret. Touch nothing else in the workspace.
```

---

## 4. PROMPT B — paste this to Claude Code (closes the loop)

> Run this in your Claude Code session (it has the ReloPass Supabase service-role key + the bridge secret). This is the ingest half. Claude can also run it from Cowork on request.

```
TASK — Close the bridge self-test: pull Otto's manifest, live-collision-check, stage into otto_staging,
post the receipt.

Otto pushed a self-test manifest through otto-claude-bridge (direction otto_to_claude, kind manifest,
payload.test === true, payload.correlation_id starts "bridge-selftest-"). You have the ReloPass Supabase
service-role key and the bridge secret (otto.md → My Plan → "Otto ↔ Claude bridge"). Execute URL:
https://audos.com/api/hooks/execute/workspace-776786/otto-claude-bridge, header x-hook-secret.

1. PULL direction otto_to_claude. Find the pending row with payload.test === true and
   payload.correlation_id starting "bridge-selftest-". Keep: bridge_row_id, corr, PUSH_ID, and payload.record.

2. LIVE collision check against ReloPass Supabase (service-role):
     SELECT 1 FROM public.requirement_facts f
       JOIN public.requirement_entities e ON e.id = f.entity_id
      WHERE e.destination_country = 'IE'
        AND e.topic_key = 'ES-IE:thirdcountry:immigration_work_authorization'
        AND f.fact_key = 'csep_no_labour_market_needs_test'
      LIMIT 1;
   dup_existing_live = 1 if any row, else 0.

3. staging_count_before =
     SELECT count(*) FROM otto_staging.immigration_fact_candidates
      WHERE batch_id = 'bridge-selftest-2026-08-22';     -- expect 0

4. STAGE (mirror import_otto_facts stage()):
   -- entity
   INSERT INTO otto_staging.immigration_entities
     (destination_country, domain_area, topic_key, title, batch_id, source)
   VALUES ('IE','immigration','ES-IE:thirdcountry:immigration_work_authorization',
           'Ireland - Immigration and work authorisation (third-country professional)',
           'bridge-selftest-2026-08-22','otto_research')
   ON CONFLICT (destination_country, topic_key) DO NOTHING
   RETURNING id;   -- staged_entity_id (on conflict, SELECT the existing id)

   -- fact candidate (values from payload.record)
   INSERT INTO otto_staging.immigration_fact_candidates
     (destination_country, entity_topic_key, fact_type, fact_key, fact_text, applies_to,
      source_url, evidence_quote, confidence, confidence_score, accuracy_tier,
      extraction_method, batch_id, dedupe_key, status)
   VALUES ('IE','ES-IE:thirdcountry:immigration_work_authorization','eligibility',
           'csep_no_labour_market_needs_test', <record.fact_text>, <record.applies_to::jsonb>,
           <record.source_url>, <record.evidence_quote>, 'high', 0.9, 'representative',
           'otto_research','bridge-selftest-2026-08-22',
           'ES-IE:thirdcountry:csep_no_labour_market_needs_test:bridgetest','new')
   ON CONFLICT (dedupe_key) DO NOTHING
   RETURNING id;   -- staged_fact_candidate_id

5. staging_count_after = recount (expect 1). mapped_new = after - before.

6. PUSH receipt: direction claude_to_otto, kind receipt, source claude, payload:
   { correlation_id: corr, in_reply_to: PUSH_ID, ok: true,
     staged_entity_id, staged_fact_candidate_id, dup_existing_live, mapped_new,
     staging_count_before, staging_count_after,
     note: "staged in otto_staging only; not promoted to serving (human/lawyer gate)" }

7. ACK the original otto_to_claude manifest row: ack ids:[bridge_row_id].

8. Report the same values to Romain.

TEARDOWN (after Romain confirms he has seen the proof):
   DELETE FROM otto_staging.immigration_fact_candidates WHERE batch_id = 'bridge-selftest-2026-08-22';
   DELETE FROM otto_staging.immigration_entities        WHERE batch_id = 'bridge-selftest-2026-08-22';

GUARDRAILS: write ONLY to otto_staging. Do NOT write public.requirement_facts / requirement_entities —
serving stays governed by the human + lawyer gate.
```

---

## 5. How to read the result (the scorecard)

| Signal | Pass looks like | What it proves |
|---|---|---|
| `push` → PUSH_ID | `{ok:true, id:n}` in < 1s | Otto → ReloPass DB transport works with no founder token |
| `staging_count` 0 → 1, `mapped_new = 1` | one real fact landed in `otto_staging` | the *real* first-stage of the promotion pipeline ran over the bridge |
| `dup_existing_live` = 0 or 1 | a definite verdict comes back | Claude gave Otto a **live-DB check the offline gate cannot do** |
| receipt pulled + `ack` ok | round-trip closes | the bridge is genuinely **two-way**, durable, idempotent |

If all four are green, the bridge has done — in one 30-second round-trip, credential-free on Otto's side — the thing that Phase 4 of the ES→IE plan otherwise cannot do at all.

## 6. Where this goes next (if the test passes)

- **Collapse Phase 4** for real batches: Otto pushes the 38 ES→IE destination facts as a manifest; Claude stages + reports the collision ledger; promotion to serving still waits for the lawyer gate — but the *transport* stops needing the founder token.
- **Live collision-as-a-service**: Otto asks the bridge for `dup_existing` per fact before it even files a batch (kills the "stale export" risk in Phase 3).
- **Return-path worklists**: Claude posts the `reject list` / `needs re-sourcing` rows back over the bridge; Otto re-researches. The import script already calls the reject list "the re-sourcing worklist" — the bridge closes that loop automatically.

---

## 7. RESULT — PASSED (2026-08-22)

The test ran end to end and every claim was verified against ReloPass prod (`nsvefcvpvwwwhuqyuqmp`). Three parties acted across the secret-gated seam: **Otto** (push / poll / ack on the bus), **Claude (Cowork)** (the real Supabase service-role write + live collision check), and **Claude Code** (independent re-verification against prod + the return-leg push).

**Round-trip proven:** Otto → bus (push, row 5, `otto_to_claude` / `manifest`) → Claude ingest wrote `otto_staging` on ReloPass prod via service-role → receipt (push, row 6, `claude_to_otto`) → Otto (pull → verify → ack). **No `OTTO_LOADER_TOKEN`, no GCS, no otto-loader anywhere in the path** — exactly the hop the production loader otherwise blocks.

| Field | Value | Verified |
|---|---|---|
| PUSH_ID — manifest (`otto_to_claude`) | 5 | ✅ acked; left the pending queue |
| Receipt row (`claude_to_otto`) | 6 | ✅ pulled + acked by Otto |
| correlation_id | `bridge-selftest-20260822T0833Z` | ✅ |
| staged_entity_id | `b7bcaaaa-1070-484d-8670-9d7b14d6539f` | ✅ exact match in prod |
| staged_fact_candidate_id | `8ed5f4c8-ba75-405b-bae2-5ca4e8e6e299` | ✅ exact match in prod |
| dup_existing_live | 0 | ✅ fact + topic entity absent from `public.requirement_facts` — genuinely new |
| staging_count 0 → 1 (`mapped_new`) | 1 | ✅ |
| IE live facts (context) | 130 | ✅ unchanged by the test |

**Independent verification:** Claude Code `SELECT`-checked every receipt field against prod *before* it went on the wire — all matched.

**Governance held:** nothing promoted to `public.requirement_facts`; `review_status: pending` / `representative`; `main` and git untouched.

**Teardown:** `otto_staging` batch `bridge-selftest-2026-08-22` deleted — 1 fact + 1 entity removed; batch recount **0 / 0**; serving still shows **0** for the fact and **130** IE facts total. Clean.

**Findings for operationalizing the bridge:**
1. The Claude-side ingest runner must live where **both** `audos.com` and the ReloPass DB are reachable. Cowork reaches the DB but is egress-blocked from `audos.com` (403 at the proxy); the device-bridge shell is too. **Claude Code is the runner** — secret stored at `~/.otto-bridge-secret` (chmod 600).
2. The bridge `kind` enum is `["message","record","manifest"]` — `"receipt"` is rejected `400 invalid_kind`. Use **`kind: "record"`** for structured replies going forward.
3. The bus is a durable queue: rows persist `pending` until acked, so the two halves need not run simultaneously.

**Next payoff:** the real 38-fact ES→IE destination batch can now be carried over this same path (Otto pushes the manifest → Claude Code stages all 38 + returns the collision ledger), with promotion to serving still gated by lawyer review.
