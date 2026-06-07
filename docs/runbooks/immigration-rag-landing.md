# Immigration RAG (N1–N4) — landing & prod-ops runbook

End-to-end steps to ship the immigration RAG feature (crawl → corpus → retrieval
gates → grounded answers). Everything is built and PR'd; this is the land + verify
sequence. The whole feature is **additive and fail-safe** — endpoints are
authenticated and refuse cleanly when corpus/keys are absent, so partial rollout
never breaks existing surfaces.

## 1. Merge order

Already merged to `main`: **W1/W2/W3, N1 #413, N2 #420, N3 #421**.

Open PRs:
| PR | What | Tier | Notes |
|----|------|------|-------|
| #424 | N4 — answer engine + `POST /api/immigration/answer` | 🔴 Red | human review, then merge |
| #423 | N2 follow-up — indexer CLI | chore | independent; merge anytime |

Both branch off `main` and are independent — any order. #424 is the human gate.

## 2. Render env vars (backend service)

| Var | Why | Without it |
|-----|-----|------------|
| `OPENAI_API_KEY` | corpus embeddings (`text-embedding-3-small`, 1536-dim) | indexer falls back to **hash** embeddings that **mismatch** the retriever → don't run it |
| `ANTHROPIC_API_KEY` | answer generation (`claude-sonnet-4-6`) | `/answer` still works but always **refuses** (fails safe) |
| `IMMIGRATION_MIN_SIMILARITY` | optional retrieval floor (default `0.25`) | uses default |

## 3. Post-merge: index the FR_NO corpus (prod only)

US→FR and IN→DE already serve retrieval (curated corpus migrated in N2). FR_NO was
crawled (N1) but its chunks must be embedded **where `OPENAI_API_KEY` exists**:

```bash
# On Render (after #423 merges, which adds the CLI):
python -m backend.app.services.immigration_chunk_indexer --corridor FR_NO
# Idempotent. Warns if it ran with hash embeddings (i.e. key missing).
```

Verify: `SELECT corridor, count(*) FROM immigration_corpus_chunks GROUP BY 1;`
→ expect `US_FR`, `IN_DE`, and (after the run) `FR_NO` all > 0.

## 4. Smoke tests (prod)

```bash
# Retrieval (W1) — should return chunks for a covered corridor:
curl -X POST https://api.relopass.com/api/immigration/retrieve \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"corridor_from":"US","corridor_to":"FR","nationality":"American","permit_type":"long_stay_visa","is_eea":false}'
# expect 200, chunks non-empty, corpus_empty=false

# Answer (N4) — grounded + cited:
curl -X POST https://api.relopass.com/api/immigration/answer \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"corridor_from":"US","corridor_to":"FR","nationality":"American","permit_type":"long_stay_visa","is_eea":false,"query":"What documents are required?"}'
# expect 200, answer_kind="answer", cited_sources>=1, [source: ...] in answer_text,
#        all_stale_warning present, trace_id present

# Answer with no corpus → safe refusal, no LLM spend:
curl ... -d '{"corridor_from":"ZZ","corridor_to":"XX","nationality":"X","permit_type":"work","is_eea":false,"query":"x"}'
# expect answer_kind="refusal_insufficient_context", cost_usd=0
```

Trace check: `SELECT feature_key, created_at FROM policy_assistant_traces
WHERE feature_key='immigration_answer' ORDER BY created_at DESC LIMIT 1;`

## 5. Rollback

Low blast radius — the three immigration endpoints are new and additive. To disable,
revert the router registration (remove `immigration_retrieve` / `/answer` route) or
revert the PR; no existing endpoint or schema is modified by N3/N4. N1/N2 tables are
additive and unused by other features.

## 6. Outstanding

- 🔐 **Revoke the leaked `github_pat_…` token** (in this session's scrollback).
- Optional: schedule the crawler (`immigration_crawl_job --corridor <key>`) on a cadence to refresh sources (it respects robots.txt + `crawl_interval_days`).
